# Completeness audit - 2026-09-01

**Plan:** `docs/PLAN.md`. **36 rows (0-35), 18 closed / 18 open at entry; 37 rows (0-36),
18 closed / 19 open at exit.** Contiguous by parse both times.
**Procedure:** STEP 1's marker grep run as its own pass (NOT meta-review's CHECK 1, run
separately). STEP 2 run against the independent review `wf_a71fb7d3-79d` and this session's gate
output. Plus a third check the re-cut made necessary: **is the new ORDER complete?**

---

## STEP 1 - soft-defer sweep

This skill's own marker list, case-insensitive: `-> park`, `park`, `on demand`, `wait for a
concrete`, `deferred opportunistic`, `pick when value beats`, `someday`, `maybe later`, `if time`,
`DROPPED`, `EXCLUDED`.

**11 hits, 0 real soft-defers.** Every one is ordinary prose: `deliberately excluded` describing a
roster exclusion with its reason; `dropped the broken clone out of the roster` describing a past
defect; `"say what you dropped"` quoting a rule; `52 findings, 52 adjudicated, 0 dropped` quoting
the review's coverage line; `the maintenance obligation is dropped` and `has been dropped`
describing decisions already taken with triggers attached.

The public/private repo question at line ~1524 remains a DECISION with a TRIGGER, not a build item
- unchanged and correct.

---

## ORDER COMPLETENESS - the check the re-cut made necessary

The session added a tiered order to a plan that had never had one. An order is only worth having
if it is total, so it was verified mechanically rather than read:

```
open rows (derived) : [8,9,11,12,13,14,16,18,19,26,27,28,29,30,31,32,34,35]  (+36 after STEP 2)
MISSING from order  : []
DUPLICATED in order : []
CITED BUT NOT OPEN  : []
```

**Every open row appears in the order exactly once. None dropped, none duplicated, no ghost
entries.** Re-verified after STEP 2 added item 36: still total, 19 of 19.

---

## STEP 2 - source-coverage sweep (the dangerous direction)

Authoritative source: the independent review `wf_a71fb7d3-79d` - 52 findings, 52 adjudicated,
**46 confirmed**. Reconciled finding-by-finding against the plan.

| disposition | count | where |
|---|---|---|
| resolved by DELETION | 29 | item 17 - the file is gone |
| recorded, deliberately unscheduled | 12 | item 33 - `gate_registry.py`, none misfires |
| **NO HOME AT ALL** | **11** | **the gap** |

The plan disposed of those 11 as *"and the handful elsewhere"*. **That is the vague
non-disposition this step exists to catch** - a phrase that reads like coverage and enumerates
nothing. Derived from the journal, the "handful" is 11 confirmed findings in files that still
exist, **3 of them HIGH**, and all three are about ONE mechanism:

- `MACHINE_STATE` can exclude every gate from the `--code-only` verdict (HIGH)
- `MACHINE_STATE`'s only consumer is pinned by a probe that re-implements the routing (HIGH)
- the `#45` disarm probe does the same - it re-implements its subject instead of exercising it (HIGH)

### Scheduled as item 36, and placed FIRST in Tier 1

**VERIFIED before scheduling, not taken on the reviewers' word.** `run_selftests.py:327` reads
`if rc != 0 and code_only and label in MACHINE_STATE: ... excluded`, and grep finds **no assertion
anywhere on `MACHINE_STATE`'s size**. It holds 1 label against 20 `AUX_GATES` rows today, so the
defect is LATENT.

It goes first under the new bar because **`.claude/pre-push.cmd` runs `--code-only`** - this is
the only open row sitting in the verdict path of the gate he actually relies on. If that roster
ever grew to cover everything, the push gate would print a clean pass while every gate failed.

The repo has already built this exact floor twice (`SHIPBAR-FLOOR`, `FS-FLOOR`) for the population
collapsing to zero; this is the same collapse from the other side - the *exclusion* set growing to
swallow the population.

The remaining 8 (2 MEDIUM/LOW in `piped_gate_guard`, 2 in `hook_divergence_trend`, 1 in
`hook_divergence_selftest`, 3 MEDIUM/LOW in `run_selftests`) are now enumerated here rather than
hidden behind "a handful". None is user-facing; they are folded into item 33's recorded-but-
unscheduled set with that disposition stated.

---

## DONE items verified against their own definitions

- **17 REVERTED** - correct. The file is deleted, and the row keeps the evidence plus the three
  findings worth carrying. Verified: `tools/check_tier_freshness.py` does not exist; suite 44/44.
- **20 DONE** - the marker was added THIS session because the row had none. A machine parse scored
  it OPEN while every session prompt called it DONE; the two disagreed for six days.
- **33 DONE** - the review ran; its output is reconciled above rather than asserted.

---

## Ledger

| item | status | home |
|---|---|---|
| 36 `MACHINE_STATE` floor | **SCHEDULED (new)** | Tier 1, position 0 |
| 11 undisposed review findings | ENUMERATED | 1 -> item 36; 10 -> item 33's recorded set |
| 29 findings in the deleted file | RESOLVED | item 17 |
| 12 in `gate_registry.py` | RECORDED, unscheduled | item 33, with the reason |
| 27, 32 | RETIRE RECOMMENDED | Status section, awaiting the owner |

**Zero optional-forever items. Zero open rows without a place in the order. 37 rows, 0-36,
contiguous.**

## Verdict

STEP 1 clean. **STEP 2 found 11 confirmed findings with no home, 3 of them HIGH and all in the
push-verdict path** - scheduled as item 36 and placed first. The order is total and was verified
mechanically twice, before and after that addition.
