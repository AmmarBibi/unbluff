# Meta-review - 2026-08-28

**Subject:** commits `34f82eb..f10a242` - items 7 (registry cut), 24 (trajectory), 17
(tier-freshness), plus the coverage work.
**Plan:** 32 items (0-31) at entry, **36 (0-35) at exit**, contiguous by parse.

CHECK 1 was run as its OWN grep (`PARK|DEFER|TODO|OPTIONAL|candidate|later`), a different question
from the completeness pass's optional-forever sweep, which ran separately.

---

## CHECK 1 - parked but unscheduled

14 hits; 13 are the ordinary English words `later` / `candidate` inside scheduled rows, or
quotations of a marker (item 18 quotes `[TODO]`/`[TABLE]` because it documents the false-positive
class). One is substantive and already correct:

- **L490** *"OPTIONAL - both files are now declared in `REQUIRED_HOOKS`"* - a resolved
  adjudication, not a parked item.
- **L1054** *"Deferring it also means a SessionStart with no candidate pays nothing"* - a design
  rationale inside a scheduled row, not a deferral of the row.

**Zero parked-but-unscheduled items.** (The completeness pass separately found and promoted the
one real soft-defer, item 27's "consider making that mechanical" -> item 32.)

---

## CHECK 2 - instance vs mechanism (the focus of this run)

Every notable fix this session, asked: *did we fix the instance, or install a mechanism?*

| fix | form | verdict |
|---|---|---|
| registry cut moved `AUX_GATES` out of the orchestrator | STRUCTURAL - adding a gate no longer edits `run_selftests.py`, proved by `964899b`'s diffstat | **MECHANISM** |
| the two source-text readers repointed | both FAIL CLOSED, and each is covered by an existing gate that goes red (guard selftest -> `0 of 20`; sweep -> harness error) | **MECHANISM (existing)** |
| MODE-1's verifier | 6-tuple `verify`, pinned by the sweep | **MECHANISM** |
| `head()` local-time-labelled-Z fail-open | mutation `TF-UTC` | **MECHANISM** |
| `files_withheld: 0` -> `files_no_count` reason | asserted in `_selftest_item24`; the sibling `entry_stale` side is mutation-pinned by TR-ZERO | **MECHANISM (partial - the files_ side is battery-only, not mutation-pinned)** |
| scratchpad probes for the trend module | MOVED into `hook_divergence_selftest.py` and mutation-pinned | **MECHANISM** (this was the REMEMBER->ENFORCE conversion) |
| README 44 -> 45 | caught by `readme-fresh` before I noticed | **MECHANISM (pre-existing, worked)** |
| item 7's `20 rows` stale count | corrected by hand and labelled an INSTANT | **INSTANCE** - `numbers_match_on_write` exists but did not fire on this; the durable form is item 15's rule applied where no gate reaches |
| standing check 4's stale "NOT wired" example | corrected by hand | **INSTANCE, and left as one deliberately** - a gate on present-tense liveness claims in prose would be a false-alarm generator, and the standing bar is that a guard firing on correct work gets switched off. Judgment calls stay judgment calls. |
| **the UTC assertion that printed "did not run" and returned PASS** | assertion made self-contained | **INSTANCE ONLY -> SCHEDULED as item 35** |

### The one that mattered: item 35

`check_tier_freshness`'s UTC assertion compared `head()` against the repo's own `%cI`. In
`mutation_check`'s scratch tree - `git init -q`, `git add -A`, **never commits** - `git show -s
HEAD` fails, so the assertion printed *"the UTC assertion below did NOT run"* and the selftest
returned 0. **`TF-UTC` SURVIVED against it, twice.** The comparison was correct and was never
reached; nothing distinguished "checked and passed" from "could not check".

The instance is fixed. The CLASS is not, and it is available to every assertion that reads a file,
shells out, or needs a fixture. The repo has paid for this shape before - `gate_ledger.read()` has
three outcomes instead of two for exactly this reason, and `check_file_size` carries FS-CANNOTRUN.

Scheduled with its trap: the fix must NOT fire on `SKIPPED (posix only ...)`, which is an
ADJUDICATED skip the harness already reports separately. The distinction is whether the skip was
declared in advance or discovered at runtime.

---

## CHECK 3 - optimization (numbers, not vibes)

| file | lines | note |
|---|---|---|
| `run_selftests.py` | 444 | was 655; item 7. Real headroom restored. |
| `hooks/piped_gate_guard.py` | **800** | AT the limit, zero headroom - item 27 |
| `tools/hook_divergence_report.py` | 732 | was 803; split rather than shaved |
| `tools/hook_divergence_trend.py` | 105 | new |
| `tools/check_tier_freshness.py` | ~366 | new |
| `tools/gate_registry.py` | ~300 | new |
| recorded offenders | 4, none grew | `pre_push_gate_selftest` 1213, `fast_test_on_stop_selftest` 1026, `duplicate_registration_check` 858, `fast_test_on_stop` 851 |
| population | 69 `.py` (source: git) | 68 -> 69 this session |

**Duplication, deliberate and recorded:** the `ast` walk reading `AUX_GATES` exists twice
(`mutation_check`, `piped_gate_guard`). Not unified, with the reason written in
`gate_registry.py`: `piped_gate_guard` SHIPS to `~/.claude/hooks/` where `tools/` does not exist,
so one implementation would have to be a conditional import whose two branches nothing exercises
together. Eight duplicated lines is the cheaper defect and both copies fail closed.

**Cost:** four full sweeps, ~3 hours of the session. Two of the four earned it outright (MODE-1,
TF-UTC). See the source-coverage artifact on 7.1 - the allocation, not the spend, is the finding.

---

## CHECK 4 - missing / wrong. READ THE LEDGER, do not reconstruct it

Read via `tier-freshness` (item 17, built this session precisely so this check stops being a human
reading JSON by hand at the close), against HEAD `f10a242`:

- **`integration` last ran 2026-08-27T17:15:24Z - predating ALL FIVE of this session's commits.**
  This session edited a wired hook, and `test_integration.py` installs and fires every hook. The
  tier had never seen this session's code. **ACTED ON: re-run at HEAD, 34/34 rc=0.** This is
  exactly the failure CHECK 4 exists for, and it is the second consecutive session in which this
  tier was the one behind.
- `false_alarm_scorer` 2026-08-20 - eight days. Already item 31 (declared tier whose registered
  mode never reaches its `record()` call).
- `mutation_sweep` 09:03:55Z PASS `executed=228` - the ledger independently corroborates sweep 4's
  count, and **corrected a number I had written**: I recorded sweep 4 as "08:18:41Z", which is its
  START. The ledger gives the end. Plan now reads `08:18:41Z-09:03:55Z, 45m14s`.
- The ledger also holds the TF-UTC story in its own words: two `check_tier_freshness` FAIL rows
  (08:10:58, 08:12:01) then PASS (08:14:58). The record shows the probe being wrong twice.

Nothing else missing at the product level. No capability silently refuses; the one gate that fails
(`hook-provenance`) does so correctly and is excluded by `--code-only` with its reason named.

---

## CHECK 5 - improvements for a better outcome

1. **`--release` is built and has never been run.** `tier-freshness --release` is the blocking
   half of item 17 and nothing invokes it. The natural home is the pre-push gate, where "has this
   worktree verified every tier at the commit being pushed?" is exactly the right question. Not
   scheduled - it is a wiring decision for the user, and wiring a blocking gate deserves an
   explicit choice (item 5 is the precedent for asking first).
2. **The trajectory is printed but never consulted.** `hook_provenance`'s trend line is a real
   series now; nothing reads it back at a milestone. Cheap follow-on once there are enough rows.
3. **`mutation_sweep_filtered` is recorded but is in no `RECORDING_TIERS` row**, so
   `tier-freshness` cannot ask about it. Correct today (it is the same tier in a narrower mode)
   but worth stating, because a filtered run PASSING is not evidence about the 227 entries it
   skipped - the harness says so in its own output and the ledger does not.

---

## CHECK 6 - mechanism health

- Suite **45/45 rc=0** under `--code-only`. `hook-health` rc=0.
- `hook-provenance` fails without `--code-only`, correctly: this session edited a wired hook, so
  the live clone is genuinely behind until this branch reaches `main`. MACHINE_STATE, named.
- **Exactly ONE canonical order**: `docs/PLAN.md`, 36 rows, 0-35, contiguous by parse. No
  competing sequence block. All six rows added this session (32-35 plus 33, 34) were placed IN
  that list, not in a side block.
- Four audit artifacts written this session, each to its own procedure.

---

## Order refresh (always last)

DONE this session: **7** (both halves, sweep-verified), **17**, **24**. **8 UNBLOCKED** by 7.
Open, cheapest-first as the session prompt had it, with the new rows placed by materiality:

`9, 8, 12, 11, 18, 14, 13, 16, 19` then `26, 29, 30, 31, 27, 32, 34, 35` with **33 first among
them** - it qualifies the confidence of everything this session marked DONE, and section 6 says to
do it BEFORE reporting a unit as sound, not after.

## Verdict

One instance-only fix promoted to a mechanism row (35 - the sharpest lesson of the session).
One stale tier found by reading the ledger and immediately re-run to green (34/34). One number
corrected from the ledger (sweep 4's timestamp). Zero parked-but-unscheduled items. Mechanisms
healthy; one canonical order, refreshed.
