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


def dirty_units(unit_list: list) -> set:
    """Units with UNCOMMITTED changes in the working tree.

    last_change() reads commit history only, but --record stamps now() against the WORKING
    TREE the reviewer just read, and run_selftests invokes this on every gate run - i.e. mid
    development, with a dirty tree. Without this, appending `def backdoor(): return 42` to a
    reviewed hook leaves the gate printing "all units have an adversarial review newer than
    their last change" and exiting 0. Not solved by swapping in mtimes: the prescribed
    review -> record -> commit order would then flip every just-reviewed unit to STALE.
    """
    try:
        r = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "-z", "--"] + unit_list,
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="surrogateescape")
    except (OSError, ValueError, subprocess.SubprocessError):
        return set()
    if r.returncode != 0:
        return set()
    out = set()
    fields = (r.stdout or "").split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            i += 1
        out.add(path.replace("\\", "/"))
    return out


def evaluate() -> tuple[list, list, list, list]:
    """(stale, unreviewed, unknown, fresh) - each a list of (unit, detail) tuples.

    `unknown` is its own bucket because an unanswerable freshness question is not a passing
    one. Folding it into `fresh` made the release gate exit 0 having asked git nothing -
    reproduced with `git archive HEAD` into a scratch dir (the sdist / exported-release-tree
    case), where all 8 correctly-STALE units flipped to FRESH. That is the very contract this
    same fix round wrote into pre_push_gate.newest_source_mtime, broken in the tool built to
    enforce the lesson.
    """
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

    all_units = units()
    dirty = dirty_units(all_units)
    stale, unreviewed, unknown, fresh = [], [], [], []
    for unit in all_units:
        if unit not in newest:
            unreviewed.append((unit, "never adversarially reviewed"))
            continue
        reviewed_at, entry = newest[unit]
        raw = last_change(unit)
        changed = _parse(raw or "")
        if raw is None:
            unknown.append((unit, "git could not answer when this last changed "
                                  "(not a checkout, or git unavailable)"))
        elif changed is None:
            unknown.append((unit, f"git returned an unparseable date: {raw!r}"))
        elif unit in dirty:
            stale.append((unit, f"UNCOMMITTED changes in the working tree since the "
                                f"{reviewed_at.date()} review (run {entry.get('run_id', '?')})"))
        elif changed > reviewed_at:
            stale.append((unit, f"changed {changed.date()} but last reviewed "
                                f"{reviewed_at.date()} (run {entry.get('run_id', '?')})"))
        else:
            fresh.append((unit, f"reviewed {reviewed_at.date()}, unchanged since"))
    return stale, unreviewed, unknown, fresh


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

    stale, unreviewed, unknown, fresh = evaluate()
    total = len(stale) + len(unreviewed) + len(unknown) + len(fresh)
    # Always print the DENOMINATOR: "0 stale" is meaningless without knowing how many were asked.
    print(f"[review-freshness] {len(fresh)}/{total} units reviewed since their last change")
    for unit, why in stale:
        print(f"  STALE:      {unit} - {why}")
    for unit, why in unreviewed:
        print(f"  UNREVIEWED: {unit} - {why}")
    for unit, why in unknown:
        print(f"  UNKNOWN:    {unit} - {why}")
    if not stale and not unreviewed and not unknown:
        print("  all units have an adversarial review newer than their last change")
    if args.release and (stale or unreviewed or unknown):
        print(f"\nRELEASE BLOCKED: {len(stale)} stale, {len(unreviewed)} unreviewed, "
              f"{len(unknown)} unknown.")
        print("An unanswerable freshness question is not a passing one.")
        print("Run the adversarial-review skill over them, then record it with --record.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
