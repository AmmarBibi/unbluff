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
# Floor, not roster: these must always be self-testable. New hooks are picked up by detection.
SELFTESTABLE = {
    "rate_prompt", "fast_test_on_stop", "show_your_proof", "meta_audit_on_stop",
    "memory_hygiene_guard", "stop_dispatcher", "hook_health_check", "plan_defer_guard",
    "post_tooluse_dispatcher", "numbers_match_on_write",
}
# Matches the dispatch in ANY of the forms used here:
#   "--selftest" in sys.argv        (most hooks)
#   "--selftest" in argv            (pre_push_gate, which takes argv as a parameter)
# Requires a real membership test, not a prose mention, so a docstring cannot false-positive.
# Widened 2026-07-29: the sys.argv-only form silently skipped pre_push_gate, which has a full
# selftest - the same under-reach this detector exists to prevent.
_DISPATCH_RE = re.compile(r"""["']--selftest["']\s+in\s+(?:sys\.)?argv\b""")


def has_selftest(path):
    """True iff the file actually dispatches on --selftest (not merely mentions it)."""
    try:
        return bool(_DISPATCH_RE.search(open(path, encoding="utf-8", errors="replace").read()))
    except OSError:
        return False


def main():
    failed = []
    ran = 0
    for path in sorted(glob.glob(os.path.join(HERE, "hooks", "*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        detected = has_selftest(path)
        if name in SELFTESTABLE and not detected:
            print(f"{name}: FAIL (listed in SELFTESTABLE but no --selftest dispatch found)")
            failed.append(name)
            continue
        if not detected:
            print(f"skip {name} (no selftest)")
            continue
        ran += 1
        rc = subprocess.run([sys.executable, path, "--selftest"],
                            stdin=subprocess.DEVNULL).returncode
        print(f"{name}: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append(name)
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

    record_gate_run(ran, failed)
    if failed:
        print(f"\nFAILED ({len(failed)}/{ran}): {failed}")
        return 1
    print(f"\nall {ran} selftests passed")
    return 0


def record_gate_run(ran, failed):
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
            "result": "PASS" if not failed else "FAIL",
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history[-200:], f, indent=2)  # bounded: keep the last 200 runs
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
