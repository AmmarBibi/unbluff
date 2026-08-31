# Completeness audit - 2026-08-28

> **[SUPERSEDED IN PART, 2026-08-29]** This artifact describes `tools/check_tier_freshness.py`
> as shipped. That file was **DELETED** the next day - it was invoked by nothing, it carried 29
> of the 52 findings from the independent review (`wf_a71fb7d3-79d`), and CI was red on it.
> See `docs/PLAN.md` item 17 for the reversal and the three findings kept from it. Everything
> else here stands as written, as the record of what was true on 2026-08-28.

**Plan:** `docs/PLAN.md`, 32 items (0-31) at entry, **35 items (0-34) at exit**, contiguous by
parse both times.
**Session:** commits `34f82eb..f10a242`.
**Procedure:** STEP 1's soft-defer grep run as its own pass (NOT meta-review's CHECK 1, which asks
a different question about instance-vs-mechanism). STEP 2 run as a source-vs-plan sweep over this
session's own gate outputs.

---

## STEP 1 - soft-defer sweep (failure mode a)

Markers grepped case-insensitively across this session's rows (7, 8, 11, 17, 24, 26-31 and the
"Known-stale by design" section): `park`, `on demand`, `wait for a concrete`, `deferred
opportunistic`, `someday`, `maybe later`, `if time`, `DROPPED`, `candidate`, `consider`, `later`,
`probably`, `for now`, `until then`.

**11 hits. 10 adjudicated as not soft-defers:**

- `later the same session`, `landed forty minutes later`, `compares as LATER than it is`,
  `discovered by a later reader` - the English word, not a deferral.
- item 28 *"Fix candidates, cheapest first"* - proposals INSIDE an open scheduled row. The row
  itself is the home; naming two approaches is not deferring the row.
- item 31 *"the fix is probably neither"* and *"Until then `tier-freshness` reports it every run"* -
  an open row that states its interim state honestly. Scheduled, not parked.
- `"say what you dropped"`, `maintenance obligation is dropped` - quotations of a rule.

**1 REAL soft-defer, FIXED:**

> item 27: **"Consider making that mechanical rather than remembered"**

Optional-forever framing, and worse than usual because of where it sat: **item 27 closes by
splitting ONE file** (`piped_gate_guard.py`), while the thing being "considered" is a GENERAL
detector for comment-shaving. Closing 27 would have deleted it. That is precisely the
defer-and-forget shape this step exists to catch, in a row I authored this session.

**Promoted to item 32** with a stated fix, a report-don't-block decision, and a both-directions
probe requirement including the harder case (a shave spread across two commits). Item 27 now
points at it.

**Re-grep after the fix:** the only surviving `consider` hits are the two sentences that DESCRIBE
the promotion. Zero optional-forever items remain in this session's rows.

---

## DONE items verified against their OWN stated definitions

Not "is it closed" - "is it done to what the row actually asked for".

### Item 7 - PASS, verified empirically
Stated goal: *"after the move, adding a gate stops touching the orchestrator at all."*
Commit `964899b` registered a brand-new gate (`tier-freshness`). Its diffstat names four files:
`README.md`, `docs/PLAN.md`, `tools/check_tier_freshness.py`, `tools/gate_registry.py`.
**`run_selftests.py` count: 0.** The goal is met by measurement, not by assertion.

### Item 24 - PASS
Stated fix: *"record the counts per run in the gate ledger alongside the tier result... Then the
trajectory is derived, like the count, instead of retyped."* Both halves shipped - the recording
(7th declared tier, enforced by AST in both directions) and the derived comparison printed each
run. The row's confirm-don't-assume note was honoured and caught a false premise in the row
itself (`hook-provenance` did NOT already call into that path).

### Item 17 - PASS WITH A DEVIATION, now recorded
Stated fix: *"a gate that, per tier, compares its latest ledger stamp against **the newest commit
touching the surface that tier covers**."*
**What shipped compares every tier against HEAD**, not against a per-tier surface.

