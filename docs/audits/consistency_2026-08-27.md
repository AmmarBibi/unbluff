# Consistency audit - 2026-08-27

**Scope:** what THIS session authored, `d9723a5..HEAD` (`aeba569`, `4d800cb`, `9f67ebb`).
Deliverable `docs/PLAN.md`; docstrings only for the `.py` files. Mechanical pass run with the
skill's bundled `scripts/audit.py`, tolerance rel=0.01, source index = `file_size_baseline.json`
+ `gate_runs.json` (106 values, 2 files). 627 numbers found, 478 checked.

## STEP 1 - mechanical pass

| class | raw | adjudicated real |
|---|---|---|
| [A] number with no source match | 250 | **1** |
| [B] orphan figure | 0 | 0 |
| [C] dangling cross-ref | 0 | 0 |
| [D] claim to verify by reasoning | 11 | **1** |
| [E] unfilled placeholder | 7 | **0** |
| [F] table promised, not rendered | 0 | 0 |

**[A]'s 250 is an instrument artifact and is reported as one.** The script indexes numeric
values from source CSV/JSON and asks whether each prose number appears there. `PLAN.md`'s
numbers are UTC timestamps, commit SHAs, line counts and gate counts, and its authoritative
sources are the GATES that print them, not two JSON files. The class is not usable at this
scope. Recorded rather than quietly skipped, because "250 candidates, all noise" and "the
extractor looked in the wrong place" are the same output.

## STEP 2 - adjudication

### [E] 7 placeholders, 0 real - and it is item 18 firing on item 18

All seven are lines 542-551, inside **item 18's own body**, which exists to describe
`[TODO]` / `[TABLE]` / `[insert value]` / `[]` as tokens the placeholder detector should or
should not match. The shipped extractor cannot tell a placeholder from prose ABOUT a
placeholder.

This is a second measurement of item 18, not a new finding: **11 false candidates and 0 real on
2026-08-25, 7 false and 0 real today.** Two sessions, 18 candidates, zero real. That is now
enough evidence to stop treating item 18 as low materiality bookkeeping - the class has never
once been right on this deliverable.

### [D] ONE real drift, and it is the plan's own recurring defect

**`docs/PLAN.md:676` says `pre_push_gate_selftest.py` is "1192 lines and the largest file
here". It is 1213**, and `file_size_baseline.json` records 1213. The `_accepted_growth_2026_08_25`
note took it 1192 -> 1213 and updated the baseline; this prose line was not updated with it.

- **Verdict: DRIFT.** Pre-existing, not authored this session.
- **Cause: the exact class item 15 was built to end** - a number restated in a second place
  drifted in one of them. This is the THIRD independent instance in this file (the BUILT IS NOT
  LIVE count, item 2's copy of it, and now this).
- **Action: correct 1192 -> 1213, and stop restating it** - the baseline is the source, the
  prose should point at it. Deferred until the mutation sweep in flight completes, because
  `file_size_baseline.json` is an input the sweep verifies mutations against.

### [A] the one real member of the class - and it is MINE, from this session

Not surfaced by the script (its index could not see it); found by re-deriving every number this
session wrote, which is the check the script cannot perform.

**`docs/PLAN.md` item 7 and `file_size_baseline.json` both state the split sizes as
`hook_divergence_report.py` 667 and its sibling 321. They are now 681 and 351.**

The numbers were correct when written and stopped being correct forty minutes later, when the
`sync_phrase()` fix and the M8 probe were added to those same two files. **I wrote a
measurement and then changed the thing measured, inside the write-up of the item whose entire
subject is that hand-written numbers drift.**

- **Verdict: DRIFT**, authored this session.
- **Action:** label them as at-the-split INSTANTS and give the current values, following the
  convention `file_size_baseline.json` already uses in its own notes ("THOSE ARE AN INSTANT,
  NOT A CURRENT FACT"). Same deferral as above.
- **The generalisable point:** item 15 moved ONE number out of prose and into a gate. Every
  other line count in this file is still hand-written and still drifts. The mechanism is right;
  its scope is one number wide.

## STEP 3 - reasoning pass

1. **Claim support.** The session's substantive claims were each re-derived from the artifact
   rather than the prose: `run_selftests.py` 655 (matches), suite 44/44 rc=0 (matches the
   05:26Z run), `BUILT IS NOT LIVE 0 of 16 / 0 of 28` (matches the post-merge gate output),
   integration 34/34 rc=0, 8 of 8 mutations caught. All hold. The two that did not are above.
2. **Cross-section consistency.** The BUILT IS NOT LIVE count now appears in exactly one
   authoritative place - the gate - and the plan's history table is explicitly labelled as
   history and carries no current figure. Item 2's duplicate copy is deleted. Checked by grep:
   no remaining line asserts a current stale-count.
3. **Interpretation.** One narrative correction was required and was made in-place rather than
   quietly: item 20's first draft claimed the branch-vs-wired mechanism was undocumented and
   that a deadlock existed. Both were false - `.claude/pre-push.cmd` `[#45]` and
   `run_selftests.MACHINE_STATE` document the mechanism, and `--code-only` means there was
   never a deadlock. The item now records the correction as the finding.

## Tolerance and reproducibility

rel-tol 0.01, sources `docs/audits/file_size_baseline.json`, `docs/audits/gate_runs.json`.
Re-run: `python ~/.claude/skills/consistency-audit/scripts/audit.py --deliverable docs/PLAN.md
--sources docs/audits/file_size_baseline.json,docs/audits/gate_runs.json`

## Verdict

**2 real drift items, both of the same class, one of them authored today by the session that
was fixing that class.** No orphan figures, no dangling refs, no real placeholders. The
mechanical pass contributed 1 of the 2; the other came from re-deriving the session's own
numbers, which is the half no script does.
