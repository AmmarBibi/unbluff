# Meta-review - 2026-08-09

Run at the v1.0 planning milestone, after the promise inventory, the plan audit and the total
gap-closure sweep. Repo HEAD `00fc9ba`.

## Check 1 - parked-but-unscheduled

**PASS.** Soft-defer sweep over `docs/NEXT_SESSION_PROMPT.md`: 2 marker hits in 114 lines, both
benign - a section header ("THEN, in later sessions", whose sessions are scheduled as real steps)
and a pointer to the EXCLUDED-state ledger. **Zero optional-forever items in the canonical plan.**

The 46 hits inside `promise_inventory_2026-08-09.md` are claim text *about* the markers, not
soft-defers - the same self-reference artefact recorded in `consistency_2026-08-09.md`.

## Check 2 - instance-only fixes (the durability check)

Two fixes made today are **instance-only** and are now scheduled:

| fix made | why it is instance-only | durable form - SCHEDULED |
|---|---|---|
| Corrected the plan audit's false numbers (78/45/120 -> 85/0/158) | The root cause was reading a derived number off a producer that was still running. Correcting the numbers does not stop it recurring. **This project ships a hook for timing claims and one for unmatched numbers, and neither covers this case.** | A gate that refuses to publish a derived figure unless its producer has exited - i.e. mechanise the repo's own rule *"a number read off a still-running producer is not a measurement"*. Step 3. |
| `[]` placeholder in the reliability headline | Fixing the string leaves the generator able to emit an empty format value again | Assert non-empty on every interpolated count in the generator, or render counts through one helper that raises on `None`/empty. Step 3. |

**A third, pre-emptive:** if `CA-SELFREF` is fixed only by tweaking the placeholder vocabulary,
that is instance-only. The general fix is a self-reference exclusion (skip fenced/quoted regions,
or a `--self-doc` mode), because the same defect will recur for `[C]` and `[F]` independently.
Recorded in the ledger as such.

## Check 3 - optimization (code / structure / perf)

**3 files over the project's 800-line rule** (numbers, not vibes):

| lines | file | disposition |
|---|---|---|
| 2338 | `docs/V131_REVIEW_PLAN.md` | **FINALIZED-EXCLUSION** - history, collapse cancelled (ledger F) |
| 965 | `tools/mutation_check.py` | **SCHEDULED** - behaviour-preserving split. It carries 138 mutation entries plus the harness; the entries are data and belong in their own module. Safety net: the harness has 2 mutations of its own |
| 805 | `tools/no_regression.py` | **SCHEDULED** - marginal, split after `mutation_check` |

No duplication, N+1 or unbounded-query classes apply to this codebase (no DB, no server).
Dead code: not measured this pass - recorded as unmeasured rather than reported as clean.

## Check 4 - missing / wrong (gate ledger READ, not reconstructed)

**FINDING - HIGH. The gate ledger records 1 of 5 gate tiers.**

`docs/audits/gate_runs.json` holds **195 entries, every one of them `run_selftests`** (19 non-PASS
historically; last run `2026-08-09T05:34:32Z`, PASS, 32/32).

| gate tier | recorded? |
|---|---|
| `run_selftests` | YES - 195 runs |
| `tools/mutation_check.py` | **NO** |
| `tests/test_integration.py` | **NO** |
| CI (`selftest.yml`) | **NO** |
| `pre_push_gate` | **NO** |

This is exactly the blindness this check exists for: *a gate that did not run leaves no trace in
the plan or the code.* For four of five tiers, "did it run, and what did it say?" is unverifiable
from the record. The v1.3.1 mutation result (136 of 138 per platform) is known only from prose in
the session prompt - **no artefact in the repo records it.**

**Action: SCHEDULED, step 3.** Every gate tier writes to `gate_runs.json`, and the ledger prints
its own tier denominator ("5 of 5 tiers reporting").

## Check 5 - improvements for a better outcome

Listed, not actioned - the owner picks:

1. **`--self-doc` mode for `consistency-audit`** (or fenced-region exclusion). Turns a
   criterion-2 defect into a feature: the tool becomes usable on documentation about itself.
2. **One helper for every interpolated count** in the audit generators, raising on empty. Kills
   the `[]` class permanently.
3. **`check_review_freshness` should print both labels**, not one. Today a unit that is STALE
   *and* has open findings reports only STALE, which is how 37 of 42 open findings stayed
   invisible. One-line fix, large visibility gain.
4. **A `gate_runs.json` tier-coverage line** at session start, next to the existing hook-health
   line - so a missing tier is visible before the work, not after.

Items 2 and 3 are low-risk / high-value and belong in step 3 with the rest of the criterion-2
queue. Items 1 and 4 are step 3 candidates behind them.

## Check 6 - mechanism health

| mechanism | state |
|---|---|
| `run_selftests` | **GREEN** - 32/32, run live this session |
| hook health | **GREEN** - 8 hook commands verified |
| notes / plan lean | `V131_REVIEW_PLAN.md` at 2338 lines, excluded as history |
| **exactly ONE canonical recommended-order list** | **FAIL - two competing orderings existed** |

**The check-6 defect, and the action taken.** `docs/NEXT_SESSION_PROMPT.md` carried Steps 1-4
while `plan_audit_2026-08-09.md` and `coverage_ledger_2026-08-09.md` referenced a 6-step forward
plan. Two orderings, drifted apart, exactly the failure mode this check names.

**Merged.** `NEXT_SESSION_PROMPT.md` is now the single canonical order; the ledger's step numbers
refer to it. Per the end-of-turn finalize rule, done items are marked and the next items are in
priority order.

## Summary

| check | result |
|---|---|
| 1 parked-but-unscheduled | PASS - 0 in the canonical plan |
| 2 instance-only fixes | **2 found, both scheduled** + 1 pre-emptive |
| 3 optimization | 2 files scheduled for split; dead code unmeasured and said so |
| 4 missing / wrong | **HIGH - gate ledger covers 1 of 5 tiers** |
| 5 improvements | 4 listed, 2 folded into step 3 |
| 6 mechanism health | **FAIL on the single-order rule - merged this pass** |
