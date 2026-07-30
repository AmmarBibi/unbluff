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
    # Also gate the consistency-audit skill's mechanical extractor: its scripts ship in the
    # repo and expose a --selftest, but they live outside hooks/ so the glob above misses them.
    skill_audit = os.path.join(HERE, "skills", "consistency-audit", "scripts", "audit.py")
    if os.path.exists(skill_audit):
        ran += 1
        rc = subprocess.run([sys.executable, skill_audit, "--selftest"],
                            stdin=subprocess.DEVNULL).returncode
        print(f"consistency-audit-skill: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append("consistency-audit-skill")
    # examples/settings.json is what people copy when wiring by hand; it went stale twice.
    # Derive-and-compare so a drift is a red build, not a silent copy-paste that omits hooks.
    regen = os.path.join(HERE, "tools", "regen_example_settings.py")
    if os.path.exists(regen):
        ran += 1
        rc = subprocess.run([sys.executable, regen, "--check"],
                            stdin=subprocess.DEVNULL).returncode
        print(f"examples-settings-fresh: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append("examples-settings-fresh")

    # The README advertises a Python floor; CI only exercises files it actually runs.
    # Parse every file at the floor so a tools/ script cannot silently break the promise.
    floor = os.path.join(HERE, "tools", "check_python_floor.py")
    if os.path.exists(floor):
        ran += 1
        rc = subprocess.run([sys.executable, floor], stdin=subprocess.DEVNULL).returncode
        print(f"python-floor: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append("python-floor")

    # A hook can name a skill the repo does not ship (close_skills_guard shipped requiring
    # four while only three were installed). Nothing connected those lists until this gate.
    deps = os.path.join(HERE, "tools", "check_skill_deps.py")
    if os.path.exists(deps):
        ran += 1
        rc = subprocess.run([sys.executable, deps], stdin=subprocess.DEVNULL).returncode
        print(f"skill-deps: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append("skill-deps")

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


if __name__ == "__main__":
    raise SystemExit(main())
