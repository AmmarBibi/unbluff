# Meta-review - 2026-08-23

**Target:** this session, `d89e3dc..a9b5cc6` plus close edits. Gates 1, 2, 3, 5, 7 (local), 8.

## CHECK 1 - parked-but-unscheduled

Grep `PARK|DEFER|TODO|OPTIONAL|candidate|later` over `docs/PLAN.md`: **2 hits, both false
positives** - "treats as OPTIONAL and drops from the install roster" (naming a mechanism) and
"a later one that can read the file" (describing fall-through).

Worth recording that this grep and completeness STEP 1's returned **different** hits and neither
found a `park`. Two markers sets, two passes, zero real defers - which is the outcome the two
being different is supposed to buy.

**Real finding came from the completeness pass, not this grep:** criterion 1 was declared
"survives as a post-release issue" and appeared in no roster. Scheduled as #6/#28.

## CHECK 2 - instance-only fixes (durability)

Every fix this session, asked "instance, or mechanism?":

| fix | instance or mechanism | verdict |
|---|---|---|
| gate 1 baseline conflict | re-measured the tree instead of picking a side | mechanism |
| gate 2 disclosure | new module + selftest + 6 mutations | mechanism |
| gate 2 opt-in | derived from the shim's presence, no new state | mechanism |
| gate 3 README count | **would have been instance-only** - fixed by deriving count AND roster in `check_readme_fresh` | mechanism |
| gate 5 PDF | emptiness check + distinguished diagnosis + PDF-1 pin | mechanism |
| gate 8 stale shim | fixed the CLASS (any missing path, not just uninstall) | mechanism |
| "58 files" drift | **instance fix + #42 filed** - the number is corrected and dated, but nothing gates plan/changelog cardinalities | **instance-only, scheduled** |
| SECURITY.md ungated claims | **labelled honestly + #43 filed** - no gate built | **instance-only, scheduled** |
| ledger pollution | `UNBLUFF_LEDGER_OFF` + selftest + mutation | mechanism (#44 closed) |

Two instance-only fixes remain, both scheduled with the mechanism named. That is the honest
state, not a clean sweep.

## CHECK 3 - optimization / structure

| file | lines | limit 800 |
|---|---|---|
| `hooks/pre_push_gate_selftest.py` | 1192 | offender, **worst in repo** |
| `hooks/fast_test_on_stop_selftest.py` | 1003 | offender |
| `install.py` | 927 | offender (`selftest()` is 299 of it) |
| `hooks/duplicate_registration_check.py` | 858 | offender |
| `hooks/fast_test_on_stop.py` | 851 | offender |
| `hooks/pre_push_gate.py` | **792** | **8 lines of headroom** |

The ratchet fired correctly three times and was re-recorded twice with stated reasons. It also
**steered architecture**: gate 8's test went into `tests/test_integration.py` partly because its
natural home had no room. That is the signal, filed as #41. Two splits with in-repo precedent are
available and should precede the next feature.

No duplication, dead code or unbounded work found in the new modules; `fast_test_disclosure.py`
is 335 lines with one bounded walk (depth 2, pruned, cap routed through `capped_report`).

## CHECK 4 - missing / wrong (READ THE LEDGER)

`docs/audits/gate_runs.json`, read not reconstructed:

| gate | latest | result |
|---|---|---|
| `file_size` | 2026-08-23T15:11 | PASS |
| `ship_bar` | 2026-08-23T15:11 | PASS |
| `run_selftests` | 2026-08-23T15:11 | FAIL (hook-provenance, #39) |
| `integration` | 2026-08-23T15:09:18 | PASS 34/34 |
| `mutation_sweep_filtered` | 2026-08-22T14:27 | PASS |
| **`mutation_sweep`** | **2026-08-20T17:28** | **FAIL - now 10 commits and 3 days stale** |
| `false_alarm_scorer` | 2026-08-20T13:46 | PASS |

**This check earned its keep and produced the session's best finding.** The `integration` row
read **FAIL 33/34** when I opened the ledger - from a MUTATED tree, written by my own shim probe
eight minutes after the real tree passed 34/34. Nothing in the code or the plan showed it. Had
the release proceeded on the ledger, it would have blocked on a failure that did not exist; had
it proceeded ignoring the ledger, the ledger would have been worthless. Fixed at the mechanism
(#44, closed) and the row corrected by a clean re-run.

**Still outstanding and it is gate 10:** no clean full mutation sweep exists for any recent HEAD.
The last is 2026-08-20T17:28:15Z, FAIL on 2 harness errors, now 10 commits behind.

## CHECK 5 - improvements for a better outcome

1. **Make `--install-global`'s shim path relative to a stable location** rather than the clone,
   or have it re-resolve. #30's loud-but-open failure is the right floor, not the ceiling.
2. **`readme-fresh` is becoming the repo's cardinality gate.** Generalise it to any document
   (#42) rather than adding a fourth bespoke check.
3. **The disclosure could show a diff** when a repo's `scripts.test` changes, rather than
   re-printing the whole disclosure - the reader's question is "what changed".
4. **`UNBLUFF_LEDGER_OFF` should probably be automatic** for any process whose tree is dirty
   versus HEAD, rather than opt-in by the probe author.

## CHECK 6 - mechanism health

- Suite 39/40, real rc 1 captured directly; the one failure is #39's worktree artifact and is
  green in a plain checkout (derived both ways).
- `plan_defer_guard --selftest` rc 0, `hook_health_check` OK in-suite, `check_no_network` rc 0.
- **Exactly one canonical order** - `docs/PLAN.md`. `NEXT_SESSION_PROMPT.md` remains superseded
  (#10) and was not resurrected.
- The plan is 190 lines against its own stated two-page cap. **It is at the edge**: five new rows
  (#39-#44) landed today. The cap is a real rule here and the next session should prune, not add.

## End-of-turn finalize

`docs/PLAN.md`'s single order is refreshed: gates 1, 2, 3, 5, 7(local), 8 marked DONE with
evidence; 4 and 6 already DONE; 9, 10, 11 outstanding and in priority. #39-#44 are all in Phase 2
with homes, #40 and #44 marked CLOSED. Criterion 1 (#6/#28) added to the roster it was missing
from.

## Deviations

1. **No fresh held-out probe** for CHECK 4's product level, as the skill prefers. The gates were
   re-run rather than a new independent probe written.
2. **Self-review.** Every finding here came from running a checklist against my own work.
   Gate 9 is the independent pass and has NOT run; nothing in this document substitutes for it.
3. **CHECK 5's items are unscheduled by design** - the skill says list them and let the user
   pick. They are not in the plan and would be lost if the user does not act on them.
