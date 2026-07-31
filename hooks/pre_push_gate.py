"""Universal pre-push gate - never push source your tests have not seen.

Installed as .git/hooks/pre-push in any repo (`--install`), so it is git that enforces it, not a
model. It closes the hole fast_test_on_stop leaves open: it debounces, so a passing run
followed by 29 more minutes of edits ends the turn silently and that work reaches the remote
unverified. Silence and success look identical from outside; this makes them different at the one
moment it matters.

Mechanical by design (no reasoning):
  1. command = <project>/.claude/pre-push.cmd if present, else fast_test_on_stop's own detect()
     (same file format: line1 = command, optional "timeout=N"). A project can therefore run a
     STRICTER gate at push time than at turn end - pushes are rare, turns are not.
  2. no command detectable  -> say so, ALLOW the push (a repo with no tests has nothing to gate)
  3. fast_test_on_stop already recorded a PASS for this same command, newer than the newest source file
                            -> ALLOW instantly, costing one stat() sweep and no test run
  4. otherwise             -> run the command now; non-zero BLOCKS the push
  5. timeout               -> warn loudly, ALLOW (a timeout is a config problem, not a red test)

A fresh pass here updates fast_test_on_stop's state file: same command, same meaning, one source of truth.
Bypass at any time with `git push --no-verify`. Run with --selftest to verify the mechanics.

Coverage: `--install-global` points git's core.hooksPath at ~/.claude/githooks, so EVERY repo is
gated - including ones that do not exist yet - with no per-repo install to remember. Per-repo
`--install` still exists for the rare repo that sets its own local core.hooksPath (husky, lefthook),
because a LOCAL core.hooksPath silently beats the global one and would otherwise drop the gate.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import time

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

import fast_test_on_stop as fast_test  # noqa: E402  (path set above; it owns detect/state/SRC_EXT)

SHIM = """#!/bin/sh
# Universal pre-push gate - managed by ~/.claude/hooks/pre_push_gate.py
# Bypass once with: git push --no-verify
exec "{py}" "{script}" "$@"
"""


# git speaks UTF-8 on every platform. Decoding its output with the process locale codec (the
# `text=True` default, cp1252 on a Western Windows install) turns `C:\Users\José\dev` into a
# path that does not exist - so resolve_command found nothing there and the gate announced
# "no test command - nothing to verify", which reads exactly like a healthy skip. surrogateescape
# rather than replace: it round-trips back through os.* on POSIX instead of corrupting the name.
_GIT_TEXT = {"encoding": "utf-8", "errors": "surrogateescape"}


def _git(args: list, timeout: int = 30):
    """Run git with a fixed codec. Returns the CompletedProcess, or None if git could not run."""
    try:
        return subprocess.run(["git"] + args, capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL, **_GIT_TEXT)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _repo_root(start: str) -> str | None:
    r = _git(["-C", start, "rev-parse", "--show-toplevel"], timeout=10)
    if r is None or r.returncode != 0:
        return None
    root = (r.stdout or "").strip() or None
    # A decoded path that does not exist is an UNANSWERED question, not "this repo has no
    # tests". Without this check a mis-decoded root produced a confident, wrong all-clear.
    if root and not os.path.isdir(root):
        return None
    return root


def _common_git_dir(target: str) -> str | None:
    """The repo's real .git directory - shared by every linked worktree, submodule-aware.

    NOT `--git-path hooks`: when core.hooksPath is set (which is exactly when the global
    dispatcher runs) git answers that with the hooksPath itself, so it can never point at a
    repo's own hooks. Measured on this machine 2026-07-29: in both a plain repo and a linked
    worktree it returned ~/.claude/githooks. `--git-common-dir` is unaffected by hooksPath and
    resolves a linked worktree to the HOST repo's .git, which is where the hooks actually live.
    """
    r = _git(["-C", target, "rev-parse", "--git-common-dir"], timeout=10)
    if r is None or r.returncode != 0:
        return None
    d = (r.stdout or "").strip()
    if not d:
        return None
    if not os.path.isabs(d):
        root = _repo_root(target)
        d = os.path.join(root or target, d)
    return os.path.normpath(d)


def resolve_command(root: str) -> tuple[str | None, int]:
    """(command, timeout_s): a push-time override if the project has one, else fast_test_on_stop's own choice."""
    ov = os.path.join(root, ".claude", "pre-push.cmd")
    if os.path.exists(ov):
        # PUSH_OPTIONS, not the turn-end table: a push may legitimately take longer than a
        # turn end, and sharing one ceiling silently clamped `timeout = 1800` to 600 (P13 D5).
        cmd, timeout_s, _ = fast_test._read_override(ov, fast_test.PUSH_OPTIONS)
        if cmd:
            return cmd, timeout_s
    cmd, timeout_s, _ = fast_test.detect(root)
    return cmd, timeout_s


