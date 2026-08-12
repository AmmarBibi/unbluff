# Completeness audit - 2026-08-12 (close ritual, pass 2 of 4)

**Subjects:** `docs/NEXT_SESSION_PROMPT.md`, `docs/audits/coverage_ledger_2026-08-09.md` at `0ef4e2b`.
**STEP 1 run in full** - all 15 soft-defer markers, both files, mechanically.

## STEP 1 - soft-defer sweep: 7 hits, 0 genuine

All seven are prose: `"NONE of these may be dropped"`, the ledger's own
`BUILT / SCHEDULED / EXCLUDED` taxonomy label, three coverage statements
(`"0 dropped, coverage_complete: true"`), a historical miscount
(`"the 41 excluded skills/*/scripts/"`), and one row whose body happens to contain the word.
**No optional-forever item remains.**

## STEP 2 - does every item this session surfaced have a HOME?

Checked by enumerating what the session produced and testing both documents for each, rather
than re-reading them and judging whether they looked complete.

**21 of 22 had a home.** Everything BUILT is in the ledger; the plan carries the queue, which
is the correct division. The one gap:

### pytest rc 3 - a DECISION that existed only in a transcript

`INTERNAL_ERROR` appeared in **neither** document. It is a confirmed MEDIUM from the
adversarial pass - rc 3 is by pytest's own definition not a verdict, and it still hard-blocks
both gates - and I decided to leave it blocking, gave three reasons, and wrote them **only in
conversation**.

That is precisely the failure this skill's failure-(a) is named for, and precisely the one
caught the day before with `SELFTEST-BUDGET-FTOS`. **A decision that lives only in a transcript
is indistinguishable, a week later, from an item nobody considered.** Worse than an unhomed
build item, in fact: a future reader finding rc 3 absent from `_PYTEST_INCONCLUSIVE` cannot
tell a deliberate exclusion from an oversight, and the obvious "fix" would re-introduce
`FTB-RC4`.

Now recorded as a **FINALIZED-EXCLUSION** with its reasoning: `FTB-RC4` is direct evidence that
waiving a not-really-a-failure code is the dangerous direction; rc 3 means pytest itself broke
so zero tests ran, making its traceback more actionable than a once-per-project notice; and it
is not a false alarm on CORRECT code, which is the only thing criterion 3 asks of this map.

**Second occurrence of this exact mode in two days.** The generalisation worth carrying: after
deciding NOT to do something, write the decision down in the same edit - the reasoning is the
deliverable, not the non-action.

## STEP 3 - ledger refreshed

Ledger N3 gained this session: `FTB-RC4`, `FTB-MASK`, `FTB-SPELL`, `FTB-CFG`/`FTB-LAYOUT`,
`FTB-GATES`, `FTB-MARKER`/`FTB-CAP`, `ROSTER-DERIVE`, `WT-CAUSE`, `RICH-CI`, `CI-JOBS`,
`SELFTEST-BUDGET-FLAKE` (BUILT), the five hollow-pin modes, the anchor-drift rule, the
guard-fires rule, and now the rc-3 exclusion.

## STEP 4 - verify

Re-grepped after the edit: **0 genuine soft-defer markers**; every surfaced item now maps to
BUILT, SCHEDULED, or FINALIZED-EXCLUSION with a named home.

**Scope limit, stated:** STEP 2's full fan-out form applies to encoding a spec corpus. For this
session the completeness question is "does every surfaced finding have a home", which is what
was audited. The 243-row claim disposition remains criterion 1's step 5 - SCHEDULED, not
skipped, and not duplicated here.
