# Next session start prompt

**Supersedes the 2026-07-31 version, which pointed at plan sections P11/P12. That work is done
and v1.3.1 is shipped.** Paste the block below to start.

---

```
unbluff - STEP 1 of the finish plan. Repo C:\Users\ammar\Downloads\unbluff.

=== STATE, all verified 2026-08-08 ===

HEAD fb7982f on main, = origin/main, 0 unpushed, tree clean. v1.3.1 is TAGGED and pushed, and CI
is GREEN on the tagged commit itself (14/14 jobs, 11 OS/Python combinations, both mutation
sweeps: 136 of 138 per platform, 2 posix-only, 0 unproven, 0 SURVIVED). Suite 32/32, integration
30/30, anchors 139 across 138 entries in 30 files.

=== THE GOAL ===

Finish unbluff into a v1.0 I am happy to share. It is primarily for MY use, but I publish it and
it must be genuinely good for other people. It is my #1 project, worked on alongside GHG Copilot.

=== DEFINITION OF DONE for v1.0 - agreed 2026-08-08. DO NOT WIDEN IT ===

  1. Every behavioural claim in README.md and skills/*/SKILL.md is TRUE and has a test proving
     it - or the claim is DELETED.
  2. No defect reachable by a user who installs it and uses it.
  3. Each hook's FALSE-ALARM rate on ordinary correct code is MEASURED and recorded. (This is
     the criterion that decides whether it is good for other people: a guard that fires on
     correct code gets switched off, which is worse than no guard.)
  4. install -> fire -> uninstall verified on Windows, macOS and Linux.

Anything not on that list is WON'T-FIX BY DESIGN and gets said so in the README.

=== CLOSED DECISIONS - do not reopen, do not re-litigate ===

* Guards that can be silently DISARMED BY EDITING UNBLUFF'S OWN SOURCE are WON'T-FIX. If someone
  edits it and breaks a guard, that is their fault. This DELETES AR-1..AR-11 and the 32 AR
  MEDIUM/LOW rows from the roadmap entirely. The ONLY way any of them comes back is if criterion
  1 finds a README claim that depends on it - in which case the choice is fix it or delete the
  claim.
* The v1.3.1 ship gate ("no HIGH in the shipped hook path") is retired; it did its job.
  Criteria 1-4 above replace it.
* The 2,200-line docs/V131_REVIEW_PLAN.md is HISTORY, not a live worklist. Read it for context,
  do not grow it. Step 3 collapses it.

=== THIS SESSION: STEP 1 - the promise inventory. The ONLY deliverable ===

Extract EVERY behavioural claim from README.md and the four skills/*/SKILL.md files. For each
claim, name the test, gate or selftest that proves it - or mark it UNPROVEN.

  - Print the DENOMINATOR: N claims found, M proven, K unproven. That number is the whole point:
    it converts the remaining work from open-ended into finite.
  - A claim is behavioural if it asserts what the software DOES ("blocks X", "fires on Y",
    "never Z", "runs at most weekly"). Prose about motivation is not a claim.
  - "Proven" means a specific named test/gate would FAIL if the claim became false. If you cannot
    name it, it is UNPROVEN. Do not credit a claim to a test that merely touches the same file.
  - Output: docs/audits/promise_inventory_2026-08-XX.md, a claim -> proof matrix.

DO NOT FIX ANYTHING THIS SESSION. The inventory IS the deliverable, and it defines the scope of
everything after it. Fixing while inventorying is how the denominator gets lost.

Good Workflow candidate (parallel extraction: README + 4 SKILL files, then one adjudicator).
ASK ME FOR A USAGE SNIP before any fan-out.

=== THEN, in later sessions ===

  Step 2: measure each hook's false-alarm rate on ordinary correct Python (criterion 3). The
          corpus machinery already exists - tests/cap_spelling_corpus.py, tools/score_corpus.py.
  Step 3: INT-WIN (mirror the ubuntu-only integration job on windows-latest - it hid two live
          defects), then collapse V131_REVIEW_PLAN.md into a short ROADMAP.md + GitHub issues.
  Step 4: cut v1.0, and write the WON'T-FIX rule into the README so the product's claims and its
          behaviour match.

Estimated 3-4 sessions total. If a session ends with the estimate GROWN, say so explicitly
rather than quietly re-planning.

=== WORKING RULES - unchanged, all earned ===

Regression test FIRST and watch it FAIL. Mutation-test every fix; SURVIVED means the test is
decorative. Treat every PRESCRIBED fix as a HYPOTHESIS - one scored 7 of 12 and failed on its own
headline example. Fixtures must ASK THE BOX rather than name a platform, and a fixture that finds
no case must FAIL rather than pass vacuously. Every timing claim interleaved against a control,
and check the control before believing the subject. Any cap, sample or top-N prints its
denominator. Never weaken an invariant to fit a failing scan - widen the check. Never edit code
while a gate is in flight. Use Edit, not heredocs, for anything containing backslashes, and
verify with repr(). Never pipe a gate into head/tail/grep or Select-Object - it destroys the exit
code. Prefer skills and agents over hand-rolled probes. Never let the author write the only
probe. A number read off a still-running producer is not a measurement, and silence from a
watcher is not a green result.

=== USEFUL POINTERS ===

  unbluff-review-recovery\ - harvest_review.py, pair_verdicts.py, merge_runs.py, and
    final_adjudication.json (20 findings, 12 confirmed, 8 refuted). Recovers a Workflow's results
    from disk after a session ends, since resumeFromRunId is session-scoped.
  docs/audits/coverage_ledger_2026-08-08.md - current BUILT / SCHEDULED / EXCLUDED state.
  docs/audits/consistency_2026-08-08.md - the last consistency pass.

=== AT CLOSE ===

Invoke the four audit skills (consistency-audit, completeness-audit, source-coverage,
meta-review) via the Skill tool and COMPLETE each procedure, including refreshing the coverage
ledger. In the last session each of the four found something real, so this is not a formality.
```

---

## One thing to watch

If step 1 returns a large `UNPROVEN` count, the instinct will be to start fixing immediately.
Resist it. The inventory is the scope document, and its value is being **complete** before
anything is touched - a partial inventory reads as a floor and you plan against a denominator
that is really larger.
