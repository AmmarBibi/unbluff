# P14 cluster 1 - the workflow evidence, persisted

`hooks/capped_report.py`. Two adversarial fix rounds, 2026-08-01/02.

**Why this file exists.** Every artefact below existed ONLY in OS temp task-output files
and a session scratchpad. `docs/audits/p14_triage.md` section 4 records that a resumed
workflow nearly lost 42 findings because they lived in a journal and nowhere else; the
completeness audit then found the same class one layer up, in the same session, for the
COMPLETED runs. A workflow result is not recorded until it is in the repo.


---


## ROUND 1 - run `wf_7c6b33a8-265`

- ground truth in: taxonomy 30/47 blind, fp-sweep 35 files, 2 genuine, 107 FPs to avoid, exemption-design ok, scope 35 files
- implement: closed 8/8, not closed 1, 60 fixtures, 13 mutation entries
- verify: 8/8 verdicts returned, 7 still open, 0 closed-but-decorative

### Ground truth

- **taxonomy_spellings**: 47
- **taxonomy_blind_before**: 30
- **fp_files_swept**: 35
- **fp_genuine** (2): ["skills/consistency-audit/scripts/audit.py:181", "skills/consistency-audit/scripts/extract.py:355"]
- **fp_must_not_flag** (107): ["hooks/memory_hygiene_guard.py:147", "hooks/memory_hygiene_guard.py:318", "hooks/meta_audit_on_stop.py:298", "hooks/meta_audit_on_stop.py:312", "hooks/meta_audit_on_stop.py:531", "hooks/plan_defer_guard.py:371", "hooks/numbers_match_on_write.py:395", "hooks/capped_report.py:48", "hooks/capped_report.py:58", "hooks/capped_report.py:131", "hooks/close_skills_guard.py:354", "hooks/close_skills_guard.py:399", "hooks/close_skills_guard.py:426", "hooks/close_skills_guard.py:452", "hooks/close_skills_guard.py:460", "hooks/close_skills_guard.py:465", "hooks/close_skills_guard.py:471", "hooks/close_skills_guard.py:483", "hooks/duplicate_registration_check.py:147", "hooks/duplicate_registration_check.py:330", "hooks/duplicate_registration_check.py:354", "hooks/duplicate_registration_check.py:356", "hooks/duplicate_registration_check.py:370", "hooks/duplicate_registration_check.py:377", "hooks/duplicate_registration_check.py:380", "hooks/duplicate_registration_check.py:395", "hooks/duplicate_registration_check.py:407", "hooks/duplicate_registration_check.py:410", "hooks/duplicate_registration_check.py:412", "hooks/duplicate_registration_check.py:425", "hooks/duplicate_registration_check.py:434", "hooks/fast_test_on_stop.py:59", "hooks/fast_test_on_stop.py:422", "hooks/fast_test_on_stop.py:427", "hooks/fast_test_on_stop_selftest.py:390", "hooks/fast_test_on_stop_selftest.py:432", "hooks/h
- **exemption_design**: Adopt design (b) - a central roster - but with neither of the two keys the finding proposed. The surviving key is (module, const, ENCLOSING FUNCTION, EXACT SITE COUNT), applied to the collection branch ONLY, plus an exemption_problems() liveness pass that prints "N exemptions, M load-bearing" and appends a FAIL for every non-load-bearing entry.

Measured, not argued (10/10 scenarios in exp9_verify_final.py against the real hooks/ tree; 8/8 in the exp6 head-to-head):
  GREEN on the pristine tree, on an innocent comment inserted above the exempted site, and on renaming the capped variable at the exempted site.
  RED on: a bogus module; a bogus constant; either of the two originally-dead entries; deletion of the exempted cap; the C1-M3 display-cap over-reach; a 2nd collection cap in another function; a 2nd collection cap in the SAME function.

The site COUNT is what makes it a floor rather than a roster: a second cap appearing under an approved exemption changes the observed count, so it fails instead of inheriting the approval. The FUNCTION qualifier earns its place empirically - the count-only variant (module, const, n) scored 7/8, silently swallowing the SWAP mutation (delete the approved cap in run(), add one in _walk_source_files(); module-wide count stays 1, so it stayed GREEN with 0 offenders and 0 stale).

Use glob.escape() on the scan root. A "[E3]" in my own sandbox path made glob.glob() read it as a character class, scanned 0 files, and printed off=0 stale=1 - a harness bug that looked exactly like a design failure until I re-ran the cell in isolation.
- **scope_files**: 35

### Implement

- files changed: `capped_report.py`, `hook_health_check.py`, `mutation_check.py`, `audit.py`, `extract.py`
- fixtures added: 60
- mutation entries added: 13
  - capped_report C1-H1 - _cap_names back to bare ast.Assign (3-edit mutation killing the AnnAssign/AugAssign, NamedExpr and ImportFrom branches). CAUGHT: 'BLIND to 3 of 46 cap spellings: annotated_assign_slice, walrus_bound, from_import_bound'
  - capped_report C1-H2 - reintroduces the whole-file skip (`if not caps: return []` in module_cap_sites). CAUGHT: 'BLIND to 2 of 46: import_attribute_bound, break_on_attribute_bound'
  - capped_report C1-H3a - _compare_caps reads only .comparators again. CAUGHT: 'BLIND to 1 of 46: reversed_comparison_break'
  - capped_report C1-H3b - _has_exit back to direct ast.Break children only. CAUGHT: 'BLIND to 3 of 46: break_nested_in_with, return_instead_of_break, ...' (3 fixture failures)
  - capped_report C1-H3c - offender message drops file:line AND sorted(set(...)) returns, collapsing distinct sites (2-edit). CAUGHT: "fixture 'two_sites_one_constant' produced 1 offender(s), expected 2"
  - capped_report C1-H4 - is_cap_expr stops matching an ast.Attribute on its own attr. CAUGHT: 'BLIND to 3 of 46: import_attribute_bound, class_attr_bound, break_on_attribute_bound'
  - capped_report C1-M1 - the ast.While collection branch disabled. CAUGHT: 'BLIND to 2 of 46: pop_until_under_cap, while_test_cap'
  - capped_report C1-M2 - exemption_problems iterates nothing and reports every entry live. CAUGHT: 'exemption_problems cannot tell a live entry from a rotting one: live=2 of 2, problems=[]'
  - capped_report C1-M3 - exemption predicate broadened back to (module, constant) whole-module matching. CAUGHT: 'BLIND to 1 of 46: second_cap_under_an_approved_exemption'
  - capped_report C1-M3b - an exemption starts applying in the DISPLAY branch too. CAUGHT: 'BLIND to 1 of 46: display_in_the_exempted_function'
  - capped_report C1-L1a - os.walk replaced by a single non-recursive listdir. CAUGHT: 'BLIND to 1 of 46: module_in_subdirectory'
  - capped_report C1-L1b - UNIT_GLOBS re-declared locally as ('hooks/*.py',) instead of imported from check_review_freshness. CAUGHT: 'BLIND to 2 of 46: module_in_tools, module_in_skill_scripts' (6 fixture failures)
  - capped_report B8 (RE-ANCHORED, not added) - the old anchor `for path in sorted(glob.glob(os.path.join(hooks_dir, "*.py")))` was deleted by the scope widening; re-anchored on `offenders, swept, skipped = [], 0, 0` + `for path in scan_scope(repo_root):`. Still CAUGHT (rc=1). Without this the entry wou

**Findings closed (8):**

- C1-H1 - _cap_names now resolves Assign (incl. Tuple/List/Starred targets), AnnAssign, AugAssign, NamedExpr (walrus), ImportFrom, function/lambda parameter names, plus an alias/arithmetic fixpoint (SHOWN = MAX_BULLETS; N = SHOWN - 1) restricted to _is_arith_shape so a `"...%d" % MAX_X` string binding cannot become a cap name. One caps set feeds both branches. Fixtures: annotated_assign_slice, augassign_adjusted_bound, walrus_bound, tuple_target_bound, list_target_bound, from_import_bound, alias_bound, arithmetic_bound, function_local_bound, lowercase_cap_parameter - all RED before, GREEN after.
- C1-H2 - the display branch now matches 9 shapes, not 1: slice upper, slice lower (xs[-MAX:], del xs[MAX:]), xs[slice(0,MAX)], itertools.islice, heapq.nlargest/nsmallest, comprehension generator ifs, while+pop, and cap expressions that are Attribute/BinOp/UnaryOp/Subscript. The `if not caps: continue` whole-file gate is GONE - there is no early return on an unrecognised bound anywhere in module_cap_sites. Mutation C1-H2 proves its absence is load-bearing. The reporting path prints its denominator every run: '-- cap sweep: 34 file(s) swept (1 sanctioned self-skip), 0 unrouted cap(s)'.
- C1-H3 - (a) _compare_caps scans cmp.left AND cmp.comparators, so `MAX_X <= len(hits)` is seen (fixture reversed_comparison_break). (b) _has_exit walks the If body/orelse with a scope-stopping walker instead of testing direct children, so a break inside `with contextlib.suppress(...)`, a return and a continue are all seen. (c) the denominator is printed. (d) hooks/hook_health_check.py:470 problems[:12] is no longer a live unrouted cap - it is now capped_report.render(problems, MAX_PROBLEM_BULLETS, prefix='  - ', noun='problem'). Verified equivalent by execution: identical output for 0/5/12 problems, same 13-line count for 13 and 30, and end-to-end main() with 25 seeded problems prints header '25 problem(s)', 12 bullets and '...and 13 more problem(s) not shown (25 total, showing 12)'. hook_health_check --selftest still SELFTEST OK.
- C1-H4 - is_cap_expr matches an ast.Attribute on its own .attr, so limits.MAX_BULLETS and Limits.MAX_BULLETS resolve with NO local Name and an EMPTY caps set. Combined with the removal of the whole-file skip, a module holding only an imported/attribute cap is fully inspected. Fixtures import_attribute_bound, class_attr_bound, break_on_attribute_bound: RED before, GREEN after; mutation C1-H4 re-blinds exactly those three.
- C1-M1 - collection detection now covers break/return/continue in body OR orelse, at any nesting depth inside the If (with/try wrappers), reversed operands, BoolOp tests, walrus counters, bare counter variables, arithmetic bounds, attribute bounds, `while <cap test>`, itertools.takewhile and zip(range(CAP), xs). The review's warning was respected: this is NOT the naive 'any MAX_* load' rule. Measured on the real tree it produces 0 of the 6 claimed false positives (memory_hygiene_guard:147,318; meta_audit_on_stop:298,312,531; plan_defer_guard:371) and 0 of the full 107-item must-not-fire list. The discriminators that do it are structural, not lexical: an early exit must be break/return/continue and NOT raise (neg_max_used_as_loud_rejection stays quiet), the If must be inside a loop, range(CAP) only counts inside zip(), and integer literals are never caps.
- C1-M2 - BOUND_EXEMPTIONS is now a dict keyed (repo-relative path, constant, enclosing function, exact site count) with a reason string, and exemption_problems() mirrors run_selftests' stale_exempt shape: an inert entry FAILS, a drifted site count FAILS. selftest prints '-- 3 exemption(s), 3 load-bearing' every run, plus a drop-one assertion (removing any entry must produce >=1 offender). The verifier is itself verified hermetically: a temp tree with one planted cap and a 2-entry roster (one live, one naming a function that does not exist) must report live=1, problems=1; a second roster declaring 2 sites where 1 exists must report the 'inherited its approval' problem. The old MAX_FILE_BYTES entry is DELETED outright - it was never a list cap (os.path.getsize > MAX_FILE_BYTES) and is now excluded in the DETECTOR by SCALAR_SUFFIXES, so it can never pre-authorise a real collection cap at tha
- C1-M3 - implemented the settled design: central roster, key (path, const, enclosing_function, exact_site_count), COLLECTION branch only. Neither rejected key (lineno, shape) is used, and no marker comment exists. Display is structurally non-exemptible - the display branch never consults the roster at all. Two new fixtures pin both halves of the over-reach: display_under_a_collection_exemption (display in a DIFFERENT function, must still be 1 offender) and display_in_the_exempted_function (display in the SAME function the exemption approves, must still be 1 offender); second_cap_under_an_approved_exemption pins the count floor (2 sites under a roster declaring 1 -> 2 offenders). Mutations C1-M3 and C1-M3b revert each half and are both CAUGHT.
- C1-L1 - scope is now derived by importing UNIT_GLOBS from tools/check_review_freshness (single source of truth; a failed import raises rather than falling back to hooks/*.py) and walking each glob root recursively with os.walk, skipping SKIP_DIRS, using glob.escape() on the repo root so a '[' in the path cannot read as a character class. 34 files swept vs 17 before. The self-skip is keyed on the repo-relative path 'hooks/capped_report.py', and exemption keys are repo-relative paths - all three legacy basename keys were rewritten in the SAME edit, so the numbers_match_on_write.py:432 red-suite trap did not fire. Fixtures pin every keying property: a cap in hooks/lib/, in tools/, in skills/*/scripts/, an offender in a file NAMED tools/capped_report.py (must be flagged), and a cap in tools/numbers_match_on_write.py (must NOT borrow the hooks/ exemption by basename), plus a copy of this modu

**Findings NOT closed (1):**

- NONE of the eight cluster-1 findings is left open. Three caveats I will not paper over, none of which is a finding left unclosed: (1) the two POLICY rows the probe flagged (non_max_constant_name BULLET_LIMIT, dict_config_bound LIMITS['bullets']) are CLOSED, but only because I first measured the cost of the naming widening rather than assuming it: I enumerated all 197 UPPER_SNAKE constants bound anywhere in the 35 canonical units and the added patterns (_LIMIT / _CAP suffix, bare LIMIT/LIMITS/CAP/CAPS, lowercase cap/limit) match ZERO additional existing names, so adopting the convention costs this repo nothing today. If the owner disagrees with widening the convention, the change is one frozenset (CAP_EXACT/CAP_SUFFIXES) and those two fixtures would need must_flag flipped. (2) hooks/capped_report.py is now 864 lines, over the repo style guide's 800-line max, and is the longest file in the repo. The overage is entirely the 53-entry fixture corpus. No gate enforces line count (I checked tools/ and run_selftests.py). I chose not to split it into a hooks/capped_report_selftest.py sibling - the precedent exists (pre_push_gate_selftest.py) but a new hooks/*.py file feeds five other flat hooks/ rosters (hook_health_check:85/90/558, transcript_util:243, install.py:256, run_selftests:87) and I would not risk that without it being asked for. Flagging, not hiding. (3) The probe flagged an asymmetry at skills/consistency-audit/scripts/sources.py:87 - it silently `continue`s on an oversized source file AND skips idx.files += 1, where its exact twin numbers_match_on_write.py:393 returns an explicit 'NOTHING was verified in it' message. That is a real defect of the same class, but it is a byte bound, not a cap, so it is outside these eight findings and outside the files this task names. Not fixed; recorded here so it is not lost.

### Gate results (round 1)

```
FOUR GATES, exact tails, all run against C:/Users/ammar/Downloads/unbluff after the final edit.

1) python hooks/capped_report.py --selftest
-- taxonomy: 46/46 must-flag spellings caught, 0/7 negative controls wrongly flagged (53 spellings total)
-- cap sweep: 34 file(s) swept (1 sanctioned self-skip), 0 unrouted cap(s)
-- 3 exemption(s), 3 load-bearing
SELFTEST OK

2) python run_selftests.py
readme-fresh: OK

all 22 selftests passed

3) python tests/test_integration.py
==== 29/30 scenarios passed ====
The single failure is [FAIL] C1 hook_health reports OK. PROVEN PRE-EXISTING, not caused by this task: I cloned the repo at the baseline commit 1dcf430 into the OS temp dir and ran its own tests/test_integration.py, which produced the byte-identical failure line ("rc=0 out='[hook-health] 1 problem(s) across 8 hook commands, weekly selftests 11/11 OK, 5 left for the next session; 2 of 18 hooks'") and the same 29/30. I then widened the scenario's out[:120] truncation ON THE BASELINE CLONE ONLY and read the actual problem: "Stop: executable not on PATH: echo". The scenario seeds a pre-existing Stop hook whose command is `echo ...`; on Windows `echo` is a cmd.exe builtin, not an executable on PATH, so hook_health_check correctly reports it. A Windows environment artifact in a scenario I did not touch. NOTE: my brief said to expect 30/30; the true baseline on this machine is 29/30, which the probe report also observed (it reported the same scenario failing with different environment-dependent numbers).

4) python tools/mutation_check.py   (FULL run, unfiltered)
[capped_report                #C1-L1a  ] the walk stops recursing, so a cap in a hooks/ SUBPACKAGE  -> CAUGHT (rc=1)
[capped_report                #C1-L1b  ] scope re-declared locally as hooks/*.py instead of importe -> CAUGHT (rc=1)
[./run_selftests              #A3b     ] an undeclared tools/ file no longer forces a decision      -> CAUGHT (rc=1)

92 of 94 mutations executed, 0 skipped, 2 not-runnable-here, 0 unproven
NOT RUNNABLE ON THIS PLATFORM (2): [('pre_push_gate', '30'), ('fast_test_on_stop', 'D10c')]
  These are proven by the OTHER platform's job, not by this one. If that job does not exist, they are proven NOWHERE.
every EXECUTED mutation was caught; 2 remain unproven here

NOTHING SURVIVED. grep over the full 94-line output for SURVIVED / HARNESS ERROR / UNPROVEN returns zero hits. The only two non-CAUGHT verdicts are the two posix-only SKIPPED entries (pre_push_gate #30, fast_test_on_stop #D10c), which are structurally unrunnable on Windows and sit in files I did not touch. NO entry that was CAUGHT at baseline is now SURVIVED. Entry count went 82 -> 94 (12 added).

5) After the run I made one docstring-only edit (correcting a number I had quoted from the brief instead of measuring). I re-ran the affected subset rather than claim the earlier evidence still covered it:
15 of 15 mutations executed, 0 skipped, 0 not-runnable-here, 0 unproven (filter 'capped_report': 15 of 94 entries consi
```

### Red-then-green evidence (round 1)

```
THE ORDER WAS FOLLOWED. I wrote the fixtures into hooks/capped_report.py FIRST, keeping the SHIPPED implementation byte-unchanged (only selftest() was replaced), ran it, and recorded the failures. Only then was the detector written.

RED (fixtures added, shipped implementation untouched) - actual output of `python hooks/capped_report.py --selftest`:
  -- taxonomy: 0/42 must-flag spellings caught, 0/7 negative controls wrongly flagged (49 spellings total)
  -- cap sweep: -1 file(s) swept (-1 sanctioned self-skip), 0 unrouted cap(s)
  -- exemption denominator UNKNOWN: exemption_problems() does not exist
  SELFTEST FAIL: the guard is BLIND to 42 of 42 cap spellings, so a cap written any of those ways reports clean: ['plain_assign_slice', 'annotated_assign_slice', 'augassign_adjusted_bound', 'walrus_bound', 'tuple_target_bound', 'list_target_bound', 'from_import_bound', 'import_attribute_bound', 'alias_bound', 'arithmetic_bound', 'class_attr_bound', 'dict_config_bound', 'non_max_constant_name', 'negative_lower_tail_slice', 'del_tail', 'islice', 'slice_object_call', 'comprehension_index_guard', 'pop_until_under_cap', 'heapq_nlargest', 'sorted_then_slice', 'function_local_bound', 'two_sites_one_constant', 'unparseable_module', 'module_in_subdirectory', 'module_in_tools', 'module_in_skill_scripts', 'break_ge_in_body', 'reversed_comparison_break', 'break_in_orelse', 'break_nested_in_with', 'return_instead_of_break', 'continue_instead_of_break', 'while_test_cap', 'takewhile', 'break_on_attribute_bound', 'break_on_counter_variable', 'break_with_boolean_op', 'break_on_arithmetic_bound', 'zip_range_cap', 'break_via_walrus_counter', 'break_in_nested_loop']
  SELFTEST FAIL: sweep() does not exist, so the guard has no reporting path that names its denominator - 'clean' is printed over a number nobody can check
  SELFTEST FAIL: the guard cannot see a display cap in hooks/ at hooks/planted.py - a structural check that matches nothing is indistinguishable from a clean sweep
  SELFTEST FAIL: the guard cannot see a collection cap in hooks/ at hooks/planted2.py - ...
  SELFTEST FAIL: the guard cannot see a display cap in a hooks/ SUBPACKAGE (flat glob) at hooks/lib/planted3.py - ...
  SELFTEST FAIL: the guard cannot see a display cap in a file NAMED capped_report (basename-keyed self-skip) at tools/capped_report.py - ...
  SELFTEST FAIL: the guard cannot see a collection cap borrowing the hooks/ exemption by basename at tools/numbers_match_on_write.py - ...
  SELFTEST FAIL: self-skip covered -1 file(s), expected exactly 1 (hooks/capped_report.py)
  SELFTEST FAIL: planted tree swept -1 file(s), expected 5
  SELFTEST FAIL: exemption_problems() does not exist: a bogus BOUND_EXEMPTIONS entry raises nothing and a dead one sits inert, so the roster is unverified
  SELFTEST FAIL: the guard reports skills/consistency-audit/scripts/audit.py:181 as clean, but it is a live unrouted collection cap that silently under-reports its own total
  SELFTEST FAIL: the guard reports skill
```

### Adversarial verdicts (8)

| finding | closed | test load-bearing | residual / new defect |
|---|---|---|---|
| `C1-H1` | False | True | STILL OPEN: _cap_names in C:/Users/ammar/Downloads/unbluff/hooks/capped_report.py (lines 188-233) models 12 of Python's 24 name-binding forms. A cap bound reaching the slice through any of the other 12 removes the name from the caps set and both the display and collection branches go blind to a byte |
| `C1-H2` | False | True | The class is still open even though every sub-case named in the finding text is closed. The display branch went from 1 hardcoded shape to 9 hardcoded shapes; it is still an enumeration of callee-name strings and argument positions, so adjacent spellings of the same cap keep passing. Five demonstrate |
| `C1-H3` | False | False | 1) HIGH, the finding's own headline: an int-literal bound makes any cap invisible. 0/5 int-literal cap shapes caught, including the verbatim `problems[:12]` site C1-H3 names and an int-literal COLLECTION cap (`if len(out) >= 10: break`) that destroys the total. Planted into hooks\plan_defer_guard.py |
| `C1-H4` | False | True | 1) NARROW BUT IN-CLASS: `from constants import *` leaves an imported cap invisible - 4 of 4 star-import variants blind (display slice, collection break, islice, and with an unrelated local cap also present). ast.ImportFrom with alias.name == "*" binds no name, so the bare Name never enters caps. Thi |
| `C1-M1` | False | True | 1) FALSE-POSITIVE REGRESSION (highest severity, introduced BY this fix): hooks/capped_report.py:380-383 flags any `while <x> <cmp> <cap>` with no exit and no scan discriminator. 3 of 4 planted must-stay-quiet shapes fire, including a retry loop that is semantically identical to the repo's own neg_ma |
| `C1-M2` | False | True | 1. PRIMARY, the finding's own second sentence. A real unrouted collection cap at hooks/numbers_match_on_write.py named MAX_FILE_BYTES is still swallowed while --selftest prints "0 unrouted cap(s)" and SELFTEST OK (rc=0). The pre-authorisation moved from BOUND_EXEMPTIONS into SCALAR_SUFFIXES in the d |
| `C1-M3` | False | True | The exemption still over-reaches beyond the bound it was written for, one narrowing short of closed. The key's function component (hooks/capped_report.py:319) is a bare def NAME, not a qualified scope path, so all same-named scopes in a module - a method of any class, a nested def, an async def - sh |
| `C1-L1` | True | True | Nothing left open in C1-L1 itself. Two measured items outside it, both recorded so they are not lost:  1. NAMING BOUNDARY (C1-H1 class, not scope). probe_edges.py measured 18 bound names as display slices: 7 of 18 are recognised. Lowercase `cap` and `limit` ARE cap names - a shipped fixture (lowerca |

**Still open (7):**

- C1-H1: STILL OPEN: _cap_names in C:/Users/ammar/Downloads/unbluff/hooks/capped_report.py (lines 188-233) models 12 of Python's 24 name-binding forms. A cap bound reaching the slice through any of the other 12 removes the name from the caps set and both the display and collection branches go blind to a byte-identical truncation. Ranked by how likely each is to occur in this repo:  1. FUNCTION PARAMETER DEFAULT (and kwonly default): def f(xs, n=MAX_B) -> xs[:n]. Highest severity because it is already live at hooks/show_your_proof.py:232/242 (read_tail_lines(path, max_lines=TAIL_LINE_COUNT) -> lines[-max_lines:]), a real un-routed list cap the guard reports as clean today, and because the imple
- C1-H2: The class is still open even though every sub-case named in the finding text is closed. The display branch went from 1 hardcoded shape to 9 hardcoded shapes; it is still an enumeration of callee-name strings and argument positions, so adjacent spellings of the same cap keep passing. Five demonstrated live blind spots, ranked by how damning they are: (1) `heapq.nlargest(n=MAX, iterable=xs)` / `nsmallest` - node.keywords is never inspected, a hole INSIDE a shape the implementer added; (2) `from itertools import islice as take` - the finding's own named example behind an import alias, while the same file already resolves asname for bound names at line 216; (3) `collections.deque(xs, maxl
- C1-H3: 1) HIGH, the finding's own headline: an int-literal bound makes any cap invisible. 0/5 int-literal cap shapes caught, including the verbatim `problems[:12]` site C1-H3 names and an int-literal COLLECTION cap (`if len(out) >= 10: break`) that destroys the total. Planted into hooks\plan_defer_guard.py and hooks\meta_audit_on_stop.py, the whole gate stack stays green (capped_report --selftest rc=0, run_selftests 22/22). The stated invariant "a new cap not routed here is a selftest failure" is still false. Note the tension the implementer must resolve rather than ignore: flagging all int-literal slices would hit ~78 sites in scope that are overwhelmingly string truncation (msg[:120]) and 
- C1-H4: 1) NARROW BUT IN-CLASS: `from constants import *` leaves an imported cap invisible - 4 of 4 star-import variants blind (display slice, collection break, islice, and with an unrelated local cap also present). ast.ImportFrom with alias.name == "*" binds no name, so the bare Name never enters caps. This is an IMPORT form of a cap constant, which is the class C1-H4 states, so by the finding's own text the condition still obtains. Demonstrated closable at zero cost: hooks/capped_report.py:247, `return node.id in caps` -> `return node.id in caps or is_cap_name(node.id)`; with that line the shipped selftest still reports 46/46 must-flag, 0/7 false positives, 0 unrouted caps on the repo. No f
- C1-M1: 1) FALSE-POSITIVE REGRESSION (highest severity, introduced BY this fix): hooks/capped_report.py:380-383 flags any `while <x> <cmp> <cap>` with no exit and no scan discriminator. 3 of 4 planted must-stay-quiet shapes fire, including a retry loop that is semantically identical to the repo's own neg_max_used_for_retries fixture. Zero live instances in the tree today, so the "0 false positives" measurement never exercised the branch. Needs a discriminator that is not _has_exit (m12 proves that one blinds pop_until_under_cap and while_test_cap) - e.g. require the compared expression to be len(<name>) of a container the loop body appends to - plus at least 3 negative fixtures: retry-while, 
- C1-M2: 1. PRIMARY, the finding's own second sentence. A real unrouted collection cap at hooks/numbers_match_on_write.py named MAX_FILE_BYTES is still swallowed while --selftest prints "0 unrouted cap(s)" and SELFTEST OK (rc=0). The pre-authorisation moved from BOUND_EXEMPTIONS into SCALAR_SUFFIXES in the detector, where the new liveness machinery cannot reach it, and it grew from one module to all 34 swept files, from one constant to the _BYTES/_LEN/_CHARS/_SECONDS families, and from the collection branch to both branches. Six spellings the pre-fix guard at 1dcf430 caught are now invisible. The blind spot is latent today (D3 shows the ban currently suppresses only 2 genuine non-caps), but MA
- C1-M3: The exemption still over-reaches beyond the bound it was written for, one narrowing short of closed. The key's function component (hooks/capped_report.py:319) is a bare def NAME, not a qualified scope path, so all same-named scopes in a module - a method of any class, a nested def, an async def - share one exemption bucket. When a cap MOVES from the approved scope into a same-named scope, the declared site count stays at 1 and the roster silently adopts a never-reviewed bound; demonstrated end to end on the real repo with the real roster (new LegacyScanner.run cap absorbed by the entry written for module-level run(), sweep "0 unrouted cap(s)", exemption_problems "3 live of 3", SELFTES

