# Coverage ledger - 2026-08-23 (design, not only code)

**Sources enumerated:** `SECURITY.md`'s stated execution model and its "what unbluff does not do"
claims; `docs/PLAN.md`'s gate-2 design promise; the 7 standing checks.
**Reconciled against:** the code and the gates that would go red if a claim stopped being true.

The question this pass asks is deliberately not "does the code work" - it is **"does the DESIGN
say anything the code never mentions"**. That is the gap a grep of the plan can never find.

## A. SECURITY.md - execution model

| # | source claim | status | carrier |
|---|---|---|---|
| 1 | resolution order: `.claude/fast-test.cmd` -> `package.json scripts.test` -> pytest | **BUILT** | `fast_test_on_stop.detect()`; fast-test detection selftest, 7 decline + 16 accept shapes |
| 2 | steps 2 and 3 execute repository code | **BUILT** (statement of fact) | `looks_like_pytest_project` accepts a bare root `conftest.py` |
| 3 | discloses the `scripts.test` BODY, not the wrapper | **BUILT** | `fast_test_disclosure.disclosure()`; selftest asserts body present AND wrapper absent |
| 4 | discloses the `conftest.py` files pytest will import | **BUILT** | same; root + `tests/` asserted |
| 5 | notice keyed on disclosed CONTENT, not the project | **BUILT** | `_marker_path()`; selftest asserts the key CHANGES when `scripts.test` changes |
| 6 | a cap on disclosed conftests announces what it hid | **BUILT** | routed through `capped_report`; asserted with 15 files |
| 7 | control it via `.claude/fast-test.cmd` or removing the Stop hook | **BUILT** (override branch) / narrative (hook removal) | override precedence pinned |
| 8 | push-time auto-detect OFF unless opted in | **BUILT** | `repo_opted_in()`; scenario 15b |
| 9 | `--install` is the opt-in and restores auto-detect | **BUILT** | scenario 15b second half |
| 10 | a FOREIGN `pre-push` (husky/lefthook) is not opt-in | **BUILT** | scenario 15c - exists only because a mutation survived |
| 11 | declining says so and ALLOWS the push | **BUILT** | scenario 15 widened to both no-command paths |
| 12 | `git push --no-verify` bypasses | **FINALIZED EXCLUSION** | git's own behaviour, not ours to gate |
| 13 | private advisory reporting URL | **BUILT** (verified) | URL path matches `origin` = `AmmarBibi/unbluff` |

## B. SECURITY.md - "what unbluff does not do"

| # | source claim | status | carrier |
|---|---|---|---|
| 14 | no network / telemetry | **BUILT** | `tools/check_no_network.py`, 59 files / 0 reaches, 2 negative controls |
| 15 | no writes outside the repo and `~/.claude/hooks/state/` | **GAP -> SCHEDULED #43** | **nothing**; grep across `tools/ hooks/ tests/` finds no check |
| 16 | no credential access (keychain, env secrets, git credentials) | **GAP -> SCHEDULED #43** | **nothing** |

### The finding

Two of the three trust claims in a security document are enforced by nothing, and **both were
written by me today**, one file away from the gate that exists precisely because the README's
"no network" badge was once enforced by nothing. An unenforced claim listed beside an enforced one
borrows its credibility, which is the specific dishonesty this repository is named after.

Interim fix applied: `SECURITY.md` now splits the list into ENFORCED and ASSERTED-NOT-ENFORCED and
says plainly that the second pair is the author's word. Real fix scheduled as #43.

## C. Gate-2 design promise vs implementation

| promise in `docs/PLAN.md` row 2 | status |
|---|---|
| "one-time per-repo stderr notice **naming the exact command**" | **DELIBERATELY NOT BUILT AS WRITTEN.** The exact commands name nothing untrusted. Implemented as body-disclosure instead, and the row was rewritten to say so rather than left claiming a thing that was not done. |
| no auto-detect under `--install-global` | BUILT |
| ship `SECURITY.md` | BUILT |

## D. The 7 standing checks, as sources

| check | honoured this session? | evidence |
|---|---|---|
| 1 new instance of the fixed class | **FIRED TWICE, both caught** | push-gate README claim (gate 3); ungated SECURITY.md claims (this pass) |
| 2 what would make this control unable to fire | yes | mutation probes on all four new units, 16/16 killed overall |
| 3 number derived just now | **FAILED ONCE, caught** | "58 files" stale in two docs; now dated |
| 4 is this surface LIVE | yes | disclosure demonstrated end-to-end on two synthetic repos |
| 5 never edit while a gate is in flight | yes | no edits during any suite/probe run |
| 6 a probe not shown to fail is not a probe | yes | every new assertion mutation-probed before being trusted |
| 7 an agent's finding is a hypothesis | n/a | no agents used this session |

## Verification

Re-ran after the edits: `check_no_network` rc 0 (59 files), `check_readme_fresh` rc 0 (all three
cardinalities), `plan_defer_guard --selftest` rc 0.

## Deviations

1. **No fan-out.** The skill prescribes one pass per source section. Sources here are one
   190-line plan and a 100-line SECURITY.md; a single reader covers them, and a Workflow would
   need the budget check this session has not run.
2. **Rows 14-16 were reconciled by grep for an absent gate**, which proves absence of a *named*
   check, not absence of any enforcement. A gate under a name I did not think to grep for would
   read as a GAP here. The claim is "no check found", not "no check exists".
3. **A, C and D were reconciled by the author of the code.** Independent verification is gate 9.
