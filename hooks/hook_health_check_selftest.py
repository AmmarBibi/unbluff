"""Selftest suite for hook_health_check.py - split out to keep the hook body under the 800-line rule.

Imported by hook_health_check.py's `--selftest` dispatch; not a hook and not registered
anywhere. It is listed in hook_health_check.KNOWN_NO_SELFTEST because it IS the selftest - a
module whose only job is testing another one does not need one of its own, and the floor exists
to force that statement rather than let the omission pass unnoticed.

Split on 2026-08-06 when HB-1 took the hook body to 858 lines. M3 had recorded it at 790
specifically so the next addition would be a deliberate decision rather than the edit that
quietly crosses the line, and B3-P set the precedent that the answer is to MOVE code rather
than log the violation.

REBINDING RULE, inherited verbatim from fast_test_on_stop_selftest.py and load-bearing: the
parent's production code reads the PARENT module's globals, so assigning to a bare name here
would rebind only this module's copy and leave production reading the old one - the test would
keep passing while testing nothing. Before the split, the moved code was scanned mechanically
for that hazard: ZERO `global` statements and ZERO assignments to any parent global, against 6
read-only uses (_HOOKS_DIR, _LOCAL_HOOKS_FLOOR, _SELFTEST_TIMEOUT_S, _WEEKLY_BUDGET_S,
_WEEKLY_MARKER, _WEEKLY_PROGRESS). The snapshot below is therefore READS ONLY. Any future
rebind must go through `_m.<name> = ...`, and any read of a rebindable name through `_m.<name>`.
"""

from __future__ import annotations

import hook_health_check as _m

# Snapshot the parent's namespace so the test bodies can use bare names (including the
# underscored helpers `from x import *` would skip). READS only - see the rebinding rule above.
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})


def _selftest_malformed_config() -> list:
    """[P13 C4/C5] A malformed sub-tree must cost that sub-tree, never the whole report."""
    fails = []
    shapes = [
        {"hooks": "not-a-dict"},
        {"hooks": ["not-a-dict"]},
        {"hooks": {"Stop": "not-a-list"}},
        {"hooks": {"Stop": {"not": "a list"}}},
        {"hooks": {"Stop": [{"hooks": "not-a-list"}]}},
        {"hooks": {"Stop": [{"hooks": [{"command": {"a": 1}}]}]}},
        {"hooks": {"Stop": [{"hooks": [{"command": 42, "args": "not-a-list"}]}]}},
        {"hooks": {"Stop": [{"hooks": [{"command": None}]}]}},
        {"hooks": None},
        "not-a-dict-at-all",
    ]
    for shape in shapes:
        try:
            list(_iter_hook_commands(shape))
        except Exception as e:
            fails.append("_iter_hook_commands raised on %r: %r - one bad sub-tree discards "
                         "the entire hook-health report" % (shape, e))
    # a non-string command must be REPORTED, not merely survived: surviving in silence still
    # leaves the malformed entry unmentioned, which is half the defect.
    bad = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": 42}]}]}}
    try:
        n_cmd, problems = check_config(bad)
    except Exception as e:
        fails.append("check_config raised on a non-string command: %r" % (e,))
    else:
        if not any("not a string" in str(p_) for p_ in problems):
            fails.append("a non-string hook command was not reported: %r" % (problems,))
    return fails


