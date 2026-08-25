# Completeness audit - 2026-08-25 (session 4)

Target: `docs/PLAN.md` at `4072b51`. Run to its OWN procedure - STEP 1's grep set is distinct from
meta-review CHECK 1's, and only the word `park` overlaps.

## STEP 1 - soft-defer sweep (failure mode a)

10 raw hits. Nine are already FINALIZED exclusions or descriptive prose, not defers:

| line | hit | verdict |
|---|---|---|
| L4-5 | `retired` (the v1.4.0 plan) | FINALIZED - archived verbatim, path recorded |
| L149 | `deliberately excluded` (read-only git callers) | FINALIZED - reason stated, prevents a gate firing on correct work |
| L219 | `plan_v140_retired` | reference, not a defer |
| L287 | `dropped the broken clone out of the roster` | describes a DEFECT that was fixed |
| L310 | `OPTIONAL` (guarded imports) | describes a mechanism, and the fix that followed |
| L346-362 | the `Retired, not forgotten` section | the section exists to make retirement explicit |
| L355 | `maintenance obligation is dropped` | FINALIZED with reason |

**One real hit, and it is the exact shape STEP 1 exists for:**

- **"Undecided, deliberately: whether the repo stays public ... Parked by choice on 2026-08-24,
  not forgotten."** A decision with no date and no condition is indistinguishable from one that has
  been dropped, and "not forgotten" is an assertion, not a mechanism.
  **RECLASSIFIED**: it is a DECISION, not a build item, so it gets a TRIGGER rather than a
  materiality slot - *the next time this repo would be shown to anyone (a CV link, an application,
  a PR from a stranger), or the next re-cut of this plan, whichever comes first.* Until then
  public stands **by default rather than by omission**, which is the distinction that was missing.

Zero optional-forever items remain.

## STEP 2 - source-coverage (failure mode b - the dangerous one)

The plan's authoritative sources are its own audit artifacts. Swept
`docs/audits/meta_review_2026-08-25.md` - the newest, and the one this session was told to act on -
item by item against the plan.

**Two of its three CHECK 5 recommendations had NO home in the plan.** A grep could never have found
these: the plan did not mention them, which is the whole definition of this failure mode.

| meta-review recommendation | in the plan before this audit? | action |
|---|---|---|
| 5.2 `hook_health_check` is the natural home for machine-sanity checks | YES - became item 10 | built this session |
| **5.1 Run CHECK 1 mid-session, not only at the close** | **NO - zero hits for "mid-session"** | **folded into standing check 1 itself** |
| **5.3 The heredoc trap wants a hook (REMEMBER vs ENFORCE)** | **NO - zero hits for "heredoc"** | **scheduled as new item 14** |

### Why 5.1 mattered enough to change the check rather than add a row

The practice existed only inside an audit file nobody re-reads, which makes it prose about prose.
It is now part of standing check 1's text, because the TIMING is the load-bearing half: the check
has fired on this author's own work in **four consecutive sessions**, and in the first three the
fix was already committed by the time it fired. Asked mid-session on 2026-08-25 it paid three
times over, all before the commit - the extractor that scanned the directory its own battery lives
in, the gate narrowing that released a fixture-building module from its safety population, and a
denominator that shipped two hardcoded literals of which one was wrong.

### Why 5.3 is a build item and not a note

The cost is measured: **four incidents in two days**, and the worst was SILENT - backticks inside a
`python -c "..."` payload were command-substituted by the shell before Python saw them, the script
printed success, and the file it wrote had every backticked filename deleted. Nothing failed.
This repo has already converted this exact class of recurring prose into a hook twice
(`piped_gate_guard`, `timing_claim_guard`), and both were scoped **by measurement** - they fire on
4 of 15 and 18 of 109 real cases. Item 14 carries that constraint explicitly: measure the
false-alarm rate against real history before wiring, because a guard that fires on correct work
gets disabled, which is strictly worse than no guard.

## STEP 3 - ledger

| item | state |
|---|---|
| 0, 1, 3, 4, 6 | BUILT, dated, commits recorded |
| 2 | PARTIAL - config half done; the `git pull` is the session's blocker and blocks 7, 9 and the sweep |
| 5 | DECISION OWED BY THE USER - evidence refreshed, recommendation WIRE |
| 7, 9 | SCHEDULED, blocked behind item 2's pull -> clean sweep |
| 8 | SCHEDULED, blocked behind item 7 - **proved by the ratchet this session**, design recorded so it is not rediscovery |
| 10 | BUILT this session |
| 11, 12, 13 | SCHEDULED, opened this session from what item 10 turned up |
| **14** | **SCHEDULED this session - the silent gap found above** |
| public-or-not | DECISION with a TRIGGER (was: parked) |

## STEP 4 - verify

Re-grepped: zero optional-forever markers remain; every hit is a finalized exclusion, a
description, or a decision with a stated trigger. Every item raised anywhere this session has a
home in the plan's numbered order.
