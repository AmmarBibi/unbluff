#!/usr/bin/env python3
"""Gate: every mutation anchor must still match the source it is anchored to.

[P14 M1] A mutation entry finds its target by a literal `find` string. An unrelated fix that
edits that line does not break the build, does not break the mutated hook, and does not break
any FILTERED mutation run - it silently makes the mutation UNRUNNABLE. The harness reports it
honestly as `HARNESS ERROR`, but only on the FULL sweep, which takes ~25 minutes and is CI-only.
The window between disarming a mutation and hearing about it is therefore a whole CI cycle at
best, and the mutation table is what certifies every other fix in this repo as pinned.

MEASURED 2026-08-05: the B3 entry-encoding change (the duplicate-registration invocation key
grew event/matcher fields) broke the anchor for mutation `#20/23`. Every filtered run reported
clean. The response at the time was to re-anchor that one entry and hand-check the rest once -
an instance fix, with nothing stopping the next edit doing exactly the same thing.

This is the durable half, and it is cheap: reading each unit once is sub-second against the
~25-minute sweep it stands in for, so it can run on every stop instead of only in CI.

ONE implementation: the rule lives in `mutation_check.missing_anchors()` / `anchor_audit()` and
is shared with `mutation_check.run()`. A second copy of the rule here would be the twin defect
this repo hunts - a gate whose rule has quietly diverged from the harness it speaks for is
worse than no gate, because it reports on something other than what actually runs.

SCOPE, deliberately not widened: this checks anchor PRESENCE, exactly as `run()` does. Anchor
UNIQUENESS - failing when a `find` matches more than once, so `str.replace(..., 1)` mutates the
wrong site - is a real and separate defect, scheduled as M-M12 in cluster 2. The multi-match
count is REPORTED here so that row lands with its measurement already taken; failing on it here
would be quietly doing M-M12's job under M1's name.

    python tools/check_mutation_anchors.py              # exit 1 on any drifted anchor
    python tools/check_mutation_anchors.py --selftest    # planted-fixture checks
"""
from __future__ import annotations

import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

from mutation_check import MUTATIONS, anchor_audit  # noqa: E402  (path set above)


def verdict(problems, anchors, units, multi, entries) -> tuple:
    """(exit_code, message) for one audit result. PURE, so the selftest can exercise EVERY branch.

    [P14 meta-review 2026-08-06] This decision used to be inline in `main()`, which left the
    gate's own decision path completely untested. Changing `if problems:` to `if False:`
    disarmed the gate - a drifted anchor could no longer fail it - while its selftest still
    printed SELFTEST OK and BOTH its mutations still reported CAUGHT, because they only ever
    exercised `anchor_audit()`. That is finding #16 of this plan ("the guard can be fully
    disarmed with all gate assertions green") reproduced inside a guard written to prevent that
    exact class. `check_readme_fresh.verdict()` already solved this the same way and for the
    same stated reason; the pattern simply was not applied here.
    """
    # The DENOMINATOR first. "anchors OK" is true of whatever happened to be iterated, so a
    # MUTATIONS list that silently shrank - or an entry shape the loop stopped unpacking - would
    # read exactly like a healthy sweep.
    if not entries or anchors <= 0:
        return 1, ("mutation-anchors: FAIL - %d mutation entr(ies) and %d anchor(s) to check. A "
                   "zero denominator makes this gate pass against any repo." % (entries, anchors))

    note = ""
    if multi:
        # NOT a failure - see the SCOPE note above. Reported so M-M12 arrives measured.
        shown = "; ".join(multi[:5]) + ("; ..." if len(multi) > 5 else "")
        note = ("\n  note: %d anchor(s) match their source more than once, and replace(..., 1) "
                "mutates the FIRST. Uniqueness is M-M12's row, not enforced here: %s"
                % (len(multi), shown))

    if problems:
        head = ("mutation-anchors: FAIL - %d of %d anchor(s) across %d mutation entr(ies) in %d "
                "file(s) no longer match their source. Each one is a mutation that cannot run, "
                "and nothing short of a full ~25-minute sweep would have said so:"
                % (len(problems), anchors, entries, len(units)))
        return 1, head + "".join("\n  " + p for p in problems) + note

    return 0, ("mutation-anchors: OK - %d anchor(s) across %d mutation entr(ies) in %d file(s) "
               "still match their source%s" % (anchors, entries, len(units), note))


def main() -> int:
    problems, anchors, units, multi = anchor_audit(REPO)
    rc, msg = verdict(problems, anchors, units, multi, len(MUTATIONS))
    print(msg)
    return rc


