# Coverage ledger - 2026-08-08

The objective proof of coverage. Every item is `BUILT` (with the unit that carries it),
`SCHEDULED` (with a phase), or `FINALIZED-EXCLUSION` (with a justification). Nothing may sit in
none of the three.

**This ledger supersedes `coverage_ledger_2026-08-06_b1.md`, which predates
`piped_gate_guard`, `timing_claim_guard` and `tooling-discipline.md` section 6 - all three are
recorded here for the first time.**

## A. The independent review of the ship-gate classification

Runs `wf_c9822f7b-865` (5 lenses + 9 refuters) and `wf_5741d0aa-244` (the remaining 11 refuters).
**Denominator: 20 findings produced, 20 adjudicated, 0 dropped. 12 confirmed, 8 refuted.**
Recovered from disk after the launching session ended; both runs left the tree byte-identical to
its pre-run snapshot (`4f1f466d`).

| # | confirmed finding | sev | state | carrier |
|---|---|---|---|---|
| 1 | `_is_superseded` freezes an ACTIVE user plan file | HIGH | **BUILT** | `meta_audit_on_stop._SUPERSEDED_DECL_RE`, mutation `SUP1`, commit `d6e7ad2` |
| 2 | the same defect via the accounting lens (a HIGH outside the 21) | HIGH | **BUILT** | same fix; the accounting point is recorded in "THE CLASSIFICATION WAS REVIEWED AND IS REFUTED" |
| 3 | "SHIP-BLOCKING is at least 2, not 1" | HIGH | **BUILT** | same fix; the count correction is in the same section |
| 4 | a bracket in the install path blinds every sweep | HIGH | **BUILT** | `glob.escape` at 13 call sites in 9 files, mutations `GLOB1a`/`GLOB1b`, commit `d70f869` |
| 5 | one SKIP freezes every recorded pass forever | HIGH | **BUILT** | `hook_health_check` slice age stamp, mutation `SKIP1`, commit `aa7883f` |
| 6 | `install.py` ships executable Python to `~/.claude/skills`, outside the rule | HIGH | **BUILT** (code) + **SCHEDULED** (guard) | DOCX-1 fixed in `extract.py` with mutations `DOCX1a`/`DOCX1b`, commit `904219c`; R1 clause 4 written; the mechanical guard is `ENTRY-GUARD`, v1.4 phase 1 |
| 7 | the rule was applied only to items already labelled HIGH | HIGH | **BUILT** (doc) | CORRECTIONS item 5 - population restated as "every open finding" |
| 8 | row 18 attributed to the file its source exonerates | MEDIUM | **BUILT** (doc) | CORRECTIONS item 4 |
| 9 | the problem list prints under the process locale encoding | MEDIUM | **SCHEDULED** | `ENC-1`, v1.4 phase 1, design-critique-first, roster measured at 24 of 24 |
| 10 | entry points and the universe exclude the four installed skills | MEDIUM | **BUILT** (doc) | CORRECTIONS items 1-2, universe restated 41 -> 44 |
| 11 | "24 of 41 (17 dev-time)" is not reproducible | MEDIUM | **BUILT** (doc) | CORRECTIONS item 3 |
| 12 | three citations do not resolve; two line numbers stale by four | LOW | **SCHEDULED** | v1.4, with the other LOW rows. Recorded explicitly rather than silently absorbed |

**8 REFUTED** are retained in `final_adjudication.json` with each refuter's reasoning. A cluster
of near-misses is itself information; none requires a home.

## B. Deferred this session - every one carries a phase

Verified mechanically: 9 of 9 have a row AND name a phase/owner.

| id | sev | phase | why it was not built now |
|---|---|---|---|
| `BUDGET-1` | MEDIUM | v1.4 phase 1 | the selftest sits at 90-96% of its share, but every reading available is against a control saying the box is loaded. Not raising a cap on a confounded number - the A8-PP discipline |
| `ENC-1` | MEDIUM | v1.4 phase 1 | MEDIUM, and the naive fix duplicates a block into 24 files, creating the twins three findings already exist to remove. Design critique first |
| `ENTRY-GUARD` | MEDIUM | v1.4 phase 1 | new gate surface, and the surface is frozen |
| `INT-MUT` | MEDIUM | v1.4 phase 2 | the 30-scenario integration suite has zero mutations; needs a harness mechanism, i.e. new gate surface |
| `INT-WIN` | MEDIUM | v1.4 phase 1 | a Windows mirror for the integration job; deliberately not added in the same commit as the defects it would have caught |
| `PGG-PS` | MEDIUM | v1.4 phase 1 | `piped_gate_guard` is `matcher: "Bash"` and blind to PowerShell; needs its own corpus and mutations |
| `M-M12` | MEDIUM | phase 2 | anchor uniqueness; one live instance measured and reported by the M1 gate |
| `SC1` | MEDIUM | phase 2 | the measurement-tool exemption hole |
| `SC2` | LOW | phase 4 | mutation scratch-tree leak |

## C. Shipped surface recorded here for the FIRST time

The 2026-08-06 ledger predates all three.

| item | state | carrier |
|---|---|---|
| `hooks/piped_gate_guard.py` | **BUILT** | the suite's first PreToolUse hook; wired by `install.py:desired_groups()["PreToolUse"]`; mutations PG1-PG5; **known gap `PGG-PS` scheduled** |
| `hooks/timing_claim_guard.py` | **BUILT** | joins `post_tooluse_dispatcher`; advisory, exit 0 always; mutations TC1-TC4; fires on 18 of 109 duration lines (17%) |
| `tooling-discipline.md` section 6 | **BUILT as policy** | "never let the author write the only probe". Enforced this session by ACTION: the classification was independently reviewed rather than self-certified, and the review refuted it |
| `hooks/hook_health_check_selftest.py` | **BUILT** | the 800-line split (`07b0a01`); in `KNOWN_NO_SELFTEST`, so the suite stays at 32 |
| `skills/consistency-audit/scripts/extract.py` | **BUILT + newly GATED** | first skill script reached by the mutation harness (`DOCX1a`/`DOCX1b`); anchors now span 30 files, was 29 |

## D. Gate state at this ledger

| gate | result |
|---|---|
| `run_selftests.py` | **32/32**, rc=0 |
| `tests/test_integration.py` | **30/30**, rc=0 |
| `tools/check_mutation_anchors.py` | **139 anchors / 138 entries / 30 files**, rc=0 |
| `tools/mutation_check.py` (filtered, per unit) | SUP1, GLOB1a/b, SKIP1, DOCX1a/b all CAUGHT |
| full cross-platform sweep | **CI - in progress at the time of writing.** Not recorded as green here; a number read off a still-running producer is not a measurement |

## E. Justified exclusions

| excluded | justification |
|---|---|
| `tests/*.py` (4) from the module universe | test fixtures, not shipped surface. Stated, not assumed |
| headers/footers/footnotes in docx extraction | separate OOXML parts, read by neither path. Recorded as a limit in `extract._docx_to_text`'s docstring rather than left as a surprise |
| the 8 REFUTED review findings | each carries a refuter's reasoning; refuted is an adjudicated outcome, not a deferral |

## Audit-instrument defects found while producing this ledger

Recorded because the ratio is the finding: **in today's two audits the instrument was wrong four
times and the deliverable twice.**

- The completeness probe phrase-matched finding TITLES against the plan and reported 2 of 12
  homeless; both were the same defect as SUP-1, homed and fixed. Phrase-matching a title is not
  a coverage test.
- The consistency checker could not distinguish a dated historical record from a live claim, and
  counted mutation-table anchor STRINGS as call sites.
