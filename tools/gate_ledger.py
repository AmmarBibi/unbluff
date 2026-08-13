#!/usr/bin/env python3
"""The gate ledger: which gates actually RAN, and when. Shared by every tier.

WHY THIS EXISTS AS A MODULE. A gate that did not run leaves no trace in the code or the docs,
so "were the gates green?" is unanswerable after the fact - you can only re-run and hope
nothing changed in between. Reviewers then reconstruct it from memory, which is how eight
eval batteries once went unexecuted while every review reported healthy.

WHY IT WAS NOT ENOUGH. The writer lived inside `run_selftests.py` as a private function with
the gate name HARDCODED, so exactly one of five tiers could record anything. Measured
2026-08-13: 200 entries, `{'run_selftests': 200}`, while that same day ran the mutation
harness five times, the integration suite four times, the anchors gate four times and a new
criterion-3 scorer - none of which left a trace. The 1-of-5 finding had been recorded as
abstract record-keeping for days; it is the ENABLER for the ship bar's verify-before-pushing
half, which cannot exist until more than one tier is recorded.

THE CAP IS PER GATE, AND THAT IS THE LOAD-BEARING PART. The original kept `history[-200:]`
GLOBALLY. Extending that to five tiers would not have worked: `run_selftests` runs many times
an hour and the 30-minute mutation sweep runs once or twice a day, so a global cap lets the
CHEAPEST gate evict the record of the most EXPENSIVE one - and the expensive, rarely-run gate
is precisely the one whose last-run date you need. Per-gate retention makes the rare tier's
record survive exactly as long as the frequent one's.
"""

import datetime
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "docs", "audits", "gate_runs.json")

# Per GATE, not overall. See the module docstring - a global cap silently deletes the tier you
# most need, and does it faster the more tiers you add.
#
# 200 rather than a smaller bound, and the reason is a mistake made here on 2026-08-13: the
# first version used 60, and the very first run PERMANENTLY DISCARDED 140 of this file's 200
# historical `run_selftests` rows. The file is GITIGNORED (.gitignore:23), so there was no
# restore. Matching the previous global bound per-gate means a migration can only ever ADD
# history, never remove it.
KEEP_PER_GATE = 200

# WHAT THIS LEDGER IS NOT. It is gitignored, so it never reaches CI, does not survive a clone,
# and no reviewer can read it. It records what THIS MACHINE ran. A ship-bar gate built on it
# therefore enforces LOCAL discipline - "the sweep has been run since the last source change
# on this box" - which is exactly what verify-before-pushing needs, and is NOT a shared or
# auditable record. Anything claiming the latter needs a different artifact.


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            history = json.load(f)
        return history if isinstance(history, list) else []
    except (OSError, ValueError):
        return []


def prune(history, keep=KEEP_PER_GATE):
    """Keep the last `keep` runs OF EACH GATE, preserving overall order.

    Pure, so the retention rule can be asserted without writing a file - the previous version
    was an inline slice inside a try/except that no test could reach.
    """
    counts = {}
    keep_idx = set()
    for i in range(len(history) - 1, -1, -1):
        gate = (history[i] or {}).get("gate", "?")
        counts[gate] = counts.get(gate, 0) + 1
        if counts[gate] <= keep:
            keep_idx.add(i)
    return [row for i, row in enumerate(history) if i in keep_idx]


def record(gate: str, result: str, **fields) -> None:
    """Append one gate run. BEST-EFFORT: an unwritable ledger must never fail the gate."""
    try:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        history = _load(LEDGER)
        row = {"gate": gate,
               "utc": datetime.datetime.now(datetime.timezone.utc).replace(
                   microsecond=0).isoformat(),
               "result": result}
        row.update(fields)
        history.append(row)
        with open(LEDGER, "w", encoding="utf-8") as f:
            json.dump(prune(history), f, indent=2)
    except Exception:                              # noqa: BLE001 - never fail the caller
        pass


def last_run(gate: str, path: str = LEDGER):
    """The most recent recorded run of `gate`, or None. The reader a ship-bar gate needs."""
    rows = [r for r in _load(path) if (r or {}).get("gate") == gate]
    return rows[-1] if rows else None


def tiers(path: str = LEDGER) -> dict:
    """{gate: count} - the coverage question, answerable without reconstructing it."""
    out = {}
    for r in _load(path):
        g = (r or {}).get("gate", "?")
        out[g] = out.get(g, 0) + 1
    return out


def selftest() -> int:
    fails = []

    # The retention rule, asserted directly. A frequent gate must NOT evict a rare one.
    hist = ([{"gate": "run_selftests", "utc": "t%d" % i} for i in range(500)]
            + [{"gate": "mutation_harness", "utc": "rare"}])
    kept = prune(hist, keep=60)
    rare = [r for r in kept if r["gate"] == "mutation_harness"]
    frequent = [r for r in kept if r["gate"] == "run_selftests"]
    if not rare:
        fails.append("a 500-run frequent gate EVICTED the only run of a rare one - which is "
                     "exactly what the global cap did, and why this is per-gate")
    if len(frequent) != 60:
        fails.append("per-gate retention kept %d of a 500-run gate, expected 60"
                     % len(frequent))
    # order must survive, or "the last run" stops meaning the last run
    if kept != sorted(kept, key=lambda r: hist.index(r)):
        fails.append("prune() reordered history; last_run() would return the wrong row")

    # last_run must read back what record() writes, keyed by gate
    import tempfile
    with tempfile.TemporaryDirectory(prefix="unbluff-gl-") as td:
        p = os.path.join(td, "g.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump([{"gate": "a", "utc": "1", "result": "PASS"},
                       {"gate": "b", "utc": "2", "result": "FAIL"},
                       {"gate": "a", "utc": "3", "result": "PASS"}], f)
        if (last_run("a", p) or {}).get("utc") != "3":
            fails.append("last_run returned the wrong row for a repeated gate")
        if last_run("zzz", p) is not None:
            fails.append("last_run invented a row for a gate that never ran")
        if tiers(p) != {"a": 2, "b": 1}:
            fails.append("tiers() miscounted: %r" % (tiers(p),))

    print("-- gate-ledger: keep %d per gate; tiers recorded live: %r"
          % (KEEP_PER_GATE, tiers()))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else print(json.dumps(tiers(), indent=2)) or 0)
