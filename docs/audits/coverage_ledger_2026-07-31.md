# Coverage ledger - every adversarial-review finding vs the plan

Generated 2026-07-31 by the completeness-audit close skill, because the plan reported only
the ADJUDICATED subset of findings as though it were the whole.

| run | scope | raw produced | reached a refuter | never adjudicated |
|---|---|---|---|---|
| `wf_b5ea865a-a33` | v1.3.0 (P1-P7) | 39 | 39 | **0** |
| `wf_c2218ef3-6d2` | pass 2 (P8) | 25 | 16 | **9** |
| `wf_3355090a-59e` | item 45 (P9) | 43 | 16 | **27** |
| `wf_a51d3013-715` | pass 3 (P10) | 28 | 16 | **12** |
| **total** | | **135** | **87** | **48** |

**The v1.3.0 run had NO cap** (39 produced, 39 adjudicated). The `.slice(0, 4)` per-lens
cap was introduced in the three workflow scripts written on 2026-07-30/31 - a regression in
the review harness itself, not a pre-existing limitation.

## Completeness verdict

Findings PRODUCED but neither adjudicated NOR written into the plan: **0**.

**Zero.** Every one of the 135 findings across all four runs is either FIXED with a
mutation-verified regression test, REFUTED with a written justification in the plan's
refuted section, or listed as OPEN in P11. The plan is a true completeness ledger.

Note the distinction this ledger exists to preserve: *recorded* is not *adjudicated*. The
48 unadjudicated findings are all written down, but none has been refuted or confirmed.
They are candidates, and P11 says so.
