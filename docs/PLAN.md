# unbluff - the plan

**Scope changed 2026-08-24: this is a tool I use, not a product I ship.** The previous plan is
archived verbatim at [plan_v140_retired](audits/plan_v140_retired_2026-08-24.md) - 284 lines,
12 gates, written against a premise that no longer holds. Nothing was deleted; it was retired.

## Why it was re-cut, with the number that decided it

The old plan's premise was its own second paragraph: *"Public MIT repo, maintained partly as a
career artifact - which means an unpublished month delivers none of its point."* Every gate
descended from that. With no release, most of them serve nobody.

Measured on the v1.4.0 branch, `b6cc6cc...3354c0b`, taken 2026-08-24T20:32:53Z and re-verified
21:17:11Z. Pinned to that commit for two reasons, both learned the hard way today: `HEAD` is a
moving ref and this table was first written citing it - which made it false the moment the next
commit landed - and `3354c0b` is the last commit BEFORE this re-cut, so the measurement does not
fold its own response into the thing being measured. At `58ad05c` the same range reads
docs 2,264 / total 6,945; only the `docs/` row moves, and the headline is 12.8% instead of 13.0%.

| area | lines | share |
|---|---|---|
| `tools/` + `tests/` - gates that check the gates | 2,455 | **36%** |
| `docs/` - plan, audits, evidence | 2,139 | **31%** |
| `README` / `install` / CI / `CHANGELOG` - mostly shipping | 1,338 | 20% |
| `hooks/` - the 7 things that actually run | 735 | 11% |
| `skills/` - the 4 things actually invoked | 153 | **2%** |

**13% of the release branch touched what is actually used.** And of that session's four defects,
**three were in the checking instruments**, not in the hooks - which is
`tooling-discipline.md` section 4 ("a green result that cannot fail is not evidence") arriving as
a measurement rather than a warning. The ladder had started climbing itself.

## What unbluff IS, now

Seven hook commands wired in `~/.claude/settings.json`, running from
`C:\Users\ammar\Downloads\unbluff` - **verified live 2026-08-24T20:32Z**, plus a global
`core.hooksPath` at `~/.claude/githooks`, plus four skills `install.py` copies into
`~/.claude/skills`. That is the product. Everything else is scaffolding around it.

**BUILT IS NOT LIVE, and this plan no longer says by how much.** The count is DERIVED and
PRINTED by `hook-provenance`, as of item 15 (2026-08-26):

```
python tools/hook_divergence_report.py
  BUILT IS NOT LIVE: N of M entry points stale, P of Q hooks/*.py
```

**No number is written here on purpose.** It was hand-counted five times and was wrong five
times, and each correction fixed the NUMERATOR while the denominator stayed scoped to whatever
the author had in mind. Ask the gate.

History of this one number, kept because it is the clearest worked example of the defect this
whole file is about - and it is HISTORY, not current state:

| written | claimed | what was actually wrong |
|---|---|---|
| 2026-08-24T22:06Z | 2 of 6 | numerator: only the two hooks built that afternoon |
| 2026-08-24T23:06Z | 4 of 6 | numerator again |
| 2026-08-25T01:42Z | 5 of 6 | numerator again; the 6 was "files I worked on", not a population |
| 2026-08-25T02:19Z | 5 of 10 | denominator corrected once - still missing 5 hooks that RUN |
| 2026-08-26T19:35Z | 6 of 11 | ditto, plus `piped_gate_guard` newly wired while stale |
| 2026-08-26T20:34Z | **derived** | population is **16**, not 11 |

The last row is the finding. `stop_dispatcher.HOOKS` has FOUR children and was counted as two;
`post_tooluse_dispatcher` has a table of its own - `plan_defer_guard`, `numbers_match_on_write`,
`timing_claim_guard` - that no count ever included. **Five hooks that run on every matching
event sat outside the denominator through five hand-counts and three consistency passes.**

Two further things the derived count says that no hand-count did:

- **A `git pull` in the live clone could never take it to zero**, and the plan predicted it
  would. The live copies are the MAIN worktree of THIS SAME repository tracking `main`; the work
  is on a branch ahead of it. Pulling delivers `origin/main`, not unpushed commits. The gate now
  prints the branch relationship next to the number, because a number that invites the wrong
  remedy is worse than no number.
- **Line endings are not staleness.** A raw byte compare called 10 of 28 files stale when 8
  were: `cap_shapes.py` and `capped_report.py` differ from the live copy by 756 and 171 bytes
  and are the same commit. `_same_repo_same_bytes` had that bug too, so this gate could have
  flagged a correct linked worktree as FOREIGN.

**Item 2 is DONE (2026-08-26T20:24:36Z).** The config half landed 2026-08-24T23:05:49Z -
`core.bare`, the local `core.hooksPath` pointing at a deleted temp dir, the `t@t` identity and
the stale `branch.feat/enforcing-verify.*` section are all unset, with the full prior config in
that commit message as the rollback record. The `git pull --ff-only`, blocked by the
tool-permission classifier for three sessions, ran on the fourth attempt: **`b6cc6cc` ->
`d44138c`, 44 commits, 0 behind `origin/main`, clean tree.**

**It did not turn `hook-provenance` green, and that is the session's finding rather than a
leftover.** The live copies are the MAIN worktree of this same repository on `main`; this branch
is 15 commits ahead and has never been pushed, and those 15 commits touch 9 `hooks/*.py`. A pull
delivers `origin/main` and cannot deliver what was never pushed. The condition clears on a
**push or merge**, not on a pull. The count and its cause are now printed by the gate - see
BUILT IS NOT LIVE above.

(This paragraph used to carry its own copy of the headline count and drifted in four consecutive
sessions - "all four stale hooks", then "five ... 12 of 26", then "6 of 11 ... 14 of 28", each
one silently disagreeing with the table it copied. **A number restated in a second place is a
number that will drift in one of them.** Item 15 removed both copies; the gate is the only
source now.)

## The bar

**Does this make my sessions better?**

Replaces *"Would I defend this release under adversarial review?"*, which was a shipping bar. A
change that only makes the repo more defensible to a stranger is no longer worth doing.
Materiality still decides ORDER, never WHETHER - anything kept here gets built.

## Open - and this list is deliberately short

0. **`close_skills_guard` enforces RECENCY, not just presence.** **DONE 2026-08-24.** The
   guard asked "were all four skills invoked since the last user message", which is satisfiable
   by an audit of a state that no longer exists - MEASURED on this hook's own session: skills at
   15:54, then a guard fix, a full plan re-cut and a merge to `main`, guard PASSED, and
   re-auditing that tail found four defects all authored after the ritual. It now also fires if
   any file was WRITTEN after the last required-skill invocation, excluding the close artifact
   itself. Reads and tool_results do not count (a guard that reddens its own verification pass
   gets disabled); re-running the four re-closes the window; a missing skill still takes
   precedence. Six cases probed against the real shape BEFORE the fix, five pinned in the
   selftest, and mutation-probed with a matched control - neutering the rule turns it red
   naming the right case. This is the REMEMBER-vs-ENFORCE conversion: the instruction was prose
   in a session prompt, and prose is advisory.
