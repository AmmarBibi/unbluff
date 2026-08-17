# Next session start prompt

**Supersedes the 2026-08-08 version.** That version's Steps 1-4 and this file's Steps 1-6 were two
competing orderings; the 2026-08-09 meta-review merged them. **This is the single canonical
recommended order.** Step 1 of the old plan (the promise inventory) is DONE.

Paste the block below to start.

---

```
unbluff - v1.0 finish plan. Repo C:\Users\ammar\Downloads\unbluff.

STATE (verify, do not trust): tree clean. Suite 38/38, integration 30/30, anchors 213/212, FULL
sweep 209 of 211 / 0 SURVIVED / 0 HARNESS ERROR, 7 of 7 ledger tiers fresh. Criteria 2/3/4 done
or gated; criterion 1 untouched. Detail: docs/audits/*_2026-08-16.md.

FIRST THREE: git status --porcelain && git log --oneline -5
  gh run list --limit 3        # count jobs BY CONCLUSION - an in-progress job has none
  python tools/gate_ledger.py  # counts ONLY; there is still no "when" - that is task #4(a)

08-16/17 review wf_f63b9ccf-816 (46 agents; 41 produced / 41 adjudicated / 40 confirmed): 33
fixed, 26 pinned by a mutation verified to DIE, 7 scheduled, 0 dropped. The CRITICAL was real -
nothing read AUX_GATES' argv, and 08-14's defect reproduced on a clean clone in ONE TOKEN.

THE ORDER - highest leverage first, and this is the single canonical list:
  1. #15 enforcing-mode verify in mutation_check. Every pin verifies via `<unit> --selftest`,
     so nothing in main() is reachable. This ONE fix unblocks SEVEN unpinned behaviours.
  2. #17 sweep the 51 files no reviewer has opened - cheap, high-yield (7.1). MEASURED: class
     5 = 106 excepts, class 6 = 88 rosters, class 4 not swept. One live instance confirmed.
  3. #16 three findings under a green tick: budget_coverage's roster, the ratchet that does
     not self-tighten, INCONCLUSIVE with no consumer.
  4. #4 pre-push gate: a RECORDED sweep newer than the last source change; incl. 4(d),
     unrecorded_tiers() checks a call site EXISTS, not that it is REACHED.
  5. #14 printed==recorded, #5 pinned_by, #3 silent-failure-hunter, #6 meta_audit budget.
  6. #7 criterion 1 - DECIDE ITS SHAPE FIRST; re-derive the estimate after 1-5, not before.

TWO DECISIONS OWED BY ME, NOT CLAUDE:
  * Criterion 1 is 243 rows / 158 UNPROVEN. Is proving every README claim worth 3-4 sessions?
  * Push policy: HOLD on any non-zero sweep exit (recommended and adopted).
RULES THAT COST SOMETHING TO LEARN:
  DERIVE numbers, never assert them - and STAMP THE INSTANT (three of mine went stale in hours).
  A gate registered in the wrong MODE cannot fail. Check argv, not the name.
  A control that checks a call site EXISTS has not checked that it is REACHED. And a pin you
    DRAFTED is not one that LANDED - check the table, not your memory (GL-ATOMIC).
  MEASURE platform semantics. A wrapper's rc is not the gate's; a number off a running producer
    is not a measurement. Expect the defect in the INSTRUMENT, and never let its author write
    the only probe. KEEP THIS UNDER ~40 LINES.

AT CLOSE: consistency -> completeness -> source-coverage -> meta-review LAST, each COMPLETED. On
08-16 all four found defects in MY OWN work, two in controls built that same session.
```

---

## One thing to watch

The 2026-08-08 version warned: *if step 1 returns a large UNPROVEN count, the instinct will be to
start fixing immediately - resist it.* That warning held; the inventory is complete and nothing
was fixed while it was being built.

**The 2026-08-09 successor warning:** the plan audit published false numbers because it read the
inventory **while the inventory was still being regenerated**. Every derived figure it quoted
came from an intermediate state. The rule already existed - *a number read off a still-running
producer is not a measurement* - and the audit that was checking compliance with the rules broke
it. When steps 2-6 produce numbers, re-read the producer **after it has exited**, or cite nothing.
