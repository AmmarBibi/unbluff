# Consistency audit - V131_REVIEW_PLAN.md, sections of 2026-08-06 and 2026-08-08

**Deliverable:** `docs/V131_REVIEW_PLAN.md` - the `RE-SCOPED SHIP GATE`, `THE CLASSIFICATION WAS
REVIEWED AND IS REFUTED`, `CORRECTIONS`, and the SUP-1 / GLOB-1 / SKIP-1 / DOCX-1 / BUDGET-1 /
ENC-1 rows.

**Sources of truth:** this deliverable's sources are not CSVs, they are **gate output**. Each
cited figure was re-derived by running the gate that produces it - `tools/check_mutation_anchors.py`,
`run_selftests.py`, `tests/test_integration.py`, `tools/mutation_check.py`'s table - plus
`unbluff-review-recovery/final_adjudication.json` for the review figures. STEP 1 was adapted
accordingly; STEP 2-3 (adjudication and reasoning) are below and are the point.

**Tolerance:** none. Every figure here is an exact count, so any mismatch is drift by definition.

**Denominator: 27 claims checked. 24 OK on the first pass, 3 flagged, 1 confirmed DRIFT.**

## [A] Numbers with no source match

| claim | expected | live authority | verdict |
|---|---|---|---|
| suite count 32 | 32 | `all 32 selftests passed`, rc=0 | **OK** |
| integration 30/30 | 30/30 | `==== 30/30 scenarios passed ====`, rc=0 | **OK** |
| anchors 139 / 138 entries / 30 files | 139/138/30 | gate prints exactly that | **OK** |
| review: 20 produced, 20 adjudicated, 12 confirmed, 8 refuted, 0 unadjudicated | - | `final_adjudication.json` | **OK**, and `produced == confirmed + refuted` holds |
| 12 mutation ids named in prose (SUP1, GLOB1a/b, SKIP1, DOCX1a/b, WMA1a/b, HB1a/b, CS1/2) | all registered | `tools/mutation_check.py` | **OK**, 12 of 12 |
| ENC-1 "24 of 24 printing hooks lack a reconfigure" | 24 of 24 | recomputed over `hooks/*.py` | **OK** (25 hooks total, 24 print) |
| universe restated as 44 | 44 | 41 + 3 `skills/*/scripts/*.py` | **OK** |
| GLOB-1 "13 sites" | 13 | 13 real call sites | **OK** |
| GLOB-1 "**11 files**" | 11 | **9** distinct files | **DRIFT - CORRECTED to 9** |

### The one confirmed DRIFT

`13 sites, 11 files` was wrong: the 13 call sites live in **9** files - `cap_shapes`,
`hook_health_check`, `hook_health_check_selftest`, `numbers_match_on_write`, `selftest_budget`,
`install.py`, `run_selftests.py`, `check_review_freshness`, `hook_divergence_report`. The error
was mine and mechanical: I counted the 12 *rules* in the fix script and reported a file count
near it. Corrected in the plan. The commit message for `d70f869` carries the wrong figure
permanently and is left alone - history is not rewritten to hide an error the audit caught.

## [Adjudicated NOT drift - the checker was wrong, twice]

Both are worth recording because in each case the instrument, not the deliverable, was at fault -
the pattern this repo keeps finding.

1. **"the plan's anchor triple is stale (129/128/29 vs live 139/138/30)".** REFUTED. Line 2084 is
   the CI-SHALLOW row, explicitly stamped `FIXED 2026-08-06 (59fb389)`, and 129/128/29 was
   correct **at that commit**. It is a dated historical record, not a live claim. My checker took
   the last matching triple in the file as "the current claim", which cannot distinguish a
   timestamped observation from an assertion about now - a distinction this plan elsewhere makes
   explicitly ("this figure is a timestamped observation and not a current claim"). A consistency
   checker over this document must respect that, and mine does not.
2. **"glob.escape appears 17 times, not 13".** REFUTED. 13 are call sites; the other 4 are inside
   `tools/mutation_check.py`'s anchor STRINGS, which quote code as data. The same false-positive
   shape the finding-19 twin detector already had to fix ("a detector that cannot tell a
   definition from a string is its own false alarm").

## [B]/[C]/[E]/[F] figures, references, placeholders, tables

Not applicable in the usual form - this deliverable has no figures or rendered tables. Checked
instead: no `[TODO]`/`[TBD]`/`[insert ...]` placeholder text in the audited sections (0 found),
and every commit SHA cited in the new rows (`d6e7ad2`, `d70f869`, `aa7883f`, `904219c`,
`59fb389`) resolves in `git log`.

## [D] Claim support - the reasoning pass

- **"SHIP-BLOCKING is at least 2, not 1"** is supported: two independent lenses produced it and
  both survived refutation, and the underlying defect was reproduced end-to-end through
  `stop_dispatcher`.
- **"the classification was INCOMPLETE, not mis-applied"** is supported by a specific mechanical
  fact rather than by interpretation: every run-2 verdict answered
  `moves_a_row_to_ship_blocking = false`, so no row of the 21 moved while four HIGHs outside the
  21 were confirmed. The narrative and the data agree.
- **"the triple 24 / 41 / 17 has never been simultaneously correct at any commit"** is the
  strongest claim in the new text. Its support is `git log -S` placing the string's introduction
  at an ancestor of the split commit, where the universe was 40. Verified by the review and
  re-stated here as its finding, not as an independent measurement of mine.
- **BUDGET-1's 90-96%** is a MEASURED range with a control, and is correctly written as a
  timestamped observation against a loaded box rather than as the hook's true cost. Consistent
  with the decision recorded beside it (not raising the share).

## Cross-section consistency

The four fixed HIGHs are named identically in the row table, the corrections section and each
commit message. The `41 -> 44` restatement is consistent with the `+3 skills` arithmetic used in
the ENTRY-GUARD row. No quantity carries two values across sections.

## Action taken

- Corrected `11 files` to `9 files` (2 occurrences).
- Recorded both checker false-positives above rather than only the deliverable's error, since a
  checker that cannot tell a dated record from a live claim will mis-flag this document every
  time it is run.
