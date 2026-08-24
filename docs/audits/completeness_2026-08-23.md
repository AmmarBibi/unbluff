# Completeness audit - 2026-08-23

**Plan:** `docs/PLAN.md` at `a9b5cc6` plus this session's uncommitted close edits.
**Authoritative sources:** the 11 ordered gates, the task ledger #1-#42, the 7 standing checks.
**Question asked:** did gates 1, 2, 3, 5, 7, 8 park or defer-and-forget anything, and does every
deferred item have a real home?

## STEP 1 - soft-defer sweep (failure a)

Grepped for this skill's own marker set: `-> park`, `\bpark\b`, `on demand`, `on-demand`,
`only on real user demand`, `wait for a concrete`, `deferred opportunistic`,
`pick when value beats`, `someday`, `maybe later`, `if time`, `only when ... window`, `DROPPED`,
`excluded`.

**2 hits, both false positives**, adjudicated by reading:

| line | text | verdict |
|---|---|---|
| 61 | "it silently **dropped** the 91 SKILL.md claims" | describes a DEFECT being fixed, not a defer |
| 170 | "a name can therefore be **dropped** from the evidence block" | describes a defect, not a defer |

Zero `park` / `on demand` / `someday` / `if time`. **No optional-forever framing remains.**
`plan_defer_guard --selftest` rc 0, so the always-on tripwire between audits is itself live.

## STEP 2 - coverage of the sources (failure b - the dangerous one)

Every gate and every item this session touched, checked for a home:

| item | state | home | verdict |
|---|---|---|---|
| gate 1 merge | DONE `d89e3dc` | row 1 | covered |
| gate 2 execution model | DONE `13a8845` | row 2 | covered |
| gate 3 README claims | DONE `1aed8cc` | row 3 | covered |
| gate 5 PDF branch | DONE `2200229` | row 5 | covered |
| gate 7 notes, local half | DONE `a9b5cc6` | row 7 | covered |
| gate 7 **publish v1.3.1** | NOT DONE, needs authorisation | named in row 7 | covered |
| gate 8 install/uninstall | DONE `31ec83e` | row 8 | covered |
| gate 9 adversarial review | not started | row 9 | covered |
| gate 10 sweep + CI PR | not started | row 10 | covered |
| gate 11 tag | not started | row 11 | covered |
| #39 worktree provenance | filed | Phase 2 | covered |
| #40 readme roster | **FIXED in gate 3** | Phase 2 entry said OPEN | **STALE MARKER - corrected** |
| #41 size ratchet | filed | Phase 2 | covered |
| #42 plan/changelog cardinalities | filed | Phase 2 | covered |
| **criterion 1 (#6/#28)** | declared "survives as a post-release issue" | **NOWHERE** | **GAP - scheduled now** |

### GAP 1 - criterion 1 was declared surviving and never scheduled

Gate 3's row says *"Criterion 1 survives as a post-release issue carrying the full 243/152/91
denominator, so the route stays open and nothing is orphaned."* Phase 2's roster reads
`#3, #4, #5, #7, #8, #13's pinning, #15, #17, #18, #19, #21, #22, #24, #33, #34, #35's residue`.
**#6 and #28 are not in it.** Criterion 1 had no home for three hours.

This is the worst kind of gap because the assertion was **load-bearing**. The entire argument for
re-cutting gate 3 was: do not delete criterion 1, because `findings.json`'s `exclusion_basis`
names it as the only route back for 42 excluded findings, 10 of them HIGH. If criterion 1 exists
only in a sentence and not in the roster, those 42 are orphaned exactly as they would have been
under the plan I rejected - reached by a different route, with a better-sounding rationale.

Scheduled now, with the denominator carried so a re-auditor can recount: 243 = README 152
(70 proven / 82 unproven) + SKILL.md 91 (15 / 76), and A1's undecided question is worth precisely
the 76 unproven SKILL.md rows.

### GAP 2 - #40 carried a done-token contradiction

Gate 3 line 75 says "(#40 closed with it)". The Phase 2 entry at line 166 presents #40 as an open
finding. Both were written in the same commit. Unambiguous once checked - the gate exists,
`readme-pieces` passes - so it is corrected rather than left for adjudication, and the entry is
kept for the record of why the gate checks a roster.

## STEP 3 - ledger

No new source content was found unencoded: this plan's "sources" are its own gates and ledger,
all 11 gates and all 42 rows are accounted for above. Coverage ledger for the claim inventory is
`docs/audits/promise_inventory_2026-08-09.md`, unchanged and now referenced by a scheduled row.

## STEP 4 - verify

Re-grepped after the edits: still 2 hits, still the same two false positives, no new markers.

## Deviations

1. **STEP 2 was NOT run as a Workflow fan-out**, which the skill prescribes. The sources here are
   a 190-line plan and a 42-row ledger, not multi-hundred-page PDFs, and one reader covers them;
   a fan-out would also have needed the budget check this session has not done. Stated because
   the skill asks for one and a reader who skips a prescribed step should say so.
2. **The auditor and the author are the same agent.** GAP 1 was found - but it was found by
   running a checklist against my own work three hours later, which is the weakest form of
   independence. Gate 9 is the real check, and it has not run.
3. **Only this session's rows were swept for stale markers.** Rows 4, 6, 9, 10, 11 were read for
   their state but their bodies were not re-verified against the repo.
