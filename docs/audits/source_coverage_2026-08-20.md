# Source-coverage audit - 2026-08-20 session

The "source" here is the repo's own code surface plus its review ledger. The question this pass
answers is the one a grep cannot: **what does the plan never mention?**

## 1. Never-examined units vs what #17 actually swept

DERIVED 2026-08-20T14:19:31Z with `python tools/check_review_freshness.py`, diffed against the
32-unit list the sweep was scoped from.

| | |
|---|---|
| tracked units now | **57** (was 55) |
| UNREVIEWED now | **34** (was 32) |
| swept by #17 | 33 |

Set difference - units never examined now that were not in the sweep's scope list:

- `tools/gate_modes.py` - **covered**. Created mid-session, and deliberately added to batch b11 so
  the sweep would not exclude the author's own new file. It is UNREVIEWED only in the ledger's
  sense (no `--record` row was written); a reviewer did read it.
- `tools/noregress_selftest.py` - **NOT covered by any reviewer, and now scheduled** (task #20).
  Created today by the `no_regression` split, after the sweep ran.

Nothing dropped out of the unreviewed set, which is the expected shape: no `--record` calls were
made this session. **That is itself worth stating** - the sweep examined 33 files and recorded
reviews for none of them, so the freshness gate still reports all 33 as never-examined. Recording
them is not a bookkeeping nicety: `--record --unit scripts/make_demos.py` is the exact action that
would have detonated the roster gap fixed in `4cb9d81`, which is why it was not done blind.
Filed as part of task #20's scope.

## 2. Gates and tools whose failure would be silent

- **`AUX_GATES`: 16 rows, all 16 now visible** to `piped_gate_guard` (derived, printed by its
  selftest). Before `6a0aba8`, 3 enforcing rows were invisible - including the ship bar.
- **`tools/` classification**: both files added this session (`gate_modes.py`,
  `noregress_selftest.py`) are declared in `NOT_A_GATE` with reasons; `classify_tools()` passes,
  so no tool sits in neither list.
- **Gaps found: none new.** Every gate whose silent failure is known has a task: `hook-provenance`
  (#8, worktree-blind), `hook_divergence_report`'s unreachable FAIL branch (#15), the two
  ledger-recording paths (#4e), the two unpinnable behaviours (#7).

## 3. Were the defect CLASSES swept, or assumed?

| Class | Status |
|---|---|
| C1 record-on-PASS-path-only | **SWEPT**, 2 confirmed (both fixed, `ac84464`) |
| C4 floor living only in `selftest()` | **SWEPT** - supersedes the 2026-08-16 record of "class 4 not swept". One confirmed finding carries the class (`extract.py`'s unvalidated PyMuPDF branch, task #16) |
| C5 swallowed exception | **SWEPT**, several candidates, most refuted |
| C6 declared-vs-derived roster | **SWEPT**, 3 confirmed (2 fixed, 1 open as #17) |
| C7 invocation-dependent import | **SWEPT**, 1 confirmed (fixed in `ac84464`) - **and see below** |
| C8 shrinkable denominator | **SWEPT**, 2 confirmed (open as #17) |

The 2026-08-16 meta-review's "class 4 explicitly recorded as NOT swept rather than as zero" is now
discharged. It was the right call to record it as unswept rather than as zero - had it been
recorded as zero, nobody would have pointed the sweep at it.

## 4. Did a fix I made create a NEW instance of the class it fixed?

**Yes - one, and it is the finding of this pass.**

`ac84464` fixed a **C7** instance (`import gate_ledger` inside `main()` in
`score_false_alarms.py`). `0bb540b`, four commits earlier, **created one**: the `no_regression`
split left `selftest()` doing a lazy `from noregress_selftest import selftest`, and the docstring
beside it asserted *"the sibling directory is put on sys.path explicitly at module scope, above"*
- **which was false**. There was no such line.

MEASURED:

```
python tools/no_regression.py --selftest   ->  rc 0   (works: a script puts its dir at sys.path[0])
python -m tools.no_regression --selftest   ->  rc 1   ModuleNotFoundError: noregress_selftest
```

Every caller in this repo invokes it as a script, so **nothing was red** - the silent,
invocation-dependent shape exactly. Fixed in this pass by adding the module-scope
`sys.path.insert(0, HERE)` the docstring already claimed existed; both invocations and the
enforcing gate now return 0.

Three things are worth recording about how this was found, because none of them was luck:

1. It was found by ASKING THE QUESTION - "did a fix create a new instance of the class it fixed?"
   No gate asks this, and no gate could have: the code passes every check in the repo.
2. My first probe for it was **rigged and proved nothing**: it inserted `tools/` into `sys.path`
   itself before importing, so of course the import resolved. The real test had to remove the
   condition being tested, not supply it.
3. A DOCSTRING asserted the mitigation. Prose describing a safety property is not the property -
   the same lesson `PG2`'s drifted anchor taught two hours earlier, when a comment saying "this is
   PG2's mutation anchor" failed to stop me editing the anchor.

**Other classes checked for self-inflicted instances, none found:** the new `_PROTECTORS` and
`PS_TRUNCATING` vocabularies are declared rosters (C6) but are shell semantics that cannot be
derived from this repo - recorded as a justified exclusion, and both are asserted in both
directions by the selftest. `COPY_TREES` remains declared but is now guarded by `roster_gaps()`,
which derives its adequacy from `UNIT_GLOBS`. `GATE_TOKENS` remains declared but its coverage is
now derived from `AUX_GATES` and printed. Every new floor added this session
(`roster_gaps`, `shared_siblings`) is reached from `main()`/`compare()`, not only from a selftest,
so no new C4 instance was created.

## Ledger status

Every source item enumerated above is BUILT, SCHEDULED against a numbered task, or a recorded
justified exclusion. The one gap this pass found (the C7 instance) was fixed during the pass
rather than scheduled, because it was a defect introduced by this session and leaving it open
would have shipped a false docstring with it.
