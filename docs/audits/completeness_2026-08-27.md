# Completeness audit - 2026-08-27

**Plan:** `docs/PLAN.md`, items 0-22 plus 8 standing checks. **Session scope:** `d9723a5..HEAD`
(`aeba569`, `4d800cb`, `9f67ebb`). STEP 1 run as its own grep set, distinct from the
meta-review's CHECK 1.

## STEP 0 - numbering contiguity, parsed not eyeballed

30 numbered rows parsed from the headings: **0-21 contiguous** (22 added by this pass, making
0-22), then standing checks **1-8**. Two sequences, both contiguous, no repeat of the
skipped-13 defect. Verified by parsing `^(\d+)\. \*\*`, not by reading.

## STEP 1 - soft-defer sweep (failure mode a)

Grep set: `-> park`, `\bpark\b`, `on demand`, `on-demand`, `wait for a concrete`,
`deferred opportunistic`, `pick when value beats`, `someday`, `maybe later`, `if time`,
`DROPPED`, `EXCLUDED`/`excluded`.

**8 hits, 0 findings.** Adjudicated individually:

| line | hit | verdict |
|---|---|---|
| 166 | "deliberately excluded" | descriptive - a design decision about `fast_test_on_stop`'s ratchet headroom |
| 381 | "dropped the broken clone out of the roster" | descriptive - a past defect being narrated |
| 518 | "ever scheduled or excluded" | item 17 describing the GAP it exists to close |
| 592 | "`hook-provenance` listed as excluded" | descriptive - what `--code-only` prints |
| 606 | "recorded rather than dropped" | item 20 explicitly PREVENTING a drop |
| 656, 685, 687 | Retired section | the section whose job is recording retirements |

No optional-forever item remains. `plan-defer-guard` stays the tripwire between runs.

## STEP 2 - the dangerous half: what did THIS session raise that has no home?

The plan is not the only source here - the session itself is. Every item raised in the last six
hours was enumerated and checked for a home, which is the check that catches defer-and-forget
at the moment it would happen.

| raised | home | status |
|---|---|---|
| branch-vs-wired divergence | item 20 | DONE, decided, merged |
| per-worktree gitignored ledger | item 21 + precondition inside item 17 | scheduled |
| `piped_gate_guard` false positive | **was a loose end - now item 22** | **GAP CLOSED** |
| item 18's second measurement | item 18 body | **GAP CLOSED** |
| `PLAN.md:676` says 1192, file is 1213 | **no home - scheduled below** | **GAP** |
| this session's own 667/321 line counts already stale | **no home - scheduled below** | **GAP** |
| `pytest tests/test_integration.py` -> exit 5, "no tests ran" | adjudicated below | EXCLUSION |

### GAP 1 (closed) - a "check it when X happens" whose X happened in-session

Item 20 recorded the `piped_gate_guard` false positive and deferred the verification: *"whether
M10 fixes that shape is unverified, and it should be checked when item 5's fix goes live rather
than assumed."* **Item 5's fix went live at 05:21Z, in this session, forty minutes later.** The
completeness pass is what noticed that the precondition had been met.

Checked rather than assumed: **M10 does NOT fix it**, on the wired copy and the repo copy. Now
item 22, characterised with a control (swap the gate filename for a non-gate file and the guard
goes quiet, so it is the NAME triggering it). This is the single most likely item in the file to
have been silently dropped - a deferred check whose trigger fires inside the same session reads
as "already handled" to the next reader.

### GAP 2 (scheduled) - two number drifts from the consistency pass

`consistency_2026-08-27.md` found two, neither of which had a home in the plan:

1. `PLAN.md:676` calls `pre_push_gate_selftest.py` "1192 lines"; it is **1213**, and the
   baseline records 1213. Pre-existing drift from the 08-25 accepted growth.
2. `PLAN.md` item 7 and `file_size_baseline.json` both state the split sizes as **667 / 321**.
   They are now **681 / 351** - written correct, then invalidated forty minutes later by this
   session's own `sync_phrase()` fix and M8 probe, inside the write-up of the item about
   hand-written numbers drifting.

**Both are DEFERRED, WITH A REASON AND A DATE, not dropped:** a full `mutation_sweep` is in
flight, and `file_size_baseline.json` is an input the sweep verifies mutations against. Editing
it mid-sweep could flip a mutation verdict, which is `tooling-discipline` section 3. They are
applied the moment the sweep lands, in this session - and if the sweep does not land, they carry
to the next session as an explicit row rather than as a memory.

### EXCLUSION - the pytest invocation

`python -m pytest tests/test_integration.py -q` returns **exit 5, "no tests ran"**; the tier's
real entry point is `python tests/test_integration.py`. **FINALIZED EXCLUSION, not a build
item:** exit 5 is non-zero, so it cannot be misread as a pass, and the suite and CI both invoke
the correct form. Recorded so the next person who reaches for pytest here knows within one line
that they have the wrong entry point, and so this is a decision rather than an omission.

## STEP 3 - ledger

The BUILT vs SCHEDULED inventory for this session:

| item | state | evidence |
|---|---|---|
| 2 - clone repair + pull | **BUILT** | `b6cc6cc` -> `d44138c`, 0 behind, clean |
| 15 - derived BUILT IS NOT LIVE count | **BUILT** | gate prints `0 of 16` / `0 of 28`; 8/8 mutations caught |
| 7 - orchestrator split | **PARTIAL, row says so** | 803 -> 655; the REGISTRY cut is still open |
| 20 - branch/wiring decision | **BUILT** | pushed, merged, suite 44/44 rc=0 |
| 21 - per-worktree ledger | SCHEDULED | precondition written into item 17 |
| 22 - piped-gate false positive | SCHEDULED | characterised, control included |
| 18 - placeholder class | SCHEDULED, evidence upgraded | 18 candidates, 0 real, 2 sessions |
| 8, 9, 11, 12, 13, 14, 16, 17, 19 | SCHEDULED, untouched | - |

## STEP 4 - verify

Re-grepped: zero soft-defer markers survive as real items; numbering contiguous 0-22 and 1-8;
every item raised this session has a home or a written exclusion. **Two items are deferred with
a stated reason and a same-session trigger** - that is the only form of deferral this plan
permits, and it is named here so it cannot quietly become a third form.

## Verdict

**2 gaps closed, 2 scheduled with a reason and a trigger, 1 finalized exclusion, 0
optional-forever items.** The pass's own best catch was GAP 1: a deferred verification whose
trigger fired inside the same session, which is exactly how a check gets recorded as done
without being done.
