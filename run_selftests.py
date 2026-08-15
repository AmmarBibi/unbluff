#!/usr/bin/env python3
"""Run every self-testable hook's --selftest and exit nonzero if any fail.

Cross-platform (used by CI on Linux/macOS/Windows and locally).

Self-testability is DETECTED, not listed. A hardcoded roster silently drops any hook whose
author forgets to add it: `duplicate_registration_check` shipped with a full selftest and
CI printed "skip (no selftest)" while still reporting all-green (found 2026-07-29).
Detection looks for the actual dispatch (`"--selftest" in sys.argv`), not a prose mention,
so a docstring reference cannot cause a false positive. SELFTESTABLE stays as a FLOOR: a
name listed there must remain self-testable, and losing its dispatch is an error rather
than a silent skip.
"""

import datetime
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# [2026-08-14] The suite's own DURATION. It grew from ~56s to 109.1s in a day and
# silently approached the pre-push gate's 120s ceiling until that gate BLOCKED a correct
# push. Growth that is only discovered at the ceiling is growth nobody was watching, so
# it is recorded in the gate ledger beside the result.
import time as _time
_STARTED = _time.perf_counter()
sys.path.insert(0, os.path.join(HERE, "hooks"))

# ONE detector, imported - not a second copy. This file and hook_health_check.py each carried
# the SAME hardcoded roster; run_selftests was converted to detection on 2026-07-29 and the
# twin in hook_health_check was left behind, so the SessionStart line kept reporting
# "weekly selftests 10/10 OK" while four hooks went unswept. Two implementations of one rule
# is the defect, so there is now one implementation and one import.
from hook_health_check import (  # noqa: E402  (path set above)
    KNOWN_NO_SELFTEST, SKIP_RC, all_hook_files, floor_violations, has_selftest,
    selftestable_hooks,
)

# (label, path parts under the repo root, extra argv). A FLOOR: every entry MUST exist and run.
AUX_GATES = (
    # the consistency-audit skill's mechanical extractor - ships in the repo, exposes a
    # --selftest, but lives outside hooks/ so the detection glob above cannot see it
    ("consistency-audit-skill", ("skills", "consistency-audit", "scripts", "audit.py"),
     ("--selftest",)),
    # examples/settings.json is what people copy when wiring by hand; it went stale twice
    ("examples-settings-fresh", ("tools", "regen_example_settings.py"), ("--check",)),
    # [INSTALL-TAUTOLOGY] install.py - the file a user literally RUNS - was a registered gate
    # NOWHERE and exposed no --selftest at all, which is how its partial-checkout guard sat
    # tautological (glob the directory, then assert those same files exist) through every
    # review while its comment called itself DERIVED. 9 of 25 hook files were unguarded, 5 of
    # them imported by production hooks.
    ("install-guard", ("install.py",), ("--selftest",)),
    # [800-LINE RULE] Enforced by NOTHING until 2026-08-14, and the count it was tracked with
    # was wrong: the plan carried a hand-maintained list of offenders that each session added
    # to, and nobody walked the tree - tools/no_regression.py at 805 lines was over the limit
    # and in no list at all. A RATCHET, not a hard fail: red-for-weeks gets disabled.
    ("file-size", ("tools", "check_file_size.py"), ("--selftest",)),
    # [SHIP-BAR] Criterion 2's stopping rule, as a CONTROL rather than prose: no CRITICAL or
    # HIGH may be unbuilt, severities are DERIVED from the review report every run, and the
    # hand-adjudicated state ledger is RECONCILED against it - which is exactly the drift that
    # made "the remaining 8 findings" unverifiable (its list named five items marked BUILT).
    ("ship-bar", ("tools", "ship_bar_gate.py"), ("--selftest",)),
    # [SHIP-BAR enabler] The gate LEDGER's own retention rule. It recorded 1 of 5 tiers for
    # days, and the fix is not just "let other tiers write" - the cap was GLOBAL, so the
    # cheapest gate would evict the record of the 30-minute sweep as soon as both wrote.
    ("gate-ledger", ("tools", "gate_ledger.py"), ("--selftest",)),
    # [criterion 3] The false-alarm scorer is itself a CHECKING INSTRUMENT, and on 2026-08-12
    # every defect found after the adversarial pass was in an instrument rather than in the
    # product. Its --selftest is the gate. The MEASUREMENT is deliberately NOT the gate: a
    # known, recorded false alarm is a ledger row, and wiring it here would either turn the
    # suite permanently red or create pressure to delete the corpus entry that found it.
    ("false-alarm-scorer", ("tools", "score_false_alarms.py"), ("--selftest",)),
    # the README advertises a Python floor; CI only exercises files it actually runs
    ("python-floor", ("tools", "check_python_floor.py"), ()),
    # a hook can name a skill the repo does not ship (close_skills_guard shipped requiring
    # four while only three were installed); nothing connected those lists until this gate
    ("skill-deps", ("tools", "check_skill_deps.py"), ()),
    # the review-freshness gate's own scope check: it asked about 17 of 31 tracked .py files
    # and could not detect its own sabotage until P13 A1
    ("review-freshness-scope", ("tools", "check_review_freshness.py"), ("--selftest",)),
    # the README pastes a run_selftests transcript as EVIDENCE; it claimed 18 while the suite
    # ran 21. A stale paste reads exactly like a fresh one.
    ("readme-fresh", ("tools", "check_readme_fresh.py"), ()),
    # [P14 D2] Mutation entries pin what a fix ADDS. NOTHING in this repo pinned what a fix
    # TOOK AWAY. A rewrite of capped_report.py went blind to 10 of 14 cap spellings its own
    # predecessor caught while this suite printed 22/22, integration printed 30/30, and 92
    # of 94 mutations reported ALL CAUGHT. Measured at ~0.4s, so it belongs in the per-stop
    # path rather than CI-only.
    ("no-regression", ("tools", "no_regression.py"), ()),
    # [P14 A3] A stale COPY of these hooks ran every `git push` on the author's machine for
    # weeks - unbluff's own pushes included, gated by an outdated fail-open copy of unbluff's
    # own gate - while `git status` here stayed clean, because the copy lived outside the repo.
    # No gate in this repo read git's own wiring (core.hooksPath, .git/hooks), so nothing could
    # see it. This one asks provenance instead of directory-equality, so it keeps working after
    # the duplicate directory is deleted.
    ("hook-provenance", ("tools", "hook_divergence_report.py"), ("--selftest",)),
    # [P14 M1] A mutation entry finds its target by a literal string, so an unrelated fix that
    # edits that line disarms the mutation SILENTLY - it stays green everywhere except the full
    # ~25-minute sweep, which is CI-only. Measured 2026-08-05: the B3 encoding change broke
    # #20/23's anchor and every filtered run still reported clean. Sub-second, so it belongs
    # here rather than in CI, where the answer arrives a cycle late.
    ("mutation-anchors", ("tools", "check_mutation_anchors.py"), ()),
    # [P14 B1] Was exempted as "measurement, no pass/fail opinion of its own". That reasoning is
    # what let it double-count: it added NEGATIVE_CONTROLS to the negatives already inside
    # ENTRIES and printed "96 + 58 = 154 corpus entries" for a corpus of 125, doubling every
    # false-positive count it reported - in the tool the B1 ship-blocker is graded with.
    # Whether a scorer can count its own corpus IS a pass/fail question, and it is independent
    # of whatever guard is being scored.
    ("corpus-scorer", ("tools", "score_corpus.py"), ("--selftest",)),
)

