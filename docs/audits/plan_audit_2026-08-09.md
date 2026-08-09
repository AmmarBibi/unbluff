# unbluff v1.0 - FINISH PLAN AUDIT

**Date:** 2026-08-09  **Repo HEAD:** `00fc9ba` (clean, `== origin/main`)  
**Question:** does the v1.0 finish plan, executed exactly as written, reach its own
Definition of Done (criteria 1-4)?  
**Answer: no.** Four CRITICAL issues each independently block a criterion.

> Scope was Steps 2, 3 and 4. The four DoD criteria and the CLOSED DECISIONS were given to
> every agent as **fixed inputs** - an agent could report a criterion UNREACHABLE, but not
> that it was the wrong criterion, and any finding reopening a closed decision was to be
> discarded. Nothing here proposes widening the DoD.

---

## CORRECTIONS - READ BEFORE ANY NUMBER IN THIS DOCUMENT

An independent sweep on 2026-08-09 audited this document and found the numbers below to be
WRONG. The four CRITICAL findings survive re-attack; their **evidence** does not. Root cause,
stated plainly: this audit was written against `promise_inventory_2026-08-09.md` **while that
file was still being regenerated**. It read the intermediate state (78 PROVEN / 45 pending) and
published figures derived from it. That is this project's own rule - *a number read off a
still-running producer is not a measurement* - broken by the audit that was checking compliance
with it.

| stated here | truth at HEAD `00fc9ba` |
|---|---|
| "78 rows marked `**PROVEN**`" | **85** |
| "45 rows marked `_PENDING_` (grep counts)" | **0** - the string `PENDING` does not occur in the inventory |
| "45 claims that carry no verdict at all" | **0** - all 243 rows are adjudicated (85 + 158 = 243) |
| "120 UNPROVEN" | **158** |
| "165 claim dispositions" (P6) / "all 243" (P2 correction) / "158" (heading) | **158 of 243**, one figure, everywhere |
| `MX-18`/`MX-19`/`MX-20` cited as unadjudicated | all three are **PROVEN** - delete the example |
| "Plan assertions verified against the repo \| 82" | **not a coverage figure.** 82 is a sum of verification *events* across 5 lenses with overlap uncounted. The plan file contains **86** falsifiable assertions; this audit's declared scope covers at most **21** of them. |
| "`V131_REVIEW_PLAN.md` is 2,200 lines" (quoting the plan) | **2,338** |
| reliability headline "and `{}` were killed" | placeholder never filled - the kill count was **0 of 48** |

Two further defects in this document: its citation for "the plan's Step list contains no
fix-or-delete task" points at `finish_plan.md`, a **scratch transcription that is not in the
repo** - the correct citation is `docs/NEXT_SESSION_PROMPT.md` lines 66-76; and its quote of
Step 4 is truncated in a way that removes a clause bearing on its own finding.

Finally, P4 is **understated, not overstated**: it reports 5 open confirmed findings because
that is what `tools/check_review_freshness.py` prints. Parsing `docs/audits/review_runs.json`
directly, run `wf_1b621b24-7ef` carries **42 open confirmed findings across 12 units**. The
other 37 are masked because a unit that is both STALE and has open findings is labelled only
STALE.

---

## HEADLINE

| | |
|---|---|
| Role lenses | 5 (senior engineer, release engineer, QA/test architect, OSS product owner, adversarial critic) |
| Plan assertions verified against the repo | 82 |
| Findings raised | 49 |
| Findings with a refuter verdict | 48 |
| Distinct issues after clustering | **7** |
| CRITICAL issues | **4** |

### Reliability caveat - read this before trusting the numbers

**48 of 49 findings were attacked by a refuter and 0 were killed.** A zero kill rate is not by itself evidence the findings are sound - it is equally consistent with lax refuters. Two independent controls were applied:

1. Five role lenses converged on the same four core issues **without seeing each other's**
   **output**. Independent convergence is the strongest signal in this report.
2. The four sharpest factual claims were re-verified by hand, outside the agent fleet:

| claim | verified |
|---|---|
| `v1.0.0` tag already exists | YES - `v1.0.0  2026-07-13  b8d3f9e`; `git tag v1.0.0` would fail |
| `piped_gate_guard` registered `matcher: "Bash"` | YES - confirmed in `install.py` |
| No hook reconfigures stdout | YES - **0 of 25** hooks |
| `V131_REVIEW_PLAN.md` is 2,200 lines | **NO - it is 2,338**; the plan's own number is stale |

