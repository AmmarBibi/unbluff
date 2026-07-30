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
        cmd, timeout_s, _ = fast_test._read_override(ov)
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


def install(target: str, remove: bool = False) -> int:
    root = _repo_root(target)
    if not root:
        print(f"not a git repository: {target}")
        return 1
    # Ask git where its hooks live rather than assuming <root>/.git/hooks. In a linked worktree
    # .git is a FILE, so the old join crashed with FileNotFoundError/NotADirectoryError; in the
    # variant where the write succeeded it reported success for a path git never reads
    # (finding 6). --git-common-dir is correct for plain repos, linked worktrees and submodules.
    gitdir = _common_git_dir(target)
    if not gitdir:
        print(f"cannot resolve a git directory for {target}; use --install-global")
        return 1
    dest = os.path.join(gitdir, "hooks", "pre-push")
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
    print(f"installed {dest}\n  gate command: {cmd or '(none detected - will allow pushes and say so)'}")
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
          f"  and each repo's OWN .git/hooks/<name> still runs after the gate.\n"
          f"  caveat: a repo setting its own core.hooksPath (husky/lefthook) overrides this -\n"
          f"          run `--install <repo>` there to restore the gate.")
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


def selftest() -> int:
    import tempfile
    fails = []

    def _repo(stack):
        d = _tmpdir(stack)
        try:
            if subprocess.run(["git", "-C", d, "init", "-q"], capture_output=True).returncode:
                return None
        except (OSError, subprocess.SubprocessError):
            return None
        return d

    real_state = fast_test.STATE_DIR
    with __import__("contextlib").ExitStack() as stack:
        fast_test.STATE_DIR = _tmpdir(stack)
        r = _repo(stack)
        if r is None:
            # A skip is NOT a pass. Exiting 0 here made the whole gate evaporate on any image
            # without git while the ledger recorded a clean run (finding 32).
            print("SELFTEST SKIP: git unavailable")
            fast_test.STATE_DIR = real_state
            return SKIP_RC

        # 1. no command -> allow (a repo with no tests must not be un-pushable)
        if gate(r) != 0:
            fails.append("repo with no test command should allow the push")

        # 2. push-time override wins over fast_test_on_stop's detection, and carries its timeout
        os.makedirs(os.path.join(r, ".claude"), exist_ok=True)
        os.makedirs(os.path.join(r, "tests"), exist_ok=True)  # would make fast_test_on_stop pick pytest
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write("# strict gate\ntimeout=222\npython -c \"pass\"\n")
        cmd, t = resolve_command(r)
        if (cmd, t) != ('python -c "pass"', 222):
            fails.append(f"pre-push override not honored: {(cmd, t)}")

        # 3. failing tests BLOCK
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write("python -c \"import sys; sys.exit(1)\"\n")
        with open(os.path.join(r, "app.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        if gate(r) != 1:
            fails.append("failing tests must block the push")

        # 4. passing tests allow, and record state fast_test_on_stop can read
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write("python -c \"pass\"\n")
        if gate(r) != 0:
            fails.append("passing tests must allow the push")
        if last_pass(r, 'python -c "pass"') <= 0:
            fails.append("a fresh pass was not recorded to fast_test_on_stop state")

        # 5. the fast path: nothing touched since that pass -> no re-run
        before = last_pass(r, 'python -c "pass"')
        if gate(r) != 0 or last_pass(r, 'python -c "pass"') != before:
            fails.append("clean tree should short-circuit without re-running tests")

        # 6. touching source re-arms the gate
        time.sleep(0.01)
        os.utime(os.path.join(r, "app.py"), None)
        newest, where = newest_source_mtime(r)
        if where != "app.py" or newest <= 0:
            fails.append(f"newest source detection wrong: {(where, newest)}")
        if newest <= before:
            fails.append("a touched source file must read as newer than the last pass")

        # 7. a foreign pre-push hook is never overwritten
        dest = os.path.join(r, ".git", "hooks", "pre-push")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho someone elses hook\n")
        if install(r) != 1:
            fails.append("install must refuse to clobber a foreign pre-push hook")
        os.remove(dest)

        # 8b. the global dispatcher must DELEGATE to a repo's own hook, never replace it
        gdir = _tmpdir(stack)
        body = render_shim()
        disp = os.path.join(gdir, "post-commit")  # a non-pre-push name: pure delegation, no gate
        with open(disp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        marker = os.path.join(r, "LOCAL_HOOK_RAN").replace("\\", "/")
        localdir = os.path.join(r, ".git", "hooks")
        os.makedirs(localdir, exist_ok=True)
        local_hook = os.path.join(localdir, "post-commit")
        with open(local_hook, "w", encoding="utf-8", newline="\n") as f:
            f.write(f'#!/bin/sh\necho ran > "{marker}"\n')
        # The dispatcher invokes a repo-local hook as an executable, so it needs the execute
        # bit. Windows ignores mode bits entirely, which is why this passed on the authoring
        # machine and failed on EVERY Unix CI runner with exit 126 ("found but not
        # executable"), 2026-07-29. Fail-soft: a filesystem without mode bits still runs the
        # assertions below.
        try:
            mode = os.stat(local_hook).st_mode
            os.chmod(local_hook, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass

        def _dispatch() -> int:
            try:
                return subprocess.run(["sh", disp], cwd=r, capture_output=True, timeout=60).returncode
            except (OSError, subprocess.SubprocessError):
                return -1

        rc = _dispatch()
        if rc == -1:
            print("SELFTEST SKIP: sh unavailable, dispatcher delegation untested")
        else:
            if rc != 0:
                fails.append(f"dispatcher should exit 0 when delegating, got {rc}")
            if not os.path.exists(marker):
                fails.append("dispatcher did NOT run the repo's own hook - project hooks would break")
            # and with no repo-local hook it must still succeed quietly
            os.remove(os.path.join(localdir, "post-commit"))
            if _dispatch() != 0:
                fails.append("dispatcher should exit 0 when the repo has no hook of that name")

        # 8. install then uninstall round-trips
        if install(r) != 0 or not os.path.exists(dest):
            fails.append("install did not write the hook")
        elif "pre_push_gate.py" not in open(dest, encoding="utf-8").read():
            fails.append("installed shim does not point at this script")
        # 8c. [finding 30] git REFUSES to run a non-executable hook on POSIX and merely warns.
        # Windows ignores mode bits, so only CI can see a regression here - assert it there.
        if os.name != "nt" and os.path.exists(dest):
            if not os.stat(dest).st_mode & stat.S_IXUSR:
                fails.append("installed pre-push hook is not executable - git would skip it")
        if install(r, remove=True) != 0 or os.path.exists(dest):
            fails.append("uninstall did not remove the hook")

        # ---------------------------------------------------------------- v1.3.1 regressions
        env = dict(os.environ)
        env["UNBLUFF_STATE_DIR"] = fast_test.STATE_DIR  # child processes share the temp state

        def _child(cwd, timeout=60):
            """Run this script as git would, in `cwd`. (rc, stderr) or (None, '') if it hung."""
            try:
                p = subprocess.run([sys.executable, os.path.abspath(__file__)], cwd=cwd,
                                   capture_output=True, text=True, timeout=timeout, env=env,
                                   encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
                return p.returncode, p.stderr or ""
            except subprocess.TimeoutExpired:
                return None, ""
            except (OSError, subprocess.SubprocessError) as e:
                return -1, str(e)

        # 9. [finding 1, CRITICAL] a non-ASCII repo path must not silently disable the gate.
        # git emits UTF-8; decoding it with the Windows locale codec yields a path that does
        # not exist, so resolve_command finds nothing and the gate reports the healthy-sounding
        # "no test command - nothing to verify".
        uni_parent = _tmpdir(stack)
        uni = os.path.join(uni_parent, "José-café")
        try:
            os.makedirs(uni, exist_ok=True)
            uni_ok = subprocess.run(["git", "-C", uni, "init", "-q"],
                                    capture_output=True).returncode == 0
        except (OSError, subprocess.SubprocessError, UnicodeError):
            uni_ok = False
        if uni_ok:
            root_u = _repo_root(uni)
            if not root_u or not os.path.isdir(root_u):
                fails.append("non-ASCII repo path: _repo_root returned %r which is not a "
                             "directory - the gate would silently skip this repo" % (root_u,))
            else:
                os.makedirs(os.path.join(root_u, ".claude"), exist_ok=True)
                with open(os.path.join(root_u, ".claude", "pre-push.cmd"), "w",
                          encoding="utf-8") as f:
                    f.write('python -c "import sys; sys.exit(1)"\n')
                rc_u, err_u = _capture_gate(root_u)
                if rc_u != 1 or "BLOCKED" not in err_u:
                    fails.append("non-ASCII repo path: failing tests did NOT block "
                                 "(rc=%s err=%r)" % (rc_u, err_u[:120]))
        else:
            print("SELFTEST SKIP: could not create a non-ASCII repo path")

        # 10. [findings 3, 11] git failing must NEVER read the same as "nothing changed".
        # A locked index made ls-files exit 128, the gate saw (0.0, None), trusted a stale
        # pass and announced "verified - no source touched since".
        not_a_repo = _tmpdir(stack)
        newest_bad, where_bad = newest_source_mtime(not_a_repo)
        if newest_bad is not None:
            fails.append("git failure returned a real mtime (%r) instead of the UNKNOWN "
                         "sentinel - a stale pass would satisfy the fast path" % (newest_bad,))

        # 10b. [finding 1] a root git reports but which does not exist is an UNANSWERED
        # question, not "this repo has no tests". With the codec fixed this state is
        # unreachable on a healthy machine, so pin the guard directly - otherwise deleting it
        # is a mutation nothing catches, and the CRITICAL failure returns the moment any other
        # decode path regresses.
        class _FakeGit(object):
            returncode = 0
            stdout = os.path.join(not_a_repo, "definitely-not-a-directory")
            stderr = ""

        _real_git = globals()["_git"]
        globals()["_git"] = lambda *a, **k: _FakeGit()
        try:
            if _repo_root("anything") is not None:
                fails.append("_repo_root accepted a root that is not a directory - a "
                             "mis-decoded path would read as a healthy repo with no tests")
        finally:
            globals()["_git"] = _real_git

        # 11. [findings 2, 12] source outside SRC_EXT must still re-arm the gate.
        for extra in ("deploy.sh", "schema.sql", "Dockerfile"):
            with open(os.path.join(r, extra), "w", encoding="utf-8") as f:
                f.write("# x\n")
        newest_x, where_x = newest_source_mtime(r)
        if newest_x is None or where_x is None:
            fails.append("non-.py source: scan returned UNKNOWN unexpectedly")
        elif os.path.basename(str(where_x)) not in ("deploy.sh", "schema.sql", "Dockerfile"):
            fails.append("a changed shell/sql/Dockerfile is invisible to the gate (newest=%r) "
                         "- it would claim 'no source touched since'" % (where_x,))

        # 12. [finding 4] a non-ASCII source filename is C-quoted by git and was skipped
        # entirely, so editing it left the gate announcing a verified tree.
        quoted = "données.py"
        try:
            with open(os.path.join(r, quoted), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            made = True
        except (OSError, UnicodeError):
            made = False
        if made:
            time.sleep(0.01)
            os.utime(os.path.join(r, quoted), None)
            newest_q, where_q = newest_source_mtime(r)
            if newest_q is None:
                fails.append("non-ASCII source: scan returned UNKNOWN")
            elif os.path.basename(str(where_q or "")) != quoted:
                fails.append("C-quoted source file is invisible to the gate (newest=%r)"
                             % (where_q,))

        # 13. [finding 9] a corrupt state file must not crash the gate. It used to raise
        # through main(), so git REFUSED every push in that repo with a bare traceback.
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write('python -c "pass"\n')
        for junk in ('[]', '{"ts": "not-a-number", "rc": 0, "cmd": "python -c \\"pass\\""}',
                     'null', '{"ts": {"a": 1}, "rc": 0}'):
            with open(fast_test._state_path(r), "w", encoding="utf-8") as f:
                f.write(junk)
            try:
                if last_pass(r, 'python -c "pass"') != 0.0:
                    fails.append("corrupt state %r was trusted as a pass" % junk)
            except Exception as e:
                fails.append("corrupt state %r raised %r - git would refuse the push"
                             % (junk, e))
            rc_c, _ = _child(r)
            if rc_c not in (0, 1):
                fails.append("corrupt state %r made the hook exit %r (a traceback refuses "
                             "the push)" % (junk, rc_c))
        try:
            os.remove(fast_test._state_path(r))
        except OSError:
            pass

        # 14. [finding 10] a test that leaves a grandchild holding the captured pipe hung
        # `git push` forever: subprocess.run's timeout kills the direct child, then blocks
        # again draining a pipe nobody will close.
        hangdir = _repo(stack)
        if hangdir:
            os.makedirs(os.path.join(hangdir, ".claude"), exist_ok=True)
            with open(os.path.join(hangdir, ".claude", "pre-push.cmd"), "w",
                      encoding="utf-8") as f:
                f.write("timeout=5\n"
                        '"%s" -c "import subprocess,sys; '
                        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])\"\n"
                        % sys.executable.replace("\\", "/"))
            with open(os.path.join(hangdir, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            # The command itself exits at once; a grandchild sleeps 120s holding the captured
            # pipe. subprocess.run's cleanup blocks on that pipe forever, so the ONLY property
            # worth asserting is that a verdict arrives promptly. Reverting run_tests to
            # subprocess.run makes _child time out and rc_h come back None.
            t0 = time.time()
            rc_h, err_h = _child(hangdir, timeout=45)
            elapsed = time.time() - t0
            if rc_h is None:
                fails.append("a test leaving a grandchild on the pipe HUNG the push "
                             "(no verdict within 45s)")
            elif rc_h not in (0, 1):
                fails.append("grandchild-on-pipe: expected a real verdict, got rc=%r err=%r"
                             % (rc_h, err_h[:160]))
            elif elapsed > 40:
                fails.append("grandchild-on-pipe: verdict took %.0fs - the pipe is not bounded"
                             % elapsed)

        # 15. [finding 8] every outcome must SAY something. A refactor that drops a stderr
        # write leaves a gate that blocks with no diagnosis, or allows with no warning.
        msgdir = _repo(stack)
        if msgdir:
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "no test command" not in err_m:
                fails.append("no-command outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            os.makedirs(os.path.join(msgdir, ".claude"), exist_ok=True)
            with open(os.path.join(msgdir, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            cmdfile = os.path.join(msgdir, ".claude", "pre-push.cmd")
            with open(cmdfile, "w", encoding="utf-8") as f:
                f.write('python -c "import sys; sys.exit(1)"\n')
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 1 or "BLOCKED" not in err_m:
                fails.append("failing outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            with open(cmdfile, "w", encoding="utf-8") as f:
                f.write('python -c "pass"\n')
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "tests passed" not in err_m:
                fails.append("passing outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "no source touched since" not in err_m:
                fails.append("fast-path outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            with open(cmdfile, "w", encoding="utf-8") as f:
                f.write('timeout=5\npython -c "import time; time.sleep(60)"\n')
            with open(os.path.join(msgdir, "app.py"), "a", encoding="utf-8") as f:
                f.write("y = 2\n")
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "NOT verified" not in err_m:
                fails.append("timeout outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))

        # 16. [finding 7] the GLOBAL_SHIM's pre-push branch - the ONE line that runs the gate
        # in every repo on the machine - was covered by nothing. Deleting it stayed green.
        ppdir = _repo(stack)
        if ppdir:
            os.makedirs(os.path.join(ppdir, ".claude"), exist_ok=True)
            ppcmd = os.path.join(ppdir, ".claude", "pre-push.cmd")
            with open(ppcmd, "w", encoding="utf-8") as f:
                f.write('python -c "import sys; sys.exit(1)"\n')
            with open(os.path.join(ppdir, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            shim_dir = _tmpdir(stack)
            pp_disp = os.path.join(shim_dir, "pre-push")
            with open(pp_disp, "w", encoding="utf-8", newline="\n") as f:
                f.write(render_shim())
            try:
                p = subprocess.run(["sh", pp_disp], cwd=ppdir, capture_output=True, text=True,
                                   timeout=90, env=env, encoding="utf-8", errors="replace")
                sh_ok = True
            except (OSError, subprocess.SubprocessError):
                sh_ok = False
            if not sh_ok:
                print("SELFTEST SKIP: sh unavailable, pre-push dispatcher branch untested")
            else:
                if p.returncode == 0 or "BLOCKED" not in (p.stderr or ""):
                    fails.append("pre-push dispatcher did NOT run the gate on failing tests "
                                 "(rc=%r err=%r)" % (p.returncode, (p.stderr or "")[:160]))
                with open(ppcmd, "w", encoding="utf-8") as f:
                    f.write('python -c "pass"\n')
                p2 = subprocess.run(["sh", pp_disp], cwd=ppdir, capture_output=True, text=True,
                                    timeout=90, env=env, encoding="utf-8", errors="replace")
                if p2.returncode != 0:
                    fails.append("pre-push dispatcher blocked a passing repo (rc=%r err=%r)"
                                 % (p2.returncode, (p2.stderr or "")[:160]))

        # 17/18. [findings 5, 6] linked worktrees. `git rev-parse --git-dir` resolves to
        # .git/worktrees/<name>, so the dispatcher looked for hooks in a directory that has
        # none and silently skipped every repo-local hook; install() crashed outright.
        wt_host = _repo(stack)
        if wt_host:
            with open(os.path.join(wt_host, "seed.txt"), "w", encoding="utf-8") as f:
                f.write("seed\n")
            genv = dict(env)
            genv.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                         "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
            wt_ok = True
            for argv in (["add", "-A"], ["commit", "-qm", "seed"]):
                if subprocess.run(["git", "-C", wt_host] + argv, capture_output=True,
                                  env=genv).returncode:
                    wt_ok = False
            wt_path = os.path.join(_tmpdir(stack), "wt")
            if wt_ok and subprocess.run(["git", "-C", wt_host, "worktree", "add", "-q", wt_path],
                                        capture_output=True, env=genv).returncode:
                wt_ok = False
            if not wt_ok:
                print("SELFTEST SKIP: git worktree unavailable")
            else:
                # 17: the dispatcher must still delegate to the repo's own hook
                hooks_common = os.path.join(wt_host, ".git", "hooks")
                os.makedirs(hooks_common, exist_ok=True)
                wt_marker = os.path.join(wt_path, "WT_HOOK_RAN").replace("\\", "/")
                lh = os.path.join(hooks_common, "post-commit")
                with open(lh, "w", encoding="utf-8", newline="\n") as f:
                    f.write('#!/bin/sh\necho ran > "%s"\n' % wt_marker)
                try:
                    os.chmod(lh, os.stat(lh).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                except OSError:
                    pass
                wdisp_dir = _tmpdir(stack)
                wdisp = os.path.join(wdisp_dir, "post-commit")
                with open(wdisp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(render_shim())
                try:
                    subprocess.run(["sh", wdisp], cwd=wt_path, capture_output=True, timeout=60,
                                   env=env)
                    if not os.path.exists(os.path.join(wt_path, "WT_HOOK_RAN")):
                        fails.append("dispatcher did NOT delegate inside a linked worktree - "
                                     "every repo-local hook is silently bypassed there")
                except (OSError, subprocess.SubprocessError):
                    print("SELFTEST SKIP: sh unavailable, worktree delegation untested")
                # 18: --install must not crash, and must write where git actually looks
                rc_i = 99
                try:
                    rc_i = install(wt_path)
                except Exception as e:
                    fails.append("install() in a linked worktree RAISED %r" % (e,))
                if rc_i == 0:
                    probe = subprocess.run(["git", "-C", wt_path, "rev-parse", "--git-path",
                                            "hooks"], capture_output=True, text=True,
                                           encoding="utf-8", errors="replace")
                    hd = (probe.stdout or "").strip()
                    if hd and not os.path.isabs(hd):
                        hd = os.path.join(wt_path, hd)
                    if not (hd and os.path.exists(os.path.join(hd, "pre-push"))):
                        fails.append("install() in a worktree wrote where git never looks "
                                     "(git-path hooks=%r)" % (hd,))
                    install(wt_path, remove=True)

        # 19b. [finding 34] CROSS-HOOK: a pass recorded by fast_test_on_stop's OWN entry point
        # must be visible to the gate. They advertise "one source of truth"; keyed differently
        # they each behaved plausibly in isolation while every push re-ran a suite that had
        # passed seconds earlier. Drive the real main(), not the helper.
        xr = _repo(stack)
        if xr:
            os.makedirs(os.path.join(xr, ".claude"), exist_ok=True)
            with open(os.path.join(xr, ".claude", "fast-test.cmd"), "w", encoding="utf-8") as f:
                f.write('debounce=0\npython -c "pass"\n')
            with open(os.path.join(xr, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            import io as _io
            real_in, real_err = sys.stdin, sys.stderr
            sys.stdin = _io.StringIO(json.dumps({"cwd": xr}))
            sys.stderr = _io.StringIO()
            try:
                fast_test.main()
            finally:
                sys.stdin, sys.stderr = real_in, real_err
            xroot = _repo_root(xr) or xr
            if last_pass(xroot, 'python -c "pass"') <= 0:
                fails.append("a pass recorded by fast_test_on_stop is invisible to the gate - "
                             "the shared state file is not actually shared "
                             "(cwd=%r root=%r)" % (xr, xroot))

        # 19. [finding 27] core.hooksPath REPLACES .git/hooks wholesale, so any client hook
        # name with no dispatcher silently stops firing everywhere. Derive the list from git
        # rather than trusting a tuple that has already drifted once.
        missing_names = sorted(set(git_client_hook_names()) - set(CLIENT_HOOKS))
        if missing_names:
            fails.append("git knows client hooks with no dispatcher: %s" % missing_names)

    fast_test.STATE_DIR = real_state
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
