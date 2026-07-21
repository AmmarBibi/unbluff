---
name: consistency-audit
description: Catch consistency drift in a deliverable (report/doc/slide deck) - numbers, figures, or claims in the prose that no longer match the source-of-truth data (CSVs, computed results, sweep outputs). Run before submitting or re-exporting a report, after regenerating results, at each revision, and whenever the user asks "do the numbers in the report still match the data / are all figures referenced / is anything stale or fabricated / did a value drift". The mechanical half (extract every cited value + figure ref, cross-check against the source data with tolerance) is a bundled script; the reasoning half (is a claim actually SUPPORTED, is the interpretation consistent across sections) is Claude's - which is why this is a skill, not just a hook.
metadata:
  origin: mcg3707-report-vs-csv-drift-2026-07
tools: Read, Grep, Glob, Bash
---

# Consistency Audit

A deliverable drifts from its data silently. Prose is edited, a CSV is regenerated,
a figure is swapped - and a cited number, a figure reference, or a claim quietly
stops matching the source of truth. This skill catches four drift classes, splitting
the work the way it must be split: a **script** does the deterministic extraction and
tolerance cross-check; **Claude** does the judgment a script cannot.

Motivating case (MCG3707): `results/*.csv` held full-precision values
(`Overshoot_pct = 94.7651...`) that the report cited as "94.8 %"; across revisions a
figure got embedded but never referenced, a "see Figure 4" pointed at a caption that
had become Figure 5, and a superlative ("the lowest overshoot") no longer matched any
row. None of these are syntax errors - they are consistency drift.

## The six drift classes

- **(A) Number with no source match** - a value in the prose that appears in no source
  file within tolerance. Possible stale edit or fabrication. *The important one.*
- **(B) Orphan figure** - a figure embedded/captioned but never referenced in the text.
- **(C) Dangling cross-reference** - "Figure/Table N" cited with no matching caption
  (or a number that no longer lines up with the caption it points to).
- **(D) Unsupported claim** - a comparative/superlative or quantitative claim whose
  supporting number is absent or unmatched. *Only Claude can settle these.*
- **(E) Unfilled placeholder** - a bracketed placeholder left in the deliverable
  (`[TABLE]`, `[TODO]`, `[insert value]`, `[XX]`, `TKTK`, `TBD`, ...). Should never ship.
- **(F) Table referenced/captioned but not rendered** - the prose promises "Table N"
  (a reference or a caption) yet the deliverable contains no actual table - the classic
  placeholder-table miss.

## Inputs

- **Deliverable**: the report/doc/slides (`.docx`, `.pdf`, `.tex`, `.md`, `.txt`, ...).
- **Source-data dir(s)**: the authoritative CSVs / results / sweep outputs / JSON.
- Optional: numeric tolerance (default relative 1 %, which absorbs normal rounding).

## Procedure

### STEP 1 - Run the mechanical pass
```bash
python <skill_dir>/scripts/audit.py \
    --deliverable <path/to/report.(docx|pdf|tex|md)> \
    --sources <dir1,dir2 or file.csv> \
    [--rel-tol 0.01] [--json audit.json]
```
It normalises the deliverable to text (docx/pdf need `python-docx`/`pdftotext`/PyMuPDF/
pdfminer if the format is binary - it prints exact guidance if none is available),
indexes every numeric value in the sources, and prints candidates grouped [A]-[F].
If extraction fails, produce a text/markdown export of the deliverable and re-run.

### STEP 2 - Adjudicate the mechanical flags (this is the point)
The script proposes; **you decide**. For each candidate, do not just repeat it:

- **[A] unmatched numbers** - open the cited context AND the nearest source value the
  script named. Classify each as: **DRIFT** (prose disagrees with data - fix the prose
  or regenerate), **DERIVED** (legitimately computed from source values, e.g. a ratio or
  a sum - confirm the derivation), **ROUNDED** (beyond tolerance but defensible - note
  it), or **DEFINITIONAL/EXTERNAL** (a spec constant, a citation, a target - not drift).
  Prefer reading the source row over trusting the prose.
- **[B] orphan figures** - is the figure genuinely unused (drop it or reference it), or
  referenced by a name the regex missed? Confirm before recommending removal.
- **[C] dangling refs** - did the figure/table numbering shift? Trace the reference to
  the caption it *should* point to and report the corrected number.
- **[E] placeholders** - a leftover `[TABLE]`/`[TODO]`/`[insert ...]` is almost always a
  real defect: fill it from the source or remove it. Zero placeholders should ship.
- **[F] promised-but-missing tables** - if the prose says "Table N" (or captions one) but
  no table is rendered, build the table from the source data or drop the reference.

### STEP 3 - The reasoning pass (the half no hook can do)
Now do what the script cannot:
1. **Claim support.** For each [D] candidate and each substantive claim in the prose,
   ask: is there a source number that actually supports it, at the stated precision and
   direction? "The passive design gives the lowest overshoot" is only true if the
   passive row IS the minimum in the sweep - check the data, not the sentence.
2. **Cross-section consistency.** Does the same quantity carry the same value everywhere
   it appears (abstract vs body vs table vs conclusion)? A number that is internally
   inconsistent is drift even if each instance matches *some* source row.
3. **Interpretation.** Does the narrative reading match what the numbers say (a "stable"
   claim against a row that shows instability; "improved" against a worse value)? This is
   the failure a number-matcher cannot see.

### STEP 4 - Report + fix
Write a short audit report (to the project's audit dir, e.g.
`docs/audits/consistency_<date>.md`, or inline if the user prefers): per class, each
candidate with its verdict (DRIFT / DERIVED / ROUNDED / DEFINITIONAL / OK) and the
action taken or recommended. Fix the clear DRIFT items (correct the prose or flag the
stale source) and surface the judgment calls for the user. State the tolerance used and
the source files indexed, so the audit is reproducible.

## Guarantees this enforces
- Every number in the prose either matches a source value within tolerance or has an
  explicit, recorded reason it does not (derived / rounded / definitional).
- Every figure is referenced, and every reference resolves to a real caption.
- Every quantitative claim is checked against the data that would support it, not just
  against whether *a* matching number exists somewhere.

## Why this is a skill, not just a hook
A hook can mechanically flag "this number appears in no source file" - and the companion
`numbers-match` hook (unbluff) does exactly that on write, fail-silent and once per
session. But a hook cannot decide whether an unmatched number is drift or a legitimate
derivation, whether a claim is actually supported, or whether two sections tell a
consistent story. That judgment is STEP 2-3 here. Keep the hook mechanical and let this
skill carry the reasoning; they are the two halves of the same guarantee.