def _selftest_shell_builtin_is_not_missing() -> list:
    """[HB-1] A hook command the shell CAN run must not be reported as a missing executable.

    Claude Code runs a hook command through a shell, so the shell's builtins are valid even
    though shutil.which() - which looks for a FILE on PATH - cannot see them. `echo` is the
    canonical trivial hook and is a cmd.exe builtin on Windows, so this hook reported a WORKING
    config as broken on the one line the user reads at every SessionStart. B3-FP's rule: a
    guard that fires on a correct config gets disabled, which is strictly worse than none.

    MEASURED before fixing: check_config({"Stop": [... "echo other"]}) returned
    ['Stop: executable not on PATH: echo'] on win32 while `echo other` ran with rc=0 through
    the shell. It stayed green in CI because the integration job is ubuntu-only, where
    /bin/echo is a real file - P13 F's shape, already fixed for the mutation jobs with a
    Windows mirror and never applied here.

    Both directions are asserted. A guard that stops reporting a genuinely missing executable
    would "pass" this test while being useless, which is the trade this repo never makes.
    """
    fails = []
    # DERIVED, not named. The first version hardcoded `echo` on Windows and `export` on POSIX,
    # and CI proved the Windows half wrong: GitHub's windows-latest runners carry Git for
    # Windows' usr/bin on PATH, so shutil.which("echo") FINDS echo.exe there. The unfixed code
    # never flagged it, so reverting the fix changed nothing and mutation HB1a came back
    # SURVIVED - a test that could not fail, on the very machine it was written to protect.
    #
    # Which builtins are invisible to which() is a property of the BOX, so the fixture asks the
    # box instead of guessing. `.isalpha()` only to keep the message readable.
    _pool = sorted(b for b in (_CMD_BUILTINS if os.name == "nt" else _SH_BUILTINS)
                   if b.isalpha() and shutil.which(b) is None)
    if not _pool:
        # An extractor that finds nothing must prove it looked in the right place. With no
        # such token the assertion below is vacuous, and vacuous must never read as passing.
        fails.append("no shell builtin on this machine is invisible to shutil.which(), so the "
                     "branch this test exists for was never exercised - it proved nothing")
    for builtin in _pool[:1]:
        _n, probs = check_config({"hooks": {"Stop": [{"matcher": "*", "id": "someone-else:keep",
                                  "hooks": [{"type": "command",
                                             "command": "%s other" % builtin}]}]}})
        if any("not on PATH" in str(p_) for p_ in probs):
            fails.append("a shell-builtin hook command (`%s other`) is reported as a missing "
                         "executable: %r - a correct config reads as broken at every "
                         "SessionStart" % (builtin, probs))
    # ...and the check must keep its teeth.
    _n, probs = check_config({"hooks": {"Stop": [{"matcher": "*", "id": "x",
                              "hooks": [{"type": "command",
                                         "command": "ub-definitely-not-a-real-exe --go"}]}]}})
    if not any("not on PATH" in str(p_) for p_ in probs):
        fails.append("a genuinely missing executable was NOT reported (%r) - the builtin "
                     "exemption swallowed the real case too" % (probs,))
    return fails


