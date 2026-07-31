# Next session start prompt

**Start here: `docs/V131_REVIEW_PLAN.md`, sections P11 and P12.** P1-P10 are done. P11 holds
48 findings that were produced by the review runs but never adjudicated. That is the work.

## What happened on 2026-07-31

All 38 open plan items (P1-P6) shipped, plus items 40-45 found during the pass, plus three
further adversarial passes (P8, P9, P10) and their fixes. 19 selftests, 30/30 integration
scenarios, 51 mutations, CI green on 12 jobs (13 from the next push - a mutation-harness job
was added).

The close audit then found the thing that matters most: **the three workflow scripts written
on 2026-07-30/31 capped refutation at four findings per lens (`.slice(0, 4)`)**, so each run
made exactly 16 refuter calls no matter how many findings its lenses produced. Across the
four runs, 135 findings were produced and **48 were never adjudicated** - neither confirmed
nor refuted. The original v1.3.0 run had no cap (39 produced, 39 adjudicated), so this was a
regression introduced in the review harness itself.

Full accounting: `docs/audits/coverage_ledger_2026-07-31.md`.

## The prompt

```
unbluff v1.3.1 - P11 pass. Read Downloads/unbluff/docs/V131_REVIEW_PLAN.md sections P11 and
P12 FIRST, then `git status -sb`. Repo is at main == origin, clean, CI green.

STATE. Four adversarial review runs have produced 135 findings. 87 were adjudicated: fixed with
a mutation-verified regression test, or refuted with a written justification in the plan.
48 were NEVER adjudicated - neither confirmed nor refuted - because the three workflow scripts
written on 2026-07-30/31 capped refutation at four findings per lens (`.slice(0, 4)`), giving
exactly 16 refuter calls per run regardless of how many findings the lenses found. The original
v1.3.0 run had no cap (39 produced, 39 adjudicated), so this was a regression in the review
harness itself. Full ledger: docs/audits/coverage_ledger_2026-07-31.md.

DO THIS FIRST, before any fixing: remove the `.slice(0, 4)` cap, and make any cap in a review
harness print what it dropped. That omission is why 48 findings were lost, and it is the same
denominator failure the plan documents four times over.

THEN adjudicate the P11 findings. They are CANDIDATES, not confirmed defects - the prior passes
refuted roughly 6%, which is not zero. Refute each properly before fixing it.

Start with the two caused by this session's own fixes, because they are live:
- check_review_freshness.units() omits tools/ and tests/. VERIFIED: the ledger holds recorded
  reviews for tools/mutation_check.py, tools/check_review_freshness.py and
  tests/test_integration.py that the gate never asks about, so --record for them is a no-op and
  --release can pass while the evidence tooling is unreviewed. FOURTH instance of the
  hardcoded-roster class.
- pre_push_gate HIGH_FREQUENCY_HOOKS excludes reference-transaction from --install-global, which
  silently stops repo-local hooks of that name firing - the exact effect this file's own comment
  at :318 forbids.

Then the HIGH: meta_audit_on_stop.count_unpushed returns 0 for both "nothing unpushed" and "no
upstream", so a never-pushed branch with unpushed commits is byte-identical to a clean tree.
The meta_audit cluster is the densest in P11 (5 findings) - do it as one unit.

AFTER P11 completes, and not before (it will move code in both files and invalidate mutation
anchors): split hooks/pre_push_gate.py (1038 lines) and hooks/fast_test_on_stop.py (821) back
under the 800-line rule by moving each selftest() into a sibling *_selftest.py.

WORKING RULES, non-negotiable:
- Regression test FIRST. Write it, watch it fail, then fix.
- Mutation-test every fix (`python tools/mutation_check.py`). A SURVIVED verdict means the test
  is decorative. The harness now runs the unmutated baseline first - trust a HARNESS ERROR about
  a red baseline, it means the test proves nothing in that environment.
- After each fix, grep for the twin. Four separate hardcoded rosters have been found this way.
  Assume a fifth.
- Push and read CI. This machine is Windows; CI is the only Unix check, and it now runs the
  mutation harness on ubuntu (so posix-only mutation #30 executes there for the first time).
- Any cap, sample or top-N you introduce MUST print its denominator.
- If context pressure would make you read less, sample less, or cap a fan-out: FLAG IT AND STOP.
  Do not deliver a smaller version of the job quietly.

DEFINITION OF DONE: all 48 P11 findings adjudicated (fixed with a mutation-verified test, or
refuted with a written justification in the plan); suite + integration + mutations green; CI
green on all 13 jobs; and `python tools/check_review_freshness.py --release` reporting an honest
denominator that includes tools/ and tests/.
```
