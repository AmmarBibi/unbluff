# Completeness audit - 2026-08-20 session

Ledger audited: the Task list (#1-#20), `docs/NEXT_SESSION_PROMPT.md`'s canonical order, and the
15 confirmed findings in `docs/audits/task17_sweep_2026-08-19.md`.

## STEP 1 - soft-defer sweep (failure mode a)

Grep of the forward-looking plan for `park | on demand | wait for a concrete | deferred
opportunistic | someday | maybe later | if time | optional-forever | DROPPED | nice to have`:

**Zero optional-forever markers.** Six hits, all adjudicated as false positives: every one is the
word "dropped" used descriptively inside a finding ("0 dropped", "silently dropped", "adjudicated,
not dropped", "a source file over 8 MB is dropped from the index"). None frames an item as
optional. Nothing to reclassify.

## STEP 2 - coverage: does every item have a home?

### The 15 confirmed #17 findings - all 15 accounted for, none dropped

| # | Severity | Finding | Home | State |
|---|---|---|---|---|
| 1 | HIGH | no-regression's only unit is a delegate (self-comparison) | #11 | **FIXED** `0bb540b` |
| 2 | HIGH | STALE waiver tautology (`_detected_now` returns `gained`) | #11 | **FIXED** `0bb540b` |
| 3 | HIGH | `cap_types` lists set/frozenset as aggregators | #12 | **FIXED** `fd13d56` |
| 4 | MED | mutation table's module roster is declared twice by hand | #17 | open |
| 5 | MED | cap corpus APPEND-ONLY is prose, not enforced | #17 | open |
| 6 | MED | `score_false_alarms` HARNESS ERROR returns before record | #13 | **FIXED** `ac84464` |
| 7 | MED | `selftest_budget` I/O assertion has no CPU control | #18 | open |
| 8 | MED | `hook_divergence_report` broken-parse FAIL unreachable | #15 | open |
| 9 | MED | `hook_divergence_report` hardcoded `.git/hooks` | #15 | open |
| 10 | MED | `piped_gate_guard` GATE_TOKENS declared roster | #14 | **FIXED** `6a0aba8` |
| 11 | MED | `piped_gate_guard` PROTECTED whole-command substring | #14 | **FIXED** `6a0aba8` |
| 12 | MED | `ship_bar_gate` skips the ledger on both failure exits | #13 | **FIXED** `ac84464` |
| 13 | MED | `extract.py` PyMuPDF branch returns unvalidated text | #16 | open |
| 14 | MED | `extract.py` cannot see Word tables (check [F] false-positives) | #16 | open |
| 15 | LOW | `piped_gate_guard` PowerShell abbreviations undetected | #14 | **FIXED** `6a0aba8` |

**8 fixed, 7 open with a named task. Zero without a home.**

### The other three checks requested

- **The two behaviours #15 could not pin** (`load_factor`'s failure NOTE;
  `hook_divergence_report`'s surfaces-but-zero-examined FAIL) - **scheduled**, task #7, with the
  mechanism each needs recorded (a selftest injecting a raising calibrator; a planted wiring
  fixture). Neither was folded into a "done".
- **Deliberate deferrals** - all three have homes: #10 (the `NEXT_SESSION_PROMPT` correction, held
  because `close_skills_guard` blocks that file until these audits run - the guard was obeyed, not
  routed around), #19 (the self-comparison guard being shallower than the fix it backs up), and
  #13's UNPINNED ledger paths, which task #4 now **explicitly owns** as item (e) rather than
  merely implying.
- **`hook-provenance` cannot pass in a worktree** - task #8, unchanged and still open.

## The gap this audit found - and it had no home

**Task #20, created by this audit.** The independent review `wf_ae5964ca-35e` covered **only**
commit `ef4956d`. Everything after it - `4cb9d81`, `0bb540b`, `fd13d56`, `ac84464`, `6a0aba8`,
roughly **700+ inserted lines across 12 files** - has had **no independent pass at all**.

That matters more than a line count suggests, because most of it is GUARD AND GATE LOGIC, the one
class this project's rules say must never ship on the author's own probe alone:
`shared_siblings()` / `load_with_siblings()`, `_is_protected()` / `_ps_truncates()`,
`roster_gaps()`, `_record()`, the module-scope `gate_ledger` import, and the whole of
`tools/noregress_selftest.py`.

Two facts from this very session say the risk is real rather than theoretical:

1. The one commit that DID get an independent pass had **four real defects** in it, all confirmed,
   none of which the author's own probes had found.
2. The transitive-isolation fix in `fd13d56` was an **incomplete fix to `0bb540b`** - a defect in
   a defect-fix - and it surfaced only because an unrelated change (new corpus entries) happened
   to expose it. Nothing was watching for it.

**Consequence for #17's coverage claim, carried over from consistency finding C-1:**
`tools/noregress_selftest.py` is a never-examined unit created AFTER the sweep, so the sweep's
33-file coverage no longer covers the tree. DERIVED 2026-08-20T14:12:28Z: **57 tracked units, 34
UNREVIEWED**. The sweep is not stale as a record; it is stale as a coverage claim, and only the
second reading would have been wrong to leave implicit.

## STEP 4 - verify

Re-grep after the additions: still zero soft-defer markers. Every one of the 15 findings, the 2
unpinnable behaviours, the 3 deliberate deferrals and the newly-found review gap has a numbered
task. Nothing in this session is reported as done that is not, with one qualification stated
plainly in its own task: **#13's fixes are verified by induction but UNPINNED**, and #4(e) owns
the pinning.
