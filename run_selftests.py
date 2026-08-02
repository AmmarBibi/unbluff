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
)

# tools/*.py deliberately NOT gated here. Every name needs a reason, and the classification
# check below fails if a tool appears in neither list, or if a name here stops existing.
NOT_A_GATE = {
    "mutation_check.py",            # a gate, but minutes-long: CI runs it as its own job
    "compare_delivery_gate.py",     # measurement, produces numbers for the plan
    "measure_dispatcher_cost.py",   # measurement
    "hook_divergence_report.py",    # reporting
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
    present = {os.path.basename(p) for p in glob.glob(os.path.join(tools_dir, "*.py"))}
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

    record_gate_run(ran, failed, skipped)
    if failed:
        print(f"\nFAILED ({len(failed)}/{ran}): {failed}")
        return 1
    # Always print the DENOMINATOR. "all 18 selftests passed" was true of whatever happened to
    # be listed, so a shrinking sample never looked wrong.
    note = f" ({len(skipped)} SKIPPED: {skipped})" if skipped else ""
    print(f"\nall {ran} selftests passed{note}")
    return 0


def record_gate_run(ran, failed, skipped=()):
    """Append this run to docs/audits/gate_runs.json.

    A gate that did not run leaves no trace in the code or the docs, so "were the gates
    green?" is unanswerable after the fact - you can only re-run and hope nothing changed
    in between. Reviewers then reconstruct it from memory, which is how eight eval
    batteries once went unexecuted while every review reported healthy. This makes the
    process auditable, not just the deliverable.

    Best-effort: never fails the run. An unwritable ledger must not turn a green suite red.
    """
    try:
        path = os.path.join(HERE, "docs", "audits", "gate_runs.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, encoding="utf-8") as f:
                history = json.load(f)
            if not isinstance(history, list):
                history = []
        except (OSError, ValueError):
            history = []
        history.append({
            "gate": "run_selftests",
            "utc": datetime.datetime.now(datetime.timezone.utc).replace(
                microsecond=0).isoformat(),
            "ran": ran,
            "failed": sorted(failed),
            "skipped": sorted(skipped),
            "result": "PASS" if not failed else "FAIL",
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history[-200:], f, indent=2)  # bounded: keep the last 200 runs
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
