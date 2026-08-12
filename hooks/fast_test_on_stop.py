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


# pytest's own defaults for what a test file is called (`python_files`). A project that
# renames them declares so in a config file, which the config branch below already accepts.
_PYTEST_FILE_CAP = 5000     # bounded walk; see _has_collectible_tests for what the cap MEANS
# [FASTTEST-BLOCK] Config markers, each in the file that owns it. `tests/` is deliberately NOT
# on this list: it is Cargo's integration-test directory, and Go/JS/Java projects use it too.
_PYTEST_CONFIG_MARKERS = (
    ("pytest.ini", None),                    # existing at all is the declaration
    ("pyproject.toml", "[tool.pytest"),
    ("setup.cfg", "[tool:pytest]"),
    ("tox.ini", "[pytest]"),
)


def _pytest_importable() -> bool:
    """Can the interpreter that would RUN the command actually import pytest?

    The command is literally `"{sys.executable}" -m pytest`, so this asks about exactly the
    interpreter that will execute it - which is why find_spec is the right question here and
    was the WRONG one in install.py's import closure (OPT-1). There the question was "does
    this file exist for every user" and the answer was about this box; here the box IS the
    subject. Do not "fix" this back into a static check.

    Without it, a repo with real pytest config on a machine where pytest is not installed runs
    `python -m pytest` and gets **rc 1** - byte-identical to a genuine test failure - so no
    exit-code interpretation downstream can ever separate the two. MEASURED, case J.
    """
    try:
        import importlib.util
        return importlib.util.find_spec("pytest") is not None
    except (ImportError, ValueError, AttributeError):
        return False


def _has_pytest_config(cwd: str) -> bool:
    """True iff this project DECLARES itself a pytest project in one of pytest's own config files."""
    for name, marker in _PYTEST_CONFIG_MARKERS:
        p = os.path.join(cwd, name)
        if not os.path.exists(p):
            continue
        if marker is None:
            return True
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                if marker in f.read():
                    return True
        except OSError:
            continue
    return False


