# Consistency audit - 2026-08-25

**Scope:** what THIS session authored - `1e12792..d39559d`, deliverable `docs/PLAN.md`.
**Tolerance:** rel 0.01. **Sources indexed:** `file_size_baseline.json`, `gate_runs.json`, plus
live derivation from git for anything those two do not carry.

## STEP 1 - mechanical pass, and its denominator problem

`scripts/audit.py --deliverable docs/PLAN.md --sources file_size_baseline.json,gate_runs.json`
returned **[A] 88**, [B] 0, [C] 0, [E] 0, [F] 0 over 237 numbers (186 checked).

**88 is not a finding, it is a measurement artifact, and saying so is the point.** The source set
was two JSON files; the plan's numbers come mostly from git (line counts, commit counts, dates).
Every one of those is trivially "unmatched" because its source was never indexed. That is exactly
the failure the session protocol names - *a denominator that reflects the source set's coverage
rather than the prose's accuracy*. Reported rather than quietly re-scoped, then re-scoped.

## STEP 2 - re-scoped and adjudicated one by one

Numeric claims this session ADDED to the plan, each re-derived at 2026-08-25T01:42:33Z:

| claim | derived | verdict |
|---|---|---|
| "4 of 6 wired hooks STALE" | **5 of 6** | **DRIFT - fixed** |
| "about 228 lines" (registry block) | **219** (AST) | **DRIFT - fixed** |
| "44 commits behind `origin/main`" | 44 | OK |
| "8 files" in the isolation population | 8 | OK |
| "851/851, zero ratchet headroom" | 851 actual, 851 baseline | OK |
| "1003 -> 1026", "1192 -> 1213", "794 -> 803" | match baseline | OK |

**Both drifts were self-inflicted, and the first one matters more than its size.** `4 of 6` became
`5 of 6` *because of this session*: item 3's scrub edited `meta_audit_on_stop`, which was one of
the two hooks still matching the wired copy. So the trajectory is **2 -> 4 -> 5**, and the honest
reading is that **this session made the live machine MORE stale, not less**, and will keep doing so
until item 2's pull runs. Only `stop_dispatcher` is still live. The plan now says that.

## STEP 3 - reasoning pass

- **Cross-section consistency.** The `--code-only` contract is described in three places
  (`.claude/pre-push.cmd`, `MACHINE_STATE`'s comment, item 5). All three now agree that exclusion
  applies to the VERDICT only. No drift.
- **Interpretation.** Item 3 previously read "three run a mutating verb"; the gate found eight.
  The narrative was corrected to say so, and to name the correction as being about my method (a
  roster derived over `hooks/` only, called DERIVED) rather than about the code.
- **Claim support.** "M10 is fixed" is supported by a mutation control, not by the selftest alone -
  neutering `strip_comments` turns exactly the two M10 cases red and names them. Recorded because
  "the selftest passes" is the precise claim this repo distrusts.

## Deviations

- The `[A] 88` figure is left in this report rather than suppressed; a reader who only saw the
  re-scoped table would not know the first pass was mis-scoped.
- `1,215 lines of new Python` remains unverified and is now three sessions old. It lives in the
  retired plan, so it no longer misleads the live one, but it was never derived.
