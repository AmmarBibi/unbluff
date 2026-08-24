# Close audits - delta pass, 2026-08-24

Scope: **only** the work authored after `9bcbbbd` - commits `1a0d649`, `73e04bf`, `0427c5b`.
Deliberately not a re-run over the whole session; run 1 of an unscoped consistency pass on this
plan returned candidates whose denominator was the source set's coverage rather than the prose's
accuracy, and the GHG protocol's fix for that is to scope the deliverable to what THIS pass
authored. Four skills invoked via the Skill tool, each to its own procedure. Four verdicts below;
the two earlier-invoked skills produced their findings before `close_skills_guard` blocked the
close for the two that had not run - which is the guard doing its job on its own author.

## 1. consistency-audit

Mechanical pass: `scripts/audit.py --deliverable docs/PLAN.md --sources gate_runs.json,
file_size_baseline.json`. [B] 0, [C] 0, [E] 0, [F] 0. [A] 3 candidates, [D] 7.

| candidate | verdict | action |
|---|---|---|
| L172 "a 37-item list" vs ledger max 46 | **DRIFT** | stale since the ledger grew; the sentence is about the ARGUMENT for GitHub issues, so the count is incidental - left, but now dated |
| L184 "30 of 53 claims" | DEFINITIONAL | a historical measurement inside standing check 3, not a live count |
| L186 "10 commits rotted to 11 to 12" | DEFINITIONAL | quoted as the example that motivated the rule |
| L34 "6 items to 37" | DEFINITIONAL | historical, names the spiral the bar replaced |
| L70 "1,215 lines of new Python" | **UNVERIFIED** | inherited from an earlier session, never re-derived. Flagged, not corrected - correcting it would need the gate-9 denominator |
| remaining [D] | OK | claims supported by the surrounding evidence |

## 2. completeness-audit

STEP 1 soft-defer sweep: 3 hits, 2 benign (the word "dropped" in prose). **One real:**

- **`#45` still read "Three options, none taken unilaterally"** three commits after one WAS taken
  (`73e04bf`). A row asserting indecision over a decision already made is the `B100` shape - a
  token contradicting its own body. **FIXED** in this commit: the row now records which option was
  taken, that `--no-verify` was REJECTED and why, and the probe that proved it.

Every row filed today has a home in the order: `#39` (Phase 2, FIXED), `#45` (Phase 2, RESOLVED),
`#46` (**gate 0**, Phase 1). Nothing deferred today is unscheduled.

## 3. source-coverage - read the DESIGN, not only the code

Reconciled `.claude/pre-push.cmd`, the `MACHINE_STATE` contract, and `SECURITY.md`.

- `--code-only` excludes only the VERDICT: **BUILT** - `MACHINE_STATE` appears 9x in
  `run_selftests.py`, three properties asserted in `--selftest`, and probed live.
- `SECURITY.md`'s two unenforced claims: **SCHEDULED** as `#43`, and the honest
  "Asserted but NOT yet enforced - true as far as the author knows, checked by nobody" heading is
  intact. Re-verified rather than assumed.
- **GAP FOUND -> `#47`.** `.claude/pre-push.cmd` asserts `--code-only` is "deliberately NOT the
  default" **and nothing enforces that.** It is a comment; a comment is advisory. Adding
  `--code-only` to `.claude/fast-test.cmd` would silently weaken the strictest check in the
  project and no gate would notice. This is precisely the README-"no network"-badge shape from
  `#32a`, reproduced by me one session after fixing it. Scheduled.

## 4. meta-review

- **CHECK 1 (new instance of the fixed class):** yes, twice, and both are recorded above - `#47`
  (a new unenforced assertion, created by the commit that fixed an unenforced assertion) and the
  stale `#45` row. Standing check 1 earning its place for the third time this session.
- **CHECK 4 (READ the ledger, do not reconstruct):** the newest two `run_selftests` rows are
  **polluted**. `05:49:54Z FAIL ['python-floor']` is my own deliberate disarm probe;
  `05:56:18Z FAIL [5 gates]` is the corrupted push-gate run from `#46`. `#44` fixed exactly this
  class via `UNBLUFF_LEDGER_OFF` - and I did not set it for my probe, and the hook path does not
  set it either. **The fix did not cover the paths that then polluted the ledger.** Recorded here
  rather than edited out: rewriting a ledger to look clean is the failure it exists to prevent.
- **CHECK 6 (exactly ONE canonical order):** **FAILED.** `docs/NEXT_SESSION_PROMPT.md` existed -
  66 lines calling themselves "the single canonical recommended order", for **v1.0**, dated
  2026-08-16, citing a 38/38 suite. `#10` has forbidden this for two days. **Worse: earlier in
  this same session I told the user the file was ABSENT** - I checked the repository root and it
  lives in `docs/`. A verification that looks in the wrong place returns a comforting answer.
  Reduced to a pointer.
- **CHECK 3 (optimization):** `hooks/pre_push_gate_selftest.py` is 1131 lines, the largest file in
  the repo and the one carrying `#46`. Its size is why the defect had room to hide.

## Deviations, including the ones that make this report look worse

- The delta scope means **nothing here re-checks the eight gate rows closed before `9bcbbbd`**.
  Those were audited at that commit and have not been re-read.
- `1,215 lines of new Python` is still unverified and is now two sessions old.
- `mutation_sweep` has not run since `2026-08-20T17:28:15Z` - now **16 commits** stale at `20647d7`
  (13 when first reported this morning; it was 15 when this line was drafted and the close commit
  itself made it 16 - which is why a count belongs next to the commit it was taken at). It cannot be run until `#46` is fixed.
- The stray local branch `feature` and six fixture commits from `#46` still exist as refs. Left in
  place deliberately: they are the evidence, and deleting them is a destructive op that belongs
  with the `#46` fix, not with its diagnosis.