# A push-time gate must err toward re-running: an over-broad gate costs one extra test run, an
# under-broad one costs an unverified push. So this is a DENYlist, not the allowlist
# fast_test_on_stop uses at turn end. The allowlist made a repo whose source is .sh/.sql/.tf -
# or one where only a migration and a deploy script changed - short-circuit to
# "no source touched since" while shipping broken code (findings 2 and 12).
NON_SOURCE_EXT = frozenset({
    ".md", ".markdown", ".rst", ".txt", ".adoc", ".org",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp", ".tif", ".tiff",
    ".pdf", ".mp4", ".mov", ".mp3", ".wav", ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".gz", ".bz2", ".xz", ".tar", ".7z", ".rar", ".jar", ".whl",
    ".log", ".map", ".min.js", ".min.css",
})


def newest_source_mtime(root: str) -> tuple[float | None, str | None]:
    """(mtime, path) of the most recently modified non-ignored source file.

    Returns (None, reason) when the question CANNOT be answered. That third state is the whole
    point: git failing (locked index, corrupt repo, a concurrent git, an unreadable tree) used
    to return the same (0.0, None) as "nothing here", so any recorded pass beat it and the gate
    announced "verified - no source touched since" over failing, unverified code (findings 3,
    11). An unanswerable question must never resolve to the same value as "answered, nothing
    changed" - the caller runs the tests instead.
    """
    # -z disables C-quoting outright: git renders `données.py` as "donn\303\251es.py" by
    # default, which no os.path call can open, so an edit to it was invisible and the gate
    # reported a verified tree (finding 4). -z also makes newline-in-filename safe.
    r = _git(["-C", root, "ls-files", "-cmo", "--exclude-standard", "-z"])
    if r is None:
        return None, "<git could not be run>"
    if r.returncode != 0:
        return None, "<git ls-files failed>"

    import errno
    newest, where, unreadable = 0.0, None, 0
    for rel in set((r.stdout or "").split("\0")):
        if not rel:
            continue
        if os.path.splitext(rel)[1].lower() in NON_SOURCE_EXT:
            continue
        try:
            m = os.path.getmtime(os.path.join(root, rel))
        except OSError as e:
            # ENOENT is ordinary: `-c` lists tracked files, including ones deleted from the
            # working tree. Anything else means the scan did NOT see the whole tree, and a
            # file the gate cannot stat is a reason to verify, not a reason to skip.
            if getattr(e, "errno", None) != errno.ENOENT:
                unreadable += 1
            continue
        except ValueError:
            unreadable += 1
            continue
        if m > newest:
            newest, where = m, rel
    if unreadable:
        return None, "<%d path(s) could not be read>" % unreadable
    return newest, where


