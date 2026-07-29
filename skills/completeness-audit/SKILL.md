---
name: completeness-audit
description: Guarantee a plan/roadmap stays a TRUE completeness ledger for its authoritative sources - catch both parked/deferred-and-forgotten items AND source content silently missing from the plan. Run when a plan is created or rebuilt, at milestones / after each cluster ships, before declaring any source or the project "done", and whenever the user asks "did we forget anything / is this complete / did you defer-and-forget". Prevents the failure where a plan asserts completeness ("each gap has a home", "essentially all built") without it being verified against the sources.
---

# Completeness Audit

A plan drifts away from 100% coverage in two silent ways. This skill catches BOTH. Materiality decides ORDER, never WHETHER an item ships (the no-defer-and-forget mandate).

- **Failure (a) - soft-defer drift:** items get "parked", "on demand", "wait for a concrete failing case", "deferred opportunistic", "someday" - technically in the plan but framed optional-forever. A grep finds these (the plan mentions them).
- **Failure (b) - silent source gaps:** governed content in the source docs was never catalogued in the plan at all (e.g. an entire refining method family overlooked by a note that claimed "essentially all built"). A grep CANNOT find these - the plan does not mention them. Only a source-vs-plan coverage sweep finds them. This is the more dangerous mode.

## Procedure

### STEP 1 - Soft-defer sweep (failure a)
Grep the plan for the optional-forever markers (case-insensitive):
`-> park`, `\bpark\b`, `on demand`, `on-demand`, `only on real user demand`, `wait for a concrete`, `deferred opportunistic`, `pick when value beats`, `someday`, `maybe later`, `if time`, `only when ... window`, `DROPPED`, `EXCLUDED`/`excluded`.

For each hit, reclassify into exactly one of:
- a **real SCHEDULED build item** in correct materiality order (with a home), OR
- an **explicit FINALIZED justified exclusion** (state the reason; e.g. "value genuinely not in the source corpus", "process artifact, not source content").

No "optional-forever" item may remain. (The `plan-defer-guard` hook is the always-on tripwire between audit runs; this step is the deliberate cleanup.)

### STEP 2 - Source-coverage audit (failure b - the important one)
1. List the authoritative source(s) the deliverable must fully encode (PDFs, specs, standards). Note their file paths.
2. Fan out a **Workflow**: one agent per source, or per major section of a large source (split a big PDF by section so no agent is overloaded). Each agent INDEPENDENTLY extracts/reads its slice (e.g. PyMuPDF for a PDF) and enumerates every quantitative/testable content item: table, equation, method, factor, default, requirement, invariant.
3. Give each agent the current **BUILT + SCHEDULED inventory** (what modules/functions exist + what the plan already lists). The agent reports as a GAP only items in NEITHER list.
4. Be conservative: a real gap PRODUCES or SUPPORTS a deliverable output (an emission number, a required behaviour). Ignore pure narrative, references, figures with no quantitative content, and worked examples (those are test fixtures for a method, not separate content). Flag "confirm-don't-assume" items (a method equation that must ship WITH its scheduled data table, not as a data-only stub).

### STEP 3 - Schedule + ledger
- Add EVERY found gap to the plan in materiality order (each with a home).
- Write/refresh a **coverage ledger** at `docs/audits/coverage_ledger_<date>.md` (or the project's audit dir) mapping every source item -> `BUILT` (module/fn) | `SCHEDULED` (plan item) | `FINALIZED-EXCLUSION` (justification). The ledger is the objective proof of 100% and MUST precede declaring any source "done". Record covered-confirmations and justified exclusions too, for the audit trail.

### STEP 4 - Verify + resume
- Re-grep to confirm zero soft-defer markers remain and the ledger is current.
- Resume the build with the now-complete plan (highest-materiality newly-found item first).

## Guarantees this enforces
- The plan is a completeness LEDGER, not an optimistic list.
- A source is "done" only when every item it contains is built or an explicit justified exclusion in the ledger.
- "Low materiality" is never a reason to skip - only to sequence later.
- Related: the `plan-defer-guard` hook (tripwire for failure a); the no-defer-and-forget memory (the policy/why).