This is the stricter of the two - it cannot miss a stale tier - and the reason is this repo's
most repeated defect class: a per-tier "surface" is a DECLARED ROSTER, and a declared roster that
drifts under-scopes the very check it defines. HEAD is derived and cannot drift. The cost is
over-reporting, which is why the default is a measurement.

**The audit finding is not the deviation - it is that the row said DONE without naming it.**
Now recorded in item 17, with the constraint that any future per-tier surface must be DERIVED
(e.g. from the files each tier reads), never hand-listed.

---

## STEP 2 - source-coverage sweep (failure mode b, the dangerous one)

Sources: this session's four gate-output classes (suite, mutation sweeps, tier-freshness,
anchors/file-size) plus `docs/audits/*`. A grep cannot find these; the plan does not mention them.

**2 GAPS FOUND, both scheduled:**

### Gap 1 -> item 33: three gate-layer modules with the author as their only reviewer
`review-freshness` names all three in its own output every run:
`tools/gate_registry.py`, `tools/check_tier_freshness.py`, `tools/hook_divergence_trend.py` -
*"never adversarially reviewed"*. The plan mentioned none of them.

Not covered by the existing `install_selftest.py` note, which concludes "the gate can keep
asking". That stance is defensible for a TEST file. These are not: `gate_registry.py` decides what
counts as a gate, which mode each runs in and which tiers must record - governance;
`check_tier_freshness.py` is gate logic carrying an exemption roster. tooling-discipline section 6
names exactly these categories as requiring an independent pass.

**This session supplied two live demonstrations inside its own new code**: the `TF-UTC` assertion
passed while being decorative, and `head()` shipped a fail-open its own selftest could not see.
Both were caught by the sweep and by reading real output - not by the author's reasoning, which
had twice concluded the code was correct. Items 7, 17 and 24 are currently reported DONE on the
strength of gates the same author wrote.

### Gap 2 -> item 34: the false-alarm corpus covers 1 of 45 units
`-- coverage: 1 of 45 units have a corpus (2%); 44 uncovered` prints in every suite run.
Grep for the phrase in the plan: **zero hits**. It has never had a home.

Material because the repo's most-repeated operational rule is that a guard firing on correct work
gets switched off - four measured instances in two sessions, and the reason `tier-freshness`
defaults to a measurement. The corpus is the only thing that MEASURES that rule rather than
asserting it. At 2%, the false-alarm claim for 44 of 45 units rests on the absence of complaints,
which is the "silence is not evidence" shape audited elsewhere in this same plan.

Scheduled with a derived denominator rather than a demand for 45 corpora: derive which units can
actually fire at a user, report against THAT, and schedule corpora for those.

---

## Ledger

| item | status | home |
|---|---|---|
| 7 registry cut | BUILT, sweep-verified both sides | done to its stated goal, measured |
| 17 tier-freshness | BUILT | done, deviation from own wording now recorded |
| 24 trajectory | BUILT | done to its stated fix |
| 26 SURVIVED-vs-HARNESS-ERROR | SCHEDULED | own row, fix + trap written |
| 27 ratchet shaving (3 files) | SCHEDULED | own row; general half promoted to 32 |
| 28 UNBLUFF_LEDGER_OFF setter | SCHEDULED | own row, adjudicated not-a-live-defect |
| 29 gate_ledger writer/reader binding | SCHEDULED | own row |
| 30 git-derived population blind to untracked | SCHEDULED | own row |
| 31 false_alarm_scorer declared-but-not-executing | SCHEDULED | own row |
| 32 comment-shaving detector | SCHEDULED (new) | promoted out of 27 |
| 33 independent review of 3 new gate modules | SCHEDULED (new) | source gap |
| 34 false-alarm corpus denominator | SCHEDULED (new) | source gap |

**Zero optional-forever items. Zero items without a home. 35 rows, 0-34, contiguous by parse.**

## Verdict

STEP 1: 1 real soft-defer found and promoted. STEP 2: 2 silent source gaps found and scheduled -
neither was greppable, and one of them (item 33) directly qualifies the confidence of the three
DONE items this session shipped. One DONE item (17) passed but deviated from its own wording; the
deviation is now stated rather than absorbed.
