# Next session start prompt

**Supersedes the 2026-08-08 version.** That version's Steps 1-4 and this file's Steps 1-6 were two
competing orderings; the 2026-08-09 meta-review merged them. **This is the single canonical
recommended order.** Step 1 of the old plan (the promise inventory) is DONE.

Paste the block below to start.

---

```
unbluff - STEP 1 of the v1.0 finish plan (the NEW step 1). Repo C:\Users\ammar\Downloads\unbluff.

=== STATE, verified live 2026-08-09 ===

HEAD 00fc9ba on main, = origin/main, 0 unpushed. Tree clean apart from docs/audits/.
run_selftests: 32/32 PASS. Integration 30/30 (ubuntu only). Mutation 138 entries / 30 units,
139 anchors all matching. v1.3.1 is the latest tag (56f8932); HEAD is one commit past it.

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
* The v1.3.1 ship gate ("no HIGH in the shipped hook path") is retired. Criteria 1-4 replace it.
* docs/V131_REVIEW_PLAN.md (2,338 lines - NOT 2,200) is HISTORY. **The collapse is CANCELLED.**
  It discharges no criterion, and CHANGELOG.md:56 stays true if the file keeps its phases. It
  gets a HISTORY header, not a rewrite. 40 of its 247 items must survive - see ledger section F.
* The v1.0 milestone ships as tag **v1.4.0**. `v1.0.0` has existed since 2026-07-13 (b8d3f9e);
  "v1.0" stays a milestone LABEL in prose and the CHANGELOG explains it.
* Claim DISPOSITION gets its own step and runs BEFORE any step that edits README/SKILL.md.

=== THE RECOMMENDED ORDER - the single canonical list ===

  [DONE 2026-08-09] Promise inventory. N=243 claims, 85 PROVEN, 158 UNPROVEN, 0 pending.
                    docs/audits/promise_inventory_2026-08-09.md

  STEP 1  Re-home what only exists inside V131_REVIEW_PLAN.md, and correct the record.
          - Lift the R1/R2 rule + its four-clause entry-point derivation into the ledger. It is
            the ONLY operational definition of "reachable by a user", and criterion 2 is stated
            in exactly those words.
          - Move the five CORRECTIONS blocks into the ledger. coverage_ledger_2026-08-08.md
            records 4 confirmed findings as BUILT naming "CORRECTIONS item N" as the carrier -
            the ledger points at them, it does not contain them.
          - Add the HISTORY header + "these five accounting systems must never be summed".
          No code. Half a session.  [criterion 2's definition; unblocks everything else]

  STEP 2  Make the platform evidence real.
          - Give the `integration` job the matrix the `selftest` job already has:
            [ubuntu-latest, macos-latest, windows-latest]. Same edit size as INT-WIN, closes
            criterion 4 instead of two thirds of it.
          - Make pre_push_gate's three `SELFTEST SKIP: sh unavailable` paths ASK THE BOX (resolve
            git's bundled sh.exe) and FAIL when neither is found. A fixture that finds no case
            must fail, not pass.
          - Fix CHANGELOG 1.1.1's false claim that the integration suite passes on all three
            platforms - it has never run anywhere but ubuntu.
          NOTE: there is no macOS MUTATION sweep either; say so rather than overstating.
          [criterion 4. Do this BEFORE step 5 - it converts all 35 platform-caveated PROVEN rows]

  STEP 3  The criterion-2 defect queue.
          - INSTALL-TAUTOLOGY (CRITICAL): install.py's partial-checkout guard globs the very
            directory it validates, so it can never detect a missing file. 9 of 25 hooks
            unguarded, 5 of them imported by production hooks.
          - ENC-1: 0 of 25 hooks reconfigure stdout. cp1252 + non-ASCII path = half-printed
            report then exit 0. Silent, not a visible crash.
          - PGG-PS: piped_gate_guard is registered matcher "Bash"; never fires for PowerShell.
          - SKILLDIR-DESTROY, FASTTEST-BLOCK, CA-SELFREF, --dry-run, settings.json backup.
          - The 42 open confirmed findings (NOT 5 - check_review_freshness masks 37 because a
            unit that is both STALE and has open findings is labelled only STALE).
          - Gate-ledger coverage: 4 of 5 gate tiers write no record at all.
          - Buy ONE INDEPENDENT adversarial pass over the R1 dispositions. Non-negotiable: the
            author's probe set and the author's blind spot are the same object.
          [criterion 2]

  STEP 4  Build criterion 3 for real.
          4a: a PAYLOAD-DRIVEN scorer. The existing machinery scores 0 of 16 REQUIRED_HOOKS -
              13 read sys.stdin and none expose slicing_offenders(), the only entrypoint
              score_corpus.py calls. "The corpus machinery already exists" was FALSE.
          4b: one corpus of ordinary correct work per input class.
          Fix FASTTEST-BLOCK first (step 3) - it is a false alarm that would be measured.
          Settle the denominator: the repo's own detectors say 25 / 24 / 22.
          [criterion 3. Largest unknown in the estimate - RE-ESTIMATE AFTER THIS LANDS]

  STEP 5  Disposition: one pass over all 243 rows into a MACHINE-READABLE claim ledger.
          Every row gets exactly one of KEEP-PROVEN / KEEP-BUILD-PROOF / DELETE /
          OUT-OF-SCOPE-INSTRUCTION, and the four counts are PRINTED BY THE TOOL and sum to 243.
          Every KEEP-BUILD-PROOF row gets a MUTATION anchor, not a text anchor - a freshness gate
          proves the sentence still exists, never that it is still true.
          Record BOTH denominators for the SKILL.md population question (~76 rows turn on it).
          Zero source files edited in this step - decisions only.
          [criterion 1, decision half + the only mechanism that keeps criterion 1 true]

  STEP 6  Execute the dispositions, write the WON'T-FIX section, cut v1.4.0.
          - Apply every DELETE and build every KEEP-BUILD-PROOF proof.
          - Document the two shipped hooks that appear ONLY in CHANGELOG - one of them blocks the
            user's Bash commands.
          - Fix install.py --help (it promises per-hook --only/--without; the flags are per-EVENT).
          - The WON'T-FIX section states the residual risks plainly: criterion 2 means "no defect
            reachable through the paths R1/R2 enumerates, as of this enumeration"; criterion 4 is
            proven on three clean CI images, not on machines; criterion 3's rate is published WITH
            its corpus provenance and never as "never fires"; nothing here proves a stranger can
            use it, and the feedback path is <named>.
          - CHANGELOG entry naming the four criteria and their evidence; annotated tag v1.4.0;
            confirm the CI badge is green ON the tagged commit.
          [criterion 1 edit half + the DoD's own closing clause + release mechanics]

Estimated 7 sessions from here. The old 3-4 was made before the population had ever been
measured and was wrong by ~2.5x. If a session ends with the estimate GROWN, say so explicitly
rather than quietly re-planning. Step 4's size is genuinely unknown - RE-ESTIMATE AFTER IT LANDS.

=== WORKING RULES - unchanged, all earned. NONE of these may be dropped ===

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

  docs/audits/coverage_ledger_2026-08-09.md - CURRENT BUILT / SCHEDULED / EXCLUDED state.
    Supersedes the 08-08 ledger. Sections A-D are the four criteria; J is the source-coverage gaps.
  docs/audits/promise_inventory_2026-08-09.md - the 243-row claim -> proof matrix.
  docs/audits/plan_audit_2026-08-09.md - the 7 plan issues. READ ITS CORRECTIONS BLOCK FIRST;
    the body carries superseded numbers on purpose, to preserve the record of the error.
  docs/audits/consistency_2026-08-09.md, meta_review_2026-08-09.md - the 2026-08-09 close ritual.
  unbluff-review-recovery\ - harvest_review.py, pair_verdicts.py, merge_runs.py, and
    final_adjudication.json (20 findings, 12 confirmed, 8 refuted). Recovers a Workflow's results
    from disk after a session ends, since resumeFromRunId is session-scoped.

=== AT CLOSE ===

Invoke the four audit skills (consistency-audit, completeness-audit, source-coverage,
meta-review) via the Skill tool and COMPLETE each procedure, including refreshing the coverage
ledger. On 2026-08-09 all four found something real - consistency found a live `[]` placeholder
and a tool self-reference defect, source-coverage found two unreconciled populations, and
meta-review found the gate ledger covers 1 of 5 tiers. This is not a formality.
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