def _has_collectible_tests(tests_dir: str) -> bool | None:
    """Does `tests/` hold a file pytest would actually collect? None = could not finish looking.

    Three states on purpose, per this repo's standing rule that a check must distinguish "no
    answer" from "bad answer". Hitting the cap on a huge tree is NOT evidence of absence, and a
    directory that large is almost certainly a real suite - so the caller treats None as accept
    and lets the rc-5 containment below catch it if that guess was wrong. The two halves of the
    fix cover each other here rather than each having to be perfect.
    """
    seen = 0
    try:
        for root, dirs, files in os.walk(tests_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fn in files:
                seen += 1
                if seen > _PYTEST_FILE_CAP:
                    return None
                if not fn.endswith(".py"):
                    continue
                if fn.startswith("test_") or fn[:-3].endswith("_test"):
                    return True
    except OSError:
        return None
    return False


def looks_like_pytest_project(cwd: str) -> bool:
    """Is there real evidence this is a pytest project, beyond a directory called `tests`?

    ONE definition, called by both detect() and the no-gate notice, so the two can never drift
    into disagreeing about what a pytest project is.
    """
    if _has_pytest_config(cwd):
        return True
    tests_dir = os.path.join(cwd, "tests")
    if not os.path.isdir(tests_dir):
        return False
    return _has_collectible_tests(tests_dir) is not False   # None (cap reached) accepts


# pytest's documented exit codes. Only rc 5 (NO_TESTS_COLLECTED) is verdict-free HERE.
#
# [FTB-RC4] rc 4 (USAGE_ERROR) was in this map and that was a REAL DEFECT - a false NEGATIVE,
# which is the more dangerous direction than the false alarm the fix was removing. Found by an
# independent adversarial pass (run wf_a6b49ecf-667), not by the author who wrote both the fix
# and its probes.
#
# The argument that put rc 4 here was "a broken conftest is not the user's tests failing". That
# is backwards: conftest.py is a .py file and is in this module's OWN SRC_EXT, so it is exactly
# the code the gate exists to verify. And because detect() HARD-CODES the argv (`-m pytest -x
# -q`, no user flags), a genuine bad-CLI usage error is UNREACHABLE through the auto-detected
# command - so rc 4 here can essentially only mean the user's own conftest.py or ini failed to
# load. Re-measured against pytest: SyntaxError in conftest, ModuleNotFoundError in conftest, a
# raising tests/conftest.py, and a bad `addopts` in pytest.ini ALL return 4 with ZERO tests run.
#
# Measured A/B through the real hook: with app.py regressed so the suite genuinely fails, a
# broken conftest.py present gave rc 0 (silent green); removing only the conftest gave rc 2 and
# pytest's traceback. The waiver converted a CAUGHT REGRESSION into a silent pass - the precise
# failure this project exists to catch, shipped inside the fix for a different one.
#
# rc 2 (INTERRUPTED) and rc 3 (INTERNAL_ERROR) stay OUT of this map deliberately: both also mean
# nothing was proven, but blocking is the safe direction and neither is a false alarm on correct
# code, which is the only thing criterion 3 asks this map to prevent.
_PYTEST_INCONCLUSIVE = {
    5: "pytest collected no tests, so nothing was verified",
}


_PYTEST_VERSIONED = None    # compiled lazily; `pytest-3`, `pytest-3.11`, ... (Debian/Fedora)


def _is_pytest_command(cmd: str) -> bool:
    """True iff `cmd` invokes pytest, so pytest's exit table applies to its return code.

    [FTB-SPELL] Was a whole-word substring search for "pytest", which was wrong BOTH ways and
    measured so:
      * MISSED `py.test` - pytest's own still-shipped console script - and `pytest-3` /
        `pytest-3.11`, which is what Debian and Fedora install. An unrecognised pytest command
        falls through to the blanket `rc != 0 -> FAILING` branch, i.e. FASTTEST-BLOCK survived
        VERBATIM for those spellings, in both gates.
      * MATCHED `/opt/pytest/bin/collect` - a DIRECTORY named pytest - so an unrelated tool's
        exit 5 would have been waived.

    So ask the question properly: is any ARGUMENT of this command the pytest EXECUTABLE? Test
    the basename of each token, not the raw string. `-m pytest` lands here too, because the
    module name is its own token.
    """
    import re
    global _PYTEST_VERSIONED
    if _PYTEST_VERSIONED is None:
        _PYTEST_VERSIONED = re.compile(r"pytest-\d[\d.]*\Z")
    for tok in re.findall(r"[^\s\"']+", cmd or ""):
        base = tok.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if base.endswith(".exe"):
            base = base[:-4]
        if base in ("pytest", "py.test") or _PYTEST_VERSIONED.match(base):
            return True
    return False


def inconclusive_reason(cmd: str, rc: int | None) -> str | None:
    """Why this run proved NOTHING, or None when `rc` is a real verdict about the user's code.

    [FASTTEST-BLOCK] Both gates mapped every non-zero rc onto "your tests are failing". For
    pytest, rc 5 means it collected nothing and rc 4 means it never got as far as running -
    neither is a statement about the code, and reporting them as failures blocks a turn end
    (and a push) on a repo with nothing wrong. Not applied to non-pytest commands: their exit
    codes mean different things, and misreading one would silently disarm that gate instead.
    """
    if rc is None or not _is_pytest_command(cmd):
        return None
    return _PYTEST_INCONCLUSIVE.get(rc)


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
    # [FASTTEST-BLOCK] `os.path.isdir(cwd/"tests")` used to be sufficient here. MEASURED: that
    # blocked the turn end AND the push on a Rust repo (tests/ is Cargo's own integration-test
    # dir), a Go repo, a JS repo whose package.json has no scripts.test, an empty tests/, and a
    # tests/ holding only helpers - five shapes, all exiting 5 (NOTHING COLLECTED), all
    # reported to the user as "FAILING at stop - fix before finishing".
    if looks_like_pytest_project(cwd) and _pytest_importable():
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


def _reason_slug(reason: str) -> str:
    """A short stable tag for a notice REASON, so two different reasons cannot share a marker.

    [FTB-MASK] These markers used to be keyed on the PATH ALONE. A project therefore got exactly
    ONE notice ever, whichever fired first, and every later - materially DIFFERENT - reason was
    silenced permanently, with nothing in the code to clear it. The masking that
    `_inconclusive_state_path` was added to prevent between the two notice FAMILIES was still
    live WITHIN each of them.
    """
    return hashlib.sha1(reason.encode("utf-8", "surrogateescape")).hexdigest()[:8]


def _nogate_state_path(cwd: str, reason: str = "") -> str:
    return os.path.join(STATE_DIR, "nogate-" + hashlib.sha1(
        _state_key(cwd).encode("utf-8", "surrogateescape")).hexdigest()[:16]
        + ("-" + _reason_slug(reason) if reason else "") + ".json")


def _inconclusive_state_path(cwd: str, reason: str = "") -> str:
    """Its OWN key, deliberately: a project that was once ungated and has since acquired a
    pytest config would otherwise have this notice masked by the stale `nogate-` marker, and
    the two say different things. Distinguishing "there is no gate" from "the gate ran and
    proved nothing" is the whole point of the notice existing. The reason is part of the key
    for the same reason one level down - see _reason_slug [FTB-MASK]."""
    return os.path.join(STATE_DIR, "inconclusive-" + hashlib.sha1(
        _state_key(cwd).encode("utf-8", "surrogateescape")).hexdigest()[:16]
        + ("-" + _reason_slug(reason) if reason else "") + ".json")


def _nogate_reason(cwd: str) -> tuple[str, str]:
    """(kind, message) for why this project has no usable gate. ONE definition, so the marker
    key and the printed text can never disagree about which reason fired."""
    if looks_like_pytest_project(cwd) and not _pytest_importable():
        return ("pytest-not-importable",
                f"[fast-test] This looks like a pytest project, but pytest is not importable by "
                f"{sys.executable} - point .claude/fast-test.cmd at the interpreter that has "
                f"it.\n")
    return ("no-gate-configured",
            "[fast-test] Add one to activate the gate: .claude/fast-test.cmd, package.json "
            "scripts.test, or a pytest config (pytest.ini / pyproject / setup.cfg / tox.ini) "
            "or tests/ containing test_*.py.\n")


def _notice_no_gate(cwd: str) -> int:
    """Say ONCE PER REASON that no test gate exists here, so a skip cannot pass for a green run.

    Only speaks when source files actually changed - i.e. you are writing code in an ungated repo.
    Always exits 0: this is information, never a block. Adding a test command retires it naturally;
    deleting the state file re-arms it.

    [FTB-MASK] Once per REASON, not once per project. This function emits two materially
    different messages, and the second - "your pytest is not usable, so this gate is dead" - is
    the one a user most needs. Keyed on the path alone, whichever fired first silenced the other
    forever.
    """
    kind, why = _nogate_reason(cwd)
    np = _nogate_state_path(cwd, kind)
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
    # `why` and the marker key both come from _nogate_reason(), so the text printed and the
    # reason suppressed can never drift apart.
    sys.stderr.write(
        f"[fast-test] NO TEST GATE in '{name}': source changed, nothing was verified.\n"
        f"{why}"
        f"[fast-test] Said once per project. Delete {np} to hear it again.\n")
    return 0


def _notice_inconclusive(cwd: str, cmd: str, reason: str) -> int:
    """The gate RAN and proved nothing. Say so once, exit 0 - never block on it.

    Once per project rather than every turn: a recurring nag at every turn end is how a guard
    gets switched off, and a switched-off guard is worse than no guard (criterion 3). The push
    gate says it on EVERY push instead, because a push is a rare event where the line is signal.
    """
    ip = _inconclusive_state_path(cwd, reason)
    if os.path.exists(ip):
        return 0
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(ip, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "cwd": cwd, "cmd": cmd, "reason": reason}, f)
    except OSError:
        return 0
    name = os.path.basename(cwd.rstrip("/\\")) or cwd
    sys.stderr.write(
        f"[fast-test] NOTHING VERIFIED in '{name}': {reason} (cmd: {cmd}).\n"
        f"[fast-test] This is NOT a test failure and is not blocking. Point "
        f".claude/fast-test.cmd at a command that runs your tests to gate this project.\n"
        f"[fast-test] Said once per project. Delete {ip} to hear it again.\n")
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
        # [FASTTEST-BLOCK] "non-zero" is not "your tests failed". Ask first whether this run
        # produced a VERDICT at all - a pytest that collected nothing (rc 5) or could not start
        # (rc 4) says nothing about the user's code, and reporting it as a failure hard-blocked
        # the turn end on five measured repo shapes that had nothing wrong with them.
        reason = inconclusive_reason(cmd, rc)
        if reason:
            return _notice_inconclusive(cwd, cmd, reason)
        tail = "\n".join(line for line in tail_src.splitlines() if line.strip())[-1500:]
        sys.stderr.write(f"[fast-test] FAILING at stop - fix before finishing (cmd: {cmd}):\n{tail}\n")
        return 2  # feed the failure back to Claude exactly once (stop_hook_active guards the loop)
    return 0


def selftest() -> int:
    """Delegates to the sibling suite (see fast_test_on_stop_selftest.py)."""
    import fast_test_on_stop_selftest as _s
    return _s.selftest()


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
