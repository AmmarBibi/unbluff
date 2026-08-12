# Source-coverage audit - 2026-08-12 (close ritual, pass 3 of 4)

**Subject:** `docs/NEXT_SESSION_PROMPT.md` reconciled against its sources - the ledger and the
repo state it describes. **STEP 5 run in full.** Every figure below was DERIVED from the repo
in this pass, not read back out of the plan.

## Repo truth vs plan claims

| quantity | plan said | repo says | verdict |
|---|---|---|---|
| HEAD | `367ace4` | **`0ef4e2b`** | **DRIFT** - 5 commits behind |
| mutation entries / anchors | 162 / 163 | **179 / 180** | **DRIFT** |
| CI jobs | 16 (three places) | **17** (derived by `check_readme_fresh.expected_jobs`) | **DRIFT** |
| last full sweep | 160 of 162 | 171 of 173 at the time it was run; 179 entries exist now | **DRIFT / stale** |
| suite gates | 33 / 33 | 33 | OK |
| `SELFTEST-BUDGET-FLAKE` | listed as **SCHEDULED** in the queue | **BUILT** today | **DRIFT** |

Everything closed today (`FTB-RC4`, `FTB-SPELL`, `ROSTER-DERIVE`, `WT-CAUSE`, `RICH-CI`,
`CI-JOBS`, and the rest) is correctly absent from the plan's queue and present in the ledger -
the intended division, and it held.

## The one that matters

The **CI job count is the only one of these that is now GATED**. It drifted 14 -> 16 -> 17 by
hand over the project's life; as of today `check_readme_fresh.verdict_jobs()` derives it from
the workflow with two independent parsers that must agree, and fails when it cannot parse at
all. So README's copy of that number can no longer go stale silently.

**The plan's copies still can.** Every other row above is a hand-maintained figure in a
briefing document, which is the class rule 7.3 warns about: a document that only grows becomes
unreadable, and its stale numbers are indistinguishable from fresh ones. The mitigation applied
here is not another gate but the resume procedure itself - the plan's FIRST instruction is to
re-derive `git status`, `gh run list` and the suite before trusting anything it says. That is
why the STATE block is safe to carry stale figures between sessions, and why it is corrected at
every close rather than trusted mid-session.

## STEP 5 verification

- **Optional-forever language: none** (7 marker hits, all prose - see `completeness_2026-08-12.md`).
- **Ledger current:** every item surfaced today maps to BUILT, SCHEDULED, or
  FINALIZED-EXCLUSION with a named home, including the rc-3 decision this ritual recovered.
- **Plan corrected** in the same close: STATE block re-derived, and `SELFTEST-BUDGET-FLAKE`
  moved out of the pending queue.
