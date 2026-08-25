# Source-coverage ledger - 2026-08-25

**Run against the DESIGN, not only the code**, which is the whole point of this pass: a claim can
be true in prose, absent from the code, and invisible to every test that reads the code.

**Sources enumerated:** `.claude/pre-push.cmd`, `run_selftests.py`'s `MACHINE_STATE` contract,
`tools/check_selftest_isolation.py`'s three stated questions, the M10 fix in
`hooks/piped_gate_guard.py`, and `SECURITY.md`'s trust claims.

## Reconciliation

| # | design claim | status | carrier |
|---|---|---|---|
| 1 | `check_selftest_isolation` DERIVES its population from the AST | **BUILT** | `mutating_verbs_in()` + selftest control asserting a read-only caller stays OUT |
| 2 | it verifies the scrub is REACHED, not merely present | **BUILT** | `_scrub_reached()` + control asserting an unscrubbed fixture is flagged |
| 3 | inline fallbacks must match `GIT_REDIRECT_VARS` exactly | **BUILT** | `_pops_redirect_vars()` + control asserting a 2-of-7 fallback is caught |
| 4 | `--code-only` excludes machine-state gates from the VERDICT only | **BUILT** | `MACHINE_STATE` + 3 assertions + a live disarm probe |
| 5 | `--code-only` is "deliberately NOT the default" | **GAP -> SCHEDULED item 8** | nothing. See the completeness artifact |
| 6 | a commented protector does not protect (M10) | **BUILT** | `strip_comments()` + 5 selftest cases + over-strip control |
| 7 | PG-QUOTED known limit is deliberate, not an oversight | **BUILT** | pinned assertion in the direction it behaves + docstring reason |
| 8 | `SECURITY.md`: "no network" | **BUILT** | `tools/check_no_network.py` |
| 9 | `SECURITY.md`: "no writes outside", "no credential access" | **FINALIZED-DISCLOSED** | labelled *"Asserted but NOT yet enforced - checked by nobody"*; re-verified intact |

## GAP FOUND - and it is this repo's signature concern

**Every guard this session built is enforced by its own selftest, and NONE is registered as a
mutation entry.** Derived, not assumed:

```
grep -c 'strip_comments|scrub_environ|PG-QUOTED'  tools/mutation_entries_a.py -> 0
                                                  tools/mutation_entries_b.py -> 0
```

`tools/mutation_check.py` exists because *"the suite passes"* was twice read as *"the suite asks
the right questions"*, and its own docstring says a test that stays green when you delete the code
it covers is decorative. I ran the controls **by hand** this session and they bit - neutering
`strip_comments` turned exactly the two M10 cases red and named them; neutering the scrub call was
probed. **A hand-run control proves the test bites today. It does not survive into the sweep.** A
refactor six months from now that disarms these is caught by nothing.

**Scheduled as item 9**, blocked on the same ordering as item 7: a mutation entry is only
meaningful once a clean full sweep exists to run it, and the sweep is stale and blocked behind
item 2's pull. Order: **item 2's pull -> clean sweep -> items 7 and 9 together.**

## Verify

No optional-forever language in the plan (see the completeness artifact's STEP 1). Every gap above
has a numbered home. Nothing in this ledger is marked done on the strength of prose alone.
