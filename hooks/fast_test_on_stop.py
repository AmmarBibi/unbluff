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
    """Paths of modified/added/renamed SOURCE files from `git status --porcelain=v1` output.

    Accepts BOTH the -z (NUL-separated) form the callers now request and the newline form.

    -z matters for the CONTRACT, not for the boolean: the callers only ask "did any source
    change?", and a C-quoted `"donn\\303\\251es.py"` still ends in `.py`, so detection was
    never actually lost. What was wrong is that the returned PATH was a mangled string no
    os.path call could open - a correct-looking answer that breaks the first caller to use
    the paths for anything. With -z git emits raw bytes and no quoting, and a rename's
    original name arrives as its own field rather than inside a " -> " substring that a
    filename may legitimately contain.
    """
    if "\0" in porcelain:
        out = []
        fields = porcelain.split("\0")
        i = 0
        while i < len(fields):
            entry = fields[i]
            i += 1
            if len(entry) < 4:
                continue
            xy, path = entry[:2], entry[3:]
            if "R" in xy or "C" in xy:
                i += 1        # the ORIGINAL name follows as a separate field; skip it
            if os.path.splitext(path)[1].lower() in SRC_EXT:
                out.append(path)
        return out
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


def is_git_worktree(cwd: str) -> bool:
    """True iff `cwd` is inside a git working tree - plain repo, LINKED WORKTREE, or submodule.

    `os.path.isdir(cwd/.git)` is FALSE in a linked worktree and in a submodule, where `.git` is
    a FILE pointing at the real gitdir. The Stop gate therefore returned 0 before detect() ever
    ran, and `_notice_no_gate` (which sits after the guard) never fired either - rc 0, empty
    stderr, indistinguishable from a clean passing turn, for the entire life of the worktree.
    Reproduced: identical repo, override and dirty file, host rc=2, worktree rc=0.

    `os.path.exists` - the variant meta_audit_on_stop used - fixes the worktree case but still
    returns False when cwd is a SUBDIRECTORY of the repo, which is the normal case for a
    monorepo package. Both hooks now call this one function rather than each keeping a probe.
    """
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True, timeout=10,
                           stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    except (OSError, ValueError, subprocess.SubprocessError):
        # git unrunnable: fall back to the cheap probe rather than claiming "not a repo",
        # which would silently disable the gate everywhere.
        p = os.path.join(cwd, ".git")
        return os.path.isdir(p) or os.path.isfile(p)
    return r.returncode == 0 and (r.stdout or "").strip() == "true"


# [P13 D5] Two gates, two ceilings. The turn-end hook must never stall a turn, so 600s is
# right for it - but pre_push_gate shared this table, so a project that set `timeout = 1800`
# in .claude/pre-push.cmd had it silently clamped to 600, making the remedy the gate's own
# error message prescribes ("raise the timeout") a no-op. A push may legitimately take longer
# than a turn end; that is the whole difference between the two gates.
TURN_END_OPTIONS = {"timeout": (5, 600), "debounce": (0, 86400)}
PUSH_OPTIONS = {"timeout": (5, 7200), "debounce": (0, 86400)}
_OPTION_KEYS = TURN_END_OPTIONS   # the turn-end default; kept as the name callers already use


def _read_override(path: str, options: dict | None = None) -> tuple[str | None, int, int]:
    """(command, timeout_s, debounce_s) from a .claude/fast-test.cmd file.

    A malformed OPTIONAL line must never discard the COMMAND. `timeout=5m` used to raise
    ValueError out of the whole loop and return `(None, DEFAULT, DEFAULT)`, so a repo that had
    deliberately configured a stricter push-time gate got "no test command - nothing to verify,
    allowing push" - wording indistinguishable from a repo that has no tests at all. With a
    `tests/` dir present it was worse: resolve_command fell through to the weaker auto-detected
    command with NO message. Only an unreadable FILE may yield cmd=None, and even that is said
    out loud, because the file existing at all proves the repo intends to be gated.

    `key = value` with spaces is recognised too. Unrecognised, it fell through to the `elif`
    and became the COMMAND - so a typo'd option line was handed to a shell and executed.
    """
    opts = options or _OPTION_KEYS
    cmd, timeout_s, debounce_s = None, DEFAULT_TIMEOUT_S, DEFAULT_DEBOUNCE_S
    name = os.path.basename(path)
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.readlines()
    except OSError as e:
        sys.stderr.write(f"[fast-test] cannot read {name} ({e}); this project is NOT gated.\n")
        return None, DEFAULT_TIMEOUT_S, DEFAULT_DEBOUNCE_S
    for num, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head, sep, val = line.partition("=")
        key = head.strip().lower()
        if sep and key in opts:
            lo, hi = opts[key]
            try:
                parsed = int(val.strip())
            except ValueError:
                sys.stderr.write(
                    f"[fast-test] {name} line {num}: ignoring malformed {key}="
                    f"{val.strip()!r}, using the default. The test command is unaffected.\n")
                continue
            if key == "timeout":
                timeout_s = max(lo, min(hi, parsed))
            else:
                debounce_s = max(lo, min(hi, parsed))
        elif cmd is None:
            cmd = line
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


