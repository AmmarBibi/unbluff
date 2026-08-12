# Consistency audit - 2026-08-12 (close ritual, pass 1 of 4)

**Deliverable:** `docs/audits/coverage_ledger_2026-08-09.md` at `0ef4e2b`.
**STEP 1 run in full** via the bundled `scripts/audit.py`. Tolerance rel 0.01 / abs 1e-9.
**Source index: 824 values from 29 files** - scoped wide from the start, applying yesterday's
lesson rather than rediscovering it (an under-scoped index reported 92 false `[A]` hits and
would have produced 92 confident FALSE-POSITIVE verdicts that read as thorough work).

## Verdicts

**[A] numbers with no source match - 0 of 864 checked.** 1028 found, 864 checked, 102 skipped
as reference-context, 62 as years. No numeric drift.

**[B] orphan figures 0. [C] dangling cross-refs 0. [F] tables promised but not rendered - 0 of
25 tables.**

**[D] claims to verify by reasoning - 2, both OK, both re-verified rather than carried over.**

- `L456` *"200 entries and every one is `run_selftests`"* - re-read `gate_runs.json`: **200
  entries, `{'run_selftests': 200}`**. Still exactly true after roughly fifteen further suite
  runs today, because the file is a fixed-size rolling window. **And it re-confirms the finding
  it supports for the second day running:** this session ran the mutation harness ~15 times,
  the integration suite, and seven CI rounds, and the ledger still records only
  `run_selftests`. The "gate ledger covers 1 of 5 tiers" row is not stale - it was
  re-demonstrated by today's work as well as yesterday's.
- `L550` - K1's qualitative import-closure claim, unchanged by this session. No new evidence
  required.

**[E] unfilled placeholders - 3, ALL FALSE POSITIVE, all `CA-SELFREF`.** `L306` is the `[]` in
"both rosters return `[]`" (a literal empty-list RESULT); `L373` x2 sit inside the ledger's own
`CA-SELFREF` row, which is *describing* the flag. Instance count continues to rise purely
because the defect keeps being documented - the self-propagation recorded yesterday, still
SCHEDULED, still not a new row.

## Cross-section consistency - this session's own figures, checked against their producers

| claim in the ledger | source | verdict |
|---|---|---|
| 24 confirmed of 49 produced | workflow result: `produced=49 adjudicated=49 confirmed=24 refuted=25 coverage_complete=True` | **OK** |
| 8 confirmed findings remain | 24 - 16 closed | **OK, derived** |
| 7 of 25 dispatcher sub-hooks | `dispatcher_subhooks()` returns exactly those 7 | **OK, measured** |
| CI is 17 jobs | now gated by `check_readme_fresh.verdict_jobs`, two parsers agreeing | **OK, enforced** |

**One interpretation check, which is what this step exists for:** the ledger says
`ROSTER-DERIVE` was BUILT *and* that no user was ever exposed. Those are consistent only
because the row states plainly that coverage was correct while the DERIVATION was not, and
distinguishes "we were lucky" from "we were right". Had it said the roster was previously
*wrong*, that would have been drift of the interpretation kind - the failure a number-matcher
cannot see.

## Actions

- No DRIFT found; no prose corrected.
- `CA-SELFREF` unchanged, still SCHEDULED.
- Method note carried forward and applied here: **scope the source index before believing an
  `[A]` count, in either direction.**
