# Consistency audit - 2026-08-25 (session 4)

**Scope: ONLY prose authored this session** - `ff251e2..HEAD` (`60b9305`, `4072b51`, plus the
uncommitted denominator fix). 532 lines of prose: the `docs/PLAN.md` and `README.md` diffs, and
the docstrings/comments of `hooks/wired_clone_sanity.py` and its selftest.

Scoped deliberately. The previous unscoped run returned 88 candidates whose denominator was the
SOURCE SET's coverage, not the prose's accuracy - i.e. it measured which numbers happened to
appear in the indexed CSVs, which is a different question from whether this session's claims are
true. Tolerance: default rel 1%. Sources indexed: `docs/audits/gate_runs.json`,
`docs/audits/file_size_baseline.json`, the captured suite output.

## STEP 1 - mechanical pass (`scripts/audit.py`)

| class | raw | after adjudication |
|---|---|---|
| [A] number with no source match | 5 shown | **0 drift** - all four timing values are measurements this session TOOK; the source set contains no timing series to match against |
| [B] orphan figures | 0 | 0 |
| [C] dangling cross-refs | 0 | 0 |
| [D] claims to verify by reasoning | 4 | **0 drift, 1 fixed** (see below) |
| [E] unfilled placeholders | 11 | **0 real** - all are Python list literals (`[]`) and a type annotation `[(origin, key, value)]`, an artifact of including source code in the deliverable |
| [F] tables promised, not rendered | 0 | 0 |

**[E] is a false-positive class of my own making**, recorded rather than quietly dropped: feeding
`.py` files to a prose placeholder-detector makes every empty list look like `[TODO]`. The right
scoping for a code-carrying deliverable is docstrings only. Not a defect in the skill.

## STEP 2/3 - adjudication, and the two things that were actually wrong

Every headline number was **re-derived from scratch**, not re-read:

| claim | verdict |
|---|---|
| 12 of 26 `hooks/*.py` stale vs `ff251e2` | **CONFIRMED** - re-derived by content hash, 26 files, 12 differ |
| 5 of 10 entry points stale | **CONFIRMED** - same five names: `close_skills_guard`, `fast_test_on_stop`, `hook_health_check`, `meta_audit_on_stop`, `pre_push_gate` |
| 2 of 7 `settings.json` hooks stale | CONFIRMED |
| `hook_health_check.py` 861 lines / `run_selftests.py` 803 -> 897 | CONFIRMED by the `file-size` gate's own output |
| 50 files scanned, `{t@t, t}` from 3 files | CONFIRMED by direct execution |
| 1 wired clone, 0.33s, zero problems | CONFIRMED by the live run |
| 6.78s / 68%, battery 1.78s | CONFIRMED by `selftest-budget`'s own printed line |
| suite 43/44 | **RE-MEASURED at 03:00:14Z** - see below |

### DRIFT-1 (fixed) - a denominator carrying two literals, one of them wrong

The battery's verdict line printed `plus %d extractor and %d totality case(s)` with the numbers
supplied as the **literals `3` and `5`**. Two defects in one line:

1. It cannot move. Adding or deleting an extractor case leaves the printed count unchanged -
   "detect, don't list" violated *inside a denominator added to satisfy "name the denominator"*.
2. **It was already wrong.** Derived by execution, the true count is **5**, not 3.

Fixed: each extractor case now appends its own label as it runs, and the totality shapes are
hoisted so the count comes from the data. The line now reads
`10 state(s) asserted (3 must fire, 7 controls that must NOT), plus 5 extractor and 5 totality
case(s)` - and the 3 -> 5 correction IS the proof the counter is real rather than a new literal.

### DRIFT-2 (fixed) - a claim measured on a superseded tree

The item-10 commit states **"Suite 43/44 at 02:46:06Z"**. True when taken. But the item-8 attempt
and its revert both changed the tree afterwards, and the number was never re-taken - a figure read
off a state that no longer existed, which is this repo's own most-repeated defect.
**Re-measured at HEAD, 2026-08-25T03:00:14Z: `FAILED (1/44): ['hook-provenance']`, real rc
captured, not a pipe's.** The claim holds, but it now holds *because it was measured*, not because
it was inherited.

### [D] claims - all four hold

- *"12 of 26 files differ, so even the five LIVE entry points are importing stale siblings"* -
  SUPPORTED: `cap_shapes`, `cap_types`, `capped_report` are all stale and all imported by live hooks.
- *"the gate has never actually seen the write it most needs to see"* - SUPPORTED by direct
  execution: `_git(["config", "--global"] + args)` yields `[]` from `mutating_verbs_in`.
- *"this repo's single most-repeated defect"* - SUPPORTED: the plan names the scoped-denominator
  defect in three separate places, and this session made it a fourth.
- *"a guard that does that gets disabled"* - DEFINITIONAL, quoting the repo's own standing rule.

## Cross-section consistency

`5 of 10` and `12 of 26` appear in `docs/PLAN.md`, the commit message and this file, and agree in
all three. `HHC-SETTINGS-ONLY`'s "7 of the 10 entry points" is consistent with the table's 7
settings.json rows. The retired `5 of 6` figure survives nowhere: grep confirms it was replaced,
not merely contradicted elsewhere.

**One stale-by-design note carried forward:** the selftest docstring's cost paragraph describes
the 84% reading it was written for AND the 68% that superseded it, explicitly labelled as a second
reading, because the split that fixed it was made for an unrelated reason. That is deliberate
history, not drift.
