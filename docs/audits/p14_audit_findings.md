# P14 audit findings - consistency, completeness, and the guard audit

Run `wf_e0a4cf3d-acb`, 2026-08-02. Six agents; **five completed, one died on a session
usage limit** (the D1 self-budgeting design), which is recorded here rather than dropped.

**Why this file exists.** These results existed only in an OS temp task file. The same
class of loss already happened twice in this pass: 42 findings that survived only in a
workflow journal, and the rounds 1-2 evidence recovered as item N6. A completed agent's
output is not recorded until it is in the repo.


---

## The guard audit (B5) - three guards, three fail open


### hooks/transcript_util.py selftest() lines 236-261 - the "THE TWIN MUST NOT COME BACK" block, asserting that exactly ONE implementation of the genuine-user classifier exists

- **fails open:** True
- **shapes enumerated:** 4
- **recommendation:** rebuild-fail-closed

**Blind shapes demonstrated (6):**

- N1 complete divergent classifier with every name renamed (HARNESS_TEXT_MARKERS / leading_text / looks_like_harness_text / is_real_user_turn) - the P14 hypothesis, confirmed CLEAN exit=0
- N2 an ENUMERATED name written as an annotated assignment: `SYNTHETIC_PREFIXES: tuple[str, ...] = (...)`. Line 253's regex requires `=` immediately after the name, so any strict-typing codebase spells the twin invisibly
- N3 enumerated FUNCTION names bound without a plain `def`: `first_text = lambda content: ...` and `async def is_synthetic`. Lines 255/257 both anchor on `^\s*def _?`
- N4 a BYTE-IDENTICAL enumerated twin one directory down (hooks/lib/user_turns.py). Line 243 globs `os.path.join(here, '*.py')` - non-recursive, so moving the same file into a subpackage erases it
- N5 the same byte-identical twin in a sibling directory (tools/turn_classifier.py). The scan is scoped to hooks/ only; tools/mutation_check.py already sits outside it and already references isMeta, sourceToolUseID, is_synthetic and first_text
- N6 the rule copied INLINE into a hook - prefixes as a local tuple inside the transcript loop, text extraction inlined, no module constant and no named helper. This is what copy-paste actually looks like; a tidy renamed module is the easy case

**Evidence**

```
A/B over 11 cases (5 CONTROL + 6 NOVEL), each a fresh scratch copy of hooks/ with one file planted, scored by running `python transcript_util.py --selftest` inside the copy. Harness scripts at C:\Users\ammar\AppData\Local\Temp\claude\C--Users-ammar-Downloads-Claude\61196ffe-d66d-4ad7-9208-af4a3f565559\scratchpad\twinprobe\ (probe.py, planted.py, divergence.py, failclosed_cost.py, verify_failclosed.py).

CONTROLS 5/5 behaved as specified, so the harness is live:
  C0 baseline, nothing planted            -> CLEAN   exit=0
  C1 `SYNTHETIC_PREFIXES = (...)`         -> FLAGGED exit=1
  C2 `def first_text`                     -> FLAGGED exit=1
  C3 `def is_synthetic`                   -> FLAGGED exit=1
  C4 `_META_PROMPT_PREFIXES = (...)`      -> FLAGGED exit=1
C1's message: "SELFTEST FAIL: a SECOND transcript classifier exists in ['turn_boundary_a.py (own prefix list)']".

NOVEL 6/6 reported CLEAN, exit=0, guard silent. Every one is a working second classifier a competent author could plausibly write.

The headline novel case (N1) is not a straw man. Running the real is_genuine_user and the planted twin's is_real_user_turn over the same 16 entries: they DISAGREE on 8/16, and the twin re-introduces defects this module was created to fix - image-ONLY prompt False vs True and document-ONLY False vs True (the P13 D4 regression), origin.kind=task-notification accepted as the user, and 5 harness tags accepted as prompts ("Base directory for this skill:", "[Request interrupted by user]", "This session is being continued...", <bash-stdout>, <command-args>). It ships all-green.
```

**Notes**

DIRECT ANSWER: yes, it shares the premise exactly. The guard enumerates 4 hardcoded names (SYNTHETIC_PREFIXES, META_PROMPT_PREFIXES, first_text, is_synthetic) across 3 line-anchored regexes, over 1 non-recursive directory. Anything outside that set is reported CLEAN. It is the capped_report defect in miniature: 6/6 novel shapes silent, 5/5 controls caught.

THE SHAPE SPACE IS NOT BOUNDED. capped_report enumerated Python cap SYNTAX (large but at least syntax-shaped). This guard enumerates IDENTIFIER CHOICES - a strictly unbounded space, since the whole scenario it guards against is an author who did not know transcript_util.py existed and therefore had no reason to pick its names. The guard can only ever catch a twin written by someone who already knew the canonical names, which is close to the population that would not have written a twin.

IT ALREADY NARROWED ITSELF ONCE, FOR THE CAPPED_REPORT REASON. Line 251-252 records it: "A real assignment at the start of a line - not a mention inside a string or comment, which is how a previous twin-guard produced its own false alarm." One false positive was treated as disqualifying and the rule was tightened into enumeration. Same trade, same outcome.

FAIL-CLOSED IS CHEAP HERE - MEASURED, NOT ASSERTED. Candidate rule: flag any .py in the repo that touches a BEHAVIOURAL harness/user discriminator (isMeta, sourceToolUseID, tool_result, a harness tag literal, or a role=="user" test) and does not import transcript_util.
  - Clean-tree cost: 2 exemptions out of 36 python files (5.6%) - tools/compare_delivery_gate.py and tools/mutation_check.py. That is one THIRD of the 6 false positives that were treated as disqualifying in the capped_report case.
  - hooks/close_skills_guard.py and hooks/show_your_proof.py auto-pass because they already import the canonical module.
  - Catch rate on the same planted set: 9/10 vs the shipped guard's 4/10, including all 6 novels.

BE FAIR - ONE HONEST GAP IN THE REPLACEMENT. The fail-closed rule MISSED control C2 (a bare `def first_text` text extractor with no harness marker in it). So do not delete the name checks: keep the 4 names as a FLOOR and add the behavioural rule as the ceiling, and make the glob recursive over the repo rather than `hooks/*.py`.

THE REPO HAS ALREADY MADE THIS EXACT CONVERSION THREE TIMES. install.py:248-256 - "[MEDIUM-1] DERIVED, with the tuple as a floor only. REQUIRED_HOOKS was a hardcoded 14-name roster and today's transcript_util.py was the one hooks/*.py absent from it... This exact class was already fixed in run_selftests.py and hook_health_check.py - the third copy of the roster was simply never converted." The twin guard is the fourth copy, and the only one where the roster is of shapes rather than filenames. The floor-plus-derived pattern is already the house style; this guard just never got it.

CONSTRAINTS HONOURED: nothing under C:/Users/ammar/Downloads/unbluff was written; all planting happened in fresh temp copies. tools/mutation_check.


### hooks/duplicate_registration_check.py (C:/Users/ammar/Downloads/unbluff/hooks/duplicate_registration_check.py, 516 lines, baseline 1dcf430)

- **fails open:** True
- **shapes enumerated:** 11
- **recommendation:** rebuild-fail-closed

**Blind shapes demonstrated (7):**

- A .js hook wired twice (`node <path>.js` x2). The repo's OWN sibling guard hardcodes _SCRIPT_EXTS = (".py", ".js", ".ps1", ".sh") at hooks/hook_health_check.py:137, so this repo already treats .js as a hook shape - just not here.
- A .ps1 hook wired twice (`pwsh -NoProfile -File x.ps1` + `powershell -File x.ps1`). The author develops on Windows.
- A .sh hook wired twice (`bash x.sh` + `sh x.sh`).
- The same Python hook wired twice as a MODULE: `python -m hooks.rate_prompt` x2. No ".py" token exists anywhere in the command string, so nothing is extracted at all.
- A dispatcher whose FILENAME does not contain the substring "dispatcher" (e.g. hooks/fanout.py). Line 195 `if "dispatcher" not in base: continue` is a name test, not a behaviour test - the fan-out to plan_defer_guard.py was invisible while the same file named stop_dispatcher.py was expanded correctly.
- A correctly-named dispatcher whose module list is named MODULES (or PIPELINE) instead of HOOKS. Line 162 requires `t.id == "HOOKS"` literally; post_tooluse_dispatcher.py with MODULES = (("show_your_proof", "s"),) fanned out to nothing.
- Plugin-provided hooks: 7 hooks.json files exist on this machine, declare hook events, and are not in settings_layers() - e.g. ~/.claude/plugins/marketplaces/claude-plugins-official/plugins/hookify/hooks/hooks.json declares PreToolUse, PostToolUse, Stop, UserPromptSubmit. Measured by C:\Users\ammar\AppData\Local\Temp\claude\...\scratchpad\probe_layers.py.

