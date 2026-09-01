# Consistency audit - 2026-09-01

**Scope:** what THIS session authored - the new `## Status and order` section, the restated bar,
item 20's DONE marker, and item 34's denominator. Docstrings only for `.py`.
**Deliverable:** `docs/PLAN.md`
**Sources:** `derived.json` (every count re-derived by parsing the plan and the gate output this
session, not typed) plus the live suite run `s_recut.txt`. 96 values, 2 files.
**Tolerance:** rel 0.01. **Mechanical pass:** bundled `scripts/audit.py`, exit 0.
1324 numbers found, 1041 checked.

## Mechanical result

| class | count | in the NEW section | adjudication |
|---|---|---|---|
| [A] number with no source match | 103 | 2 | both benign - see below |
| [B] orphan figure | 0 | 0 | - |
| [C] dangling cross-ref | 0 | 0 | - |
| [D] claim to verify by reasoning | 15 | **0** | none in new text |
| [E] unfilled placeholder | 12 | 1 | item 18's known class |
| [F] table promised, not rendered | 0 | 0 | of 5 tables |

### The two [A] flags inside the section I wrote - both OK

- **L166 `79`** - parsed out of the review run id `wf_a71fb7d3-79d`. Not a quantity.
  **DEFINITIONAL.**
- **L139 `[]`** - my own sentence *describing* item 18's defect quotes `[]`, and the extractor
  flagged it. **Item 18's documented false-positive class firing on the description of item 18.**
  Self-demonstrating, and the second consecutive close at which this class has fired on this
  repo's own plan. It remains open with the fix written (require a letter in the token, or skip
  the class for code extensions).

The other 101 [A] flags are outside this session's text: ISO timestamp components, commit SHAs
read as integers, file:line citations, and figures from earlier sessions. The source index holds
this session's derived facts, not eight sessions of history.

## DRIFT FOUND AND FIXED - 1, and I authored part of it today

**The false-alarm corpus denominator moved 45 -> 44 and the plan said 45 in four places.**

Item 17's deletion removed a `.py` unit from the population. The suite now prints
`-- coverage: 1 of 44 units have a corpus (2%); 43 uncovered`. The plan claimed:

| line | claimed | corrected |
|---|---|---|
| 141 (**written by me this session**) | 1 of 45 | 1 of 44, with the reason |
| 1427 (item 34 headline) | 1 of 45 | 1 of 44 + a note that the denominator moved |
| 1436 | 44 of 45 | 43 of 44 |

The 1428 quotation of the original suite line is left as a dated quote - it is what the suite
said on 2026-08-28 and the row now says so explicitly.

**This is the sharpest finding of the audit and it is about me.** Item 34 exists to complain that
a denominator nobody examines is worthless - and its own denominator went stale three days after
it was written, inside the row making the argument. I then copied the stale figure into a brand
new section *while re-cutting the plan for accuracy*. A hand-copied denominator drifts the moment
its population changes; that is item 15's defect, and this is its fourth instance in this file.

## Cross-section consistency

- **Counts in the new Status section re-derived and MATCHED exactly:** 36 rows, 0-35, contiguous;
  18 closed `[0,1,2,3,4,5,6,7,10,15,17,20,21,22,23,24,25,33]`; 18 open
  `[8,9,11,12,13,14,16,18,19,26,27,28,29,30,31,32,34,35]`. The parse and the written claim agree
  set-for-set, not just count-for-count.
- **That agreement required a correction first.** My initial parse said 10 closed / 26 open. The
  probe was wrong twice: it took the LAST `^N. **` match, and the Retired section reuses the same
  numbers, so items 1-7 and 20 were being read out of the wrong section. Scoping strictly to the
  `## Open` section fixed it. **A probe that disagrees with the document is not automatically
  right** - it has to be shown to be looking in the right place, and this one was not.
- **Item 20 genuinely had no status marker.** A machine parse scored it OPEN while every session
  prompt called it DONE. Two sources of truth disagreed for six days. Marker added, with that
  disagreement recorded as the reason the new Status section exists.
- 44 selftests: the plan carries no stale "45" reference to the suite count (the only `45` hits
  were the corpus denominator, now fixed).

## Interpretation

Does the narrative match the numbers? Yes, with one thing said plainly: **the new Status section
asserts a bar change that deletes work** ("materiality decides ORDER, never WHETHER" is replaced),
and it then recommends retiring items 27 and 32. That is a real reduction in scope, recommended
not executed, and it is flagged for the owner rather than applied silently.

## Verdict

**1 DRIFT found and fixed** (the corpus denominator, in 3 places, one of them authored this
session). 0 orphan figures, 0 dangling refs, 0 real placeholders, 0 unsupported [D] claims in the
new text. Every count in the new Status and order section is derived and matches its parse.