**1 finding was never adjudicated.** The join pairs refuter verdicts to
findings by exact title, and one title did not round-trip, so it auto-survived. It is NOT
refuter-confirmed and is marked as such below. An unadjudicated finding is an OPEN finding,
not an absent one.

> `[HIGH] 'Each hook' in criterion 3 has three live denominators in the repo, and the plan carries two of them as facts` - raised by Senior software engineer, no verdict.

---

## THE ISSUES

### P1 · CRITICAL · Criterion 4 is unreachable: macOS integration is never scheduled

**Found independently by 5 of 5 role lenses** (Adversarial, Product, QA, Release, Senior) · 7 finding(s) · target: `criterion 4 / Step 3 (INT-WIN)`

**What goes wrong**

tests/test_integration.py is the only artefact that performs install -> fire -> uninstall, and it is invoked by exactly one CI job, which is ubuntu-only. run_selftests.py does not call it, so the 3-OS `selftest` matrix does not cover it either. Step 3 adds windows-latest and stops. After Step 4 completes exactly as written, macOS install/uninstall has been executed nowhere, and criterion 4 is 2/3 met while the README will say v1.0.

**Evidence**

> .github/workflows/selftest.yml lines 97-111: job `integration`, `runs-on: ubuntu-latest`, single step `python tests/test_integration.py`. `grep -n "test_integration" run_selftests.py` returns no invocation - only comment text at line 57. proof_surface.md line 68 records the same: 'CI runs this on ubuntu ONLY'.

**Smallest correction that does not widen the DoD**

Change Step 3's INT-WIN from 'mirror the integration job on windows-latest' to 'give the existing integration job the same os matrix the selftest job already uses: [ubuntu-latest, macos-latest, windows-latest]'. Same edit size, and it closes criterion 4 instead of half of it.

<details><summary>Corroborating findings from the other lenses</summary>

- *Release engineer* — Criterion 4 is unreachable: Step 3 mirrors integration on Windows only, macOS is never scheduled
- *QA / test architect* — Criterion 4 names three platforms; Step 3 schedules only Windows - macOS integration is never built
- *Product owner for an OSS release* — Criterion 4 names three platforms; no step adds the macOS leg, so the DoD is unreachable as written
- *Adversarial completeness critic* — Criterion 4 names macOS; no step in the plan ever puts the integration test on a Mac
- *Product owner for an OSS release* — Install and uninstall destroy user-owned skill directories, and the integration test has no skills analogue of A3/G3 - so INT-WIN/INT-MAC will mirror the blind spot
- *Adversarial completeness critic* — Step 3, executed literally, falsifies README claims that Step 1 recorded as true - and no gate catches it

</details>

### P2 · CRITICAL · Criterion 1 has no owning step - 158 claim dispositions belong to nobody

**Found independently by 5 of 5 role lenses** (Adversarial, Product, QA, Release, Senior) · 14 finding(s) · target: `criterion 1 / Step 4 (and the gap between Steps 1 and 2)`

**What goes wrong**

Criterion 1 requires every behavioural claim to be either PROVEN by a named test or DELETED. Step 1 produced the decision list; Steps 2, 3 and 4 contain no task that executes a single one of those decisions. Step 2 is measurement (criterion 3), Step 3 is a CI job plus a doc collapse, Step 4 is 'cut v1.0, and write the WON'T-FIX rule into the README' - and that rule only disposes of source-editing disarms, not of claims like RM-05 ('install.py --dry-run writes no files') or RM-06 ('copies settings.json to a backup first'). Executed literally, v1.0 ships with 120 untested behavioural promises and 45 claims that carry no verdict at all, including the exit-code contracts MX-18/MX-19/MX-20 (rc 2) that make the whole suite non-inert.

**Evidence**

> docs/audits/promise_inventory_2026-08-09.md: 78 rows marked `**PROVEN**`, 45 rows marked `_PENDING_` (grep counts). Its own section 'WHAT THE UNPROVEN CLAIMS CLUSTER INTO' at line 405 says 'This is the scope of Steps 2-4' and then has an EMPTY body - the appendix starts at line 410. The plan's Step list (finish_plan.md lines 38-45) contains no fix-or-delete task.

**Smallest correction that does not widen the DoD**