# tools/*.py deliberately NOT gated here. Every name needs a reason, and the classification
# check below fails if a tool appears in neither list, or if a name here stops existing.
NOT_A_GATE = {
    "mutation_check.py",            # a gate, but minutes-long: CI runs it as its own job
    "compare_delivery_gate.py",     # measurement, produces numbers for the plan
    "measure_dispatcher_cost.py",   # measurement
    # [P14 B1] grades a cap-guard against tests/cap_spelling_corpus.py and prints the
    # denominator. Measurement, not a gate: it scores whatever guard it is pointed at, so it
    # has no pass/fail opinion of its own. Kept in the repo because the C1-NEW rebuild is
    # graded with it and a scorer that lives only in a scratchpad is a measurement nobody can
    # reproduce.
    "make_hook_screenshot.py",      # docs asset generation
}


def missing_gates(root: str, gates=AUX_GATES) -> list:
    """Labels of AUX_GATES whose file is not present under `root`.

    Pure and root-parameterised so the selftest can build a tree where gates ARE missing. The
    old code asked `if os.path.exists(...)` inline and skipped in silence, so this question had
    no answer anywhere: a renamed tool removed its gate and the suite still printed all-green.
    """
    return [label for label, parts, _extra in gates
            if not os.path.exists(os.path.join(root, *parts))]


def classify_tools(tools_dir: str, gates=AUX_GATES, not_a_gate=NOT_A_GATE) -> tuple:
    """(unclassified, stale_exempt) for the tools/ directory.

    DETECTION with a floor: a new tool must be declared a gate or explicitly exempted, and an
    exemption naming a file that no longer exists is itself reported - otherwise the exemption
    list rots into cover for whatever gets added next.
    """
    gate_basenames = {parts[-1] for _l, parts, _e in gates if parts[0] == "tools"}
    present = {os.path.basename(p) for p in glob.glob(os.path.join(glob.escape(tools_dir), "*.py"))}
    return (sorted(present - gate_basenames - set(not_a_gate)),
            sorted(set(not_a_gate) - present))


