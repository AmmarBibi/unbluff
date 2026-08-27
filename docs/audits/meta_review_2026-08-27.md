# Meta-review - 2026-08-27

**Scope:** `d9723a5..HEAD` (`aeba569`, `4d800cb`, `9f67ebb`) plus today's uncommitted edits.
CHECK 1's grep set (`PARK|DEFER|TODO|OPTIONAL|candidate|later`) is run as its own, distinct from
the completeness pass's soft-defer sweep.

## CHECK 1 - parked but unscheduled

**10 hits, 0 parked items - and 1 real finding of a different kind.**

Nine hits are descriptive prose: item 18 necessarily contains `[TODO]` to describe it, item 13
says "candidate shape", item 4's "OPTIONAL" describes what `REQUIRED_HOOKS` makes non-optional,
items 20 and 24 narrate a deferred check. None is a parked item.

**The tenth was a contradiction this very session introduced.** CHECK 1's grep pulled up item
18's original *"Low materiality - it fails LOUD..."* sitting **below** the verdict added minutes
earlier that says *"That retires the low materiality label."* Two opposite claims, the stale one
underneath the fresh one - the token-vs-body contradiction this plan flags elsewhere, committed
by the pass that flags it. Merged, with the original wording kept and its scope narrowed (true
of the failure MODE, not a fair summary of the cost), and the ten-minute contradiction recorded
rather than silently tidied.

## CHECK 2 - instance vs mechanism (the durability check)

| fix this session | instance or mechanism? |
|---|---|
| the count corrected from 6 of 11 to a derived number | **MECHANISM** - item 15; the gate derives it, both prose copies deleted |
| dispatcher population 11 -> 16 | **MECHANISM** - `dispatcher_children()` matches by SHAPE, so a third dispatcher cannot be missed by name |
| CRLF false positive | **MECHANISM** - `_same_program`, plus M1/M2 probes in both directions |
| `run_selftests.py` headroom | **MECHANISM (partial)** - the split buys 145 lines; adding a gate still edits the orchestrator, and item 7 says so |
| `ROOT_FILES` enumerated roster | **MECHANISM** - now a glob; closed a hole that already existed for `install_selftest.py` |
| `PLAN.md:676` says 1192, file is 1213 | **INSTANCE** - and the third instance of "a number restated in a second place drifts". See below |
| the `sync_phrase` remedy-on-a-synced-tree bug | **MECHANISM** - pure function + M8 |

**The one that is still instance-only is the interesting one.** Item 15 moved ONE number out of
prose and into a gate. `PLAN.md` still hand-writes every other line count, and one of them
(1192 vs 1213) has been wrong since 2026-08-25. **The mechanism is correct and one number
wide.** Not scheduled as a new item, deliberately: a gate that checks every integer in a
markdown file against the tree is a large instrument for a small problem, and the honest fix is
to stop restating file sizes in prose at all when the baseline already holds them. Recorded here
so the judgment is on the record rather than implied.

## CHECK 3 - optimization

`file-size`: **66 files** (up from 64 - two new modules), limit 800, **4 recorded offenders,
none new, none grown.** `run_selftests.py` left the baseline entirely (803 -> 655), which is the
ratchet turning the correct way for the second time.

| file | lines |
|---|---|
| `hooks/pre_push_gate_selftest.py` | 1213 - still the largest, still the top split candidate |
| `hooks/fast_test_on_stop_selftest.py` | 1026 |
| `hooks/duplicate_registration_check.py` | 858 |
| `hooks/fast_test_on_stop.py` | 851 |

## CHECK 4 - READ the gate ledger, do not reconstruct

Read from `docs/audits/gate_runs.json` (265 rows):

| tier | latest | result |
|---|---|---|
| `run_selftests` | 2026-08-27T05:30:12Z | PASS (44/44) |
| `file_size` | 2026-08-27T05:56:56Z | PASS |
| `ship_bar` | 2026-08-27T05:29:37Z | PASS |
| **`integration`** | **2026-08-26T20:58:07Z** | PASS 34/34 - **but STALE, see below** |
| `mutation_sweep_filtered` | 2026-08-24T21:23:01Z | PASS |
| **`mutation_sweep`** | 2026-08-20T17:28:15Z | FAIL - **a full run is IN FLIGHT since 05:37Z** |
| `false_alarm_scorer` | 2026-08-20T13:46:26Z | PASS (age by design) |

