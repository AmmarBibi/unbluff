# Consistency audit - 2026-08-28

**Scope:** what THIS session authored - commits `34f82eb..f10a242` (items 7, 24, 17, the coverage
work, and the closing baseline). Plan rows 7, 8, 11, 17, 24, 26-31 and the "Known-stale by design"
section. Docstrings only for `.py`.

**Deliverable:** `docs/PLAN.md`
**Sources indexed:** 9 raw gate outputs captured this session - `sweep1..sweep4.txt`,
`suite13.txt`, `tf_run2.txt`, `anch2.txt`, `sw_tf3.txt`, `sw_tr.txt` (93 values).
**Tolerance:** rel 0.01, abs 1e-9.
**Mechanical pass:** `skills/consistency-audit/scripts/audit.py`, exit 0.
1092 numbers found, 856 checked (123 reference-context, 113 year-skipped).

## Mechanical result

| class | count | adjudication |
|---|---|---|
| [A] number with no source match | 102 | 1 DRIFT, rest DEFINITIONAL / OUT-OF-SCOPE |
| [B] orphan figure | 0 | - |
| [C] dangling cross-ref | 0 | - |
| [D] claim to verify by reasoning | 15 | 1 in scope, VERIFIED empirically |
| [E] unfilled placeholder | 11 | all OK - quoted examples inside item 18 |
| [F] table promised, not rendered | 0 | of 5 tables found |

### [A] - adjudicated

The source index holds 93 values from this session's gate outputs; the plan is ~1300 lines
spanning eight sessions. Almost every flag is a number the index could not possibly contain.

- **DEFINITIONAL / EXTERNAL (majority):** ISO timestamp components (`05:05:59Z` -> 59, 51),
  file:line citations (`check_readme_fresh.py:190`), commit SHAs read as integers (`1443a59` ->
  1443), byte deltas, and line counts. Not drift; not comparable to a sweep index.
- **OUT OF SCOPE:** figures from earlier sessions (the 284-line retired plan, the 2,455/2,139/
  1,338/735/153 area table, `6 of 11`, `756`/`171` byte differences). Authored before this
  session; untouched by it. Flagged only because the index is this session's.
- **DRIFT (1), FIXED:** item 7 line 247 read *"verified, 20 rows"* of `AUX_GATES`. True at the
  moment of the cut; `AUX_GATES` is **21** since `tier-freshness` registered later the same
  session. A count that grows every time a gate is added - which is the row's own subject -
  stated as though current. Fixed to name it an INSTANT and point at the registry for the live
  value, using `file_size_baseline.json`'s own convention. This is the same defect item 15
  exists for, one level up, and it appeared inside the row describing that defect.

### [D] - the reasoning half

Only one of the 15 is a substantive technical assertion authored this session:

- **L248** - *"a re-ASSIGNMENT would have been WORSE than nothing: it leaves an `ast.Assign`
  named `AUX_GATES` whose value is an Attribute, so the source-text readers would find the
  assignment, fail `literal_eval`, and report corruption rather than a move."*
  It was written as REASONING, not measurement, so it was executed:
  `ast.parse("AUX_GATES = gate_registry.AUX_GATES")` yields an `ast.Assign` whose value is
  `ast.Attribute`; `ast.literal_eval` on it raises `ValueError: malformed node or string`, which
  is the branch returning *"AUX_GATES is not a literal this harness can read"*. **VERIFIED.**
- **L502** - item 11's second-instance paragraph. Its supporting measurement (the mutating
  population stayed at 8 and excluded `check_tier_freshness.py`) is recorded in the row and was
  taken from `check_selftest_isolation`'s own output. **SUPPORTED.**
- The remaining 13 are prose from earlier sessions, out of scope.

### [E] - all OK, and the run is itself evidence

All 11 flags sit at lines 694-715, inside **item 18** - the row documenting that the shipped
placeholder class fires on source-code literals. They are the row's own quoted examples
(`[]`, `[TODO]`, `[TABLE]`, `[insert value]`).

Worth recording: **the audit script reproduced its own documented defect on this run.** Item 18
predicts exactly this and remains open with the fix written (require a letter in the token, or
skip the class for code extensions, probing both directions). No new row needed.

## Cross-checked directly against source (not via the index)

Every number this session authored, against the raw gate output that produced it:

| claim | source | verdict |
|---|---|---|
| `run_selftests.py` 655 -> 444 | `git show c2926c0:` / `34f82eb:` | OK (655, 444) |
| `tools/gate_registry.py` 275 lines | `git show 34f82eb:` | OK |
| `piped_gate_guard.py` exactly 800 | `wc -l` | OK |
| `hook_divergence_report.py` 803 -> 732 | `git show 0d9e8a5:` | OK (732) |
| `tools/hook_divergence_trend.py` 105 | `git show 0d9e8a5:` | OK |
| `check_readme_fresh.py:190` | `grep -n` | OK (line 190) |
| sweep 1 rc=1, 223/225, survivor MODE-1 | `sweep1.txt` | OK |
| sweep 2 rc=0, 223/225, 0 survivors | `sweep2.txt` | OK |
| sweep 3 rc=0, 223/225, 0 survivors | `sweep3.txt` | OK |
| sweep 4 rc=0, 228/230, 0 survivors | `sweep4.txt` | OK |
| 2 not-runnable (#30, #D10c) all sweeps | `sweep1..4.txt` | OK |
| `false_alarm_scorer` last run 2026-08-20T13:46:26Z | `tf_run2.txt` | OK (8 days) |
| 7 declared tiers, 1 exempt | `tf_run2.txt` | OK |
| 233 anchors / 230 entries / 42 files | `anch2.txt` | OK |
| file-size 69 files | `suite13.txt` | OK |
| suite 45/45 rc=0 | `suite13.txt` | OK |
| `RECORDING_TIERS` = 7 | live import | OK |

## Cross-section consistency

- The sweep counts appear in item 7 (four sweeps), item 24, item 26 and the closing-baseline
  block. All four tell the same story and each is bound to a named sweep with its timestamp, so
  none is a floating "current" number. The closing block explicitly says **compare against
  228 of 230, not 223 of 225**, which is the guard against the older figure being copied forward.
- `223 of 225` survives in six places; every one belongs to a dated instant (sweeps 1-3, the
  08-27 baseline, the CI run at `91f015e`, and item 26's `1 of 225`). Correct as written.
- "Known-stale by design" no longer carries the retyped *"Every other tier is current as of
  2026-08-24T21:23Z"*. It now defers to `tier-freshness`. That removes the only hand-maintained
  freshness claim in the document.

## Interpretation check

Does the narrative match the numbers? Yes, with one thing worth stating plainly: **item 7's
headline is "DONE", and sweep 1 for that item returned rc=1.** The row says so in its own text
and names MODE-1 as the survivor, with the fix and the clean sweep 2 that followed. The DONE is
earned by sweep 2, not asserted over sweep 1. That is the honest ordering and it reads correctly.

## Verdict

**1 DRIFT found and fixed** (item 7's `20 rows`). **1 unverified claim, verified** (L248).
0 orphan figures, 0 dangling refs, 0 real placeholders, 0 promised-but-missing tables.
No fabricated numbers: every quantity this session put in the plan traces to a captured gate
output, and the six surviving `223 of 225` references are dated instants rather than stale
currents.