def main():
    failed = []
    skipped = []
    ran = 0
    hooks_dir = os.path.join(HERE, "hooks")

    # The floor turns "a hook with no selftest" into a RED build rather than a silent skip.
    # KNOWN_NO_SELFTEST is empty, so ADDING an untested hook is what breaks the gate.
    violations = floor_violations(hooks_dir)
    for v in violations:
        print(f"FAIL: {v}")
        failed.append(v.split(":")[1].strip().split()[0] if ":" in v else v)

    detected = selftestable_hooks(hooks_dir)
    total = len(all_hook_files(hooks_dir))
    print(f"-- sweeping {len(detected)} of {total} hook files "
          f"({len(KNOWN_NO_SELFTEST)} explicitly exempt)")
    for path in detected:
        name = os.path.splitext(os.path.basename(path))[0]
        ran += 1
        rc = subprocess.run([sys.executable, path, "--selftest"],
                            stdin=subprocess.DEVNULL).returncode
        if rc == SKIP_RC:
            # A skip is NOT a pass. Under CI it is a failure: the whole point of running on
            # four Pythons x three OSes is that the assertions actually execute there.
            label = "SKIPPED"
            if os.environ.get("CI"):
                print(f"{name}: FAIL (selftest could not run, and CI must not skip)")
                failed.append(name)
                continue
            skipped.append(name)
        else:
            label = "OK" if rc == 0 else "FAIL"
            if rc != 0:
                failed.append(name)
        print(f"{name}: {label}")
    # Auxiliary gates: real checks that are not hook selftests. Each one used to be invoked
    # under a bare `if os.path.exists(...)` with no else, so RENAMING a tool silently deleted
    # its gate - `ran` just got smaller and there was no expected count to compare it against
    # (P13 A3). A missing gate file is now a FAILURE, which is the only reading that cannot be
    # mistaken for "nothing to check".
    for label, parts, extra in AUX_GATES:
        path = os.path.join(HERE, *parts)
        ran += 1
        if not os.path.exists(path):
            print(f"{label}: FAIL (gate file missing: {'/'.join(parts)} - a gate that cannot "
                  f"be found is not a gate that passed)")
            failed.append(label)
            continue
        rc = subprocess.run([sys.executable, path, *extra],
                            stdin=subprocess.DEVNULL).returncode
        if rc == SKIP_RC:
            # Same contract as the hook selftests above: a skip is not a pass, and CI must
            # never skip - the point of running everywhere is that it actually executes.
            if os.environ.get("CI"):
                print(f"{label}: FAIL (gate could not run, and CI must not skip)")
                failed.append(label)
            else:
                print(f"{label}: SKIPPED")
                skipped.append(label)
            continue
        print(f"{label}: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append(label)

    # DETECTION, not just a list: every tools/*.py must be classified as a gate or explicitly
    # as not-a-gate. Adding a tool therefore forces the decision instead of defaulting to
    # "ungated and nobody noticed" - the same shape as KNOWN_NO_SELFTEST for the hooks.
    unclassified, stale_exempt = classify_tools(os.path.join(HERE, "tools"))
    if unclassified:
        print(f"FAIL: {len(unclassified)} file(s) in tools/ are classified neither as an "
              f"AUX_GATES entry nor in NOT_A_GATE: {unclassified}")
        failed.append("tools-classification")
    if stale_exempt:
        print(f"FAIL: NOT_A_GATE names {len(stale_exempt)} file(s) that no longer exist "
              f"(the exemption is rotting): {stale_exempt}")
        failed.append("tools-classification")

    # Informational every run, a BLOCKER only at release (--release). Printing it here is the
    # point: "CI green" and "reviewed since it last changed" are different questions, and the
    # second one had no answer at all until this ledger existed.
    fresh = os.path.join(HERE, "tools", "check_review_freshness.py")
    if os.path.exists(fresh):
        subprocess.run([sys.executable, fresh], stdin=subprocess.DEVNULL)

    record_gate_run(ran, failed, skipped, round(_time.perf_counter() - _STARTED, 1))
    if failed:
        print(f"\nFAILED ({len(failed)}/{ran}): {failed}")
        return 1
    # Always print the DENOMINATOR. "all 18 selftests passed" was true of whatever happened to
    # be listed, so a shrinking sample never looked wrong.
    note = f" ({len(skipped)} SKIPPED: {skipped})" if skipped else ""
    print(f"\nall {ran} selftests passed{note}")
    return 0


def record_gate_run(ran, failed, skipped=(), seconds=0.0):
    """Append this run to docs/audits/gate_runs.json.

    A gate that did not run leaves no trace in the code or the docs, so "were the gates
    green?" is unanswerable after the fact - you can only re-run and hope nothing changed
    in between. Reviewers then reconstruct it from memory, which is how eight eval
    batteries once went unexecuted while every review reported healthy. This makes the
    process auditable, not just the deliverable.

    Best-effort: never fails the run. An unwritable ledger must not turn a green suite red.
    """
    try:
        # [2026-08-13] Was an inline writer with the gate name HARDCODED here, which is why
        # exactly ONE of five tiers could ever be recorded. Now the shared ledger, which every
        # tier can call and which retains PER GATE - a global cap let this frequent gate evict
        # the record of the 30-minute sweep, i.e. the one whose last-run date actually matters.
        sys.path.insert(0, os.path.join(HERE, "tools"))
        import gate_ledger
        gate_ledger.record("run_selftests", "PASS" if not failed else "FAIL",
                           ran=ran, failed=sorted(failed), skipped=sorted(skipped),
                           seconds=seconds)
    except Exception:
        pass


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

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
