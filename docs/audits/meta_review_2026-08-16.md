# Meta-review - 2026-08-16/17 session

Run LAST, after consistency, completeness and source-coverage, and after the full sweep had
EXITED (a number read off a still-running producer is not a measurement).

## 1. Parked-but-unscheduled

Grep of the plan for `PARK|DEFER|TODO|OPTIONAL|later`: **zero** optional-forever markers. Every
open item has a numbered task: #3 silent-failure-hunter, #4 pre-push recorded-sweep gate, #5
`pinned_by`, #6 meta_audit budget, #7 criterion 1 (blocked on the user), #14 printed-vs-recorded,
#15 enforcing-mode verify, #16 residuals of #12/#13, #17 the 51-file class sweep.

## 2. Instance-only fixes - the durability check

Three fixes are still INSTANCE-only, i.e. the general mechanism does not exist yet:

| Fixed as an instance | Where it still lives | General mechanism owed |
|---|---|---|
| invocation-dependent `import gate_ledger` | `score_false_alarms.py` | a check that every file importing `gate_ledger` puts `tools/` on `sys.path` at module scope - task #17 |
| printed number != recorded number | `mutation_check.py` `executed` omits `unproven` | one helper computing the tally ONCE, returning the object that is both printed and recorded - task #14 |
| a floor living only in `selftest()` | unknown - never swept | task #17 class 4, explicitly recorded as NOT swept rather than as zero |

## 3. The controls I built this session, audited as adversarially as the code

This is the check that paid. **Two real defects, in my own new controls:**

**(a) `unrecorded_tiers()` makes a weaker claim than it appears to.** It verifies a
`gate_ledger.record(` call SITE EXISTS in the source. It does not verify the call is ever
REACHED under the mode the tier is registered with. `score_false_alarms` is the live proof: it
is declared in `RECORDING_TIERS`, the check passes, its `record()` sits in `main()`, and the
gate is registered `("--selftest",)` - so the tier records only when someone runs it enforcing
by hand, and its ledger row sat **45.2h stale while every gate was green**. Scheduled into task
#4(d) with the fix: combine it with `enforcing_mode_gaps()` so a tier declared as recording AND
registered `--selftest` must be re-registered or explicitly marked "records only when enforcing".

**(b) `GL-ATOMIC` was drafted and never landed.** The atomic write - serialise, temp file,
`os.replace` - is the most load-bearing change in `gate_ledger`, and it had **no pin at all**.
It is also the hardest of the four to pin, because truncate-then-write produces a correct file
on the happy path, so every other assertion passes against the defective version. FIXED during
this review: the selftest now INTERRUPTS the write (patching `prune` to raise) and asserts the
existing history survived; `GL-ATOMIC` was added and verified CAUGHT.

**Correction to a number I reported.** Before finding (b) I told the user "26 pinned". With
`GL-ATOMIC` missing, finding #16 was FIXED but UNPINNED, so the honest figure at that moment was
**25 pinned / 8 fixed-unpinned**. Adding the pin restores it to **26 / 7**. Recorded because the
overstatement was mine and the audit trail should show it, not just the corrected total.

**Still UNPINNED, all for one root cause** - `mutation_check` verifies every pin via
`<unit> --selftest`, so nothing in `main()` is reachable (task #15):
`ship_bar_gate`'s empty-population floor; `check_file_size`'s population floor and its
`CANNOT RUN` branch; `population()`'s git derivation; `load_factor`'s failure NOTE;
`hook_divergence_report`'s surfaces-but-zero-examined failure.

## 4. Missing / wrong - the GATE LEDGER, read not reconstructed

All **7 of 7** tiers fresh against the last source change: `run_selftests`, `integration`,
`false_alarm_scorer`, `mutation_sweep`, `mutation_sweep_filtered`, `ship_bar`, `file_size`.
Two were stale mid-session (`false_alarm_scorer` -45.2h, `integration` -0.4h) and were re-run
rather than assumed. The `false_alarm_scorer` staleness is what exposed defect 3(a) - a stale
row was the only visible symptom of a control that could not fire.

Full sweep after all fixes: **209 of 211 executed, 0 SURVIVED, 0 HARNESS ERROR, 0 unproven**,
2 posix-only proven on the ubuntu job, exit 0. Suite 38/38, integration 30/30, anchors 213
across 212 entries.

## 5. Improvements, ordered by value for next session

1. **#15 enforcing-mode verify in `mutation_check`** - unblocks SEVEN unpinned behaviours at
   once. Highest leverage item in the backlog.
2. **#17 the 51-file class sweep** - per tooling-discipline 7.1 this is the CHEAP high-yield
   target: 51 files no reviewer has ever opened, against classes with a known base rate
   (3 of 40 findings came from class 5 alone). Point the fan-out here, not at code just written.
3. **#16 residuals** - three findings under a green tick.
4. **#4 pre-push gate** + its 4(d) fix - the ledger is now durable enough to build on.
5. **#14 general printed-vs-recorded**, **#5 `pinned_by`**, **#3 silent-failure-hunter**.
6. **#7 criterion 1** - blocked on the user, and its estimate should be re-derived after the
   above, not before.

## 6. Mechanism health

Suite green, hooks green, one canonical order (the task ledger; `NEXT_SESSION_PROMPT.md`
refreshed to match and kept under 40 lines). No competing sequence blocks.

## 7. Anything reported as done that is not

- `#8` was reported complete with its residual filed as `#15` - accurate, and the completeness
  audit verified #15 covers both findings (#12, #22).
- `#12` and `#13` were reported complete while three findings were unfixed - caught by the
  completeness audit, filed as `#16`. **This is the one genuine over-report of the session.**
- "26 pinned" was overstated to 25 for the reasons in section 3. Corrected, and the pin added.
