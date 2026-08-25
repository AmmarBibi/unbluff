# Meta-review - 2026-08-25 (session 4)

**Scope:** `ff251e2..HEAD`, this session. Run to its own procedure; CHECK 1's grep set
(`PARK|DEFER|TODO|OPTIONAL|candidate|later`) differs from the completeness sweep's - only the
word `park` overlaps, and it appears in neither result this time.

## CHECK 1 - parked but unscheduled

**Two hits, both benign, and this is the first close in four sessions where CHECK 1 did NOT find
a same-class regression at the end.** That is not because the session was cleaner - it is because
the check was moved. Standing check 1 now says *ask it MID-SESSION*, and asked mid-session it
fired three times, all before the commit:

1. `fixture_identities()` scans `hooks/*.py`, and its battery lives in `hooks/` - so the control
   identity was absorbed into the vocabulary and the check began firing on the control that
   proves it does not fire on correct work. **A grep guard must never search for a literal it
   contains** - the defect class the guard was built inside.
2. Narrowing `check_selftest_isolation` to ignore read-only `config` released
   `wired_clone_sanity.py` from the population, and with it the delegation edge that pulls in its
   fixture-building selftest - **a mutating selftest with no enforced scrub, created by the fix
   for mutating selftests with no enforced scrub.**
3. The battery's own denominator line - added to satisfy "name the denominator" - shipped two
   hardcoded literals, one of which was already wrong (3 where the truth is 5).

The two live grep hits are descriptive prose (`OPTIONAL` explaining why a guarded import reads as
optional; `candidate` naming a proposed hook shape in item 13). Neither is a parked item.

## CHECK 2 - instance-only fixes (the durability check)

| fix this session | instance or mechanism? |
|---|---|
| item 10's three config checks | **MECHANISM** - a standing SessionStart check, own gate, weekly sweep |
| `CONFIG_READ_ONLY_FLAGS` narrowing | **MECHANISM** - pinned in that gate's own selftest, 7 cases, both directions |
| `install.py` `REQUIRED_HOOKS` + 2 | instance, but the FLOOR is the mechanism and `install-guard` detects deletion - **OK** |
| README transcript refresh | instance; `readme-fresh` is the mechanism that forced it - **OK** |
| item 10's own controls | **NOT mutation-pinned** -> folded into item 9, whose scope was itself stale at "four guards" |
| **BUILT IS NOT LIVE correction** | **INSTANCE ONLY -> new item 15** |

**The BUILT IS NOT LIVE correction is the notable one, and it is the sharpest finding here.**
Correcting a number is not installing a mechanism. That number has now been wrong four times
(2 of 6, 4 of 6, 5 of 6, and the denominator wrong in all three), and three of those corrections
came from consistency passes that re-derived the NUMERATOR while never questioning the
DENOMINATOR. The fourth was caught only because item 10 happened to print a count that disagreed
with the prose - **luck wearing the costume of a process.** Item 15 converts it: `hook-provenance`
already compares the wired copies and already fails when they differ; it reports a verdict but not
a COUNT. Make it print the derived `N of M`, and the plan's sentence becomes checkable.

A second, smaller instance: item 9's row said "this session's four guards", a fixed count in a row
whose whole job is to track a growing set. It silently stopped covering anything built after it
was written - which is item 10's controls. Rewritten to name the families.

## CHECK 3 - optimization

`file-size`: **64** files in population (was 62 - the two new modules), limit 800, **5 recorded
offenders, all AT baseline, 0 new, 0 grown, 0 shrunk** (ledger, 02:59:46Z).

The interesting number is not the offenders - it is that the ratchet **blocked a legitimate fix
this session**. Adding item 8 took `run_selftests.py` 803 -> 897 and the gate failed with *"the
ratchet only turns one way"*. That is item 7's prediction (six lines of headroom) arriving as a
measurement on the very next addition. Reverted rather than re-recorded; see item 8.

