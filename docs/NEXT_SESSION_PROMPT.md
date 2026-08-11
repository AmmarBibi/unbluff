# Next session start prompt

**Supersedes the 2026-08-08 version.** That version's Steps 1-4 and this file's Steps 1-6 were two
competing orderings; the 2026-08-09 meta-review merged them. **This is the single canonical
recommended order.** Step 1 of the old plan (the promise inventory) is DONE.

Paste the block below to start.

---

```
unbluff - STEP 3 of the v1.0 finish plan, RESUMING mid-step.
Repo C:\Users\ammar\Downloads\unbluff.

=== STATE, verified live 2026-08-11 ===

HEAD 367ace4 on main, PUSHED, CI GREEN (run 31531141633, 16 jobs, 0 failed).
run_selftests 33/33 exit 0 on an IDLE machine AND on a pytest-LESS interpreter.
Integration 30/30. Criterion 4 CLOSED. Mutation harness 162 entries, 163 anchors.
CI full sweep 160 of 162 executed, 0 SURVIVED, 2 not-runnable-here.
Normal sweep runtime is ~30 MIN (measured 1770s and 1960s); far past that is a HANG,
not a slow run - one sat at 48h with 2.2s of CPU and a 0-byte file.

FIRST THING TO DO ON RESUME:
  1. `git status --porcelain` and `git log --oneline -8`. Expect clean at 367ace4.
  2. `gh run list --limit 3`. Expect success on 367ace4. CONFIRM before trusting the above.
  3. Run the suite on an IDLE machine. A suite run alongside other work false-fails on
     hook_health_check and meta_audit_on_stop - see SELFTEST-BUDGET-FLAKE below. "33/33" is
     not evidence unless the box was idle.
  4. NEW, and it is the cheapest lesson here: also run the suite AND the mutation harness
     under a `venv --without-pip` interpreter. Running the SUITE deprived proves only
     PORTABILITY; running the MUTATION HARNESS deprived proves the pins still BITE there.
     Two mutations shipped DECORATIVE on 2026-08-11 because only the first was done.
     That is DEPRIVED-CI, scheduled in step 3.

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
* docs/V131_REVIEW_PLAN.md (2,368 lines - re-measured 2026-08-11) is HISTORY. **The collapse is CANCELLED.**
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

  [DONE 2026-08-09] STEP 2. Platform evidence is real. **CRITERION 4 IS CLOSED.**
                    HEAD `eab22f0`; CI run 31304861194 green, 16 jobs, `integration` on
                    ubuntu + macos + windows. It was expected to go RED and did not - no fix
                    was required on any platform, so the unpriced part of step 2 cost nothing.
                    pre_push_gate's three sh paths now resolve a shell and FAIL when none is
                    found (was 0 of 3 sites executing while the suite printed SELFTEST OK and
                    exited 0). CHANGELOG 1.1.1 corrected in place; two README claims that the
                    matrix falsified repaired in the same commit. INT-MUT unblocked - its
                    "blocked on a mechanism" premise was refuted by measurement - and given its
                    first 2 mutations. `unit_path` fixed so repo-ROOT files are mutable at all.
                    Full detail + everything it surfaced: ledger sections D, E1, J2, L.

  STEP 3  The criterion-2 defect queue. IN PROGRESS - two items closed 2026-08-09.
          [DONE] INSTALL-TAUTOLOGY (CRITICAL). The guard globbed hooks/*.py into its required
            set then asserted those files exist - the same statement twice, so real coverage
            was the hardcoded floor alone: 16 of 25, 9 unguarded, 5 imported by production
            hooks. Roster is now the AST IMPORT CLOSURE of the wired entry points. 16 of 25
            -> 25 of 25 detected. install.py gained its FIRST --selftest and is registered as
            the `install-guard` gate (suite 32 -> 33). Pinned by IT-1/IT-2. Ledger section N.
          [DONE 08-11] The optional-import regression ENTRY-GUARD shipped: it turned ALL 16
            CI jobs red. find_spec('docx') returns None on a runner without python-docx, so
            the closure reported consistency-audit/scripts/docx.py as a missing LOCAL file -
            it invented three files that never existed. Fixed: an import whose enclosing try
            catches ImportError is optional BY DEFINITION. Pinned OPT-1. It passed locally
            ONLY because this box has python-docx/PyMuPDF/pdfminer installed.
          [DONE 08-11] SKILLDIR-DESTROY (HIGH, user DATA LOSS). Two paths: install merged
            over a user's pre-existing same-named skill; uninstall rmtree'd the WHOLE dir, so
            uninstalling unbluff deleted a skill that predated it, silently. Fixed with a
            provenance manifest, following install()'s existing refuse-foreign-hook rule.
            5 user-data cases incl. the reverse direction. Pinned SD-1/SD-2.
          [NEW, SCHEDULED] SELFTEST-BUDGET-FLAKE - selftest_budget asserts a wall-clock
            duration with NO control for load. Under load hook_health_check (10.81s vs
            10.00s) and meta_audit_on_stop (19.63s vs 17.50s) FAIL; both pass standalone and
            the suite is 33/33 idle. Do not just loosen it - a selftest over its share of the
            25s weekly cap IS reported to users as ERRORED. The same output says the gate
            covers 3 of 24 hooks and is self-declared never-adversarially-reviewed.
          [NEW, SCHEDULED] MUT-HANG - the sweep can hang forever with no timeout, no
            heartbeat, no output. One sat at 48h with 2.2s of CPU and a 0-byte file. Normal
            is ~30 min. Fix with MUT-CONC: watchdog + progress printed as it goes.
          [NEW, SCHEDULED] close_skills_guard verifies INVOCATION, not COMPLETION. It
            correctly blocked three premature closes, but cannot see a skill that was
            invoked and then half-run - which happened, to all FOUR skills, and was caught
            by the user asking rather than by any gate. The repo's own defect class turned
            on its own close ritual: a check that confirms the ritual STARTED and reports
            that as the ritual HAPPENING. Beware the obvious fix - having each skill
            self-report completion is the same defect one level down. Ledger N2.
          [DONE] ENTRY-GUARD, fixed WITH it as K3 required. install_skill() warned and
            CONTINUED on a missing skill dir, so install exited 0 and close_skills_guard - a
            WIRED hook - then blocked every close demanding a skill the user never got.
            Derived from what a SKILL.md TELLS THE USER TO RUN plus its import closure.
            Pinned by EG-1/EG-2. One shared _import_closure serves both rosters.
          [DONE 08-11] FASTTEST-BLOCK (HIGH). MEASURED through the real entry point, 10 repo
            shapes: SEVEN hard-blocked a turn end with nothing wrong - `tests/` alone was
            taken as proof of a pytest project, and `tests/` is Cargo's own integration-test
            dir, so every Rust repo blocked every turn end AND every push (pre_push_gate
            shares detect()). Fixed in two halves: detection needs real pytest evidence AND
            an importable pytest; containment maps pytest rc 4/5 to "could not answer", not
            "you failed". Pinned FTB-1/1b/2/3/4/5/6, 7 of 7 CAUGHT on a pytest-PRESENT and a
            pytest-LESS interpreter. CI green on `367ace4`, 16 jobs. Ledger N0.
            LIMIT: author wrote the fix and its only probe - "12 shapes passed", NOT "no
            false alarm remains". Independent pass still owed.
          - ENC-1: 0 of 25 hooks reconfigure stdout. cp1252 + non-ASCII path = half-printed
            report then exit 0. Silent, not a visible crash.
          - PGG-PS: piped_gate_guard is registered matcher "Bash"; never fires for PowerShell.
          - CA-SELFREF (now THIRD instance and SELF-PROPAGATING: each time the defect is
            documented, the documentation becomes a new instance), --dry-run, settings.json
            backup.
          - CAP-FP-1 (NEW 08-11): cap_shapes false-positives on a COUNTER bound in a
            BOOL-returning function - its own clauses 1 and 2 exclude both. Measured with
            controls both directions. V1.4-BACKLOG by R1/R2 (R1 yes, R2 no), so
            developer-facing, NOT a criterion-3 user-facing false alarm. Held by a
            liveness-audited BOUND_EXEMPTIONS entry that self-reports DEAD when fixed.
          - SELFTEST-BUDGET-FTOS (NEW 08-11): fast_test_on_stop's selftest is at 15.8s of a
            25s cap it cannot see, and is one of the 21 of 24 hooks that do NOT self-budget.
            Same mechanism as SELFTEST-BUDGET-FLAKE; fix them together.
          - The 42 open confirmed findings (NOT 5 - check_review_freshness masks 37 because a
            unit that is both STALE and has open findings is labelled only STALE).
          - Gate-ledger coverage: 4 of 5 gate tiers write no record at all.
          - Buy ONE INDEPENDENT adversarial pass over the R1 dispositions. Non-negotiable: the
            author's probe set and the author's blind spot are the same object. **Step 2's fix
            is now also in scope for this pass** - it changed a CHECKING INSTRUMENT and its
            author wrote its only probe.
          --- ADDED BY STEP 2's CLOSE RITUAL, 2026-08-09 (ledger E1 / J2 / L) ---
          - INT-MUT: 2 of 30 integration scenario-groups are mutation-pinned. Close the rest.
          - 16 of 47 gate-able .py files carry ZERO mutations; 11 were in NO ledger state.
            Load-bearing first: selftest_budget, fast_test_on_stop_selftest,
            skills/consistency-audit/scripts/sources.py (SHIPPED to users), check_python_floor,
            check_skill_deps, run_selftests.
          - The TWIN ROSTER of step 2's defect: 9 more vacuous `SELFTEST SKIP` sites in 4 files.
            MEASURED LATENT, not live - 0 fired in a full run; they key on git, which is always
            present. Scheduled because the sh sites were assumed harmless on identical reasoning.
          - `_SH_SITES_REQUIRED` is a DECLARED roster, not a derived one - a 4th delegation site
            that forgets to register is invisible. Same shape as INSTALL-TAUTOLOGY/ENTRY-GUARD.
          - The 800-line rule is enforced by NOTHING. Over today: pre_push_gate_selftest.py 866
            (step 2 pushed it over), mutation_check.py 1033. Build the GATE, then split.
          --- FROM THE INDEPENDENT REVIEW wf_feb7202e-8fe (24 found / 24 adjudicated / 14
              confirmed). Its 3 defects in step 2's own code are FIXED; these are the rest ---
          - `_child()` runs the SELFTEST module, not the gate (HIGH). Check 14 is WHOLLY
            decorative - proven by applying mutation #10 and still getting SELFTEST OK. Also:
            mutation #10's in-code "the twin is covered" claim is false, repointing _child is
            NOT sufficient (a traceback exits 1, which the predicate accepts), and main()'s
            fail-open wrapper is pinned by nothing.
          - The git-ancestor-walk branch of _resolve_sh executes on NO CI runner - windows-latest
            has `sh` on PATH. Step 2's headline code path is exercised on one machine only.
            Needs a fixture that hides `sh` and asserts the git branch resolves.
          - mutation_check counts HARNESS ERRORs as "executed", and has NO concurrency lock
            (MUT-CONC). Its baseline guard is the only thing that stopped 11 mutations scoring
            CAUGHT for an unrelated reason.
          - `main` is unprotected, zero rulesets: a red CI job blocks nothing. Criterion 4's
            evidence is produced but not ENFORCED.
          - The `exit 7` probe's discrimination is unpinned - needs an injectable runner.
          [criterion 2]

  STEP 4  Build criterion 3 for real.
          4a: a PAYLOAD-DRIVEN scorer. The existing machinery scores 0 of 16 REQUIRED_HOOKS -
              13 read sys.stdin and none expose slicing_offenders(), the only entrypoint
              score_corpus.py calls. "The corpus machinery already exists" was FALSE.
          4b: one corpus of ordinary correct work per input class.
          FASTTEST-BLOCK is DONE (step 3, 2026-08-11) - that false alarm is out of the corpus.
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

**Estimate: 6 sessions remaining, and THE ESTIMATE HAS GROWN - saying so explicitly, as the rule
requires.** Step 2 began with 6 remaining and completed a whole step, so a pure countdown would
say 5. It is still 6 because step 2's close ritual added five item-clusters to step 3 (INT-MUT's
remaining 28 scenario-groups, 16 zero-mutation files, the 9-site twin roster, the declared sh
roster, the unenforced 800-line rule). Step 2 itself came in UNDER budget - the integration
matrix was expected to go red and did not - but step 3 grew by more than step 2 saved. The
growth is in the DISCOVERED population, not in the work done: none of it was known before the
close ritual looked. Step 4's size is still genuinely unknown - RE-ESTIMATE AFTER IT LANDS.

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

Invoke the four audit skills via the Skill tool IN THIS ORDER - consistency-audit,
completeness-audit, source-coverage, then **meta-review LAST** - and COMPLETE each procedure,
including refreshing the coverage ledger. The order is not cosmetic: on 2026-08-11 meta-review
was run FIRST and therefore never saw MUT-HANG, a finding the later three produced, even though
meta-review is the synthesising pass whose job is to weigh it.

COMPLETE means every step, not just the invocation. Also on 2026-08-11 all four were invoked and
three were only half-run (the consistency script skipped for a targeted derivation, the
soft-defer sweep skipped, meta-review checks 1 and 5 skipped). `close_skills_guard` did not
catch it - it verifies INVOCATION, not COMPLETION - and it was found only because a human asked.
Running the skipped steps afterwards produced two new findings (ledger N2). On 2026-08-09 all four found something real - consistency found a live `[]` placeholder
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