def _win_job_kill_on_close():
    """A Windows Job Object that kills every process in it when its handle closes, or None.

    `taskkill /T` walks ParentProcessId, so it cannot reach a grandchild once the direct child
    has been reaped - which is precisely the case cleanup is for. A job object is the OS-level
    answer: anything the child spawns is in the job too (jobs are inherited), and closing the
    handle terminates the lot regardless of who is still alive. Fail-safe: any error returns
    None and the caller falls back to taskkill.
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class _IO_COUNTERS(ctypes.Structure):
            _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                        ("WriteOperationCount", ctypes.c_ulonglong),
                        ("OtherOperationCount", ctypes.c_ulonglong),
                        ("ReadTransferCount", ctypes.c_ulonglong),
                        ("WriteTransferCount", ctypes.c_ulonglong),
                        ("OtherTransferCount", ctypes.c_ulonglong)]

        class _BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class _EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", _BASIC),
                        ("IoInfo", _IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(job, 9,  # ExtendedLimitInformation
                                           ctypes.byref(info), ctypes.sizeof(info)):
            k32.CloseHandle(job)
            return None
        return job
    except Exception:
        return None


def _win_job_assign(job, pid) -> None:
    if not job:
        return
    try:
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # PROCESS_SET_QUOTA | PROCESS_TERMINATE - not Popen._handle, which is private.
        handle = k32.OpenProcess(0x0100 | 0x0001, False, int(pid))
        if handle:
            k32.AssignProcessToJobObject(job, handle)
            k32.CloseHandle(handle)
    except Exception:
        pass


def _win_job_close(job) -> None:
    """Closing the last handle terminates every process still in the job."""
    if not job:
        return
    try:
        import ctypes
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(job)
    except Exception:
        pass


def _kill_tree(proc, pgid=None, job=None) -> None:
    """Kill the child AND everything it spawned.

    `pgid` must be captured BEFORE the child is reaped. On the "command exited but a grandchild
    still holds stdout" path - the exact case this cleanup exists for - `proc.wait()` has
    already reaped it, so `os.getpgid(proc.pid)` raises ProcessLookupError straight into the
    except and killpg never fires; on Windows `taskkill /T` reports "process not found" because
    it cannot walk ParentProcessId from a dead parent. The hang was fixed, but the cleanup half
    of the promise silently never ran, so a test command that starts a dev server or watcher
    leaked it every turn and kept its port held.
    """
    if os.name == "nt":
        # The job object is the one that actually reaches an orphaned grandchild; taskkill
        # still runs first because it also handles the case where the job could not be created.
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, timeout=20)
        except Exception:
            pass
        _win_job_close(job)
    else:
        import signal
        # start_new_session makes pgid == the child's pid, so the saved value stays valid
        # after the child is reaped; the whole group dies with it.
        for target in (pgid, getattr(proc, "pid", None)):
            if not target:
                continue
            try:
                os.killpg(target, signal.SIGKILL)
                break
            except Exception:
                continue
    try:
        proc.kill()
    except Exception:
        pass


def run_tests(cmd: str, cwd: str, timeout_s: int) -> tuple[int | None, str]:
    """(returncode, combined output); returncode None means the timeout fired.

    Lives here, not in pre_push_gate, because BOTH gates run a project's test command and both
    had the same defect - pre_push_gate imports this module, so this is the only direction the
    shared code can go. Fixing it in one caller would have left the other hanging.

    subprocess.run(timeout=) bounds NOTHING: it kills the DIRECT child, then calls communicate()
    again with no timeout, blocking until every writer closes the pipe. A vitest/jest watcher, a
    pytest-xdist worker, a gradle daemon or a dev server started by an integration test all
    outlive their parent. At push time that hung `git push` with no output; here it hung the end
    of the turn just as silently.

    Two distinct hazards, both bounded:
      * the command itself overruns -> kill the TREE, report the timeout
      * the command exits but something it spawned still holds stdout -> the verdict is already
        known, so return it at once and kill the survivor rather than waiting on the pipe
    The reader is a daemon thread and never calls communicate(): a second concurrent
    communicate() from the timeout path races Popen's own wait lock.
    """
    import threading
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kw["start_new_session"] = True  # own process group, so killpg reaches the whole tree
    job = _win_job_kill_on_close()
    proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            universal_newlines=True, encoding="utf-8", errors="replace", **kw)
    # Assign immediately: jobs are inherited, so anything the child spawns from here on is in
    # the job too and dies with it - even after the child itself has been reaped.
    _win_job_assign(job, proc.pid)
    box = {"out": ""}

    def reader():
        try:
            box["out"] = proc.stdout.read() or ""
        except Exception:
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

    t = threading.Thread(target=reader)
    t.daemon = True   # can never keep this process alive, whatever the pipe does
    t.start()

    # Capture the process group BEFORE waiting. proc.wait() reaps the child, after which
    # os.getpgid(proc.pid) raises and the group can no longer be found (D10).
    pgid = None
    if os.name != "nt":
        try:
            pgid = os.getpgid(proc.pid)
        except Exception:
            pgid = proc.pid   # start_new_session guarantees pgid == pid

    timed_out = False
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
    t.join(0.5 if timed_out else 2.0)
    if timed_out or t.is_alive():
        _kill_tree(proc, pgid, job)  # release the pipe; never leave what we spawned running
        t.join(5)
    else:
        _win_job_close(job)          # clean exit: still release the job handle
    return (None if timed_out else proc.returncode), box["out"]


def project_root(cwd: str) -> str:
    """The repo TOPLEVEL - the same anchor pre_push_gate._repo_root() uses.

    [P13 D6] The Stop payload's `cwd` is the SESSION directory, routinely a package
    subdirectory in a monorepo. pre_push_gate keyed the shared state file by `git rev-parse
    --show-toplevel` while this hook keyed it by the raw session cwd, so a pass recorded at
    turn end from `repo/pkg/api` was invisible to the push gate keyed on `repo` - and the
    advertised fast path (skip tests that just passed) could never fire from a subdirectory.
    Finding 28/34 canonicalised the SPELLING of the key; the two gates were still keying
    different DIRECTORIES. Falls back to cwd when git cannot answer, which just restores the
    old behaviour rather than inventing a new key.
    """
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=10,
                           stdin=subprocess.DEVNULL, encoding="utf-8", errors="surrogateescape")
    except (OSError, ValueError, subprocess.SubprocessError):
        return cwd
    if r.returncode != 0:
        return cwd
    top = (r.stdout or "").strip()
    return top if top and os.path.isdir(top) else cwd


def _state_key(cwd: str) -> str:
    """One canonical spelling of a project root, so every caller lands on the same state file.

    pre_push_gate and fast_test_on_stop share this state and are the "one source of truth" the
    docstring promises - but on Windows one of them hashed `C:\\a\\b` and the other `C:/a/b`, so
    a pass recorded by either was invisible to the other and the advertised fast path could
    never fire (findings 28, 34). normcase folds separators and case on Windows and is a no-op
    on POSIX, where two differently-cased paths really are two directories; realpath collapses
    symlinked and 8.3-short-name spellings of the same root.
    """
    try:
        p = os.path.realpath(cwd)
    except OSError:
        p = cwd
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")


def _state_path(cwd: str) -> str:
    return os.path.join(STATE_DIR, "fasttest-" + hashlib.sha1(
        _state_key(cwd).encode("utf-8", "surrogateescape")).hexdigest()[:16] + ".json")


def _nogate_state_path(cwd: str) -> str:
    return os.path.join(STATE_DIR, "nogate-" + hashlib.sha1(
        _state_key(cwd).encode("utf-8", "surrogateescape")).hexdigest()[:16] + ".json")


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
        porcelain = subprocess.run(["git", "-C", cwd, "status", "--porcelain=v1", "-z", "-uall"],
                                   capture_output=True, text=True, timeout=10,
                                   encoding="utf-8", errors="surrogateescape").stdout
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
    if not is_git_worktree(cwd):
        return 0
    # Anchor the SHARED state on the repo toplevel, exactly as pre_push_gate does, so a pass
    # recorded from a package subdirectory is visible to the push gate (P13 D6).
    cwd = project_root(cwd)

    cmd, timeout_s, debounce_s = detect(cwd)
    if not cmd:
        return _notice_no_gate(cwd)

    sp = _state_path(cwd)
    try:
        with open(sp, encoding="utf-8") as fh:
            last = json.load(fh)
    except (OSError, ValueError):
        last = {}
    # [LOW-2] Treat every field as hostile, exactly as pre_push_gate.last_pass does. This
    # reader is the TWIN of that one - same file, same fields - and only one was hardened.
    # A non-dict or non-numeric `ts` raised here; stop_dispatcher swallows it, so the Stop
    # gate went permanently dead in that repo and the poisoned file is never rewritten.
    if not isinstance(last, dict):
        last = {}
    try:
        last_ts = float(last.get("ts") or 0)
    except (TypeError, ValueError):
        last_ts = 0.0
    if time.time() - last_ts < debounce_s:
        return 0

    try:
        porcelain = subprocess.run(["git", "-C", cwd, "status", "--porcelain=v1", "-z", "-uall"],
                                   capture_output=True, text=True, timeout=10,
                                   encoding="utf-8", errors="surrogateescape").stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    if not _changed_source_files(porcelain):
        return 0

    os.makedirs(STATE_DIR, exist_ok=True)
    started = time.time()
    try:
        rc, tail_src = run_tests(cmd, cwd, timeout_s)
    except (OSError, ValueError, subprocess.SubprocessError):
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


def _selftest_gate_alignment() -> list:
    """[P13 D5/D6] The two gates must share a CEILING policy and a state ANCHOR."""
    global project_root, STATE_DIR
    import tempfile
    fails = []

    # D5: the push gate has its own, larger ceiling; the turn-end gate keeps 600.
    if TURN_END_OPTIONS["timeout"][1] != 600:
        fails.append("the turn-end timeout ceiling moved off 600 - a Stop hook must not stall "
                     "a turn: %r" % (TURN_END_OPTIONS["timeout"],))
    if PUSH_OPTIONS["timeout"][1] <= TURN_END_OPTIONS["timeout"][1]:
        fails.append("the push ceiling is not above the turn-end ceiling, so `timeout = 1800` "
                     "in .claude/pre-push.cmd is still clamped and the remedy the gate's own "
                     "error message prescribes is a no-op: %r" % (PUSH_OPTIONS["timeout"],))
    with tempfile.TemporaryDirectory() as td:
        ov = os.path.join(td, "pre-push.cmd")
        with open(ov, "w", encoding="utf-8") as fh:
            fh.write("timeout = 1800" + chr(10) + "python -c \"pass\"" + chr(10))
        _c, t_turn, _d = _read_override(ov)
        _c, t_push, _d = _read_override(ov, PUSH_OPTIONS)
        if t_turn != 600:
            fails.append("turn-end clamp changed: %r" % (t_turn,))
        if t_push != 1800:
            fails.append("the push gate still clamps a configured 1800s to %r" % (t_push,))

    # D6: a SUBDIRECTORY of a repo must key the shared state on the same root as the toplevel.
    with tempfile.TemporaryDirectory() as td:
        try:
            ok = subprocess.run(["git", "-C", td, "init", "-q"], capture_output=True,
                                timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
        if not ok:
            print("SELFTEST SKIP: git unavailable, state-anchor case untested")
            return fails
        sub = os.path.join(td, "pkg", "api")
        os.makedirs(sub, exist_ok=True)
        if _state_path(project_root(sub)) != _state_path(project_root(td)):
            fails.append("a session in a package SUBDIRECTORY keys the shared state file "
                         "differently from the repo toplevel, so the pass it records is "
                         "invisible to the push gate and the fast path never fires")

        # ...and main() must actually APPLY it. The check above only proves project_root()
        # computes the right answer; deleting the one line in main() that calls it left this
        # green (its own mutation came back SURVIVED). Recorder + real main(), same shape as
        # the shared-repo-probe twin guard.
        called = []
        real_pr, real_state = project_root, STATE_DIR

        def _recorder(cwd):
            called.append(cwd)
            return real_pr(cwd)

        project_root = _recorder
        STATE_DIR = os.path.join(td, "state")
        try:
            os.makedirs(STATE_DIR, exist_ok=True)
            real_stdin, sys.stdin = sys.stdin, __import__("io").StringIO(
                __import__("json").dumps({"session_id": "anchor-test", "cwd": sub}))
            real_err, sys.stderr = sys.stderr, __import__("io").StringIO()
            try:
                main()
            finally:
                sys.stdin, sys.stderr = real_stdin, real_err
        finally:
            project_root = real_pr
            STATE_DIR = real_state
        if not called:
            fails.append("main() does not anchor the shared state on the repo toplevel - it is "
                         "keying on the raw session cwd again, so a pass recorded from a "
                         "package subdirectory is invisible to the push gate")
    return fails


def selftest() -> int:
    import tempfile
    fails = []
    # 1b. [plan item 41] the -z form the callers actually request. Fields are NUL-separated
    # and a rename's ORIGINAL name is its own field, so a " -> " parser would mis-read it.
    # git C-quotes non-ASCII under the newline form, which left the returned path a mangled
    # string no os.path call could open - the boolean stayed right, the contract did not.
    z = (" M src/app.py\0R  new/thing.ts\0old.js\0 M docs/readme.md\0"
         "?? tools/données.py\0")
    got = _changed_source_files(z)
    if "src/app.py" not in got:
        fails.append(f"-z parser missed a modified source file: {got}")
    if "new/thing.ts" not in got:
        fails.append(f"-z parser missed the NEW side of a rename: {got}")
    if "old.js" in got:
        fails.append(f"-z parser counted a rename's ORIGINAL name as a change: {got}")
    if "docs/readme.md" in got:
        fails.append(f"-z parser treated a doc as source: {got}")
    if "tools/données.py" not in got:
        fails.append(f"-z parser lost a non-ASCII path: {got}")

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
    # 5b. [findings 28, 34] pre_push_gate SHARES this state file - "same command, same meaning,
    # one source of truth". On Windows one hashed `C:\a\b` and the other `C:/a/b`, so every
    # _record_pass was orphaned and the advertised fast path could never fire.
    if os.name == "nt":
        if _state_path("C:/a/b") != _state_path("C:\\a\\b"):
            fails.append("state key differs by separator - the two gates cannot share a pass")
        if _state_path("C:/A/B") != _state_path("c:/a/b"):
            fails.append("state key is case-sensitive on Windows - one repo, two state files")
    else:
        # The old key lowercased unconditionally, so on a case-SENSITIVE filesystem two
        # genuinely different repos silently shared one state file - each suppressing the
        # other's run. Case must be preserved here.
        if _state_path("/x/Y") == _state_path("/x/y"):
            fails.append("state key folds case on POSIX - two different repos share a file")
    # 5c. a non-ASCII project root must produce a key at all, not a UnicodeEncodeError
    try:
        _state_path("/tmp/José/café")
    except Exception as e:
        fails.append("non-ASCII project root broke the state key: %r" % (e,))
    # 5d. [finding 10] run_tests must be BOUNDED. Two separate hazards, and this hook has to
    # survive both on its own - the identical defect at push time hung `git push`, and here it
    # hung the end of every turn just as silently. Tested at this level as well as in
    # pre_push_gate so that neither gate depends on the other's suite to stay honest.
    _py = sys.executable.replace("\\", "/")
    t0 = time.time()
    rc_b, _ = run_tests('"%s" -c "import subprocess,sys; '
                        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])\""
                        % _py, os.getcwd(), 5)
    took = time.time() - t0
    if took > 30:
        fails.append("run_tests did not bound a grandchild holding the pipe (%.0fs)" % took)
    if rc_b not in (0, 1):
        fails.append("command exited but run_tests reported %r instead of its real code" % rc_b)
    # a command that genuinely overruns must report the timeout, not a verdict
    t1 = time.time()
    rc_t, _ = run_tests('"%s" -c "import time; time.sleep(60)"' % _py, os.getcwd(), 3)
    if rc_t is not None:
        fails.append("run_tests returned %r for a command that overran its timeout" % rc_t)
    if time.time() - t1 > 30:
        fails.append("run_tests timeout is not bounded (%.0fs)" % (time.time() - t1))

    # 5e. [D10] The grandchild must actually be DEAD, not merely stop blocking us. Nothing
    # asserted that, and it was not true: on the "command exited, grandchild holds the pipe"
    # path proc.wait() has already reaped the child, so os.getpgid() raised into a bare except
    # (POSIX) and `taskkill /T` had no parent left to walk (Windows). The hang was fixed while
    # the cleanup half silently never ran - a dev server or watcher started by a test leaked
    # every single turn and kept its port. The survivor writes a marker AFTER sleeping, so the
    # marker existing is proof it outlived the kill.
    import tempfile as _tf5
    _d5 = _tf5.mkdtemp()
    try:
        survived = os.path.join(_d5, "SURVIVED")
        started = os.path.join(_d5, "STARTED")
        # SCRIPT FILES, not nested -c quoting. The old spawner embedded a quoted python
        # program inside another quoted python program inside a shell command; cmd.exe
        # tolerated it, /bin/sh did not. On Linux the grandchild therefore never started, the
        # marker never appeared, and this assertion passed for entirely the wrong reason - CI
        # reported the mutation as a decorative test for two runs (P13 F).
        gc_py = os.path.join(_d5, "gc.py")
        with open(gc_py, "w", encoding="utf-8") as _f:
            _f.write("import time\n"
                     "open(r'%s', 'w').write('x')\n"
                     "time.sleep(4)\n"
                     "open(r'%s', 'w').write('x')\n" % (started, survived))
        sp_py = os.path.join(_d5, "spawn.py")
        with open(sp_py, "w", encoding="utf-8") as _f:
            _f.write("import subprocess, sys\n"
                     "subprocess.Popen([sys.executable, r'%s'])\n" % gc_py)
        run_tests('"%s" "%s"' % (_py, sp_py.replace("\\", "/")), _d5, 5)
        time.sleep(7)   # well past the grandchild's own sleep
        # A fixture that never RAN proves nothing. Without this the case degrades to a silent
        # pass wherever the spawn fails, which is precisely what happened on Linux.
        if not os.path.exists(started):
            fails.append("the D10 grandchild fixture never started, so the kill assertion "
                         "proves nothing here - fix the fixture rather than trusting the green")
        elif os.path.exists(survived):
            fails.append("run_tests left the grandchild ALIVE - it outlived the kill and "
                         "wrote its marker; a dev server started by a test leaks every turn")
    finally:
        _shutil_5 = __import__("shutil")
        _shutil_5.rmtree(_d5, ignore_errors=True)

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

    # ---------------------------------------------------------------- D5 / D6 regressions
    import shutil as _shutil
    import tempfile as _tf

    def _tmp(stack_list):
        d = _tf.mkdtemp()
        stack_list.append(d)
        return d

    _trash = []
    real_state3 = STATE_DIR
    try:
        STATE_DIR = _tmp(_trash)
        genv = dict(os.environ)
        genv.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                     "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

        def _git(cwd, *a):
            try:
                return subprocess.run(["git", "-C", cwd] + list(a), capture_output=True,
                                      env=genv, timeout=60).returncode
            except (OSError, subprocess.SubprocessError):
                return 1

        host = _tmp(_trash)
        wt_ok = _git(host, "init", "-q") == 0
        if wt_ok:
            with open(os.path.join(host, "seed.txt"), "w", encoding="utf-8") as f:
                f.write("s\n")
            wt_ok = _git(host, "add", "-A") == 0 and _git(host, "commit", "-qm", "seed") == 0
        wt = os.path.join(_tmp(_trash), "feat")
        if wt_ok:
            wt_ok = _git(host, "worktree", "add", "-q", wt) == 0
        if not wt_ok:
            print("SELFTEST SKIP: git worktree unavailable, D5 untested")
        else:
            # [D5] In a linked worktree `.git` is a FILE, so the old
            # `os.path.isdir(cwd/.git)` guard returned 0 before detect() ever ran: the Stop
            # gate AND its no-gate safety net were both dead for the whole life of the
            # worktree, with rc 0 and empty stderr - indistinguishable from a passing turn.
            if os.path.isdir(os.path.join(wt, ".git")):
                fails.append("fixture wrong: a linked worktree's .git should be a FILE")
            if not is_git_worktree(wt):
                fails.append("is_git_worktree() says a linked worktree is not a repo - the "
                             "Stop gate stays dead there")
            if not is_git_worktree(host):
                fails.append("is_git_worktree() says a plain repo is not a repo")
            # a SUBDIRECTORY of a repo is still in the repo (meta_audit's probe missed this)
            sub = os.path.join(host, "pkg", "deep")
            os.makedirs(sub, exist_ok=True)
            if not is_git_worktree(sub):
                fails.append("is_git_worktree() fails for a subdirectory of a repo")
            if is_git_worktree(_tmp(_trash)):
                fails.append("is_git_worktree() returns True for a non-repo directory")

            # end-to-end: a failing test in a WORKTREE must reach rc 2
            os.makedirs(os.path.join(wt, ".claude"), exist_ok=True)
            with open(os.path.join(wt, ".claude", "fast-test.cmd"), "w", encoding="utf-8") as f:
                f.write('debounce=0\npython -c "import sys; sys.exit(1)"\n')
            with open(os.path.join(wt, "broken.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            real_in, real_err = sys.stdin, sys.stderr
            sys.stdin = io_mod.StringIO(json.dumps({"cwd": wt}))
            sys.stderr = io_mod.StringIO()
            try:
                rc_wt = main()
                err_wt = sys.stderr.getvalue()
            finally:
                sys.stdin, sys.stderr = real_in, real_err
            if rc_wt != 2:
                fails.append(f"failing tests in a linked worktree did not fire: rc={rc_wt} "
                             f"err={err_wt[:120]!r}")

        # [D6] One malformed OPTIONAL line must not discard the COMMAND. `timeout=5m` made
        # _read_override return cmd=None, so the push gate announced "no test command -
        # nothing to verify, allowing push" for a repo that had explicitly configured one.
        ovdir = _tmp(_trash)
        for bad, label in ((("timeout=5m", 'python -c "pass"'), "timeout=5m"),
                           (("debounce=abc", 'python -c "pass"'), "debounce=abc"),
                           ((" timeout = 30s ", 'python -c "pass"'), "spaced timeout"),
                           (("timeout=", 'python -c "pass"'), "empty timeout")):
            ovp = os.path.join(ovdir, "fast-test.cmd")
            with open(ovp, "w", encoding="utf-8") as f:
                f.write(bad[0] + "\n" + bad[1] + "\n")
            real_err = sys.stderr
            sys.stderr = io_mod.StringIO()
            try:
                cmd_o, t_o, d_o = _read_override(ovp)
                warn = sys.stderr.getvalue()
            finally:
                sys.stderr = real_err
            if cmd_o != 'python -c "pass"':
                fails.append(f"{label}: a bad optional line discarded the COMMAND "
                             f"(got {cmd_o!r}) - the gate would report 'nothing to verify'")
            if t_o != DEFAULT_TIMEOUT_S or d_o != DEFAULT_DEBOUNCE_S:
                if label not in ("spaced timeout",):
                    fails.append(f"{label}: bad value not replaced by the default "
                                 f"(timeout={t_o} debounce={d_o})")
            if "fast-test.cmd" not in warn:
                fails.append(f"{label}: parse failure was SILENT - no stderr naming the file")
        # a good file must still parse, and stay silent
        with open(os.path.join(ovdir, "fast-test.cmd"), "w", encoding="utf-8") as f:
            f.write('timeout=222\ndebounce=333\nnpm test\n')
        real_err = sys.stderr
        sys.stderr = io_mod.StringIO()
        try:
            g_cmd, g_t, g_d = _read_override(os.path.join(ovdir, "fast-test.cmd"))
            g_warn = sys.stderr.getvalue()
        finally:
            sys.stderr = real_err
        if (g_cmd, g_t, g_d) != ("npm test", 222, 333):
            fails.append(f"well-formed override regressed: {(g_cmd, g_t, g_d)}")
        if g_warn.strip():
            fails.append(f"well-formed override warned anyway: {g_warn[:100]!r}")
        # an UNREADABLE file is the one case that may yield cmd=None - and must say so
        real_err = sys.stderr
        sys.stderr = io_mod.StringIO()
        try:
            miss = _read_override(os.path.join(ovdir, "nope.cmd"))
        finally:
            sys.stderr = real_err
        if miss[0] is not None:
            fails.append(f"missing override should yield cmd=None, got {miss[0]!r}")
    finally:
        STATE_DIR = real_state3
        for d in _trash:
            _shutil.rmtree(d, ignore_errors=True)

    fails += _selftest_gate_alignment()
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