1. **Land the branch.** **DONE - [PR #3](https://github.com/AmmarBibi/unbluff/pull/3) MERGED
   2026-08-24T20:55:41Z**, so `main` now carries the moved-clone fix, the scanned-PDF fix, #45 and
   #46. Verified by asking GitHub, not by inferring it from a local ref. Marked here 2026-08-25
   because the row still read OPEN after the merge - a plan that lags the world it describes is
   the same defect as a stale count, one level up.
   **The branch is ahead again**: 4 commits (items 3, 4, 6, 7 and the config repair) are on
   `feat/enforcing-verify` and not on `main`, so a second PR is owed before they are live.
2. **Repair the main clone's git config.** **DONE 2026-08-26T20:24:36Z.** The config half landed
   2026-08-24T23:05:49Z: `core.bare=true`, a local `core.hooksPath` pointing at the deleted
   `%TEMP%/tmp7dq12juu/myhooks`, a `t@t` identity and a stale `branch.feat/enforcing-verify.*`
   section - all four #46 residue, all unset, verified by re-reading the config and confirming
   the clone resolves to the global `~/.claude/githooks` as `AmmarBibi`, tree clean at `b6cc6cc`.
   The `git pull --ff-only` had tripped the tool-permission classifier three sessions running; it
   was attempted a fourth time and **went through**: `b6cc6cc` -> `d44138c`, 44 commits, 56 files,
   clean tree, 0 behind `origin/main`. Three sessions of "Claude cannot run this" were three
   sessions of not re-trying a classifier decision that had changed.
   **It did NOT clear `hook-provenance`, and that is a finding, not a leftover** - see item 20.

3. **Make the per-hook `--selftest` form isolated.** **DONE 2026-08-25.** All 8 files that run
   a MUTATING git verb from a `--selftest` path now scrub, enforced by item 4's gate rather than
   by memory: `meta_audit_on_stop`, `fast_test_on_stop_selftest`, `pre_push_gate_selftest`,
   `pre_push_gate` (by import delegation), `check_review_freshness`, `hook_divergence_report`,
   `no_regression`, `noregress_selftest`.
   **My hand-derived population was 3. The gate found 8.** The five I missed were all in `tools/`,
   including `check_review_freshness` - which `git_isolation.py`'s own header names as one of the
   six incident instances. I had called my roster "DERIVED"; it was derived over `hooks/` only,
   which is a scoped denominator wearing the word derived. That is the finding, not the fix.
   Placement was forced by the ratchet and is recorded: the scrub sits in the `*_selftest` modules
   because `fast_test_on_stop.py` has ZERO headroom at 851/851, and in `tools/` it needs no
   ImportError fallback because `git_isolation` is a sibling there.
   **Standing caveat carried forward:** the underlying `GIT_DIR` mechanism is WELL-EVIDENCED, NOT
   PROVEN, for this incident - see the note under item 4's history and `git_isolation.py`'s header.
   The scrubs are correct regardless; what is unproven is that GIT_DIR was the causal path.
4. **Pin the #46 control's own wiring.** **DONE 2026-08-25.**
   `tools/check_selftest_isolation.py`, registered ENFORCING plus a paired `--selftest`. It walks
   the AST and asks three questions with printed denominators: which selftests run a MUTATING git
   verb (derived, never listed), is a scrub actually REACHED before their fixtures, and do the
   inline fallback lists still match `git_isolation.GIT_REDIRECT_VARS` exactly. Item 4's precise
   case - `scrub_environ()` moved out of `main()`'s direct body into an uncalled helper - is a
   named failure.
   **It paid for itself on its first run.** My hand-derived population was 3 files; the gate found
   **8**, including `tools/check_review_freshness.py`, which `git_isolation.py`'s own header names
   as one of the six incident instances. All 8 are now scrubbed. Read-only git callers are
   deliberately excluded, so `fast_test_on_stop.py` - which has zero ratchet headroom - never
   enters the population.
   Two of its own defects were caught by running it: an exact-name roster missed the `_scrub_environ`
   alias its companion script had just inserted (fixed to match by shape), and it flagged
   `pre_push_gate.py`, whose only mutating verb is production `install_global()` and whose
   `--selftest` delegates to a module that scrubs at import - so it now resolves import delegation
   rather than firing on correct work.
5. **Decide whether to wire `piped_gate_guard` at all - and only then fix its `pipefail` disarm.**
   **DECIDED AND DONE: WIRE.** The user chose WIRE on 2026-08-25 and it is now registered as
   **`unbluff:piped-gate`**, PreToolUse, matcher `Bash|PowerShell` - the matcher DERIVED from the
   guard's own `SHELL_TOOLS` exactly as `install.py` derives it, rather than the literal `"Bash"`
   that was PGG-PS's defect. `~/.claude/settings.json` backed up first to
   `settings.json.bak-2026-08-25-item5`; hook-health went 30 -> 31 commands and reports
   `1 wired clone(s) config-checked` with **zero MACHINE-SANITY problems** - it reports 8 problems
   overall, all of them stale-root registrations from running out of the worktree, which is item
   2's condition and not item 5's. (This sentence read "with zero problems" until 2026-08-26,
   which is true only under the scoped reading and false under the plain one - caught by the close
   consistency pass re-reading the live output instead of the prose.)
   **PROVEN where it ships, both directions, against the copy that actually runs:**
   `python run_selftests.py | tail -5` -> **rc=2, blocked**, naming `PIPESTATUS[0]` and
   `set -o pipefail` as the fix. Control `ls -la | head -5`, no gate token -> **rc=0, silent.**
   **CAVEAT, and it is the BUILT IS NOT LIVE problem again - THIS WIRING MADE THAT NUMBER WORSE.**
   `piped_gate_guard.py` is stale, so the wired copy is the PRE-M10 version: the main case fires
   (proven above), but the commented-`pipefail` disarm is still live in the code that runs until
   item 2's pull. The M10 fix exists on this branch and is inert on this machine.
   **A DEFECT IN THE WIRING ITSELF, found 2026-08-26 by the close source-coverage pass and fixed:**
   the group's `id` was written `unbluff-piped-gate`, with a HYPHEN. `install.ID_PREFIX` is
   **`unbluff:`**, with a COLON, and `--uninstall` selects groups by
   `str(g.get("id","")).startswith(ID_PREFIX)` - so **the hand-written group would have survived an
   uninstall**, an orphan PreToolUse hook invisible to the tool that manages it. Corrected to
   `unbluff:piped-gate` and verified against install.py's OWN predicate rather than a reading of
   it: `uninstall WOULD remove it: True`, field set identical to install's. The guard was
   re-probed after the change and still fires both directions. This is the "registered once, from
   the wrong root" class that `stale_root_registrations` exists for, one level over: a
   registration that WORKS but is unmanageable. Found by asking what `install.py` would write that
   I did not - which is the entire value of running source-coverage against the DESIGN.
   And wiring it **moved the denominator**: `piped_gate_guard` was not an entry point before, so
   the population went **10 -> 11 and the stale count 5 -> 6** (derived 2026-08-26T19:35:02Z at
   `1443a59`). The plan's own sentence - *every session that fixes something makes the live machine
   MORE stale* - is not a metaphor; this is the mechanism, and item 5 is the instance. The first
   hook wired since M10 was written is itself the argument for the pull.
   Evidence that decided it, refreshed 2026-08-25T01:15:51Z:
   Re-derived, not trusted: it is wired **0 times** in `~/.claude/settings.json`, so its defect
   currently costs nothing - which is why fixing it first would have violated standing check 4.
   **What changed is the evidence FOR wiring it, and it is first-person.** Across 2026-08-24/25 I
   read `$?` after piping a gate into `head`/`tail` **four times**, and at least twice it returned
   0 over a real failure - once reporting `rc=0` while the same run printed `SELFTEST FAILED`, and
   once masking a `SWEEP_RC=1`. Every instance was caught by reading the OUTPUT, never by the exit
   code. That is precisely the hook's purpose, observed four times in two days on the maintainer's
   own commands, which is a stronger case than any argument from principle.
   **M10 IS NOW FIXED (2026-08-25), so the pairing constraint is discharged and wiring is a
   one-line decision rather than a project.** `_is_protected` strips shell comments before asking,
   quote-aware, so a commented `# remember set -o pipefail` no longer converts the DENY into an
   allow - and neither does a trailing `# check PIPESTATUS` for the "anywhere" words. Both
   directions probed, in both dialects, plus an OVER-STRIP control proving a quoted `#` does not
   swallow a real protector after it. Mutation-proven: neutering the strip turns exactly the two
   M10 cases red and names them.
   One KNOWN LIMIT adjudicated rather than left to be rediscovered, pinned as **PG-QUOTED**: after
   stripping, this is still a substring test, so `echo "# pipefail"` reads as protective.
   Deliberate - tightening it to `set -o pipefail` would reject `set -euo pipefail` and
   `bash -o pipefail -c`, and start firing on correct work. Exposure is small because the guard
   only speaks when a GATE TOKEN is already present.
6. **`fast_test_disclosure` records its marker before printing.** **DONE 2026-08-25.**
   Print moved ahead of the record, so an unwritable `STATE_DIR` can no longer silence the #25
   disclosure permanently and silently. PROVEN with a matched control: pre-fix, unwritable ->
   SILENT; post-fix, unwritable -> discloses, and it names the untrusted surface (`jest --ci`
   from `scripts.test`) rather than the `npm test --silent` wrapper.
   The sibling notices in `fast_test_on_stop` deliberately do the opposite - record first, stay
   silent if they cannot - and that stays right for them: they are nags, and a nag that repeats
   forever gets the hook deleted. This one is a security disclosure, so the trade inverts.
   Note for the record: the probe was INVALID on its first two writes (wrong entry point, then
   wrong `source` constant) and both times returned an answer that looked like a finding.
7. **Split `run_selftests.py`.** **PARTIAL 2026-08-26 - the headroom is bought, the REGISTRY cut
   this item actually specifies is NOT done and still waits on a clean sweep.** Read the two
   halves separately before marking this row anything else.
   **What landed (2026-08-26T20:51Z):** `selftest()` -> `run_selftests_selftest.py`, 803 -> 655
   lines, removed from the file-size baseline by the ratchet's own rule. **This is a DIFFERENT
   cut from the one specified below, chosen precisely because it does not touch the trap:**
   `AUX_GATES` does not move, so `mutation_check.aux_gates()`'s `ast.literal_eval` of this
   file's source text keeps working, and no sweep baseline is needed to verify it honestly. The
   seam was measured before cutting - ZERO pinned mutation anchors inside `selftest()`, no
   parent-global rebinds, and `main()` stays put for `check_selftest_isolation`'s assertion.
   **What that does NOT achieve:** this item's stated goal is *"after the move, adding a gate
   stops touching the orchestrator at all."* It still does - `AUX_GATES` and `NOT_A_GATE` are
   still here, and this session added a `NOT_A_GATE` entry to prove it. What changed is only
   that there are now 145 lines of headroom instead of 6, so the next gate registration is no
   longer a file-size failure.
   (The two files measured **667 and 321 AT THE SPLIT. THAT IS AN INSTANT, NOT A CURRENT
   FACT** - they are 681 and 351 within the same session, because the `sync_phrase()` fix and
   the M8 probe landed forty minutes later. The close consistency pass caught the drift; the
   convention for saying so is `file_size_baseline.json`'s own. Current sizes come from
   `check_file_size`, not from this line.)
   **Why it was done now rather than in its scheduled slot:** it became hard-blocking. Item 15
   split `hook_divergence_report.py`, the new sibling had to be classified in `NOT_A_GATE`, and
   at 803/800 there was no room to write the line. The 08-25 baseline note predicted this in
   those words - "the orchestrator having only 6 lines of headroom is the actual finding here,
   and it will bite the next person who adds a gate." It bit on the next session.
   **Still open below, unchanged:** the registry cut, its trap, and the forced order.

   New 2026-08-25. It is a recorded 803-line offender, but the
   overage is not the finding - the finding is that the orchestrator had SIX lines of headroom, so
   registering one gate with its reasoning pushed it over and the next person hits the same wall.
   **Scoped, and its trap is already mapped so nobody discovers it mid-refactor.** The right cut is
   the REGISTRY - `AUX_GATES`, `NOT_A_GATE`, `MACHINE_STATE`, `SELFTEST_IS_THE_GATE`,
   `RECORDING_TIERS`, lines 55-273 - **219 lines, derived by AST at 2026-08-25T01:42:33Z**, not the "about 228" first written here - into `tools/gate_registry.py`. That is
   exactly the part that grows every time a gate is added, so after the move adding a gate stops
   touching the orchestrator at all.
   **THE TRAP, found 2026-08-25 by looking before cutting.** `tools/mutation_check.py:155`
   `aux_gates()` does NOT import the registry - it `ast.literal_eval`s the assignment out of
   `run_selftests.py`'s SOURCE TEXT, deliberately, so the rows it reads are the SCRATCH tree's.
   Move `AUX_GATES` and it returns `"no AUX_GATES assignment in ..."`. It fails CLOSED, so this
   surfaces as a red harness rather than a silent pass - but it means the split edits **the
   instrument that certifies every other fix**, and that cannot be honestly verified without a
   full sweep. The sweep is 16+ commits stale and blocked behind item 2.
   **So the order is forced: item 2's pull, then a clean full sweep, THEN this.** Doing it before
   there is a green sweep to compare against means changing the certifying instrument with no
   baseline - which is the one move `tooling-discipline` section 4 is entirely about.
   (`tools/check_readme_fresh.py:190` also does `from run_selftests import AUX_GATES`; that one is
   fine, a re-export keeps it working.)
   **THE FORCED ORDER IS NOW FULLY SATISFIED - THE REGISTRY CUT IS UNBLOCKED.** It waited on
   item 2's pull (ran 2026-08-26T20:24Z), then on a clean full sweep, then on `mutation_sweep`
   as the baseline to compare the cut against. All three landed:
   - suite **44/44 rc=0** (2026-08-27T06:30Z)
   - `integration` **34/34 rc=0** (06:28Z, re-run because it was stale BY CONTENT)
   - **`mutation_sweep` 2026-08-27T06:24:42Z PASS** - **223 of 225 executed, every executed
     mutation CAUGHT, 0 skipped, 0 unproven**; the 2 remaining are not-runnable-on-this-platform
     (`pre_push_gate` #30, `fast_test_on_stop` #D10c) and are named as proven by the OTHER
     platform's job or nowhere. First PASS of this tier since 2026-08-20, six days.
   **This is the baseline the registry cut must be measured against.** Cut it next session and
   re-run the sweep immediately after: `mutation_check.aux_gates()` reads `AUX_GATES` out of
   `run_selftests.py`'s source text, so the cut edits the instrument that certifies every other
   fix, and that is only honest with a green sweep on both sides.

8. **Nothing enforces that `--code-only` stays off the turn-end command.**
   **BUILT AND PROBED, THEN REVERTED - BLOCKED BEHIND ITEM 7 by the file-size ratchet.** (Verdict
   hoisted into the header 2026-08-26 by the close sweep: it sat 20 lines down, so the row scanned
   as OPEN and could be picked up out of order - which is how it got orphaned the first time.)
   Was #47, ORPHANED by the 2026-08-24 re-cut and re-homed here 2026-08-25 by the close
   completeness pass.
   `.claude/pre-push.cmd` runs `python run_selftests.py --code-only`, and its own comment says the
   flag is "deliberately NOT the default". That is a comment, and a comment is advisory. Adding
   `--code-only` to `.claude/fast-test.cmd` would silently weaken the strictest check in the
   project and no gate would notice - verified 2026-08-25T01:43:40Z, grep across `tools/` finds
   nothing checking it.
   **Why it matters more than its size:** this is the README "no network" badge shape from #32a,
   created by the same session that fixed #32a, and then LOST by a plan re-cut - so it has now
   failed twice over, once as a defect and once as a bookkeeping error. It appears exactly once in
   `plan_v140_retired` and appeared ZERO times here until now.
   Fix: assert in `run_selftests --selftest` that the turn-end command does not carry `--code-only`.

   **BUILT AND PROBED 2026-08-25, THEN REVERTED - it is BLOCKED BEHIND ITEM 7, and the ratchet
   is what proved it.** Attempted out of order because it is small and the pull does not block
   it. It does not fit: adding it took `run_selftests.py` from **803 to 897 lines**, and
   `file-size` failed with *"grew 803 -> 897, and it was ALREADY over the limit. The ratchet only
   turns one way."* Reverted rather than re-recorded - `file_size_baseline.json` calls
   re-recording "THE LOOPHOLE IN THIS DESIGN" and says the next growth should be preceded by the
   split, and for this file the split IS item 7.
   **So this is item 7's finding arriving as a measurement rather than a prediction.** Item 7
   says the problem is not the 3-line overage but that the orchestrator has no headroom, so the
   next addition hits the wall. It did, on the very next addition, and the addition was 94 lines
   of a check this plan already wanted. Every route out is blocked the same way: a `tools/` gate
   still needs an `AUX_GATES` row, and the ratchet fails on ANY growth. `hooks/` auto-detection
   is the one path that needs no row - that is how `wired_clone_sanity` registered itself this
   session without touching the orchestrator - but a check on THIS repo's own `.claude/*.cmd`
   files is not a hook and does not belong there.
   The design is settled, so re-landing it after item 7 is minutes, not rediscovery:
   `code_only_placement_problems(claude_dir)` driven by a
   `CODE_ONLY_PLACEMENT = (("fast-test.cmd", False, "turn-end"), ("pre-push.cmd", True,
   "push-time"))` table; reads the command with `fast_test_on_stop._read_override` - **the SAME
   parser the hook that runs it uses**, so it asserts against what EXECUTES and there is no twin
   parser to drift; asserts BOTH directions, because checking only that turn-end lacks the flag
   leaves the twin free and silently dropping it from `pre-push.cmd` re-creates #45; and a
   missing file is 2 problems rather than silence. All four cases were SHOWN TO FAIL before the
   revert - weakened turn-end fires, stripped push-time fires, an absent directory yields 2, and
   a correct pair yields 0.

9. **Five guard families are hand-probed but NOT registered as mutation entries.**
   **SCHEDULED - BLOCKED behind item 2's pull -> a clean sweep, together with item 7.** (Verdict
   hoisted into the header 2026-08-26 by the close sweep.) Was four families;
   **item 10's controls were added 2026-08-25 by the close meta-review's CHECK 2**, because a row
   that names a fixed count silently stops covering whatever is built after it - the same
   scoped-denominator shape this plan keeps paying for). The fifth family is item 10's:
   `wired_clone_sanity`'s `--absolute-git-dir` derivation, its `has_worktree` gate, the composed
   fixture vocabulary, and the `(?!)` blind control - all hand-probed this session, none of them
   in `mutation_entries_{a,b}.py`. Originally found
   2026-08-25 by the close source-coverage pass, reading the design rather than the code.
   BUILT and enforced by their own selftests: `check_selftest_isolation`'s three questions each
   carry a negative control; M10 carries five cases plus an over-strip control; `PG-QUOTED` is
   pinned. **SCHEDULED gap:** `grep` over `tools/mutation_entries_{a,b}.py` finds **zero** entries
   for `strip_comments`, for any `scrub_environ` call site, or for the isolation gate.
   **Why that is not pedantry here.** `tools/mutation_check.py` exists because "the suite passes"
   was twice read as "the suite asks the right questions", and its own docstring says a test that
   stays green when you delete the code it covers is decorative. My controls were run BY HAND this
   session - neutering `strip_comments` turned exactly the two M10 cases red, neutering the scrub
   call was probed - and a hand-run control proves the test bites TODAY. It does not survive into
   the sweep, so a refactor six months from now that disarms them is caught by nothing.
   **Blocked on the same ordering as item 7**: a mutation entry is only meaningful once a clean
   full sweep exists to run it, and the sweep is stale and blocked behind item 2's pull. Order is
   therefore: item 2's pull -> clean sweep -> items 7 and 9 together.

