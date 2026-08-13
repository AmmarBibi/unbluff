# Coverage ledger - 2026-08-09

The objective proof of coverage. Every item is `BUILT` (with the unit that carries it),
`SCHEDULED` (with a phase), or `FINALIZED-EXCLUSION` (with a justification). Nothing may sit in
none of the three.

**This ledger supersedes `coverage_ledger_2026-08-08.md`.** That ledger predates the v1.0
Definition of Done and the promise inventory; it is organised around the retired v1.3.1 ship
gate. Its rows are carried forward in section E below. **Its four `CORRECTIONS`-carried rows are
re-homed here in section F - see the CRITICAL finding that made that necessary.**

**As first written:** repo HEAD `00fc9ba`, tree clean apart from that session's audit files; all
numbers verified live at that commit. **That HEAD is superseded - see the step 2 update directly
below, which is the current state.** Marked rather than overwritten because this file is appended
to across sessions, and an unqualified "Repo HEAD X" at the top of a document whose body has moved
on is the exact drift this ledger exists to make impossible.

**STEP 2 UPDATE, 2026-08-09 (HEAD `eab22f0`).** Criterion 4 is CLOSED. Sections A, D, G and J
below carry the change. CI run **31304861194** on `eab22f0`: conclusion `success`, **16 jobs**,
0 failed, with `integration` executing on ubuntu-latest, windows-latest AND macos-latest for the
first time. The job count is GitHub's own `total_jobs`, not arithmetic. Step 2 was expected to go
red and did not: no fix was required on any platform.

---

## A. Criterion 1 - every behavioural claim is TRUE and proven, or DELETED

**Source:** `README.md` + the four `skills/*/SKILL.md`.
**Denominator: 243 claims found, 243 adjudicated, 0 pending.** Full matrix in
`promise_inventory_2026-08-09.md`.

| state | count | carrier |
|---|---|---|
| **BUILT** (PROVEN - a named artefact goes red if the claim breaks) | **85** | per-row in the inventory |
| **SCHEDULED** (UNPROVEN - each needs a fix-or-delete decision) | **158** | forward-plan step 5 (disposition) + step 6 (execution) |
| FINALIZED-EXCLUSION | 0 | - |

**19 rows struck before counting** and recorded with reasons: 14 mechanical duplicates, 5
judgement calls. Struck rows are listed in the inventory; the judgement calls are reversible.

**Caveat carried, not hidden:** 35 of the 85 BUILT rows carried a platform caveat, overwhelmingly
"integration runs on ubuntu only". Those 35 were BUILT-on-Linux and UNPROVEN elsewhere until
section D landed. **They were not double-counted; they were counted as BUILT with the caveat
printed.**

**RESOLVED by step 2, 2026-08-09.** The integration job now runs on all three platforms (CI
`31304861194`, green), so the "ubuntu only" caveat no longer attaches to any of those 35 rows.
**Two limits remain, and neither is the caveat that was just lifted:** (a) the MUTATION sweep is
still two-platform - ubuntu/3.12 and windows/3.12, no macOS - so no row may be described as
mutation-proven on macOS; (b) criterion 4 is proven on three clean CI images, not on user
machines, which is residual risk R4 in section H and unchanged. **The 35 rows have not been
individually re-read**; the caveat was removed at its single shared cause. Re-reading them
row-by-row belongs to step 5's disposition pass.

### A1. The SKILL.md population question - OPEN, not decided

A proposed rule ("an imperative instruction to an agent is not a behavioural assertion about
software") would remove ~76 rows. **State: SCHEDULED as a decision, not applied.** Both
denominators must be recorded in the disposition ledger so a re-auditor can redraw the line and
recount without redoing the work. Recorded here so the narrowing cannot happen silently.

---

## B. Criterion 2 - no defect reachable by a user who installs and uses it

**Denominator problem, recorded:** `tools/check_review_freshness.py` prints **5** open confirmed
findings. Parsing `docs/audits/review_runs.json` directly, run `wf_1b621b24-7ef` carries **42
open confirmed findings across 12 units**. The other 37 are masked because a unit that is both
STALE and has open findings is labelled only STALE. **The ledger, not the tool, is the
denominator.**

| item | sev | state | carrier / why |
|---|---|---|---|
| 42 open confirmed findings, 12 units | mixed | **SCHEDULED** | forward-plan step 3. Bounded by the ledger, never by the tool's UNRESOLVED line |
| `INSTALL-TAUTOLOGY` - the partial-checkout guard is a no-op; 9 of 25 hooks unguarded, 5 imported by production hooks | **CRITICAL** | **BUILT** 2026-08-09 - see section N | step 3. Reproduced live: delete `hooks/transcript_util.py` -> `install.py` exits 0 -> `close_skills_guard.py` raises `ModuleNotFoundError` |
| `ENC-1` - 0 of 25 hooks reconfigure stdout; cp1252 + non-ASCII path = half-printed report then **exit 0** | HIGH | **SCHEDULED** | step 3. Carried from the 08-08 ledger; **worse than recorded there** - silent, not a visible crash |
| `PGG-PS` - `piped_gate_guard` registered `matcher: "Bash"`; never fires for PowerShell users | HIGH | **SCHEDULED** | step 3. Two-part: matcher AND the guard's POSIX-only vocabulary |
| `SKILLDIR-DESTROY` - install/uninstall destroys a user's pre-existing same-named skill directory | HIGH | **SCHEDULED** | step 3 |
| `FASTTEST-BLOCK` - `fast_test_on_stop` hard-blocks every turn end on any repo that merely has a `tests/` dir | HIGH | **BUILT** 2026-08-11 - see N0 | Was SCHEDULED here while N0 recorded it BUILT, i.e. this document carried TWO states for one item. Found by the source-coverage pass, not by re-reading. CI green on `367ace4`, 16 jobs |
| `--dry-run writes nothing` / `settings.json backup` | - | **SCHEDULED** | step 3. Zero coverage of any kind today; inventory rows `RM-05`, `RM-06` |
| `CA-SELFREF` - the consistency-audit skill flags its own detection vocabulary as placeholders | MEDIUM | **SCHEDULED** | step 3. **Found by running the skill during this session's close ritual**; 16 of 16 [E], 3 of 3 [C], 4 of 4 [F] false positives on a document that discusses the tool |

**Bounding rule:** criterion 2's scope is the R1/R2 four-clause entry-point derivation. See
section F - that rule currently exists **only** inside `V131_REVIEW_PLAN.md`.

---

## C. Criterion 3 - each hook's false-alarm rate MEASURED and recorded

| item | state | evidence |
|---|---|---|
| corpus coverage | **1 of 32 units (3%)** | `python tools/no_regression.py`, live |
| hooks the existing scorer can grade | **0 of 16 `REQUIRED_HOOKS`** | 13 of 16 read `sys.stdin`; 0 of 16 expose `slicing_offenders()`, the only entrypoint `score_corpus.py` calls |
| the one covered unit | `hooks/capped_report.py` | a dev-time self-lint; the function scored is not the function the 6 importing hooks use |
| the denominator itself | **DISPUTED: 25 / 24 / 22** | the repo's own detectors disagree on how many hooks exist |

**State: SCHEDULED**, forward-plan step 4, split into 4a (payload-driven scorer) and 4b (one
corpus per input class). **The plan's "the corpus machinery already exists" framing is retired -
it is false for every shipped guard.**

---

## D. Criterion 4 - install -> fire -> uninstall on Windows, macOS and Linux

**State: CLOSED 2026-08-09 (step 2, HEAD `eab22f0`).** All four rows below are BUILT.

| platform | state | evidence |
|---|---|---|
| Linux | **BUILT** | CI job `integration ubuntu-latest`, run `31304861194`, conclusion `success` |
| Windows | **BUILT** | CI job `integration windows-latest`, same run, `success`. Also run locally on a developer Windows box first: 30/30, exit 0 - recorded as the weaker evidence it is, since a dev box is not a clean image |
| macOS | **BUILT** | CI job `integration macos-latest`, same run, `success`. **First execution on macOS ever**, and it required no fix |
| `pre_push_gate` delegation on Windows | **BUILT** | The three `SELFTEST SKIP: sh unavailable` paths now resolve a shell by asking the box and FAIL when none is found. Verified RED-first (`0 of 3 required site(s) executed`, exit 1) then green (`3 of 3`), and pinned by mutations SH-1..SH-4, all CAUGHT |

**What this row does NOT say.** Criterion 4 is proven on three clean GitHub-hosted images, not on
user machines - residual risk R4, section H, unchanged and still disclosed in the README's
WON'T-FIX section (step 6). The mutation sweep remains TWO-platform; see section J.

---

## E. Carried forward from the 2026-08-08 ledger

All 9 previously-deferred items retain their phase. Re-homed against the new step numbering:

| id | old phase | new home |
|---|---|---|
| `ENC-1` | v1.4 phase 1 | step 3 (section B) |
| `ENTRY-GUARD` | v1.4 phase 1 | step 3 |
| `BUDGET-1` | v1.4 phase 1 | step 3 |
| `INT-MUT` | v1.4 phase 2 | **CORRECTED 2026-08-09** - see the row below. It does NOT fold into the 3-OS matrix work |
| remaining LOW rows | v1.4 | step 3 |

The 12 confirmed findings of run `wf_c9822f7b-865` keep their BUILT/SCHEDULED state unchanged.

### E1. `INT-MUT` - the correction, and what step 2 actually did about it

**The claim "step 2 - folds into the 3-OS matrix work" was FALSE, and it was mine.** INT-MUT is
"the 30-scenario integration suite has zero mutations". Running an unverified suite on three
runners MULTIPLIES it; it does not verify it. Nothing about the matrix touches INT-MUT, and the
gap got *more* load-bearing after step 2, not less: criterion 4 (section D) is now claimed BUILT
on three platforms on the strength of a suite whose scenarios had never been shown to still bite.
This was found by the completeness-audit at close, not while the row was being written.

**The plan's second claim about it was also refuted - by measurement.** V131 recorded INT-MUT as
blocked on a mechanism: *"either `test_integration.py` grows a `--selftest` (it is a script, not a
unit) or the harness learns to verify through a command."* Neither is needed. The script ignores
argv entirely and exits 0 on pass / 1 on fail, which IS the verify contract. Measured:
`python tests/test_integration.py --selftest` -> rc 0. INT-MUT had been carried as blocked since
the v1.3.1 review on a premise nobody had tested.

| item | state | carrier |
|---|---|---|
| the integration suite has ZERO mutation coverage | **BUILT** 2026-08-09 | `INT-1` and `INT-2` in `tools/mutation_check.py`, both verified through `verify_unit="tests/test_integration"`, both **CAUGHT**. They revert the two regressions v1.1.1 added scenarios to catch: skills copied without their bundled `scripts/`, and only the first of four skills shipping |
| **DENOMINATOR: 2 of 30 scenario-groups pinned, not 30** | **SCHEDULED** - step 3 | The zero-coverage state is closed and the mechanism is proven; per-scenario coverage is not. Stated as a fraction so this cannot be read as "the integration suite is mutation-covered" |
| **NEW:** `install.py` was UNREACHABLE by the mutation harness | **BUILT** 2026-08-09 | `unit_path()` mapped a bare name to `hooks/` and a slashed name repo-relative, so a repo-ROOT file had no addressable form. Both `COPY_FILES` entries - `install.py`, `run_selftests.py` - were copied into every scratch tree and could not be mutated. The most user-facing file in the repo was uncoverable BY CONSTRUCTION while the summary printed a clean total. Fixed generally (root fallback, `hooks/` probed first so all pre-existing entries resolve unchanged), not by addressing it as `./install`. **Same shape as `INSTALL-TAUTOLOGY` and `ENTRY-GUARD`: a roster not derived from what the code does.** `run_selftests.py` is now addressable too and still has no mutation - SCHEDULED, step 3 |

---

## F. V131_REVIEW_PLAN.md - the collapse is CANCELLED

**Denominator: 247 item-occurrences enumerated mechanically (217 distinct after id dedup, and
15 ids are reused for different findings - itself a hazard). 40 of 247 must survive any
collapse, plus 8 id-linked.**

**State: FINALIZED-EXCLUSION for the collapse itself** - it discharges no DoD criterion, and
`CHANGELOG.md:56` ("All carry a phase in `docs/V131_REVIEW_PLAN.md`") stays TRUE if the file
keeps its phases. The file gets a HISTORY header instead of a rewrite.

**Two CRITICAL rows that made this necessary - both CLOSED 2026-08-09 (step 1):**

