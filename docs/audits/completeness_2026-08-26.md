# Completeness audit - 2026-08-26

Target: `docs/PLAN.md` at `1443a59` plus today's edits. Run to its OWN procedure - STEP 1's grep
set is distinct from meta-review CHECK 1's.

## STEP 1 - soft-defer sweep (failure mode a)

Five hits, **zero optional-forever items**:

| line | hit | verdict |
|---|---|---|
| 163 | `deliberately excluded` (read-only git callers) | FINALIZED - reason stated; including them would put files in a population that cannot corrupt anything |
| 334 | `dropped the broken clone out of the roster` | describes a DEFECT that was found and fixed |
| 468 | `maintenance obligation is dropped` | FINALIZED retirement, reason recorded |
| 497-499 | the public-repo decision | **the previous close's fix, working.** The word `Parked` still greps because the text now QUOTES its own former state to explain why a trigger was added. Self-documenting, not a defer. |

The `plan-defer-guard` hook remains the tripwire between runs; this sweep found nothing for it.

## STEP 2 - source-coverage against the prior artifacts (failure mode b)

Swept `meta_review_2026-08-25b.md` and `source_coverage_2026-08-25b.md` against the plan, keying on
every ACTION they name. Two zeros were real gaps; the rest were already homed.

| key from the artifacts | plan hits | verdict |
|---|---|---|
| `worktree` (item 14's residue class) | 8 | homed |
| `BinOp` (item 11) | 1 | homed |
| `delegation` (item 12) | 4 | homed |
| `mid-session` (CHECK 5.1) | 2 | homed in standing check 1 |
| `heredoc` (item 13) | 3 | homed |
| `mutation_sweep` | 2 | homed, incl. the known-stale-by-design note |
| `0 of 10` (item 15's timing) | 1 | homed |
| `CONFIG_READ_ONLY_FLAGS` | 0 | **not a gap** - completed work, referenced by description in item 10 ("selftest-isolation, twice - see items 11 and 12"). Done work needs no schedule. |
| **`integration`** | **0** | **GAP -> item 17** |
| **`placeholder`** | **0** | **GAP -> item 18** |

### GAP 1 -> item 17: no gate flags a tier older than the code it covers

The plan does not mention the `integration` tier at all, so its freshness was neither scheduled nor
excluded. The previous session measured it at 2026-08-24T18:42:34Z - predating every commit of a
session that added two hook modules and two `REQUIRED_HOOKS` entries `install.py` acts on. It was
caught **only because meta-review CHECK 4 says READ the ledger, by hand, at the close.** Re-running
returned 34/34, so nothing was wrong - but that was unverified for a full session and the detection
mechanism was a person opening a JSON file.

`tools/gate_ledger.py` already stamps every run, so the data exists; nothing ASKS. Scheduled with
its trap recorded: `mutation_sweep` is permanently stale by design (CI cannot write the local
ledger), so it must be exempted with a written reason or the new gate is red forever and gets
switched off.

### GAP 2 -> item 18: the shipped extractor fires on code literals

`skills/consistency-audit/scripts/audit.py` is a REGISTERED gate (`consistency-audit-skill` in
`AUX_GATES`) - unbluff's own shipped code. Proven against the shipped copy: a file containing
`x = []` reports `[E] UNFILLED PLACEHOLDERS -> 2`, flagging the bare `[]` next to a real `[TODO]`.
Cost 11 false candidates and 0 real ones in the 2026-08-25 close.

Low materiality - it fails LOUD, as candidates a human adjudicates - but it is a guard firing on
correct work, and the previous close recorded this as "not a defect in the skill". **That
adjudication was wrong**, and this pass reverses it: unbluff ships the file and gates on it, so it
is in scope.

## STEP 3 - ledger

| item | state |
|---|---|
| 0, 1, 3, 4, 5, 6, 10 | BUILT, dated, commits recorded |
| 2 | PARTIAL - the pull; now blocks 7, 8, 9, 15 and the sweep |
| 7, 9 | SCHEDULED, blocked behind item 2 -> clean sweep |
| 8 | SCHEDULED, blocked behind 7; ratchet-proved, design recorded |
| 11, 12, 13, 14, 15, 16 | SCHEDULED, opened 2026-08-25 |
| **17, 18** | **SCHEDULED this pass - the two silent gaps above** |
| public-or-not | DECISION with a trigger |

## STEP 4 - verify

Re-grepped after the edits: zero optional-forever markers; every hit is a finalized exclusion, a
description of a fixed defect, or a decision carrying a trigger. Every action named in either prior
artifact now has a home in the numbered order. Item numbering runs 0-18 with no gaps.