10. **The item-2 config repair was an INSTANCE fix; nothing would catch it happening again.**
    **DONE 2026-08-25** - `hooks/wired_clone_sanity.py`, commit `60b9305`. (Marker hoisted into
    the header by the close sweep for stale DONE markers: the row led with its problem statement
    and buried the verdict seven lines down, so it scanned as OPEN. That is item 2's token-vs-body
    contradiction inverted, and a row you have to read to the middle of is a row that gets
    mis-sequenced.)
    Found 2026-08-25 by the close meta-review's CHECK 2 (instance vs mechanism).
    `git_isolation.fingerprint()` catches a fixture mutating a repo DURING a sweep, which is the
    upstream cause - but nothing ever asks whether THIS MACHINE's wired clone is currently sane.
    `hook_health_check` runs at SessionStart and does not look at git config at all (grep:
    zero hits for `core.bare` or `hooksPath`). So the exact state that sat there unnoticed - a
    non-bare repo marked `core.bare=true`, `core.hooksPath` aimed at a DELETED temp directory
    which silently disabled every git hook on the machine, and a `t@t` identity - would sit
    unnoticed again.
    **DONE 2026-08-25.** `hooks/wired_clone_sanity.py`, called by `hook_health_check.main()` at
    SessionStart, registered as its own gate (`wired_clone_sanity`) and swept weekly. It asks the
    three questions of every clone the machine wires hooks from, and the clones are **DERIVED
    from `settings.json`**, never named - a hardcoded path would check this machine and nobody
    else's. Fixture identities are DERIVED too, by scanning `hooks/` and `tools/` for the
    call shape that writes one: the population is exactly right by construction, because an
    identity no fixture here writes cannot have escaped from a fixture here. Verified against
    `git_isolation.py`'s own header - the scan over 50 files returns exactly `{t@t, t}`, from the
    3 files that write them. Measured live at 02:17:52Z: `1 wired clone(s) config-checked`, zero
    problems, whole hook 0.33s. **10 states asserted, 7 of them CONTROLS that must NOT fire**,
    plus 3 extractor and 5 totality cases.

    **THE PROBE EARNED ITS COST, three times, and none of the three were typos.**
    - `rev-parse --show-toplevel` FAILS on a repo marked `core.bare`, so the first version
      dropped the broken clone out of the roster entirely and reported nothing while the
      healthy-repo control still passed. **The defect made itself invisible to its own
      detector.** Fixed with `--absolute-git-dir`, which answers in both states; pinned by
      `the BROKEN repo is still in the roster`.
    - The extractor scans `hooks/*.py`, and the battery LIVES in `hooks/` - so its control
      identity was absorbed into the fixture vocabulary and the check began firing on the very
      control meant to prove it does not fire on correct work. Five controls red at once.
      **A grep guard must never search for a literal it contains**, and the first draft of the
      comment explaining that contained the literal. Fixed by composing the strings, the same
      technique `_flag = "--" + "selftest"` already uses in that file for the same reason, and
      pinned by `this file contributes zero identities`.
    - The blind-extractor CONTROL was not blind: it neutered the pattern with a sentinel WORD
      that is itself a literal in the scanned file, and `findall` on a group-less pattern
      returns WHOLE matches - so the "blind" extractor derived exactly one identity, its own
      sentinel. It then reported that production "passes silently", **a finding about the probe
      wearing the costume of a finding about the code.** Fixed with `(?!)`, and the control now
      asserts it is controlling before it asserts anything else.

    Three gates then caught three more things, which is the argument for running them rather than
    reasoning about them: **file-size** (the block took `hook_health_check.py` to 861 lines, so
    the checks MOVED to their own module per B3-P rather than being recorded as debt - item 7's
    finding arriving on the session that wrote item 7 down); **install-guard** (2 of 28 deleted
    files undetected, because the deliberate `try/except ImportError` fallback correctly reads as
    OPTIONAL - both files are now declared in `REQUIRED_HOOKS`, which is the one job that floor
    exists for); and **selftest-isolation**, twice - see items 11 and 12.
    KNOWN LIMIT, adjudicated rather than left to be rediscovered, pinned as **HHC-SETTINGS-ONLY**:
    the repo roster comes from `settings.json` alone, which is 7 of the 10 entry points that
    actually run. It is a limit on the DENOMINATOR and not on the checks - each repo is asked
    about its EFFECTIVE config, so a global `core.hooksPath` at a deleted directory is caught
    through whichever repo is examined - and `n_repos` is printed rather than assumed.