Split Step 4 into 4a and 4b before 4b runs: 4a = adjudicate the 45 PENDING rows and execute the fix-or-delete decision for all 243, recording the decision and the naming artefact per row in the inventory; 4b = cut v1.0. This schedules work criterion 1 already demands; it does not widen it. Per the plan's own rule, state that the 3-4 session estimate has grown.

<details><summary>Corroborating findings from the other lenses</summary>

- *Senior software engineer* — Criterion 2 has no owning step, and two live user-reachable defects the closed decisions do not dispose of are still open at HEAD
- *Release engineer* — Criterion 1 has no remediation step and no CI job that proves it - the tag ships ~120 unproven claims
- *QA / test architect* — Criterion 1 has no owning step: 120 UNPROVEN + 45 unadjudicated claims are never disposed of by Steps 2, 3 or 4
- *Product owner for an OSS release* — No step performs criterion 1's fix-or-delete work, and Step 1 is marked DONE while 45 claims are still unadjudicated
- *Adversarial completeness critic* — No step owns criterion 1's actual remediation - the 120 UNPROVEN claims have no home
- *Product owner for an OSS release* — Step 4 rewrites the README after the only claim check, and the README's own counts already drift undetected
- *Product owner for an OSS release* — The README omits two shipped hooks - one of them blocks the user's Bash commands - so a delete-the-unprovable pass makes it more misleading, not less
- *Senior software engineer* — Criterion 3's recorded numbers land in exactly the 'a stated NUMBER nothing checks' class criterion 1 forbids, and they are written after the only inventory
- *QA / test architect* — Step 1's inventory has no freshness mechanism, and Step 4 is the first edit that falsifies it
- *QA / test architect* — Criterion 2 has no owning step and no bounding procedure, so it can only be declared met by assertion
- *Product owner for an OSS release* — Criterion 1's population is undefined for skills/*/SKILL.md, and a literal prove-or-delete pass guts the skills
- *Adversarial completeness critic* — Step 1 is marked DONE with 45 of 243 claims never adjudicated, and its cluster table - "the scope of Steps 2-4" - is empty in the delivered artefact
- *Product owner for an OSS release* — The CLOSED DECISION defines a re-entry trigger for the deleted AR rows and no step ever evaluates it

</details>

### P3 · CRITICAL · Step 2's premise is false - the named corpus machinery cannot score any user-facing hook

**Found independently by 5 of 5 role lenses** (Adversarial, Product, QA, Release, Senior) · 14 finding(s) · target: `Step 2 (criterion 3)`

**What goes wrong**

Step 2 is sized as 'run the machinery that already exists'. That machinery is a single-purpose cap-detector grader: tools/score_corpus.py calls `guard.slicing_offenders(hooks_dir)` and nothing else, and tests/cap_spelling_corpus.py entries are Python modules planted on disk. The one covered unit, hooks/capped_report.py, is not a user-facing guard at all - `slicing_offenders` scans unbluff's OWN hooks/ directory for uncapped slices, and capped_report is an imported render/keep helper, not a wired hook. Every guard whose false-alarm rate criterion 3 actually cares about reads a Claude Code event payload on stdin: rate_prompt (a prompt string), show_your_proof (a transcript), piped_gate_guard (a Bash command string), plan_defer_guard / numbers_match_on_write / timing_claim_guard (edited-file text), memory_hygiene_guard (memory files). None of them expose `slicing_offenders`, none of them consume 'ordinary correct Python', and no driver exists that feeds a hook a payload and records fired/quiet. Step 2 as written is 'build a second scorer, plus one corpus per input class, to the repo's own corpus discipline (append-only, negative controls, contradiction detection, printed ceiling)' - the same order of work as Step 1, not its tail.

**Evidence**

> tools/score_corpus.py line 44: `return bool(guard.slicing_offenders(hooks_dir))`. tools/no_regression.py line 65-67: `PROBE_ENTRYPOINTS` contains one family, `cap_detector`. tests/noregress_registry.py: REGISTRY has exactly one key, `hooks/capped_report.py`. hooks/capped_report.py docstring lines 19-20: the sweep exists to scan hooks/ for a hook that grew its own cap. install.py REQUIRED_HOOKS (lines 57-64) does not list capped_report. Verified by direct read that 8 of 11 sampled hooks take `sys.stdin`, and 3 (cap_shapes, cap_types, capped_report) do not.

**Smallest correction that does not widen the DoD**

