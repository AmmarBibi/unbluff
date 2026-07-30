#!/usr/bin/env python3
"""Release gate: has every unit been adversarially reviewed SINCE it last changed?

v1.3.0 shipped CI-green and was declared closeable twice; an adversarial review then found 34
confirmed defects in it. The lesson - "CI green means the tests pass, not that they ask the
right questions" - lived only as a sentence in a handoff doc. A sentence is an instance fix.
This is the mechanism: `docs/audits/review_runs.json` records each review the way
`gate_runs.json` records selftest runs, and this reads it back.

DETECTION, not a roster: the unit list comes from the repo (hooks/*.py plus the top-level
entry points), never from the ledger. A ledger-driven list would silently stop asking about
any file nobody remembered to add - the exact failure that put two hardcoded rosters in this
release. A unit absent from the ledger is UNREVIEWED and reported, not skipped.

    python tools/check_review_freshness.py            # report; exit 0 unless --release
    python tools/check_review_freshness.py --release  # exit 1 if anything is stale/unreviewed
    python tools/check_review_freshness.py --record --unit hooks/x.py --run-id wf_... \\
        --lenses a,b --confirmed 3
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "docs", "audits", "review_runs.json")


def units() -> list:
    """Every unit a review is expected to cover, derived from the repo."""
    found = sorted(glob.glob(os.path.join(REPO, "hooks", "*.py")))
    for extra in ("install.py", "run_selftests.py"):
        p = os.path.join(REPO, extra)
        if os.path.exists(p):
            found.append(p)
    return [os.path.relpath(p, REPO).replace("\\", "/") for p in found]


def load_ledger() -> list:
    try:
        with open(LEDGER, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def last_change(unit: str) -> str | None:
    """ISO date of the newest commit touching this unit, or None if git cannot say."""
    try:
        r = subprocess.run(["git", "-C", REPO, "log", "-1", "--format=%cI", "--", unit],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return (r.stdout or "").strip() or None


def _parse(ts: str):
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def evaluate() -> tuple[list, list, list]:
    """(stale, unreviewed, fresh) - each a list of (unit, detail) tuples."""
    ledger = load_ledger()
    newest: dict = {}
    for entry in ledger:
        if not isinstance(entry, dict):
            continue
        unit, when = entry.get("unit"), _parse(entry.get("utc"))
        if not unit or when is None:
            continue
        if unit not in newest or when > newest[unit][0]:
            newest[unit] = (when, entry)

    stale, unreviewed, fresh = [], [], []
    for unit in units():
        if unit not in newest:
            unreviewed.append((unit, "never adversarially reviewed"))
            continue
        reviewed_at, entry = newest[unit]
        changed = _parse(last_change(unit) or "")
        if changed is None:
            fresh.append((unit, f"reviewed {reviewed_at.date()} (change date unknown)"))
        elif changed > reviewed_at:
            stale.append((unit, f"changed {changed.date()} but last reviewed "
                                f"{reviewed_at.date()} (run {entry.get('run_id', '?')})"))
        else:
            fresh.append((unit, f"reviewed {reviewed_at.date()}, unchanged since"))
    return stale, unreviewed, fresh


def record(args) -> int:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    history = load_ledger()
    stamp = args.utc or datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()
    for unit in [u.strip().replace("\\", "/") for u in args.unit.split(",") if u.strip()]:
        history.append({
            "unit": unit,
            "run_id": args.run_id,
            "lenses": [x.strip() for x in (args.lenses or "").split(",") if x.strip()],
            "agents": args.agents,
            "findings": args.findings,
            "confirmed": args.confirmed,
            "utc": stamp,
        })
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(history[-500:], f, indent=2)
        f.write("\n")
    print(f"recorded {args.run_id} for {args.unit} at {stamp}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--release", action="store_true",
                    help="exit 1 when any unit is stale or unreviewed")
    ap.add_argument("--record", action="store_true", help="append a review run to the ledger")
    ap.add_argument("--unit", default="", help="comma-separated repo-relative paths")
    ap.add_argument("--run-id", default="", help="the Workflow run id")
    ap.add_argument("--lenses", default="")
    ap.add_argument("--agents", type=int, default=0)
    ap.add_argument("--findings", type=int, default=0)
    ap.add_argument("--confirmed", type=int, default=0)
    ap.add_argument("--utc", default="", help="override the timestamp (tests)")
    args = ap.parse_args()

    if args.record:
        if not args.unit or not args.run_id:
            sys.exit("ERROR: --record needs --unit and --run-id")
        return record(args)

    stale, unreviewed, fresh = evaluate()
    total = len(stale) + len(unreviewed) + len(fresh)
    # Always print the DENOMINATOR: "0 stale" is meaningless without knowing how many were asked.
    print(f"[review-freshness] {len(fresh)}/{total} units reviewed since their last change")
    for unit, why in stale:
        print(f"  STALE:      {unit} - {why}")
    for unit, why in unreviewed:
        print(f"  UNREVIEWED: {unit} - {why}")
    if not stale and not unreviewed:
        print("  all units have an adversarial review newer than their last change")
    if args.release and (stale or unreviewed):
        print(f"\nRELEASE BLOCKED: {len(stale)} stale, {len(unreviewed)} unreviewed.")
        print("Run the adversarial-review skill over them, then record it with --record.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
