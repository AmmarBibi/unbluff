"""fast-test-on-stop (Claude Code Stop hook) - a mechanical CI safety net.

At turn end: if source files changed (git porcelain), run the project's FAST tests and feed a
FAILURE back to Claude (exit 2, once); success and every skip path are silent (exit 0).

Mechanical by design (no reasoning): command resolution is
  1. <project>/.claude/fast-test.cmd   line1 = command; optional "timeout=N" / "debounce=N" lines
  2. package.json scripts.test         -> "npm test --silent"
  3. pytest markers (pytest.ini / tests/ / pyproject [tool.pytest]) -> "<python> -m pytest -x -q"
Guards: never re-fires while Claude is already continuing from this hook (stop_hook_active);
per-project debounce (default 10 min); 90s default cap (override per project); not-a-git-repo,
no-changed-source and timeout all exit 0 quietly. State lives under ~/.claude/hooks/state/.
Run with --selftest to verify the mechanics.

no-detectable-command is the ONE skip that does not stay quiet: a repo with no test gate would
otherwise be silently unverified forever, indistinguishable from a passing run. It says so once
per project (only when source actually changed), then never again. See _notice_no_gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

DEFAULT_TIMEOUT_S = 90
DEFAULT_DEBOUNCE_S = 600
SRC_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".go", ".rs", ".java", ".rb", ".php",
           ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".vue", ".svelte"}
STATE_DIR = os.environ.get("UNBLUFF_STATE_DIR") or os.path.join(
    os.path.expanduser("~"), ".claude", "hooks", "state")


def _changed_source_files(porcelain: str) -> list[str]:
    """Paths of modified/added/renamed SOURCE files from `git status --porcelain=v1` output."""
    out = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:  # rename: take the new side
            path = path.split(" -> ", 1)[1].strip().strip('"')
        if os.path.splitext(path)[1].lower() in SRC_EXT:
            out.append(path)
    return out


def _read_override(path: str) -> tuple[str | None, int, int]:
    """(command, timeout_s, debounce_s) from a .claude/fast-test.cmd file."""
    cmd, timeout_s, debounce_s = None, DEFAULT_TIMEOUT_S, DEFAULT_DEBOUNCE_S
    try:
        with open(path, encoding="utf-8-sig") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("timeout="):
                    timeout_s = max(5, min(600, int(line.split("=", 1)[1])))
                elif line.lower().startswith("debounce="):
                    debounce_s = max(0, min(86400, int(line.split("=", 1)[1])))
                elif cmd is None:
                    cmd = line
    except (OSError, ValueError):
        return None, DEFAULT_TIMEOUT_S, DEFAULT_DEBOUNCE_S
    return cmd, timeout_s, debounce_s


def detect(cwd: str) -> tuple[str | None, int, int]:
    """(command, timeout_s, debounce_s) for this project, or (None, ...) when nothing safe exists."""
    ov = os.path.join(cwd, ".claude", "fast-test.cmd")
    if os.path.exists(ov):
        return _read_override(ov)
    pj = os.path.join(cwd, "package.json")
    if os.path.exists(pj):
        try:
            with open(pj, encoding="utf-8") as f:
                test = (json.load(f).get("scripts") or {}).get("test", "")
            if test and "no test specified" not in test:
                return "npm test --silent", DEFAULT_TIMEOUT_S, DEFAULT_DEBOUNCE_S
        except (OSError, ValueError):
            pass
    has_pytest = (os.path.exists(os.path.join(cwd, "pytest.ini"))
                  or os.path.isdir(os.path.join(cwd, "tests")))
    if not has_pytest:
        pp = os.path.join(cwd, "pyproject.toml")
        try:
            has_pytest = os.path.exists(pp) and "[tool.pytest" in open(pp, encoding="utf-8").read()
        except OSError:
            has_pytest = False
    if has_pytest:
        return f'"{sys.executable}" -m pytest -x -q', DEFAULT_TIMEOUT_S, DEFAULT_DEBOUNCE_S
    return None, DEFAULT_TIMEOUT_S, DEFAULT_DEBOUNCE_S


def _state_path(cwd: str) -> str:
    return os.path.join(STATE_DIR, "fasttest-" + hashlib.sha1(cwd.lower().encode()).hexdigest()[:16] + ".json")


def _nogate_state_path(cwd: str) -> str:
    return os.path.join(STATE_DIR, "nogate-" + hashlib.sha1(cwd.lower().encode()).hexdigest()[:16] + ".json")


def _notice_no_gate(cwd: str) -> int:
    """Say ONCE per project that no test gate exists here, so a skip cannot pass for a green run.

    Only speaks when source files actually changed - i.e. you are writing code in an ungated repo.
    Always exits 0: this is information, never a block. Adding a test command retires it naturally;
    deleting the state file re-arms it.
    """
    np = _nogate_state_path(cwd)
    if os.path.exists(np):
        return 0
    try:
        porcelain = subprocess.run(["git", "-C", cwd, "status", "--porcelain=v1"],
                                   capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    if not _changed_source_files(porcelain):
        return 0
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(np, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "cwd": cwd}, f)
    except OSError:
        return 0  # cannot record it -> stay silent rather than repeat every turn
    # Computed outside the f-string: a backslash inside an f-string expression is a SyntaxError
    # before Python 3.12 (PEP 701), and this hook must import on older interpreters.
    name = os.path.basename(cwd.rstrip("/\\")) or cwd
    sys.stderr.write(
        f"[fast-test] NO TEST GATE in '{name}': source changed, nothing was verified.\n"
        f"[fast-test] Add one to activate the gate: .claude/fast-test.cmd, package.json "
        f"scripts.test, or a tests/ dir.\n"
        f"[fast-test] Said once per project. Delete {np} to hear it again.\n")
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if payload.get("stop_hook_active"):  # already continuing from a stop hook - never loop
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    if not os.path.isdir(os.path.join(cwd, ".git")):
        return 0

    cmd, timeout_s, debounce_s = detect(cwd)
    if not cmd:
        return _notice_no_gate(cwd)

    sp = _state_path(cwd)
    try:
        last = json.load(open(sp, encoding="utf-8"))
    except (OSError, ValueError):
        last = {}
    if time.time() - last.get("ts", 0) < debounce_s:
        return 0

    try:
        porcelain = subprocess.run(["git", "-C", cwd, "status", "--porcelain=v1"],
                                   capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    if not _changed_source_files(porcelain):
        return 0

    os.makedirs(STATE_DIR, exist_ok=True)
    started = time.time()
    try:
        run = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                             timeout=timeout_s, encoding="utf-8", errors="replace")
        rc, tail_src = run.returncode, (run.stdout or "") + "\n" + (run.stderr or "")
    except subprocess.TimeoutExpired:
        rc, tail_src = None, ""
    except (OSError, subprocess.SubprocessError):
        return 0

    with open(sp, "w", encoding="utf-8") as f:
        json.dump({"ts": time.time(), "rc": rc, "cmd": cmd, "secs": round(time.time() - started, 1)}, f)

    if rc is None:
        sys.stderr.write(f"[fast-test] skipped: '{cmd}' exceeded {timeout_s}s (raise timeout= in .claude/fast-test.cmd)\n")
        return 0
    if rc != 0:
        tail = "\n".join(line for line in tail_src.splitlines() if line.strip())[-1500:]
        sys.stderr.write(f"[fast-test] FAILING at stop - fix before finishing (cmd: {cmd}):\n{tail}\n")
        return 2  # feed the failure back to Claude exactly once (stop_hook_active guards the loop)
    return 0


def selftest() -> int:
    import tempfile
    fails = []
    # 1. porcelain parser: modified source, renamed source, non-source, untracked source
    porcelain = ' M src/app.py\nR  old.js -> new/thing.ts\n M docs/readme.md\n?? tools/new_tool.py\n'
    got = _changed_source_files(porcelain)
    if got != ["src/app.py", "new/thing.ts", "tools/new_tool.py"]:
        fails.append(f"porcelain parser wrong: {got}")
    # 2. detection precedence: override file wins and carries timeout/debounce
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, ".claude"))
        with open(os.path.join(td, ".claude", "fast-test.cmd"), "w", encoding="utf-8") as f:
            f.write("# comment\ntimeout=240\ndebounce=1800\npytest -x -q tests/fast\n")
        cmd, t, d = detect(td)
        if (cmd, t, d) != ("pytest -x -q tests/fast", 240, 1800):
            fails.append(f"override detect wrong: {(cmd, t, d)}")
    # 3. pytest auto-detect via tests/ dir
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "tests"))
        cmd, _, _ = detect(td)
        if not (cmd and "-m pytest" in cmd):
            fails.append(f"pytest autodetect wrong: {cmd}")
    # 4. nothing detectable -> None
    with tempfile.TemporaryDirectory() as td:
        if detect(td)[0] is not None:
            fails.append("empty dir should detect no command")
    # 5. the two state files never collide for the same project
    if _state_path("/x/y") == _nogate_state_path("/x/y"):
        fails.append("fasttest and nogate state paths collide")
    # 6. no-gate notice: speaks once on changed source, then never; silent on non-source changes
    global STATE_DIR
    real_state, io_mod = STATE_DIR, __import__("io")
    with tempfile.TemporaryDirectory() as sd:
        STATE_DIR = sd

        def _say(repo: str, path: str) -> str:
            """Write `path` into `repo`, run the notice, return whatever it printed to stderr."""
            with open(os.path.join(repo, path), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            real_err, sys.stderr = sys.stderr, io_mod.StringIO()
            try:
                _notice_no_gate(repo)
                return sys.stderr.getvalue()
            finally:
                sys.stderr = real_err

        def _new_repo(stack):
            d = stack.enter_context(tempfile.TemporaryDirectory())
            try:
                if subprocess.run(["git", "-C", d, "init", "-q"], capture_output=True).returncode:
                    return None
            except (OSError, subprocess.SubprocessError):
                return None
            return d

        with __import__("contextlib").ExitStack() as stack:
            code_repo, docs_repo = _new_repo(stack), _new_repo(stack)
            if code_repo and docs_repo:
                if "NO TEST GATE" not in _say(code_repo, "a.py"):
                    fails.append("no-gate notice did not fire on changed source")
                if _say(code_repo, "b.py") != "":
                    fails.append("no-gate notice fired twice - it must speak once per project")
                # separate clean repo: only a non-source file ever changes here
                if _say(docs_repo, "notes.md") != "":
                    fails.append("no-gate notice fired on a non-source change")
            else:
                print("SELFTEST SKIP: git unavailable, no-gate notice untested")
        STATE_DIR = real_state
    if STATE_DIR != real_state:  # paranoia: never leave the global patched
        STATE_DIR = real_state
        fails.append("STATE_DIR was left patched after selftest")
    # 7. main() INTEGRATION: the no-gate notice must actually be reachable through main().
    #    Testing _notice_no_gate() alone leaves the one line that calls it uncovered - a mutation
    #    reverting `return _notice_no_gate(cwd)` to `return 0` passed checks 1-6 untouched
    #    (verified 2026-07-29). Drive the real entry point, not just the helper.
    real_state2 = STATE_DIR
    with tempfile.TemporaryDirectory() as sd:
        STATE_DIR = sd
        with __import__("contextlib").ExitStack() as stack:
            repo = stack.enter_context(tempfile.TemporaryDirectory())
            try:
                ok = subprocess.run(["git", "-C", repo, "init", "-q"],
                                    capture_output=True).returncode == 0
            except (OSError, subprocess.SubprocessError):
                ok = False
            if ok:
                with open(os.path.join(repo, "app.py"), "w", encoding="utf-8") as f:
                    f.write("x = 1\n")
                real_in, real_err = sys.stdin, sys.stderr
                sys.stdin = io_mod.StringIO(json.dumps({"cwd": repo}))
                sys.stderr = io_mod.StringIO()
                try:
                    rc = main()
                    emitted = sys.stderr.getvalue()
                finally:
                    sys.stdin, sys.stderr = real_in, real_err
                if rc != 0:
                    fails.append(f"main() on ungated repo should exit 0, got {rc}")
                if "NO TEST GATE" not in emitted:
                    fails.append("main() did not reach the no-gate notice (wiring untested)")
            else:
                print("SELFTEST SKIP: git unavailable, main() integration untested")
        STATE_DIR = real_state2
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