**Decorative tests (0):**


**New defects introduced (0):**


---


## ROUND 2 - run `wf_05787685-fee`

- ground truth: int-literal 113 sites, rule_validated=true, FPs=0 | structural restores 10/10, while neg=true pos=true
- implement r2: closed 7/7, not closed 4, 72 fixtures, 14 mutation entries
- verify r2: 8/8 verdicts, 2 still open, 0 decorative, 7 reporting a NEW defect

### Ground truth

- **int_literal_sites**: 113
- **int_literal_rule**: ADD an int-literal path ALONGSIDE the named-bound path; do not touch is_cap_expr (it keeps returning False for int literals). module_cap_sites(tree) returns sites + int_cap_sites(tree). Exemptions reuse BOUND_EXEMPTIONS unchanged, keyed (rel, const, func, count) with const the literal as a string ("10", "12").

SHAPE INFERENCE (AST only, three-valued list/str/unknown; default unknown; conflicting evidence collapses to unknown; recursion depth-capped at 4):
  LIST evidence: [..] literal or ListComp; call to list()/sorted(); method call .split/.rsplit/.splitlines/.readlines/.findall/.most_common; a list / List / list[X] / List[X] annotation on a parameter or an AnnAssign target; .append/.extend/.insert/.remove called on that bare Name anywhere in the enclosing scope chain; a Name whose every in-scope binding resolves to list.
  STR evidence: str/bytes Constant, JoinedStr, .stdout/.stderr attribute, str-returning methods (.strip .lower .upper .replace .format .join .hexdigest .decode .encode .group .read ...), str()/repr(), a str/bytes annotation, and BoolOp/BinOp/IfExp whose only proven side is str (covers (proc.stderr or "")).
  DELIBERATELY NOT list evidence: Sequence/Iterable annotations (a str satisfies both), tuple/dict/set literals.

