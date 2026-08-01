# P14 triage - the dropped candidate adjudicated, the two runs reconciled

Companion to `p14_new_code_review.md`. That document records what the review PRODUCED.
This one records what survived triage, and is the authoritative work-list for the P14 fix
pass. Written 2026-08-01.

## 1. The dropped candidate: `verify:ast-guard-completeness:1` - **CONFIRMED**

Recovered from the journal (`agent-a75c13662f711848e`, no `result` record - the refuter
died mid-run on a session usage limit with its final A/B still in flight).

**As filed (HIGH):** "A hook whose cap constant is imported rather than assigned is skipped
whole, forbidden slice and all." `hooks/capped_report.py:100-102` - `caps = _max_names(tree)`
then `if not caps: continue`; `_max_names` sees only `ast.Assign`, so
`from constants import MAX_BULLETS` yields `caps == set()` and the file is skipped before a
single node is examined.

**Verdict: CONFIRMED, severity HIGH, latent.** Re-adjudicated from scratch against the
pristine module rather than inherited from the dead agent.

Demonstrated (6 cap spellings planted in a temp dir, guard run over each - denominator
printed, 1 of the 6 is the already-handled control):

| spelling | `caps` resolved to | flagged |
|---|---|---|
| `MAX_BULLETS = 12` (control) | `{'MAX_BULLETS'}` | yes |
| `from constants import MAX_BULLETS` | `set()` | **no** |
| imported + an unrelated local `MAX_UNRELATED` | `{'MAX_UNRELATED'}` | **no** |
| `MAX_BULLETS: int = 12` | `set()` | **no** |
| `MAX_BULLETS, _PAD = 12, 0` | `set()` | **no** |
| `constants.MAX_BULLETS` | `{'MAX_OTHER'}` | **no** |

**5 of 6 blind.** And the filer's stated cause is only half of it: the
"imported + unrelated local `MAX_`" row is NOT whole-file-skipped (`caps` is non-empty) and
is still missed, so `_max_names`' name-resolution gap is the deeper cause and
`if not caps: continue` is merely the first of TWO gates that must be fixed. A fix that only
deletes the early-skip leaves the import and attribute spellings blind.

**Scope, measured, not asserted:** `if not caps: continue` skips **13 of the 17** hook files
in `hooks/` today. The guard's own docstring claims a repo-wide invariant while examining
four files.

**Live or latent:** latent. Zero imported `MAX_*` and zero annotated `MAX_*` caps exist in
`hooks/` today, so no shipped hook currently exploits it.

**Effect on the work order: none to the sequence, but row 1 widens.** This is the same unit
as work-order row 1 (`hooks/capped_report.py`) and the same function as two already-confirmed
HIGHs. It adds two spellings neither of them covers - **import** and **attribute** - so the
`_max_names` fix must collect `ast.ImportFrom` aliases and the slice/comparator test must
additionally match `ast.Attribute` whose `attr` starts with `MAX_` (an attribute load has no
`Name` to resolve). Row 1 stays first.

## 2. The recovered first-run set, deduplicated - **overlap 41 of 42**

Both sets deduplicated finding-by-finding against each other. Denominator: 42 main confirmed
x 42 recovered. **41 of the 42 recovered findings have a clear twin in the main 42 (97.6%).**
Nothing was dropped for being a near-miss; the four rows below are every item that is not a
plain duplicate.

### 2a. No twin in the main 42 - additional findings

| id | severity | finding | disposition |
|---|---|---|---|
| F-M8 | MEDIUM as filed | `_max_names` collects only `ast.Assign`, so `from constants import MAX_BULLETS`, `MAX_BULLETS: int = 12` and `constants.MAX_BULLETS` are all invisible; explicitly corrects the reviewer's stated cause (the early-out) as wrong | **twin of the dropped candidate above.** Two independent passes found the same defect, and it is precisely the one the main run failed to adjudicate. Folds into row 1; no separate row |
| F-L8 | LOW | `transcript_util` X5+X6: the composition IS loudly caught (2/22 FAILED), **but X6 alone is a real surviving mutation** worth one misclassified entry in 2033, and two concrete killing fixtures are supplied | **NEW.** The main list refuted this finding *wholesale*; the first run's refuter agreed about the composition and kept a residual. Add as LOW against `hooks/transcript_util.py` |

### 2b. Same defect, first run rated it higher AND found a live instance

| id | main | recovered | what the recovered version adds |
|---|---|---|---|
| M-L7 / F-M19 | LOW | **MEDIUM** | not latent: **2 of the 79 executed mutations** already die on an uncaught traceback at the call line before any assertion about the mutated behaviour runs, and deleting those assertions outright still yields CAUGHT. Names both sites: `verdict()`'s success message, and `rate_prompt`'s non-str block call above line 125 |
| M-L10 / F-M22 | LOW | **MEDIUM** | `crashes.clear()` is a SECOND unpinned thing beside the `crashed` ledger key, with a specific assertion shape (clean run after a crashing run must report `crashed == {}`) |

Both are **escalated to MEDIUM** and their fixes must cover the added instances. Severity
moved up, never down: where the two runs disagree the higher rating wins, because a
downgrade here is exactly the silent-shrink this repo exists to catch.
(`M-M11 / F-L4` disagrees the other way - main MEDIUM, recovered LOW - so main stands; no
action.)

### 2c. Corroborations worth keeping in the fix, not separate rows

- `F-M12` demonstrates the collection-cap blind spot with a **pure operand swap**
  (`MAX_X <= len(hits)`) in a registered hook flipping the gate from FAIL to SELFTEST OK with
  22/22 green. Main `M-M15` calls the same class latent. Use the operand-swap as the planted
  fixture; it is the cheapest shape that proves the arm is one-sided.
- `F-H3` establishes a **fix ORDER** the main list does not state: fix `_child` FIRST, because
  adding `verify_unit` to mutation #10 alone just flips it to SURVIVED.

## 3. Merged backlog

| | HIGH | MEDIUM | LOW | total |
|---|---|---|---|---|
| main P14 confirmed | 10 | 22 | 10 | 42 |
| + dropped candidate, now confirmed | +1 | | | +1 |
| + F-L8 (transcript_util X6 residual) | | | +1 | +1 |
| + escalations M-L7, M-L10 (LOW -> MEDIUM) | | +2 | -2 | 0 |
| **merged total** | **11** | **24** | **9** | **44** |

The work order in `docs/V131_REVIEW_PLAN.md` P14 is unchanged in SEQUENCE. Row 1
(`hooks/capped_report.py`) grows from 7 findings to 8 and from 3 HIGH to 4.

## 4. The harness gap this exposed, which no row above closes

A resumed workflow re-ran its lenses instead of replaying them and returned only the second
run's results. The coverage block reconciles *within* one run, so it reported a
complete-looking 47/46/1 that was complete for the resume and silently excluded 42
independent findings. **Nothing in the harness reconciles across a resume boundary.** The
overlap turned out to be 97.6%, which is the good case - and it was unknowable before
someone counted. Recorded here so the number is not mistaken for a reason to skip the count
next time.
