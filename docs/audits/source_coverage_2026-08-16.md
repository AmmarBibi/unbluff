# Source-coverage audit - 2026-08-16 session

**The gap this looks for:** not what the plan defers, but what the plan never mentions. Here the
"source" is not a document - it is the repo itself. Review `wf_f63b9ccf-816` examined **4 of 55**
tracked `.py` files. Its 40 confirmed findings are defect **classes**, and fixing them only where
they were found is the instance-fix this project forbids.

**DENOMINATOR: 55 tracked `.py` files. 4 reviewed. 51 never examined by any reviewer.**

## Per class

| Class | Candidates found | Real | Verdict |
|---|---|---|---|
| 1 - `record()` on the PASS path only, or a hardcoded result | 6 call sites | **0** | **CLEAN** - all 6 now compute a real verdict |
| 2 - invocation-dependent sibling import swallowed by `except` | 4 outside the reviewed pair | **1** | `score_false_alarms.py` is a genuine instance |
| 3 - tautological stub using the constant under test | 0 by pattern | 0 | the one instance was `selftest_budget`'s, fixed |
| 4 - floor living only in `selftest()` | not mechanically greppable | - | see note |
| 5 - read/parse failure mapped to a legitimate-empty value | **106** except clauses | unknown | needs adjudication |
| 6 - declared roster where a derived one exists | **88** module-level rosters | unknown | needs adjudication |

## Class 2 - the one confirmed live instance

`tools/score_false_alarms.py` inserts `REPO`, `tests/` and `hooks/` into `sys.path` and **never
`tools/`**, so its `import gate_ledger` resolves only because running it as a script puts
`tools/` at `sys.path[0]`. Under `-m`, or any in-process import from another cwd, it raises into
`except Exception: pass` and the `false_alarm_scorer` tier records nothing while exiting 0 -
finding #35 exactly, in a file the review never opened.

Three sibling sites are **safe** and are recorded as justified rather than fixed:
`run_selftests.py:451` and `tests/test_integration.py:291` insert `tools/` explicitly, and
`tools/mutation_check.py:109` gained a module-scope insert during this session's split.

## Classes 5 and 6 - candidate counts, NOT defect counts

106 and 88 are the size of the population that needs looking at, not the number of defects. They
are reported because a class with 3 of the 40 confirmed findings behind it (5) and one with the
repo's most-repeated defect behind it (6) should not be described as "checked" on the strength of
a grep. Adjudicating them by hand in the main session would be the wrong instrument; per
tooling-discipline 7.1 the 51 unexamined files are the *cheap* high-yield fan-out target - the
run that finds what survives because nobody looks.

**Scheduled as task #17**, with the measured denominators carried into the task so the next
session does not re-derive them.

## Class 4 - stated honestly as not-swept

"A floor that lives only in `selftest()`" has no reliable textual signature: it requires knowing
which function the registered gate actually invokes. Two instances were found by the review
(`ship_bar_gate`, `check_file_size`) and both are fixed. Whether others exist is **unknown and
unmeasured**, and is included in task #17's scope rather than reported as zero. A class nobody
swept is not a class with no instances.