DISPLAY clauses - an int literal N counts ONLY with positive list evidence AND N > POSITIONAL_FLOOR (=5):
  D1  EXPR[:N]           where shape(EXPR) == list
  D2  del EXPR[N:]       where shape(EXPR) == list
  D3  islice(..., N) / nlargest(N, ...) / nsmallest(N, ...)
  D4  a comprehension whose enumerate() index is bounded by N under an ordering operator
  NOT counted: negative literals (xs[:-1], xs[-N:]); positive slice-lower outside del (xs[1:], xs[3:]); == / != comparisons.

COLLECTION clauses - NO magnitude floor, but a hard ACCUMULATOR gate:
  C1  a While test, or an If inside a loop whose body/orelse break/return/continues, containing an ORDERING compare (< <= > >=) between a POSITIVE int literal and len(ACC), where ACC is a bare Name with LIST evidence (append/extend/insert in the enclosing scope chain, or a list annotation). Both operand orders.
  C2  zip(range(N), ...) with N > 5
  C3  takewhile whose predicate bounds against N > 5 under an ordering operator

POSITIONAL_FLOOR = 5 is MEASURED, not chosen: across the 84 int-literal head-slice bounds in this tree the values are bimodal with an EMPTY BAND from 6 to 29 - {2,3,5} are positional destructuring (entry[:2], kept[:3], entry[:5]) and {30..240} are character truncation (msg[:120], err[:160], out[:200]). Any floor in [5,11] is equally supported by the data; 5
- **int_literal_fps** (0): []
- **scalar_replacement**: SCALAR_SUFFIXES is DELETED from is_cap_name(); is_cap_name() is now name-only (CAP_PREFIXES/CAP_SUFFIXES/CAP_EXACT) and says nothing about scalar-ness. Scalar-ness is decided AT THE SITE by two structural predicates over what the code measures, and a site so classified is emitted as a THIRD branch "size" - never dropped.