| item | state | why |
|---|---|---|
| **6** confirmed findings whose ONLY carrier was plan prose | **BUILT** 2026-08-09 | Now carried verbatim in **section K2**. A carrier-cell scan of `coverage_ledger_2026-08-08.md` finds **6 of its 27 carrier cells** point at plan-only prose: **rows 2, 3, 7, 8, 10, 11**. Rows 7/8/10/11 name "CORRECTIONS item N"; row 3 names "the same section"; row 2 names the plan section *"THE CLASSIFICATION WAS REVIEWED AND IS REFUTED"*. That ledger now carries a supersession note directing readers to K2. **Six rows, not the four the original finding named.** <br>**Correction, 2026-08-09 source-coverage pass:** an earlier revision of this row listed the set as 3/6/7/8/10/11. That was wrong - row 6's carrier names code and a commit (`904219c`), so it was never plan-only, and row 2 was missed. Row 2's substance (run ids, the 20/20/12/8 denominator, the `4f1f466d` snapshot) is independently carried in the 08-08 ledger's own section A header and in K2, so no content was lost - only the enumeration was wrong |
| the R1/R2 rule - the only operational definition of "reachable by a user" | **BUILT** 2026-08-09 | Now **section K1**, with the fourth R1 clause folded in from CORRECTIONS item 1. Lifting the base rule alone would have moved a three-clause version of a four-clause rule. Verified after the lift that all four R1 clauses, R2, the population rule and the residual-risk limit survived |
| the HISTORY header | **BUILT** 2026-08-09 | `V131_REVIEW_PLAN.md` now opens with a HISTORY block and four reading warnings: the five accounting systems that must never be summed (247 occurrences / 217 distinct / 15 reused ids), superseded arithmetic left standing on purpose, the self-contradicting SKIP-1 row, and that the file is a shipped hook's calibration corpus |

---

## G. Claim surfaces OUTSIDE criterion 1's scope

**Denominator: 92 tracked files outside the DoD line; 57 claim-extracted; ~308 behavioural
claims found. This is a FLOOR, not a ceiling - 35 files are unmeasured.**

**State: FINALIZED-EXCLUSION as a population** - criterion 1 names README + `skills/*/SKILL.md`
and the owner has said not to widen it. Recorded so the exclusion is a decision, not an
oversight.

**Three rows escape that exclusion because they are FALSE, not merely unproven:**

| item | state | why it is not excludable |
|---|---|---|
| `CHANGELOG` 1.1.1 asserts the integration suite passes on Linux/macOS/Windows | **BUILT** 2026-08-09 | Corrected IN PLACE with a dated `CORRECTION` block rather than deleted - a changelog that quietly edits away its own false statements is the failure this project exists to catch. `CHANGELOG.md:61` ("14 jobs") is deliberately NOT touched: it is a historical statement inside v1.3.1's Verification section and was true at that release |
| **NEW, found by step 2:** two README claims that were TRUE became FALSE the moment the matrix landed | **BUILT** 2026-08-09 | `README.md:149-150` ("the integration test below runs on Linux") and `:277-279` ("CI is 14 jobs"). Repaired in the SAME commit as the matrix. Recorded because the hazard generalises: a fix to the evidence can falsify a claim that correctly described the old evidence, and nothing in this plan was watching for that direction |
| **NEW, found by step 2:** the "CI is N jobs" claim has NO gate | **SCHEDULED** - step 5 | `tools/check_readme_fresh.py` derives and checks the SELFTEST count only. The job count was hand-updated 14 -> 16, which replaces one ungated number with another - a claim with no proof, which criterion 1 forbids. Durable fix: derive it from `.github/workflows/selftest.yml` (the derivation was written and verified during step 2 - it yields 16 on the new file and reproduces the recorded 14 on the old). NOT built here: a new gate is outside "make the platform evidence real" |
| Two shipped, auto-installed hooks documented ONLY in `CHANGELOG` - one blocks the user's Bash commands | **SCHEDULED** - step 6 | A delete-the-unprovable pass over the README would leave two hooks undocumented anywhere a user looks |
| `install.py --help` promises per-hook `--only/--without`; the flags operate at EVENT granularity | **SCHEDULED** - step 6 | The help text is a promise the code does not keep |

---

## H. Residual risks - what remains after the full plan executes

Recorded because "unclosable" must still be a ledger row.

| risk | state | disposition |
|---|---|---|
| R3 R1/R2 is an assertion, not a proof | **FINALIZED-EXCLUSION** | disclose in the README WON'T-FIX section: criterion 2 means "no defect reachable through the paths R1/R2 enumerates, as of this enumeration" |
| R4 criterion 4 proven on CI runners, not machines | **FINALIZED-EXCLUSION** | disclose the exact proven environment and what it excludes |
| R1 criterion 3's statistics | **FINALIZED-EXCLUSION** | publish the rate with provenance; never as "never fires" |
| R10 nothing proves a stranger can use it | **FINALIZED-EXCLUSION** | disclose + provide the feedback path. Only publication answers it |
| R2 the 42 findings are self-adjudicated | **SCHEDULED** - step 3 | buy one independent adversarial pass over the R1 dispositions. This is the repo's own rule 6 |
| R5 the freshness gate proves existence, not truth | **SCHEDULED** - step 5 | pair each `KEEP-BUILD-PROOF` row with a **mutation** anchor, not a text anchor |
| R6 the SKILL.md rule is a judgement call worth ~76 rows | **SCHEDULED** - step 5 | record both denominators (section A1) |
| R7 ~308 out-of-scope claims, floor not ceiling | **SCHEDULED** - step 6 (partial) | finish extraction over the remaining 35 files; the 3 FALSE rows are already scheduled in section G |
| R8 V131 ships in every clone | **FINALIZED-EXCLUSION** | HISTORY header + "these five accounting systems must never be summed" |
| R9 the estimate is the least-evidenced number here | **SCHEDULED** - re-estimate after step 4 | the previous estimate was wrong by 2.5x for exactly this reason |

---

## I. Ledger denominators - what this document itself covers

| population | enumerated | adjudicated |
|---|---|---|
| behavioural claims, README + 4 SKILL.md | 243 | 243 |
| plan assertions, `NEXT_SESSION_PROMPT.md` | 86 | 71 (15 not repo-checkable; listed in the round-3 sweep) |
| V131 item-occurrences | 247 | 247 |
| tracked files outside criterion 1 | 92 | 57 - **incomplete, and section G says so** |
| criterion-2 entry points | 10 externally-invoked | 10 (8 executed live); +7 dispatcher-reached, 2 executed, **5 contract-level only** |
| open confirmed findings | 42, across **all 6** runs in `review_runs.json` (68 unit-entries; the other 5 runs carry 0 open) | 0 - all SCHEDULED, none adjudicated |
| CI jobs | 4 | 4 - see J |
| shipped skill scripts | 3 | 3 - see J |

**Two populations in this table are knowingly incomplete** (out-of-scope files 57/92;
dispatcher-reached entry points 2/7 executed). Both are SCHEDULED above. No population in this
ledger is reported as complete when it is not.

---

## J. Gaps found by the source-coverage pass (2026-08-09 close ritual)

Content that existed in an authoritative source and was in **none** of BUILT / SCHEDULED /
FINALIZED-EXCLUSION until this pass. This is the failure class a grep cannot find.

| gap | state | detail |
|---|---|---|
| CI jobs `mutations` and `mutations-windows` were unreconciled | **BUILT** 2026-08-09 (as a DISCLOSURE, not as coverage) | Both are gates and neither appeared anywhere in this ledger. They run on `ubuntu-latest/3.12` and `windows-latest/3.12`. **There is still no macOS mutation sweep.** Section D's 3-OS work closed `integration` on macOS and left the mutation evidence two-platform, exactly as predicted. `README.md:277-279` now states this in the shipped documentation - "there is no macOS mutation sweep" - so a reader cannot mistake the integration win for a mutation win. A macOS mutation job is a **FINALIZED-EXCLUSION**, labelled as such rather than left as a bare "not scheduled" - the completeness-audit at close caught this row asserting a decision without giving it one of the three states. **Justification:** no mutation in the harness is macOS-specific the way `#30` is posix-specific and `#D10b` is Windows-specific; both posix-only entries are discharged by the ubuntu job, and macOS is posix, so a third sweep would re-prove what ubuntu already proves. **Re-open condition, stated so the exclusion is falsifiable:** the first mutation whose behaviour differs between Linux and macOS (BSD vs GNU tooling, case-insensitive filesystem, arm64) makes this a real gap and the job must then be built. |
| The 3 shipped skill scripts were an unnamed population | **SCHEDULED** - step 3 | `skills/consistency-audit/scripts/{audit,extract,sources}.py`. `install.py` copytrees them into `~/.claude/skills`, which is **R1 clause 4** - they are inside criterion 2's entry-point scope. `CA-SELFREF` (section B) is a defect in `extract.py`; the ledger recorded the defect without ever recording the population it belongs to. |
| `review_runs.json`'s denominator was unstated | **CLOSED by this pass** | The ledger said "42 open" without saying over what. Verified: 6 runs, 68 unit-entries, 42 open, all in `wf_1b621b24-7ef`; the other 5 runs carry 0 open. **The 42 is the complete population**, now stated as such in section I. |

**Method note:** these were found by enumerating each source mechanically and testing whether the
ledger names it - not by re-reading the ledger. Re-reading the ledger would have agreed with
itself, which is precisely why that is not the procedure.

### J2. Second source-coverage pass, 2026-08-09 close ritual (step 2)

Same method, run against the step-2 surface. **All 4 CI jobs are named in this ledger - that
population is CLOSED with no gap.** Two new gaps found:

| gap | state | detail |
|---|---|---|
| **16 of 47** gate-able `.py` files carry ZERO mutations; **11 of the 16 appeared in NO state in this ledger until this row was written** (all 16 are SCHEDULED by it - re-derived at close, the count is unchanged at 16 of 47, because the 5 mutations added later target units that already had coverage) | **SCHEDULED** - step 3 | Denominator derived, not listed: 47 `.py` files are copied into every mutation scratch tree (`COPY_TREES` + `COPY_FILES`); 32 distinct units carry at least one mutation. Materiality split, because "16 uncovered" flattens two very different things. **Load-bearing (shipped or a registered gate):** `hooks/selftest_budget.py`, `hooks/fast_test_on_stop_selftest.py`, `skills/consistency-audit/scripts/sources.py` (SHIPPED to users - R1 clause 4; note `audit.py` beside it IS named while `sources.py` was not), `tools/check_python_floor.py`, `tools/check_skill_deps.py`, `run_selftests.py`. **Dev-time only, lower materiality but still scheduled:** the 4 remaining `tools/*` utilities and the 3 `tests/*` registries. Materiality sets ORDER, never WHETHER |
| **The twin roster of the sh defect:** 9 more vacuous `SELFTEST SKIP` sites across 4 files | **SCHEDULED** - step 3 | Found by grepping for the defect CLASS after fixing the instance, per "grep for the twin roster". `fast_test_on_stop_selftest.py` (4), `meta_audit_on_stop.py` (4), `tools/check_review_freshness.py` (1) print a skip and CONTINUE - structurally identical to the three sh sites. **MEASURED, and this is the part that must not be overstated: ZERO of them fired in the full suite run.** They key on `git`, which is a hard requirement of this repo and present on every box and runner, so they are LATENT, not live - materially weaker than the sh case, which was measured firing 3 of 3 on a stock Windows machine. They are scheduled because the sh sites were assumed harmless on exactly the same reasoning until someone measured them, not because a live failure is known. `hook_health_check_selftest.py:438` is NOT in this set: it writes a fixture that exits `77`, the suite's real SKIP_RC, which is the correct pattern |

**What this pass did NOT check:** mutation coverage is a proxy for "the tests bite", not for "the file is
correct". A file with mutations can still be under-tested, and step 3's defect queue is the pass that
looks at behaviour rather than at coverage bookkeeping.

---

## L. Meta-review, 2026-08-09 close ritual (step 2)

**Is criterion 4 genuinely closed, or only bookkept as closed?** **Genuinely closed by its own
words** - criterion 4 says "install -> fire -> uninstall verified on Windows, macOS and Linux",
`tests/test_integration.py` does exactly that sequence, and it now executes on all three (CI
`31304861194`, all three jobs `success`). **Its evidential limit, stated rather than implied:**
the suite's scenarios are only **2 of 30** mutation-pinned, so "these scenarios still bite" is
proven for two of them and assumed for twenty-eight. Criterion 4 is closed; the strength of the
instrument behind it is a step-3 item. Plus residual risk R4 (clean CI images, not user machines),
unchanged.

