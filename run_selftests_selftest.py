"""run_selftests' own selftest. Split out of run_selftests.py 2026-08-26 [item 7].

WHY. The orchestrator sat at 803 lines against an 800 limit with SIX lines of headroom, and
the baseline recorded the same instruction four times: the next growth is preceded by a SPLIT,
not by a fifth deliberate re-record. It then bit exactly as predicted - item 15 split
hook_divergence_report.py, the new sibling had to be classified in NOT_A_GATE, and there was no
room to write the line. This is that split, following install / install_selftest.

THE SEAM WAS MEASURED, not chosen by taste:
  * ZERO pinned mutation anchors fall inside selftest() - checked against both entry tables
    before cutting. A3/A3b/MODE-1/MODE-2 all anchor production lines, which stay in the parent.
  * AUX_GATES DOES NOT MOVE. tools/mutation_check.py does not import it; it `ast.literal_eval`s
    it straight out of run_selftests.py's source text, so moving that table would break the
    mutation harness without breaking any import.
  * tools/check_selftest_isolation.py asserts that run_selftests.main() calls a scrub in its
    DIRECT body. main() stays in the parent.

THE REBINDING RULE. Everything here READS the parent's module-level names; nothing rebinds one.
A moved function that assigned to a parent global would bind a copy in THIS module and the
parent would never see it. Checked before the cut (no `global` statements in the moved body)
and it must stay true.

Run it the way it has always been run - `python run_selftests.py --selftest`.
"""
from __future__ import annotations

import os
import subprocess
import sys

from run_selftests import (  # noqa: E402
    AUX_GATES,
    HERE,
    MACHINE_STATE,
    classify_tools,
    enforcing_mode_gaps,
    missing_gates,
    unrecorded_tiers,
)

