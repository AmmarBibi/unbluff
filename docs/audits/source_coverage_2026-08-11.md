# Source-coverage audit - 2026-08-11 (close ritual, pass 3 of 4)

**Subjects:** `docs/NEXT_SESSION_PROMPT.md` (the plan) reconciled against its sources - the
coverage ledger and the repo state it describes.
**STEP 5 was run IN FULL.** It is the step that was skipped on 2026-08-11 (ledger N2), and it
produced findings again this time - four drifts, none of which a re-reading of the plan would
have surfaced, because a plan cannot report a number it believes.

## Findings - 4 drifts, all confirmed by measurement

### 1. The ledger carried TWO states for one item
`coverage_ledger:79` listed `FASTTEST-BLOCK` as **SCHEDULED** while `N0` recorded it **BUILT**,
in the same document. Section B is the criterion-2 index a reader consults first, so the item
most likely to be looked up was the one that was wrong. **Fixed:** section B now reads BUILT and
points at N0. Found by reconciliation, not by re-reading - re-reading is what produced the
contradiction.

### 2. The 800-line row is an instance of the defect it describes
Measured against the files:

| file | ledger said | a third doc said | **actual** |
|---|---|---|---|
| `hooks/pre_push_gate_selftest.py` | 866 | 956 | **995** |
| `tools/mutation_check.py` | 1033 | 1128 | **1154** |
| `hooks/fast_test_on_stop_selftest.py` | *unnamed* | *unnamed* | **852** |

**Three different pairs were in circulation simultaneously**, and a THIRD violating file existed
in no document at all - one this session created. The rule is now broken five times across three
files. The row's own prescription is the only durable form and it stands unchanged: **build the
line-count GATE, then split.** Patching the figures a third time would be the instance fix the
row itself warns against, so the ledger now says plainly that its numbers are a snapshot, not a
control.

### 3. The plan's step-3 queue still listed closed work
`NEXT_SESSION_PROMPT.md:132` listed `SKILLDIR-DESTROY` and `FASTTEST-BLOCK` as pending; both are
done. `:176` still instructed "Fix FASTTEST-BLOCK first". **Fixed:** the queue now carries
`FASTTEST-BLOCK` as `[DONE 08-11]` with its evidence and its stated limit, and the two new items
(`CAP-FP-1`, `SELFTEST-BUDGET-FTOS`) have homes in the order.

### 4. Stale harness figures
`:18` and `:20` quote "155 entries" and "153 of 155"; the harness now holds **162** entries with
**163** anchors. `:56` quotes `V131_REVIEW_PLAN.md` at 2,338 lines; it is **2368**. Both are the
ungated-number class already SCHEDULED for step 5's gate work - corrected here, and noted as
instances rather than treated as the fix.

## STEP 5 verification

- **Optional-forever language: none.** Re-grepped all 15 markers across both documents after the
  edits; 5 hits, all prose about *not* deferring (full adjudication in
  `completeness_2026-08-11.md`).
- **Ledger current:** every item this session surfaced maps to BUILT or SCHEDULED with a named
  home. Nothing is unhomed.

## A live demonstration, worth recording

Editing `NEXT_SESSION_PROMPT.md` during this pass **tripped `close_skills_guard`**, which
correctly refused the close because `meta-review` had not yet been invoked since the last user
message. The repo's own guard fired on its own author, mid-close-ritual, and it was right.

That is also a precise illustration of its known limit (ledger N2): it verified that the ritual
had **started**, and it could see that one of the four skills was missing - but it cannot see
whether the three that *were* invoked ran to completion. This pass ran STEP 5 in full; the guard
would have been equally satisfied had it not. The finding stands exactly as recorded, and the
obvious fix - each skill self-reporting completion - remains the same defect one level down.