def last_pass(root: str, cmd: str) -> float:
    """Timestamp of fast_test_on_stop's last recorded PASS for this exact command, else 0.0.

    Every field is treated as hostile. A non-object or a non-numeric `ts` - a partial write, an
    unrelated tool sharing $UNBLUFF_STATE_DIR, a hand-edit - used to raise straight out of the
    hook, so git REFUSED every push in that repo with a bare traceback (finding 9).
    """
    try:
        with open(fast_test._state_path(root), encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return 0.0
    if not isinstance(st, dict):
        return 0.0
    if st.get("rc") != 0 or st.get("cmd") != cmd:
        return 0.0
    try:
        return float(st.get("ts") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _record_pass(root: str, cmd: str, secs: float) -> None:
    """Share the result with fast_test_on_stop so the two gates agree on what has been verified."""
    try:
        os.makedirs(fast_test.STATE_DIR, exist_ok=True)
        with open(fast_test._state_path(root), "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "rc": 0, "cmd": cmd, "secs": round(secs, 1)}, f)
    except OSError:
        pass  # advisory only - never fail a push because state could not be written


# The bounded runner lives in fast_test_on_stop: BOTH gates run a project's test command and
# both had the unbounded-pipe defect, and the import only goes one way. Re-exported here so
# call sites and tests read naturally.
run_tests = fast_test.run_tests
_kill_tree = fast_test._kill_tree


def gate(root: str) -> int:
    cmd, timeout_s = resolve_command(root)
    name = os.path.basename(root.rstrip("/\\")) or root
    if not cmd:
        sys.stderr.write(f"[pre-push] '{name}' has no test command - nothing to verify, allowing push.\n")
        return 0

    newest, where = newest_source_mtime(root)
    passed_at = last_pass(root, cmd)
    if newest is None:
        # Could not enumerate the tree. Re-run rather than trust a recorded pass.
        why = f"could not enumerate sources ({where}) - re-running to be safe"
    elif passed_at and passed_at > newest:
        age = int(time.time() - passed_at)
        # Name what was actually checked. The unqualified "no source touched since" was true
        # of .py and false of the deploy script the developer had just broken.
        sys.stderr.write(f"[pre-push] verified {age}s ago, no source touched since "
                         f"(docs/images excluded) - allowing push.\n")
        return 0
    elif where:
        why = f"'{where}' changed since the last passing run"
    else:
        why = "no passing run on record"

    sys.stderr.write(f"[pre-push] {why} - running: {cmd}\n")
    started = time.time()
    try:
        rc, output = run_tests(cmd, root, timeout_s)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        sys.stderr.write(f"[pre-push] WARNING: could not run tests ({e}). This push is NOT verified.\n")
        return 0

    if rc is None:
        sys.stderr.write(f"[pre-push] WARNING: tests exceeded {timeout_s}s and were killed. "
                         f"This push is NOT verified. Raise timeout= in .claude/pre-push.cmd.\n")
        return 0
    if rc != 0:
        tail = "\n".join(ln for ln in (output or "").splitlines() if ln.strip())[-2000:]
        sys.stderr.write(f"\n[pre-push] BLOCKED - tests are failing:\n{tail}\n"
                         f"\n[pre-push] Fix them, or bypass with: git push --no-verify\n")
        return 1
    _record_pass(root, cmd, time.time() - started)
    sys.stderr.write(f"[pre-push] tests passed in {time.time() - started:.0f}s - allowing push.\n")
    return 0


def _hooks_dir_for(target: str) -> tuple:
    """(directory git will ACTUALLY read hooks from, came_from_hooksPath).

    git honours `core.hooksPath` INSTEAD of `$GIT_DIR/hooks`, with no fallback: if it is set,
    nothing in .git/hooks ever runs again. install() wrote to <common-dir>/hooks regardless, so
    in a husky or lefthook repo it printed "installed ... gate command: npm test" and the repo
    was NOT gated - precisely the case install_global()'s own message prescribes --install for.

    Only the LOCAL setting is honoured. A GLOBAL core.hooksPath is what --install-global sets,
    and following it here would make --install write its shim into ~/.claude/githooks and
    clobber the dispatchers themselves.
    """
    r = _git(["-C", target, "config", "--local", "--get", "core.hooksPath"], timeout=10)
    if r is not None and r.returncode == 0:
        hp = (r.stdout or "").strip()
        if hp:
            if not os.path.isabs(hp):
                hp = os.path.join(_repo_root(target) or target, hp)
            return os.path.normpath(hp), True
    gitdir = _common_git_dir(target)
    return (os.path.join(gitdir, "hooks") if gitdir else None), False


def install(target: str, remove: bool = False) -> int:
    root = _repo_root(target)
    if not root:
        print(f"not a git repository: {target}")
        return 1
    # Ask git where its hooks live rather than assuming <root>/.git/hooks. In a linked worktree
    # .git is a FILE, so the old join crashed with FileNotFoundError/NotADirectoryError; in the
    # variant where the write succeeded it reported success for a path git never reads
    # (finding 6). A LOCAL core.hooksPath overrides that entirely and must win (D7).
    hooks_dir, via_hooks_path = _hooks_dir_for(target)
    if not hooks_dir:
        print(f"cannot resolve a git directory for {target}; use --install-global")
        return 1
    dest = os.path.join(hooks_dir, "pre-push")
    if remove:
        if os.path.exists(dest):
            os.remove(dest)
            print(f"removed {dest}")
        else:
            print(f"nothing installed at {dest}")
        return 0
    if os.path.exists(dest):
        with open(dest, encoding="utf-8", errors="replace") as f:
            if "pre_push_gate.py" not in f.read():
                print(f"REFUSED: a different pre-push hook already exists at {dest}")
                return 1
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(SHIM.format(py=sys.executable.replace("\\", "/"),
                            script=os.path.abspath(__file__).replace("\\", "/")))
    os.chmod(dest, 0o755)
    cmd, _ = resolve_command(root)
    where = " (this repo sets core.hooksPath, so .git/hooks is never read)" if via_hooks_path else ""
    print(f"installed {dest}{where}\n"
          f"  gate command: {cmd or '(none detected - will allow pushes and say so)'}")
    return 0


GLOBAL_HOOKS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "githooks")

# Every client-side hook git can fire. A dispatcher is installed for ALL of them - not just
# pre-push - because core.hooksPath REPLACES .git/hooks wholesale: any name missing from the
# global dir would silently stop firing in every repo that has one.
# FLOOR, not the roster - install_global() uses git_client_hook_names(), which unions this with
# whatever git itself ships samples for. The seven names after "post-index-change" were missing
# in v1.3.0, so --install-global silently killed any repo-local hook of those names.
CLIENT_HOOKS = ("applypatch-msg", "pre-applypatch", "post-applypatch", "pre-commit",
                "prepare-commit-msg", "commit-msg", "post-commit", "pre-rebase", "post-checkout",
                "post-merge", "pre-push", "post-rewrite", "pre-auto-gc", "push-to-checkout",
                "sendemail-validate", "post-index-change",
                "pre-merge-commit", "reference-transaction", "fsmonitor-watchman",
                "p4-changelist", "p4-prepare-changelist", "p4-post-changelist", "p4-pre-submit")

# Fired by a SERVER receiving a push, never by a client. git ships samples for some of them;
# installing dispatchers for them in a client-side hooks dir would be noise.
SERVER_HOOKS = frozenset({"pre-receive", "update", "proc-receive", "post-receive", "post-update"})

# Hooks git fires MANY TIMES per command - reference-transaction runs once per ref per
# transaction phase, so a 100-tag fetch invokes it 300+ times. Even a fork-free dispatcher
# multiplies by that count, and install_global() sets core.hooksPath GLOBALLY, so the cost is
# machine-wide and permanent. Measured on this machine before exclusion: git fetch 0.58s ->
# 106s. Excluded from the global install; a repo that genuinely needs one can wire it locally.
#
# Subtracted INSIDE git_client_hook_names(), NOT by removing it from CLIENT_HOOKS: that
# function UNIONS git's own *.sample list, so a name dropped from the tuple would come
# straight back. This is the same detect-don't-list trap as the twin rosters, one layer up.
HIGH_FREQUENCY_HOOKS = frozenset({"reference-transaction"})


def all_client_hook_candidates() -> set:
    """Every client-side hook name git knows, WITHOUT the cost-based exclusions subtracted.

    [P13 D8] git_client_hook_names() subtracts HIGH_FREQUENCY_HOOKS, so the selftest guard
    written to catch exactly this - `set(git_client_hook_names()) - set(CLIENT_HOOKS)` - was
    structurally incapable of ever seeing an excluded name: the exclusion happens on the LEFT
    of that difference. Reporting what was dropped has to start from the unsubtracted set.
    """
    names = set(CLIENT_HOOKS)
    r = _git(["--exec-path"], timeout=10)
    if r is None or r.returncode != 0 or not (r.stdout or "").strip():
        return names - SERVER_HOOKS
    exec_path = (r.stdout or "").strip()
    for rel in ("../../share/git-core/templates/hooks", "templates/hooks",
                "../../templates/hooks", "../../../share/git-core/templates/hooks"):
        d = os.path.normpath(os.path.join(exec_path, rel))
        if not os.path.isdir(d):
            continue
        try:
            for fn in os.listdir(d):
                if fn.endswith(".sample"):
                    names.add(fn[:-len(".sample")])
        except OSError:
            pass
        break
    return names - SERVER_HOOKS


def undispatched_hook_names() -> tuple:
    """Client hook names --install-global deliberately does NOT dispatch. Derived, never listed."""
    return tuple(sorted(all_client_hook_candidates() & HIGH_FREQUENCY_HOOKS))


def git_client_hook_names() -> tuple:
    """Client-side hook names git ITSELF knows about (its template dir's *.sample files).

    Detection, not a roster. CLIENT_HOOKS is a FLOOR and it has already drifted: seven names
    git fires were missing, so `--install-global` silently killed any repo-local hook of those
    names while its own message promised the opposite. A tuple cannot learn about a hook a
    future git adds; this can. Falls back to the floor when git cannot be asked.
    """
    names = set(CLIENT_HOOKS)
    try:
        r = subprocess.run(["git", "--exec-path"], capture_output=True, text=True, timeout=10,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError, ValueError):
        return tuple(sorted(names - SERVER_HOOKS - HIGH_FREQUENCY_HOOKS))
    exec_path = (r.stdout or "").strip()
    if r.returncode != 0 or not exec_path:
        return tuple(sorted(names - SERVER_HOOKS - HIGH_FREQUENCY_HOOKS))
    for rel in ("../../share/git-core/templates/hooks", "templates/hooks",
                "../../templates/hooks", "../../../share/git-core/templates/hooks"):
        d = os.path.normpath(os.path.join(exec_path, rel))
        if not os.path.isdir(d):
            continue
        try:
            for fn in os.listdir(d):
                if fn.endswith(".sample"):
                    names.add(fn[:-len(".sample")])
        except OSError:
            pass
        break
    return tuple(sorted(names - SERVER_HOOKS - HIGH_FREQUENCY_HOOKS))

# Runs the universal gate (pre-push only), then ALWAYS delegates to the repo's own hook of the
# same name, so project-specific hooks keep working. The gate reads no stdin (</dev/null), leaving
# git's ref list untouched for the repo-local hook that may actually need it.
# Runs the universal gate (pre-push only), then ALWAYS delegates to the repo's own hook of the
# same name, so project-specific hooks keep working. The gate reads no stdin (</dev/null),
# leaving git's ref list untouched for the repo-local hook that may actually need it.
#
# --git-common-dir, NOT --git-dir and NOT --git-path hooks:
#   * --git-dir resolves to .git/worktrees/<name> inside a LINKED WORKTREE, which has no hooks
#     directory, so every repo-local hook was silently skipped there for as long as the worktree
#     existed - a pre-commit secret scanner simply stopped running (finding 5).
#   * --git-path hooks looks right but answers with core.hooksPath whenever it is set, i.e.
#     always, since that is what makes this dispatcher run at all. Measured 2026-07-29: it
#     returned ~/.claude/githooks in both a plain repo and a worktree, so it would have
#     disabled delegation EVERYWHERE. --git-common-dir is immune to hooksPath.
# PERFORMANCE IS CORRECTNESS HERE. This runs for EVERY client hook in EVERY repo on the
# machine, and git fires some hooks once per ref. The first version forked `basename`, `git
# rev-parse` and `grep` on every single invocation: measured 0.58s -> 106s on a 100-tag fetch
# (312 invocations). The common case now forks NOTHING:
#   * ${0##*/} is a shell builtin, not `basename` - stripped for BOTH separators, because a
#     dispatcher invoked with a Windows path leaves backslashes in $0 and a /-only strip then
#     returns the whole path, so the hook name never matches and every hook silently no-ops
#     (caught by the selftest the moment the fork was removed)
#   * git exports GIT_DIR, so the usual repo needs no `rev-parse` at all
#   * the `-f` test short-circuits before `grep` when the repo has no hook of this name,
#     which is the overwhelmingly common case
# The rev-parse fallback survives ONLY for the linked-worktree case (finding 5): a worktree's
# GIT_DIR is .git/worktrees/<name>, which has no hooks dir, so we re-resolve to the common dir
# there and nowhere else.
GLOBAL_SHIM = """#!/bin/sh
# Universal git hook dispatcher - managed by ~/.claude/hooks/pre_push_gate.py
# 1. universal pre-push gate  2. this repo's own hook, if it has one (never overridden)
# Bypass once with: git push --no-verify
hook=${{0##*/}}
hook=${{hook##*\\\\}}
if [ "$hook" = "pre-push" ]; then
    "{py}" "{script}" < /dev/null || exit $?
fi
gitdir="$GIT_DIR"
if [ -z "$gitdir" ] || [ ! -d "$gitdir/hooks" ]; then
    gitdir=`git rev-parse --git-common-dir 2>/dev/null` || exit 0
fi
[ -n "$gitdir" ] || exit 0
local_hook="$gitdir/hooks/$hook"
[ -f "$local_hook" ] || exit 0
# Delegate to the repo's own hook - unless it is one of ours, which would run the gate twice.
grep -q pre_push_gate.py "$local_hook" 2>/dev/null && exit 0
exec "$local_hook" "$@"
"""


def render_shim() -> str:
    """The dispatcher body. One renderer so a shim change cannot reach install_global()
    while the tests keep exercising a stale copy."""
    return GLOBAL_SHIM.format(py=sys.executable.replace("\\", "/"),
                              script=os.path.abspath(__file__).replace("\\", "/"))


def _git_config(args: list[str]) -> tuple[int, str]:
    r = _git(["config", "--global"] + args, timeout=15)
    if r is None:
        return 1, "git could not be run"
    return r.returncode, (r.stdout or "").strip()


def install_global(remove: bool = False) -> int:
    """Gate EVERY repo, present and future, via git's core.hooksPath."""
    if remove:
        _git_config(["--unset", "core.hooksPath"])
        print("unset global core.hooksPath (per-repo .git/hooks are in charge again)")
        return 0
    rc, existing = _git_config(["core.hooksPath"])
    if rc == 0 and existing and os.path.abspath(existing) != os.path.abspath(GLOBAL_HOOKS_DIR):
        print(f"REFUSED: core.hooksPath is already set to '{existing}'. Point it here yourself if intended.")
        return 1
    os.makedirs(GLOBAL_HOOKS_DIR, exist_ok=True)
    body = render_shim()
    # Derived, not the tuple: core.hooksPath REPLACES .git/hooks wholesale, so any name with no
    # dispatcher here silently stops firing in every repo that has one - while this very
    # function prints "each repo's OWN .git/hooks/<name> still runs after the gate" (finding 27).
    names = git_client_hook_names()
    for name in names:
        dest = os.path.join(GLOBAL_HOOKS_DIR, name)
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        os.chmod(dest, 0o755)
    if _git_config(["core.hooksPath", GLOBAL_HOOKS_DIR.replace("\\", "/")])[0]:
        print("FAILED to set global core.hooksPath")
        return 1
    print(f"installed {len(names)} dispatchers in {GLOBAL_HOOKS_DIR}\n"
          f"  global core.hooksPath -> {GLOBAL_HOOKS_DIR}\n"
          f"  every git repo on this machine is now gated, including ones not created yet,\n"
          f"  and each repo's OWN .git/hooks/<name> still runs after the gate, for the\n"
          f"  {len(names)} names listed above.\n"
          f"  caveat: a repo setting its own core.hooksPath (husky/lefthook) overrides this -\n"
          f"          run `--install <repo>` there to restore the gate.")
    # [P13 D8] Say what was DROPPED. core.hooksPath REPLACES .git/hooks wholesale, so a name
    # with no dispatcher here stops a repo-local hook of that name firing at all - the exact
    # effect the CLIENT_HOOKS comment above forbids. The exclusion itself is correct and stays
    # (re-including reference-transaction measured a 200-tag `git fetch --tags` going from
    # ~0.9s to over 100s). Making a change with a real functional consequence while printing
    # an unqualified guarantee that it has none is the defect.
    dropped = undispatched_hook_names()
    if dropped:
        print(f"  NOT DISPATCHED (git fires these once per ref; a global dispatcher measured\n"
              f"  0.9s -> 100s+ on a 200-tag fetch): {', '.join(dropped)}\n"
              f"    core.hooksPath REPLACES .git/hooks, so a repo-local hook of these names\n"
              f"    WILL STOP FIRING while this is set. A repo that needs one must set that\n"
              f"    repo's own core.hooksPath and run `--install <repo>` there.")
    return 0


SKIP_RC = 77  # selftest could not run (missing git/sh). NEVER 0: a skip is not a pass.


def _capture_gate(root: str) -> tuple[int, str]:
    """(exit_code, stderr) for one gate() call. Asserting the code alone lets a gate that
    fires with no explanation - or allows a push with no warning - pass (finding 8)."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        rc = gate(root)
    return rc, buf.getvalue()


def _tmpdir(stack) -> str:
    """A temp dir whose cleanup can FAIL without killing the run.

    TemporaryDirectory's cleanup raises on Windows when anything still holds the directory -
    which is precisely the state finding 10 creates (an orphaned grandchild). That exception
    escaped the ExitStack and discarded the whole `fails` list, so a run that had found real
    defects reported only a traceback. `ignore_cleanup_errors` is 3.10+; this repo floors at 3.8.
    """
    import shutil
    import tempfile
    d = tempfile.mkdtemp()
    stack.callback(shutil.rmtree, d, True)
    return d


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--install-global" in argv or "--uninstall-global" in argv:
        return install_global(remove="--uninstall-global" in argv)
    if "--install" in argv or "--uninstall" in argv:
        rest = [a for a in argv[1:] if not a.startswith("--")]
        return install(rest[0] if rest else os.getcwd(), remove="--uninstall" in argv)
    # The gate path - and ONLY it - is fail-open. README:248 promises "any unexpected error
    # exits 0"; without this a corrupt state file crashed the hook with a traceback and exit 1,
    # so git REFUSED the push (finding 9). It stays LOUD: silence and success must differ.
    # --selftest and --install deliberately stay outside, so a broken install still reports 1.
    try:
        root = _repo_root(os.getcwd())
        if not root:
            return 0  # not a git repo: nothing to gate, never block
        return gate(root)
    except Exception as e:
        sys.stderr.write(f"[pre-push] WARNING: the gate crashed ({e!r}). "
                         f"This push is NOT verified.\n")
        return 0


def selftest() -> int:
    """Delegates to the sibling suite (see pre_push_gate_selftest.py)."""
    import pre_push_gate_selftest as _s
    return _s.selftest()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