Rewrite Step 2 as two ordered sub-steps and drop the 'already exists' framing: 2a = one payload-driven scorer that feeds a hook its real stdin event and records fired/quiet, reusing score_corpus's denominator/ceiling/contradiction code; 2b = one 'ordinary correct' corpus per INPUT CLASS (prompt, transcript, edited-file text, shell command, Python source), not per hook. Then restate the session estimate.

<details><summary>Corroborating findings from the other lenses</summary>

- *QA / test architect* — Step 2's stated machinery can score exactly one module, and that module is not one of the installed hooks - and 'ordinary correct Python' is the wrong input for most of them
- *Adversarial completeness critic* — Step 2's stated premise is false: the existing corpus machinery cannot score any hook that fires at a user
- *Senior software engineer* — 'Each hook' in criterion 3 has three live denominators in the repo, and the plan carries two of them as facts **[NO VERDICT]**
- *Release engineer* — Criterion 3 is unreachable with the machinery Step 2 names: score_corpus.py can only score the 2 hooks that expose slicing_offenders()
- *Release engineer* — Steps 2 and 3 falsify README claims that Step 1 already adjudicated, and Step 4 never re-runs the inventory
- *Product owner for an OSS release* — Step 2's stated machinery cannot measure a false-alarm rate for any hook a user actually installs
- *Release engineer* — Criterion 3 has no fixed denominator, and the repo's own detectors disagree: 25 / 24 / 22 hooks
- *QA / test architect* — 'MEASURED and recorded' produces no re-runnable artefact - Step 2 ends in a number, not a gate
- *QA / test architect* — A denominator of 30 hand-written synthetic snippets cannot yield a false-alarm RATE on ordinary code
- *Adversarial completeness critic* — Step 2 states no denominator, and the repo offers three incompatible answers to "each hook"
- *Senior software engineer* — Step 3's own deliverable is a test case for a hook Step 2 will not have measured
- *QA / test architect* — The instruments Step 2's numbers will come from have never been independently reviewed, and one has already shipped a miscount
- *QA / test architect* — Step 2's new tools and gates will red the suite mid-step until each is classified, and will bump the number README pastes

</details>

### P4 · CRITICAL · Criterion 2 has no owning step, and live user-reachable defects are open

**Found independently by 4 of 5 role lenses** (Adversarial, Product, Release, Senior) · 4 finding(s) · target: `criterion 2 / Steps 2-4`

**What goes wrong**

"No defect reachable by a user who installs it and uses it" has no discovery or closure mechanism anywhere in Steps 2-4. Two concrete pools already exist and neither is assigned: (a) five adversarially-CONFIRMED findings are still OPEN on four shipped units - plan_defer_guard, rate_prompt, stop_dispatcher (2), check_readme_fresh - and they are NOT covered by the closed decision, which deletes only the AR rows from run wf_91a48c61-20d; (b) the installer's `--dry-run` and settings.json backup paths have zero coverage of any kind, and the backup path is the most destructive surface in the product (it rewrites the user's ~/.claude/settings.json). A v1.0 cut in Step 4 would ship with an unadjudicated user-reachable defect list, which is criterion 2 unmet by definition.

**Evidence**

> C:\Users\ammar\Downloads\unbluff\docs\audits\review_runs.json - entries with run_id `wf_1b621b24-7ef` carry "open": 1/1/2/1 for hooks/plan_defer_guard.py, hooks/rate_prompt.py, hooks/stop_dispatcher.py, tools/check_readme_fresh.py; `python tools/check_review_freshness.py` (run live, exit 0) prints those four as UNRESOLVED. The AR run is a different one: docs/audits/adversarial_review_2026-08-06_guards.md line 3 "Run wf_91a48c61-20d". Installer: install.py:140-145 `backup_settings()` and install.py:239/282-287 `--dry-run`; grep for `dry_run\|dry-run\|backup` across tests/, tools/, hooks/ and run_selftests.py returns NOTHING.

**Smallest correction that does not widen the DoD**

Name criterion 2's owner explicitly inside Step 3 (it is already the defect-hunting step): adjudicate the 5 open confirmed findings (fix, or record why not user-reachable) and add integration scenarios for `--dry-run writes nothing` and `backup written before first write`. Both are criterion-2 work already implied, not new scope.

<details><summary>Corroborating findings from the other lenses</summary>

