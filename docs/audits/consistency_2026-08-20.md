# Consistency audit - 2026-08-20 session

Deliverables audited: `docs/audits/task17_sweep_2026-08-19.md`, the erratum in
`source_coverage_2026-08-16.md`, the `CHANGELOG` `[Unreleased]` entries added this session, and
the seven commit messages on `feat/enforcing-verify` (`ef4956d`..`6a0aba8`).

Mechanical pass: `skills/consistency-audit/scripts/audit.py`, tolerance rel=0.01, indexing 901
values from 41 files under `docs/audits`. **[A] 0, [B] 0, [C] 0**, [D] 6 for reasoning, [E] 16.

## Adjudication

| Class | Count | Verdict |
|---|---|---|
| [A] number with no source match | 0 | nothing to adjudicate |
| [B] orphan figure | 0 | - |
| [C] dangling cross-ref | 0 | - |
| [D] claim to verify | 6 | all OK - see below |
| [E] placeholder | 16 | **all FALSE POSITIVES** - see below |

**[E] is noise on this deliverable, and the reason is worth recording.** Every hit is markdown or
Python, not a placeholder: severity tags (`[MEDIUM]`, `[HIGH]`), Python slices (`[:MAX_FINDINGS]`,
`[MAX]`), and empty lists (`[]`) quoted inside findings. The extractor's placeholder rule assumes
prose; a findings document is mostly code. Recorded rather than silently dismissed, because "16
placeholders" in a report that has none is exactly the shape that trains a reader to ignore the
class. No action on the deliverable; a note for the skill is filed as a task.

**[D] six claim sentences.** Each is a qualitative statement inside a quoted finding
(`gates that CANNOT FAIL rather than edge cases`, the set()/frozenset() failure scenario, the
load_factor claim, ...). All six were adjudicated against the code they name during the sweep and
its refutation round; none asserts a number. No drift.

## Findings the reasoning pass produced

### C-1. DRIFT - the never-examined denominator is stale by 2

`task17_sweep_2026-08-19.md` states "55 tracked `.py` files ... 32 never examined ... plus
`tools/gate_modes.py` - 33". DERIVED 2026-08-20T14:12:28Z: **57 tracked, 34 UNREVIEWED**.

Cause, and it is benign: two files were created after the sweep list was derived -
`tools/gate_modes.py` (which WAS swept: it was added to batch b11 deliberately) and
`tools/noregress_selftest.py` (created today by the no_regression split, and NOT swept).

Verdict: the figures were correct when written and the document is a dated record, so they stay.
What matters is the consequence, which is a COVERAGE fact rather than a numeric one, and it is
carried into the completeness audit rather than left here: **one never-examined unit now postdates
the sweep**, and so does every line of new code written today in seven other files.

### C-2. DRIFT - `no_regression.py` cited at 684 lines, now 696

Commit `0bb540b` says "no_regression.py is now 684 lines", which was true at that commit. The
transitive-isolation fix in `fd13d56` added 12 lines. LIVE: **696**.

Verdict: DRIFT in the number, but the CONCLUSION it supports is unaffected and re-derived here -
696 is still under the 800 limit, the file is still absent from `file_size_baseline.json`, and the
ratchet still records **5** offenders (down from 6). The commit message is history and stays; the
task ledger entry for #11 carried the stale figure and has been corrected.

### C-3. STALE EVIDENCE - the recorded full sweep is older than the last two commits

The newest `mutation_sweep` row is `2026-08-20T13:39:47Z`, `executed=219, survivors=0, errors=0,
unproven=0`. Commits `ac84464` (~13:48Z) and `6a0aba8` (~14:11Z) landed AFTER it.

This is the exact condition task #4 exists to gate on, found by this audit rather than by that
gate - which does not exist yet. The changed units were covered by FILTERED runs (`no_regression`
6 of 6, `piped_gate_guard` 9 of 9, both all-CAUGHT), and the harness itself prints the right
caveat: *"filtered run - this proves nothing about the N entries not considered"*.

Action taken: a full sweep was launched at 14:12Z against `6a0aba8` and its result is reported in
the meta-review. Until it lands, the honest statement is "the last FULL sweep predates the last
two commits", and no claim of a fully-swept tree at HEAD may be made.

### C-4. OK - the generated record matches its source exactly

Every count in `task17_sweep_2026-08-19.md` re-derived from workflow `wf_7b752d72-92e`'s result
object: files_swept 33, batches 11, produced 61, unadjudicated 0, confirmed 15, refuted 46. All
match. The yield arithmetic checks out too: 15/8.5M = 1.76 per M and 4/4.6M = 0.87 per M, as
stated. This is what generating a record rather than transcribing it buys.

### C-5. OK - anchors, ledger and baseline agree with the prose

`mutation-anchors: OK - 225 anchor(s) across 222 mutation entr(ies)` matches the figure used in
the last two commit messages. `file_size` row `walked=57, over_limit=5` matches the baseline file's
5 recorded offenders.

## Tolerance and reproducibility

rel-tol 0.01, sources `docs/audits` (41 files, 901 indexed values). Every figure above was
re-derived at 2026-08-20T14:12:28Z by running the producing tool, not by reading a prior report -
the one exception being the sweep row, which is read from the ledger because its producer had
exited.
