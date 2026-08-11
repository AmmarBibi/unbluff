"""Selftest suite for fast_test_on_stop.py - split out to keep the hook body under the 800-line rule.

Imported by fast_test_on_stop.py's `--selftest` dispatch; not a hook and not registered anywhere. It is
listed in hook_health_check.KNOWN_NO_SELFTEST because it IS the selftest - a module whose only
job is testing another one does not need one of its own, and the floor exists to force that
statement rather than let the omission pass unnoticed.

REBINDING RULE, and it is load-bearing: the parent's production code reads the PARENT module's
globals. A `global STATE_DIR` in this file would rebind a name here and leave production
reading the old one, so the test would keep passing while testing nothing - the precise silent
failure this repo exists to catch, and one this split could have introduced for free. Every
rebind therefore goes through `_m.<name> = ...`, and every read of a rebindable name through
`_m.<name>`.
"""

from __future__ import annotations

import fast_test_on_stop as _m

# Snapshot the parent's namespace so the test bodies can use bare names (including the
# underscored helpers `from x import *` would skip). READS only - see the rebinding rule above.
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})

def _selftest_gate_alignment() -> list:
    """[P13 D5/D6] The two gates must share a CEILING policy and a state ANCHOR."""
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
        if _state_path(_m.project_root(sub)) != _state_path(_m.project_root(td)):
            fails.append("a session in a package SUBDIRECTORY keys the shared state file "
                         "differently from the repo toplevel, so the pass it records is "
                         "invisible to the push gate and the fast path never fires")

        # ...and main() must actually APPLY it. The check above only proves _m.project_root()
        # computes the right answer; deleting the one line in main() that calls it left this
        # green (its own mutation came back SURVIVED). Recorder + real main(), same shape as
        # the shared-repo-probe twin guard.
        called = []
        real_pr, real_state = _m.project_root, _m.STATE_DIR

        def _recorder(cwd):
            called.append(cwd)
            return real_pr(cwd)

        _m.project_root = _recorder
        _m.STATE_DIR = os.path.join(td, "state")
        try:
            os.makedirs(_m.STATE_DIR, exist_ok=True)
            real_stdin, sys.stdin = sys.stdin, __import__("io").StringIO(
                __import__("json").dumps({"session_id": "anchor-test", "cwd": sub}))
            real_err, sys.stderr = sys.stderr, __import__("io").StringIO()
            try:
                main()
            finally:
                sys.stdin, sys.stderr = real_stdin, real_err
        finally:
            _m.project_root = real_pr
            _m.STATE_DIR = real_state
        if not called:
            fails.append("main() does not anchor the shared state on the repo toplevel - it is "
                         "keying on the raw session cwd again, so a pass recorded from a "
                         "package subdirectory is invisible to the push gate")
    return fails