- *Senior software engineer* — timing_claim_guard ships inside the PostToolUse dispatcher with no install->fire coverage on any platform, so widening the CI matrix widens nothing for it
- *Release engineer* — The Windows selftest jobs pass vacuously: pre_push_gate's three sh-unavailable branches print SKIP but return 0, so run_selftests' CI-must-not-skip rule never sees them
- *Product owner for an OSS release* — Step 3 collapses the review plan into a roadmap without adjudicating any row against criterion 2, so known reachable defects get filed and shipped

</details>

### P5 · HIGH · INT-WIN is aimed at the wrong job - the known Windows hole is unreachable from it

**Found independently by 4 of 5 role lenses** (Adversarial, Product, QA, Senior) · 5 finding(s) · target: `Step 3 (INT-WIN) / criterion 4`

**What goes wrong**

The plan's own measured facts record that on Windows hooks/pre_push_gate.py --selftest prints 'SELFTEST SKIP: sh unavailable' three times and the suite still reports 32/32. Step 3's INT-WIN mirrors tests/test_integration.py, which contains no pre_push_gate scenario at all. So after Step 3, 'install -> fire -> uninstall verified on Windows' is asserted from a green run that has never exercised pre_push_gate's dispatcher delegation, pre-push dispatcher branch, or worktree delegation on Windows - and cannot even distinguish 'those paths ran' from 'those paths were skipped', because the skip is printed to stdout and the selftest returns 0. The repo already built the mechanism for exactly this and the sub-case skip routes around it: SKIP_RC=77 is documented as 'NEVER 0: a skip is not a pass', and run_selftests.py treats SKIP_RC as a FAIL under CI - but these three branches print and continue rather than returning it. This also violates the working rule 'a fixture that finds no case must FAIL rather than pass vacuously'.

**Evidence**

> hooks/pre_push_gate_selftest.py lines 200, 465, 522 (print 'SELFTEST SKIP: sh unavailable, ... untested', no append to `fails`); contrast line 113-115 which DOES `return SKIP_RC` for missing git. hooks/pre_push_gate.py:547 'SKIP_RC = 77 # selftest could not run (missing git/sh). NEVER 0: a skip is not a pass.' run_selftests.py:144-149 'A skip is NOT a pass. Under CI it is a failure'. `grep -n 'pre_push' tests/test_integration.py` returns nothing.

**Smallest correction that does not widen the DoD**

Before adding the INT-WIN job, make the three sh-unavailable branches route through the existing contract: either append to `fails`, or make the whole selftest return SKIP_RC when any sub-case could not run, so run_selftests.py's CI-must-not-skip rule fires. Then a green Windows run is evidence. Cost: one branch change in an existing file, inside the step that is already touching CI.

<details><summary>Corroborating findings from the other lenses</summary>

- *Senior software engineer* — After Step 3, run_selftests still reports 32/32 green on Windows while three delegation paths were skipped
- *Product owner for an OSS release* — Step 3's Windows work is aimed at the wrong job: the known Windows hole is in pre_push_gate's selftest, which INT-WIN cannot reach, and it passes vacuously
- *Adversarial completeness critic* — The 3-4 session estimate is already wrong at plan time, and the plan asks to be told when that happens
- *Adversarial completeness critic* — The vacuous SELFTEST SKIP passes are recorded as a fact, owned by no step - and the fact itself is shell-dependent, not platform-dependent

</details>

### P6 · HIGH · The inventory rots: Steps 2-4 change the README with no mechanism keeping Step 1 true

**Found independently by 1 of 5 role lenses** (QA) · 1 finding(s) · target: `'Estimated 3-4 sessions total' / Steps 2-4 sizing`

**What goes wrong**

The plan budgets 3-4 sessions total, of which one is spent. Step 1 - inventory only, fixing nothing - consumed 14 agents, 2.12M subagent tokens and 46 minutes and still returned 45 of 243 claims with no verdict. The work the plan has NOT yet scheduled is 165 claim dispositions (120 UNPROVEN + 45 pending), six per-hook negative corpora, a generalised scorer, a CI matrix change and the V131 collapse. Two to three sessions is not a plausible envelope, and the plan's own rule - 'If a session ends with the estimate GROWN, say so explicitly rather than quietly re-planning' - is triggered NOW, at the close of Step 1, not at some future overrun.

**Evidence**