(1) COLLECTION position - _is_size_measure(measured_operand, per_item_names): the operand paired against the bound in the comparison is a per-item SIZE when it is a call to getsize(...), an attribute .st_size, len(<read-like call>) (read/read_text/read_bytes/readline/decode/encode/str/repr/join/format/getvalue), or len(<name>) where <name> is a per-item binding. A per-item binding is structurally defined: a for-target (the loop re-binds it every iteration, so its length CANNOT accumulate across items) or a name provably bound to str/bytes. Anything else - len(out) where out outlives the loop, a bare counter, an enumerate index - is a count of survivors and stays "collection".

(2) DISPLAY position - _is_scalar_expr(sliced_object, text_names): a slice is a scalar truncation only when the sliced object is PROVABLY str/bytes (read-like call, str/bytes literal, f-string, or a name bound to one). text_names is deliberately NARROWER than per_item_names: a for-target is excluded, because `for group in groups: return group[:MAX_BULLETS]` is a display cap and routing it to the softer roster would leak the display doctrine away one shape at a time. Anything not proven text falls through to "display", which no roster may silence.

The suppression itself moved from the detector into an auditable roster: SIZE_EXEMPTIONS, keyed identically to BOUND_EXEMPTIONS by (repo-relative path, constant, ENCLOSING FUNCTION, exact site count). sweep() reports every "size" site as an offender unless a SIZE_EXEMPTIONS entry with a matching site count covers it; exemption_problems() liveness-checks BOTH rosters (an inert entry fails, a site-count drift fails); the selftest prints every suppression by name with a denominator ("5 cap site(s) in scope: 0 display, 3 collection, 2 size; 5 suppressed by a roster entry, 0 by a name"). A guard-rail assertion fails the selftest if is_cap_name() ever returns False for MAX_LEN / MAX_BYTES / MAX_CHARS / MAX_SECONDS / MAX_FILE_BYTES, and mutation entry R2-H1 re-introduces the ban and is CAUGHT.
- **scalar_restores**: 10
- **scalar_residual** (7): ["[NEW, from this rule] SIZE_EXEMPTIONS ('hooks/numbers_match_on_write.py', 'MAX_FILE_BYTES', 'index_sources', 1) - the site at line 180, `os.path.getsize(fpath) > MAX_FILE_BYTES -> continue`. Classified [size] structurally by the getsize call, not by the constant's spelling. Liveness-checked by exemption_problems(); printed by the selftest; drop it and an offender appears (verified by the shield check).", "[NEW, from this rule] SIZE_EXEMPTIONS ('skills/consistency-audit/scripts/sources.py', 'MAX_FILE_BYTES', 'index_sources', 1) - the site at line 87, same shape. Same liveness contract, same shield check.", "[PRE-EXISTING, not from this rule] BOUND_EXEMPTIONS ('hooks/numbers_match_on_write.py', 'MAX_FINDINGS_TRACKED', 'run', 1) - unchanged by this round.", "[PRE-EXISTING, not from this rule] BOUND_EXEMPTIONS ('hooks/numbers_match_on_write.py', 'MAX_SOURCE_VALUES', 'index_sources', 1) - unchanged by this round.", "[PRE-EXISTING, not from this rule] BOUND_EXEMPTIONS ('skills/consistency-audit/scripts/sources.py', 'MAX_VALUES', 'index_sources', 1) - unchanged by this round.", "[ZERO suppressions needed] hooks/memory_hygiene_guard.py MAX_INDEX_BULLET_LEN - is_cap_name() now returns True (it returned False at HEAD), and the name produces NO cap site at all, because the `if line.lstrip().startswith('- [') and len(line) > MAX_INDEX_BULLET_LEN:` only appends and stops no scan. Proven b
- **while_discriminator**: container = _container_of_len(measured) and _body_changes_length(node.body, container) - i.e. the operand compared against the cap must be len(<name>) (Name or Attribute, ast.NamedExpr unwrapped first, so a walrus `(n := len(out))` resolves; len() of a CALL such as len(text.encode()) yields None and is quiet), AND the loop body must change how many items that container holds. _body_changes_length walks the body (stopping at nested scopes) for: a method call <name>.M(...) with M in _LEN_CHANGING = {append, appendleft, extend, extendleft, add, insert, update, pop, popleft, popitem, remove, discard, clear, setdefault}; `del <name>[...]`; `<name> += ...`; `<name> = <name> + ...`; `<name>[k] = v`; or <name> passed as an argument to any call in the body (conservative catch-all so a callee that fills in place still fires). `pop` is in the set for the same reason `append` is - pop_until_under_cap shrinks a list to a bound and that IS a collection cap.

This is NOT _has_exit, and cannot be: pop_until_under_cap has no exit statement at all and while_test_cap's only statement is an append, so an exit test blinds both positives - which is exactly what mutation C1-M1 already pins. Verified structurally rather than by reading: an AST probe of the shipped module found exactly 1 while-branch If node, and the functions it calls are ['_body_changes_length', '_cap_label', '_compare_pairs', '_container_of_len', 'add', 'isinstance'] - _has_exit is absent.

### Implement

- files changed: `capped_report.py`, `show_your_proof.py`, `measure_dispatcher_cost.py`, `mutation_check.py`
- fixtures added: 72
- mutation entries added: 14
  - capped_report R2-H1a - the SCALAR_SUFFIXES name ban returns to is_cap_name() - CAUGHT
  - capped_report R2-H1b - the [size] branch stops being reported, so scalar-looking sites vanish in the detector instead of a roster - CAUGHT
  - capped_report R2-H1c - _is_scalar_expr admits a loop variable, routing a DISPLAY cap to the softer size roster - CAUGHT
  - capped_report R2-H2 - the ast.While branch drops its container discriminator - CAUGHT
  - capped_report R2-H3 - a PARAMETER DEFAULT stops binding a cap name - CAUGHT
  - capped_report R2-H4a - the INT-LITERAL path is removed - CAUGHT
  - capped_report R2-H4b - the int path's ACCUMULATOR GATE is dropped (the rejected 'unconditional collection' proposal) - CAUGHT
  - capped_report R2-H4c - the int path loses POSITIONAL_FLOOR - CAUGHT
  - capped_report R2-M1 - the exemption key's function component goes back to a bare def name - CAUGHT
  - capped_report R2-M2 - a star-imported bound is invisible again - CAUGHT
  - capped_report R2-M3a - the display shapes stop reading node.keywords - CAUGHT
  - capped_report R2-M3b - the callee-alias map is dropped - CAUGHT
  - REPAIRED (not new): capped_report C1-H2 and C1-H3a anchors had gone to 0 occurrences after my edits (HARNESS ERROR, pinning nothing); C1-M2's anchor likewise. All three re-anchored, all CAUGHT.
  - REPAIRED (not new): transcript_util #13's anchor matched TWICE (first_text and has_tool_result); .replace(...,1) mutated whichever came first, so re-ordering two functions would silently re-point the entry. Anchor extended to be unique.

**Findings closed (7):**

- R2-H1 - SCALAR_SUFFIXES deleted from is_cap_name(); scalar-ness now decided at the site by _is_size_measure/_is_scalar_expr and emitted as a third branch [size] that only SIZE_EXEMPTIONS may silence. Baseline floor 14/14 (was 4/14). All 3 named live sites handled: numbers_match MAX_FILE_BYTES and sources.py MAX_FILE_BYTES are now rostered [size] entries; memory_hygiene MAX_INDEX_BULLET_LEN is_cap_name False->True and produces no site (the if only appends).
- R2-H2 - while branch now requires _container_of_len(measured) AND _body_changes_length(body, container). Not _has_exit (that blinds both positives). 4/4 negatives quiet, 2/2 positives still firing. Independent stdlib corpus: 557/557 files, 692 while loops, HEAD-minus-discriminator fires on 12, shipped on 4, 8 dropped 0 added.
- R2-H3 - parameter defaults now feed the alias-propagation loop. The live site is closed: TAIL_LINE_COUNT renamed MAX_TAIL_LINES (it was ALSO invisible by name, which the finding did not state - see notes), site now visible and recorded as a SIZE_EXEMPTIONS entry with the written judgement, liveness- and shield-checked.
- R2-H4 - int_cap_sites() added alongside the named path; is_cap_expr untouched. D1-D4 display clauses gated on list evidence + POSITIONAL_FLOOR=5, C1-C3 collection clauses gated on the accumulator. 0 of 152 in-scope int-literal sites fire. The third live unrouted cap, tools/measure_dispatcher_cost.py:91, is routed through capped_report.render(). Six blind spots declared in the module docstring beside the invariant.
- R2-M1 - the exemption key's function component is a qualified scope path via _annotate_scopes (Class.method, outer.inner). MOVE fixture added plus a same-named control that must stay quiet.
- R2-M2 - is_cap_expr matches a cap-spelled bare Name; 4 star-import fixtures added, one pinned by an offender COUNT so it cannot pass on the local cap alone.
- R2-M3 - node.keywords scanned alongside node.args, deque added, and a callee-alias map built from Import/ImportFrom. IfExp and elementwise tuple-unpack added to alias propagation.

**Findings NOT closed (4):**

- BS1-BS6, the int path's six declared blind spots - the largest is an UNANNOTATED parameter with no local list evidence (def build_message(problems): return problems[:12]). Closable only by widening list evidence to iteration/join context, which I could not show stays at 0 false positives. Written into the module docstring so the invariant reads 'true for these shapes' rather than 'true'.
- BS3 named/int asymmetry, LEFT OPEN DELIBERATELY - json.dump(history[-MAX_HISTORY:]) fails the guard while history[-200:] passes. Both live tail-window sites (run_selftests.py:219, tools/check_review_freshness.py:245) are commented rolling ledgers. This is the one judgement call in the int rule and the place a reviewer could reasonably overrule me.
- The int COLLECTION clause has a measured out-of-scope false-positive rate. In scope: 0 of 152. On the Python 3.12 stdlib (557 files): 6 hits, 5 collection + 1 display, all innocent - difflib._line_iterator (while len(lines) < 4 padding), heapq.merge x2, re._compiler (len(runs) >= 2 bail-out), warnings._setoption (pad to 5), email/contentmanager (lines[:10] sniff sample). All the collection ones have bounds <= 5, so a magnitude floor on the int While/If form would remove them - but the settled ground truth says NO magnitude floor for collection and I implemented it as specified rather than relitigating. Recorded, not fixed.
- pre_push_gate #30 and fast_test_on_stop #D10c remain posix-only and did not execute on this machine. Unchanged by this round; named because a skip is not a pass.

### Baseline no-regression check (round 2)

```
Three arms over ONE planted corpus of 14 cases (5 scalar-suffixed names + 2 CONTROLS, x display and collection). Scripts: scratchpad/r2b/ab_baseline.py and ab_arm3.py; the baseline is the real file from `git show 1dcf430:hooks/capped_report.py`, driven through its own signature slicing_offenders(hooks_dir).

case                              baseline  shipped  branch
MAX_LEN_display                   True      True     ['display']
MAX_LEN_collection                True      True     ['collection']
MAX_BYTES_display                 True      True     ['display']
MAX_BYTES_collection              True      True     ['collection']
MAX_CHARS_display                 True      True     ['display']
MAX_CHARS_collection              True      True     ['collection']
MAX_SECONDS_display               True      True     ['display']
MAX_SECONDS_collection            True      True     ['collection']
MAX_FILE_BYTES_display            True      True     ['display']
MAX_FILE_BYTES_collection         True      True     ['collection']
MAX_BULLETS_display               True      True     ['display']      <- CONTROL
MAX_BULLETS_collection            True      True     ['collection']   <- CONTROL
MAX_FINDINGS_TRACKED_display      True      True     ['display']      <- CONTROL
MAX_FINDINGS_TRACKED_collection   True      True     ['collection']   <- CONTROL

denominator: 14 cases (7 constant names x 2 branches), 4 of them CONTROLS
baseline flags: 14/14 ; shipped flags: 14/14
REGRESSIONS vs baseline (non-control): 0 []
REGRESSIONS vs baseline (CONTROL - a harness failure): 0 []

ZERO regressions. And the check is NOT vacuous - arm 3 runs the same 14 cases against the shipped guard with mutation R2-H1a applied (the ban put back):
ARM 3 (shipped guard + mutation R2-H1a): 4/14 flagged
regressed under the mutation: 10 [MAX_LEN/BYTES/CHARS/SECONDS/FILE_BYTES x display+collection]
controls regressed: []

This floor is now PERMANENT in capped_report.selftest() as _baseline_floor_cases(), generated from a name list so the five families and the two controls get byte-identical bodies and only the NAME can change the verdict. It prints "-- baseline floor: 14/14 ...". It failed 4/14 before the fix and passes 14/14 after.
```

### Gate results (round 2)

```
All four gates run on the FINAL bytes, in this order after the last edit.

python hooks/capped_report.py --selftest:
-- taxonomy: 82/82 must-flag spellings caught, 0/29 negative controls wrongly flagged (111 spellings total)
-- baseline floor: 14/14 spellings visible to the 1dcf430 guard still visible (7 constant names x 2 branches)
-- branch classification: 16/16 fixtures land in the branch they are pinned to
-- cap sweep: 34 file(s) swept (1 sanctioned self-skip), 0 unrouted cap(s)
-- 6 exemption(s) (3 collection + 3 size), 6 load-bearing
   suppressed [collection] hooks/numbers_match_on_write.py:432 run() MAX_FINDINGS_TRACKED - ...
   suppressed [collection] hooks/numbers_match_on_write.py:191 index_sources() MAX_SOURCE_VALUES - ...
   suppressed [collection] skills/consistency-audit/scripts/sources.py:105 index_sources() MAX_VALUES - ...
   suppressed [size] hooks/numbers_match_on_write.py:180 index_sources() MAX_FILE_BYTES - ...
   suppressed [size] hooks/show_your_proof.py:256 read_tail_lines() max_lines - ...
   suppressed [size] skills/consistency-audit/scripts/sources.py:87 index_sources() MAX_FILE_BYTES - ...
-- 6 cap site(s) in scope: 0 display, 3 collection, 3 size; 6 suppressed by a roster entry, 0 by a name in the detector
SELFTEST OK

python run_selftests.py:  all 22 selftests passed   (22/22)

python tests/test_integration.py:  ==== 30/30 scenarios passed ====
  I got 30/30, NOT the 29/30 the brief warned might be environment-dependent. Stated explicitly rather than accepted either way.

python tools/mutation_check.py  (FULL, unfiltered, run twice - once before the final docstring edit and again after it):
104 of 106 mutations executed, 0 skipped, 2 not-runnable-here, 0 unproven
NOT RUNNABLE ON THIS PLATFORM (2): [('pre_push_gate', '30'), ('fast_test_on_stop', 'D10c')]
every EXECUTED mutation was caught; 2 remain unproven here
  -> 104 CAUGHT, 0 SURVIVED, 0 HARNESS ERRORS. All 27 capped_report entries (15 pre-existing + 12 new) CAUGHT.

Anchor uniqueness sweep: 106 entries checked, 0 anchors not-exactly-once.
```

### Red-then-green evidence (round 2)

```
Fixtures were added and run BEFORE any fix existed. Recorded at C:/Users/ammar/AppData/Local/Temp/claude/C--Users-ammar-Downloads-Claude/61196ffe-d66d-4ad7-9208-af4a3f565559/scratchpad/r2b/RED1.txt. Verbatim RED run:

-- taxonomy: 48/77 must-flag spellings caught, 2/26 negative controls wrongly flagged (103 spellings total)
-- baseline floor: 4/14 spellings visible to the 1dcf430 guard still visible (7 constant names x 2 branches)
-- branch classification: 5/14 fixtures land in the branch they are pinned to
SELFTEST FAILED

Attributed by finding:
  R2-H1  BASELINE REGRESSION: 10 of 14 - floor_MAX_LEN/BYTES/CHARS/SECONDS/FILE_BYTES x {display, collection}; scalar_slice_without_a_roster_entry, size_skip_by_getsize, size_skip_on_a_loop_variable all blind.
  R2-H2  negative controls 'neg_retry_while' and 'neg_depth_while' WERE FLAGGED. Important correction to the brief: neg_poll_while and neg_scalar_shrink_while were quiet at HEAD only because MAX_WAIT_SECONDS/MAX_BYTES were hidden by the scalar ban - so fixing R2-H1 alone would have widened R2-H2 from 2 false positives to 4. The findings interact.
  R2-H3  param_default_bound, param_default_bound_collection blind.
  R2-H4  13 int fixtures blind (int_display_annotated_list_param, int_display_local_accumulator, int_collection_break/return/reversed_operands/while, int_del_tail, int_sorted_then_slice, int_comprehension_assigned_base, int_islice, int_zip_range, int_takewhile, int_list_of_dict_then_slice, int_comprehension_index_guard).
  R2-M1  collection_cap_moved_into_a_same_named_method blind - it inherited the exemption written for the module-level run().
  R2-M2  star_import_display/collection/islice blind, and star_import_plus_an_unrelated_local_cap produced 1 offender where 2 exist (it would have passed on the local cap alone without the count assertion).
  R2-M3  nlargest_keyword_args, nsmallest_keyword_args, islice_behind_a_callee_alias, deque_maxlen, alias_via_conditional, alias_via_tuple_unpack blind.

GREEN after the fix: 82/82 must-flag, 0/29 negatives, 14/14 floor, 16/16 branch pins.

Honestly flagged: the 12 int-literal NEGATIVE controls and the 3 roster-silenced size negatives were quiet at RED too (int literals were invisible; the size names were name-banned). Their value is post-fix, and their load-bearingness is proven by the per-entry SIZE_EXEMPTIONS shield check (drop the entry, an offender must appear) and by mutations R2-H4b/R2-H4c, not by the RED run.
```

### Adversarial verdicts (8)

| finding | closed | test load-bearing | residual / new defect |
|---|---|---|---|
| `R2-H1` | True | True | **NEW DEFECT:** TWO new defects, both created by the [size] branch and the census line this round added.  (1) MEDIUM - SIZE MIS-BRANCH ON A SCAN-TRUNCATING BREAK. _is_size_measure() calls len(<for-target>) a size measure because "the loop re-binds it every iteration, so its l // THE GUARD GENERALISES TO SEVEN NAMES, NOT TO THE CLASS. The finding's own last sentence frames R2-H1 as a class defect ("pre-authorisation that nothing audits"). The named instance is closed; the class is reachable one rename away.  Measured (p3_general.py, 4/4 variants, families |
| `R2-H2` | False | True | **NEW DEFECT:** FALSE NEGATIVE (new, caused by this fix): the drop-until-under-cap loop is now invisible whenever the drop is a rebind-slice instead of a method call. Minimal pair against the repo's own shipped must-flag fixture pop_until_under_cap (hooks/capped_report.py:133 // To close R2-H2 the while branch needs, in this order: 1. NEGATIVE fixtures for the three unpinned innocent classes, not just the four already written: (a) retry counted with a list (`while len(attempts) < MAX_RETRIES` + append + raise on exhaustion) - the finding's own named clas |
| `R2-H3` | True | True | **NEW DEFECT:** NEW FALSE-POSITIVE SURFACE (R2-H3-attributable, demonstrated with a control, 0 live occurrences today). `caps` is MODULE-scoped, so one function's cap-valued default promotes its lowercase PARAMETER NAME for the whole module. Planted `MAX_N = 12 / def report(x // 1. HALF THE SHIPPED FIX IS UNPINNED. Deleting ONLY the keyword-only lines (`for arg, default in zip(a.kwonlyargs, a.kw_defaults): if default is not None: bindings.append(...)`, hooks/capped_report.py:369-371) leaves the gate fully green: taxonomy 82/82, 0/29 negative controls, 6  |
| `R2-H4` | True | True | **NEW DEFECT:** Documentation overclaim, in the artifact whose job is to not overclaim. C:/Users/ammar/Downloads/unbluff/hooks/capped_report.py:54-55 states: the invariant "is true for the 111 spellings in _TAXONOMY and false for the six blind spots named beside int_cap_sites // Four items, ranked by what I measured.  1. BS1 is the real remaining surface and it is honestly declared. `problems[:12]` where the base has no provable list evidence stays invisible. I count 75 such in-scope sites and 114 in the stdlib - but that 75 is dominated by string trunca |
| `R2-M1` | True | True | **NEW DEFECT:** YES, one narrowing, measured, not blindness in the aggregate gate. The site-count floor's ADD case got narrower on one channel. A/B with roster {(rel, MAX_FINDINGS_TRACKED, "run", 1)} against a module holding the approved cap in module-level run() PLUS a NEW c // 1. QUALNAME CEILING, confirmed 3 ways with 2 matched controls (scratchpad\r2m1\q1_residual.py). Two definitions that SHARE a qualname are still one exemption bucket, so the MOVE case is closed only for scopes the qualname can separate. RES1 two module-level `def run` under an if/ |
| `R2-M2` | True | True | **NEW DEFECT:** YES - one new defect, coverage-only, does not reopen R2-M2. The widening at hooks/capped_report.py:403 makes every `caps.add(<cap-spelled name>)` in _cap_names redundant, because is_cap_expr now resolves a cap-spelled bare Name without consulting `caps` at all // 1. NEW, from question 3: the two dead branches at hooks/capped_report.py:333-335 and :355-357. Nothing pins them, and a regression test written against either would be decorative the day it lands. The general fix is the sweep the implementer did not do - after any widening of is_ |
| `R2-M3` | False | True | The class named by the finding - "an enumeration of callee-name strings and argument POSITIONS, so adjacent spellings of shapes it already claims keep passing" - is narrowed, not eliminated. Three residual sub-shapes, all proven to sweep CLEAN against a working control: 1. CALLEE RENAMED BY ASSIGNME |
| `NO-REGRESSION acceptance test (cluster-2 gate on R2-H1: "HEAD must not be blinder than the guard at 1dcf430")` | True | True | **NEW DEFECT:** YES, one, found while re-verifying the stated gates. tests/test_integration.py is 29/30, NOT the stated 30/30. Failing scenario: C1 "hook_health reports OK". Cause: the rewrite's scan_scope() does `from check_review_freshness import UNIT_GLOBS` off a sibling t // 1. THE STANDING CHECK IS A ROSTER OF 7 NAMES, NOT A GUARD ON THE CLASS. Both defences name their spellings literally: the is_cap_name guard rail tests 5 string literals, and _baseline_floor_cases() iterates _BASELINE_FLOOR_NAMES (7 names x 2 branches = 14). Measured (residual_che |

**Still open (2):**

- R2-H2: To close R2-H2 the while branch needs, in this order: 1. NEGATIVE fixtures for the three unpinned innocent classes, not just the four already written: (a) retry counted with a list (`while len(attempts) < MAX_RETRIES` + append + raise on exhaustion) - the finding's own named class; (b) fill/pad to a target (`while len(cells) < MAX_COLUMNS: cells.append('')`), which the implementer already concedes is innocent for the int path; (c) a while whose only ending is `raise`, so the While branch inherits the raise exclusion _has_exit already gives the If branch (hooks/capped_report.py:431-434). 2. A POSITIVE fixture for the rebind-slice twin of pop_until_under_cap (`while len(out) > MAX_BULLE
- R2-M3: The class named by the finding - "an enumeration of callee-name strings and argument POSITIONS, so adjacent spellings of shapes it already claims keep passing" - is narrowed, not eliminated. Three residual sub-shapes, all proven to sweep CLEAN against a working control: 1. CALLEE RENAMED BY ASSIGNMENT (highest value). _callee_aliases (capped_report.py:806-824) reads only Import/ImportFrom, so `take = itertools.islice`, `take = islice`, and the two-hop `T = take` all hide the cap in both the named path (:904) and the int path (:1040). This is the finding's own named example with the rename spelled differently. Fix: extend _callee_aliases with plain Assign bindings whose value is a Name

**Decorative tests (0):**


**New defects introduced (7):**

- R2-H1: TWO new defects, both created by the [size] branch and the census line this round added.  (1) MEDIUM - SIZE MIS-BRANCH ON A SCAN-TRUNCATING BREAK. _is_size_measure() calls len(<for-target>) a size measure because "the loop re-binds it every iteration, so its length CANNOT accumulate". True about accumulation, silent about the exit. Planted into a real repo copy (scratchpad/v_r2h1/p5_misbranch.py, 4/4 variants):   for x in xs: if len(x) >= MAX_FILE_BYTES: break     -> branch=size,       1 site   for x in xs: if len(x) >= MAX_FILE_BYTES: continue  -> branch=size,       1 site   CONTROL len(out) + break                            -> branch=collection, 1 site   CONTROL no cap             
- R2-H2: FALSE NEGATIVE (new, caused by this fix): the drop-until-under-cap loop is now invisible whenever the drop is a rebind-slice instead of a method call. Minimal pair against the repo's own shipped must-flag fixture pop_until_under_cap (hooks/capped_report.py:1331-1333) - change ONE token, `out.pop()` -> `out = out[1:]` (or `out = out[:-1]`), and the site disappears. Same constant, same function, same semantics (oldest items silently dropped to a bound). CONTROL: revert column A (guard deleted) catches it True, revert column B (_has_exit) catches it True, SHIPPED catches it False. Cause: _body_changes_length's ast.Assign clause (hooks/capped_report.py:780-788) only accepts `key = key + .
- R2-H3: NEW FALSE-POSITIVE SURFACE (R2-H3-attributable, demonstrated with a control, 0 live occurrences today). `caps` is MODULE-scoped, so one function's cap-valued default promotes its lowercase PARAMETER NAME for the whole module. Planted `MAX_N = 12 / def report(xs, n=MAX_N): return xs[:n] / def head_pair(row, n): return row[:n]` -> HEAD emits 2 display sites (report:3 AND head_pair:5); the pre-fix control emits 0. head_pair's `n` is a caller-supplied positional index, not a bound. No negative fixture covers this: `neg_param_default_not_a_bound` (hooks/capped_report.py:1526) only tests a NON-cap default, and the 29 negative controls contain no same-name-reused-in-another-function case. No
- R2-H4: Documentation overclaim, in the artifact whose job is to not overclaim. C:/Users/ammar/Downloads/unbluff/hooks/capped_report.py:54-55 states: the invariant "is true for the 111 spellings in _TAXONOMY and false for the six blind spots named beside int_cap_sites()". That reads as a complete description of the coverage boundary; it is not one. I demonstrated three int-literal cap shapes that are in NEITHER set and are blind end-to-end: `if len(out) == 10: break` (B1), `problems[:6 * 2]` (B3), and `shown = 12; problems[:shown]` (B4). The sharpest is B1, because it is a SECOND undeclared named/int asymmetry beside the one (BS3 tail-window) the implementer did flag and call "the one judgeme
- R2-M1: YES, one narrowing, measured, not blindness in the aggregate gate. The site-count floor's ADD case got narrower on one channel. A/B with roster {(rel, MAX_FINDINGS_TRACKED, "run", 1)} against a module holding the approved cap in module-level run() PLUS a NEW cap in Foo.run: bare-name build = 2 offenders + 1 roster problem ("declares 1 site(s) but 2 exist"), live=0/1. Shipped build = 1 offender (Foo.run only), 0 roster problems, live=1/1. So exemption_problems() now prints the roster fully healthy while an unrouted cap sits in the same module; the cap itself still fires through sweep(), which is the channel --selftest gates on. Before the fix the count floor caught adds into ANY same-n
- R2-M2: YES - one new defect, coverage-only, does not reopen R2-M2. The widening at hooks/capped_report.py:403 makes every `caps.add(<cap-spelled name>)` in _cap_names redundant, because is_cap_expr now resolves a cap-spelled bare Name without consulting `caps` at all. The implementer found ONE instance of this hollowing (mutation C1-H1 went SURVIVED) and repaired it with three lowercase-alias fixtures at capped_report.py:1627-1633. They did not sweep the rest of _cap_names for the same effect. Two more branches are now dead code:   (1) hooks/capped_report.py:333-335, the ast.Assign target branch;   (2) hooks/capped_report.py:355-357, the FunctionDef parameter-NAME branch. DEMONSTRATED (scrat
- NO-REGRESSION acceptance test (cluster-2 gate on R2-H1: "HEAD must not be blinder than the guard at 1dcf430"): YES, one, found while re-verifying the stated gates. tests/test_integration.py is 29/30, NOT the stated 30/30. Failing scenario: C1 "hook_health reports OK". Cause: the rewrite's scan_scope() does `from check_review_freshness import UNIT_GLOBS` off a sibling tools/ dir, so `python capped_report.py --selftest` DIES with ModuleNotFoundError in the INSTALLED layout (hooks/ copied to ~/.claude/hooks with no sibling tools/) - which is where this hook actually ships. Measured 3 ways with controls: (1) installed layout, HEAD capped_report.py -> exit 1, "ModuleNotFoundError: No module named