**Evidence**

```
HARNESS: C:\Users\ammar\AppData\Local\Temp\claude\C--Users-ammar-Downloads-Claude\61196ffe-d66d-4ad7-9208-af4a3f565559\scratchpad\probe_dupreg.py (guard COPIED to temp and imported from the copy, sys.dont_write_bytecode=True, so nothing was written under the repo). Every novel fixture carries an IN-FIXTURE CONTROL: control_marker.py wired twice in the SAME settings file as the novel shape. If the control is not caught the case proves nothing.

RESULT: harness sound (in-fixture control caught in 6 of 6 novel cases). Enumerated shapes caught: 3 of 3. Novel shapes reported CLEAN: 6 of 6 attempted.

PLANTED CASE (N1_js_hook_twice), one settings.json containing four entries - notify.js wired twice AND control_marker.py wired twice:
  guard report = "control_marker.py - registered 2 times - SAME FILE twice (redundant): <- .../hooks [user] [sha 55c1e7fdd657] | <- .../hooks [user] [sha 55c1e7fdd657]"
  notify.js: ZERO lines. The guard read the file, flagged the .py duplicate in it, and reported the .js duplicate as clean in the same pass.

CONTROLS (must be caught, and were):
  C1 same .py path twice -> "registered 2 times - SAME FILE twice (redundant)"
  C2 dispatcher fan-out via stop_dispatcher.py HOOKS tuple -> "widget.py - registered 2 times ... (via stop_dispatcher.py)"
  N7 fairness control, uv run --script x.py + python x.py -> CAUGHT (the guard is wrapper-agnostic for .py, it is not blind to everything)

BASELINE SANITY: python guard_selftest_copy.py --selftest -> "SELFTEST PASS: variant conflict, args-style duplicate, dispatcher fan-out, no false positive, main() prints to stdout", exit 0. The fail-open is by construction, not a regression.

MECHANISM (hooks/duplicate_registration_check.py:66 and :132): _path_tokens keeps a token only `if t.lower().endswith(".py")`. A shape that yields no token never enters the `registered` dict, and a basename absent from the dict can never reach `len(entries) < 2: continue` at :205. Non-extraction is indistinguishable from non-duplication.
```

**Notes**

SHAPE COUNT, mechanically located by C:\Users\ammar\AppData\Local\Temp\claude\C--Users-ammar-Downloads-Claude\61196ffe-d66d-4ad7-9208-af4a3f565559\scratchpad\probe_count.py (each is a gate: a miss produces silent CLEAN, not a warning). 11 of 11 literals located, denominator 11:
  1 script extension ".py" (lines 66, 132)  2 config key "command" (111)  3 config key "args" (125)
  4 layer ~/.claude/settings.json (42)  5 layer ~/.claude/settings.local.json (81)  6 layer <cwd>/.claude/settings.json (82)  7 layer <cwd>/.claude/settings.local.json (83)
  8 dispatcher by filename substring "dispatcher" (195)  9 dispatcher list must be named HOOKS (162)  10 dispatcher element first item is a str Constant (166)  11 dispatched module file is <name>.py (200)

IS THE SHAPE SPACE BOUNDED? No. A Claude Code hook `command` is an arbitrary shell command string, so the set of spellings is the set of shell commands. Claude Code hooks are language-agnostic and the repo's own hook_health_check.py already recognises four extensions. A competent author writing a node, bash, pwsh, deno or `python -m` hook lands outside the set on the first try. This is the same non-terminating enumeration that cost the capped_report revert (47 spellings round 1, 111 round 2, fresh blind spots after each).