> docs/audits/promise_inventory_2026-08-09.md METHOD section: '14 agents, 0 errors, 0 empty results, 2.12M subagent tokens, 46 min'; the same document's pending count of 45; docs/V131_REVIEW_PLAN.md is 2,338 lines (`wc -l`), not the 2,200 the plan states, so the Step 3 collapse is slightly larger than assumed.

**Smallest correction that does not widen the DoD**

Restate the estimate in the plan text now, with the driver named: '3-4 sessions was sized before the inventory returned 165 undisposed claims; the revised figure is N sessions, of which the criterion-1 disposition is M.' Do not re-scope the criteria to fit the old number.

### P7 · MEDIUM · 'Cut v1.0' collides with the v1.0.0 tag published 2026-07-13

**Found independently by 2 of 5 role lenses** (Adversarial, Release) · 3 finding(s) · target: `Step 4`

**What goes wrong**

Step 4 is six words of release work: "cut v1.0, and write the WON'T-FIX rule into the README". Executed literally, `git tag v1.0.0` fails - the tag exists and points at b8d3f9e from 2026-07-13 - and the repo's most recent release is v1.3.1 (2026-08-08, commit 56f8932, one commit behind HEAD). The DoD's "v1.0" is a maturity milestone, but the CHANGELOG explicitly declares SemVer, so the milestone needs a semver number the plan never states, and the release notes need to explain why the project's v1.0 milestone ships as some later number. Beyond the name, Step 4 enumerates none of the artifacts a cut requires: CHANGELOG entry, tag, GitHub release notes, the README WON'T-FIX section, and a check that the badge row still resolves. There is also no release automation to lean on - .github/workflows/ holds selftest.yml only, and its triggers are `push: branches: [main]` and `pull_request`, with no `tags:` trigger, so pushing the tag runs no CI at all.

**Evidence**

> `git for-each-ref refs/tags`: v1.0.0 2026-07-13 b8d3f9e, v1.1.0, v1.1.1, v1.2.0, v1.2.1, v1.3.1 2026-08-08 56f8932. `git tag --points-at HEAD` returns empty; HEAD is 00fc9ba, one commit past the v1.3.1 tag. CHANGELOG.md:4 "this project uses [SemVer]"; CHANGELOG.md:6 "## [1.3.1] - 2026-08-08". .github/workflows/selftest.yml:3-6 - triggers are push-to-main and pull_request only. `ls .github/workflows` -> selftest.yml (sole file). README.md:9-13 is the badge row; the CI badge targets selftest.yml.

**Smallest correction that does not widen the DoD**

Rewrite Step 4 as an explicit checklist and fix the number now rather than at tag time: "tag v1.4.0 as the v1.0 milestone (v1.0.0 is taken); CHANGELOG entry naming the four DoD criteria and their evidence; README WON'T-FIX section; GitHub release notes; confirm the CI badge's workflow is green on the tagged commit." No new criterion - only the artifact list the step already implies.

<details><summary>Corroborating findings from the other lenses</summary>

- *Adversarial completeness critic* — "Cut v1.0" collides with the versions already published - v1.3.1 shipped four days ago
- *Release engineer* — Step 3's collapse of V131_REVIEW_PLAN.md breaks a link in the already-published v1.3.1 release notes

</details>

### Unclustered findings

- **[LOW]** Step 3's "then" clause hides a second, differently-shaped job, and mis-states its size by 138 lines — *Adversarial completeness critic*

---

## WHAT THIS DOES TO THE PLAN

Every correction below is work the DoD **already demands**. None adds a criterion.

| | current plan | after the audit |
|---|---|---|
| Criterion 1 | implied by Step 1 | needs an explicit disposition step - 158 fix-or-delete decisions |
| Criterion 2 | asserted, unowned | needs an owner; 2 live user-reachable defects + 5 open confirmed findings |
| Criterion 3 | 'machinery already exists' | machinery scores 1 of 32 units, and that unit is not a user-facing hook |
| Criterion 4 | Step 3 = INT-WIN | INT-WIN gives 2 of 3 platforms; macOS never scheduled |

## APPENDIX - findings per role

| role | raised | survived | plan assertions verified |
|---|---|---|---|
| QA / test architect | 11 | 11 | - |
| Adversarial completeness critic | 11 | 11 | - |
| Product owner for an OSS release | 10 | 10 | - |
| Senior software engineer | 9 | 9 | - |
| Release engineer | 8 | 8 | - |

Total plan assertions verified against the repo across all lenses: **82**.

