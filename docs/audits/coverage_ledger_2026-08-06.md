# Coverage ledger - 2026-08-06

Supersedes `coverage_ledger_2026-08-05.md` for the items touched this session. That ledger
reconciled the B5 guard audit; this one reconciles what the 2026-08-06 session built, plus the
two source-coverage gaps it found.

**Why this file exists at all:** it was nearly missed. `source-coverage` STEP 4 and
`completeness-audit` STEP 3 both require the ledger artifact, and this session found SC1/SC2 and
scheduled them in the plan *without* refreshing the ledger. The skills were run and produced
real findings, but their procedures were only partly completed. Caught by being asked to verify
rather than assert - which is the same lesson the session's three best findings came from.

A source item is "done" only when BUILT, SCHEDULED with a plan row, or a FINALIZED EXCLUSION
with a written justification.

## Source: `docs/audits/p14_audit_findings.md` + the meta-review / source-coverage passes

| item | status | where |
|---|---|---|
| M1 - a mutation anchor can be silently disarmed; only a full sweep notices | **BUILT** | `tools/check_mutation_anchors.py`, AUX gate 26. Commit `6807121`. Mutations M1a/M1b |
| M-M12 - anchor UNIQUENESS (`replace(..., 1)` mutates the FIRST match) | **SCHEDULED** | plan row M-M12, phase 2. It was previously covered only by being an unnamed member of work-order row 2's nine; asserted as "scheduled" by shipped code comments with no row. Live instance measured: `duplicate_registration_check #B3a` matches 2x |
| B3-P - `settings_layers()` blind to plugin `hooks.json` | **BUILT** | `hooks/hook_layers.py`. Commit `cb1b600`. Mutations B3Pa/B3Pb/B3Pc |
| B3-P premise - "7 plugin hooks.json, 6 declare real events" | **CORRECTED, not built to** | only 2 plugins are ENABLED and only 1 ships hooks; building to the stated premise would have produced a false-alarm guard (B3-FP repeating). Correction recorded in the B3-P row |
| `~/.claude/hooks/hooks.json` as a missed layer | **FINALIZED EXCLUSION** | it is NOT a layer Claude Code merges: 0 of 30 command strings shared with `settings.json`, and `hook_health_check` independently reports exactly settings.json's 30. It is a source template installed INTO settings.json; reading it would double-count every ECC hook |
| `score_corpus` double-counted every negative control | **BUILT** | `split_corpus()` + `--selftest`, promoted to AUX gate `corpus-scorer`. Commit `7d789c3`. Mutation #B1s |
| **SC1** - the measurement-tool exemption is a HOLE, not a one-off | **SCHEDULED** | plan row SC1, phase 2. 3 tools remain in `NOT_A_GATE` with no selftest; 2 of them exist to produce numbers quoted in this plan. `score_corpus` was only the first instance - fixing it alone was an INSTANCE fix |
| **SC2** - `mutation_check` leaks scratch trees and swallows the reason | **SCHEDULED** | plan row SC2, phase 4. Measured: 22 orphaned `unbluff-mut-*` dirs, 16 MB, Jul 31 -> Aug 5, via `rmtree(ignore_errors=True)` |
| MR-a - the anchor gate could be fully disarmed with every test green | **BUILT** | pure `verdict()` + every branch asserted. Commit `e0f730c`. Mutation #MRa. Re-probed after the fix: disarming now goes RED |
| MR-b - `hook_layers` merged every on-disk copy of one enabled plugin | **BUILT** | one deterministic copy merged, ambiguity REPORTED. Commit `e0f730c`. Mutation #MRb |
| C1-NEW discrimination rule | **DESIGNED, NOT BUILT** | plan section "C1-NEW discrimination design, 2026-08-06". Commit `bec1821`. The detector is the next unit |
| B1 corpus entries derived from the PREDECESSOR's capabilities | **SCHEDULED, NOT STARTED** | owed regardless of score; only the 14 scalar-suffix entries are baseline-verified, so any score above 31/96 on today's corpus is not yet real progress |
| B1 exemption roster must report an exemption that stops being needed | **SCHEDULED, NOT STARTED** | two negative controls are structurally IDENTICAL to true positives, so the roster stays load-bearing. `transcript_util`'s used-check is the model |
| `enabledPlugins` at PROJECT scope | **OPEN QUESTION, recorded** | `hook_layers` reads user scope only; probed to yield 0 layers. Errs toward MISSING a layer, never inventing one - the safe direction - but B3-P is not complete until confirmed |

## Not gaps - checked and excluded

- The 2 posix-only mutations (`pre_push_gate #30`, `fast_test_on_stop #D10c`) are not runnable on
  this machine and are proven by the other platform's CI job, not by this one.
- The 14 HARNESS ERRORs seen mid-session were wall-clock budget failures under 97% CPU (A8), not
  defects. Re-run on a quiet box: all CAUGHT. A8 is now promoted to phase 0 as a blocker on the
  verification loop itself.

## Not covered by any audit this session - stated, not hidden

**The three files written this session have never been adversarially reviewed:**
`hooks/hook_layers.py`, `tools/check_mutation_anchors.py`, `tools/score_corpus.py`
(`check_review_freshness` reports them UNREVIEWED, 4/43 units reviewed).

This is a CONSTRAINT, not an oversight: the session ran under "do not call the Agent tool and do
not use workflows unless the user requested it", which excludes `code-reviewer`,
`python-reviewer`, `silent-failure-hunter` (agents) and `adversarial-review` (Workflow fan-out).
The project's own `code-review.md` names "after writing or modifying code" as a MANDATORY review
trigger, so this is a real deviation from the standing rule, made for a stated reason and
recorded here so it is a decision rather than a gap. **UNREVIEWED is a different bucket from the
UNRESOLVED that `--release` gates on**, so it does not block on its own - but three new files
carrying guard logic is exactly the material `adversarial-review` exists for, and it is worth
spending on before v1.3.1 ships.

## Verdict

Everything this session found has a home: 6 BUILT, 5 SCHEDULED with plan rows, 1 FINALIZED
EXCLUSION with justification, 1 DESIGNED, 1 OPEN QUESTION recorded. **Zero items remain with no
home.** The unreviewed-code deviation is recorded above rather than left implicit.