**`integration` is stale AGAIN, and by content rather than age** - the rule that caught it twice
before caught it a third time. Two `.py` files (`tools/hook_divergence_report.py`,
`tools/hook_divergence_selftest.py`) were committed after its 20:58:07Z run. **Third consecutive
session this tier has been stale**, which is no longer an anecdote supporting item 17 but the
strongest argument in the file for it.

**And it is stale in ONE WORKTREE ONLY.** The live worktree ran integration at 05:33Z; this
worktree's ledger stops at 20:58Z, because the ledger is gitignored and per-worktree (item 21).
So "is this tier stale?" currently has two correct and opposite answers depending on where you
ask - which is the concrete harm item 21 predicts and item 17 would inherit.

**Not re-run during this pass, deliberately and with the reason stated:** a full
`mutation_sweep` has been running since 05:37Z, it writes to the repository, and `integration`
installs and uninstalls hooks. Running both against one tree is the concurrency case
`tooling-discipline` section 3 describes as silent. It is re-run the moment the sweep lands.

## CHECK 5 - improvements worth considering

1. **Point the expensive pass at what nobody has looked at.** The design-lens pass produced the
   two sharpest findings today (items 23 and 25) at trivial cost, both by comparing new code to
   a convention written in ANOTHER file. That is now three consecutive sessions where this lens
   won. It should stop being a closing check and become the FIRST thing done to any new unit.
2. **`hook_health_check` and `hook-provenance` should not be able to disagree.** Item 25 is the
   instance; the general form is that two gates answering "is my wiring healthy?" share no code.
   The fix named in item 25 (reuse `_same_repo_same_bytes`) is also the structural one.
3. **Three items now block on one unanswered question** - is the gate ledger per-worktree state
   or repository state? Items 17, 21 and 24 all depend on it. It is one decision and it unblocks
   three rows; it should be taken before any of them is built.

## CHECK 6 - mechanism health, and exactly ONE canonical order

**One canonical order: PASS.** `docs/NEXT_SESSION_PROMPT.md` remains a pointer.
Items **0-25 verified contiguous by parsing the headings** (`^(\d+)\. \*\*`), standing checks
**1-8**, two sequences, no gaps, no repeats. New items 20-25 were added to that one list as they
were raised, never in a side block.

**Suite:** 44/44 rc=0 at 05:26Z. `--code-only` 44/44 rc=0, with `hook-provenance` named as
excluded. Pre-push gate exercised three times for real and behaved correctly each time,
including once when it correctly REFUSED a push (`readme-scenarios`, item 21).

**Hooks: NOT healthy, and that is finding 25.** `hook_health_check` reports **8 problems across
31 hook commands** on a fully-synced tree, all of them byte-identical copies reached through a
sibling worktree, while `hook-provenance` reports the same machine as clean. Scheduled.

## End-of-turn finalize

`docs/PLAN.md` carries one list, **0-25**: items 0-6, 10, 15 and 20 DONE with dates and commits;
7 PARTIAL and saying so in its first line; 8, 9, 11-14, 16-19 and 21-25 open. Every item raised
in this close was added to that list as it was raised.

**Six new items came out of this close (20-25), four of them defects in code written today.**
That ratio is the argument for auditing the session that wrote the code rather than the one
after it.

## Deviations, stated as deviations

1. **The four skills were invoked before the last remediation.** `close_skills_guard` enforces
   recency; the plan edits and the item-23 code fix follow the artifacts that prompted them.
   That is the intended audit -> fix order, and every edit is described in the artifact that
   caused it.
2. **Two fixes are deferred within this session with a stated trigger** - the consistency
   corrections and item 23's fail-open - because `file_size_baseline.json` and the source files
   are inputs the in-flight `mutation_sweep` verifies against. Named here so a deferral with a
   reason does not quietly become a deferral without one.
3. **`integration` was not re-run before this artifact was written**, for the concurrency reason
   in CHECK 4. Its result is therefore UNVERIFIED at the moment of writing, not assumed passing.