11. **`check_selftest_isolation` cannot see a mutating verb inside a CONCATENATED argument list.**
    New 2026-08-25, found while verifying item 10's narrowing of that gate rather than accepting
    its green. `mutating_verbs_in` walks Call nodes for string CONSTANTS, so
    `_git(["config", "--global"] + args)` yields **nothing** - and that call is
    `pre_push_gate.install_global()`, the code that writes `core.hooksPath` **globally, for every
    repository on the machine**. Verified both directions: the same call written as a flat list
    IS detected, and `sh(*(["config"] + rest))` is not.
    Not caused by item 10 and not hidden by it: `pre_push_gate.py` was in the population on the
    strength of a READ elsewhere in the file and was already adjudicated `scrubbed` by import
    delegation, so no verdict changed. But the gate has never actually seen the write it most
    needs to see. Fix: flatten `BinOp`/`Starred` argument nodes before extracting constants.

12. **That gate's POPULATION is decided by a prose mention.** New 2026-08-25, same investigation.
    Membership is `has a mutating verb AND the string "--selftest" appears in the file text` - so
    `hooks/wired_clone_sanity_selftest.py`, which builds real repositories with `init` and
    `config` writes, was **silently exempt from the gate that checks it scrubs**, purely because
    its docstring did not happen to use the flag. Fixed for that file by documenting the dispatch
    relationship it genuinely has, which is what its sibling already does - but the rule is the
    defect. Fix: membership should follow DELEGATION, the way the scrub verdict already does
    (`res["_deferred"]`), so a module reached from a `--selftest` path inherits it structurally.