def selftest() -> int:
    """[P13 A3] HERMETIC checks for the two decisions that used to have no answer at all."""
    import tempfile
    fails = []

    # 1. a gate whose file is absent must be REPORTED, never skipped. An empty tree is the
    #    strongest form of "every tool was renamed", so every label must come back.
    with tempfile.TemporaryDirectory() as empty:
        got = missing_gates(empty)
        want = [label for label, _p, _e in AUX_GATES]
        if sorted(got) != sorted(want):
            fails.append("missing_gates() on an empty tree reported %r, expected all %d gate "
                         "labels %r - a gate file that is gone must not read as a pass"
                         % (got, len(want), want))
    # ...and the real tree must have none missing, or the suite is lying right now.
    live_missing = missing_gates(HERE)
    if live_missing:
        fails.append("AUX_GATES names %d gate(s) that do not exist in this repo: %r"
                     % (len(live_missing), live_missing))

    # 2. a tools/ file that is neither a gate nor exempt must be reported, and an exemption
    #    naming a vanished file must be reported too.
    with tempfile.TemporaryDirectory() as td:
        tools = os.path.join(td, "tools")
        os.makedirs(tools)
        for name in ("check_python_floor.py", "brand_new_tool.py"):
            with open(os.path.join(tools, name), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
        unclassified, stale = classify_tools(tools, not_a_gate={"deleted_tool.py"})
        if unclassified != ["brand_new_tool.py"]:
            fails.append("classify_tools() did not flag an undeclared tool: %r" % (unclassified,))
        if stale != ["deleted_tool.py"]:
            fails.append("classify_tools() did not flag an exemption for a file that no longer "
                         "exists: %r" % (stale,))

    # 3. [MODE-CONTROL] the argv check itself. Asserted on a SYNTHETIC tree, so the assertion
    #    states what the rule is rather than restating whatever the live table happens to say -
    #    a golden that round-trips the current registration would pin nothing.
    with tempfile.TemporaryDirectory() as td:
        enforcing = os.path.join(td, "enforcing_gate.py")
        with open(enforcing, "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0\n\n\ndef main():\n    if 1:\n"
                    "        return 1\n    return 0\n")
        printer = os.path.join(td, "printer.py")           # gate_ledger's shape: no main() at all
        with open(printer, "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0\n")
        harmless = os.path.join(td, "harmless.py")         # a main() that cannot fail
        with open(harmless, "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0\n\n\ndef main():\n    return 0\n")

        rows = (("enforcing", ("enforcing_gate.py",), ("--selftest",)),
                ("printer", ("printer.py",), ("--selftest",)),
                ("harmless", ("harmless.py",), ("--selftest",)))
        gaps, stale_adj = enforcing_mode_gaps(td, gates=rows, adjudicated={})
        if gaps != ["enforcing"]:
            fails.append("enforcing_mode_gaps() flagged %r, expected exactly ['enforcing'] - a "
                         "gate registered --selftest whose main() CAN fail is the 2026-08-14 "
                         "defect, and a printer or a can't-fail main is not" % (gaps,))
        if stale_adj:
            fails.append("enforcing_mode_gaps() invented a stale adjudication: %r" % (stale_adj,))

        # an adjudication silences it, and an adjudication for a row that does not need one is
        # itself reported - the exemption must not be able to rot
        gaps2, stale2 = enforcing_mode_gaps(td, gates=rows,
                                            adjudicated={"enforcing": "reason", "ghost": "gone"})
        if gaps2 != []:
            fails.append("an explicit adjudication did not silence the gap: %r" % (gaps2,))
        if stale2 != ["ghost"]:
            fails.append("a stale adjudication was not reported: %r" % (stale2,))

        # [ROSTER-GLOB 2026-08-19] THE SELFTEST-SHAPED-BUT-NOT-EQUAL ROW. Every fixture above
        # uses exactly ("--selftest",), so a detector written with `!= ("--selftest",)` and one
        # written with `"--selftest" in extra` agree on all of them - the cases could not tell the
        # two spellings apart, which is why the disarm survived until an independent review. The
        # target dispatches on MEMBERSHIP (`"--selftest" in sys.argv`), so this row runs the
        # selftest and must be adjudicated exactly like the plain one.
        for shape in (("--selftest", ""), ("--selftest", "-v"), ("-v", "--selftest")):
            padded = (("enforcing", ("enforcing_gate.py",), shape),)
            if enforcing_mode_gaps(td, gates=padded, adjudicated={})[0] != ["enforcing"]:
                fails.append("a registration of %r was not treated as running the SELFTEST. The "
                             "target dispatches on membership, so this row runs its selftest "
                             "while the gate's real measurement is invoked by nothing - a "
                             "one-token disarm of this very control" % (shape,))

        # THE MUTATION THIS EXISTS TO CATCH: flipping an ENFORCING row to --selftest must be
        # detected. This is the one-token edit that reproduced on a clean clone.
        flipped = (("enforcing", ("enforcing_gate.py",), ()),)
        if enforcing_mode_gaps(td, gates=flipped, adjudicated={})[0]:
            fails.append("an enforcing registration was reported as a gap - false positive")
        flipped_back = (("enforcing", ("enforcing_gate.py",), ("--selftest",)),)
        if enforcing_mode_gaps(td, gates=flipped_back, adjudicated={})[0] != ["enforcing"]:
            fails.append("flipping () -> ('--selftest',) went UNDETECTED, which is exactly the "
                         "one-token disarm this control exists to stop")

    # 4. [RECORD-SITES] the rule on a synthetic tree, then the live one. A tier whose recording
    #    is deleted keeps passing every other check in this repo, so this assertion is the only
    #    thing standing between "the ship bar reads a fresh row" and "it reads a stale one".
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "good.py")
        with open(good, "w", encoding="utf-8") as f:
            f.write('gate_ledger.record("mine", "PASS")\n')
        silent = os.path.join(td, "silent.py")
        with open(silent, "w", encoding="utf-8") as f:
            f.write('print("I am a tier that forgot to record")\n')
        wrong = os.path.join(td, "wrong.py")
        with open(wrong, "w", encoding="utf-8") as f:
            f.write('gate_ledger.record("somebody_elses_name", "PASS")\n')
        got = unrecorded_tiers(td, tiers={"good.py": "mine", "silent.py": "mine",
                                          "wrong.py": "mine", "absent.py": "mine"})
        flagged = sorted(g.split(" ")[0] for g in got)
        if flagged != ["absent.py", "silent.py", "wrong.py"]:
            fails.append("unrecorded_tiers() flagged %r; a tier that records under ANOTHER "
                         "gate's name, one that records nothing, and one that cannot be read "
                         "must all be reported, and a correct one must not" % (flagged,))

    live_unrecorded = unrecorded_tiers(HERE)
    if live_unrecorded:
        fails.append("%d declared tier(s) no longer record to the gate ledger: %r"
                     % (len(live_unrecorded), live_unrecorded))

    # [#45] --code-only must be an EXCLUSION with a written reason, never a way to go green.
    # Three properties, and the last two are the ones that would make it a disarm switch.
    labels = {label for label, _p, _e in AUX_GATES}
    orphans = sorted(set(MACHINE_STATE) - labels)
    if orphans:
        fails.append("MACHINE_STATE names %r, which is not in AUX_GATES. A roster that drifts "
                     "from the gates it classifies silently excludes nothing, or worse, "
                     "excludes a gate that has been renamed out from under it" % (orphans,))
    for lab, why in MACHINE_STATE.items():
        if len(why.strip()) < 40:
            fails.append("MACHINE_STATE[%r] has no real reason written. An exclusion without a "
                         "stated reason is indistinguishable from a bypass" % lab)
    # The disarm probe: a CODE gate that fails must STILL fail under --code-only. Run for real
    # in a scratch tree rather than reasoned about - a probe not shown to fail is not a probe.
    with tempfile.TemporaryDirectory() as td:
        red = os.path.join(td, "red_gate.py")
        with open(red, "w", encoding="utf-8") as f:
            f.write("import sys\nprint('deliberately red')\nsys.exit(1)\n")
        probe = [(lab, rc) for lab, rc in
                 (("hook-provenance", 1), ("some-code-gate", 1))]
        sim_failed, sim_excluded = [], []
        for lab, rc in probe:
            if rc != 0 and lab in MACHINE_STATE:
                sim_excluded.append(lab)
            elif rc != 0:
                sim_failed.append(lab)
        if sim_failed != ["some-code-gate"] or sim_excluded != ["hook-provenance"]:
            fails.append("--code-only routing is wrong: failed=%r excluded=%r. A CODE gate must "
                         "still fail and only a MACHINE_STATE gate may be excluded"
                         % (sim_failed, sim_excluded))
        r = subprocess.run([sys.executable, red], capture_output=True, stdin=subprocess.DEVNULL)
        if r.returncode == 0:
            fails.append("the red-gate fixture exited 0; the disarm probe proves nothing")

    # ...and the live table must be clean right now, or the suite is lying about itself.
    live_gaps, live_stale = enforcing_mode_gaps(HERE)
    if live_gaps:
        fails.append("live AUX_GATES has %d unadjudicated --selftest registration(s): %r"
                     % (len(live_gaps), live_gaps))
    if live_stale:
        fails.append("live SELFTEST_IS_THE_GATE has %d stale adjudication(s): %r"
                     % (len(live_stale), live_stale))

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1