| finding | state | detail |
|---|---|---|
| **The gate ledger records 1 gate tier, not 5** | **SCHEDULED** - step 3 (unchanged, re-confirmed) | Read, not reconstructed: `docs/audits/gate_runs.json` holds 200 entries and **every one is `run_selftests`**. The mutation sweep, the integration test, CI and the review-freshness gate write nothing. So "did the full mutation sweep run for step 2?" is unanswerable from the durable record - the evidence exists only in a scratchpad file and this ledger's prose. This is why check 4 of the meta-review procedure says read the ledger rather than trust memory |
| **My own sh-delegation roster is DECLARED, not DERIVED** | **SCHEDULED** - step 3 | `_SH_SITES_REQUIRED` is a hand-written frozenset of three names. A fourth delegation site added later that calls `subprocess.run([sh_exe, ...])` and forgets `_sh_site(...)` is invisible to the guard - the denominator would keep printing "3 of 3" over a file with four sites. **This is the same shape as `INSTALL-TAUTOLOGY`, `ENTRY-GUARD` and the `unit_path` gap I fixed this session: a roster not derived from what the code does.** Recorded against myself in the same session I criticised it elsewhere. Durable fix: discover the sites by shape (walk the AST for `subprocess.run` calls whose first element is the resolved shell) and assert each is registered - the pattern `_selftest_shim_self_reference` already uses for shim templates |
| **The 800-line rule is enforced by NOTHING** | **SCHEDULED** - step 3 | Grepped: "800" appears in exactly one place in the gate tooling, and it is a *comment* recording that the rule was broken before. Currently over (**re-measured 2026-08-11, and every previous figure in this row was stale**): `hooks/pre_push_gate_selftest.py` **995** (was recorded 866, and 956 in a third document), `tools/mutation_check.py` **1154** (was 1033, and 1128 elsewhere), and **`hooks/fast_test_on_stop_selftest.py` 852 - a THIRD violator, newly over, named in no document until now**. A documented rule with no gate, now violated **five** times across three files. <br>**This row is an instance of the defect it describes.** Three different pairs of line counts were in circulation simultaneously (866/1033, 956/1128, 995/1154), which is what an ungated number does. Patching the figures again would be another instance fix; the row's own prescription stands and is the only durable form - **build the line-count GATE, then split.** Recorded so the next reader knows the numbers here are a snapshot, not a control REMEMBER vs ENFORCE: prose is advisory, only a gate is a control. The fix is a line-count gate, not a split; the split follows from the gate |
| **The README/CHANGELOG repairs are instance fixes** | **SCHEDULED** - step 5 | Correcting "14 jobs" to "16 jobs" by hand replaces one ungated number with another. The durable form is the job-count gate already scheduled in section G. Recorded here so the instance/mechanism distinction is explicit rather than implied |

---

## N. STEP 3 progress - the criterion-2 defect queue (2026-08-09, HEAD `c488ab3`)

**Two items closed, both CRITICAL-adjacent and both the same shape: a roster not derived from
what the code does.** The ledger said to fix them together (K3) and they were.

| item | state | evidence |
|---|---|---|
| `INSTALL-TAUTOLOGY` (**CRITICAL**) | **BUILT** | The guard globbed `hooks/*.py` into its required set then asserted those files exist - the same statement twice, so the globbed half could never report a missing name and real coverage was the hardcoded floor alone: **16 of 25**, 9 unguarded, 5 imported by production hooks. The roster is now the **AST import closure** of the wired entry points; a module that fails to resolve with the hook dirs off `sys.path` is a LOCAL file that is missing - the one case a listing structurally cannot report. **16 of 25 -> 25 of 25** detected. Pinned by `IT-1`/`IT-2`, both CAUGHT |
| `ENTRY-GUARD` | **BUILT** | `install_skill()` printed "skipping" and CONTINUED on a missing skill dir, so install exited 0 and then `close_skills_guard` - a WIRED hook - blocked every session close demanding a skill the user never received. Now guarded, derived from what a `SKILL.md` TELLS THE USER TO RUN plus its import closure (globbing `scripts/*.py` would reproduce the tautology one directory over). One shared `_import_closure` serves both rosters. Pinned by `EG-1`/`EG-2`, both CAUGHT |
| `install.py` had NO `--selftest` and was a registered gate NOWHERE | **BUILT** | The structural reason the tautology survived every review: nothing ever asked the file a user literally runs a question. Now exposes `--selftest` and is EXPLICITLY registered in `run_selftests.py` as `install-guard`, per that file's own rule that name-pattern detection is a backstop. Suite is 33 gates, was 32 |
| the probe deletes each file IN TURN, not a hand-picked victim | **BUILT** | 26 hook + 7 skill deleted-file cases, denominator printed. A roster-shaped guard probed only with names already ON its roster proves nothing about the names that are not - which is exactly how the 9 stayed invisible |
| carriers, named so this is greppable at resume | **BUILT** | `install.py`: `missing_hook_files()`, `missing_skill_files()`, `_import_closure()` (one walk, two rosters), `_resolves_outside()`, `selftest()`, and from 2026-08-11 `_catches_import_error()`, `SKILL_MANIFEST`, `_read_skill_manifest()`, `_skill_payload()`, plus the `dest_root`/`src_root` params on `install_skill`/`remove_skill`. `run_selftests.py`: the `install-guard` AUX_GATES entry. `tools/mutation_check.py`: `IT-1`, `IT-2`, `EG-1`, `EG-2`, `OPT-1`, `SD-1`, `SD-2` |
| the `sys.path` blocking is pinned by the ONE case that decides it | **BUILT** | For a DELETED file the blocking is inert, so a delete-only probe would have left it unpinned. It matters TRANSITIVELY (`capped_report -> cap_shapes -> cap_types`): with the dir on `sys.path` and no blocking, a PRESENT intermediate reads as external and is never traversed. Removing the blocking makes the probe red with that exact message |

### N0. Step 3, continued 2026-08-11

| item | state | evidence |
|---|---|---|
| **the optional-import regression** - ENTRY-GUARD turned all 16 CI jobs RED on `c488ab3` | **BUILT** 2026-08-11 | The closure asked `find_spec("docx")`, got None on a runner without python-docx, and reported `consistency-audit/scripts/docx.py` as a MISSING LOCAL FILE - it invented three files that never existed. `extract.py` guards those readers with `try/except ImportError` on purpose. **It passed locally because THIS box has python-docx, PyMuPDF and pdfminer installed and a clean runner does not** - verified at resume. Fix: an import whose enclosing `try` catches ImportError is optional BY DEFINITION, derived from the AST. Verified against the real failure condition by stubbing `_resolves_outside` so exactly those three are unresolvable - both rosters return `[]`. Probe is SYNTHETIC so it answers identically on every box, and asserts BOTH directions (guarded = not required, unguarded = still required). Pinned by `OPT-1`. CI green on `bc8fcec`, 16 jobs |
| `SKILLDIR-DESTROY` (HIGH, **user data loss**) | **BUILT** 2026-08-11 | Worse than this ledger recorded - TWO paths, both reproduced live before fixing. **install** merged over a user's pre-existing same-named skill (`copytree(dirs_exist_ok=True)`); **uninstall** `rmtree`d the WHOLE directory with `ignore_errors=True`, so uninstalling unbluff silently deleted a skill that predated it. Fixed with a provenance manifest, following this repo's own precedent that `install()` refuses to clobber a foreign pre-push hook. Install refuses any skill dir with no manifest; uninstall removes exactly the manifest's paths and prunes only directories that end up empty. **The reverse direction is tested too** - a fix that protects user data by breaking uninstall is not a fix: 5 user-data cases covering refuse-on-foreign, don't-delete-foreign, clean round trip, a file added AFTER install surviving, and an all-ours directory still disappearing (or integration G5 would go red). Pinned by `SD-1`/`SD-2`. Integration 30/30 |

