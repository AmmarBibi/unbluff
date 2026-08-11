# Consistency audit - 2026-08-11 (close ritual, pass 1 of 4)

**Deliverable:** `docs/audits/coverage_ledger_2026-08-09.md`
**Tolerance:** rel 0.01, abs 1e-9.
**STEP 1 was run IN FULL via the bundled `scripts/audit.py`** - not a targeted derivation.
That substitution is precisely what was recorded as skipped on 2026-08-11 (ledger N2), and
running it properly is why this pass has anything to report.

## The extractor had to prove it looked in the right place - and at first it had not

| run | source index | `[A]` unmatched |
|---|---|---|
| 1 | this session's scratchpad + task outputs only (435 values, 12 files) | **92** |
| 2 | + `docs/audits`, `NEXT_SESSION_PROMPT.md`, `README.md`, `CHANGELOG.md`, `mutation_check.py`, `cap_shapes.py` (1168 values, 40 files) | **0** |

The 92 were an ARTEFACT of an under-scoped source index, not drift: the ledger's historical
figures (243 claims, 247 item-occurrences, 85 PROVEN) cannot appear in today's measured
outputs, so "no source match" meant "absent from the files I indexed". **Reported here rather
than quietly re-run**, because a 92-candidate list adjudicated one-by-one would have produced
92 confident FALSE-POSITIVE verdicts and read as thorough work. The rule that caught it is the
skill's own: an extractor that finds nothing - or finds everything - must first prove it looked
in the right place.

## Verdicts

**[A] numbers with no source match - 0 of 632 checked.** 771 found, 632 checked, 101 skipped as
reference-context, 38 as years. Every figure this session introduced resolves: mutation entries
155 -> 162, anchors 156 -> 163, 33 gates, live exemptions 2 -> 3, 16 CI jobs, 7 of 7 FTB pins,
7 of 10 blocked shapes, 16/17 and 24/25 executed with 0 unproven.

**[B] orphan figures - 0. [C] dangling cross-refs - 0. [F] tables promised but not rendered -
0 of 24 tables found.**

**[D] claims to verify by reasoning - 2, both OK.**

- `L419` *"200 entries and every one is `run_selftests`"* - **VERIFIED against the file, not
  assumed**: 200 entries, `{'run_selftests': 200}`, 177 PASS / 23 FAIL. The claim still holds
  exactly. **It also re-confirms the finding it supports, with fresh evidence:** this session
  ran the mutation harness four times, the integration test, and three CI rounds, and
  `gate_runs.json` still contains *only* `run_selftests`. The "gate ledger records 1 of 5 tiers"
  row (section L) is not stale - it was re-demonstrated today.
- `L513` *"a pure import-closure of the entry points reaches most of the local modules,
  including the entire cap detector"* - qualitative, unchanged by this session's work, and
  already established in K1. No new evidence required; no drift.

**[E] unfilled placeholders - 3, ALL FALSE POSITIVE, all one cause.**

- `L306` - the `[]` in *"both rosters return `[]`"*, a literal empty-list RESULT of the OPT-1
  fix, not an unfilled slot.
- `L337` x2 - inside the ledger's own `CA-SELFREF` row, which literally reads *"The bundled
  script flagged `[E] placeholder` ... the `[]` sits inside the plan's own sentence"*.

**`CA-SELFREF` is now THIRD-instance and demonstrably SELF-PROPAGATING.** Instance 1 was in
`NEXT_SESSION_PROMPT.md:235`; instance 2 was recorded in the ledger; instance 3 is the
ledger's record OF instance 2. Each time the defect is documented, the documentation becomes a
new instance, so the count grows by writing about it. That is a stronger argument for fixing it
than "one false positive" was: the flag rate rises monotonically with how carefully the project
records its own findings, which is a direct tax on this repo's central practice. Already
SCHEDULED (section B); this pass adds the propagation argument, not a new row.

## Cross-section consistency

The figures this session introduced are stated once each in the ledger and once in the
corresponding commit message, and agree in both places: 7 of 10 shapes, 7 of 7 pins, 16 jobs,
33/33 both interpreters, 30/30 integration. No quantity carries two values.

**One interpretation check, since a number-matcher cannot see it:** the ledger says
`FASTTEST-BLOCK` is **BUILT** while also saying the author wrote its only probe. Those are
consistent only because the row states the limit in the repo's own rule-6 language ("12 shapes
passed", not "no false alarm remains") and leaves the independent pass SCHEDULED. Had the row
said "proven" or "no longer false-alarms", it would have been drift of the interpretation kind -
the failure this step exists to catch.

## Actions

- No DRIFT found; no prose corrected.
- `CA-SELFREF` propagation argument appended to this report (row already SCHEDULED).
- Methodological note recorded: **scope the source index before believing an `[A]` count**,
  in either direction.
