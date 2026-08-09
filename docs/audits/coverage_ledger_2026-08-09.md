# Coverage ledger - 2026-08-09

The objective proof of coverage. Every item is `BUILT` (with the unit that carries it),
`SCHEDULED` (with a phase), or `FINALIZED-EXCLUSION` (with a justification). Nothing may sit in
none of the three.

**This ledger supersedes `coverage_ledger_2026-08-08.md`.** That ledger predates the v1.0
Definition of Done and the promise inventory; it is organised around the retired v1.3.1 ship
gate. Its rows are carried forward in section E below. **Its four `CORRECTIONS`-carried rows are
re-homed here in section F - see the CRITICAL finding that made that necessary.**

Repo HEAD `00fc9ba`, tree clean apart from this session's audit files. All numbers verified live.

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

**Caveat carried, not hidden:** 35 of the 85 BUILT rows carry a platform caveat, overwhelmingly
"integration runs on ubuntu only". Those 35 are BUILT-on-Linux and UNPROVEN elsewhere until
section D lands. **They are not double-counted; they are counted as BUILT with the caveat
printed.**

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
| `INSTALL-TAUTOLOGY` - the partial-checkout guard is a no-op; 9 of 25 hooks unguarded, 5 imported by production hooks | **CRITICAL** | **SCHEDULED** | step 3. Reproduced live: delete `hooks/transcript_util.py` -> `install.py` exits 0 -> `close_skills_guard.py` raises `ModuleNotFoundError` |
| `ENC-1` - 0 of 25 hooks reconfigure stdout; cp1252 + non-ASCII path = half-printed report then **exit 0** | HIGH | **SCHEDULED** | step 3. Carried from the 08-08 ledger; **worse than recorded there** - silent, not a visible crash |
| `PGG-PS` - `piped_gate_guard` registered `matcher: "Bash"`; never fires for PowerShell users | HIGH | **SCHEDULED** | step 3. Two-part: matcher AND the guard's POSIX-only vocabulary |
| `SKILLDIR-DESTROY` - install/uninstall destroys a user's pre-existing same-named skill directory | HIGH | **SCHEDULED** | step 3 |
| `FASTTEST-BLOCK` - `fast_test_on_stop` hard-blocks every turn end on any repo that merely has a `tests/` dir | HIGH | **SCHEDULED** | step 3. Also a criterion-3 false alarm - fix before measuring |
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

| platform | state | evidence |
|---|---|---|
| Linux | **BUILT** | CI job `integration`, `runs-on: ubuntu-latest`, 30/30 |
| Windows | **SCHEDULED** | step 2 (3-OS matrix). `run_selftests.py` never invokes `tests/test_integration.py`, so the 3-OS `selftest` matrix does not cover this |
| macOS | **SCHEDULED** | step 2. **Was in NO step before today** - the plan's INT-WIN closed Windows only |
| `pre_push_gate` delegation on Windows | **SCHEDULED** | step 2. Three `SELFTEST SKIP: sh unavailable` paths pass vacuously while the suite reports 32/32 |

---

## E. Carried forward from the 2026-08-08 ledger

All 9 previously-deferred items retain their phase. Re-homed against the new step numbering:

| id | old phase | new home |
|---|---|---|
| `ENC-1` | v1.4 phase 1 | step 3 (section B) |
| `ENTRY-GUARD` | v1.4 phase 1 | step 3 |
| `BUDGET-1` | v1.4 phase 1 | step 3 |
| `INT-MUT` | v1.4 phase 2 | step 2 - folds into the 3-OS matrix work |
| remaining LOW rows | v1.4 | step 3 |

The 12 confirmed findings of run `wf_c9822f7b-865` keep their BUILT/SCHEDULED state unchanged.

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
| **6** confirmed findings whose ONLY carrier was the plan's `CORRECTIONS` prose | **BUILT** 2026-08-09 | Now carried verbatim in **section K2**. `coverage_ledger_2026-08-08.md` recorded rows 3/6/7/8/10/11 as BUILT naming "CORRECTIONS item N" - it *pointed at* them and never contained them. That ledger now carries a supersession note directing readers to K2. **Six rows, not four:** re-homing found two more than the original finding named |
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
| `CHANGELOG` 1.1.1 asserts the integration suite passes on Linux/macOS/Windows | **SCHEDULED** - step 2 | It has never run anywhere but ubuntu. A published false claim |
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
| CI jobs `mutations` and `mutations-windows` were unreconciled | **SCHEDULED** - step 2 | Both are gates and neither appeared anywhere in this ledger. They run on `ubuntu-latest/3.12` and `windows-latest/3.12`. **There is no macOS mutation sweep**, so section D's 3-OS work closes `integration` on macOS but leaves the mutation evidence two-platform. Recorded so the platform story is not overstated. |
| The 3 shipped skill scripts were an unnamed population | **SCHEDULED** - step 3 | `skills/consistency-audit/scripts/{audit,extract,sources}.py`. `install.py` copytrees them into `~/.claude/skills`, which is **R1 clause 4** - they are inside criterion 2's entry-point scope. `CA-SELFREF` (section B) is a defect in `extract.py`; the ledger recorded the defect without ever recording the population it belongs to. |
| `review_runs.json`'s denominator was unstated | **CLOSED by this pass** | The ledger said "42 open" without saying over what. Verified: 6 runs, 68 unit-entries, 42 open, all in `wf_1b621b24-7ef`; the other 5 runs carry 0 open. **The 42 is the complete population**, now stated as such in section I. |

**Method note:** these were found by enumerating each source mechanically and testing whether the
ledger names it - not by re-reading the ledger. Re-reading the ledger would have agreed with
itself, which is precisely why that is not the procedure.

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

**State: SCHEDULED, step 3.** Note this is the same shape as `INSTALL-TAUTOLOGY` (section B) -
both are "the roster is not derived from what the code actually does". **Fix them together.**