13. **The heredoc trap is prose, and prose is advisory - it wants a hook.**
    Found 2026-08-25 by the close completeness pass, as a **silent gap**: the meta-review of
    2026-08-25 raised it as CHECK 5's third recommendation, and it appeared **ZERO times in this
    plan** until now. That is failure mode (b) - the audit named it, the plan never did, so
    nothing would ever have scheduled it. Same shape as item 8, which was orphaned by a re-cut.
    The cost is measured, not asserted: **four incidents in two days**, and they are not all
    loud. One put a literal TAB into this plan, inside the line documenting the path that broke
    the clone. The dangerous one was silent - backticks inside a `python -c "..."` string were
    COMMAND-SUBSTITUTED BY THE SHELL before Python saw them, the script printed its success
    message, and it wrote a file with every backticked filename deleted. Nothing failed.
    **FIFTH INCIDENT 2026-08-27, and it WIDENS THE SCOPE: it was not a heredoc.** A commit
    message was written with `printf '...'`, and `printf` treated the `%` in "68% -> 7.17s/72%"
    as a format specifier, died on it, and wrote a TRUNCATED file. `git commit -F` then
    succeeded on the truncated message: the commit is real, its body stops mid-word at
    `6.78s/68`, and its final paragraph and `Co-Authored-By` trailer are simply gone. **`git
    commit` reported success and the shell reported an error that scrolled past above it** -
    caught only by reading the message back, which is the remedy this rule already prescribes.
    Not amended: the commit was already pushed, and rewriting published history to tidy a commit
    message is a worse trade than recording it. `edabd81` is the instance.
    **So the guard cannot key on heredocs alone.** The family is *any inline content passed to
    a shell*: an unquoted heredoc, backticks inside `python -c`, AND a format string given to
    `printf`. The rule that would have caught all five is the simple one - content goes in a
    FILE written by the Write tool, then `git commit -F` / `python file.py`. A `PreToolUse`
    check for `printf`/`echo` writing a file that is then passed to `-F` is as mechanical as the
    heredoc case and covers the incident that actually happened most recently.
    This repo already converts exactly this kind of recurring prose into a hook, twice:
    `piped_gate_guard` (a gate piped into `head`/`tail` returns the pipe's status) and
    `timing_claim_guard` (a duration written as MEASURED with no control marker). A heredoc /
    inline-content guard is the third of the same family and belongs here more than anywhere.
    Scope it by MEASUREMENT, as both of those were: they fire on 4 of 15 and 18 of 109 real
    cases respectively, and a guard that fires on correct work gets disabled. The obvious
    candidate shape is a `PreToolUse` check on a Bash command carrying an unquoted heredoc
    delimiter, a backtick inside a double-quoted `-c` payload, or an apostrophe inside a
    single-quoted block - **and its false-alarm rate must be measured against real history
    before it is wired**, exactly as item 5's evidence was gathered.

14. **Item 10 checks the CONFIG slice of #46's residue. A stray linked WORKTREE is not checked.**
    Found 2026-08-25 by the close source-coverage pass, run against the DESIGN rather than the
    code - i.e. by enumerating the authoritative source (`git_isolation.py`'s incident account and
    `fingerprint()`'s own docstring) and reconciling it against what was built, rather than by
    re-reading item 10.
    `fingerprint()` names the FIVE classes the incident damaged: **HEAD, refs, config, index,
    worktrees**. Item 10 built a standing check for exactly one of them - `config`, and 3 of its
    4 fields. The gap is not that the others were rejected; it is that **they were never
    enumerated**, so nothing recorded a decision about them. That is the failure mode a grep can
    never find, because the plan did not mention them.
    Adjudicated per class rather than scheduled wholesale:
    - **`worktrees` - SCHEDULE.** `fast_test_on_stop_selftest.py:902` registered a linked worktree
      in the real repo under the system temp directory. That is residue with **exactly the shape
      item 10 already treats as material**: silent, persistent, and pointing at a path that no
      longer exists. It is decidable and cheap - `git worktree list`, flag any entry whose path is
      absent - and it cannot false-alarm on correct work, because a live worktree's path exists.
      Verified clean on this machine 2026-08-25T03:0Z: two worktrees, both present.
    - **`HEAD` / `index` - FINALIZED EXCLUSION.** Transient working state. A user legitimately has
      a moved HEAD and a dirty index; a standing check here would fire on correct work constantly,
      which is how a guard gets switched off.
    - **`refs` - FINALIZED EXCLUSION.** The fixture created branches named `feature` and `wt`.
      Detecting those needs a roster of fixture names, and a roster is the twin defect this repo
      keeps paying for - a real branch called `feature` is not a defect.
    - **the stale `branch.<name>.*` config section** (part of the item-2 repair) - **FINALIZED
      EXCLUSION**: harmless, and unlike a dead `core.hooksPath` it disables nothing.

15. **BUILT IS NOT LIVE is a hand-counted number, and hand-counting it failed five times.**
    **DONE 2026-08-26T20:34Z.** Found 2026-08-25 by the close meta-review's CHECK 2 (instance vs
    mechanism): **correcting the number was an INSTANCE fix.** `hook-provenance` already walked
    every wiring surface and already failed when copies differed - it computed the count and
    threw it away. It now derives and prints
    `BUILT IS NOT LIVE: N of M entry points stale, P of Q hooks/*.py`.
    **Built immediately after item 2's pull deliberately**, because a wrong count is least likely
    to be noticed at the moment everyone expects a zero. Three things fell out of doing it then,
    and none would have been found by re-counting by hand:
    - **The denominator was wrong AGAIN - 11, when it is 16.** `stop_dispatcher.HOOKS` has FOUR
      children and the plan counted two; `post_tooluse_dispatcher` has a table of its own that no
      count ever included. Five hooks that run on every matching event were outside the
      population through five hand-counts and three consistency passes. `dispatcher_children()`
      therefore recognises a dispatcher **by SHAPE** - a module-level `HOOKS` of string-pairs -
      because naming the two known ones is exactly how the third gets missed.
    - **The predicted post-pull answer, 0, was wrong: it is 3 of 16.** See item 20.
    - **A raw byte compare over-reports.** `cap_shapes.py` and `capped_report.py` differ from the
      live copy by 756 and 171 bytes and are the same commit - CRLF vs LF. That made it 10 of 28
      instead of 8 of 28, and `_same_repo_same_bytes` carried the same bug, so this gate could
      have called a correct linked worktree FOREIGN. Fixed via `_same_program`, which normalises
      **line endings only** - deliberately not whitespace, comments or docstrings.
    Prose restatements DELETED from this file, both of them; the history table above is labelled
    as history and carries no current figure. **7 mutations placed against the new probes, 7
    caught, 0 survived** (raw-byte compare, over-wide normalisation, name-based dispatcher
    lookup, unwired-dispatcher children, ABSENT folded into stale, line-endings counted as
    stale, and `_same_repo_same_bytes` reverted) - run against a COPY in `tools/`, never the
    real file, so there was nothing to restore and no sentinel to leak.

16. **`hook_health_check`'s selftest budget share should be revisited.** New 2026-08-25.
    Not urgent and NOT currently a problem - the item-10 split took it from 8.37s/84% back to
    **6.78s / 68%** of its 10.00s share, measured 02:31:55Z. Recorded because the 84% was reached
    by adding ONE battery, that file records 93% as the level where the mutation harness reported
    `baseline already RED` for six unrelated mutations, and the next addition starts from 68%
    rather than from the 6.4s the existing comments still assume.
    **MOVED 2026-08-27: 6.78s / 68% -> 7.17s / 72%**, from item 25's three sibling-worktree
    probes and the one `git init` they need. Recorded at the moment of the addition rather than
    discovered by a later reader - which is the whole point of this row existing. Still 21 points
    under the 93% level, but that is the SECOND item in three days to cost this hook ~4 points,
    and the trend, not the level, is what this row is watching.

17. **Nothing flags a gate TIER whose last run predates the code it covers.**
    Found 2026-08-26 by the close completeness pass as a **silent gap** - the plan does not
    mention the `integration` tier anywhere (grep: zero hits), so nothing about its freshness was
    ever scheduled or excluded.
    MEASURED the session before: `integration` last ran 2026-08-24T18:42:34Z, predating every
    commit of a session that added two hook modules and two `REQUIRED_HOOKS` entries `install.py`
    acts on. It was caught **only because the meta-review's CHECK 4 procedure says READ the
    ledger**, by hand, at the close - and re-running it returned 34/34, so nothing was wrong. But
    "nothing was wrong" was unverified for a full session, and the mechanism that caught it is a
    human reading a JSON file at the end.
    `tools/gate_ledger.py` already records every run with a UTC stamp, so the data exists. What
    does not exist is anything that ASKS. Fix: a gate that, per tier, compares its latest ledger
    stamp against the newest commit touching the surface that tier covers, and reports any tier
    that is older. Grep confirms no such check today.
    **Fails-loud by construction and cheap** - it reads a JSON file and asks git for a date.
    Note the trap before building it: `mutation_sweep` is PERMANENTLY stale by design (CI cannot
    write the local ledger), so that tier must be exempted with its reason written down, or the
    new gate is red forever and gets switched off. See "Known-stale by design" below.
    **SECOND TRAP, found 2026-08-27 - and item 21 has now ANSWERED it, so this is buildable.**
    The ledger is gitignored and therefore per-worktree LOCAL state, deliberately and by
    recorded design. That is not a defect to work around: a gate run proves something about the
    tree it ran in, so "has THIS worktree verified this tier?" is the correct question and the
    per-worktree answer is the right one. Measured: the two worktrees' ledgers disagree by TEN
    DAYS on `mutation_sweep`, and both are correct.
    **The requirement that follows is phrasing, and it is load-bearing:** this gate must report
    **"this worktree has not verified <tier> since <commit>"**, never "<tier> is stale". A local
    record stated as a global fact is how the first write-up of item 21 concluded a correct
    push-refusal was spurious.

18. **The SHIPPED consistency extractor's placeholder class fires on source-code literals.**
    Found 2026-08-26 by the close consistency pass, on itself. `skills/consistency-audit/scripts/
    audit.py` is a REGISTERED gate (`consistency-audit-skill` in `AUX_GATES`), so this is unbluff's
    own shipped code, not a note about a personal skill.
    PROVEN against the shipped copy: a file containing `x = []` reports **`[E] UNFILLED
    PLACEHOLDERS -> 2`**, flagging the bare `[]` alongside a real `[TODO]`. The class is written
    for prose deliverables, where `[TABLE]` / `[insert value]` are genuine defects; fed anything
    carrying code, every empty list, slice or subscript reads as an unfilled placeholder. It cost
    11 false candidates in the 2026-08-25 close and 0 real ones.
    **MEASURED A SECOND TIME 2026-08-27: 7 more false candidates, 0 real** - and all seven were
    lines of THIS ITEM's own body, which necessarily contains `[TODO]`, `[TABLE]`,
    `[insert value]` and `[]` in order to describe them. Two sessions, 18 candidates, zero real.
    **That RETIRES the "low materiality" label this item used to carry.** The original wording -
    "low materiality; it fails LOUD, as advisory candidates a human adjudicates, never a silent
    pass" - is still true about the failure MODE and is kept here for that reason, but it is no
    longer a fair summary of the cost. A class that has never once been right across two
    sessions and 18 candidates is not advisory noise; it is a detector that cannot distinguish a
    placeholder from prose ABOUT a placeholder, and it taxes every close.
    (The two sentences contradicted each other for about ten minutes on 2026-08-27, until the
    close meta-review's CHECK 1 grep surfaced the older one sitting under the newer verdict.
    Recorded rather than silently merged: a verdict added above stale prose is the
    token-vs-body contradiction this plan flags elsewhere, and it was committed here by the
    same pass that flags it.)
    Fix, unchanged: require a placeholder token to contain at least one letter, or skip the
    class for known code extensions. Whichever, probe BOTH directions: `[TODO]` must still fire
    and `[]` must not.

19. **Nothing asserts that a wired unbluff group carries `ID_PREFIX`.**
    Found 2026-08-26 by the close meta-review's CHECK 2, as the durability half of the id defect
    fixed in item 5. Changing one id was an INSTANCE fix.
    `install.ID_PREFIX` is `unbluff:` and `--uninstall` selects groups by
    `str(g.get("id","")).startswith(ID_PREFIX)`. A group registered under any other id **works
    perfectly and is unmanageable**: it fires, `hook_health_check` resolves its script,
    `duplicate_registration_check` sees exactly one registration, and `--uninstall` silently
    leaves it behind. Every existing check says green - which is why this survived being written
    by hand and would survive being written by hand again.
    Grep confirms nothing asserts it: `ID_PREFIX` appears in `install.py` only, and
    `show_your_proof.py`'s hits are `SESSION_ID_PREFIX_LEN`, unrelated.
    Fix: `hook_health_check` already walks every wired command and already owns "is the wiring
    healthy" - have it report any command whose script is a file THIS SUITE SHIPS while its group's
    id does not start with `ID_PREFIX`. The population is already derived there by
    `stale_root_registrations`, so this is a few lines on an existing walk. Read `ID_PREFIX` from
    `install.py` rather than restating it - a second copy of that literal is precisely the twin
    roster this repo keeps digging out, and it is the constant whose exact spelling caused the
    defect.
    **Confirm-don't-assume:** third-party groups must NOT be flagged, only groups whose command
    points at an unbluff-shipped file. Probe both directions before believing it.

20. **The plan predicted the pull would clear `hook-provenance`. The repo already knew it would
    not, and the plan never read its own design note.**
    New 2026-08-26. **The first version of this item called the mechanism an undocumented
    structural finding. That was wrong and is corrected here**, because the correction is the
    more useful fact: the mechanism was already written down, in `.claude/pre-push.cmd` under
    `[#45 2026-08-24]`, and in `run_selftests.MACHINE_STATE`. Both say, in as many words, that
    `hook-provenance` "during any release is legitimately false, because the branch is ahead of
    the copy that is wired." The plan asserted the opposite for two sessions without either
    being consulted.
    **What is true.** `C:\Users\ammar\Downloads\unbluff` is not a stale clone - it is the MAIN
    WORKTREE of this same repository (`git-common-dir` identical; `git worktree list` shows
    both), on `main` at `origin/main`. This branch is 16 commits ahead, unpushed, touching 9
    `hooks/*.py`. A pull delivers `origin/main` and cannot deliver unpushed commits, so the
    divergence is BRANCH divergence and pulling will never close it. Measured after the pull:
    **3 of 16 entry points stale, 8 of 28 `hooks/*.py`**.
    **There is no deadlock, and the first version of this item claimed one.** `.claude/
    pre-push.cmd` runs `run_selftests.py --code-only`, which excludes machine-state gates from
    the VERDICT while still running and naming them. Verified 2026-08-26T20:58Z: **exit 0, "all
    44 selftests passed", with `hook-provenance` listed as excluded and its reason printed.**
    The push is not blocked and never was.
    **So the real defect is in the PLAN, not the machine**, and it has one live consequence:
    item 7's "forced order" requires *a clean full sweep*, and a full sweep can never be clean
    on an unpushed branch **by design**. Read literally, that gate can never open. It should
    read "clean under `--code-only`, with `hook-provenance` adjudicated as machine-state" -
    which is exactly the state reached today.
    **DECIDED AND DONE 2026-08-27T05:21Z: push, merge to `main`, update the main worktree.**
    `feat/enforcing-verify` -> `origin` (the pre-push gate ran `--code-only` and allowed it in
    125s), then `git merge --ff-only` in the live worktree: `d44138c` -> `aeba569`. Result,
    measured immediately after:
    **`BUILT IS NOT LIVE: 0 of 16 entry points stale, 0 of 28 hooks/*.py`, `hook-provenance` rc=0,
    and the full suite 44/44 rc=0** - the first clean sweep in this chain, and the one items 7
    and 9 were waiting on.
    The two options not taken are recorded rather than dropped: rewiring `settings.json` to the
    worktree would have made the branch live without merging it, and accepting the divergence
    was what the design already permitted. Neither is needed while the branch is merged; both
    come back the moment the next branch starts, which is why this item stays in the file.
    **The derived count immediately caught a defect in itself here.** With 0 of 16 stale the
    note still printed "only a push/merge will clear the count" - a guard demanding the fix that
    had just been applied. `sync_phrase()` was split out as a pure function so both directions
    are probed without a git fixture, and M8 was added to the battery: 8 of 8 mutations caught.
    Found by running it where it ships, immediately after the merge it had itself recommended.
    NOT the same as the "Known-stale by design" `mutation_sweep` row below: that is stale
    because CI cannot write a local ledger. This was red because the machine ran a different
    branch, and it recurs on EVERY branch.
    **Also recorded here, and now ANSWERED:** the wired `piped_gate_guard` fired a FALSE
    POSITIVE on this session's own command. This item originally said "whether M10 fixes that
    shape is unverified, and it should be checked when item 5's fix goes live rather than
    assumed." **It went live at 05:21Z in this same session, so it was checked, and M10 does NOT
    fix it.** Characterised with a control and promoted to **item 22** - a condition written as
    "check when X happens" where X happened forty minutes later, which is the one case a
    deferred check actually gets done.

21. **The gate ledger is gitignored, so it is PER-WORKTREE - and a gate reads it to decide a
    push.** **ANSWERED 2026-08-27, and the answer was already written down.**

    **DECISION: the ledger is PER-WORKTREE LOCAL STATE. Confirmed, not chosen.** `.gitignore:23`
    carries its own comment - *"Local gate-run audit trail (evidence of which gates ran, not
    source)"* - and `gate_ledger.py`'s header treats gitignored-ness as a hazard to DESIGN
    AROUND (no restore, hence the atomic write and the quarantine path), not as an oversight.
    The question this item raised had been answered before it was asked, which is the third time
    in one session that an authority already held the answer (see items 20 and 23).
    Repository state was considered and REJECTED: an append-only JSON written by every gate run
    would conflict on every merge, dirty the tree mid-push, and break the content-clean-vs-HEAD
    preconditions the mutation harness depends on.

    **So the defect is not that the record is local - it is that a LOCAL record was read as a
    GLOBAL claim, in the prose and in one gate.** Measured, both worktrees at the same commit:

    | | rows | newest `integration` | newest `mutation_sweep` |
    |---|---|---|---|
    | `unbluff-enforcing` | 273 | 2026-08-27T06:28Z | 2026-08-27T06:24Z |
    | `unbluff` (live) | 196 | 2026-08-27T05:33Z | **2026-08-17T11:15Z** |

    **Ten days apart on the tier that certifies everything else.** Both numbers are correct;
    they answer different questions.

    **And the refusal that started this item was RIGHT, which the first write-up got wrong.**
    It said the push was blocked "for a reason that had nothing to do with the code." Not so:
    `readme-scenarios` said the README claims 34/34 while *this tree's* newest recorded run was
    30/30, and that was true of that tree. Running the tier there produced 34/34 and the push
    went through. The gate failed CLOSED on honest local evidence - the safe direction.

    **What is left to build** is phrasing, and it is the whole of the fix: every ledger-reading
    gate must say **"this worktree has not verified X"** rather than "X is stale", so local
    evidence can never be mistaken for a repository fact. Scoped into items 17 and 24 rather
    than kept as a separate build row.

    The original finding, kept because the measurement is the evidence:
    `git push origin main` from the live worktree FAILED on `readme-scenarios`: *"README pastes
    34/34; the newest recorded integration run is 30/30."* The same gate had passed minutes
    earlier from the enforcing worktree. Nothing about the code differed - the two worktrees
    were on the identical commit. What differed is that `docs/audits/gate_runs.json` is
    **gitignored** (`gate_ledger.py` says so in its own header), so each worktree keeps its own
    ledger, and today's 34/34 integration run had been recorded in the OTHER one.
    So a gate whose input is local, gitignored state gives a **different verdict depending on
    which worktree you push from**, and the failure names the README rather than the cause. The
    fix taken was the honest one - run the integration tier where `main` actually sits, which
    recorded 34/34 there and let the push through - but that is the instance, not the mechanism.
    **This lands directly on item 17**, which proposes a gate comparing each tier's newest
    ledger stamp against the commits it covers. Built naively it inherits this exactly: in a
    two-worktree setup every tier looks stale in whichever worktree did not run it, so the new
    gate would be red half the time and get switched off - the same failure mode as the
    `mutation_sweep` trap already written into item 17, arriving by a second route. Item 17 must
    therefore decide, in writing, whether the ledger is per-worktree state (and the gate reads
    only its own) or repository state (and it stops being gitignored). **Do not build item 17
    before answering that.**
    Cheap to confirm and worth confirming: it predicts that any ledger-reading gate can be
    flipped green or red purely by choosing a worktree, with no commit in between.

