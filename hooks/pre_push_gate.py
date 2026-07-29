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


def _repo_root(start: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() or None if r.returncode == 0 else None


def resolve_command(root: str) -> tuple[str | None, int]:
    """(command, timeout_s): a push-time override if the project has one, else fast_test_on_stop's own choice."""
    ov = os.path.join(root, ".claude", "pre-push.cmd")
    if os.path.exists(ov):
        cmd, timeout_s, _ = fast_test._read_override(ov)
        if cmd:
            return cmd, timeout_s
    cmd, timeout_s, _ = fast_test.detect(root)
    return cmd, timeout_s


def newest_source_mtime(root: str) -> tuple[float, str | None]:
    """(mtime, path) of the most recently modified non-ignored SOURCE file, or (0.0, None)."""
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-cmo", "--exclude-standard"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return 0.0, None
    newest, where = 0.0, None
    for rel in set(r.stdout.splitlines()):
        rel = rel.strip().strip('"')
        if not rel or os.path.splitext(rel)[1].lower() not in fast_test.SRC_EXT:
            continue
        try:
            m = os.path.getmtime(os.path.join(root, rel))
        except OSError:
            continue  # listed but gone (deleted since); nothing to verify
        if m > newest:
            newest, where = m, rel
    return newest, where


def last_pass(root: str, cmd: str) -> float:
    """Timestamp of fast_test_on_stop's last recorded PASS for this exact command, else 0.0."""
    try:
        with open(fast_test._state_path(root), encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        return 0.0
    if st.get("rc") != 0 or st.get("cmd") != cmd:
        return 0.0
    return float(st.get("ts") or 0.0)


def _record_pass(root: str, cmd: str, secs: float) -> None:
    """Share the result with fast_test_on_stop so the two gates agree on what has been verified."""
    try:
        os.makedirs(fast_test.STATE_DIR, exist_ok=True)
        with open(fast_test._state_path(root), "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "rc": 0, "cmd": cmd, "secs": round(secs, 1)}, f)
    except OSError:
        pass  # advisory only - never fail a push because state could not be written


def gate(root: str) -> int:
    cmd, timeout_s = resolve_command(root)
    name = os.path.basename(root.rstrip("/\\")) or root
    if not cmd:
        sys.stderr.write(f"[pre-push] '{name}' has no test command - nothing to verify, allowing push.\n")
        return 0

    newest, where = newest_source_mtime(root)
    passed_at = last_pass(root, cmd)
    if passed_at and passed_at > newest:
        age = int(time.time() - passed_at)
        sys.stderr.write(f"[pre-push] verified {age}s ago, no source touched since - allowing push.\n")
        return 0

    why = f"'{where}' changed since the last passing run" if where else "no passing run on record"
    sys.stderr.write(f"[pre-push] {why} - running: {cmd}\n")
    started = time.time()
    try:
        run = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True,
                             timeout=timeout_s, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"[pre-push] WARNING: tests exceeded {timeout_s}s and were killed. "
                         f"This push is NOT verified. Raise timeout= in .claude/pre-push.cmd.\n")
        return 0
    except (OSError, subprocess.SubprocessError) as e:
        sys.stderr.write(f"[pre-push] WARNING: could not run tests ({e}). This push is NOT verified.\n")
        return 0

    if run.returncode != 0:
        tail = "\n".join(ln for ln in ((run.stdout or "") + "\n" + (run.stderr or "")).splitlines()
                         if ln.strip())[-2000:]
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
    dest = os.path.join(root, ".git", "hooks", "pre-push")
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
CLIENT_HOOKS = ("applypatch-msg", "pre-applypatch", "post-applypatch", "pre-commit",
                "prepare-commit-msg", "commit-msg", "post-commit", "pre-rebase", "post-checkout",
                "post-merge", "pre-push", "post-rewrite", "pre-auto-gc", "push-to-checkout",
                "sendemail-validate", "post-index-change")

# Runs the universal gate (pre-push only), then ALWAYS delegates to the repo's own hook of the
# same name, so project-specific hooks keep working. The gate reads no stdin (</dev/null), leaving
# git's ref list untouched for the repo-local hook that may actually need it.
GLOBAL_SHIM = """#!/bin/sh
# Universal git hook dispatcher - managed by ~/.claude/hooks/pre_push_gate.py
# 1. universal pre-push gate  2. this repo's own hook, if it has one (never overridden)
# Bypass once with: git push --no-verify
hook=`basename "$0"`
if [ "$hook" = "pre-push" ]; then
    "{py}" "{script}" < /dev/null || exit $?
fi
gitdir=`git rev-parse --git-dir 2>/dev/null` || exit 0
local_hook="$gitdir/hooks/$hook"
# Delegate to the repo's own hook - unless it is one of ours, which would run the gate twice.
if [ -f "$local_hook" ] && ! grep -q pre_push_gate.py "$local_hook" 2>/dev/null; then
    exec "$local_hook" "$@"
fi
exit 0
"""


def _git_config(args: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "config", "--global"] + args, capture_output=True, text=True, timeout=15)
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)


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
    body = GLOBAL_SHIM.format(py=sys.executable.replace("\\", "/"),
                              script=os.path.abspath(__file__).replace("\\", "/"))
    for name in CLIENT_HOOKS:
        dest = os.path.join(GLOBAL_HOOKS_DIR, name)
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        os.chmod(dest, 0o755)
    if _git_config(["core.hooksPath", GLOBAL_HOOKS_DIR.replace("\\", "/")])[0]:
        print("FAILED to set global core.hooksPath")
        return 1
    print(f"installed {len(CLIENT_HOOKS)} dispatchers in {GLOBAL_HOOKS_DIR}\n"
          f"  global core.hooksPath -> {GLOBAL_HOOKS_DIR}\n"
          f"  every git repo on this machine is now gated, including ones not created yet,\n"
          f"  and each repo's OWN .git/hooks/<name> still runs after the gate.\n"
          f"  caveat: a repo setting its own core.hooksPath (husky/lefthook) overrides this -\n"
          f"          run `--install <repo>` there to restore the gate.")
    return 0


