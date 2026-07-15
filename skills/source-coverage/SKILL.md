---
name: source-coverage
description: Verify a plan or deliverable actually covers 100% of its authoritative source(s), and catch the gap a grep never can - content that was NEVER written into the plan. Run when a plan is created or rebuilt, at milestones, before declaring any source or the project "done", and whenever someone asks "did we forget anything / is this complete". The reasoning half of unbluff's completeness story: the plan-defer-guard hook catches optional-forever language the plan MENTIONS; this catches source content the plan does NOT mention.
---

# Source-Coverage Audit

A plan drifts from 100% coverage in two ways. A hook can only catch one of them; this skill catches the other - the dangerous one.

- **What a hook can catch:** optional-forever language the plan *contains* (`-> park`, `on demand`, ...). A grep finds it - that is the `plan-defer-guard` hook.
- **What only this skill can catch:** source content the plan **never mentions at all**. A grep cannot find what is not written down. A plan can confidently assert "everything is covered" while an entire family of the source's requirements was simply never catalogued. The only way to find it is to read the *source of truth* and reconcile it against the plan - not to re-read your own plan.

Motivating example (real): a plan asserted "essentially all of Section 6 is built" and every reviewer of the plan agreed - because the plan never named the refining-emissions methods it had missed. A source-coverage pass over the actual specification surfaced ~40 uncovered items in one run. No hook, and no re-reading of the plan, would ever have found them.

## When to run
Plan created / rebuilt; at milestones or after each unit ships; before declaring any source or the whole project "done"; whenever asked "is this complete / did we forget anything".

## Procedure

### 1. Name the sources
List the authoritative source(s) the deliverable must fully encode - specs, standards, PDFs, API references, requirement docs. Note their locations. "Done" is defined *against these*, not against the plan.

### 2. Enumerate the source, not the plan
Read each source (or split a large one by section) and enumerate every **testable / deliverable-bearing** item it contains: table, equation, method, factor, default, requirement, invariant, endpoint, rule. For a large source, do this as a fan-out - one pass per section - so nothing is skimmed. This step reads the SOURCE; it must not be biased by what the plan already says.

### 3. Reconcile - built | scheduled | excluded
For each enumerated source item, assign exactly one status:
- **BUILT** - implemented (name the module/function/test).
- **SCHEDULED** - a real plan item exists for it (name it).
- **FINALIZED EXCLUSION** - deliberately out of scope, with a written justification (e.g. "value not present in the source corpus", "process artifact, not source content").

Anything that maps to NONE of these is a **gap** the plan silently missed. Be conservative: a real item produces or supports a deliverable output; ignore pure narrative, references, and worked examples (those are fixtures for a method, not separate items). Flag "confirm-don't-assume" cases - e.g. a method equation that must ship *with* a scheduled data table, not as a data-only stub.

### 4. Schedule + ledger
- Add every gap to the plan in materiality order (each with a home). Materiality decides ORDER, never WHETHER an item ships.
- Write or refresh a **coverage ledger** (e.g. `docs/audits/coverage_ledger_<date>.md`) mapping every source item to BUILT | SCHEDULED | FINALIZED-EXCLUSION. The ledger is the objective proof of coverage and must precede declaring any source "done". Record the covered-confirmations and exclusions too, for the audit trail.

### 5. Verify
Confirm the ledger is current and the plan carries no optional-forever language (the `plan-defer-guard` hook is the always-on backstop for that between audit runs). A source is "done" only when every item it contains is built or an explicit justified exclusion in the ledger.

## Notes
- This is a reasoning pass - it necessarily reads content and reasons about coverage; unlike an unbluff *hook* it is not a pure mechanical grep. That is the point: the mechanical hook and the reasoning skill are two halves of one completeness guarantee.
- Pairs with: `plan-defer-guard` (the hook), `meta-review` (broader reasoning audit for parked work / optimization gaps).
