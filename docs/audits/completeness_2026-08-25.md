# Completeness audit - 2026-08-25

**Scope:** this session, `1e12792..d39559d`. Run to its own procedure - STEP 1's grep set is
distinct from meta-review CHECK 1's; only the word `park` overlaps.

## STEP 1 - soft-defer sweep (failure mode a)

Markers searched: `-> park`, `\bpark\b`, `on demand`, `on-demand`, `wait for a concrete`,
`deferred opportunistic`, `pick when value beats`, `someday`, `maybe later`, `if time`, `DROPPED`,
`not taken`, `left for later`.

**1 hit, benign:** line 199, "maintenance obligation is dropped" - prose about a consequence, not
a deferral. No optional-forever item remains.

## STEP 2 - every item carries a state

| # | state | item |
|---|---|---|
| 0 | DONE | `close_skills_guard` recency |
| 1 | DONE | Land the branch (PR #3 merged) |
| 2 | **PARTIAL** | Repair the main clone - config done, pull blocked |
| 3 | DONE | per-hook `--selftest` isolation, all 8 |
| 4 | DONE | pin the #46 control's wiring |
| 5 | **DECISION** | wire `piped_gate_guard` (M10 now discharged) |
| 6 | DONE | `fast_test_disclosure` prints before it records |
| 7 | OPEN | split `run_selftests.py` |
| 8 | OPEN | `--code-only` not-default is unenforced (was #47) |
| 9 | OPEN | this session's guards are not mutation-pinned |
| 10 | OPEN | the config repair has no mechanism |

### Finding 1 - a DONE token over a body saying blocked

Item 2 read **"CONFIG HALF DONE ... the `git pull` is still blocked"**. The leading token is DONE;
the body says blocked. That is the same token-vs-body contradiction the plan flags elsewhere, in
the plan itself. **Relabelled PARTIAL.**

### Finding 2 - #47 WAS ORPHANED BY THE PLAN RE-CUT, and the defect is live

`#47` appears **once** in `plan_v140_retired_2026-08-24.md` and **zero times** in the current plan.
The 2026-08-24 re-cut retired the old plan wholesale and this row did not make the crossing.

Verified live at 2026-08-25T01:43:40Z rather than assumed:

- `.claude/pre-push.cmd` exists and runs `python run_selftests.py --code-only`
- its own comment asserts the flag is *"deliberately NOT the default"*
- `grep` across `tools/` for anything checking that: **nothing**

So adding `--code-only` to `.claude/fast-test.cmd` would silently weaken the strictest check in the
project and no gate would notice. **Re-homed as item 8.** It has now failed twice over - once as a
defect (an unenforced assertion, created by the session that fixed an unenforced assertion) and
once as bookkeeping (lost by a re-cut). That second failure is the one this skill exists for: a
grep cannot find what the plan does not mention.

## STEP 3 - rows filed this session all have a home

`M10` (2 mentions), `PG-QUOTED` (plan + 3 in source), items 8, 9, 10 all in the order. Nothing
deferred today is unscheduled.

## Deviations

- STEP 2's full source-vs-plan sweep was **not** run: the authoritative source here is the codebase
  itself, and the equivalent pass is the source-coverage artifact, run separately today.
- Item states above are read from the plan's own prose. Items 7, 9 and 10 are blocked on ordering
  (item 2's pull -> clean sweep), which is recorded in each row rather than inferred.