def selftest() -> int:
    import tempfile
    fails = []

    def _repo(stack):
        d = stack.enter_context(tempfile.TemporaryDirectory())
        try:
            if subprocess.run(["git", "-C", d, "init", "-q"], capture_output=True).returncode:
                return None
        except (OSError, subprocess.SubprocessError):
            return None
        return d

    real_state = fast_test.STATE_DIR
    with __import__("contextlib").ExitStack() as stack:
        fast_test.STATE_DIR = stack.enter_context(tempfile.TemporaryDirectory())
        r = _repo(stack)
        if r is None:
            print("SELFTEST SKIP: git unavailable")
            fast_test.STATE_DIR = real_state
            return 0

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
        gdir = stack.enter_context(tempfile.TemporaryDirectory())
        body = GLOBAL_SHIM.format(py=sys.executable.replace("\\", "/"),
                                  script=os.path.abspath(__file__).replace("\\", "/"))
        disp = os.path.join(gdir, "post-commit")  # a non-pre-push name: pure delegation, no gate
        with open(disp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        marker = os.path.join(r, "LOCAL_HOOK_RAN").replace("\\", "/")
        localdir = os.path.join(r, ".git", "hooks")
        os.makedirs(localdir, exist_ok=True)
        with open(os.path.join(localdir, "post-commit"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f'#!/bin/sh\necho ran > "{marker}"\n')

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
        if install(r, remove=True) != 0 or os.path.exists(dest):
            fails.append("uninstall did not remove the hook")

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
    root = _repo_root(os.getcwd())
    if not root:
        return 0  # not a git repo: nothing to gate, never block
    return gate(root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
