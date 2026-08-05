# Coverage ledger - the B5 guard audit, reconciled 2026-08-05

Source: `docs/audits/p14_audit_findings.md` (the three-guard fail-open audit).
Reconciled against what P14 Part B phase 1 actually built (commit `0c0dfb9` + follow-ups).

A source is "done" only when every item it enumerates is BUILT, SCHEDULED with a plan row, or
a FINALIZED EXCLUSION with a written justification. This ledger is the audit trail; it is not
a summary of the plan, it is a reconciliation against the SOURCE.

## `hooks/transcript_util.py` - twin guard. 6 blind shapes + 2 structural recommendations

| source item | status | where |
|---|---|---|
| N1 complete divergent classifier, every name renamed | **BUILT** | behavioural ceiling (`_DISCRIMINATORS`/`_HARNESS_TAGS`); fixture `hooks/renamed.py`; probe case N1 |
| N2 enumerated name as an ANNOTATED assignment | **BUILT** | `_bound_identifiers` walks the AST; fixture `hooks/annotated.py` |
| N3 function names bound without a plain `def` (lambda, `async def`) | **BUILT** | `_bound_identifiers` covers `FunctionDef`/`AsyncFunctionDef`/`Name`-Store; fixture `hooks/lambdas.py` |
| N4 byte-identical twin one directory down | **BUILT** | `os.walk` recursion; fixture `hooks/lib/user_turns.py` |
| N5 same twin in a SIBLING directory (`tools/`) | **BUILT** | root is the repo, not `hooks/`; fixture `tools/turn_classifier.py` |
| N6 the rule copied INLINE into a hook | **BUILT** | behavioural ceiling catches it with no module constant; probe case N6 |
| rec: "keep the 4 names as a FLOOR, do not delete them" | **BUILT** | `_TWIN_CONSTANTS`/`_TWIN_HELPERS`; load-bearing - the behavioural rule alone misses control C2 |
| rec: "make the glob recursive over the repo rather than `hooks/*.py`" | **BUILT** | `twin_offenders(root=repo)` |
| measured exemption cost "2 of 36 files" | **BUILT, and corrected** | only 1 of the 2 was still needed; `tools/compare_delivery_gate.py` no longer touches the vocabulary. Dead entry removed AND a used-check added, so an exemption that stops being needed is now reported |
| F-L8 - the X6 residual (2 killing fixtures supplied) | **SCHEDULED** | plan row, phase 4 |

**Measured result: 5/11 -> 11/11 (controls 5/5, novels 0/6 -> 6/6).**

## `hooks/duplicate_registration_check.py` - 7 blind shapes

| source item | status | where |
|---|---|---|
| 1. `.js` hook wired twice | **BUILT** | `SCRIPT_EXTS` reused from `hook_health_check`; fixture `notify.js`; mutation B3a |
| 2. `.ps1` wired twice (`pwsh -File` + `powershell -File`) | **BUILT** | fixture `notify.ps1`; drove the invocation-key design (launcher flags must not differentiate) |
| 3. `.sh` wired twice (`bash` + `sh`) | **BUILT** | was working-by-accident via `SCRIPT_EXTS` with NO fixture until this ledger was written; fixture `notify.sh` added |
| 4. same hook wired twice as a MODULE (`python -m`) | **BUILT** | normalised to a path in `_path_tokens`; mutation B3b |
| 5. dispatcher whose FILENAME lacks "dispatcher" | **BUILT** | filename test removed, AST asked instead; mutation B3c |
| 6. dispatcher whose list is named `MODULES`/`PIPELINE` not `HOOKS` | **BUILT** | any ALL-CAPS module-level sequence; mutation B3d |
| **7. plugin `hooks.json` files not in `settings_layers()`** | **SCHEDULED - plan row B3-P, phase 1** | **THE GAP THIS AUDIT FOUND.** Never written into the plan at all, so no defer-grep could have surfaced it. Re-measured today: **7 plugin `hooks.json` exist, 6 declare real events**; `settings_layers()` returns 4 paths, none of them a plugin |
| counter-evidence: guard is fail-CLOSED and noisy on the event/matcher axis (cases X1, X2) | **BUILT** | this was the audit's fairness note, and fixing shape 1 made it LIVE - see B3-FP. Identity is now (script + args + event + matcher) |
| "LIVE EXPOSURE: 21 of 30 entries extract nothing" | **BUILT + verified** | all 30 now extract; live config re-run reports clean |

## `hooks/capped_report.py` - the third guard

| source item | status | where |
|---|---|---|
| `slicing_offenders` fails open; 47 -> 111 shapes and still growing | **SCHEDULED, NOT STARTED** | plan row B1, 4 HIGH, with a design brief recording why the naive inverse rule is insufficient and the measured 31/96 predecessor floor |

## Not gaps - explicitly checked and excluded

- The 111-spelling taxonomy in `p14_cluster1_evidence.md` is **test fixture material for B1**, not
  separate deliverable content; it survives as `tests/cap_spelling_corpus.py` (125 entries).
- The reverted detector's internals (`_body_changes_length`, `_callee_aliases`, `_TAXONOMY`, ...)
  describe code that no longer exists. The plan already retired those rows and kept the CLASSES
  as C1-NEW acceptance criteria - correct, and re-confirmed here.

## Verdict

The B5 guard-audit source is **fully reconciled**: 6 of 7 `duplicate_registration_check` shapes
and all 6 `transcript_util` shapes BUILT, one shape (plugin layers) newly SCHEDULED, one guard
(`capped_report`) SCHEDULED with a design brief. **Zero items remain with no home.**