22. **`piped_gate_guard` fires when a gate's SOURCE FILE is read on the producer side of a
    pipe. CONFIRMED false positive, in the wired copy, twice in one session.**
    **FIXED 2026-08-27 - and it was TWO defects, not one.** The item as written described only
    the first; the second was found by fixing the first and watching the original command STILL
    fire.

    **Layer 1 - a READER on the producer side.** `_reads_a_file()` resolves what a segment
    actually RUNS (past env assignments and `sudo`/`env`/`time` wrappers) and skips it when that
    is a file reader. The distinction is the EXECUTABLE, never the operand, and both directions
    are pinned: `grep -n "800" tools/check_file_size.py | head` is now quiet, while
    `python tools/check_file_size.py | head` still fires. A fix that keyed on the operand would
    turn the second one green, which is why it is a SHOULD_FIRE row rather than a comment.

    **Layer 2 - A PIPELINE DOES NOT CROSS A STATEMENT BOUNDARY, and this is the one that
    explains the mis-attribution.** `_segments()` splits on `|` alone, so every statement in a
    multi-statement command landed in a single "segment" and a gate named in statement A was
    reported as the producer for a pipe in statement B. That is exactly why the original message
    named `hook_divergence_report` while the offending pipe contained `check_file_size` - the
    name came from a `for` loop on the LINE ABOVE. Newlines vanish into whitespace inside
    `shlex`, so the line boundary has to be honoured before tokenising: `_logical_lines()`
    (rejoining `\` continuations first, or a continued pipeline would become a false NEGATIVE)
    plus `_last_statement()`, since only the last statement in a segment feeds the pipe.
    `_is_protected()` deliberately still reads the WHOLE command - `set -o pipefail` on one line
    protects a pipe on the next.

    **Verified 10 cases, 0 mismatches**, four quiet-directions and six fire-directions including
    the three the statement fix could have broken (a gate on the second line, a gate after `;`,
    a backslash-continued pipeline). The guard's own corpus grew from `sh 10 fire / 17 quiet` to
    `13 fire / 19 quiet`, and three rows went into `tests/false_alarm_corpus.py` as the item
    asked - the shared corpus, not a new list.

    The original finding, kept because the control is the part that made it a finding:

    Item 20 recorded the symptom and said the M10 fix should be CHECKED rather
    than assumed once it went live. It went live at 05:21Z in this session, so it was checked.
    **M10 does not fix it.** Reproduced against the wired copy and the repo copy, same verdict.
    Characterised, with a control:

    | command | verdict | correct? |
    |---|---|---|
    | `grep -n "800" tools/check_file_size.py \| head -20` | FIRES | **NO** - `grep` is the producer |
    | `cat tools/check_file_size.py \| head -20` | FIRES | **NO** |
    | `wc -l tools/check_file_size.py \| head -1` | FIRES | **NO** |
    | `grep -n "800" docs/PLAN.md \| head -20` | quiet | yes - CONTROL, a non-gate file |
    | `python tools/hook_divergence_report.py \| head -20` | FIRES | yes - genuinely piped |

    The control is what makes it a finding rather than a guess: swap the gate's filename for a
    non-gate file and the guard goes quiet, so it is the NAME triggering it, not the pipe.
    **The guard already owns this exact reasoning in the mirror direction** - its own corpus
    carries `cat log.txt | grep run_selftests` as "the gate CONSUMES, it is not the producer",
    correctly quiet. What is missing is the operand case on the PRODUCER side.
    **The distinction is the EXECUTABLE, not the operand**, and getting that backwards would
    break the real detection: `python tools/check_file_size.py | head` must keep firing, where
    the executable is `python` and the gate is its script. The rule is that a READING tool
    (`grep`, `cat`, `wc`, `sed`, `awk`, `head`, `tail`, `less`) as the producer's executable
    means any gate name after it is a FILE BEING READ, not a gate being run.
    **Materiality is higher than it looks.** This is a wired guard failing on correct work -
    the shape this repo says gets guards switched off - and it cost two command rewrites in the
    session that found it. It also mis-attributes: the first firing named `hook_divergence_report`
    when the offending segment contained `check_file_size`.
    **Probe both directions**, and reuse the corpus: `tests/false_alarm_corpus.py` already holds
    the non-firing cases, so the four rows above belong there rather than in a new list.

23. **The item-15 count reintroduced the exact fail-open its own file was rebuilt to remove.**
    **FOUND AND FIXED 2026-08-27, same session as the defect.** Found by the close
    source-coverage pass reading the DESIGN rather than the code.
    Fixed: the count now takes `main()`'s own two-cause split. Verified end to end via
    `--repo` on an empty hooks dir, which now prints
    `BUILT IS NOT LIVE: NO COUNT - 3 wiring surface(s) were read and NOT ONE resolved to an
    entry point. That is a broken derivation wearing a clean result, not a synced machine`
    instead of a bare `0 of 0`. `--json` now carries `staleness` (verified: `entry_total 16`,
    `files_total 28`). Probe 4c added, asserting the zero survives to `main()` so the branch is
    reachable at all. Suite 44/44 rc=0 after.
    The record of what it was, kept because the lesson is the point:
    `tools/hook_divergence_report.py`'s module docstring states the rule in its own words:
    *"BOTH DENOMINATORS ARE PRINTED. A provenance check that examined nothing looks exactly like
    one that examined everything and found nothing wrong."* `main()` honours it for the
    provenance verdict, with an explicit two-cause NOTE separating "no wiring surface at all"
    (inapplicable, e.g. a fresh CI checkout) from "surfaces read, zero commands parsed" (a
    broken parse wearing a clean result).
    **The new count honours neither.** Measured: with no wiring, `entry_points()` returns `{}`
    and the gate prints **`BUILT IS NOT LIVE: 0 of 0 entry points stale`** - which is
    typographically identical to a perfectly synced machine, and is what a fresh checkout will
    print forever.
    Fix: give the count the same two-cause treatment `main()` already gives `examined == 0` -
    an empty entry-point population is INAPPLICABLE (say so) or a broken derivation (fail), and
    never a zero that reads as health. Reuse `main()`'s existing branch rather than writing a
    second copy of that reasoning.
    Second, smaller half: **`--json` does not carry the counts.** The tool advertises
    `--json out.json`; the payload has `matched/foreign/unparsed/bare/examined/surfaces` and
    none of `entry_*` or `files_*`, so a consumer of the JSON cannot see the number this item
    exists to publish. Add them to the same dict.
    **Probe both directions**, and the zero case specifically: an empty population must NOT
    print a bare `0 of 0`, and a genuinely clean machine must still print `0 of 16`.

24. **The BUILT IS NOT LIVE count is now correct and has NO HISTORY. The fix removed the
    trajectory.** New 2026-08-27, from the close source-coverage pass reading the design.
    This file says of that number: *"The trajectory is the real point... every session that
    fixes something makes the live machine MORE stale."* `tools/gate_ledger.py` exists for
    exactly that reason - its header records that a per-run verdict is not an observable trend.
    **Item 15 deleted the prose that carried the trajectory and replaced it with a
    point-in-time print.** The number is right now and unrecoverable later: today's `0 of 16` is
    only meaningful against yesterday's `6 of 11`, and after the prose deletion that comparison
    cannot be made from the artifacts at all. The history table above is frozen hand-written
    rows, not a series - it stops the moment nobody updates it, which is the whole reason item
    15 existed.
    **This is a gap created BY the fix**, and it is the honest cost of it: prose that was wrong
    but longitudinal became a number that is right but instantaneous.
    Fix: record the counts per run in the gate ledger alongside the tier result -
    `gate_ledger.record()` already takes a result and a stamp, and `hook-provenance` already
    calls into that path. Then the trajectory is derived, like the count, instead of retyped.
    **Confirm-don't-assume:** check whether `gate_ledger.record()` accepts structured extras
    before designing around it; if it does not, that is the smaller change, not a reason to put
    the number back into prose.
    Interaction with item 21, now ANSWERED and in this case it resolves cleanly: the ledger is
    per-worktree local state, so a trajectory recorded there is a per-worktree trajectory. **For
    THIS number that is exactly right** - BUILT IS NOT LIVE is a `MACHINE_STATE` claim about the
    box it runs on, so a local home is the correct home, not a compromise. No divergent-history
    problem to solve here; just label the series as this worktree's.

25. **Two gates ask the same question about the same machine and give opposite answers.
    `hook_health_check` never learned the linked-worktree lesson `hook_divergence_report` has
    in writing.** **FIXED 2026-08-27.** Found by diffing against a CONVENTION IN ANOTHER FILE,
    which is now the third session running that this lens produced the sharpest finding.

    **Result, measured on the same tree that produced the 8:** `hook-health` went from **8
    problems to 1**, and the 1 remaining is a genuinely diverged file (`hook_health_check.py`
    itself, edited and not yet merged). `hook-provenance` INDEPENDENTLY reported the same
    picture at the same instant - 1 foreign, `1 of 16 entry points stale, 1 of 28`. **The two
    gates now agree exactly**, which is the check that the fix is right rather than merely quiet.

    `_sibling_worktree_verdict()` REUSES `hook_divergence_report._same_repo_same_bytes` - no
    second copy of the two-condition rule, so the CRLF half fixed earlier today cannot drift out
    of it. Three implementation facts worth keeping:
    - **The import is LAZY because a module-level one is a genuine CYCLE**:
      `hook_divergence_report` -> `duplicate_registration_check` -> `hook_health_check`.
      Deferring it also means a SessionStart with no candidate pays nothing.
    - **It returns None for "could not ask"**, and the caller SAYS so in the message rather than
      downgrading to the path comparison in silence. A partial checkout has `hooks/` without
      `tools/`; that must never read as "fine".
    - The probe fixture imports `subprocess as _sp` rather than reading the bare name, because
      this module's REBINDING RULE requires it and `subprocess` IS rebindable there (the
      fake-subprocess case rebinds `_m.subprocess`). A bare read worked only by test ordering.

    **Probed in three directions, and each was shown to FAIL** by stubbing the verdict:
    reverting the fix entirely, dropping the "same bytes" half, and treating could-not-look as
    fine - **3 of 3 CAUGHT**. Plus a standing control: a byte-identical copy OUTSIDE this
    repository must still be flagged, so identical bytes alone are never the test and the real
    2026-07-30 defect (diverged `~/.claude/hooks` copies) cannot come back.

    The original finding, kept because the measurement is the argument:
    Measured on the fully-merged, fully-synced tree, same instant, same wiring:

    | gate | verdict |
    |---|---|
    | `hook-provenance` | rc=0, **0 foreign**, `0 of 16 entry points stale, 0 of 28` |
    | `hook_health_check` | **8 problem(s)** across 31 hook commands |

    **All 8 are the same shape** - `X.py is registered from ...\unbluff\hooks but this suite
    ships it in ...\unbluff-enforcing\hooks (identical copy)` - and **0** are the
    "THE TWO COPIES ARE DIFFERENT PROGRAMS" shape the check was built for.
    `hook_divergence_report` already solved exactly this, deliberately, and wrote down why:
    `[#39] A LINKED WORKTREE IS NOT A FOREIGN COPY. Path equality alone called it one ... the
    gate fired on correct work - hard enough to BLOCK the v1.4.0 push, which is how a guard ends
    up switched off.` Its `_same_repo_same_bytes` requires TWO conditions - git says the same
    repository (same common dir, so a separate clone still fails) AND the bytes match (so a
    genuinely stale worktree still fails).
    **`hook_health_check` has no concept of a worktree at all** - grep for `worktree` /
    `common_dir` in it returns nothing. It compares `os.path.dirname` against its own
    `_HOOKS_DIR`, which is precisely the path-equality test `[#39]` records as insufficient.
    Its own message already says "identical copy" - it HAS the fact and reports a problem anyway.
    **Why it matters:** this fires at every SessionStart, and 8 standing problems on a correct
    machine is the definition of the shape this repo says gets a guard switched off. It is also
    worktree-dependent, like item 21: run from the main worktree the paths match and it prints
    `OK - 31 hook commands verified`, which is what this session's own SessionStart banner said.
    So the answer to "is my wiring healthy?" depends on which directory you ask from.
    Fix: **REUSE `_same_repo_same_bytes`, do not re-implement it.** A second copy of that
    two-condition rule is the twin-roster defect this repo keeps paying for, and `hooks/` may
    not import `tools/` on a partial checkout - so this needs the same ImportError-fallback
    treatment the other cross-layer imports here already use, and the fallback must be a
    STATEMENT that the check could not run, never a silent pass.
    **Probe both directions:** a byte-identical sibling worktree must NOT be flagged; a
    genuinely diverged `~/.claude/hooks` copy (the real 2026-07-30 defect this check exists for)
    must STILL be flagged.

## Retired, not forgotten - and why each one died

Listed so the retirement is a decision on the record rather than a quiet omission. Every item is
recoverable from the archived plan.

- **Gate 3 (prove the README's claim subset), gate 4 (mechanise the "no network" badge), gate 7
  (release notes), gate 10 (CI green via PR on 3 OSes), gate 11 (tag + convert the ledger to
  issues).** All five exist to make the repo defensible to a stranger. Gate 4's
  `check_no_network` and gate 7's v1.3.1 Release are already BUILT and stay - only their
  maintenance obligation is dropped.
- **Gate 9's M1, M5, M6, M9, M11 and L1, L2.** Defects in `check_no_network`'s exemption hatch,
  `no_regression`'s decoding, the ledger's accounting and CHANGELOG cardinalities. All real, all
  in instruments rather than in hooks, none of them changing a session *today*. Full statements
  survive in [gate 9 review](audits/gate9_review_2026-08-24.md).
  **Two of them are DORMANT, not harmless, so their triggers are recorded rather than left to be
  rediscovered** - this session's completeness audit asked whether anything still live had been
  retired by accident, and these are the two that came closest:
  - **M1 fires the first time `ALLOWED` in `check_no_network.py` gets an entry.** It is empty
    today, which is the only reason the gate is not permanently red. Add an exemption and the
    gate starts insisting that exemption is no longer needed. Fails closed, so it will annoy
    rather than deceive.
  - **M5 fires the first time a non-ASCII byte lands in a REGISTERED `no_regression` unit.**
    Checked 2026-08-24T21:18:49Z: `hooks/capped_report.py` has 0 such bytes, so the gate is
    sound right now - but `numbers_match_on_write.py` (8), `pre_push_gate.py` (4) and
    `fast_test_disclosure.py` (3) already do. The day one of those is registered, or a single
    typographic character reaches `capped_report.py`, `no-regression: OK` starts comparing a
    file against itself and means nothing. That one is worth un-retiring if it ever trips.
- **#42, #43, #6/#28 (the 243-claim inventory).** Claim-proofs and cardinality gates for
  documents nobody but me reads.
- **The `pre_push_gate_selftest.py` split (#41's remaining half).** The largest file here, but
  splitting it is refactoring an instrument. Its size, its seam and the reason it was not
  attempted are recorded in `file_size_baseline.json` - **which is the only place the number
  lives now.** This line said "1192 lines" from 2026-08-25 until 2026-08-27, while the file was
  1213 and the baseline recorded 1213: the `_accepted_growth_2026_08_25` note moved the baseline
  and left this copy behind. Caught by the close consistency pass. **Third instance in this file
  of a number restated in a second place drifting in one of them** - so the number is deleted
  here rather than corrected, which is item 15's rule applied by hand where no gate reaches.
- **`install_selftest.py` has never been adversarially reviewed.** 358 lines, split out
  2026-08-24. `check_review_freshness` will keep asking; that is fine and it can keep asking.

**Undecided, deliberately:** whether the repo stays public. It is currently public and is also the
career artifact the old premise was built on.
**Given a TRIGGER 2026-08-25 by the close completeness pass, which is the only STEP 1 hit in this
plan that was still optional-forever.** "Parked by choice, not forgotten" is the exact shape that
sweep exists to catch: a decision with no date and no condition is indistinguishable from one that
has been dropped. It is not a build item and needs no materiality slot - it is a DECISION, and the
condition that forces it is: **the next time this repo would be shown to anyone (a CV link, an
application, a PR from a stranger), or the next re-cut of this plan, whichever comes first.**
Until then the status quo - public - stands by default rather than by omission.

## Known-stale by design: the ledger's `mutation_sweep` row

`docs/audits/gate_runs.json` reads **`mutation_sweep 2026-08-20T17:28:15Z FAIL`** and will keep
reading that. The full sweep now runs in CI on two platforms - it passed 17/17 at `91f015e`,
223 of 225 executed with 0 survivors - but **a CI runner cannot write this local ledger**, so the
newest local row predates the fix that made the sweep green and says FAIL.

That matters because the close meta-review's CHECK 4 is specifically instructed to READ this
ledger rather than reconstruct it, which is the right instruction and is exactly why a
permanently-stale row is dangerous: it is #44's defect ("anything reading the ledger to decide
whether the gates passed would conclude the gate fails at HEAD") reintroduced structurally rather
than by a polluting write. **Recorded here rather than papered over by a 30-minute local re-run
whose only purpose would be to make a row look right.** If CHECK 4 is ever automated, it must
read CI for this tier. Every other tier is current as of 2026-08-24T21:23Z.

## Standing checks on every change

These are the durable part of the old plan and they survive the re-cut unchanged. Each caught a
real defect that nothing else did.

1. **Did this fix create a new instance of the class it fixed? ASK IT MID-SESSION, NOT AT THE
   CLOSE.** Caught a C7 instance introduced by the commit fixing C7 elsewhere - and on 2026-08-24
   caught three more in one session, including a gate whose input does not exist in CI, built by
   the commit removing exactly that class of defect.
   **The timing is part of the check, added 2026-08-25 by the close completeness pass** - the
   meta-review recommended it as CHECK 5.1 and it had ZERO hits in this plan, so the practice
   existed only in an audit file nobody re-reads. It has now fired on my own work in **four
   consecutive sessions**, and for the first three the fix was already committed before it fired.
   Asked mid-session on 2026-08-25 it paid immediately and three times over: the machine-sanity
   extractor scanned the directory its own battery lives in and swallowed the control identity;
   the narrowing of `check_selftest_isolation` released a fixture-building module from the
   population it belonged in; and the battery's own denominator shipped two hardcoded literals,
   one of which was wrong. All three were caught BEFORE the commit, which is the entire
   difference the timing makes.
2. **What would have to be true for this control to be UNABLE to fire?** Caught
   `load_with_siblings` failing open, `roster_gaps` accepting a non-existent tree, and
   `unrecorded_tiers` being satisfied by its own docstring.
3. **Is the number derived, and derived just now?** 30 of 53 claims checked failed - almost all
   true when written. No mutable count in a title or heading; counts live in the body, dated,
   **next to the commit they were taken at** - a denominator naming `HEAD` is one that will be
   quietly false.
4. **Is this surface actually LIVE?** A session went into `piped_gate_guard`, which is **NOT
   wired on this machine** and has never fired. Verified again 2026-08-24T21:20:34Z: zero
   occurrences in `settings.json`. This wording was corrupted to "wired but had never fired"
   during the re-cut and caught by the same session's source-coverage pass - the check's whole
   value is the word NOT, and I deleted it while copying the check that exists to catch exactly
   this. The 13%-of-the-branch measurement above is this same check applied to a whole release.
5. **Never edit while a gate is in flight.** Broken three times in one day, three sweeps
   discarded.
6. **A probe that has not been shown to FAIL is not a probe.** Four probes were invalid on first
   write and every one returned a comforting answer. A mutation that cannot be PLACED - or that
   only fails because the mutant will not compile - has proven nothing.
7. **An agent's finding is a hypothesis, and so is a PRESCRIBED FIX.** A confirmed
   "zero-interaction RCE" did not reproduce under three probes; #46's prescribed fix named the
   wrong file and was scoped an order of magnitude too small.
8. **Run it where it ships.** Six clean local suite runs missed a CRITICAL that appeared on the
   first real `git push`; 41 local gates passed over an `install.py` that refused to install.
   The local suite and CI have never once produced the same failure set.
