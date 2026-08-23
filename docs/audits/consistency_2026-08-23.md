# Consistency audit - 2026-08-23

**Scope, and it is deliberately narrow:** only what this session authored, commits
`d89e3dc..a9b5cc6` on `feat/enforcing-verify`. Deliverable = `docs/PLAN.md` gate rows 1, 2, 3, 5,
7, 8 plus rows #39/#40/#41, and `CHANGELOG.md`'s new `[1.4.0]` section.

Scoping it this way is itself a deviation worth naming: a previous unscoped run of this skill on
a whole plan returned thousands of candidates whose denominator was the source set's coverage
rather than the prose's accuracy, and a report nobody can read is a report nobody reads.

**Source of truth:** not a CSV - the live repository, measured at 2026-08-23T14:55:02Z by
`scratchpad/derive_facts.py`, which re-derives all 33 values (git shape, file line counts read as
bytes, the baseline JSON, the gates' own `expected_*()` functions, the promise inventory's
section headings). **Tolerance:** relative 1%, absolute 1e-9.

## STEP 1 - mechanical pass

`skills/consistency-audit/scripts/audit.py --deliverable docs/PLAN.md --sources derived_facts.json`

| class | raw | in-scope |
|---|---|---|
| [A] numbers with no source match | 83 of 201 (144 checked) | 62 |
| [B] orphan figures | 0 | 0 |
| [C] dangling cross-refs | 0 | 0 |
| [D] claims to verify by reasoning | 7 | 5 |
| [E] unfilled placeholders | 0 | 0 |
| [F] tables promised but not rendered | 0 | 0 |

The [A] count is **not** 62 defects. The extractor cannot distinguish a cited measurement from a
task id (`#25`), a date (`2026-08-23`), a commit sha, or a version. That is the whole reason
STEP 2 exists, and reporting 62 as a finding count would be the exact bluff this repo objects to.

## STEP 2 - adjudication

Every measurement asserted in the in-scope rows, checked against the derived source:

| claim | asserted | derived | verdict |
|---|---|---|---|
| inventory split README | 152 / 70 / 82 | 152 / 70 / 82 | **OK** |
| inventory split SKILL.md | 91 / 15 / 76 | 91 / 15 / 76 | **OK** |
| inventory total | 243 / 85 / 158 | 243 / 85 / 158 | **OK** |
| excluded findings / HIGH | 42 / 10 | 42 / 10 | **OK** |
| findings covered | 24 | 24 | **OK** |
| suite after gate 2 | 39/40 | 40 registered, 1 failing | **OK** |
| pieces shipped | 20 | 20 | **OK** |
| CI jobs | 17 | 17 | **OK** |
| `fast_test_on_stop.py` | 851 | 851 | **OK** |
| `pre_push_gate_selftest.py` | 1192 | 1192 | **OK** |
| `pre_push_gate.py` headroom | 792 of 800, 8 left | 792 | **OK** (8 = 800-792, DERIVED) |
| `install.py` selftest span | 299 of 927 | 299 / 927 | **OK** |
| baseline offenders | 5 | 5 | **OK** |
| `[1.3.1]` chars | 4,072 | 4,072 | **OK** |
| `[1.4.0]` chars | 5,285 | 5,285 | **OK** |
| `[Unreleased]` moved | 19,241 chars | 19,717 on disk | **DERIVED** - the file adds a 476-char header explaining the move; the 19,241 is the body |
| ~1,200 chars per bullet | ~1,200 | 19241/16 = 1202.6 | **DERIVED** |
| install roster guarded vs not | 25 vs 26 | probe output | **OK** |
| no-network population | **58** | **59** | **DRIFT - FIXED** |

### The one real DRIFT

`docs/PLAN.md:86` and `CHANGELOG.md:64` both said the no-network gate covers **58 files**. The
gate reports **59** as of 2026-08-23T14:56:20Z. **I caused it**: adding
`hooks/fast_test_disclosure.py` for gate 2 grew the derived population, and I wrote the stale 58
into the new `[1.4.0]` notes by copying the plan's wording instead of re-deriving it.

This is standing check 3 - "is the number derived, and derived *just now*?" - failing on the same
day it is quoted, in a document written by the person who broke it. Both are corrected to 59 and
now carry the date, per the plan's own corollary that a mutable count lives in the body, dated.

**It is also a gap, not just an instance.** Three cardinalities on the README are now derived and
gated; the equivalents in `PLAN.md` and `CHANGELOG.md` are gated by nothing, and this one was
caught by a close audit rather than by a control. Filed as **#42**.

## STEP 3 - reasoning pass

**3.1 Claim support.** The 5 in-scope [D] candidates were read against the argument around them.
All are qualitative statements with their supporting measurement in the adjacent sentence
("installing the better library makes the audit read less" - supported by the PyMuPDF branch
returning unconditionally where the other two check; "deleting it would cost more than the notes
gain" - a judgement, marked as one). No unsupported quantitative claim found.

**3.2 Cross-section consistency.** 11 quantities checked across `README.md`, `CHANGELOG.md`,
`docs/PLAN.md`, `SECURITY.md`, `SKILL.md`. 10 agreed across every document and matched the repo.

**1 reported DRIFT was a defect in the checker, not the documents.** The pattern
`(\d+) of its 927|of its (\d+) lines` captured `299` from its first alternative and compared it
against 927. Both documents in fact say "299 of its 927 lines", which is correct. Verified by
reading the literal strings before believing the tool. Recorded rather than quietly dropped: one
of eleven checks in a freshly written instrument was wrong, which is the ratio this project keeps
measuring and the reason a green from a new checker is not evidence.

**3.3 Interpretation.** The gate rows claim less than the work supports in two places rather than
more (gate 3 is marked DONE while criterion 1 explicitly survives as post-release; gate 7 is
marked LOCAL HALF DONE with the publish step named as not taken). No row reads as a stronger
claim than its evidence.

## Deviations, including the ones that make this report look less complete

1. **Source of truth is a derivation script I wrote today**, not an independent dataset. It reads
   the repo, so a defect in it would produce agreeing-but-wrong numbers on both sides. The
   cross-section pass is partial mitigation, not independence.
2. **`--sources` was a single JSON of 33 values.** The extractor therefore had no way to match
   dates, task ids or shas, which inflated [A] from a real handful to 62 in-scope candidates.
3. **[A] was adjudicated by hand against a hand-listed set of claims**, not exhaustively over all
   62. A claim I asserted and then forgot to list would not be caught by this pass.
4. **Only this session's rows were audited.** Rows 4, 6, 9, 10, 11 and the standing checks were
   not re-verified; gate 4's "58 files" was in scope only because it collided with a number I
   wrote.