def selftest() -> int:
    fails = []
    # 0. [finding 18] the weekly sweep must be DETECTED, not listed. The roster it replaced
    # excluded all four v1.3.0 hooks, so any of them could be broken outright while the line
    # printed at every SessionStart still read "weekly selftests 10/10 OK". run_selftests.py
    # had the identical roster; both now call selftestable_hooks(), so there is no twin left
    # to drift. Assert the OUTCOME (these names are swept) and the MECHANISM (a brand-new
    # self-testable hook is picked up with no edit to any list).
    _detected = {os.path.basename(p) for p in selftestable_hooks()}
    for _name in ("pre_push_gate.py", "close_skills_guard.py",
                  "duplicate_registration_check.py", "usage_snip_prompt.py"):
        if _name not in _detected:
            fails.append(f"weekly sweep does not cover {_name} - breaking it would still "
                         f"report all-green")
    if len(_detected) < len(_LOCAL_HOOKS_FLOOR):
        fails.append(f"detection ({len(_detected)}) found fewer hooks than the floor "
                     f"({len(_LOCAL_HOOKS_FLOOR)})")
    if floor_violations():
        fails.append(f"floor violations in the live hooks dir: {floor_violations()}")

    import tempfile
    # The fixtures below must CONTAIN a real dispatch, but THIS FILE must not: has_selftest()
    # scans hook files as TEXT, so a bare literal here makes the sibling look self-testable.
    # It has no __main__ block, so run_selftests would then "run" it, get rc=0 with no output,
    # and count a gate that verified nothing - W-RS2's exact defect, manufactured by the split.
    # Observed for real: the suite went 32 -> 33 and readme-fresh went red on the first run
    # after the move. Composed rather than written out, so the detector cannot see it here.
    _flag = "--" + "selftest"
    with tempfile.TemporaryDirectory() as _d:
        with open(os.path.join(_d, "brand_new_hook.py"), "w", encoding="utf-8") as f:
            f.write('import sys\nif "%s" in sys.argv:\n    print("SELFTEST OK")\n' % _flag)
        with open(os.path.join(_d, "argv_form_hook.py"), "w", encoding="utf-8") as f:
            f.write('def main(argv):\n    return 0\nif "%s" in argv:\n    pass\n' % _flag)
        with open(os.path.join(_d, "no_selftest_hook.py"), "w", encoding="utf-8") as f:
            f.write('"""Mentions --selftest in prose only, so it must NOT be detected."""\n')
        _got = {os.path.basename(p) for p in selftestable_hooks(_d)}
        if _got != {"brand_new_hook.py", "argv_form_hook.py"}:
            fails.append(f"detection wrong on a synthetic dir: {sorted(_got)} "
                         f"(a prose mention must not count; both argv forms must)")
        if len(all_hook_files(_d)) != 3:
            fails.append("all_hook_files() is not counting the full denominator")
        # a hook with no selftest and no explicit opt-out must turn the gate red, not vanish
        if not any("no_selftest_hook.py" in v for v in floor_violations(_d)):
            fails.append("a hook with no selftest is silently dropped instead of flagged")

    # 0b. [finding 19] THE TWIN MUST NOT COME BACK. run_selftests.py held a byte-identical
    # copy of this detector's roster; one was fixed and the other was not, which is the whole
    # reason finding 18 survived to v1.3.0. Fixing both lists would leave the same trap for the
    # next person, so the durable property is that exactly ONE implementation exists - and
    # that is what this asserts. Any second `def has_selftest` or `_DISPATCH_RE` is a twin.
    _root = os.path.dirname(_HOOKS_DIR)
    _twins = []
    for _p in (all_hook_files() + sorted(glob.glob(os.path.join(_root, "*.py")))
               + sorted(glob.glob(os.path.join(_root, "tools", "*.py")))):
        # `_m.__file__`, NOT `__file__`. The exclusion must name the module that OWNS
        # _DISPATCH_RE, and after the 2026-08-06 split `__file__` here is the SIBLING - so the
        # parent itself was reported as the twin. A9's class ("a canonicalisation is only
        # canonical within the program that defines it") reappearing at a module boundary
        # created minutes earlier. The twin gate caught it on the first run after the move,
        # which is the whole argument for splitting behind a green suite rather than beside one.
        if os.path.abspath(_p) == os.path.abspath(_m.__file__):
            continue
        try:
            with open(_p, encoding="utf-8", errors="replace") as _f:
                _txt = _f.read()
        except OSError:
            continue
        # Anchored to a real definition at the start of a line. An unanchored substring match
        # fired on tools/mutation_check.py, whose mutation TABLE quotes these names as data -
        # a detector that cannot tell a definition from a string is its own false alarm.
        if re.search(r"^\s*def has_selftest\b", _txt, re.M) or \
                re.search(r"^\s*_DISPATCH_RE\s*=", _txt, re.M):
            _twins.append(os.path.basename(_p))
    if _twins:
        fails.append(f"a SECOND selftest detector exists in {_twins} - import "
                     f"selftestable_hooks() instead; two copies of one rule is the defect")

    # 0c. [plan item 38, corrected] "registered once, but from the wrong root". The live
    # config wired close_skills_guard and usage_snip_prompt to ~/.claude/hooks copies that
    # had DIVERGED from the repo, so a whole release of fixes never ran. No existing check
    # could see it: not a duplicate, not a missing file. Must be caught even when the stale
    # copy is byte-identical, because it will not stay identical.
    with tempfile.TemporaryDirectory() as _sd:
        _elsewhere = os.path.join(_sd, "elsewhere")
        os.makedirs(_elsewhere, exist_ok=True)
        _victim = os.path.basename(all_hook_files()[0])
        _stale = os.path.join(_elsewhere, _victim)
        with open(_stale, "w", encoding="utf-8") as f:
            f.write("# a DIVERGED copy of a hook this suite ships\n")
        _cfg = {"hooks": {"SessionStart": [{"hooks": [
            {"command": '"%s" "%s"' % (sys.executable, _stale)}]}]}}
        _probs = stale_root_registrations(_cfg)
        if not any(_victim in p for p in _probs):
            fails.append(f"a hook registered from the WRONG root ({_stale}) was not flagged")
        elif not any("DIFFERENT PROGRAMS" in p for p in _probs):
            fails.append(f"wrong-root registration flagged but divergence not named: {_probs}")
        # and a correctly-wired one must stay silent
        _ok_cfg = {"hooks": {"SessionStart": [{"hooks": [
            {"command": '"%s" "%s"' % (sys.executable, all_hook_files()[0])}]}]}}
        if stale_root_registrations(_ok_cfg):
            fails.append("false positive on a hook registered from its own directory")
        # a path with a SPACE must not slip past the tokenizer (same class as finding 21)
        _spaced_dir = os.path.join(_sd, "John Doe", "hooks")
        os.makedirs(_spaced_dir, exist_ok=True)
        _spaced = os.path.join(_spaced_dir, _victim)
        with open(_spaced, "w", encoding="utf-8") as f:
            f.write("# diverged\n")
        _sp_cfg = {"hooks": {"SessionStart": [{"hooks": [
            {"command": '"%s" "%s"' % (sys.executable, _spaced)}]}]}}
        if not any(_victim in p for p in stale_root_registrations(_sp_cfg)):
            fails.append("a wrong-root registration with a SPACE in the path was missed")

    # 1. a known-good config shape: python exe + this very script as an absolute arg
    good = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                           "command": f'"{sys.executable}" "{os.path.abspath(__file__)}"'}]}]}}
    _, probs = check_config(good)
    if probs:
        fails.append(f"good config flagged: {probs}")
    # 2. a missing absolute script MUST be caught
    bad = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                          "command": f'"{sys.executable}" "{os.path.join(os.sep, "nope", "missing_hook_xyz.py")}"'}]}]}}
    _, probs = check_config(bad)
    if not any("missing script" in p for p in probs):
        fails.append("missing script NOT caught")
    # 3. a missing absolute executable MUST be caught
    bad2 = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                           "command": os.path.join(os.sep, "nope", "ghost.exe") + " run"}]}]}}
    _, probs = check_config(bad2)
    if not any("missing executable" in p for p in probs):
        fails.append("missing executable NOT caught")
    # 4. malformed configs MUST be reported, never raise (the whole point of this hook)
    for label, malformed in [
        ("hooks-is-list", {"hooks": [1, 2, 3]}),
        ("group-not-dict", {"hooks": {"Stop": ["oops"]}}),
        ("entry-not-dict", {"hooks": {"Stop": [{"hooks": ["oops"]}]}}),
        ("group-hooks-not-list", {"hooks": {"Stop": [{"hooks": {"bad": 1}}]}}),
    ]:
        try:
            _, probs = check_config(malformed)
            if not probs:
                fails.append(f"malformed config '{label}' produced no problem")
        except Exception as e:  # must never raise
            fails.append(f"malformed config '{label}' RAISED {e!r}")
    # 5. args-style declaration: the script must be validated, not just the interpreter
    import tempfile
    missing = os.path.join(os.sep, "nope", "args_style_missing.py")
    args_cfg = {"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": sys.executable, "args": [missing]}]}]}}
    _, probs = check_config(args_cfg)
    if not any("missing script" in p for p in probs):
        fails.append("args-style missing script NOT caught (only `command` was read)")

    # 6. duplicate registration: same script name from two directories must be reported
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        for d in (d1, d2):
            with open(os.path.join(d, "dupe.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
        with open(os.path.join(d1, "solo.py"), "w", encoding="utf-8") as f:
            f.write("y = 1\n")
        dup_cfg = {"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": f'"{sys.executable}" "{os.path.join(d1, "dupe.py")}"'},
            {"type": "command", "command": sys.executable, "args": [os.path.join(d2, "dupe.py")]},
            {"type": "command", "command": f'"{sys.executable}" "{os.path.join(d1, "solo.py")}"'},
        ]}]}}
        _, probs = check_config(dup_cfg)
        if not any("dupe.py registered from 2 directories" in p for p in probs):
            fails.append(f"duplicate registration NOT caught: {probs}")
        if any("solo.py registered" in p for p in probs):
            fails.append("false positive: singly-registered hook flagged as duplicate")

    # 7. weekly selftest runner: catches a failing hook, marker written only on all-pass, counts pass/run
    with tempfile.TemporaryDirectory() as td:
        ok_hook = os.path.join(td, "ok_hook.py")
        bad_hook = os.path.join(td, "bad_hook.py")
        with open(ok_hook, "w", encoding="utf-8") as f:
            f.write("import sys; sys.exit(0)\n")
        with open(bad_hook, "w", encoding="utf-8") as f:
            f.write("print('SELFTEST FAIL: broken'); import sys; sys.exit(1)\n")
        state = os.path.join(td, "state")
        # a selftest that cannot RUN (exit SKIP_RC) is neither a pass nor a failure
        skip_hook = os.path.join(td, "skip_hook.py")
        with open(skip_hook, "w", encoding="utf-8") as f:
            f.write("print('SELFTEST SKIP: git unavailable'); import sys; sys.exit(77)\n")
        # Each sub-case gets its OWN state dir: the sweep is now resumable, so `done` persists
        # between calls sharing a state dir and the counts are cumulative by design.
        def _state(tag):
            return os.path.join(td, "state-" + tag)

        probs, n, n_passed, n_skipped, _ = run_weekly_selftests(
            [ok_hook, bad_hook], _state("a"))
        if n != 2 or n_passed != 1 or not any("bad_hook.py" in p for p in probs):
            fails.append(f"weekly runner counts wrong: n={n} passed={n_passed} probs={probs}")
        if os.path.exists(os.path.join(_state("a"), _WEEKLY_MARKER)):
            fails.append("weekly marker written despite a failure")
        # missing hook is reported but does not inflate the run count
        probs_m, n_m, passed_m, _, _ = run_weekly_selftests(
            [ok_hook, os.path.join(td, "gone.py")], _state("b"))
        if n_m != 1 or passed_m != 1 or not any("missing hook" in p for p in probs_m):
            fails.append(f"missing-hook accounting wrong: n={n_m} passed={passed_m} probs={probs_m}")
        # [finding 32] a SKIP must never be counted as a pass - that is how a gate evaporates
        probs_s, n_s, passed_s, skipped_s, _ = run_weekly_selftests(
            [ok_hook, skip_hook], _state("c"))
        if skipped_s != 1 or passed_s != 1 or n_s != 2:
            fails.append(f"skip accounting wrong: n={n_s} passed={passed_s} skipped={skipped_s}")
        if any("skip_hook" in p for p in probs_s):
            fails.append("a skip was reported as a failure rather than a skip")
        # [finding 32] and the CONSEQUENCE, not just the counts: the marker buys a week of
        # silence, and a skipped selftest verified nothing. Asserting only the counts let a
        # mutation that re-enabled the write survive - counts right, consequence wrong.
        if os.path.exists(os.path.join(_state("c"), _WEEKLY_MARKER)):
            fails.append("weekly marker written despite a SKIPPED selftest - a week of "
                         "silence bought for a hook nobody actually tested")
        probs2, n2, passed2, _, _ = run_weekly_selftests([ok_hook], _state("d"))
        if probs2 or n2 != 1 or passed2 != 1 \
                or not os.path.exists(os.path.join(_state("d"), _WEEKLY_MARKER)):
            fails.append(f"all-pass run did not write the marker: {probs2} n={n2} passed={passed2}")
        probs3, n3, _, _, _ = run_weekly_selftests([ok_hook], _state("d"))  # within week -> skip
        if n3 != 0:
            fails.append(f"weekly skip not honored: n={n3}")

        # [D11] AGGREGATE budget + RESUMABILITY. There was no total deadline: 14 hooks at a 45s
        # per-hook cap inside a SessionStart hook that inherited the 60s host default, with the
        # marker written only after the whole loop - so an overrun was killed having recorded
        # NOTHING and started from scratch next session, potentially never completing.
        if _SELFTEST_TIMEOUT_S >= _WEEKLY_BUDGET_S:
            fails.append(f"per-hook cap ({_SELFTEST_TIMEOUT_S}s) >= aggregate budget "
                         f"({_WEEKLY_BUDGET_S}s): one slow hook consumes the whole slice")
        slow = os.path.join(td, "slow_hook.py")
        with open(slow, "w", encoding="utf-8") as f:
            f.write("import time; time.sleep(3); print('SELFTEST OK')\n")
        slow2 = os.path.join(td, "slow2_hook.py")
        with open(slow2, "w", encoding="utf-8") as f:
            f.write("import time; time.sleep(3); print('SELFTEST OK')\n")
        st = _state("budget")
        p1, c1, ok1, _, left1 = run_weekly_selftests([slow, slow2, ok_hook], st, budget_s=1)
        if c1 != 1:
            fails.append(f"budget not enforced: ran {c1} hooks with a 1s aggregate budget")
        if left1 != 2:
            fails.append(f"incomplete sweep did not report what was LEFT: left={left1} - "
                         f"a shrinking sample must never be invisible")
        if os.path.exists(os.path.join(st, _WEEKLY_MARKER)):
            fails.append("marker written for an INCOMPLETE sweep - a week of false silence")
        if not os.path.exists(os.path.join(st, _WEEKLY_PROGRESS)):
            fails.append("no progress persisted - the next session restarts from scratch")
        # resume: the already-proved hook must NOT be re-run, and the sweep must finish
        p2, c2, ok2, _, left2 = run_weekly_selftests([slow, slow2, ok_hook], st, budget_s=60)
        if c2 != 3 or ok2 != 3:
            fails.append(f"resume did not complete the sweep: n={c2} passed={ok2} probs={p2}")
        if p2 or left2:
            fails.append(f"completed resume still reported problems: {p2} left={left2}")
        if not os.path.exists(os.path.join(st, _WEEKLY_MARKER)):
            fails.append("completed sweep did not write the marker")
        if os.path.exists(os.path.join(st, _WEEKLY_PROGRESS)):
            fails.append("progress file not cleared after a completed sweep")
    fails += _selftest_malformed_config()
    fails += _selftest_shell_builtin_is_not_missing()
    # [P14 D1] share 0.40 = 10.0s. Measured 2026-08-02: 6.53s, 26% of the cap. It runs OTHER
    # hooks' selftests inside its own, so it is legitimately heavier than a leaf hook and
    # carries a recorded share rather than the 0.50 default.
    fails += selftest_budget.report(0.40, "hook_health_check")
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1
