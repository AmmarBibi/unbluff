# Coverage ledger - B1 (C1-NEW), 2026-08-06

Second ledger of 2026-08-06. `coverage_ledger_2026-08-06.md` reconciled the M1 / B3-P /
score_corpus session; this one reconciles the B1 build and the close-out audits. Written as a
separate file so neither session's artifact overwrites the other.

A source item is "done" only when BUILT, SCHEDULED with a plan row, or a FINALIZED EXCLUSION
with a written justification.

## Carried forward from `coverage_ledger_2026-08-06.md` - now discharged

| item | previous status | status now |
|---|---|---|
| C1-NEW discrimination rule | DESIGNED, NOT BUILT | **BUILT** - `hooks/cap_shapes.py` + `hooks/cap_types.py`, `f77eefd`. 102 of 105 with 0 false positives, which is the ceiling |
| B1 corpus entries derived from the PREDECESSOR's capabilities | SCHEDULED, NOT STARTED | **BUILT** - `_MODULE_SCOPE_ENTRIES`, 7 caps outside any function, each baseline-verified by running the predecessor over it. Control: an intermediate build was blind to 7 of 7 while the predecessor caught 7 of 7 |
| B1 exemption roster must report an exemption that stops being needed | SCHEDULED, NOT STARTED | **BUILT** - `cap_shapes.exemption_problems()`, audited in both directions, mutation `#B11`. Live and fixture rosters held apart so a fixture-only entry is not reported dead every run |
| `enabledPlugins` at PROJECT scope | OPEN QUESTION | **STILL OPEN.** Exposure MEASURED at zero: no project-scope `.claude/settings*.json` under `Downloads` declares it, and unbluff has none at all. That is an exposure measurement, NOT an answer - whether Claude Code honours it at project scope is unestablished and B3-P stays incomplete |

## Source: the 8 C1-NEW acceptance criteria - PROBED, not assumed

| criterion | status | evidence |
|---|---|---|
| AC1 - drop-until-under-cap must not go blind when the drop is a rebind-slice | **BUILT** | probed both spellings (rebind-slice and `pop`); both flag |
| AC2 - a callee renamed by assignment must still resolve | **BUILT, was REINTRODUCED** | found broken by this probe while the score sat at 100 of 103. Fixed in `_import_aliases`; corpus family `_ACCEPTANCE_ENTRIES`; mutation `#B18` (which first came back SURVIVED - the fixture was in the wrong file) |
| AC3 - no branch may be dead the day it lands | **SCHEDULED** | plan row `B1-AC3`, phase 2. NOT verified: every rule has a fixture, which proves reachability, not completeness. The one criterion this session neither verified nor previously scheduled |
| AC4 - the no-regression floor must be DERIVED, not a roster | **BUILT (not by this unit)** | `no_regression` derives it by running the predecessor over the corpus; nothing in C1-NEW declares a floor |
| AC5 - a size-vs-collection split must not mis-branch a scan-truncating exit | **BUILT** | probed; flags. Plus 16 negative controls for the suppression rules |
| AC6 - `caps` must not be module-scoped so one function's default promotes a name file-wide | **FINALIZED EXCLUSION** | discharged BY CONSTRUCTION: C1-NEW never builds a set of cap names, so the defect has no surface. Recorded as an exclusion rather than a pass, because nothing tests it and nothing can |
| AC7 - exemption keys must separate scopes that share a name | **BUILT** | key is `(module, qualname, kind)`; a method `run` flags while the module-level `run` stays exempt. All three components now have controls and mutation `#B19` |
| AC8 - no docstring may state a coverage boundary it does not have | **BUILT** | the docstrings state the measured figures, the ceiling and the untested band `5..9` of the positional floor explicitly |

## Source: the six audit docs - id-space reconciliation

81 distinct finding ids; 37 the plan never names; **35 adjudicated as not-gaps, 2 real.**

| item | status | where |
|---|---|---|
| **SC3** - every component of an exemption key must be load-bearing; the source reserved mutation `B9` and nobody built it | **BUILT** | three controls + mutation `cap_shapes #B19`, CAUGHT. Plan row SC3 |
| **SC4** - `F-H3`'s fix ORDER (`_child` first, or mutation #10 flips to SURVIVED) | **SCHEDULED** | plan row SC4, phase 4 |
| `F-M8` - `_max_names` sees only `ast.Assign` | **BUILT** | dispositioned in triage as folding into row 1; C1-NEW no longer classifies bounds at all, so imports / annotated assignments / attribute bounds are all covered |
| `C1-R1..R8`, `R2-H2`, `R2-M3`, `N1-N4` | **COVERED as ranges** | retired into the acceptance criteria by row A2; `R2-H2`/`R2-M3` are part of the union those 8 rows cover |
| `C0`, `C1-C4`, `N7`, `M0`, `M05`, `M50`, `L6`, `Q1`-`Q5` | **FINALIZED EXCLUSION** | not findings: experiment control labels, mutation labels in a control run, fragments of `git diff -M05`/`-M50`, a line reference, and Q-section headings |

## This session's own new findings

| item | status |
|---|---|
| B1-CEILING - 3 byte-identical corpus pairs with opposite verdicts | **BUILT** - `score_corpus.contradictions()` + ceiling printed every run, mutation `#B1c` |
| B1-SCOPE - `tools/` unswept; 4 sites, adjudicated 1 plausibly real / 2 guard false positives / 1 unadjudicated | **SCHEDULED** - phase 2 |
| B1-C2FLOW - clause 2 does not follow flow through an assignment | **SCHEDULED** - phase 2 |
| B1-AC2 / B1-AC2b - acceptance criterion 2 reintroduced; its first fixture was decorative | **BUILT** |
| B1-DUP - the module split emitted two definitions twice | **BUILT** (removed) |
| N3-DUP - no check notices a module defining the same top-level name twice | **SCHEDULED** - phase 4, with N3 |
| B1-AC3 - acceptance criterion 3 unverified | **SCHEDULED** - phase 2 |
| B1-COUNT - `f77eefd` says "11 new mutations"; it is 10 new + 1 moved | **CORRECTED** in the plan |
| the selftest timing was 1.291s, not the 1.08s committed | **CORRECTED** in the plan, with the control |

## Not covered - stated, not hidden

**The three files from the previous session (`hook_layers.py`, `check_mutation_anchors.py`,
`score_corpus.py`) are STILL unadversarially reviewed, and `cap_shapes.py` / `cap_types.py`
now join them.** The user approved the scope; it is blocked on a usage snapshot needed to
authorise a Workflow fan-out. `check_review_freshness` therefore gets WORSE this session, not
better - two new guard files, zero new reviews. Recorded as a live debt, not a gap in the
plan.

**The three large source docs were not re-enumerated prose-by-prose** (see the SC3/SC4 section
of the plan). The id-space reconciliation is complete for items carrying an id and blind to
prose-only requirements. SC3 is proof that matters: it hid for three sessions behind an id
(`B9`) that never existed.

## Verdict

Every item found has a home. **11 BUILT, 6 SCHEDULED with plan rows, 2 FINALIZED EXCLUSIONS
with justifications, 1 OPEN QUESTION recorded, 2 CORRECTIONS applied.** Zero items with no
home. Two coverage limits are stated above rather than left implicit.
