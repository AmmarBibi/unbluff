# Consistency audit - B1 (C1-NEW), 2026-08-06

Second consistency pass of 2026-08-06. The first
(`consistency_2026-08-06.md`) covered `6807121` / `cb1b600` / `7d789c3` and is disjoint from
this one, which covers `f77eefd` (the C1-NEW detector) and `b257d77` (its plan rows). Written
as a separate file rather than appended, so neither session's artifact overwrites the other.

**Deliverable:** `docs/V131_REVIEW_PLAN.md` at `b257d77`.
**Sources:** the LIVE repo. 19 metrics re-derived by importing the modules and re-running the
gates, because for this deliverable the source of truth is gate output, not a results file.
The skill's `scripts/audit.py` was also run in full against a generated source index.
**Tolerance:** exact - every figure is an integer count, except one timing with a stated spread.

## Verified against live measurement - 19 of 19 match

| claim in the plan | live value |
|---|---|
| mutation entries 115 | 115 |
| anchors 116 across 27 files | 116 / 27 |
| corpus 132 = 103 must-flag + 29 controls | 132 / 103 / 29 |
| 3 contradictory corpus pairs | 3 |
| ceiling 100 caught at zero FP, 3 min FP at full | 100 / 3 |
| `no_regression` unit population 29 | 29 |
| `cap_shapes` / `cap_types` / `capped_report` all under 800 | 694 / 489 / 158 |
| live `hooks/` offenders 0 | 0 |
| live `tools/` offenders 4 | 4 |
| live + fixture exemptions 2 + 2 | 2 / 2 |

Work-order table re-summed by parsing its own 12 rows: **11 HIGH / 44 total**, matching the
plan's assertion. Ship gate unchanged.

## [A] DRIFT - found and FIXED

**1. The selftest timing was wrong by 20%, and it was my own claim from this session.**
Committed as "1.08s of its 12.50s budget" from a SINGLE unreplicated reading. Re-measured
INTERLEAVED against a control, 5 rounds each:

- subject `capped_report --selftest`: **median 1.291s**, spread 1.275-1.355
- control `check_readme_fresh`: **median 0.091s** against the 0.099s M1 characterised = **0.92x**

The control running slightly FASTER than its historical figure is what proves the box was not
loaded, so 1.291s is the real number and 1.08s under-reported. Corrected in the B1 row, with
the spread, the control and the ratio. The conclusion does not change - 9.7x headroom inside
the budget - but this repo's rule is that a timing claim without a control is not evidence.
A8 exists because four timing conclusions were reversed by a control; the previous
consistency audit found a fifth (the "~50-minute sweep"). **This is the sixth, written by the
same agent that had just recorded the fifth.** The failure is not ignorance of the rule.

**2. The design sections' corpus arithmetic went stale the moment the corpus was widened.**
"125 entries", "96 must_flag", "31 of 96", "only the 14 scalar-suffix entries are
baseline-verified" all read in the present tense and are now false (132 / 103 / 38 of 103 /
**21** baseline-verified). STAMPED at the head of the design section with current figures
rather than rewritten, per this plan's own convention.

## [D] UNSUPPORTED CLAIM - found and FIXED

**The design brief's binding constraint was read off the wrong baseline.** "beat the FALSE
POSITIVES, CAUGHT 67/96, FALSE-POS 11/29" describes the **naive inverse rule** - a
hypothetical scored in order to design against it, never the shipped guard. The shipped
predecessor's own record is **31 of 96 with ONE false positive** (`neg_scalar_slice_rostered`),
re-measured today. So the instruction to "beat 11 false positives" was never measuring the
thing it appeared to measure, and 3 of those 11 are unwinnable by construction (B1-CEILING).
Recorded in the same stamp. Note the previous audit verified 67/96 and 11/29 as *reproducible*
- which they are. Reproducible and attributed to the wrong subject are independent properties,
and only the first was checked.

## Mechanical flags ADJUDICATED as NOT drift

- **[E] 5 placeholders** (`L145`, `L928` x2, `L1704`, `L1710`) - every one a bare `[]`
  appearing as Python source inside prose (`non-dict stdin (e.g. [])`, `failed=[] skipped=[]`,
  `out = []`). The script's placeholder pattern matches a bare `[]`. **FALSE POSITIVE.** Note
  this does not contradict the previous audit's "placeholder scan: zero hits" - that scan used
  `[TODO]`/`[TBD]`/`TKTK`-style patterns and did not include bare `[]`.
- **[C] 1 dangling figure ref + [F] 1 dangling table ref**, both at `L645`, which reads
  "`(?<![A-Za-z])` added; `Figure 3` / `Table 2` / `eq. 4` still...". Both are QUOTED EXAMPLES
  inside the plan's own description of a cross-reference detector. **FALSE POSITIVE** - the
  audit tool flagged the documentation of a cross-reference check as a broken cross-reference.
- **[A] 973 unmatched numbers, 206 in today's sections** - dominated by date fragments
  (`2026-08-06` yields 8.0 and 6.0), commit hashes and line references. **No sampling was
  applied**: all 206 were listed and scanned, and every one carrying a real claim is tabulated
  above. The rest are DEFINITIONAL or EXTERNAL relative to a 19-row source index.

## Cross-section consistency

Corpus size now appears as 125 (design sections, stamped historical) and 132 (B1 rows,
current). Intentional and marked. No other quantity carries two live values.

## Not checked, stated so the scope is not overread

Timing claims inherited from earlier sessions - 36.1s for the reverted detector, 0.087s for
the anchor gate, 24.65s -> 17.20s for `fast_test_on_stop` - were NOT re-measured. They are
stamped historical by their own rows and no conclusion in this pass rests on them.

## Verdict

3 defects found, all in prose written this session, all fixed. The most instructive is the
timing claim: the rule against uncontrolled timings was applied correctly to the mutation
sweep and to the corpus scores, and dropped for the one number that felt too small to matter.
