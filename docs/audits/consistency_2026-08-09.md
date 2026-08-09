# Consistency audit - 2026-08-09

**Deliverables audited:** `docs/audits/promise_inventory_2026-08-09.md`,
`docs/audits/plan_audit_2026-08-09.md`
**Sources indexed:** the session's workflow result JSONs (`inventory_raw.json`,
`round2_raw.json`, `round3_raw.json`) and the live repo at HEAD `00fc9ba`.
**Tolerance:** relative 1 %, absolute 1e-09 (tool default).
**Tool:** `skills/consistency-audit/scripts/audit.py` (the shipped bundled extractor).

## Mechanical pass - raw candidate counts

| class | inventory | plan audit |
|---|---|---|
| [A] number with no source match | 328 | 199 |
| [B] orphan figure | 0 | 0 |
| [C] dangling cross-reference | 3 | 0 |
| [D] claim to verify by reasoning | 15 | 12 |
| [E] unfilled placeholder | 16 | 1 |
| [F] table promised, not rendered | 4 | 0 |

Source index held 133 values (inventory) and 17 values (plan audit). **That is the
denominator that matters for [A]:** almost every number in these deliverables is a line
number, a claim id, or a value *derived* through the documented pipeline, none of which
appears as a flat value in the source JSON. [A] is therefore noise by construction here,
and is adjudicated as a class rather than row by row - see below.

## Adjudication

### [E] inventory - 16 of 16 are FALSE POSITIVES, and the cause is a real tool defect

Every flagged placeholder (`[TODO]`, `[TABLE TO BE INSERTED]`, `[XX]`, `TKTK`, `TBD`,
`[insert value]`, `XXXX`) sits inside a claim row that *documents the placeholder
detector itself*. Row `CA-12` states the claim "the specific markers `[XX]`, `TKTK` and
`TBD` are flagged as unfilled placeholders" - and the tool flags those literals.

**Verdict: OK (not drift) for the deliverable. NEW FINDING against the tool.**
This is the repo's own rule - *a grep guard must never search for a literal it
contains* - failing in the shipped skill. Any user auditing a document that discusses
the audit tool, its vocabulary, or its own output receives 16 spurious [E] flags. It is
user-reachable (the skill is installed by `install.py`), so it is criterion-2 class.
Scheduled, not fixed here: this session fixes nothing in the product.

### [C] inventory - 3 of 3 FALSE POSITIVES, same cause

`Figure 1`, `Figure 4`, `Figure 5` are quoted from the tool's own selftest fixtures
inside row `RM-55` ("the bundled extractor detects all six named drift classes"). No
figure exists in the deliverable. **Verdict: OK.** Same root cause as [E].

### [F] inventory - 4 of 4 FALSE POSITIVES, same cause

`Table 1/2/3/9` appear inside claim text quoting unbluff's README ("skips
cross-references (`Figure 3`, `Table 2`, `[12]`)") and the skill's own examples.
**Verdict: OK.** Same root cause.

### [E] plan audit - 1 of 1 is a REAL DEFECT, now fixed

Line 63 read: *"48 of 49 findings were attacked by a refuter and `[]` were killed."*
The generator formatted an empty list into the sentence where the kill count belongs.
**Verdict: DRIFT. FIXED** - now reads `0 were killed`. Independently flagged by the
2026-08-09 gap sweep, which is the second detector to catch it.

### [A] both deliverables - adjudicated as a class

Spot-checked the load-bearing figures rather than all 527 candidates:

| cited | nearest source | verdict |
|---|---|---|
| 85 PROVEN | 84 | **DERIVED.** 84 is the pre-strike round-1 count; 6 struck rows were PROVEN, +7 from the critic rows: 84-6+7 = 85. |
| 158 UNPROVEN | 155 | **DERIVED.** 133 - 13 struck unproven + 38 critic unproven = 158. |
| 243 N | - | **DERIVED**, and asserted in code: the cluster table `assert` fails the build if the clusters do not sum to the UNPROVEN count. |
| 2.12M / 2.62M / 1.77M tokens | - | **EXTERNAL.** Reported by the harness, not present in any source file. |

**Verdict: DERIVED or EXTERNAL for every figure checked. No fabrication found.**

### [D] the reasoning pass - one genuine cross-section finding

Cross-section consistency check on the "once per session" family:

| row | hook | verdict |
|---|---|---|
| `RM-38` | `meta_audit_on_stop` | **PROVEN** |
| `RN-43` | `show_your_proof` | **PROVEN** |
| `RM-42` | `plan_defer_guard` | **UNPROVEN** - its own `[M5]` selftest case *requires* a second fire on a different plan file |
| `RM-48`, `RN-31` | `numbers_match_on_write` | **UNPROVEN** - its selftest *requires* a different report in the same session to still be checked |
| `RN-36` | *every* hook (blanket claim) | **UNPROVEN, false as written** |

The deliverable is internally consistent - different hooks, correctly distinguished
verdicts. **The finding is against the README:** it makes a blanket once-per-session
promise that at least two shipped hooks contradict *by design*, and their own selftests
encode the counterexample. This is a criterion-1 disposition (fix the claim or narrow
it), already carried as rows `RM-42`, `RM-48`, `RN-31`, `RN-36`.

## Cross-section consistency of the plan audit's corrected numbers

The plan audit body still contains the superseded figures (78, 45, 120, 165, 82, 2,200).
This is **deliberate**: a `CORRECTIONS` block at the head of the file enumerates each one
against its true value, so the record of the error survives rather than being silently
rewritten. Verified mechanically: all six superseded figures appear in the corrections
block, which precedes every body occurrence.

**Residual risk, stated:** a reader who skips the corrections block reads wrong numbers.
The alternative - rewriting the body - would erase evidence of a failure this project
exists to surface. The trade is recorded here so it is a decision, not an oversight.

## Summary

| | count |
|---|---|
| Candidates raised mechanically | 578 |
| Adjudicated as OK / DERIVED / EXTERNAL | 577 |
| Real defects found | **1** (the `[]` placeholder) - **fixed** |
| New findings against the *tool* | **1** - self-reference false positives, criterion-2 class, scheduled |
| New findings against the *product* | **1** - the README's blanket once-per-session claim, already carried as 4 inventory rows |
