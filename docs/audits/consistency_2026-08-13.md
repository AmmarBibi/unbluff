# Consistency audit - 2026-08-13

**SCOPE: DELTA, not full.** Deliverable = only the text written on 2026-08-13 (ledger section
N4, the CHANGELOG `Unreleased` block, `NEXT_SESSION_PROMPT.md`'s STATE block, the README
transcript), extracted to one file and audited against a source index built from LIVE tool
output. Stating the scope because the full-file run is misleading: over the whole ledger the
script reports **210 [A] flags**, and essentially all of them are historical numbers (past CI run
ids, the 243-claim inventory) whose sources are not in this index. **An [A] count is only as wide
as its source index** - the warning was earned and it applies here.

Tolerance rel=0.01. Source index: 79 values from 6 files - `run_selftests`, `check_mutation_anchors`,
`score_false_alarms`, the fire-ledger tally, `gh run view`, and the suite transcript.

## STEP 2 - adjudication of the 23 [A] flags in today's text

| verdict | n | items |
|---|---:|---|
| DEFINITIONAL (identifier, not a quantity) | 5 | git SHAs `48b80fc`/`c9fc757`, CI run id `31680643338`, `SWEEP_EXIT=127`, a date fragment |
| EXTERNAL / carried forward with a source elsewhere | 8 | `45 of 68` and the L-row ids (quoted from `adversarial_review_2026-08-12.md`), the `1770s`/`1960s`/`48h`/`2.2s` figures (2026-08-12 record) |
| MEASURED today, source outside the index | 6 | `$LASTEXITCODE = -1`, `44 min`, integration `30/30`, the PowerShell consumer counts |
| **SNAPSHOT needing a cutoff** | 4 | fire-ledger `278` / `1765` / `1252` / `2043` |
| DRIFT | **0** | - |

**No fabricated or stale number.** The one ACTION is the snapshot: the ledger is a LIVE producer
and had grown to 2198 records by the time this audit ran, so a bare "Snapshot 2026-08-13" does not
reproduce. Re-derived with an explicit cutoff - entries with `ts <= 2026-08-13T11:24:36` give
exactly 2043 records and exactly the cited per-hook figures. **Fixed:** the ledger row now states
the cutoff.

[B] orphan figures 0. [C] dangling refs 0. [E] placeholders 0. [F] promised-but-unrendered 0.

## STEP 3 - the reasoning pass, and it found what the script could not

Two interpretation drifts, both written by me today, both in the same paragraph of the plan:

1. **"SWEEP RUNTIME, re-measured: ~30 MIN when IDLE (1770s, 1960s)"** - I did NOT re-measure
   those. They are carried forward from 2026-08-12. What I measured today is the LOADED case.
   Calling carried-forward figures "re-measured" is exactly the class source-coverage caught on
   2026-08-12. **Fixed:** the line now separates what was carried forward from what was measured.
2. **"68 of 186 entries"** - the roster held **179** when that sweep ran; it reached 186 only
   after the day's additions. **Fixed** to 179.

Claim support checked and SOUND: the PGG-PS rejection claim ("measurement rejected the prescribed
fix") is supported by the 15-consumer measurement AND durably encoded - `PS_SHOULD_STAY_QUIET`
asserts `-Last` stays quiet, pinned by `PG8`, so the claim does not rest on a scratchpad file.

## Verdict
0 DRIFT, 3 fixes applied (1 mechanical precision, 2 interpretation). Both interpretation defects
were invisible to the script and were found only by STEP 3 - which is the argument for STEP 3.
