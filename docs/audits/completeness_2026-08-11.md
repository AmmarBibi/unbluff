# Completeness audit - 2026-08-11 (close ritual, pass 2 of 4)

**Subjects:** `docs/NEXT_SESSION_PROMPT.md`, `docs/audits/coverage_ledger_2026-08-09.md`.
**STEP 1 was run IN FULL** - the soft-defer marker sweep, all 15 markers, both files. It was
skipped on 2026-08-11 (ledger N2) and that omission produced new findings, so it was run
mechanically here rather than by eye.

## STEP 1 - soft-defer sweep: 5 hits, 0 genuine

| line | marker | verdict |
|---|---|---|
| `NEXT_SESSION_PROMPT.md:212` | `DROPPED` | **PROSE.** *"NONE of these may be dropped"* - the assertion is the OPPOSITE of a defer |
| `NEXT_SESSION_PROMPT.md:228` | `EXCLUDED` | **TAXONOMY LABEL.** Names the ledger's own `BUILT / SCHEDULED / EXCLUDED` states |
| `coverage_ledger:356` | `DROPPED` | **COVERAGE STATEMENT.** *"24 adjudicated, 0 dropped, `coverage_complete: true`"* |
| `coverage_ledger:387` | `DROPPED` | **PROSE.** *"recorded rather than quietly dropped"* - the row is SCHEDULED and says so |
| `coverage_ledger:539` | `EXCLUDED` | **HISTORICAL.** Describes a past miscount ("the 41 excluded `skills/*/scripts/`"), not a decision to defer |

**No optional-forever item remains.** Every marker resolves to prose about not deferring, which
is the healthy direction for this class of hit.

## STEP 2 - does every item this session surfaced have a HOME?

Checked by enumerating what the session produced and testing the ledger for each - not by
re-reading the ledger and asking whether it looked complete.

| item | home | state |
|---|---|---|
| `FASTTEST-BLOCK` | ledger N0 | **BUILT**, CI-verified on `367ace4` |
| the selftest that ASSERTED the defect | ledger N0 | **BUILT** |
| `CAP-FP-1` (cap_shapes false positive) | ledger N0 | **SCHEDULED**, V1.4-BACKLOG by R1/R2 |
| the `meta_audit` budget misattribution | ledger N0 | **BUILT** |
| `FTB-1` / `FTB-6` decorative-probe class | ledger N0 | **BUILT** |
| independent adversarial pass | ledger + `NEXT_SESSION_PROMPT` step 3 | **SCHEDULED**, still owed |
| **`fast_test_on_stop` selftest at 15.8s of a 25s cap** | **NONE - this is the finding** | now **SCHEDULED** |

### The gap, and it was mine

`SELFTEST-BUDGET-FTOS` was surfaced during the session, stated in a chat message, and
deliberately **not** written into the plan - on the reasoning that adding it unasked would be
scope creep. That reasoning was wrong, and this audit exists to catch exactly it.

**Recording an item as SCHEDULED is not doing the work; it is refusing to lose it.** The two
rules do not actually conflict: "don't widen the scope" governs what gets BUILT, while
no-defer-and-forget governs what gets TRACKED. An item that lives only in a chat message is,
one week later, indistinguishable from one nobody ever noticed - which is the precise failure
mode this skill's failure-(a) is named after. Now filed in ledger N0 alongside
`SELFTEST-BUDGET-FLAKE`, since the durable fix is the same mechanism (self-budgeting covers 3
of 24 hooks).

## STEP 3 - ledger refreshed

Ledger N0 gained five rows this session: `FASTTEST-BLOCK`, the corrected defect-asserting
selftest, `CAP-FP-1`, the `meta_audit` budget misattribution, the `FTB-1`/`FTB-6` decorative
probe class, plus `SELFTEST-BUDGET-FTOS` from this pass.

## STEP 4 - verify

Re-grepped after the edit: still **0 genuine soft-defer markers**; the added row carries an
explicit **SCHEDULED** state and a named home (step 3, with `SELFTEST-BUDGET-FLAKE`). No item
surfaced this session is now without a home.

**Scope limit, stated rather than implied:** STEP 2's full form fans out over authoritative
source documents to find content the plan never mentions. That form applies to a spec-encoding
project; unbluff's completeness question for THIS session is "does every surfaced finding have
a home", which is what was audited. The broader source-vs-plan sweep over `README.md` and
`skills/*/SKILL.md` is criterion 1's own step 5 (the 243-row disposition) and is not duplicated
here - it is SCHEDULED, not skipped.
