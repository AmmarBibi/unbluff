# Meta-review - 2026-09-01

**Subject:** the plan decision-layer re-cut (new `## Status and order`, restated bar, item 20's
marker, item 34's denominator, new item 36) plus the deletion commit `2c72620`.
**Plan:** 36 rows (0-35) at entry, **37 rows (0-36)** at exit; 18 closed / 19 open; contiguous by
parse.
CHECK 1 run as its OWN grep (`PARK|DEFER|TODO|OPTIONAL|candidate|later`) - the completeness pass
ran a different marker list separately.

---

## CHECK 1 - parked but unscheduled

11 hits after filtering ordinary English. All resolve:

- **L170 "Retire candidates"** - my own new heading. It is a DECISION put to the owner with a
  recommendation and a trigger (*"unless the ratchet actually gets gamed again"*), not a park.
- **L820-839** - item 18's body, which necessarily contains `[TODO]`, `[TABLE]`, `[insert value]`
  and `[]` in order to describe them. The row itself records "two sessions, 18 candidates, zero
  real". Not parked - scheduled, Tier 1 position 2.
- **L564 "OPTIONAL"** - a resolved adjudication. **L634 "candidate shape"** - item 13's proposed
  fix shape.

**Zero parked-but-unscheduled items.**

---

## CHECK 2 - instance vs mechanism (the focus)

| this session's fix | form | verdict |
|---|---|---|
| deleted `check_tier_freshness.py` | STRUCTURAL - the file, its registration, its adjudication and its 3 mutations are gone | **MECHANISM** |
| item 20 given a status marker | one row hand-marked | **INSTANCE** |
| item 34's denominator 45 -> 44 | hand-corrected | **INSTANCE** |
| the `## Status and order` section itself | hand-maintained prose | **INSTANCE** |
| the audit artifacts dated SUPERSEDED | hand-written headers | INSTANCE, and correctly so - a dated record should not be automated |

**Three instance-only fixes, and they CONVERGE on one mechanism.** Item 20 had no marker; item 34's
number drifted; the Status section went stale twice within an hour. All three are the same failure:
**a fact about the plan, stated in the plan, that nothing derives.** One ~15-line check - parse the
headings, assert the Status section's counts and the open set against the parse - would have caught
all three.

It is NOT built. That is a judgment call under the owner's stop-when-it-works instruction, it is
recorded in the source-coverage artifact with an explicit trigger (**if the Status section goes
stale a third time, build the check**), and the section now embeds the one-line derive command.
Recorded, not hidden.

---

## CHECK 3 - optimization (numbers)

| | |
|---|---|
| population | **68** `.py` (source: git), down from 69 - the deletion |
| `file-size` | **EXIT=0**, no new offender, none grew |
| recorded offenders | 4, unchanged: `pre_push_gate_selftest` 1213, `fast_test_on_stop_selftest` 1026, `duplicate_registration_check` 858, `fast_test_on_stop` 851 |
| `hooks/piped_gate_guard.py` | still exactly **800** - item 27, zero headroom |
| mutation entries | **227**, down from 230 (3 removed with their subject) |
| net this session-series | **-418 lines** of code deleted |

No new duplication introduced; the session removed code rather than adding it.

---

## CHECK 4 - READ THE LEDGER, do not reconstruct it

**The gate that used to answer this was deleted, so this is a manual read of
`docs/audits/gate_runs.json` - exactly what this check has always instructed.** HEAD normalised to
UTC by hand (`%cI` carries a real offset - the TF-UTC lesson applied):

HEAD = `2026-08-31T17:33:25Z`

| tier | last local run | vs HEAD |
|---|---|---|
| `run_selftests` | 2026-09-01T18:08:39Z | at/after |
| `file_size` | 2026-09-01T18:08:14Z | at/after |
| `ship_bar` | 2026-09-01T18:08:14Z | at/after |
| `hook_provenance` | 2026-09-01T18:08:28Z (FAIL) | at/after - FAIL is correct, MACHINE_STATE |
| `integration` | 2026-08-28T09:18:41Z | **BEHIND** |
| `mutation_sweep` | 2026-08-28T09:03:55Z | **BEHIND** |
| `false_alarm_scorer` | 2026-08-20T13:46:26Z | **BEHIND - 12 days** |

**Adjudicated, and two of the three are fine:** `integration` and `mutation_sweep` are behind in
THIS WORKTREE, but **CI ran both on `a33921d` (= HEAD) and both passed** - verified job-by-job, not
inferred from the run conclusion: `mutation harness (do the tests bite?)`, `mutation harness
(windows-only mutations)` and all three `integration` jobs report success. This is precisely item
21's per-worktree-vs-global distinction, and the local ledger being behind is not the same fact as
the tier being unverified.

`false_alarm_scorer` is genuinely unverified for 12 days and cannot self-correct: it is registered
`("--selftest",)`, so the suite never reaches its enforcing `record()` call. That is item 31,
already open, and item 34 is its sibling.

---

## CHECK 5 - improvements for a better outcome

1. **The plan-parse check** (CHECK 2 above). One mechanism, three defects. Trigger written down.
2. **Merge PR #4.** It is open, mergeable and green on all 17 jobs. Merging also clears
   `hook_provenance`, which correctly reports the live clone at `Downloads\unbluff` is behind.
   Owner's call - it is the only remaining outward action.
3. **Items 27 and 32 are recommended for RETIREMENT** under the new bar. Left as a decision, not
   executed, because retiring is the owner's call and both are recorded with their reasoning.

---

## CHECK 6 - mechanism health, and ONE canonical order

- suite **EXIT=0, 44/44**; `hook-health` **EXIT=0**; `file-size` **EXIT=0**.
- `hook_provenance` fails without `--code-only`, correctly and by design.
- **The `piped_gate_guard` hook fired on me again during this very audit**, on
  `check_file_size | head`, and it was right. Third catch in this session-series. That is live
  evidence for keeping it, and it is the answer to "is the part I use working".
- **EXACTLY ONE canonical order, and as of today it is IN the plan.**
  `docs/NEXT_SESSION_PROMPT.md` is a 1168-char POINTER that has said since 2026-08-24 that
  *"The canonical order is docs/PLAN.md. Nothing else."* `docs/V131_REVIEW_PLAN.md` is a retired
  review plan. No competing list exists.
  **The finding worth recording:** that pointer has been DANGLING for eight days. `PLAN.md`
  contained no order section at all until this session - verified by grep before the re-cut. The
  file that fixed the competing-order problem pointed at a target that did not exist, and nothing
  noticed, because each file was only ever checked on its own.

---

## Order refresh (always last)

**37 rows, 0-36, contiguous. 18 closed, 19 open. Every open row appears in the tiered order exactly
once - verified mechanically twice, before and after item 36 was added.**

CLOSED: 0-7, 10, 15, 20-25, 33, and **17 REVERTED**.

OPEN, in the plan's canonical order:
- **Tier 1 (would notice in a session):** 36, 13, 18, 34, 16
- **Tier 2 (the instruments can lie):** 35, 26, 30, 29, 9
- **Tier 3 (internal rigor):** 31, 11, 12, 19, 28, 14, 8
- **Retire candidates:** 27, 32

## Verdict

CHECK 1 clean. CHECK 2 found three instance-only fixes converging on one unbuilt mechanism, with a
written trigger. CHECK 4 read the ledger by hand as instructed and adjudicated all three behind
tiers - two covered by CI at HEAD, one genuinely open and already scheduled. CHECK 6 confirms one
canonical order, now real rather than pointed-at.