def selftest() -> int:
    """PLANTED fixtures. A selftest that only ran the live audit would pass on a clean repo no
    matter what the detector did - which is exactly why every mutation of such a guard survives.
    Each case below is built so that a detector which has stopped detecting FAILS."""
    fails = []

    with tempfile.TemporaryDirectory() as td:
        hooks = os.path.join(td, "hooks")
        os.makedirs(hooks)
        with open(os.path.join(hooks, "planted.py"), "w", encoding="utf-8") as f:
            f.write("def alpha():\n    return 1\n\n\ndef alpha():\n    return 2\n")

        # NEGATIVE CONTROL: an anchor that still matches must not be reported. Without this, a
        # detector that flags everything would pass every positive case below and be useless.
        matching = [("planted", "P-OK", "control", [("    return 1", "    return 9")], False)]
        problems, anchors, units, _multi = anchor_audit(td, matching)
        if problems:
            fails.append("a MATCHING anchor was reported as drifted: %r" % (problems,))
        if anchors != 1 or len(units) != 1:
            fails.append("denominator wrong on the control: %d anchor(s), %d unit(s), expected "
                         "1 and 1" % (anchors, len(units)))

        # POSITIVE: the disarmed anchor - the exact 2026-08-05 failure, planted.
        drifted = [("planted", "P-BAD", "drifted", [("def GONE():", "def x():")], False)]
        problems, _a, _u, _m = anchor_audit(td, drifted)
        if not problems:
            fails.append("a DRIFTED anchor passed. That is the whole gate: an anchor that no "
                         "longer matches is a mutation that cannot run")
        elif not any("P-BAD" in p for p in problems):
            fails.append("the drift report does not name the mutation, so nobody can fix it "
                         "without re-deriving which one it was: %r" % (problems,))

        # An entry with TWO drifted anchors must report BOTH. run() returns on the first because
        # it only needs to abort; this is the sweep, so it must not inherit that early exit.
        two_bad = [("planted", "P-TWO", "both gone",
                    [("def GONE_A():", "x"), ("def GONE_B():", "y")], False)]
        problems, _a, _u, _m = anchor_audit(td, two_bad)
        if len(problems) != 2:
            fails.append("an entry with TWO drifted anchors reported %d problem(s), expected 2 - "
                         "a sweep that stops at the first hides the rest" % (len(problems),))

        # FAIL CLOSED: a unit whose file is gone is a problem, never a skip. A mutation naming a
        # deleted file is as unrunnable as one whose anchor drifted, and "nothing to read" is the
        # single commonest way a check evaporates into a green tick.
        absent = [("no_such_unit", "P-MISSING", "unit deleted", [("anything", "x")], False)]
        problems, anchors, _u, _m = anchor_audit(td, absent)
        if not problems:
            fails.append("a mutation whose UNIT FILE does not exist passed - the gate must fail "
                         "CLOSED on an unreadable unit, not skip it")
        elif not any("cannot read" in p for p in problems):
            # Asserted on the MESSAGE, not merely on "some problem appeared". Substituting an
            # empty string for unreadable content also produces problems - every anchor then
            # "no longer matches" - so a presence-only assertion passes while the unreadable
            # branch is dead and the operator is told the wrong thing about their repo.
            fails.append("an unreadable unit was reported as a DRIFTED ANCHOR rather than as "
                         "unreadable, which sends the reader to fix an anchor that is fine: %r"
                         % (problems,))
        if anchors != 1:
            fails.append("an unreadable unit dropped its anchor from the denominator (%d), so the "
                         "total would shrink silently as units go missing" % (anchors,))

        # The uniqueness OBSERVATION (M-M12's measurement) must be reported, and must NOT fail.
        dup = [("planted", "P-DUP", "matches twice", [("def alpha():", "def beta():")], False)]
        problems, _a, _u, multi = anchor_audit(td, dup)
        if problems:
            fails.append("a doubly-matching anchor was reported as a FAILURE. Uniqueness is "
                         "M-M12's row; failing on it here would be doing that work unlabelled")
        if not multi:
            fails.append("an anchor matching twice was not reported as a multi-match, so M-M12 "
                         "would arrive with no measurement")

    # The LIVE audit is deliberately NOT asserted here, and this is the interesting decision.
    # main() runs it on every `run_selftests.py` invocation, so the live claim is checked MORE
    # often than this selftest is. Asserting it here as well would be actively harmful: a
    # mutation of THIS file necessarily drifts its own anchor, so the live audit would go red for
    # every mutation of this gate whether or not the detector still detects. The mutation would
    # report CAUGHT while proving nothing - a decorative test wearing a pass. What is asserted
    # instead is that the table is non-empty, which mutating this file cannot fake.
    if not MUTATIONS:
        fails.append("MUTATIONS is empty, so the live gate would pass against any repo")

    # EVERY BRANCH of the gate's own decision. Without these, `if problems:` -> `if False:`
    # disarms the gate completely and this selftest still prints OK - measured, not theorised.
    rc_ok, msg_ok = verdict([], 5, ["u"], [], 3)
    if rc_ok != 0 or "OK" not in msg_ok:
        fails.append("a CLEAN audit did not verdict 0/OK: %r" % ((rc_ok, msg_ok),))
    rc_bad, msg_bad = verdict(["u #X: anchor no longer matches"], 5, ["u"], [], 3)
    if rc_bad != 1:
        fails.append("a DRIFTED anchor did not fail the gate. The detector can be correct and "
                     "the gate still green if this decision is wrong - that is how a guard gets "
                     "disarmed with every test passing")
    if "#X" not in msg_bad:
        fails.append("the failure message drops the problem detail, so the operator is told "
                     "something is wrong but not what: %r" % (msg_bad,))
    rc_zero, msg_zero = verdict([], 0, [], [], 0)
    if rc_zero != 1 or "zero denominator" not in msg_zero:
        fails.append("an EMPTY mutation table did not fail: %r" % ((rc_zero, msg_zero),))
    # the multi-match note must survive on BOTH paths, or M-M12's measurement disappears exactly
    # when the gate is red and someone is actually reading the output
    if "M-M12" not in verdict([], 5, ["u"], ["u #Y matches 2x"], 3)[1]:
        fails.append("the multi-match note is dropped on the CLEAN path")
    if "M-M12" not in verdict(["p"], 5, ["u"], ["u #Y matches 2x"], 3)[1]:
        fails.append("the multi-match note is dropped on the FAIL path")

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