LIVE EXPOSURE (probe_real_config.py / probe_live_dup2.py, against the user's real ~/.claude/settings.json): 30 hook entries; the guard extracts a script from 9 and extracts NOTHING from 21. All 21 are `node -e "..."` ECC bootstrap hooks. The guard reports 0 problem lines on the live config. If any of those 21 were double-wired the output would be identical - 0 lines.

CORRECTION TO MY OWN MEASUREMENT, stated because it nearly became a false claim: my first duplicate scan hashed only `command` and ignored `args`, which misclassified three args-style python.exe entries as invisible and produced a spurious "SessionStart x3 duplicate". Re-run classifying by what the guard actually extracts (command AND args): VISIBLE pool 9 slots, 0 duplicated; INVISIBLE pool 21 slots, 0 duplicated. There is NO live duplicate today. The finding is exposure, not a live bug.

FAIRNESS - COUNTER-EVIDENCE, and it strengthens the recommendation. The guard is already fail-CLOSED and noisy on a different axis: it merges all events and matchers before counting. Measured cases X1 and X2 - the same hook registered under Stop AND PreToolUse, and the same hook under PostToolUse matcher "Write" AND matcher "Edit" - are both reported as "registered 2 times - SAME FILE twice (redundant)" though neither double-fires on a single event. So the design already accepts false positives in one dimension while failing open in another. The argument that fail-closed noise is unacceptable here is not available to this guard; it is already paying that cost, just on the wrong axis.

WHAT FAIL-CLOSED LOOKS LIKE HERE: count REGISTRATIONS of hook ENTRIES, not of extracted .py paths. Every entry registers something. Key on (event, matche


---

## Consistency audit - 71 claims extracted and tested


### FALSE claims (13)

- README.md:171 - claim: the pasted transcript ends "==== 26/26 scenarios passed ====". MEASURED: tests/test_integration.py records 30 scenarios today. AST count of record() call sites = 28, of which 1 is inside the per-skill for-loop at line 96 and 2 are the try/except pair at 241/243 where exactly one fires -> 26 fixed + len(install.SKILL_NAMES)=4 loop records = 30. The plan asserts 30/30 in three separate places (:1150, :1171, :1279). The gate written to stop this exact rot, tools/check_readme_fresh.py, only regexes 'all (\d+) selftests passed' (_CLAIM_RE at :29), so the integration number in the same code block is ungated and wrong.

- README.md:274 - claim: "CI runs the self-tests + the integration test on Linux, macOS, and Windows across Python 3.8-3.12." MEASURED from .github/workflows/selftest.yml: the `integration` job is runs-on ubuntu-latest, python 3.12, ONE job of 14. It runs on neither macOS nor Windows. Only `python run_selftests.py` is cross-platform. Also macOS never runs 3.8 (explicitly excluded with a comment at line 25-26) and 3.10 runs on no platform at all, so "across Python 3.8-3.12" overstates the matrix ['3.9','3.11','3.12'] + 3.8 on ubuntu/windows only.

- README.md:149 and README.md:257 - claim: "run it yourself (this is exactly what CI runs on Linux, macOS, and Windows)" and "# verify the whole suite (this is exactly what CI runs)", both introducing a block containing BOTH run_selftests.py and tests/test_integration.py. MEASURED: same as above - the integration half runs on one platform, one interpreter, one job.

- docs/V131_REVIEW_PLAN.md:1177 - claim: "`hooks/capped_report.py` (7 confirmed, incl. 2 HIGH)". MEASURED by parsing docs/audits/p14_new_code_review.md's own '### HIGH' section: 3 of the 10 HIGH findings carry a `where:` naming hooks/capped_report.py (HIGH #8 annotation/tuple-target, #9 alias/arithmetic upper bound, #10 slicing_offenders blind to 9 of 11). 7 total is correct. The plan contradicts itself 25 lines later: work-order row 1 at :1202 reads 4 HIGH, which is 3 + the dropped candidate.

- docs/V131_REVIEW_PLAN.md:1178-1179 - claim: "there is already an unrouted cap in `hook_health_check.py:470` that it reports as clean", present tense. MEASURED at HEAD d641da7: line 470 is `        if n_left:`. The cap that was there (`for p in problems[:12]` plus a separately computed '... and N more') was routed through capped_report.render(problems, MAX_PROBLEM_BULLETS, ...) by commit d641da7. The repo's own docs/audits/p14_cluster1_evidence.md:62 states this explicitly: "hooks/hook_health_check.py:470 problems[:12] is no longer a live unrouted cap". The plan's 'Kept from those two rounds' paragraph at :1260 also says the fix was kept, so the same section asserts both.

- docs/V131_REVIEW_PLAN.md:1272 - claim: "Full evidence - the 111-spelling taxonomy, the 123-hit false-positive budget, ... is in `docs/audits/p14_cluster1_evidence.md`." MEASURED: the string "123" occurs ZERO times in that file. What it records is `fp_must_not_flag` declared as (107), at line 27. Worse, that list is silently TRUNCATED: the line is 1430 chars, json.loads fails with 'Unterminated string', and it contains 36 commas -> at most 37 of the declared 107 entries are present, with no truncation notice.

- docs/V131_REVIEW_PLAN.md:949 and docs/V131_REVIEW_PLAN.md:1121 - claim: the 800-line split took "`pre_push_gate.py` 1113 -> 561". MEASURED by sweeping every commit in history for that file's line count: 561 was NEVER its line count in any commit, as total OR as non-blank lines. The split commit 2318a76 leaves it at 584 and it is still 584 at HEAD (9 commits). The other three numbers in the pair of claims check out: 1113 (true at 9392bc5), 900 (true at 9392bc5), 539 (true from 2318a76 onward).

- docs/V131_REVIEW_PLAN.md:1200-1226 - claim: the P14 work-order table is "their HOME and their ORDER, so that no cluster can be quietly skipped", followed at :1225 by "**Merged backlog: 44 open - 11 HIGH, 24 MEDIUM, 9 LOW.**" MEASURED: the table's own columns sum to 11 HIGH but 43 total, not 44. Every one of the 12 per-row numbers is individually CORRECT when reconciled against p14_new_code_review.md (verified row by row; capped_report 3+1 dropped = 4/8 matches). The missing 44th item is F-L8, which p14_triage.md:65 schedules as "Add as LOW against `hooks/transcript_util.py`" - row 11 still reads total 1. The table built to stop a quiet skip is short by exactly the one finding triage added.

- docs/V131_REVIEW_PLAN.md:1316 (N3) - claim: register the new file "in the five flat `hooks/` rosters (`hook_health_check:85/90/558`, `transcript_util:243`, `install.py:256`, `run_selftests:87`)". MEASURED, all six anchors read: six anchors are called five; hook_health_check:85 and :90 are the OPENING and CLOSING lines of one docstring on `selftestable_hooks`, which is a DETECTOR (`return [p for p in sorted(glob.glob(...)) if has_selftest(p)]`), not a roster; :558 is a comment line inside selftest(); run_selftests:87 globs `tools_dir`, not hooks/. The only actual roster in that file, `KNOWN_NO_SELFTEST` at hook_health_check.py:67-70 (where the two existing *_selftest.py siblings are in fact registered), is not cited at all.

- docs/V131_REVIEW_PLAN.md:1316 (N3) - claim: "`capped_report.py` is now **2101 lines**, 2.6x the limit and the worst violator in the repo." MEASURED: 180 lines. NO file in the repo exceeds 800 lines today; the largest of the 35 tracked .py files is hooks/hook_health_check.py at 781. (A parenthetical at :1323 concedes the instance is gone, but N3 is the scheduled HIGH row that blocks the ship and still reads present-tense.) The CLASS half of N3 is CORRECT and I confirm it: grep for '800' across the repo returns only prose in fast_test_on_stop_selftest.py:1, pre_push_gate_selftest.py:1 and hook_health_check.py:64, plus unrelated 1800-second timeouts. There is no line-count gate anywhere.

- docs/V131_REVIEW_PLAN.md:1349 (B6) - claim: "**CI has never run on any of this session's work.** Every green claim is from one Windows machine." MEASURED: `git rev-list --left-right --count origin/main...HEAD` returns 0 0, and `git reflog show origin/main` records "d641da7 refs/remotes/origin/main@{0}: update by push" with .git/refs/remotes/origin/main mtime 08:15 today. The session's work IS on origin/main, so the push-to-main trigger has fired. Whether the 14 jobs went green is not checkable offline - but the stated premise is no longer true.

- docs/audits/p14_triage.md:39 - claim: "`if not caps: continue` skips **13 of the 17** hook files in `hooks/` today" and the plan's companion at :1179 "examining four files". MEASURED with the guard's own _max_names over the pristine 1dcf430 tree: 13 of 17 skipped, 4 examined - EXACT. But against HEAD d641da7 it is now 11 of 17 skipped, 6 examined, because the retained live-cap fixes added MAX_PROBLEM_BULLETS to hook_health_check.py and a cap constant to show_your_proof.py, pulling both into the examined set. Both figures are stale as present-tense claims.

- docs/audits/p14_new_code_review.md:235 and :237 - claim: "### Status: TRIAGE REQUIRED, not merged" and "Overlap with the 42 findings above is UNQUANTIFIED." MEASURED: triage was completed 2026-08-01 and the overlap quantified in docs/audits/p14_triage.md, which the plan records as done at :1222. The review doc carries no correction note - unlike the plan at :1245, which deliberately leaves its correction visible. A reader landing on the audit doc is told to do work that is finished.


### UNVERIFIABLE claims (6)

- docs/V131_REVIEW_PLAN.md:1251-1252 - "Two fix rounds grew the detector from 180 lines / 1.2s to 2101 lines / 36.1s (11.7x and 30x, both MEASURED)". The 180 checks out (measured). The strings '2101', '36.1' and '1.2s' occur in NO file in the repo except V131_REVIEW_PLAN.md itself - specifically NOT in docs/audits/p14_cluster1_evidence.md, which the very next paragraph names as the home of the full evidence. The reverted code is gone, so nothing can regenerate them. The internal ratios are self-consistent (2101/180 = 11.67, 36.1/1.2 = 30.08), which is the only check available - i.e. the numbers verify against each other and against nothing else.

- docs/V131_REVIEW_PLAN.md:1269-1270 - "Round 1 (`wf_7c6b33a8-265`, 13 agents) and round 2 (`wf_05787685-fee`, 11 agents)". Both run ids appear as headings in p14_cluster1_evidence.md, so those verify. The agent counts appear nowhere: a regex for '(\d+) agents' over the evidence doc returns zero matches.

- docs/V131_REVIEW_PLAN.md:1317 (N4) - "Widening measured to cost zero today (0 of 197 in-scope UPPER_SNAKE constants newly match)". The 197 depends on `is_cap_name`, which the revert deleted; no script or corpus in the repo reproduces it. tests/cap_spelling_corpus.py is a spelling corpus, not a constant census.

- docs/V131_REVIEW_PLAN.md:1318 (N5) - "`_cap_names` models 12 of Python's 24 name-binding forms." `_cap_names` does not exist. Loaded hooks/capped_report.py and checked 16 identifiers named across C1-R1..R8, N4 and N5: 11 are ABSENT (_cap_names, _BASELINE_FLOOR_NAMES, is_cap_expr, is_cap_name, _callee_aliases, _body_changes_length, _is_size_measure, exemption_problems, _TAXONOMY, sweep, pop_until_under_cap); 5 are present (_max_names, slicing_offenders, keep, render, BOUND_EXEMPTIONS). Row A2 at :1337 explicitly re-scopes C1-R1..R8 as acceptance criteria for deleted code - but A2 names only R1..R8. N4 and N5 sit in a different table ('NEW findings surfaced by this cluster'), carry unit `hooks/capped_report.py`, and read as live findings against a file where their subject does not exist. C1-R8's anchor `capped_report.py:54-55` today lands on render()'s docstring ("`total` overrides len(findings)..."), not on any coverage-boundary statement.

- docs/V131_REVIEW_PLAN.md:1281 "92-of-94 mutations ALL CAUGHT" and docs/audits/p14_new_code_review.md:60 "the entire 81-entry evidence base" - there is no repo-side evidence that the mutation suite has EVER run. docs/audits/gate_runs.json holds 104 entries and every single one has gate='run_selftests' (Counter over the file), which confirms C1 at :1357. Two things C1 does not say and that make it worse: (a) the file is GITIGNORED at .gitignore:23, so it is not in version control and no CI run or any other machine can ever contribute to it or read it; (b) review_runs.json IS tracked, so the ledger the plan leans on for gate evidence is the one that cannot be shared. The '92 of 94' figure is quoted as harness output inside p14_cluster1_evidence.md:98, but that describes the reverted detector's mutation set (the doc itself says entries went 82 -> 94), so it cannot be re-run.

- docs/V131_REVIEW_PLAN.md:1314 (N1) - the 'C1 hook_health reports OK scenario is ENVIRONMENT-DEPENDENT / 30/30 twice, 29/30 elsewhere' flakiness claim. Not testable in this session: tests/test_integration.py was off-limits (mutation run in flight). Noting that the plan's own B8 at :1351 already records N1 as UNPROVEN and confounded, so the plan flags this one itself.


### Stale numbers (10)

- docs/V131_REVIEW_PLAN.md:927 - 'gate_runs.json holds 44 entries; the last three are run_selftests PASS ran=19' -> 104 entries, ran=22. Dated 2026-07-31, so point-in-time by construction.

- docs/V131_REVIEW_PLAN.md:928 - 'review_runs.json holds 45 entries, latest wf_a51d3013-715' -> 68 entries, latest wf_1b621b24-7ef.

- docs/V131_REVIEW_PLAN.md:1148 - 'suite 21/21' -> ran it: 22/22, and the README's 22 is the correct current figure. Explicitly flagged point-in-time at :1143.

- docs/V131_REVIEW_PLAN.md:1150 - 'mutations: 79 entries, 78 executed' -> tools/mutation_check.py MUTATIONS now has 82 entries (78 with posix_only=False, 2 True, 2 'nt').

- docs/audits/p14_triage.md:71 - '2 of the 79 executed mutations' -> 82 entries today.

- docs/audits/p14_new_code_review.md:60 - '81 of 81 mutations executed' / 'the entire 81-entry evidence base' -> 82 today.

- docs/V131_REVIEW_PLAN.md:1357 (C1) - 'gate_runs.json has 102 entries, all run_selftests' -> 104 entries, still 100% run_selftests. The substantive claim holds; only the count drifted (and 2 of the 4 new entries landed during this audit, from another agent on this machine).

- docs/V131_REVIEW_PLAN.md:944-945 - 'pre_push_gate.py = 1038 lines' / 'fast_test_on_stop.py = 821 lines'. Both were exactly true at commit 4b78393; now 584 / 539.

- docs/audits/p14_triage.md:56 (propagated verbatim to the plan at :1223) - '41 of the 42 recovered findings have a clear twin in the main 42 (97.6%)'. Section 2a immediately below is headed 'No twin in the main 42 - additional findings' and lists TWO rows (F-M8 and F-L8), which gives 40 of 42 = 95.2% on the literal reading. The merged arithmetic at :97 (42 + 1 dropped + 1 F-L8 = 44) only balances if F-M8's twin is counted as the DROPPED candidate, which by the doc's own framing is not in 'the main 42'. Either the 41 or the section heading is wrong; the denominator is stated but the set it is measured against is not.

- docs/V131_REVIEW_PLAN.md:1152 - 'check_review_freshness --release: asked about 31/31 tracked .py files that day ... has since grown to 35' -> 35 confirmed today (git ls-files '*.py' = 35, and the gate prints '5/35 units reviewed'). This one aged correctly.


### Notes

DENOMINATOR: 71 concrete claims extracted and tested across docs/V131_REVIEW_PLAN.md (P12, P13 final-gate-state and all of P14), docs/audits/p14_triage.md, docs/audits/p14_new_code_review.md, docs/audits/p14_cluster1_evidence.md and README.md. 13 false, 6 unverifiable, 10 stale-but-dated. The other 42 held up under direct execution.

METHOD / INTEGRITY. Everything that writes was run in a tar copy at %TEMP%\...\scratchpad\ub. The real repo is untouched: git status is empty and HEAD is d641da7. I did NOT run tools/mutation_check.py or tests/test_integration.py. Proof my run_selftests invocations did not touch the repo ledger: the two entries added to the real docs/audits/gate_runs.json during this window are 05:15:48Z and 05:27:08Z; mine are 05:14:18Z and 05:15:24Z and exist only in the copy (set-differenced both files).

STATE CHANGED UNDER ME, flagging because it re-anchors several claims. When I started, HEAD was 1dcf430 with 7 modified + 2 untracked files. Mid-audit another agent committed them as d641da7 ("fix: route 5 live unrouted caps; keep the corpus, revert the detector") and pushed to origin/main. Two claims flip on that commit: the hook_health_check.py:470 unrouted cap (now fixed) and B6's "CI has never run on any of this session's work" (now pushed). hooks/capped_report.py is still byte-identical to 1dcf430 - `git diff 1dcf430 HEAD -- hooks/capped_report.py` is empty - so the revert claim itself holds.

THE FINDING THAT MATCHES YOUR OWN LENS. docs/audits/p14_cluster1_evidence.md - the document the plan calls the home of the "full evidence" - silently truncates its own content with no notice. 15 of 279 non-empty lines are cut mid-word, and the cut lengths repeat exactly: 702 chars x13, 588 x5, 329 x8, 348 x2, 322 x2, 701 x2, 902 x2. That is a per-field display cap applied at write time. The 107-item false-positive list at line 27 stops at ~37 entries inside an unterminated string. No "...and N more" anywhere. This is the exact defect capped_report.py exists to prevent, in the artifact recording the fight over capped_report.py, and no gate looks at it. It is also why the plan's "123-hit false-positive budget" cannot be checked: the budget it points at is both a different number (107) and not fully present.

THE SECOND STRUCTURAL ONE. The 800-line rule (N3) is correct that nothing enforces it - I grepped and there is no gate - but the rule is currently SATISFIED by every file (max 781, hook_health_check.py). So N3 as written blocks the v1.3.1 ship on a HIGH whose stated instance no longer exists, while its real content (build the detector) is buried in a row whose headline number is 11.7x wrong. Same shape as the roster-not-detector class it is complaining about.

WHAT THE PLAN GOT RIGHT, verified by running code, so you can trust the negative results above came from a working harness:
- "5 of 6 cap spellings blind" (p14_triage.md:26-31): reproduced EXACTLY, row for row, including the `caps` column. The control (MAX_BULLETS = 12) flagged; the other five did not.
- mutation_check `executed` omits len(errors): confirmed at tools/mutation_check.py:541.
- The SKIPPED bucket is unreachable: `skipped` is assigned at :502 and its ONLY append site is the ternary at :532, `(other_platform if "only" in verdict else skipped)`. Both SKIPPED strings - :413 "SKIPPED (posix only ...)" and :415 "SKIPPED (windows only ...)" - contain "only". So `skipped` is always empty, and the `if skipped:` block at :562-567 including the `CI must not skip: failing / return 1` guard is dead code.
- run_selftests A3: AST call graph confirms main() does not reach missing_gates() at any depth; the only two call sites (:232, :239) are both inside selftest(). Mutation A3's anchor text is present exactly once.
- has_decision_tag: A/B with two controls - plain "TODO: rewrite the parser" -> False (correct), "[SCHEDULED]" -> True (correct) - and then True for an allow-word inside a URL query, a markdown link, an ordinary parenthetical and a code span. All fo

---

## Completeness audit - denominator 56, 54 already homed


### Findings with NO home (2)

- F-L8 (LOW, hooks/transcript_util.py) - the transcript_util X6 residual. p14_triage.md:65 section 2a rules it **NEW**: the main run refuted the X5+X6 finding WHOLESALE, the first run's refuter agreed about the composition but kept a residual - 'X6 alone is a real surviving mutation worth one misclassified entry in 2033, and two concrete killing fixtures are supplied'. p14_triage.md:97 counts it into the merged total (+1 LOW -> 44). DEMONSTRATED ABSENT: grep of docs/V131_REVIEW_PLAN.md returns 0 hits for 'F-L8', 0 for 'X6', 0 for 'has_user_media', 0 for 'outrank'; all 11 'transcript_util' hits are at L674/764/790/813/938/956/1019/1212/1264/1348 and only L1212 is a P14 work-order row, which reads total=1 - the twin-guard MEDIUM alone. ARITHMETIC CONFIRMATION: the 12 work-order rows sum to HIGH=11 (matches merged 11) and total=43 (merged is 44); per-unit reconciliation of all 12 units shows exactly ONE mismatch, transcript_util plan=1 vs sources=2. Row 1 was correctly grown 7->8 for the dropped candidate; row 11 was never grown 1->2 for F-L8.

- The resume-boundary reconciliation gap (p14_triage.md:102-110, section 4, headed 'The harness gap this exposed, which no row above closes'). Source text: 'A resumed workflow re-ran its lenses instead of replaying them and returned only the second run's results... Nothing in the harness reconciles across a resume boundary.' DEMONSTRATED ABSENT: grep of the plan returns 0 hits for 'resume' and 0 for 'resume boundary'; the only 'reconcil' hits are L962, L982, L1222, L1226, none of which is a row and none of which addresses cross-resume reconciliation. The nearest plan row, N6 (L1319), covers the DIFFERENT failure that a COMPLETED workflow's evidence is not persisted, and its own text names section 4 as the thing it 'recurs from' one layer up - so N6 is the child, not a home for the parent. Not a code defect, but the source doc explicitly flags it as uncovered, and the plan's own stopping rule says everything gets a scheduled row.


### Rows moot or false after the revert (15)

- C1-R1 (L1301) - names `_body_changes_length` and cites the fixture at `hooks/capped_report.py:1331`. MEASURED: `_body_changes_length` has 0 hits across all 36 tracked .py files; capped_report.py is 180 lines, so :1331 is out of range. The named fixture `pop_until_under_cap` survives only in tests/cap_spelling_corpus.py.

- C1-R2 (L1302) - names `_callee_aliases` at `capped_report.py:806-824`. MEASURED: 0 hits repo-wide; :806 out of range (file is 180 lines).

- C1-R3 (L1303) - 'Two dead branches in `_cap_names` (:333-335 Assign target, :355-357 parameter-name)'. MEASURED: `_cap_names` 0 hits repo-wide; both line refs out of range. The baseline equivalent is `_max_names` (capped_report.py:68-76), which has neither branch.

- C1-R4 (L1304) - names `_BASELINE_FLOOR_NAMES` and the `is_cap_name` guard rail. MEASURED: both 0 hits repo-wide. The whole no-regression floor it describes does not exist.

- C1-R5 (L1305) - names `_is_size_measure`. MEASURED: 0 hits repo-wide.

- C1-R6 (L1306) - 'caps is MODULE-scoped, so one function's cap-valued default promotes its lowercase parameter name file-wide' and 'deleting the kwonly lines leaves the gate fully green'. MEASURED: `kwonlyargs` 0 hits repo-wide; the baseline `_max_names` never inspects parameters at all, so neither the FP surface nor the unpinned half exists.

- C1-R7 (L1307) - names `exemption_problems()`. MEASURED: 0 hits repo-wide. The baseline BOUND_EXEMPTIONS (capped_report.py:34-38) has no liveness check whatsoever, which is the ORIGINAL P14 MEDIUM finding (row 1), not this residual.

- C1-R8 (L1308) - quotes `capped_report.py:54-55` as stating an invariant 'true for the 111 spellings in _TAXONOMY and false for the six blind spots named beside int_cap_sites'. MEASURED: `_TAXONOMY` and `int_cap_sites` both 0 hits repo-wide; capped_report.py:54 is now a blank line inside render()'s docstring. The quoted sentence does not exist.

- L1275-1276 - '**All 8 original findings closed, plus 7 round-2 findings and 1 round-3 finding.** Verified by re-running every gate directly rather than accepting the agents' reports.' FALSE post-revert, and DIRECTLY CONTRADICTED by the correction box 30 lines above at L1245-1249 ('all 8 original cluster-1 findings are OPEN again'). Unlike the 'CLOSED to the severity bar' claim, this one was never corrected. Verified: hooks/capped_report.py is byte-identical to 1dcf430 (git diff 1dcf430 -- hooks/capped_report.py is empty; 180 lines).

- L1296-1297 - 'Severity bar for the v1.3.1 ship is zero HIGH. **None of the below is HIGH**, so cluster 1 meets the bar; every item still has a home here.' FALSE post-revert. The statement is true of the C1-R table in isolation but its conclusion is not: work-order row 1 (L1202) carries 4 open HIGH against hooks/capped_report.py, so cluster 1 does NOT meet the zero-HIGH bar. This is the most consequential false row - it reads as a ship-gate clearance.

- N3 (L1316) - '`capped_report.py` is now **2101 lines**, 2.6x the limit and the worst violator in the repo'. FALSE: 180 lines. MEASURED: 0 of 36 tracked .py files exceed 800 lines, so the class has NO live instance today. The prescribed fix ('split the ~1200-line fixture corpus into `capped_report_selftest.py` ... registering it in the five flat hooks/ rosters') is fully moot - the corpus now lives in tests/cap_spelling_corpus.py, outside hooks/. The first clause (build a line-count gate that derives its file list) is still live and still HIGH. Partially corrected by the plan itself at L1323-1324, but the row text was not rewritten.

- N4 (L1317) - 'Cap-name convention is asymmetric on one shape: lowercase `cap`/`limit` ARE cap names; `max_lines`, `TOP_N`, `BULLET_COUNT`, `N_BULLETS` are not.' MOOT: the baseline `_max_names` recognises exactly ONE form - a module-level ast.Assign to a bare ast.Name whose id startswith('MAX_'). Lowercase `cap`/`limit` are NOT cap names in the reverted guard, so the stated asymmetry does not exist. The measurement it cites (0 of 197 in-scope UPPER_SNAKE constants newly match) is still useful input to C1-NEW.

- N5 (L1318) - '`_cap_names` models 12 of Python's 24 name-binding forms.' FALSE: `_cap_names` has 0 hits repo-wide. The baseline `_max_names` models ONE binding form. The row understates the gap by an order of magnitude in the direction that matters.

- L1190 - '**Not started.** No fix from this list has been applied.' NOW IMPRECISE. Commit d641da7 (landed 2026-08-02 08:14, mid-audit) applied two live instances named INSIDE P14 findings: hook_health_check.py:470 `problems[:12]` routed through capped_report.render (the 'fifth unrouted cap' in the HIGH at p14_new_code_review.md:70), and the transcript_util #13 anchor disambiguation (the live instance of the MEDIUM at :121). The plan itself lists both at L1260-1265. Neither CLOSES its finding - the general defects remain open, verified: tools/mutation_check.py still tests anchors by presence (`if find not in live_text` :405, `if find not in text` :450), never uniqueness.

- L1260-1265 - 'Kept from those two rounds (real value, **verified after the revert**)'. The verification was incomplete. hooks/show_your_proof.py's retained docstring (:238-241) says the judgement 'is written down in capped_report.SIZE_EXEMPTIONS rather than left implicit'. MEASURED: `SIZE_EXEMPTIONS` has 1 hit repo-wide (show_your_proof.py) and 0 in capped_report.py, whose only module-level names are BOUND_EXEMPTIONS, _max_names, keep, render, selftest, slicing_offenders. The written decision the plan credits as kept has no destination - the retained fix points at a roster the revert deleted.


### Soft-defer sweep (10)

- ZERO REAL DEFERS UNDER THE BRIEF'S EXACT VOCABULARY. Sweep for park|on demand|someday|maybe later|if time|wait for a concrete case|deferred opportunistic over all 1382 plan lines returned 4 hits, none a defer: L858 and L1006 quote a meta_audit_on_stop regex defect ('the PARKED marker regex misses the bare uppercase PARK') - data, not a defer; L931 is P12's own prior sweep result 'Parked-but-unscheduled: none' (a STALE claim - it predates every P14 row, written 2026-07-31); L943 is the explicit anti-defer 'Optimization - two files now exceed the 800-line rule. SCHEDULED, not parked'. Verdict: 0 of 4 are optional-forever.

- L1301-1308, C1-R1..C1-R8, owner column = 'next cluster-1 touch' (8 rows, all MEDIUM except C1-R8 LOW). REAL scheduled rows, but the owner names no row and no order. Binding to a real home exists only in prose 30 lines below: A2 (L1337) 're-scoped as acceptance criteria for C1-NEW, not as live bugs'. Verdict: HOMED via C1-NEW, but the row itself does not say so - a reader of the table alone sees an unscheduled owner.

- L1346, B3 MEDIUM two-round rule - 'NOT DECLINED by the user - left unticked, explicitly kept open'. Verdict: has a row and a severity, has NO owner and no position in any order. The plan's own stopping rule (L1234-1235) requires 'a written owner AND a scheduled row'. Half-homed. (Correctly refuses to read an un-ticked option as a decline.)

- L1347, B4 MEDIUM fixture-coverage gate + evidence persistence - 'NOT DECLINED - left unticked, kept open'. Same shape as B3: row yes, owner no. Half-homed.

- L1350, B7 LOW - 'widen it to any generated-code path, OR accept it as a judgement call'. THE ONE GENUINE OPTIONAL-FOREVER ROW IN P14. It uses none of the brief's keywords, but the disjunction lets the row be closed by doing nothing, with no owner and no decision recorded. Recommend: resolve the OR now, in writing.

- L1361-1366, table D 'Approved by the user, not yet built' - D1 (self-budgeting selftests) and D2 (no-regression-vs-predecessor gate). Approved, but the table carries no severity, no owner and no order column. D2 is the mechanism L1283-1286 calls 'the class NOTHING in this repo currently catches' and the reason for the P15 bound - so an unscheduled row is carrying a load-bearing gate. Half-homed.

- L1359, C3 - 'Freshness is 5/35 units reviewed since last change, 10 UNRESOLVED. --release is correctly red. No action; recorded so the denominator is visible.' Verdict: LEGITIMATE FINALIZED-EXCLUSION. Justification quoted, denominator printed, no severity claimed.

- L1190 'Not started.' / L1267 'The rebuild is scheduled as C1-NEW below and has not started.' / L1368 '#### C1-NEW - the fail-closed rebuild, not started'. Verdict: status statements attached to named rows, not defers.

- L1375 'Blocked on B5 (the same premise may be wrong elsewhere)'. Verdict: legitimate - B5 is itself a HIGH row in table B, so the blocking chain terminates in a scheduled item. Noted only because every link in the chain (C1-NEW <- B5) is currently unstarted.

- L6 'Nothing here is optional.', L1235 'never "optional", never prose.', L1294 '#### OPEN against cluster 1 - scheduled, owned, none optional'. Verdict: these are the anti-defer RULE and a heading asserting it. Not defers. L1294's claim is however coupled to the FALSE sentence at L1296-1297 (see moot_rows).


### How the denominator was built

DENOMINATOR (56) AND HOW IT WAS BUILT, all mechanically re-derived rather than copied:

(a) 44 = the merged P14 backlog, p14_triage.md section 3. I re-extracted every top-level bullet from p14_new_code_review.md by script: main run 10 HIGH / 22 MEDIUM / 10 LOW = 42 (matches), refuted = 4, recovered first run 9/23/10 = 42 (matches the doc's stated spread). 42 + 1 dropped candidate now CONFIRMED + 1 F-L8 = 44; the two escalations (M-L7, M-L10, LOW -> MEDIUM) change the mix (11/24/9) but not the count.
(b) 11 = the distinct cluster-1 residuals in p14_cluster1_evidence.md: round 2's 'Still open (2)' (R2-H2, R2-M3) union 'New defects introduced (7)' = 8 distinct, plus round 1's 3 written caveats (naming widening, the 800-line overage, sources.py:87). Round 1's own 'Still open (7)' is NOT added - round 2 closed 7/7 of them, so they are subsumed, then mooted by the revert.
(c) 1 = the p14_triage section 4 harness gap.

DISPOSITION OF ALL 56.
BUILT: 0 of 56. Nothing in the backlog is closed. Two LIVE INSTANCES inside findings were fixed and committed (hook_health_check:470, transcript_util #13 anchor) but both findings' general defects are open - I verified the M-M12 general fix is absent (mutation_check.py still uses `find not in text`, lines 405 and 450). hooks/capped_report.py is byte-identical to 1dcf430, so all 8 cluster-1 findings are open.
SCHEDULED: 54. The 43 backlog items covered by work-order rows 1-12 (L1200-1213); the 11 cluster-1 residuals covered by C1-R1..R8 (re-scoped by A2 as C1-NEW acceptance criteria) and N1-N4.
FINALIZED-EXCLUSION: 0 within the 56. The 4 REFUTED findings sit outside the denominator by construction, each with a written justification in p14_new_code_review.md:211-214. One caveat: the refutation of the transcript_util X5+X6 item is only PARTIALLY final - the plan records '4 refuted' flatly at L1159, while p14_triage promoted its X6 residual to a new LOW (F-L8), which is gap 1.
GAP: 2.

PER-UNIT RECONCILIATION, the load-bearing evidence for gap 1. Parsing the 'where:' line of all 42 main findings and adding the triage's two additions gives, per unit: capped_report 8, mutation_check 9, run_selftests 3, pre_push_gate_selftest 2, meta_audit_on_stop 6, check_review_freshness 8, stop_dispatcher 2, numbers_match_on_write 1, plan_defer_guard 1, check_readme_fresh 1, transcript_util 2, rate_prompt 1. Against the plan table every unit matches EXCEPT transcript_util (plan 1, sources 2). Plan HIGH sum = 11 = merged HIGH; plan total sum = 43 = merged 44 minus one.

TWO NOTES THE ESCALATIONS DESERVE. M-L7 (mutation_check CAUGHT-is-any-nonzero) and M-L10 (stop_dispatcher `crashed` ledger key) are homed inside rows 2 and 7, but the work-order table has only HIGH and total columns, so it cannot express a severity change. The plan says 'two severity ESCALATIONS' at L1224 without naming them or their added live instances ('2 of the 79 executed mutations already die on an uncaught traceback'; '`crashes.clear()` is a SECOND unpinned thing'). A reader of the plan alone under-rates two findings. Not a gap - the pointer to p14_triage.md is explicit - but the plan is not self-sufficient here.

APPLYING THE FAIL-CLOSED LENS TO THIS AUDIT'S OWN SUBJECT. The C1-NEW spec (L1370-1376) is the fail-closed inverse rule and is correctly bounded ('by the number of real cap sites in the repo (~6-14), not by Python's grammar'), and its grader is real: I executed tests/cap_spelling_corpus.py --selftest, which prints '111 entries = 82 must-flag + 29 negative controls' and exits 0, and confirmed 111 unique names and a star-import entry. Two frictions. (i) The corpus docstring's first line reads '111 labelled ways to bound a list, and 29 ways that are not', which parses as 140 entries; the true split is 82 + 29 = 111, as its own selftest line says. The plan's phrasing ('all 111 entries must be SEEN; the 29 negative controls become "seen then exempted with a reason"') is the correct reading. (ii) B1 (L1344, HIGH) encodes exactly the principl

---

## Mechanism design: D2 - no-regression-vs-predecessor gate (tools/no_regression.py)   (validated=True)


**Design**

GOAL: block any change to a unit that stops detecting something its predecessor detected. Mutation entries pin what a fix ADDS; this pins what it TOOK AWAY.

CORE LOOP: load two versions of one file into one process, run both over a shared corpus of planted fixtures, diff the detection sets, block on any capability present before and absent after unless a reason is on record.

--- Q1 CORPUS AND COVERAGE ---
A corpus is a module exposing ENTRIES = ((name, rel_path, must_flag, source), ...) - the exact contract tests/cap_spelling_corpus.py already ships. Fixtures are planted at rel_path so directory-scoped guards are exercised.

Declaration lives in a REGISTRY in the current tree (tests/noregress_registry.py), not in the unit, because the predecessor cannot be asked how it wants to be called: REGISTRY = {"hooks/capped_report.py": {"corpus": "tests/cap_spelling_corpus.py", "probe": "cap_detector", "renamed_from": None}}.

The UNIT POPULATION is DERIVED, never listed: walk hooks/ tools/ scripts/ skills/ for .py files that both mention --selftest and define selftest()/_selftest(). Measured on the live repo: 21 units, 1 registered, 20 skipped. The registry can only say HOW to probe; it can never shrink the denominator.

A unit with no corpus is SKIP with the reason printed on its own line ("no corpus declared - UNCOVERED, not passing") and a coverage line "1 of 21 units (5%)". A registry entry naming a path that does not exist is a GHOST and is BLOCKING - that is what makes a rename impossible to do silently (verified: renaming the unit in a clone produced "REGISTRY GHOSTS: 1 -> ['hooks/capped_report.py'] -> FAIL").

--- Q2 TWO VERSIONS IN ONE PROCESS ---
importlib.util.spec_from_file_location under a UNIQUE generated module name per load (_noregress_cur_1 / _noregress_prev_2), inserted into sys.modules before exec_module. VERIFIED: both modules coexist, A.render is not B.render, both callable after both are loaded, load cost 0.014 s for 180 + 2124 lines. No subprocess needed.

THE REAL HAZARD IS NOT IMPORT, IT IS INVOCATION. Measured: the same fixture is seen by the 1dcf430 baseline only via slicing_offenders(<hooks dir>) (flat glob) and by the round-2 version only via slicing_offenders(<repo root>) (tree walk). A gate hard-coding either call measures the other version as detecting nothing.

So the probe SELF-CALIBRATES per version: score every (entrypoint, argument-strategy) pair over a sample of the corpus positives and keep the highest scorer. Entrypoints tried by capability name, not signature; strategies are root and dirname-of-planted. Escalation: if the 8-case sample scores 0 for every combination, rescore over the FULL positive set before concluding blindness - this is load-bearing, because round-1's blind spot IS the first 8 samples, and without escalation the gate over-reports 67 lost instead of the true 14.

ZERO SCORE IS NEVER A PASS, and the two sides are treated differently:
 - PREV scores 0 -> raise Broken, print "yardstick unusable", emit NO VERDICT (exit 2). A ruler that measures nothing is a broken harness, not a clean tree.
 - CUR scores 0 -> TOTAL LOSS, verdict FAIL, listing every capability the predecessor saw. The gate cannot distinguish "capability removed" from "entrypoint renamed without updating the registry" and must not try - both need a human.

CONTROLS run before any verdict, both directions: each version must (a) detect the positive control under its chosen strategy, and (b) stay silent on an empty tree AND on a cap-free file. Any disagreement -> BROKEN, no verdict.

One planted temp tree per corpus entry, read by BOTH versions. Halves filesystem cost (probe phase 0.365 s -> 0.165 s for 72x2) and removes the confound of the two versions reading different bytes.

--- Q3 WHAT "PREVIOUS VERSION" MEANS (exact) ---
1. current = the WORKING-TREE bytes (that is what ships).
2. commits = git log --follow --format=%H -- <rel>, newest first.
3. for each, read the blob; the FIRST blob differing from current (after \r\n normalisation) IS the predecessor.
4. no differing blob -> NO_PREDECESSOR, reported as a named SKIP with its reason, never as a pass.

Walking PAST identical blobs is what makes this work. The regression this gate exists to catch happened entirely between two UNCOMMITTED rewrites - hooks/capped_report.py has exactly ONE commit in its whole history (f3ebc8f) and its blob there is byte-identical to 1dcf430 and to HEAD. A rule of "HEAD~1" or "the last commit touching the file" would have compared two identical files and passed. VERIFIED end to end on a clone: with the round-1 rewrite sitting uncommitted, the gate resolved PREV=f3ebc8f from git and blocked with 14 named regressions.

Same rule handles a revert: after reverting, current equals an older blob, so the walk finds the reverted-away version and the removal must be recorded rather than passing silently.
First-commit case: no commits touch the path -> "file has never been committed" -> SKIP with reason, counted as uncovered.
--follow is required: verified that a committed rename leaves the new path with only the rename commit in plain git log, and --follow recovers f3ebc8f.
Uncommitted rename + rewrite is the one case git cannot resolve: both git log and git log --follow return EMPTY for the new path, and default rename detection reports A/D because similarity is 9%. Two independent catches, both verified: git diff -M05 --name-status HEAD finds it (R009), and the registry ghost check fails regardless.

--- Q4 THE ESCAPE HATCH (deliberate narrowing) ---
A waiver ledger, tests/noregress_waivers.py, keyed by (unit, capability id from the corpus) with a free-text reason. It is a RECORD, not a flag: there is no per-unit disable and no --skip.

FIVE states, all enforced and all demonstrated:
 ACTIVE  - lost vs predecessor right now and a reason is on file -> non-blocking, printed.
 SETTLED - the narrowing landed earlier, so NEITHER side detects it -> keep the record as the standing reason, non-blocking.
 STALE

**Exact changes**

- C:/Users/ammar/Downloads/unbluff/tools/no_regression.py (NEW, ~380 lines): the gate. load_version() (spec_from_file_location + unique sys.modules name); predecessor() (git log --follow, first differing blob, \r\n normalised, NO_PREDECESSOR reason strings); CapProbe with calibrate(positives, sample=8) + full-set escalation + negative_controls(); run_ab() with one planted temp tree per entry read by both sides; the five-state waiver ledger; report() with a denominator on every line; roster derivation over hooks/ tools/ scripts/ skills/; and selftest() carrying assertions A/B/C/D/E above. Must hold the Python 3.8 floor the CI matrix tests (use `from __future__ import annotations`, %-formatting, no walrus).
- C:/Users/ammar/Downloads/unbluff/tests/noregress_registry.py (NEW, ~45 lines): REGISTRY = {unit_relpath: {corpus, probe, renamed_from}}. One entry today: hooks/capped_report.py -> tests/cap_spelling_corpus.py, probe 'cap_detector'. Header states the rule that this file may only say HOW to probe, never WHICH units count.
- C:/Users/ammar/Downloads/unbluff/tests/noregress_waivers.py (NEW, ~30 lines): WAIVERS = () to start, entries {unit, capability, narrowed_on, reason}. Docstring records the five states and that a stale record is a blocking failure, not a warning.
- C:/Users/ammar/Downloads/unbluff/tests/cap_spelling_corpus.py (APPEND ~14 entries, ~45 lines): the 7 scalar-suffix name families x {display, collection} that the committed corpus is missing - MAX_LEN, MAX_BYTES, MAX_CHARS, MAX_SECONDS, MAX_FILE_BYTES, MAX_LINE_CHARS, MAX_TOTAL_BYTES. MEASURED GAP: on today's corpus the round-1 regression scores 1 lost of 18; on a corpus containing these it scores 14 of 67. Append-only, so this is legal under the file's own contract. Recommend must_flag=True (the 1dcf430 baseline flagged all 14, and slicing a LIST is a display cap whatever the constant is named); if the repo disagrees, appending them as must_flag=False is itself the recorded decision and D2 will then classify the loss as an improvement.
- C:/Users/ammar/Downloads/unbluff/run_selftests.py (EDIT, ~5 lines): add ('no-regression', ('tools', 'no_regression.py'), ('--selftest',)) to AUX_GATES with a one-line reason. REQUIRED, not optional: the file's classification check fails if a tools/*.py appears in neither AUX_GATES nor NOT_A_GATE. Suite goes 22/22 -> 23/23.
- C:/Users/ammar/Downloads/unbluff/.github/workflows/selftest.yml (EDIT, ~12 lines): a `noregress` job (ubuntu + windows) running `python tools/no_regression.py --repo . --all`, i.e. the full roster with git history present. Needs fetch-depth: 0 on actions/checkout - the default shallow clone breaks predecessor resolution and would turn every unit into a NO_PREDECESSOR skip, which is precisely the fail-open shape this gate exists to prevent.
- C:/Users/ammar/Downloads/unbluff/hooks/pre_push_gate.py (EDIT, ~6 lines): run the gate for units whose worktree differs from their predecessor. Measured cost of the no-change path is 0.38-0.62 s wall, so the common case is a git call and nothing else.
- NO CHANGE to hooks/capped_report.py: the probe adapter lives in the gate, so the unit needs no cooperation and cannot disable its own check.

**Would have caught**

- THE HEADLINE CASE, reproduced end to end. With the round-1 rewrite (864 lines, md5 5d85b469..., preserved at .../scratchpad/base/hooks/capped_report.py) sitting UNCOMMITTED in a clone's worktree, the gate resolved PREV=f3ebc8f from git and reported: 'LOST (true det.): 14 of 67 the predecessor saw', VERDICT FAIL, naming name_MAX_LEN_{display,collection}, name_MAX_BYTES_*, name_MAX_CHARS_*, name_MAX_SECONDS_*, name_MAX_FILE_BYTES_*, name_MAX_LINE_CHARS_*, name_MAX_TOTAL_BYTES_*. This is the exact set the session's own ab_noregress.py independently reports (14 GENUINE REGRESSIONS, identical names, identical 67-of-69 denominator) - two independently written harnesses agreeing.
- The same defect against the COMMITTED corpus, which is the configuration that would actually have shipped: round-1 vs baseline over tests/cap_spelling_corpus.py scores 'LOST (true det.): 1 of 18' on scalar_slice_without_a_roster_entry, VERDICT FAIL. It still blocks - it just understates the damage 1 vs 14, which is why appending the 14 entries is in the change list.
- The silence that let it through: run_selftests 22/22, integration 30/30 and 92 of 94 mutations ALL CAUGHT were all green on the round-1 rewrite, because every one of those asks whether the NEW code does what the NEW code claims. D2 is the only check in the change list whose question is about the OLD code.
- An entrypoint rename that quietly disables a guard - selfcheck C: renaming slicing_offenders away on the current side yields TOTAL LOSS + 17 unwaived + FAIL. A gate keyed to a function name would have silently found nothing and printed clean.
- The reverse framing of the same trap - selfcheck E: a predecessor that detects nothing raises Broken and emits NO verdict, instead of the 'zero regressions, all clean' a fail-open harness would print. This session already produced two harnesses whose own controls failed.
- Erosion of the waiver roster itself - selfcheck D: a waiver whose capability the current version detects again is STALE and blocking. Without it the ledger becomes a permanent silencer, which is how the BOUND_EXEMPTIONS roster rots.
- A rename used to escape the gate: an uncommitted `git mv` plus rewrite makes both `git log` and `git log --follow` return EMPTY for the new path (verified in the clone; git scores the pair at 9% similarity so default -M50 reports A/D, not R). Caught twice over - `git diff -M05 --name-status HEAD` recovers the pair, and the registry ghost check fails on its own.

**False-positive risk:** MEASURED, not estimated. Determinism first: identity runs (same file both sides) report 0 lost, over 3 repeats on each of two corpora plus selfcheck A - no flake.

The real FP source is a change that correctly stops emitting a false positive. The corpus label handles it automatically, and this session contains a live instance. Round-1 vs baseline on the committed 111-entry corpus stopped flagging exactly 2 things: scalar_slice_without_a_roster_entry (must_flag=True -> blocking regression, correct) and neg_scalar_slice_rostered (must_flag=False -> the baseline's own false positive, auto-classified 'improvement, non-blocking', correct). So 1 of the 2 lost detections was suppressed without human involvement - that is the measured suppression rate on the real corpus, and the baseline's total FP count there is 1 of 29 negative controls.

Residual risk is a genuine narrowing of a must_flag=True entry, which fires by design and costs one waiver line with a reason - the bookkeeping the reverted detector spent 2000 lines and 35 seconds avoiding. Bounded in practice: the 14 round-1 losses are 7 name families, so the whole regression is 14 records or, more honestly, a decision to append those 14 corpus entries as must_flag=False in the first place.

Two mis-diagnosis risks I hit and closed rather than papered over: (1) my first calibration used a single control, so blinding the capability also blinded the control and the harness said BROKEN instead of REGRESSION - fixed by calibrating o

**Cost:** RUNTIME, all measured on this Windows box.

In-process (3 repeats each, median), 180-line predecessor as PREV:
  base(180) vs base(180)  fixture corpus 72 -> 0.384 s | repo corpus 111 -> 0.539 s
  r1(864)   vs base(180)  fixture 72 -> 1.086 s | repo 111 -> 0.777 s
  r2(2124)  vs base(180)  fixture 72 -> 0.420 s | repo 111 -> 1.062 s
Per corpus case: 4.9-15.1 ms. The r1/72 case is the slowest because it triggers full-set calibration escalation.

Full CLI wall including interpreter start and git subprocesses:
  unit UNCHANGED (the common case, git-only skip path): 382, 409, 416, 422, 432, 529, 542, 615 ms across 8 runs.
  unit CHANGED (load + calibrate + 72x2 probes): 1310, 1563, 1864, 2244, 2655 ms across 5 runs, median 1.86 s.

Extrapolation with its denominator: 1 of 21 units is covered today, so CI cost is ~2 s. If all 21 had corpora it is ~20-40 s for a full sweep - fine for a CI job, which is why the full roster goes to CI and the stop/pre-push path runs only changed units. For scale: the reverted detector's own selftest was 36.1 s.

LINES: prototype tools/no_regression.py is 541 lines including the docstrings that carry the rationale and its own 5-assertion selftest; the shipped version lands ~380 excluding the roster helper. Support files ~120 lines (registry 45, waivers 30, corpus append 45). Integration edits ~23 lines across run_selftests.py, selftest.yml, pre_push_gate.py. Total ~525 lines added, against the 2101-line detector this replaces the need for.

**Notes**

PROTOTYPE LOCATIONS (all under the OS temp scratchpad, nothing written to the repo):
  C:/Users/ammar/AppData/Local/Temp/claude/C--Users-ammar-Downloads-Claude/61196ffe-d66d-4ad7-9208-af4a3f565559/scratchpad/d2/d2_noregress.py  (the gate, 541 lines, --selftest passes 5/5)
  .../scratchpad/d2/roster.py       (coverage roster, run against the live repo: 1 of 21)
  .../scratchpad/d2/cost.py         (the timing table above)
  .../scratchpad/d2/mk_fixture_corpus.py + fixture_corpus.py  (72 fixtures reshaped from the session's ab_noregress.py)
  .../scratchpad/d2/blobs/v_1dcf430.py, v_f3ebc8f.py, v_HEAD.py  (git show, all three byte-identical)
  .../scratchpad/d2/clone_repo      (a git clone used for every worktree mutation)
READ-ONLY HELD: C:/Users/ammar/Downloads/unbluff reports `git status --porcelain --untracked-files=all` empty at the end of this session. mutation_check.py and tests/test_integration.py were never invoked.

DISCREPANCY WITH THE BRIEF, stated plainly. The brief says the round-1 rewrite "was blind to 10 of 14 cap spellings its predecessor caught". I cannot reproduce a 10-of-14. Both my independently written gate AND the session's own ab_noregress.py measure the SAME thing: 14 regressions out of 67 baseline-visible fixtures (of 69 non-negative, of 72 total), across 7 MAX_* name families x {display, collection}. The defect class, direction and named cases all confirm; only the two numbers "10" and "14" do not - "14" is the count of LOST cases, not the denominator.

ITEM 6 AS WRITTEN IS NOT SATISFIABLE, and this is a finding rather than a failure to validate. The file named there, scratchpad/capped_report_r2_full.py (2124 lines), is the ROUND-2 version, and it loses NOTHING against 1dcf430: 0 lost of 67 on the fixture corpus and 0 lost of 18 on the repo corpus, gaining 65 - it is a strict superset. The regression lives in ROUND 1. I located that artifact by line count and md5 (864 lines, 5d85b469..., identical copies at scratchpad/base/, base2/, v_D2/, w/treeA/) and reproduced the regression there, in both the explicit-A/B mode and the git-derived-predecessor mode.

WHAT THIS GATE CANNOT DO. It is exactly as sharp as its corpus - on today's committed corpus the round-1 regression reads as 1 lost, not 14, because 13 of the 14 spellings were never appended. It blocks either way, but the corpus append is what makes the report honest. This is the bounded-noise trade the reverted detector refused: D2 does not try to enumerate syntaxes, it only compares two versions over whatever cases exist, and every case it does not have is visibly absent rather than silently clean.

TWO DEFECTS I FOUND IN MY OWN HARNESS while building it, both now pinned by its selftest, both instances of the disease this repo names: a single calibration control conflated "probe is mis-invoked" with "capability removed" (first selfcheck run reported BROKEN where the answer was REGRESSION), and an 8-case calibration sample landed entirely inside round-1's blind spot, which

---


## Not completed

- **D1, self-budgeting selftests** - the design agent died on a session usage limit
  before returning. Nothing was lost except the design itself; the requirement is
  scheduled in the plan (phase 0) and is re-runnable via `resumeFromRunId` so the five
  completed agents replay from cache instead of re-running.