| `FASTTEST-BLOCK` (HIGH) | **BUILT** 2026-08-11 | **MEASURED through the real entry point before any edit, 10 repo shapes: SEVEN hard-blocked a turn end (rc 2) with nothing wrong.** `detect()` treated a directory named `tests/` as proof of a pytest project, so `python -m pytest -x -q` ran in a **Rust** repo (`tests/` is Cargo's own integration-test dir), a Go repo, a JS repo whose package.json has no `scripts.test`, an empty `tests/`, and a `tests/` holding only helpers - each exiting **5 (NOTHING COLLECTED)** and each reported as "FAILING at stop - fix before finishing". A broken root conftest exited **4**; an interpreter without pytest exited **1 - the same code as a genuine failure**, which is why that case had to be prevented at DETECT time rather than contained at interpret time. `pre_push_gate` shares this `detect()` (`pre_push_gate.py:114`) and maps rc != 0 to BLOCKED, so every shape also blocked `git push`. <br>**Two halves, neither subsuming the other:** detection now requires pytest CONFIG (`pytest.ini` / `pyproject` / `setup.cfg` / `tox.ini`) or a genuinely collectible `test_*.py`/`*_test.py`, AND that pytest be importable by the interpreter that would run it; containment maps pytest rc 4/5 to "the gate could not answer", routed to a notice that exits 0 and is NOT silent. Deliberately **not** applied to non-pytest commands - applying pytest's exit table to `npm test` would waive a genuine failure there (pinned by `FTB-5`). <br>**Controls hold:** a genuinely failing pytest suite still exits 2; a passing one is still silent; a no-source-change turn is untouched. <br>**Pinned by `FTB-1`, `FTB-1b`, `FTB-2`, `FTB-3`, `FTB-4`, `FTB-5`, `FTB-6` - 7 of 7 CAUGHT.** `FTB-4` and `FTB-6` pin the two CALL SITES, not the helper: the first end-to-end case exited before `main()` ever evaluated an rc, so a mutation deleting that call would have survived it - check 7's lesson recurring in the same file. Suite 33/33, integration 30/30. <br>**Two PRE-EXISTING false negatives found by the positive controls and fixed in the same change:** `setup.cfg [tool:pytest]` and `tox.ini [pytest]` are real pytest projects that `detect()` already refused to gate. They were found only because the accept-shapes were asserted - a detector that answered None for everything would have satisfied the false-alarm half perfectly while disabling the hook. <br>**LIMIT, stated in this repo's own rule-6 language: the author wrote the fix AND its only probe.** 12 probe shapes passed; that is "12 shapes passed", NOT "no false alarm remains". The independent pass is owed and remains SCHEDULED |
| the corrected selftest that **asserted the defect** | **BUILT** 2026-08-11 | `fast_test_on_stop_selftest.py` case 3 created a BARE `tests/` dir and REQUIRED a pytest command back - the suite encoded the defect as an invariant, which is a large part of why it survived every review. Corrected rather than deleted: the intent (autodetection must work) is kept, the false premise (a directory named `tests` proves a pytest project) is replaced with real evidence, and the bare-dir shape is now asserted in the OPPOSITE direction. Same shape in `pre_push_gate_selftest.py:419`, whose comment "would make fast_test_on_stop pick pytest" had become false - that case would have kept passing while proving only that an override beats NOTHING |
| **`CAP-FP-1`** - `cap_shapes` false-positives on a COUNTER bound in a BOOL-returning function | **SCHEDULED** - V1.4-BACKLOG | Found because the repo's own cap detector went red on the new code. **Not accepted on my own say-so - I wrote the flagged code, so it was reduced to a minimal fixture and probed with controls in BOTH directions:** the same shape flags; the same shape with the bound REMOVED is clean (so the bound causes it); and a genuine offender still flags with a **different** message (`slices to a bound ... render()` vs `stops the scan at a bound ... keep()`), proving the detector was live and looking - without that positive control, "clean" would have proven nothing. Toggling `clause2`/`clause3` changes nothing for this site, locating the defect in the "stops the scan" branch not applying clauses 1-3. By the module's OWN stated rules it should never have fired: clause 1 excludes "a counter", clause 2 excludes "a bool". **Classified by the repo's own R1/R2 rule rather than by judgment: R1 holds (weekly sweep), R2 does NOT** - reaching it requires editing unbluff's own source - so it is developer-facing and is **not** a criterion-3 user-facing false alarm. Held meanwhile by a `BOUND_EXEMPTIONS` entry that states it is a measured false positive rather than borrowing the other two entries' "reports its own total" justification, which would be false for this site. The roster is liveness-audited, so the entry reports itself DEAD the moment the detector is fixed |
| the `meta_audit_on_stop` budget failure was **MINE, not the known flake** | **BUILT** 2026-08-11 | Worth recording because it was one step from being misfiled. After the fix the suite went red on `meta_audit_on_stop` at **22.73s vs its 17.50s budget** - the exact signature of `SELFTEST-BUDGET-FLAKE`, which is already SCHEDULED, and which would have absorbed it silently. **The control refused it:** standalone the same gate ran 5.63/5.82/6.68s, rc 0 each, against a 7.24s idle baseline - so the gate was fine and the ENVIRONMENT had changed. `run_selftests` is sequential (checked, not assumed), so the cause was the I/O burst from my new fixtures: 12 of 15 called `git init` for cases that only exercise `detect()`, which never shells out to git. Fixtures slimmed to build exactly what each case needs; `meta_audit_on_stop` returned to **6.40s / 17.50s (37%)** and the suite to 33/33. **A known flake is the most dangerous place to file a real regression**, and the standing "check the control before believing the subject" rule is the only thing that separated them |

| **`FTB-1` and `FTB-6` shipped DECORATIVE, and CI found it - not review** | **BUILT** 2026-08-11 | CI run `31526789857` on `6bb91b1`: *160 of 162 executed, 0 unproven,* **`MUTATIONS SURVIVED (2)`** - `fast_test_on_stop/FTB-1` and `pre_push_gate/FTB-6`. Both passed locally. Both were PROBES; the production fix was never implicated and has been stable since `25a87f2`. <br>**One class, two instances: a probe whose outcome depends on what happens to be INSTALLED.** The preceding commit NAMED that class and then fixed only some of its instances - it pinned `_pytest_importable` for the ACCEPT shapes and left the DECLINE shapes and the second gate unpinned. The "general not instance" rule broken inside the change that diagnosed it. <br>**`FTB-1` is the instructive half:** `detect()` returns None when EITHER half declines, so on a box without pytest a **BROKEN detector returns exactly what a correct one returns** and the decline assertions went green for a reason unrelated to the property they claim to test. Structurally invisible locally, where pytest exists. Fixed by asserting `looks_like_pytest_project()` DIRECTLY - the box-independent verdict - so a missing pytest can never stand in for a correct detector. `FTB-6` had no catcher at all on the runner that executes the mutation job, its case being third-state-skipped on pytest availability; now synthetic like its sibling. <br>**The methodological error, recorded because it nearly cost a third CI round:** *"SELFTEST OK on a pytest-less box" proved the suite was PORTABLE. It never proved the PINS STILL BITE there.* A passing test says nothing about whether it would fail on a defect - the entire premise of mutation testing, applied to my own verification and then skipped. **The durable form of the check: run the MUTATION HARNESS under the deprived interpreter, not just the suite.** Done: `fast_test_on_stop` 16 of 17 executed / 0 unproven, `pre_push_gate` 24 of 25 / 0 unproven, all 7 pins CAUGHT with pytest absent. CI **green on `367ace4`, 16 jobs, 0 failed** (run `31531141633`). <br>**Session tally worth carrying forward: 3 of the 4 problems here were in the CHECKING INSTRUMENTS, not the product** - `CAP-FP-1`, the `meta_audit` budget misattribution, and this. That matches the repo's own recorded 7-of-11 and should stop being surprising |

| **`SELFTEST-BUDGET-FTOS`** - `fast_test_on_stop`'s selftest is at 15.8s of a 25s cap it cannot see | **SCHEDULED** - step 3, with `SELFTEST-BUDGET-FLAKE` | MEASURED 2026-08-11: 15.83s standalone, against the 25s per-hook cap `hook_health_check` applies in its weekly sweep - **63% consumed, and the hook is one of the 21 of 24 that do NOT self-budget**, so nothing would report it before a user saw `ERRORED/timed out` on a selftest that actually passes. Not hypothetical for this file: its own D10 comment records it previously measuring 25.05-25.51s against that same cap, i.e. it has been over once already. This session's additions moved it (2 real pytest invocations), and slimming the fixtures - `git init` was being called for 12 cases that only exercise `detect()`, which never shells out to git - is what brought the SUITE back under budget. **Filed because it was surfaced and would otherwise have lived only in a chat message.** The no-defer-and-forget rule is about exactly this: an item that is mentioned but has no home is indistinguishable, a week later, from one nobody noticed. Recording it as SCHEDULED is not doing the work - it is refusing to lose it. Belongs with `SELFTEST-BUDGET-FLAKE` because the durable fix is the same mechanism: extend self-budgeting past 3 of 24 |

| **`RICH-CI`** - **BUILT 2026-08-12. This row supersedes `DEPRIVED-CI` below, which was scheduled BACKWARDS.** | **BUILT** | Checking the premise before building it inverted the finding. `DEPRIVED-CI` proposed a job running the suite WITHOUT optional packages - but **no workflow here pip-installs anything, so every runner is ALREADY permanently deprived.** CI is the poor environment; the maintainer's box is the unusual one, which is why CI *caught* `OPT-1` and `FTB-1`/`FTB-6` rather than missing them. <br>**The real hole is the mirror image, and it was live for the entire life of the suite:** the code paths that REQUIRE pytest ran on NO runner. MEASURED, run `31595884191`: `2 end-to-end case(s) run (rust-decline, synthetic-rc5-wiring)` with `SELFTEST SKIP: pytest not importable` twice. The two skipped are **`rc4-broken-conftest-BLOCKS` - the regression test for the CRITICAL `FTB-RC4`** - and `genuine-failure-still-blocks`, the control proving the gate bites at all. **The suite printed that denominator honestly on every single run and nobody read it**, which is the more useful half of this finding: the instrument was not silent, the reader was. <br>Fixed with one cheap job that installs pytest, asserts pytest is genuinely importable first (or the job is a no-op wearing a green tick), and then REQUIRES `4 end-to-end case(s) run` with no `SELFTEST SKIP: pytest not importable` - because a job that passes by skipping what it exists to cover is the same "a skip is not a pass" failure the hooks themselves guard against. CI 16 -> 17 jobs. <br>The local-deprived half retains value as a pre-push check and is folded into `NEXT_SESSION_PROMPT`'s resume steps rather than kept as a separate row |
| **`CI-JOBS`** - "CI is N jobs" was hand-maintained, and I had just hand-edited it | **BUILT** 2026-08-12 | Adding the job above made the README's count 17 and I changed it BY HAND - the exact moment to stop doing that, since `CHANGELOG` records it having said 14 while CI ran more. Now DERIVED from the workflow by `check_readme_fresh`, which already owned the sibling claim. **Two independent parsers that must AGREE**, because CI installs no pyyaml and the fallback is therefore the one that actually runs there; a parser that cannot answer returns 0 and the gate FAILS on it rather than reporting the same green as one that looked. Pinned `CI-JOBS-1` and `CI-JOBS-2`. <br>**`CI-JOBS-2` came back SURVIVED first time** - the wiring test was decorative, the THIRD time this session a helper was tested thoroughly while its call site was not (`FTB-4`, `FTB-6`, this). The harness caught it, not the author |
| the mutation scratch tree was not a faithful copy | **BUILT** 2026-08-12 | `COPY_TREES`/`COPY_FILES` omitted `.github/` and `README.md`, so any gate that READS those files went red at BASELINE - the harness measuring its own missing fixture rather than a mutation. **Found in one read each time because `BASE-WHY` had landed an hour earlier**: the harness now prints the baseline's own output instead of a bare `rc=1`. That fix paid for itself inside the same session. The roster must contain what the gates READ, not only what gets mutated. Full sweep after the change: **171 of 173 executed, 0 SURVIVED, 0 unproven** |
| **`DEPRIVED-CI`** - superseded by `RICH-CI` above; kept for the reasoning trail | **SUPERSEDED** | **Proposed by the meta-review's durability check (2), and it is the missing MECHANISM behind TWO incidents rather than a new idea.** `OPT-1`: the import closure asked `find_spec("docx")`, passed here because this box has python-docx/PyMuPDF/pdfminer, and turned all 16 CI jobs red. `FTB-1`/`FTB-6`: probes depended on pytest being importable, passed here, and came back **SURVIVED** on CI. Same shape both times - *a probe whose outcome depends on what happens to be installed* - and both times the discovery mechanism was **a red CI run**, i.e. after the push. <br>The fixes so far are per-incident: OPT-1 made its closure optional-aware, FASTTEST-BLOCK made its probes synthetic. Neither stops the NEXT probe acquiring the same dependency, so by this repo's own instance-vs-mechanism rule both are instance fixes. **Durable form: a CI job (and a local make-target) that runs `run_selftests.py` AND the mutation harness under a `venv --without-pip` interpreter.** Demonstrated to work - that is exactly how `FTB-1`/`FTB-6` were confirmed fixed today, locally, in place of a third 23-minute CI round trip. Cheap: venv creation plus one suite run. <br>**Note the asymmetry it closes:** running the SUITE deprived proves portability; running the MUTATION HARNESS deprived proves the pins still BITE there. Only the second would have caught `FTB-1`, whose assertions were green on a deprived box for a reason unrelated to the property they tested |
| the gate ledger's 1-of-5-tier blindness, **re-demonstrated with this session's own evidence** | **SCHEDULED** - step 3 (priority raised) | Read, not reconstructed: `gate_runs.json` holds 200 entries, `{'run_selftests': 200}`, newest `2026-08-11T20:05:14Z`. This session ran the **mutation harness five times** (including the two pytest-less runs that are the ONLY proof `FTB-1`/`FTB-6` now bite), the **integration test**, and **three CI rounds** - and every one of them wrote nothing. So "what proved the FTB pins?" is **unanswerable from the durable record**; the evidence exists only in this ledger's prose and in a scratchpad that will be deleted. <br>Previously recorded as an abstract gap. It is no longer abstract: the gate that validated the session's headline fix is precisely the one that left no trace |

### N4. Session 2026-08-13 - PGG-PS closed, criterion 3 MEASURED for the first time

HEAD at start `d913dde`; commits `c9fc757` (PGG-PS) and `48b80fc` (step 4).

**State re-verified rather than inherited.** The session-start prompt asserted "CI green, 17
jobs"; at session start that run was still `in_progress` with 15 of 17 done. It did land green
(all 17, counted by conclusion rather than read off a badge). Suite 33/33 idle AND on a
`venv --without-pip` interpreter, both re-run.

| item | state | detail |
|---|---|---|
| **`PGG-PS`** (was HIGH) | **BUILT** | Both halves, pinned separately because they fail separately. **The prescribed fix was a HYPOTHESIS and measurement REJECTED it:** V131 named `Select-Object -First/-Last` as PowerShell status-eaters. Measured across 15 consumers, PowerShell is the OPPOSITE of sh - `$LASTEXITCODE` is set only by NATIVE executables, so `Select-String`, `Measure-Object`, `Out-File`, `Tee-Object`, `Sort-Object`, `Get-Unique` and `-Last`/`-Skip` all PRESERVE it. Flagging `-Last` would have built a criterion-3 FALSE ALARM into the fix for a criterion-2 defect. Exactly two shapes destroy the evidence: `-First`/`-Index` TRUNCATE the pipeline and tear the gate down (`$LASTEXITCODE = -1`, completion marker ABSENT - worse than sh, since there is no verdict to discard), and a native consumer like `findstr` (3 became 0, a silent green). `sort`/`tee` are PowerShell ALIASES for preserving cmdlets and are exempted there while staying eaters in sh. Pinned `PG6`/`PG7`/`PG8`/`PGG-PS-1`; `PG4` REPOINTED (sixth anchor drift, caught by `check_mutation_anchors` in seconds) |
| **STEP 4 / criterion 3** | **BUILT, PARTIAL - and the partiality is PRINTED** | `tools/score_false_alarms.py` + `tests/false_alarm_corpus.py`, registered as gate `false-alarm-scorer` (suite 33 -> 34). **First measurement:** `piped_gate_guard`, `plan_defer_guard`, `numbers_match_on_write`, `timing_claim_guard` all **0.0%** on 15 ordinary entries, each with a FIRING control. Four Stop-class hooks (`show_your_proof`, `meta_audit_on_stop`, `memory_hygiene_guard`, `fast_test_on_stop`) are **UNMEASURED** - no control yet, and the tool refuses to print 0% for a hook it has not shown to be reachable. SessionStart's three are NOT DRIVEN, with the reason printed: they audit the machine's configuration, not the user's work |
| **`timing_claim_guard` ignored `UNBLUFF_STATE_DIR`** | **BUILT** | The ONLY stateful hook that did - a module-level constant overridden solely inside its own selftest, while all five twins read the variable. Three consequences, all observed: no harness could isolate it (its marker survived between scorer runs and silenced the control on every run after the first); measuring it WROTE INTO THE USER'S REAL `~/.claude/state`; and its default directory differed from its twins' (`.claude/state` against `.claude/hooks/state`) |
| **the fire ledger as EVIDENCE is weaker than it looks** | **CORRECTED HERE** | Snapshot with an explicit CUTOFF, because the ledger is a LIVE producer and a bare date does not reproduce: entries with `ts <= 2026-08-13T11:24:36`, which is 2043 records over 8 days (re-derived at 12:5x the same day it read 2198 - the delta is this session's own edits). At that cutoff: `proof` 6/278, `audit` 2/278, `defer` 3/1765, and `numbers`/`timing`/`memory`/`test` all ZERO. **That zero is not what it appears.** The dispatchers record each sub-hook's EXIT CODE, and `timing_claim_guard` is ADVISORY - stderr plus rc 0. So "0 fires in 1252 invocations" means never BLOCKED, not never fired. **Retiring a guard on that number would have been retiring it on a false zero** - the trap the Opus-5 item warns about, in a form it did not anticipate. The ledger is also a LIVE producer (it gained a record mid-read), so every count off it is a snapshot |
| **`LEDGER-POLLUTION`** | **SCHEDULED** | `~/.claude/hooks/state/fire_ledger.jsonl` holds 2 records (2026-08-12T11:22) whose sub-hook is `newg`, with `crashed: ModuleNotFoundError: No module named 'new_guard'` and `cwd: ""`. `new_guard` is a deliberately nonexistent module used by `post_tooluse_dispatcher`'s selftest to exercise crash handling - so a selftest escaped its temp-dir isolation and wrote to the REAL ledger. Small (2 of 2043), but the mechanism is the point: the plan's Opus-5 item says to READ this ledger rather than reason about it, and an instrument that test runs can write to is not a clean evidence base. The only tell is `cwd: ""` |
| **`LEDGER-8`** - the 8 remaining findings were NOWHERE enumerated | **RECONCILED** | N3's row "the remaining 8 confirmed findings" lists clusters (a)-(f), but FIVE of the six are marked **BUILT in the same table** (a+c = `FTB-SPELL`, b = `FTB-CFG`/`FTB-LAYOUT`, d = `FTB-GATES`, e = `ROSTER-DERIVE`). It is a stale snapshot of what the pass FOUND, never updated as items were fixed hours later the same session. Criterion 2's stopping rule needs a DEFINED population with recorded severities, so "8 remain, all MEDIUM/LOW" was uncheckable against a list that did not exist. Derived from `adversarial_review_2026-08-12.md` BY ROW: **L23** `review_runs.json` omits the 2026-08-06 guards run (MEDIUM); **L34** stale detection claims - two docstrings, `.claude/fast-test.cmd`, no CHANGELOG entry (MEDIUM); **L35** C2 false, the push-gate selftest built on that misclassification (MEDIUM); **L37** `_sh_delegation_fails` can emit three contradictory statements (LOW); **L38** `_open_count()` maps an ABSENT `open` field to 0 across 45 of 68 entries (LOW); **L39** `_has_pytest_config`'s marker check unpinned (LOW); **L40** the three-state cap unpinned (LOW). Seven identified with confidence, **none CRITICAL or HIGH - so the CONCLUSION (step 3 is closeable) survives; the PREMISE did not** |
| **`DENOM-SETTLED`** - 25 / 24 / 22 | **RESOLVED, not a contradiction** | Computed, not transcribed. **25** = every `.py` in `hooks/`. **24** = 25 minus `selftest_budget.py`, which correctly excludes ITSELF (it cannot budget itself) - that is `budget_coverage()`'s denominator. **22** = 25 minus the three `*_selftest.py` test modules, and identically the count carrying a quoted `"--selftest"`. All three are correct over different populations; the gap was that nothing recorded WHICH is which. **None is the right denominator for a false-alarm rate** - that population is "hooks that can fire on user work", a FOURTH number the scorer derives and prints |
| **`FA-MEMHYG`** - reported as a defect, then **REFUTED BY MEASUREMENT** | **FINALIZED-EXCLUSION** 2026-08-13 | `memory_hygiene_guard` emits *"could not check this project's memory: no memory dir"* on a turn ending in a clean project, and the scorer measured it at **100%**. **The severity claim was WRONG and the fix was nearly built.** The original row here said "every turn end"; MEASURED over three consecutive turns sharing one session, turn 1 fires and turns **2 and 3 are SILENT** - the notice is already bounded by a once-per-session marker. The 100% was an artefact of the SCORER, which gives every corpus entry a fresh state dir (rule 2) and thereby defeats the very suppression that bounds it. <br>The behaviour is DELIBERATE and the code says why: *"Silence here was the bug: a sanitization mismatch disabled the hook permanently and looked exactly like a healthy project."* Emitting an inconclusive notice once per session is this repo's own rule that a check which CANNOT RUN must say so. **Excluded as by-design, not scheduled as a defect.** <br>**The real finding was in the INSTRUMENT:** the scorer reported per-invocation objection while the thing that gets a guard switched off is NAGGING. It now measures both - re-running each false alarm with the SAME state and session - and reports "once per session, then SILENT" separately from "NAGS". Under that distinction the suite has **ZERO nagging false alarms**. Pinned `FA-3`, which SURVIVED its first pin (hollow mode 3: the probe exercised a helper while the mutation hit the call site) and was repointed to an extracted `repeats_in_session()` |
| **`MUT-CONC` / `MUT-HANG` gained two MEASURED requirements** | **SCHEDULED** (unchanged, better specified) | Killing an in-flight sweep showed the harness has (1) NO process-group teardown - a `-m pytest` grandchild and a scratch-dir python SURVIVED the parent kill and had to be killed by hand - and (2) NO crash-safe cleanup: 26 scratch dirs were orphaned in TEMP because the `finally: shutil.rmtree` never ran. Both are what `tooling-discipline` section 3 requires a sentinel for. The repo was verified CLEAN after the kill: the harness works on `mkdtemp` copies and never mutates in place |
| a **wrapper exit code** was nearly believed | noted | The background-task notification for the killed sweep reported *"completed (exit code 0)"* - the wrapper shell's status, not the sweep's. The file said `SWEEP_EXIT=127`. Believing the notification would have recorded a killed run as a pass: `piped_gate_guard`'s own defect class, arriving through a different door |

**RE-ESTIMATE after step 4, as the plan demanded.** Step 4 was "the largest unknown". Its BOUNDED
half is done and cost roughly half a session: the scorer, the corpus, the gate, two pins. What it
revealed is that the remaining half is bigger than "write more corpus entries" - four Stop-class
hooks need controls, and a control for `fast_test_on_stop` or `show_your_proof` means planting a
realistic failing-test repo and a realistic transcript, not a two-line fixture. **Criterion-3
tail: one further session.** The overall remaining estimate stays **6 sessions** - step 4 came in
near budget, and the three new SCHEDULED rows above are small and land inside step 3's existing
tail rather than adding to the count.

### N3. The INDEPENDENT adversarial pass, 2026-08-12 - run `wf_a6b49ecf-667`

The pass this plan had owed since 2026-08-01, run once the weekly budget reset. 7 lenses,
refuter stage UNCAPPED, 56 agents, 6.84M subagent tokens, 46 min. **Coverage: 49 produced, 49
adjudicated, 0 dropped, `coverage_complete: true`; 24 confirmed, 25 refuted.** Tree guard: zero
repo writes. Full matrix: `docs/audits/adversarial_review_2026-08-12.md`.

**It immediately justified itself: it found a defect FASTTEST-BLOCK INTRODUCED, in the more
dangerous direction than the one it removed.**

| item | state | evidence |
|---|---|---|
| **`FTB-RC4` (CRITICAL) - the rc-4 waiver turned a CAUGHT REGRESSION into a silent green** | **BUILT** 2026-08-12 | pytest rc 4 was waived as "could not answer". It is not. Re-extracted from pytest: with the argv `detect()` HARD-CODES (`-m pytest -x -q`, no user flags) a bad-CLI usage error is **unreachable**, so rc 4 here can essentially only mean the user's own `conftest.py` or ini failed to load - measured as SyntaxError, ModuleNotFoundError, a raising `tests/conftest.py`, and a bad `addopts`, with **ZERO tests running in every one**. `conftest.py` is a `.py` file and is in this hook's OWN `SRC_EXT`: it is precisely the code the gate exists to verify. <br>**Measured A/B through the real hooks:** `app.py` regressed so the suite genuinely fails - with a broken `conftest.py` present, hook **rc 0** (silent green) and the push gate allowed with "NOTHING VERIFIED"; remove only the conftest and it is **rc 2** with pytest's traceback. <br>**The suite ENSHRINED it:** the broken-conftest case ASSERTED rc 0, so running it could never object - the identical failure mode corrected in `case 3` earlier the same session, reintroduced hours later in new code. Case inverted to require rc 2 + FAILING. <br>**Prescribed fix treated as a HYPOTHESIS and rejected as over-built:** it proposed splitting rc 4 by string-matching `"ImportError while loading conftest"`. Since the argv is fixed, every reachable rc 4 is the user's problem, so the match buys nothing and adds a fragile parse. rc 4 is simply out of the map. rc 2/3 stay out too, deliberately: both mean nothing was proven, and blocking is the safe direction. <br>Pinned `FTB-7`, CAUGHT on a pytest-present AND a pytest-less interpreter |
| **`FTB-MASK` (HIGH) - one notice permanently masked every later, DIFFERENT one** | **BUILT** 2026-08-12 | `_notice_no_gate` emits two materially different messages - "add a test gate" and "this IS a pytest project but pytest is not importable by `<interpreter>`" - and keyed its once-per-project marker on the **path alone**, so whichever fired first silenced the other forever, with nothing in the code to clear it. The second is the one that tells a user their gate is dead. <br>**The refuter found an amplifier the finder did not claim:** the same path-only keying meant a project that had emitted the rc-5 notice was silent for rc 4 **from turn 1**, not merely from turn 2 - so design claim C4 ("the notice paths are never SILENT") was false even in the first-turn case it was supposed to guarantee. <br>Fixed by keying both marker families on `(path, REASON)` via `_reason_slug`, with `_nogate_reason()` as the single definition so the text printed and the reason suppressed cannot drift. Pinned `FTB-8`, CAUGHT on both interpreters |
| **`FTB-SPELL` - `py.test` and `pytest-3` escaped the classifier, so FASTTEST-BLOCK survived VERBATIM for those spellings** | **BUILT** 2026-08-12 | `_is_pytest_command` was a whole-word substring search, and it was wrong **both** ways. It MISSED `py.test` - pytest's OWN still-shipped console script - and `pytest-3` / `pytest-3.11`, which is what Debian and Fedora install; an unrecognised pytest command falls through to the blanket `rc != 0 -> FAILING` branch, i.e. the original defect, live, in both gates. <br>**The other direction was found by REPAIRING THE CONTROLS, not by the finding.** The review said the C2 control loop was decorative - none of `npm test` / `go test` / `cargo test` contains the substring `pytest`, so even a naive substring match passed it. Rewriting every control to CONTAIN the substring and still require rejection immediately exposed a false POSITIVE the old regex also had: `/opt/pytest/bin/collect` matched on a **directory** named pytest, which would have waived an unrelated tool's genuine rc 5. <br>Fixed by asking the real question - is any TOKEN's basename the pytest executable - rather than searching the raw string. `-m pytest` still lands, because the module name is its own token. <br>`FTB-5` had to be **REPLACED, not supplemented**: its anchor pointed at the regex line the fix deleted, and a mutation whose anchor has drifted is a pin that has silently stopped pinning. New `FTB-9` pins the basename derivation itself. Both CAUGHT; suite green on a pytest-present AND a pytest-less interpreter |
| **`FTB-CFG` + `FTB-LAYOUT` - detection left GENUINE pytest projects ungated (false negatives)** | **BUILT** 2026-08-12 | Two independent gaps, same consequence: a false negative silently DISABLES the gate, which is the failure mode the FASTTEST-BLOCK fix promised not to trade into, while `README:76`/`:227` assert the strong form ("auto-detects pytest"). <br>**`FTB-CFG`:** `_PYTEST_CONFIG_MARKERS` held **4 of pytest's 7** canonical `config_names` (re-extracted from `_pytest.config.findpaths.locate_config`). Missing `.pytest.ini`, and `pytest.toml` / `.pytest.toml` - the latter added in **pytest 9.0 as the HIGHEST-precedence config file, authoritative even when EMPTY**, so the gap was widening with each release rather than shrinking. Measured: a directory holding only `pytest.toml` plus a root `test_app.py` runs `1 passed`, and unbluff refused to gate it. <br>**`FTB-LAYOUT`:** detection demanded a directory literally named `tests`, rejecting four layouts pytest collects and passes (raw rc 0 on each) - a root-level `test_app.py` with no tests/ dir, `test/` SINGULAR, tests colocated beside the code, and the monorepo shape (`main()` anchors `detect()` on the repo TOPLEVEL, so that one is normal, not contrived). <br>**The fix is SIMPLER than the one prescribed.** The finding proposed enumerating more directory names; asking instead "does this repo contain a file pytest would COLLECT" collapses singular/plural/colocated/monorepo into one bounded, vendor-pruned walk. The monorepo case then fell out for free - and was ASSERTED rather than claimed. 15 accept-shapes pass, all 5 decline-shapes still decline, so the false-alarm half is intact. Pinned `FTB-10`, `FTB-11`, `FTB-12` |
| **`FTB-GATES` - the two gates disagreed, and the push gate's message was FALSE** | **BUILT** 2026-08-12 | Both gates consume the same `detect()`, which declines for two very different reasons. The Stop gate named which; the push gate printed *"has no test command - nothing to verify"* for BOTH - so a real pytest project whose pytest the interpreter cannot import was told something untrue at the RARER, HIGHER-STAKES moment, and the gate's own docstring asserted the false premise outright ("a repo with no tests has nothing to gate" - the repo has tests). **Not exotic:** the installer embeds the interpreter it was run with, so on any machine whose pytest lives in a project venv, EVERY pytest project took this path. <br>Fixed by routing through `_nogate_reason()` - the shared helper already built for `FTB-MASK` - so the fix was mostly deletion and the two gates cannot drift apart again. Docstring corrected. Pinned `FTB-GATES` |
| a second **drifted mutation anchor**, caught mechanically | **BUILT** 2026-08-12 | Rewriting `looks_like_pytest_project` deleted the line `FTB-1` anchored to, and `check_mutation_anchors` failed with *"nothing short of a full ~25-minute sweep would have said so"*. Repointed to express the same defect against the new code. **Second time this session** a pin needed REPOINTING rather than supplementing (`FTB-5` was the first, when the `_is_pytest_command` rewrite deleted its anchor). A mutation whose anchor has drifted is a pin that has silently stopped pinning, and it is indistinguishable from a healthy one until the sweep runs - which is exactly why the cheap anchors gate exists |
| **`FTB-MARKER` + `FTB-CAP`** - config markers matched inside comments, and the cap measured repo SIZE | **BUILT** 2026-08-12 | `_has_pytest_config` did a raw SUBSTRING search, so a `pyproject.toml` that merely MENTIONS `[tool.pytest]` - listing pytest as a dev dependency, or a comment explaining why it is NOT used - read as DECLARING a pytest project. Every one of these markers is a TOML/INI section header, so line-anchoring is the grammar, not a heuristic. Also switched to `utf-8-sig`: `_read_override` already used it, and a BOM hides exactly the first line where a section header lives. **The BOM case passed BEFORE the fix** (a substring match finds a marker anywhere) and is kept as an accept-shape precisely because the line-anchoring could silently break it - the same control reasoning that found the pre-existing `setup.cfg`/`tox.ini` false negatives. <br>**`FTB-CAP` was made WORSE by this session's own `FTB-LAYOUT` fix**, which widened the walk from `tests/` to the whole repo: counting every file turned the cap into a measure of repo SIZE, so a large tree of images or JSON would hit it, return `None`, and be ACCEPTED as a pytest project on no Python evidence at all. The cap now counts only what the search is looking for. Fixing one finding raised the severity of another |
| **four distinct ways a pin can be HOLLOW** - all four observed this session | **BUILT** as a checklist | Worth carrying, because each was found by a different mechanism and none by review. **(1) Green for an unrelated reason** - `FTB-1`: `detect()` returns None when EITHER half declines, so on a pytest-less box a broken detector answered exactly what a correct one did. **(2) Skipped on the machine that runs the mutation** - `FTB-6`: third-state-skipped on pytest availability, which is every CI runner. **(3) Helper tested, CALL SITE not** - `FTB-4`, `CI-JOBS-2`: every branch of the helper green while nothing asserted that anything CALLS it. **(4) A branch no fixture can REACH** - `FTB-14`/`FTB-15`: hitting the cap needed >5000 `.py` files, so the mutation could not be PLACED and was unfalsifiable; the repo's own rule ("score it as survived, never skipped") is the only reason it was visible. Fixed by making the cap injectable so a fixture reaches it in three files rather than five thousand. <br>**(1) and (2) were found by CI, (3) and (4) by the mutation harness, none by reading.** That is the argument for both instruments in one line |
| **`ROSTER-DERIVE`** - install's seed was DECLARED behind a docstring saying DERIVED | **BUILT** 2026-08-12 | INSTALL-TAUTOLOGY's shape, in the SAME function. That fix replaced the tautological glob with an AST closure and left `REQUIRED_HOOKS` as the sole seed, so **7 of 25 hooks reached the roster only because someone typed them there** - the dispatchers load sub-hooks by `importlib.import_module(<string>)`, and a string handed to importlib is not an import statement. `dispatcher_subhooks()` now reads both `HOOKS` tuples out of the dispatchers' ASTs; it derives exactly those 7. `REQUIRED_HOOKS` is KEPT as a floor, because it is the only thing covering a dispatcher whose own file is missing. <br>**The refuter's severity correction was right and mine would have been wrong:** finder said HIGH, refuter said MEDIUM because coverage is correct TODAY - and the union is still 16 names, confirming it. **No user on any shipped commit was exposed.** The guarantee was unsound; the state never was. "We were lucky" and "we were right" are different claims. <br>The repo had already written the answer: `V131_REVIEW_PLAN.md:2027` describes this exact walk. It lived in a document and not in the code - REMEMBER vs ENFORCE, inside the function whose previous version was diagnosed with that same sentence. Pinned `RD-1`, `RD-2` |
| **`WT-CAUSE`** - a broken FIXTURE was reported as "the box cannot make a worktree" | **BUILT** 2026-08-12 | `wt_ok` was ONE boolean set False by any of three git commands; only the third justifies UNAVAILABLE. This file's own `_sh_site` docstring draws exactly that line - *"a fixture that LOOKED and found nothing must FAIL - not a box that cannot be asked the question"* - and the code beside it did the opposite. <br>MEASURED both ways by pointing `gpgsign` at a nonexistent gpg: **before** = `SKIP: git worktree unavailable`, 2 of 3 sites, `SELFTEST OK`, **exit 0**; **after** = `SELFTEST FAILED` quoting git's own stderr. The old message was false about the machine, and scenarios 17/18 (worktree delegation; `install()` in a linked worktree, the case that used to CRASH) went unrun. Being an internal skip rather than `SKIP_RC`, `run_selftests`' "a skip is NOT a pass" rule never saw it and the run counted as one of the 33 OKs. <br>Fixing it exposed the sibling finding live: the message ASSERTED "no POSIX shell was found" while the line above printed the shell it had just found. It now says only what it KNOWS; each recorder supplies its own cause. Pinned `WT-1` |
| **a FIFTH way a pin can be hollow** | **BUILT** as a checklist entry | `WT-1` came back **SURVIVED while the probe was working perfectly** - reproducing the mutation by hand caught it, contradicting the harness, and that contradiction was the only signal. The entry omitted the **6th element naming the VERIFY TARGET**; this unit is a selftest MODULE with no `--selftest` of its own, so the harness applied the mutation and measured it against something that verifies nothing. **Mode 5 is the nastiest: the probe and the mutation are both CORRECT, only the wiring between them is wrong.** Full list now - (1) green for an unrelated reason, (2) skipped on the machine running mutations, (3) helper tested but not its call site, (4) a branch no fixture can reach, (5) measured against the wrong verify target |
| anchor drift is now **measured, and produced a RULE** | **BUILT** 2026-08-12 | Five drifts (`IT-1` twice, `FTB-5`, `FTB-1`, `SH-2`), four in one session, **every one caught by the seconds-long `check_mutation_anchors` gate** rather than a 25-minute sweep or by reading. `SH-2`'s was the instructive one: its anchor spanned a condition AND the prose beneath it, so it broke when a COMMENT was inserted between them. Anchors now point at the CONDITION alone. **An anchor that quotes prose drifts every time the prose is corrected** - and correcting prose is most of what this repo does |
| when a guard fires on your code, **MEASURE which of the two it is** | **BUILT** as a rule | Both outcomes occurred this session and assuming either would have got one wrong. `CAP-FP-1`: probed with controls in both directions and confirmed a genuine DETECTOR defect (its own clauses 1 and 2 exclude a counter bound in a bool-returning function). The `WT-CAUSE` truncation: NOT a false positive - the same file already carries `(p.stderr or "")[:160]` unflagged, so the difference was a convoluted `((A or B).strip() or C)[:200]` defeating type inference. Rewritten clearer, guard satisfied **honestly - no exemption, no suppression** |
| pytest **rc 3 (`INTERNAL_ERROR`) still BLOCKS**, and that is deliberate | **FINALIZED-EXCLUSION** 2026-08-12 | A confirmed MEDIUM from the pass: rc 3 is, by pytest's own definition, not a verdict about the user's code, and it still hard-blocks the turn end and the push. **Decision: leave it blocking**, for three reasons. (a) `FTB-RC4` is the direct evidence that waiving a code that "is not really a failure" is the more dangerous direction - that waiver turned a caught regression into a silent green. (b) rc 3 means pytest itself broke, so ZERO tests ran; blocking with pytest's own traceback is more actionable than a once-per-project notice a user may never see again. (c) It is not a false alarm on CORRECT code, which is the only thing criterion 3 asks this map to prevent - an internal pytest error is a real problem in the user's environment. <br>**Recorded because it was decided in conversation and written down nowhere** - found by this pass's home-check, which is the same failure mode `SELFTEST-BUDGET-FTOS` was caught by the day before. A decision that exists only in a transcript is indistinguishable, a week later, from an item nobody considered |
| **`VERIFY-TARGET-GATE`** - hollow-pin mode 5 is currently PROSE, not a mechanism | **SCHEDULED** - step 3, cheap and high value | The meta-review's durability check. Modes 1-4 are surfaced by the harness itself (it scores an unplaceable mutation as SURVIVED). **Mode 5 is not: `WT-1` was applied and then measured against `pre_push_gate_selftest.py --selftest`, a module with NO entry point, so it verified nothing and reported SURVIVED while the probe worked perfectly.** Nothing detects that class; the five-mode list in this ledger is a checklist a human must remember, which is the REMEMBER-vs-ENFORCE failure this repo has a standing rule about. <br>**Durable form, ~15 lines:** for every `MUTATIONS` entry, assert its VERIFY TARGET resolves to a file that actually exposes `--selftest` (or is explicitly exempt). It belongs in `check_mutation_anchors`, which already walks every entry, costs seconds, and is the gate that caught all five anchor drifts - so the marginal cost is one more assertion in a pass that already runs |
| **the 800-line rule is now broken by FIVE files, and this session widened it** | **SCHEDULED** - step 3, with the line-count gate | Re-measured 2026-08-12: `tools/mutation_check.py` **1263**, `hooks/pre_push_gate_selftest.py` **1109**, `hooks/fast_test_on_stop_selftest.py` **1003**, `install.py` **864**, `hooks/fast_test_on_stop.py` **832**. Was three files; is now five, and every one of the increases is mine. The prescription is unchanged and correct - **build the line-count GATE, then split** - but the trend is the argument: a rule enforced by nothing degrades monotonically while every individual addition looks justified, and four of these five grew in a single day |
| **`SHIP-BAR-GATE`** + the gate ledger as its ENABLER | **SCHEDULED** - before v1.4.0 | From the 2026-08-12 rework's meta-review. Two of the four rework items are ENFORCEABLE and two are judgment. **(a) The stopping rule can be a gate:** read the ledger, fail if any row is CRITICAL/HIGH and not BUILT - that turns the v1.0 ship bar from a promise into a control. **(b) Verify-before-pushing can be a gate too, but is BLOCKED on the gate ledger:** a pre-push hook cannot run a 30-minute sweep, but it CAN require a RECORDED sweep newer than the last source change - and `gate_runs.json` records only `run_selftests`. That promotes the 1-of-5-tiers finding from record-keeping to **the enabler for the rework's most important rule**. The reordering and the ceremony rule stay JUDGMENT: sequencing is not mechanically checkable, and a test-lines-vs-product-lines heuristic would fire on correct work, which is how a guard gets switched off |
| the remaining **8 confirmed findings** | **SCHEDULED** - step 3, triaged not swept | Deliberately NOT fixed in one silent sweep. Highest-value clusters, each with its own evidence in the review report: (a) `_is_pytest_command` misses **`py.test`** - pytest's own still-shipped console script - and `pytest-3`, so FASTTEST-BLOCK survives VERBATIM for those spellings in BOTH gates; (b) `looks_like_pytest_project` rejects three of the most common genuine pytest layouts and `_PYTEST_CONFIG_MARKERS` recognises **4 of pytest's 7** config filenames, so real projects silently get no gate while `README` claims "auto-detects pytest"; (c) the C2 control loop is **decorative** - none of its three commands contains the substring `pytest`, so a substring match would pass it; (d) the two gates DISAGREE about a pytest project whose pytest is unimportable; (e) `install.py`'s roster is DECLARED not DERIVED - 7 of 25 hooks reach it only via the hand-written `REQUIRED_HOOKS` tuple because the dispatchers load them by `importlib.import_module(<string>)`, invisible to an AST walk (severity corrected HIGH -> MEDIUM: coverage is right *today*, the derivation is not, and the repo's own `V131_REVIEW_PLAN.md:2027` already describes the walk that would fix it); (f) `review_runs.json` omits the entire 2026-08-06 guards run, so "the 42 is the complete population" is complete only over what was recorded |
| what the pass says about the METHOD | - | **The author's probes were wrong in the author's blind spot, exactly as rule 6 predicts.** Both headline design claims - C1 (rc 4/5 never carry a verdict) and C4 (notices are never silent) - were FALSE, and the suite asserted the wrong direction on the first. The caveat carried on 2026-08-11 ("12 shapes passed", never "no false alarm remains") was correct and load-bearing. **25 of 49 were refuted**, several with severity corrected downward, which is the refuter stage doing its job rather than a sign the lenses were noisy |

### N2. Found by auditing the AUDITS, 2026-08-11

Prompted by being asked whether the close ritual was actually completed. It had been
INVOKED in full - all four skills, via the Skill tool - but not COMPLETED. **All FOUR were
partial, not three** (an earlier draft of this row said three, which flattered the author;
the consistency pass caught it):

| skill | what was skipped |
|---|---|
| consistency-audit | STEP 1 - the bundled `scripts/audit.py`, replaced with a targeted derivation of that day's figures |
| completeness-audit | STEP 1 - the soft-defer marker sweep |
| source-coverage | STEP 5 - re-verify no optional-forever language and confirm the ledger is current |
| meta-review | checks 1 (parked-but-unscheduled) and 5 (improvements) |

Running the skipped steps afterwards found the rows below - so the omissions were not
harmless, which is the whole argument for completing a procedure rather than invoking it.

| finding | state | detail |
|---|---|---|
| **`close_skills_guard` verifies INVOCATION, not COMPLETION** | **SCHEDULED** - step 3 | It correctly blocked two premature closes today by detecting that a skill had not been invoked since the last user message. It cannot detect a skill that was invoked and then only half-run - which is exactly what happened, and was found by a human asking rather than by any gate. This is the repo's own defect class applied to its own close ritual: a check that confirms the ritual STARTED and reports that as the ritual HAPPENING. Any fix must avoid the obvious trap of having each skill self-report completion, since a skill that lies about finishing is the same defect one level down |
| **the four audits have no defined ORDER, and the order matters** | **SCHEDULED** - step 3 | `meta-review` was run FIRST in this pass, so it never saw `MUT-HANG` - a finding the later audits produced - even though meta-review is the synthesising pass whose job is to weigh exactly that. The plan says "invoke the four" and names no sequence. Correct order is consistency -> completeness -> source-coverage -> **meta-review last**, and the plan should say so rather than leaving it to whoever is running it |
| a live re-instance of `CA-SELFREF` | **SCHEDULED** - step 3 (unchanged) | The bundled script flagged `[E] placeholder` at `NEXT_SESSION_PROMPT.md:235`. Adjudicated FALSE POSITIVE: the `[]` sits inside the plan's own sentence *"consistency found a live `[]` placeholder"*. The tool flags a document that DESCRIBES the tool. Second recorded instance; the finding already exists in section B |

### N1. Newly surfaced by step 3 - SCHEDULED, not fixed

| gap | state | detail |
|---|---|---|
| `readme-fresh` gates the selftest COUNT but not the LIST | **SCHEDULED** - step 5 | Adding the 33rd gate turned it red on the count, and rebuilding the transcript revealed it had been stale **by six gates** - `cap_shapes`, `cap_types`, `piped_gate_guard`, `timing_claim_guard`, `corpus-scorer` were listed nowhere while the gate reported OK. Same family as the ungated "CI is N jobs" number already scheduled there. Verified at close that the list now matches a real run exactly, in both directions |
| **`SELFTEST-BUDGET-FLAKE`** - **BUILT 2026-08-12.** It stopped being theoretical: it broke unbluff's OWN CI. Run `31593005560`, the `windows-only mutations` job, went red with `HARNESS ERROR: baseline already RED` for `hook_health_check #C4` - while its neighbour `#C5` passed its baseline **in the same second**, and it did not reproduce locally (7.09s, rc 0, 70% of its share). Transient, load-dependent, and it failed a whole job. <br>**Fixed with a CONTROL, not a looser threshold** - the row below is explicit that loosening is wrong, because a selftest genuinely over its share of the 25s cap IS reported to users as ERRORED. `report()` now times a fixed CPU-bound loop against a reference measured idle (`0.0123s`, median of 7, spread x1.08) and normalises the budget by how much slower the box actually is. **Three states, all exercised by pinned probes:** normalised-under = ok; raw-over-but-normalised-under = **INCONCLUSIVE, said out loud and NOT counted as a pass**; normalised-over = a genuine overrun that still FAILS. The factor is floored at 1.0 and CAPPED at 6x so a pathologically slow box cannot scale the budget to infinity and silently disable the check - and when the cap binds, it says so. Pinned `SB-1` (control removed -> raw wall clock) and `SB-2` (cap removed -> unbounded), both CAUGHT. <br>Also fixed in the same commit: **the harness reported `baseline already RED` without saying WHY**, so this failure had to be diagnosed by inference from neighbouring timestamps rather than read from the log. It now prints the baseline's own output - a checking instrument that cannot explain its own failure is the class this repo exists to catch |
| the original `SELFTEST-BUDGET-FLAKE` record, kept for its measurements | superseded by the row above | **MEASURED 2026-08-11, interleaved against a control as this repo's own timing rule requires.** Under load (suite run back-to-back with a queued mutation sweep) the two slowest units failed their budgets: `hook_health_check` 10.81s vs 10.00s, `meta_audit_on_stop` 19.63s vs 17.50s. **CONTROL: both pass in isolation (rc 0 each), and the full suite is 33/33 on an idle machine.** The underlying concern is REAL - a selftest exceeding its share of the 25s cap `hook_health_check` applies in its weekly sweep genuinely IS reported to users as ERRORED - so the gate must not simply be loosened. The defect is that it asserts a duration with no control, which is the exact class this repo has a standing rule about. **Two consequences:** it is a FALSE ALARM on a user's loaded machine (criterion 3's subject, alongside `FASTTEST-BLOCK`), and it makes a green suite non-reproducible, so "33/33" is not evidence unless the machine was idle. <br>**Two things the tool says about ITSELF, found in the same output and worth acting on together:** `budget coverage: 3 of 24 selftestable hook(s) self-budget` - the mechanism covers an eighth of its population - and `UNREVIEWED: hooks/selftest_budget.py - never adversarially reviewed`. So the gate that just false-alarmed is both narrowly applied and self-declared unreviewed. It is a candidate for the independent pass already owed on the R1 dispositions |
| a live re-instance of the "HARNESS ERRORs count as executed" finding (M2) | **SCHEDULED** - step 3 | `IT-1`'s anchor drifted the moment the walk was extracted into `_import_closure`. The harness reported HARNESS ERROR rather than passing quietly - which is the only reason it was caught - but still printed "6 of 6 mutations executed" over a run in which one proved nothing |

---

## M. INDEPENDENT adversarial review of step 2 - run `wf_feb7202e-8fe`

The repo's own rule 6: *never let the author write the only probe.* Step 2 changed a CHECKING
INSTRUMENT, and its author wrote its only probe, so this was non-negotiable. 4 lenses
(guard-cannot-fail, resolver-correctness, mutation-harness-routing, platform-portability),
28 agents, ~3.0M subagent tokens, 29 minutes.

**Coverage: 24 findings produced, 24 adjudicated, 0 dropped, `coverage_complete: true`. 14
confirmed, 10 refuted.** Tree guard: snapshotted before, diffed after, **0 agent writes**.

**It paid for itself immediately - three CONFIRMED defects in step 2's own new code**, every one
a property the guards ASSERTED in prose but did not PIN with a check. **Precision about what is
measured here:** that the properties were unpinned is demonstrable from the old probe bodies (no
order assertion, no extension-less layout, the numerator never checked). That a mutation of each
"would have survived on every platform" is MEASURED only for the extension-less candidates - the
review's refuter demonstrated that one - and is inference for the other two. Stated as inference
rather than left to read as measurement:

| defect | state | evidence |
|---|---|---|
| `_resolve_sh` preferred Git's RAW `usr/bin/sh.exe` over the environment-setting `bin/sh.exe` | **BUILT** (fixed) | Independently re-measured from a clean PowerShell: raw -> `COREUTILS_MISSING`, wrapper -> `COREUTILS_OK`. **The first attempt at this measurement was CONFOUNDED** - run from the Bash tool, which IS a Git Bash session, so the child inherited the environment and both looked fine. Check the control before believing the subject. Pinned by mutation `SH-5` |
| the two extension-less candidates `("bin","sh")` / `("usr","bin","sh")` were asserted by NOTHING | **BUILT** (fixed) | Every layout in the probe named a `.exe`, so deleting the POSIX pair survived everywhere while the guard printed a full denominator. Probe now carries `posix-usr` and `posix-local` layouts. Pinned by `SH-6` |
| the printed numerator could be WRONG, even NEGATIVE | **BUILT** (fixed) | It subtracted skipped/missing names from a total those names need not belong to. Now an intersection, extracted to the pure `_sh_delegation_line`, and the **printed number** is asserted for all 8 accounting ledgers - previously only the verdict was probed. Pinned by `SH-7` |
| **a FALSE ALARM step 2 introduced:** `git worktree` unavailable was reported as a selftest FAILURE | **BUILT** (fixed) | It would turn a missing git feature into a red suite and every `pre_push_gate` mutation into a HARNESS ERROR on such a box - directly against criterion 3. Fixed with a TRI-STATE (`True` / `False` / `None`=UNAVAILABLE), matching this repo's existing distinction between "I could not look" and "there is nothing to look at" |

### M1. The limit on step 2's own evidence - CONFIRMED, and it contradicts what was claimed

| finding | state | detail |
|---|---|---|
| **The git-ancestor-walk branch of `_resolve_sh` executes on NO CI runner** | **SCHEDULED** - step 3 | **Confirmed against PRIMARY evidence, not just the reviewer's claim.** The `windows-latest / py3.12` job log of run `31304861194` prints: `[sh-delegation] shell: C:\Program Files\Git\bin\sh.EXE (1 candidate(s) probed)`. One candidate means `shutil.which("sh")` returned immediately - `sh` IS on PATH there - so the git-ancestor walk is **never exercised in CI**. Section D cites three green `integration` jobs as step 2's evidence; that evidence does NOT cover this branch, which runs on the author's box only. **This was the single claim flagged as weakest BEFORE the review, and it was the one that broke.** <br>**The sharper consequence:** CI's PATH yields `bin\sh.EXE`, the CORRECT wrapper, while a box without `sh` on PATH falls through to the walk and got the RAW shell. The wrong-shell defect above could therefore only ever manifest OFF CI - green runners were structurally incapable of catching it. Closing this needs a fixture that hides `sh` from PATH and asserts the git branch resolves |

### M2. Confirmed but PRE-EXISTING - not step 2's code, scheduled not fixed

| finding | sev | state | detail |
|---|---|---|---|
| `_child()` runs the SELFTEST module, not the gate | HIGH | **SCHEDULED** - step 3 | `__file__` is the selftest's own path (the namespace snapshot deliberately skips dunders) and that module has no `__main__` block, so the child always exits 0 in 0.08s. **Check 14 is therefore wholly decorative** - the refuter applied mutation #10's exact edit and the suite still printed SELFTEST OK. The refuter added three the finder missed: mutation #10's in-code claim that "the twin is covered" is measurably FALSE; repointing `_child` is NOT sufficient (an uncaught traceback exits 1, which the predicate accepts); and `main()`'s fail-open wrapper is pinned by nothing |
| `mutation_check`'s "executed" denominator counts HARNESS ERRORs as executed | MEDIUM | **SCHEDULED** - step 3 | Directly relevant to `MUT-CONC` below: the run that printed "executed" had 11 mutations that proved nothing |
| Nothing consumes the CI result - `main` is unprotected, zero rulesets | MEDIUM | **SCHEDULED** - step 3 | A red `integration` job on any platform blocks nothing. Criterion 4's evidence is produced but not ENFORCED |
| the `exit 7` probe's discrimination is unpinned | MEDIUM | **SCHEDULED** - step 3 | The property that makes `_works` more than a liveness check is asserted by no mutation. Fix: injectable `runner`, plus a fake returning rc 0 for any argv that must be REJECTED. **Not done in step 2** - it needs a refactor, and it is recorded rather than quietly dropped |

### M5. Exactly what the local sweep proves, and what it does not

**Do not read the local numbers as covering everything.** The clean local sweep measured
**145 CAUGHT of 147 entries, 0 SURVIVED, 0 HARNESS ERROR, 2 posix-only not-runnable here.**
`SH-8` was added AFTER that sweep, taking the harness to **148** entries, and is verified only by
a filtered run (8 of 8 for this unit, which the harness itself prints as "proves nothing about
the 140 entries not considered"). A "148 clean" figure would therefore be an INFERENCE, and is
not claimed. The authoritative full-sweep number for 148 entries is CI's, on ubuntu and windows.

**That number, now measured - CI run `31310388615` on `3b386d5`, conclusion `success`, 16 jobs,
0 failed:**

| job | result |
|---|---|
| `mutation harness (do the tests bite?)` - ubuntu | **146 of 148 executed, 0 skipped, 2 not-runnable-here, 0 unproven** |
| `mutation harness (windows-only mutations)` - windows | **146 of 148 executed, 0 skipped, 2 not-runnable-here, 0 unproven** |

**The two not-runnable pairs are DISJOINT, verified rather than assumed** - ubuntu cannot run
`fast_test_on_stop` `D10`/`D10b` (Windows-only), windows cannot run `pre_push_gate` `#30` and
`fast_test_on_stop` `D10c` (POSIX-only). Across the pair, **all 148 execute and none survives**.
That complementarity is the entire reason the second mutation job exists, and it is checked here
rather than trusted, because "146 of 148" printed twice would otherwise read as two identical
gaps instead of two halves of a whole.

**`SH-8` exists because the durability check found the gap:** the UNAVAILABLE tri-state - the fix
for the false alarm step 2 introduced - was asserted by a probe but pinned by no mutation. By this
repo's own standard (mutation-test every fix; SURVIVED means the test is decorative) an
unpinned fix is not a finished fix.

**Gate-ledger instance, concrete rather than abstract (section L):** `gate_runs.json` holds 200
entries and **every one is `run_selftests`**. This session's most load-bearing gate - the clean
mutation sweep that validates every fix above - **wrote nothing**, and neither did the INVALID
sweep of section M3. The ledger therefore cannot show that a gate failed and was re-run, which is
precisely the history someone auditing this work tomorrow would need.

### M4. Found by the completeness-audit at close - confirmed findings with NO home

Three of the 14 confirmed findings were in **none** of BUILT / SCHEDULED / FINALIZED-EXCLUSION
until this pass. Found by enumerating the REVIEW's finding list and testing the ledger for each,
not by re-reading the ledger. **Two of the three are defects in the `unit_path` fix itself, which
section E1 recorded only as "fixed" - the ledger described the repair and never recorded what an
independent reviewer found wrong with it.**

| gap | sev | state | detail |
|---|---|---|---|
| `unit_path`'s root fallback resolves against TWO different trees | MEDIUM | **SCHEDULED** - step 3 | Anchor validation runs against `REPO` while mutation runs against the scratch copy, and the fallback is `os.path.isfile`-dependent - so the two can disagree about which file a unit names. A root-level unit NOT in `COPY_FILES` is addressable now but is never copied into the scratch tree, so it would abort rather than report cleanly. My fix made root files nameable without making the two resolutions agree |
| `unit_path`'s root fallback decouples anchor validation from mutation; the scratch-side `open()` is unguarded | LOW | **SCHEDULED** - step 3 | Same root cause as the row above; recorded separately because the fix differs - one needs the two trees reconciled, the other needs the read guarded so a missing scratch file reports a HARNESS ERROR rather than raising |
| The case/layout rosters INSIDE the two new probes are themselves unpinned | LOW | **SCHEDULED** - step 3 | `_selftest_sh_accounting`'s 8 cases and `_selftest_sh_candidates`' 5 layouts are hand-written lists. Deleting a case shrinks the printed denominator and nothing else goes red - the guard-that-guards-the-guard has the same declared-roster weakness as `_SH_SITES_REQUIRED` (section L). Both print their count, which is why a deletion is *visible*, but visible is not enforced |

**On the 10 REFUTED findings** - a refuted finding is still information, so they were checked for
silent loss rather than discarded. They cluster in two places, and **both clusters already have a
row**: four concern `_SH_SITES_REQUIRED` / probe rosters being declared rather than derived
(section L, and M4 above), and two concern the absence of a macOS mutation job (section J,
FINALIZED-EXCLUSION with a stated re-open condition). A cluster of near-misses in one area is a
signal about that area, and in both cases the signal points at a row that already exists.

### M3. `MUT-CONC` - the mutation harness has no concurrency lock

**Found by running the gate wrong, not by the review.** A full sweep returned exit 1 with **11
HARNESS ERRORs** ("baseline already RED before mutating"): 9 `meta_audit_on_stop`, 2 `install`.
Measured immediately after, in isolation, both baselines were **GREEN** (`rc 0`; integration
30/30), and a clean re-run gave **145 CAUGHT / 0 SURVIVED / 0 HARNESS ERROR**. The run was an
INVALID MEASUREMENT caused by concurrent processes against the tree - the "never edit code while
a gate is in flight" rule applied to PROCESSES, which is the half that was got wrong.

**`MUT-HANG`, the sibling found 2026-08-11 - SCHEDULED, step 3.** The harness can hang
INDEFINITELY with no timeout, no heartbeat and no output. **MEASURED:** a sweep launched
2026-08-09 15:52 was still "running" 2026-08-11 with **2.2 seconds of CPU accumulated across 48
hours** and a **0-byte** output file. Nothing distinguished it from a slow run, because the
harness block-buffers and prints only at the end. A normal sweep is **~30 minutes** (measured
1770s and 1960s on the same box), so the signal existed - there was simply nothing emitting it.
Fix belongs with `MUT-CONC` in the same file: a per-mutation watchdog, and progress printed as
it goes so a stall is visible in minutes rather than days. Note the harness ALREADY bounds its
child subprocesses (`timeout=400`); what it does not bound is itself.

**State: SCHEDULED, step 3.** `tools/mutation_check.py` has no `O_EXCL` lock and its summary
never names concurrency as a cause. **The near-miss worth recording:** the baseline guard is the
ONLY reason this was visible - without it all 11 would have scored CAUGHT, because a mutated run
failing for an unrelated reason is indistinguishable from a mutation being caught. A false green
on the instrument that certifies every other test here. Note also that the sweep writes no row to
`gate_runs.json`, so the invalid run left no durable trace either (section L).

---

## K. RE-HOMED from V131_REVIEW_PLAN.md (2026-08-09, forward-plan step 1)

Everything below previously existed **only** inside `docs/V131_REVIEW_PLAN.md`. It is reproduced
here so this ledger CONTAINS it rather than pointing at it. Source lines are cited for
traceability; the plan file is retained as history and is no longer the carrier.

### K1. The R1/R2 rule - the operational definition of "reachable by a user"

DoD **criterion 2** is stated in exactly these words ("No defect reachable by a user who installs
it and uses it") and is made mechanically decidable ONLY here. Verbatim from
`V131_REVIEW_PLAN.md:1975-2004`, **with the fourth R1 clause from CORRECTIONS item 1 folded in** -
lifting the base rule alone would have moved a three-clause version of a four-clause rule.

A finding is **SHIP-BLOCKING** iff BOTH hold. Otherwise it is **V1.4-BACKLOG**.

- **R1 EXECUTION** - the defective code RUNS on an installed user's machine, via an entry point
  this repo wires or documents. The entry points, **derived rather than listed**:
  1. the 8 script paths `install.py:desired_groups()` writes into `~/.claude/settings.json`
     (parsed out of the AST, not transcribed): `rate_prompt`, `hook_health_check`,
     `duplicate_registration_check`, `usage_snip_prompt`, `stop_dispatcher`,
     `post_tooluse_dispatcher`, `close_skills_guard`, `piped_gate_guard`;
  2. `hooks/pre_push_gate.py` - NOT wired by `install.py`, but the README documents it as a real
     git hook the user installs (`--install-global` sets `core.hooksPath`). Excluding it because
     `install.py` does not name it would be an artifact of the rule, not a fact about the user;
  3. **`hook_health_check`'s weekly sweep**, which runs `subprocess.run([sys.executable, path,
     "--selftest"])` over every `hooks/*.py` at SessionStart (`hook_health_check.py:223`). Every
     hook selftest therefore EXECUTES on a user's box, weekly. `tools/*` and `tests/*` are not
     swept;
  4. **the skill scripts `install.py` installs.** `main()` calls `install_skill()`, which
     `shutil.copytree()`s all four `SKILL_NAMES` into `~/.claude/skills/<name>/`, bundled scripts
     included (`install.py:203-205`, explicitly "not just SKILL.md"). That lands **3 executable
     .py** on the user's machine, and `SKILL.md:48` tells them to run `audit.py` over their own
     deliverable. `close_skills_guard` - one of the 8 WIRED hooks - blocks the close until
     consistency-audit is invoked, so R1 is satisfied through a wired hook rather than a merely
     documented one.
- **R2 TRIGGER** - the input that exposes it is something the USER supplies: their repo, their
  `settings.json`, their plan documents, their transcript, their git state. **NOT a modification
  of unbluff's own source.**

**Neither half alone is sufficient, and this is the load-bearing part.** A pure import-closure of
the entry points reaches most of the local modules, including the entire cap detector -
`capped_report` is imported by five wired hooks. But `capped_report` only CALLS
`cap_shapes.slicing_offenders` / `verdict` / `exemption_problems` from inside `selftest()`, and
that selftest's subject is unbluff's own `hooks/` directory, whose contents are byte-identical on
every machine. A user who never edits unbluff's source cannot change that verdict, so R1 is
satisfied and R2 is not. Conversely R2 alone would admit `tools/mutation_check.py`, which never
runs on a user's machine at all.

**Population rule (CORRECTIONS item 5):** R1 and R2 carry no severity term. The gate's population
is **every open finding**, with severity applied AFTER reachability - never "the open HIGHs".

**Known limit, carried as residual risk R3:** clause 4 was only added after an independent review
found a defect (DOCX-1) inside the region the three-clause rule could not see. That was the
SECOND omission of the same shape - the rule had already had to hand-add `pre_push_gate`.
**There is no proof clause 4 is the last one.** Criterion 2 therefore means "no defect reachable
through the paths R1/R2 enumerates, as of this enumeration", and the README WON'T-FIX section
must say so.

### K2. The five CORRECTIONS - now carried here, not pointed at

`coverage_ledger_2026-08-08.md` records rows 3, 7, 8, 10 and 11 as **BUILT** naming
"CORRECTIONS item N" as the carrier. Those items lived only at `V131_REVIEW_PLAN.md:2208-2259`.

| # | correction | carries 08-08 row |
|---|---|---|
| 1 | R1's entry points were derived from ONE install action, not from what `install.py` DOES. **R1 gains a fourth clause: the skill scripts `install.py` installs.** DOCX-1 was found inside that blind region and is fixed. The original claim that "no open HIGH sits there today, so no row of the 21 changes" was FALSE, and its refuter proved so with a control. | 6, 10 |
| 2 | **The module universe is 44, not 41.** The 41 excluded `skills/*/scripts/` (3). Restated as a DERIVED figure: whatever the closure of `install.py`'s install actions reaches. | 10 |
| 3 | **"24 of 41 local modules (17 dev-time)" is not reproducible, and never was.** The section's own stated entry set yields **25 of 41 / 16**. The missing module is `hooks/hook_health_check_selftest.py`, reached by a plain `ast.Import` at `hook_health_check.py:526`. `git log -S` places the string's introduction at `5bbc8a9`, an ANCESTOR of the split commit `07b0a01`, where the universe was still 40 and the correct triple was 24 / 40 / 16. **The triple 24 / 41 / 17 has never been simultaneously correct at any commit.** Load-bearing conclusions survive and were re-verified: `capped_report` is in the closure and is imported by exactly 5 hooks, so "R1 alone is insufficient" and both premise corrections stand. The fix is not "bump 24 to 25" - it is to name WHICH modules and derive the number. | 11 |
| 4 | **Row 18 is attributed to the file its own source exonerates.** The row names `hooks/cap_shapes.py verdict()`; the finding it cites explicitly clears that function. The row's BUCKET is unaffected (both candidate units are backlog for the same R2 reason), but a row classified against the wrong call graph is a classification that happened to be right. | 8 |
| 5 | **The gate was only ever applied to items already labelled HIGH.** R1 and R2 carry no severity term, but the population was fixed at "the 21 open HIGH", so a user-facing defect already rated MEDIUM could never reach the gate that DEFINES user-facing. Both attempts to convert this into a shipping defect were refuted on measurement, so it is a **method** correction: population = every open finding. | 7 |

**Row 3 of the 08-08 ledger** ("SHIP-BLOCKING is at least 2, not 1") was carried by "the count
correction is in the same section". That count correction is item 3 above.

**What the pass cost and bought** - retained because it is the evidence for the independent-lens
rule: 20 findings, 20 adjudicated, 12 confirmed. Five of the twelve were defects the author's own
rule could not see, and **three were live user-facing HIGHs that would have shipped** (SUP-1,
GLOB-1, SKIP-1) plus DOCX-1 inside the blind region. The most valuable output was not any one
finding but the demonstration that **the DENOMINATOR was wrong**: the review was asked to check
21 rows and found what mattered outside them.

### K3. ENTRY-GUARD - the durable mechanism this section implies

**Nothing mechanically connects `install.py`'s install ACTIONS to the set of files the repo
gates.** The rule missed the skill scripts by reading one function; a future install action will
be missed the same way. Durable fix: AST-walk `install.py:main()` for every call that writes to
the user's machine, expand each to the files it lands, and assert that set is covered by a gate.

**State: BUILT 2026-08-09 - see section N.** Same shape as `INSTALL-TAUTOLOGY` (section B), and
they were fixed together as this row required.