def _selftest_no_false_block() -> list:
    """[FASTTEST-BLOCK] A repo that is not a pytest project must never be BLOCKED at turn end.

    MEASURED 2026-08-11 before the fix, through the real entry point, 10 repo shapes: SEVEN
    blocked a turn end (rc 2) with nothing wrong. `tests/` alone was taken as proof of a pytest
    project, so `python -m pytest -x -q` ran in a Rust repo (`tests/` is Cargo's own
    integration-test directory), a Go repo, a JS repo whose package.json has no `scripts.test`,
    an empty `tests/`, and a `tests/` holding only helpers - each exiting 5 (NOTHING COLLECTED)
    and each reported to the user as "FAILING at stop - fix before finishing". A broken root
    conftest exited 4 (USAGE ERROR) and blocked too, and an interpreter without pytest exited
    **1 - the same code as a genuine test failure**, which is why detection has to PREVENT that
    case rather than interpretation contain it.

    `pre_push_gate` calls this same `detect()` (pre_push_gate.py:114) and maps rc != 0 to a
    BLOCKED push, so every one of those shapes also blocked `git push`.

    Two halves, and neither subsumes the other:
      * detection    - `tests/` is not evidence; require pytest CONFIG or a collectible test
                       FILE, and require pytest to be importable by the interpreter that runs it
      * containment  - for a pytest command, rc 5 (collected nothing) and rc 4 (usage error) are
                       "the gate could not answer", not "your tests failed"

    The positive controls are not decoration: a detector that answered None for everything would
    satisfy the false-alarm half perfectly while disabling the hook, so every accept-shape is
    asserted too, and the genuine-failure path is asserted to still BLOCK.
    """
    import json as _json
    import shutil as _sh
    import subprocess as _sp
    import sys as _sys
    import tempfile as _tf

    fails = []
    trash = []
    # DERIVED, not transcribed: each end-to-end block appends its own label, so adding a case
    # cannot leave the printed denominator stale. A hardcoded "2" was wrong within one edit.
    e2e_run = []

    def _dir(files: dict) -> str:
        """A plain directory containing `files` - NO git.

        detect() reads the filesystem and never shells out to git, so a `git init` per
        detection case bought nothing and cost 12 subprocesses per selftest run. That
        footprint is not free: this selftest runs inside a suite whose next gates assert a
        WALL-CLOCK budget, and the I/O burst pushed meta_audit_on_stop from 7.2s to 22.7s
        against a 17.5s cap. A fixture should build exactly what its case needs.
        """
        d = _tf.mkdtemp()
        trash.append(d)
        for rel, body in files.items():
            p = os.path.join(d, *rel.split("/"))
            if body is None:
                os.makedirs(p, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(body)
        return d

    def _repo(files: dict) -> str | None:
        """A real git repo containing `files`. None when git cannot make one (third state).

        Only the END-TO-END cases need this: main() calls is_git_worktree() and returns 0
        before detect() ever runs outside a repo.
        """
        d = _dir(files)
        try:
            if _sp.run(["git", "-C", d, "init", "-q"], capture_output=True,
                       timeout=60).returncode:
                return None
        except (OSError, _sp.SubprocessError):
            return None
        return d

    T_OK = "def test_ok():\n    assert True\n"

    # ---- DECLINE shapes: none of these is a pytest project, none may yield a command -------
    decline = [
        ("rust (tests/ is Cargo's integration-test dir)",
         {"tests/integration.rs": "#[test]\nfn t() {}\n", "src/main.rs": "fn main() {}\n"}),
        ("go repo with a tests/ dir", {"tests/fixtures.json": "{}\n", "main.go": "package main\n"}),
        ("js repo, package.json with no scripts.test",
         {"package.json": '{"name":"x","scripts":{"build":"tsc"}}',
          "tests/app.test.js": "test('x',()=>{});\n"}),
        ("empty tests/ dir", {"tests": None, "app.py": "x = 1\n"}),
        ("tests/ holding only a helper module", {"tests/helpers.py": "def h():\n    return 1\n"}),
    ]
    for label, files in decline:
        d = _dir(files)
        cmd, _, _ = detect(d)
        if cmd is not None:
            fails.append(f"FASTTEST-BLOCK: {label} is not a pytest project but detect() "
                         f"returned {cmd!r} - every turn end there is BLOCKED on pytest's "
                         f"'no tests ran' (rc 5), and so is every push")

    # ---- ACCEPT shapes: a real pytest project must still be detected ----------------------
    accept = [
        ("tests/ with a test_*.py", {"tests/test_ok.py": T_OK}),
        ("tests/ with a *_test.py (pytest's other default)", {"tests/ok_test.py": T_OK}),
        ("test_*.py nested deeper under tests/", {"tests/unit/sub/test_deep.py": T_OK}),
        ("pytest.ini, tests living elsewhere", {"pytest.ini": "[pytest]\n", "src/test_x.py": T_OK}),
        ("pyproject [tool.pytest]", {"pyproject.toml": "[tool.pytest.ini_options]\n"}),
        ("setup.cfg [tool:pytest]", {"setup.cfg": "[tool:pytest]\n"}),
        ("tox.ini [pytest]", {"tox.ini": "[pytest]\n"}),
    ]
    # SYNTHETIC on purpose, and this is the OPT-1 lesson applied rather than re-learned: CI
    # installs NOTHING (no pip install anywhere in .github/workflows, requirements-dev.txt is
    # Pillow only), so _pytest_importable() is False on every runner and True on this box.
    # Asserting the real detect() here would have gone green locally and turned all 16 CI jobs
    # red - which is exactly what the ENTRY-GUARD optional-import regression did. Pinning the
    # gate to True makes the DETECTION logic answer identically everywhere; the gate's other
    # direction is asserted immediately below, so both are covered and neither depends on what
    # happens to be installed.
    _real_imp = getattr(_m, "_pytest_importable", None)
    for label, files in accept:
        d = _dir(files)
        if _real_imp is not None:
            _m._pytest_importable = lambda: True
        try:
            cmd, _, _ = _m.detect(d)
        finally:
            if _real_imp is not None:
                _m._pytest_importable = _real_imp
        if not (cmd and "pytest" in cmd):
            fails.append(f"FASTTEST-BLOCK went too far: {label} IS a pytest project but "
                         f"detect() returned {cmd!r} - the gate is disabled, which is the "
                         f"failure mode the fix must not trade into")
        if not looks_like_pytest_project(d):
            fails.append(f"looks_like_pytest_project() says {label} is not a pytest project - "
                         f"this is the box-independent half, so it is wrong on every machine")

    # ---- the pytest-importable gate is CONSULTED, not merely present ----------------------
    # Case J measured rc 1 for a missing pytest - indistinguishable from a real failure - so
    # this must be decided at detect time. Patch the parent's global (rebinding rule).
    d = _dir({"tests/test_ok.py": T_OK})
    real_imp = getattr(_m, "_pytest_importable", None)
    if real_imp is None:
        fails.append("FASTTEST-BLOCK: detect() has no _pytest_importable gate, so a box "
                     "without pytest still gets 'No module named pytest' reported as a "
                     "FAILING test run (measured rc 1, identical to a real failure)")
    else:
        _m._pytest_importable = lambda: False
        try:
            cmd, _, _ = _m.detect(d)
        finally:
            _m._pytest_importable = real_imp
        if cmd is not None:
            fails.append("FASTTEST-BLOCK: detect() ignores _pytest_importable - it still "
                         f"returned {cmd!r} for an interpreter that cannot run pytest")
        if _m._pytest_importable is not real_imp:
            fails.append("fixture left _pytest_importable patched")

    # ---- containment: pytest's rc 4 / rc 5 are NOT verdicts -------------------------------
    reason_fn = getattr(_m, "inconclusive_reason", None)
    if reason_fn is None:
        fails.append("FASTTEST-BLOCK: no inconclusive_reason() - a pytest run that collected "
                     "NOTHING (rc 5) or could not start (rc 4) is still reported to the user "
                     "as 'FAILING at stop', and blocks the push gate too")
    else:
        pyc = '"python" -m pytest -x -q'
        for rc, must in ((5, True), (4, True), (0, False), (1, False), (2, False)):
            got = reason_fn(pyc, rc)
            if must and not got:
                fails.append(f"inconclusive_reason: pytest rc {rc} must be inconclusive, "
                             f"got {got!r} - the user is blocked on a run that proved nothing")
            if not must and got:
                fails.append(f"inconclusive_reason: pytest rc {rc} is a real VERDICT, but it "
                             f"was waived as {got!r} - the gate would stop biting")
        # pytest's exit table must not be applied to a command that is not pytest. npm's rc 5
        # means something else entirely, and misreading it would silently disarm that gate.
        for other in ("npm test --silent", "go test ./...", "cargo test"):
            if reason_fn(other, 5) or reason_fn(other, 4):
                fails.append(f"inconclusive_reason applied pytest's exit table to {other!r} - "
                             f"a genuine failure there would be waived")

    # ---- END TO END through main(): allowed, and NOT silent -------------------------------
    # rc 0 alone would be satisfied by deleting the hook. The no-gate notice is what keeps a
    # skip from reading as a green run, so it is asserted in the same breath.
    io_mod = __import__("io")
    real_state = _m.STATE_DIR
    sd = _tf.mkdtemp()
    trash.append(sd)
    _m.STATE_DIR = sd
    try:
        d = _repo({"tests/integration.rs": "#[test]\nfn t() {}\n",
                   "src/main.rs": "fn main() {}\n"})
        if d is None:
            fails.append("FASTTEST-BLOCK: could not build the end-to-end rust fixture")
        else:
            real_in, real_err = _sys.stdin, _sys.stderr
            _sys.stdin = io_mod.StringIO(_json.dumps({"cwd": d}))
            _sys.stderr = io_mod.StringIO()
            try:
                rc_e2e = main()
                err_e2e = _sys.stderr.getvalue()
            finally:
                _sys.stdin, _sys.stderr = real_in, real_err
            e2e_run.append("rust-decline")
            if rc_e2e != 0:
                fails.append(f"FASTTEST-BLOCK end-to-end: a rust repo still exits {rc_e2e} at "
                             f"turn end (2 = BLOCKED): {err_e2e[:200]!r}")
            elif "NO TEST GATE" not in err_e2e:
                fails.append("FASTTEST-BLOCK end-to-end: the rust repo is allowed but SILENT - "
                             "an unverified turn now looks exactly like a verified one")
    finally:
        _m.STATE_DIR = real_state

    # ---- SYNTHETIC containment wiring, exercised on EVERY box including CI ----------------
    # The real-pytest case below is skipped wherever pytest is absent - which is every CI
    # runner - so relying on it alone would leave main()'s containment call site unpinned
    # exactly where the mutation job runs, and FTB-4 would come back SURVIVED there. Same
    # shape as M1 (a branch that executes on no CI runner). The command is a real subprocess
    # that exits 4 and carries the bare word `pytest` as an argv token, so _is_pytest_command
    # matches it on every platform without depending on shell comment semantics.
    real_state0 = _m.STATE_DIR
    sd0 = _tf.mkdtemp()
    trash.append(sd0)
    _m.STATE_DIR = sd0
    try:
        d = _repo({"app.py": "x = 1\n"})
        if d is None:
            print("SELFTEST SKIP: git unavailable, synthetic containment wiring untested")
        else:
            os.makedirs(os.path.join(d, ".claude"), exist_ok=True)
            with open(os.path.join(d, ".claude", "fast-test.cmd"), "w", encoding="utf-8") as f:
                f.write('debounce=0\n"%s" -c "import sys; sys.exit(4)" pytest\n'
                        % _sys.executable.replace("\\", "/"))
            real_in, real_err = _sys.stdin, _sys.stderr
            _sys.stdin = io_mod.StringIO(_json.dumps({"cwd": d}))
            _sys.stderr = io_mod.StringIO()
            try:
                rc_syn = main()
                err_syn = _sys.stderr.getvalue()
            finally:
                _sys.stdin, _sys.stderr = real_in, real_err
            e2e_run.append("synthetic-rc4-wiring")
            if rc_syn != 0:
                fails.append(f"FASTTEST-BLOCK: a pytest command exiting 4 still blocks the "
                             f"turn end (rc {rc_syn}) - main() is not consulting "
                             f"inconclusive_reason: {err_syn[:200]!r}")
            elif "NOTHING VERIFIED" not in err_syn:
                fails.append(f"FASTTEST-BLOCK: rc 4 waved through SILENTLY - an unverified "
                             f"turn now looks verified: {err_syn[:200]!r}")
    finally:
        _m.STATE_DIR = real_state0

    # ---- END TO END through main(), reaching the CONTAINMENT call site --------------------
    # The rust case above proves detection; it exits before main() ever evaluates an rc, so it
    # leaves `reason = inconclusive_reason(...)` in main() completely uncovered - a mutation
    # deleting that call would survive it. This is check 7's lesson in this same file: testing
    # the helper is not testing the WIRING. A real pytest project with a broken root conftest
    # exits 4 (MEASURED, case H) and is the shape that reaches the branch.
    real_state = _m.STATE_DIR
    sd3 = _tf.mkdtemp()
    trash.append(sd3)
    _m.STATE_DIR = sd3
    try:
        have_pytest = False
        try:
            have_pytest = __import__("importlib.util", fromlist=["util"]).find_spec(
                "pytest") is not None
        except Exception:
            have_pytest = False
        d = _repo({"tests/test_ok.py": T_OK, "app.py": "x = 1\n",
                   "conftest.py": "import unbluff_nonexistent_plugin_xyz\n"})
        if d is None:
            fails.append("FASTTEST-BLOCK: could not build the broken-conftest fixture")
        elif not have_pytest:
            print("SELFTEST SKIP: pytest not importable here, so the rc-4 containment WIRING "
                  "in main() could not be exercised - it was NOT verified on this box")
        else:
            real_in, real_err = _sys.stdin, _sys.stderr
            _sys.stdin = io_mod.StringIO(_json.dumps({"cwd": d}))
            _sys.stderr = io_mod.StringIO()
            try:
                rc_cf = main()
                err_cf = _sys.stderr.getvalue()
            finally:
                _sys.stdin, _sys.stderr = real_in, real_err
            e2e_run.append("rc4-containment-wiring")
            if rc_cf != 0:
                fails.append(f"FASTTEST-BLOCK: a pytest run that could not START (rc 4) still "
                             f"exits {rc_cf} from main() - main() is not consulting "
                             f"inconclusive_reason, so the containment is unwired")
            elif "NOTHING VERIFIED" not in err_cf:
                fails.append(f"FASTTEST-BLOCK: rc 4 was waved through SILENTLY - a run that "
                             f"proved nothing now looks like a green one: {err_cf[:200]!r}")
    finally:
        _m.STATE_DIR = real_state

    # ---- END TO END control: a genuinely failing pytest suite must STILL block -------------
    # Deliberately the one case that pays for a real pytest invocation (~1s). Everything else
    # above is filesystem-only, because this selftest shares hook_health_check's 25s cap.
    real_state = _m.STATE_DIR
    sd2 = _tf.mkdtemp()
    trash.append(sd2)
    _m.STATE_DIR = sd2
    try:
        d = _repo({"tests/test_bad.py": "def test_bad():\n    assert False\n",
                   "app.py": "x = 1\n"})
        have_pytest = False
        try:
            have_pytest = __import__("importlib.util", fromlist=["util"]).find_spec(
                "pytest") is not None
        except Exception:
            have_pytest = False
        if d is None:
            fails.append("FASTTEST-BLOCK: could not build the failing-suite control")
        elif not have_pytest:
            # THIRD STATE: this box cannot present the case. Say so; never pass quietly.
            print("SELFTEST SKIP: pytest not importable here, so the 'a real failure still "
                  "BLOCKS' control could not be run - it was NOT verified on this box")
        else:
            real_in, real_err = _sys.stdin, _sys.stderr
            _sys.stdin = io_mod.StringIO(_json.dumps({"cwd": d}))
            _sys.stderr = io_mod.StringIO()
            try:
                rc_bad = main()
                err_bad = _sys.stderr.getvalue()
            finally:
                _sys.stdin, _sys.stderr = real_in, real_err
            e2e_run.append("genuine-failure-still-blocks")
            if rc_bad != 2:
                fails.append(f"the fix disarmed the gate: a genuinely FAILING pytest suite "
                             f"exited {rc_bad} instead of 2 ({err_bad[:200]!r})")
    finally:
        _m.STATE_DIR = real_state
        for t in trash:
            _sh.rmtree(t, ignore_errors=True)
    # The end-to-end count is what was actually RUN, so a case skipped for a missing pytest
    # shrinks the printed number instead of being silently counted as covered.
    print(f"-- fast-test detection: {len(decline)} decline shape(s), {len(accept)} accept "
          f"shape(s), 1 importable gate, {len(e2e_run)} end-to-end case(s) run "
          f"({', '.join(e2e_run) if e2e_run else 'NONE'})")
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
    # 3. pytest auto-detect. [FASTTEST-BLOCK] This case used to create a BARE `tests/` dir and
    #    require a pytest command back - i.e. it ASSERTED the defect, which is a large part of
    #    why the defect survived every review. It is corrected here rather than deleted: the
    #    intent (autodetection must work) is kept, the false premise (a directory named `tests`
    #    proves a pytest project) is replaced by real evidence. The bare-dir shape is now
    #    asserted in the opposite direction, in _selftest_no_false_block.
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "tests"))
        with open(os.path.join(td, "tests", "test_x.py"), "w", encoding="utf-8") as f:
            f.write("def test_x():\n    assert True\n")
        # detect() now also requires pytest to be IMPORTABLE, which is false on every CI
        # runner (nothing is pip-installed there) and true here. Pin it so this case asks
        # about DETECTION and answers the same on every box - see _selftest_no_false_block.
        _ri = getattr(_m, "_pytest_importable", None)
        if _ri is not None:
            _m._pytest_importable = lambda: True
        try:
            cmd, _, _ = _m.detect(td)
        finally:
            if _ri is not None:
                _m._pytest_importable = _ri
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
        # The grandchild must outlive the runner's timeout by a wide margin. It slept 4s
        # against a 5s timeout, so on a fast Linux runner it finished on its own before any
        # kill mattered and SURVIVED went unwritten whatever _kill_tree did - the mutation came
        # back SURVIVED on ubuntu twice for exactly that reason (P13 F).
        gc_sleep = 9
        # [P14 D1-FIND] The grandchild now HEARTBEATS while it is alive instead of sleeping
        # opaquely. gc_sleep and the runner timeout are UNCHANGED - they are the margin that
        # makes SURVIVED mean something, and the two previous attempts to shave them each
        # produced a decorative test (4s vs 5s finished on its own on fast Linux; an 8s blind
        # poll ran before a genuine survivor could write, on Windows). What changed is only
        # how DEATH is observed: waiting for the survivor window to CLOSE cost ~gc_sleep+3s
        # on the healthy path, which is most of why this selftest measured 25.05-25.51s
        # against the 25s cap that governs it - a PASSING hook reported as "ERRORED/timed
        # out" in the weekly sweep. A stalled heartbeat proves the kill directly and
        # positively, which is strictly better evidence than an absence.
        beat = os.path.join(_d5, "BEAT")
        _f_txt = ("import time\n"
                  "open(r'%s', 'w').write('x')\n"
                  "_end = time.time() + %d\n"
                  "while time.time() < _end:\n"
                  "    open(r'%s', 'w').write('x')\n"
                  "    time.sleep(0.2)\n"
                  "open(r'%s', 'w').write('x')\n"
                  % (started, gc_sleep, beat, survived))
        with open(gc_py, "w", encoding="utf-8") as _f:
            _f.write(_f_txt)
        sp_py = os.path.join(_d5, "spawn.py")
        with open(sp_py, "w", encoding="utf-8") as _f:
            _f.write("import subprocess, sys\n"
                     "subprocess.Popen([sys.executable, r'%s'])\n" % gc_py)
        run_tests('"%s" "%s"' % (_py, sp_py.replace("\\", "/")), _d5, 3)
        # POLL against the grandchild's OWN start time rather than sleeping a guessed amount.
        # A blind sleep has to out-guess the spawn latency, and it kept losing: at 4s and at
        # 8s the check ran BEFORE a genuine survivor would have written, so the mutation came
        # back SURVIVED on Windows - a test passing because it looked too early. Anchoring the
        # deadline to the STARTED marker makes it correct on a fast Linux runner and a slow
        # Windows one alike, and it costs only what it needs to.
        _deadline = time.time() + gc_sleep + 20
        _BEAT_STALL_S = 2.0     # > 10x the 0.2s beat interval, so a slow box cannot fake death
        while time.time() < _deadline:
            if os.path.exists(survived):
                break
            # A STALLED heartbeat is positive evidence the grandchild is gone. This is the
            # fast path and the common one: the kill lands ~3s in, the beat stops, and we
            # conclude ~2s later instead of waiting out the whole survivor window.
            if os.path.exists(beat) and time.time() - os.path.getmtime(beat) > _BEAT_STALL_S:
                break
            # BACKSTOP, unchanged: if the heartbeat never appeared at all (a spawn so slow
            # the grandchild never wrote one), fall back to the original absence rule rather
            # than looping to the deadline. Removing this would make a never-started
            # grandchild look identical to a killed one - the STARTED check below is what
            # separates them, and it must still be reachable.
            if os.path.exists(started) and \
                    time.time() - os.path.getmtime(started) > gc_sleep + 3:
                break       # the survivor window has closed: it is genuinely dead
            time.sleep(0.25)
        # A fixture that never RAN proves nothing. Without this the case degrades to a silent
        # pass wherever the spawn fails.
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
    real_state, io_mod = _m.STATE_DIR, __import__("io")
    with tempfile.TemporaryDirectory() as sd:
        _m.STATE_DIR = sd

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
        _m.STATE_DIR = real_state
    if _m.STATE_DIR != real_state:  # paranoia: never leave the global patched
        _m.STATE_DIR = real_state
        fails.append("_m.STATE_DIR was left patched after selftest")
    # 7. main() INTEGRATION: the no-gate notice must actually be reachable through main().
    #    Testing _notice_no_gate() alone leaves the one line that calls it uncovered - a mutation
    #    reverting `return _notice_no_gate(cwd)` to `return 0` passed checks 1-6 untouched
    #    (verified 2026-07-29). Drive the real entry point, not just the helper.
    real_state2 = _m.STATE_DIR
    with tempfile.TemporaryDirectory() as sd:
        _m.STATE_DIR = sd
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
        _m.STATE_DIR = real_state2

    # ---------------------------------------------------------------- D5 / D6 regressions
    import shutil as _shutil
    import tempfile as _tf

    def _tmp(stack_list):
        d = _tf.mkdtemp()
        stack_list.append(d)
        return d

    _trash = []
    real_state3 = _m.STATE_DIR
    try:
        _m.STATE_DIR = _tmp(_trash)
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
        _m.STATE_DIR = real_state3
        for d in _trash:
            _shutil.rmtree(d, ignore_errors=True)

    fails += _selftest_gate_alignment()
    fails += _selftest_no_false_block()
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1