Both new modules are well under the limit (351 and 262). `hook_health_check.py` went 567 -> 861
-> **599** across the session, because the file-size gate forced the split that
`_selftest_machine_sanity`'s cost had already argued for.

## CHECK 4 - READ the gate ledger, do not reconstruct

Read from `docs/audits/gate_runs.json` (215 rows), latest per tier:

| tier | latest | result |
|---|---|---|
| `run_selftests` | 2026-08-25T03:00:14Z | FAIL - `['hook-provenance']` only, 106.9s |
| `file_size` | 2026-08-25T02:59:46Z | PASS |
| `ship_bar` | 2026-08-25T02:59:46Z | PASS - 24 findings, 0 blocking |
| **`integration`** | **2026-08-24T18:42:34Z -> RE-RUN 03:07:54Z** | **PASS 34/34** |
| `mutation_sweep_filtered` | 2026-08-24T21:23:01Z | PASS |
| **`mutation_sweep`** | **2026-08-20T17:28:15Z** | **FAIL - FIVE DAYS** |
| `false_alarm_scorer` | 2026-08-20T13:46:26Z | PASS (age by design - its selftest is the gate) |

**The ledger earned its keep.** `integration` predated every commit in this session, and this
session added two hook modules and two `REQUIRED_HOOKS` entries that `install.py` acts on - the
exact surface standing check 8 exists for ("41 local gates passed over an `install.py` that
refused to install"). Re-run: **34/34, rc=0**, real `~/.claude/settings.json` untouched (mtime
still 2026-08-04; the test uses a throwaway HOME). Nothing was wrong - but that was unverified
until it was run, and "unverified" is not "fine".

`mutation_sweep` remains 5 days stale and is still the tier that would prove items 9 and 7.
Blocked behind item 2's pull. Unchanged from the previous meta-review, and stated again rather
than allowed to fade.

## CHECK 5 - improvements worth considering

1. **The pull is now blocking six items, not three.** Items 7, 9, the clean sweep, and now 15
   (best done immediately after the pull, when the count becomes 0 of 10 and a wrong number is
   least likely to be noticed). One command.
2. **The consistency skill's placeholder class mis-fires on source code** - every `[]` in a `.py`
   file reads as an unfilled `[TODO]`. Not a defect in the skill; the right scoping for a
   code-carrying deliverable is docstrings only. Recorded in the consistency artifact.
3. **Item 13's heredoc guard should be scoped by measurement before it is wired**, exactly as
   `piped_gate_guard` (4 of 15) and `timing_claim_guard` (18 of 109) were. A guard that fires on
   correct work gets disabled, which is strictly worse than none.

## CHECK 6 - mechanism health, and exactly ONE canonical order

**PASS.** `docs/NEXT_SESSION_PROMPT.md`'s first line still declares itself a pointer to
`docs/PLAN.md`. The Open section carries items 0-16 in one list; standing checks 1-8 are the only
other numbered sequence and they are a different kind of thing.

One defect found and fixed here: **inserting item 13 left the numbering as 11, 12, 14, 15 - a
skipped 13.** Renumbered. Also two pieces of drift created by my own correction to the BUILT IS NOT
LIVE paragraph: a dangling paragraph explaining a superseded count (rewritten as an explicit
history of the number), and item 2's body still reading "all four stale hooks" where the derived
figure is five (fixed, with a note that a number restated in a second place is a number that will
drift in one of them).

Hooks: `[hook-health] OK - 30 hook commands verified` at SessionStart, and `wired_clone_sanity`
reports `1 wired clone(s) config-checked` with zero problems in 0.33s.

## End-of-turn finalize

`docs/PLAN.md`'s single recommended-order list is current: 0-1, 3-4, 6, 10 DONE with dates and
commits; 2 PARTIAL and blocking; 5 a decision owed by the user; 7, 8, 9 blocked in a stated chain;
11-16 open, every one of them added to that list before or as it was raised, never in a side block.
