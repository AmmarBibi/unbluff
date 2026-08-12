# Meta-review - 2026-08-12 (close ritual, pass 4 of 4 - the synthesising pass)

Run **LAST**, so it sees what the other three produced. All six checks.

## Check 1 - parked-but-unscheduled: 4 hits, 0 genuine
All four are prose about already-DONE items or the record of a previous ritual. Cross-checked
against pass 2, which independently found the one genuinely unhomed item (the rc-3 decision).

## Check 2 - instance vs mechanism: THE finding

| this session produced | durable? |
|---|---|
| five **anchor drifts** | **Yes** - `check_mutation_anchors` caught all five, in seconds, every time |
| hollow-pin **modes 1-4** | **Yes** - the harness scores an unplaceable or unfalsifiable mutation as SURVIVED |
| hollow-pin **mode 5** | **NO - and this is the gap** |
| 16 of 24 findings closed | 8 remain, all SCHEDULED with severities |

**Mode 5** - a mutation measured against the wrong verify target - is detected by nothing.
`WT-1` was applied and checked against a module with no `--selftest`, so it verified nothing and
reported SURVIVED **while the probe was working perfectly**. I found it only by reproducing the
mutation by hand and noticing the harness disagreed with me.

Right now the five-mode list is a checklist in this ledger: prose, which is advisory.
**Scheduled `VERIFY-TARGET-GATE`** - assert every `MUTATIONS` entry's verify target actually
exposes `--selftest`. ~15 lines, belongs in `check_mutation_anchors` (already walks every entry,
already runs in seconds, already the gate with the best catch record here).

## Check 3 - optimization
**Five files over the 800-line rule, measured:** `mutation_check.py` 1263,
`pre_push_gate_selftest.py` 1109, `fast_test_on_stop_selftest.py` 1003, `install.py` 864,
`fast_test_on_stop.py` 832. It was three; four of the five grew **today**, all by me. The
prescription stands - build the line-count GATE, then split - and the trend is now the
argument: a rule enforced by nothing degrades monotonically while every individual addition
looks justified.

## Check 4 - the GATE LEDGER, read not reconstructed
`gate_runs.json`: **200 entries, `{'run_selftests': 200}`**, newest `2026-08-12T17:07:36Z`.
Today ran the mutation harness ~15 times (including the two pytest-less runs that are the only
proof `FTB-1`/`FTB-6` bite), the integration suite, and **seven CI rounds**. All wrote nothing.
**Third consecutive day this finding is re-demonstrated by the session's own most load-bearing
evidence.** Priority stays raised; it remains the enabling change for every future "what
actually proved this?" question.

## Check 5 - improvements (run in full)
1. **`VERIFY-TARGET-GATE`** (check 2) - closes hollow-pin mode 5 mechanically. **Scheduled.**
2. **Line-count gate** - five files over and climbing. **Scheduled** (existing row, evidence updated).
3. **Gate-ledger writes from all five tiers** - **Scheduled**, priority raised a second time.
4. **Not scheduled, offered:** the audit-report directory now holds eight files from two days.
   Rule 7.3's accretion shape. A retention policy is the user's call, and inventing one unasked
   is the scope creep the plan warns against.

## Check 6 - mechanism health
- **`close_skills_guard` fired correctly on its own author** during yesterday's ritual, and
  correctly stayed quiet today once all four skills had run.
- **`check_mutation_anchors` earned its place five times** this session.
- `hook_health_check` 30 commands verified; suite **33/33** on a pytest-present AND a
  pytest-less interpreter; integration **30/30**; CI **green, 17 jobs**; full sweep **0
  SURVIVED, 0 unproven**.
- **Exactly one canonical order** - `NEXT_SESSION_PROMPT.md`, refreshed in this close.

## Synthesis

Yesterday's tally was "3 of 4 problems were in the checking instruments". Today's is starker and
more useful: **every defect found after the adversarial pass landed was in an instrument** - the
budget assertion with no control, a harness that could not explain its own baseline failure, a
scratch tree missing the files its gates read, five drifted anchors, and a mutation pointed at
the wrong target. The product code was fixed early and stayed fixed.

The through-line worth carrying into step 4: **the instruments fail more often than the code, and
they fail SILENTLY, which is why every one of them needs a denominator and a third state.** Step
4's false-alarm scorer is itself an instrument, and on this base rate its review is part of
writing it - not a phase afterwards.
