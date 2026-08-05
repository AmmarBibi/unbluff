# Consistency audit - docs/V131_REVIEW_PLAN.md vs the live repo, 2026-08-06

Scope: the three commits added this session - `6807121` (M1 anchor-drift gate), `cb1b600`
(B3-P plugin layers), `7d789c3` (score_corpus double-count fix) - and every figure their plan
rows assert.

Method note: this deliverable's source of truth is EXECUTABLE, not a CSV directory, so the
mechanical half was done by re-deriving each figure from the live tools
(`check_mutation_anchors`, `settings_layers()`, `plugin_layers()`, the corpus module,
`run_selftests`' own `expected_count()`, `wc -l`) rather than by `scripts/audit.py`, which
indexes numeric literals out of source files. Tolerance: exact - every figure here is a count.

## Verified, no drift

| claim | live value |
|---|---|
| suite 28 (plan + README) | 28 (`selftestable_hooks` + `AUX_GATES`) |
| `settings_layers()` 4 -> 5 paths | 5 |
| `2 enabled plugin(s), 7 hooks.json on disk, 1 merged` | 2 / 7 / 1 |
| corpus 125 entries, 96 must_flag, 29 negative | 125 / 96 / 29 |
| naive inverse rule 67 of 96 caught, 11 of 29 false-pos | reproduced |
| line counts 792 / 278 | 792 / 278 |
| predecessor floor 31 of 96 | `no_regression` confirms |
| suite transition chain 25 -> 26 (M1) -> 27 (B3-P) -> 28 (scorer) | internally consistent; each is a correct historical transition |

## [A] DRIFT - found and fixed

**M1 row: "prints the denominator every run (99 anchors across 98 entries in 22 files)".**
Live value is 103 / 102 / 24. Written in the present tense as the gate's current denominator,
it went stale the moment the next three mutations were added - within the same session.
Hardcoding ANY value there re-drifts by construction, because the denominator grows with every
mutation. Fixed by marking it explicitly as a build-time timestamped observation and pointing
the reader at what the gate actually prints.

## [D] UNSUPPORTED CLAIM - found and fixed

**"the ~50-minute sweep it stands in for".** Two defects in one phrase:

1. *Cross-section inconsistency.* The same row calls the full sweep "25-minute" twice in its
   original text and "~50-minute" in the addition - the same quantity with two values.
2. *Uncontrolled timing claim.* The 50 came from an impression formed while waiting on
   background runs; no controlled measurement was ever taken. This repo's rule is that every
   timing claim needs an interleaved A/B against a control - and it was written **two sentences
   after** applying that rule correctly to the 0.087s figure. Applying a discipline to the
   number under scrutiny and then dropping it for an incidental one is the more instructive
   failure of the two.

Fixed by withdrawing the number rather than substituting another guess: the sweep is stated as
minutes-to-tens-of-minutes, growing with mutation count and load-sensitive, with the instruction
to measure against a control before quoting a figure.

**Not fixable:** the same uncontrolled figure is in the commit *title* of `6807121` ("caught in
0.087s not 50 minutes") and in the `7d789c3` body. Commit messages are immutable; recorded here
so the plan is not silently more accurate than the history it refers to. The 0.087s half of that
title IS controlled and stands.

## [B] [C] [E] [F] - none

No orphan figures or dangling cross-references (this deliverable has no figures/tables of the
kind those classes address). Placeholder scan (`[TODO]`, `[TBD]`, `TKTK`, `[insert`, `[XX]`,
`[TABLE]`, `FIXME`) over the whole plan: **zero hits**.

## Judgment call, recorded rather than "fixed"

The B3-P row retains its ORIGINAL wrong premise ("7 plugin hooks.json exist and 6 declare real
events") followed by an explicit **CORRECTION** block. That is deliberate and correct - the
audit trail of a premise that would have shipped a false-alarm guard is worth more than a
tidied row - but a reader skimming the first sentence alone would take the wrong figure as
current. Left as-is because the correction is unmissable and bolded; flagged so the choice is
on the record rather than accidental.

## Verdict

2 real defects found, both in prose written this session, both fixed. Every other asserted
figure reproduces exactly against the live tools.
