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

**BUILT IS NOT LIVE, and right now they differ.** Re-derived 2026-08-25T02:19:47Z by content hash
against committed `ff251e2`, with the DENOMINATOR derived rather than assumed - and **the figure
this paragraph carried was wrong**:

| population | how it is reached | stale |
|---|---|---|
| 7 hooks named in `settings.json` | Claude Code | **2** - `close_skills_guard`, `hook_health_check` |
| 2 `stop_dispatcher` children | in-process import | **2** - `meta_audit_on_stop`, `fast_test_on_stop` |
| 1 `core.hooksPath` target | `~/.claude/githooks/pre-push` | **1** - `pre_push_gate` |
| **entry points that RUN** | | **5 of 10** |
| every `hooks/*.py` | incl. the libraries those import | **12 of 26**; `fast_test_disclosure.py` is ABSENT |

The five NAMES were exactly right. The denominator was not: it read **"5 of 6 ... Live:
`stop_dispatcher` alone"**, when the population is 10 and FIVE hooks are live - `stop_dispatcher`,
`duplicate_registration_check`, `post_tooluse_dispatcher`, `rate_prompt`, `usage_snip_prompt`.
The 6 was the five files that had been worked on plus the one known-good: **a denominator scoped
to what the author was thinking about rather than to the population**, which is the defect this
plan names in three other places, and the third session running that this one number has been
wrong. Found only because item 10's new check printed `1 wired clone config-checked` and that
disagreed with the prose - the mechanism catching the memo, which is the whole argument for
item 10.

**The table above is pinned to `ff251e2`. One session later, at `1443a59`, it already reads
6 of 11 entry points and 14 of 28 files** (derived 2026-08-26T19:35:02Z). Two new modules exist
in no live copy at all, and `piped_gate_guard` BECAME an entry point when item 5 wired it - while
stale. So the population grew and the numerator grew with it.

The trajectory is the real point, and it is now measured twice rather than asserted: **every
session that fixes something makes the live machine MORE stale**, and it will keep doing so until
item 2's pull runs. The library row matters more than it looks - 14 of 28 files differ, so even the
LIVE entry points are importing stale siblings.

History of this one number, kept because it is the clearest worked example of the defect in this
file: **2 of 6** (2026-08-24T22:06:53Z) named only the two hooks built that afternoon; **4 of 6**
(23:06:35Z) added the two whose fixes landed the session before; **5 of 6** (2026-08-25T01:42:33Z)
added `meta_audit_on_stop`. Each correction fixed the NUMERATOR and none of them ever questioned
the DENOMINATOR, which was wrong from the first measurement and stayed wrong through three
revisions by three separate consistency passes. **The two the first count missed are the two that
matter most to a user** - the execution-model disclosure and the gate that bricks pushes on a
moved clone.

**Item 2's config half is DONE (2026-08-24T23:05:49Z).** `core.bare`, the local `core.hooksPath`
pointing at a deleted temp dir, and the `t@t` identity are all unset, plus the stale
`branch.feat/enforcing-verify.*` section; the clone now resolves hooks to the global
`~/.claude/githooks` and its identity to `AmmarBibi <ammarbibi@hotmail.com>`, with a clean tree at
`b6cc6cc`. The full local config before the change is recorded in the commit message as the
rollback record. **The `git pull` itself remains blocked by the tool-permission classifier** - so
the clone is now REPAIRED BUT STILL BEHIND, and **6 of 11 entry points** (and **14 of 28**
`hooks/*.py` files) stay inert until someone runs that one command - derived
**2026-08-26T19:35:02Z at `1443a59`**. Before this repair the pull would have failed anyway on
`core.bare=true`; now it is purely a permission away.
(This sentence read "all four stale hooks" until 2026-08-25 and "five ... 12 of 26" until
2026-08-26. It carries its own copy of the headline count, so every correction to the table above
leaves it silently disagreeing - twice now, in two consecutive sessions. **A number restated in a
second place is a number that will drift in one of them, and this is the proof.** Item 15 is the
fix: derive it in `hook-provenance` and stop restating it in prose at all.)

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
2. **Repair the main clone's git config.** **PARTIAL - config half done 2026-08-24T23:05:49Z, the
   `git pull` is STILL BLOCKED and is the only thing standing between every fix on this branch and
   the machine that runs them.** (Relabelled by the close completeness pass: this row led with the
   word DONE over a body saying blocked, which is the same token-vs-body contradiction the plan
   flags elsewhere.) `core.bare=true`, a local `core.hooksPath` pointing at the deleted
   `%TEMP%/tmp7dq12juu/myhooks`, a `t@t` identity and a stale `branch.feat/enforcing-verify.*`
   section - all four #46 residue, all now unset, verified by re-reading the config and confirming
   the clone resolves to the global `~/.claude/githooks` as `AmmarBibi`, tree clean at `b6cc6cc`.
   Remaining, and it is one command: the clone is **44 commits behind `origin/main`** and cannot
   be advanced from here because `git pull` trips the tool-permission classifier. Until it runs,
   4 of 6 wired hooks are stale and every fix authored on 2026-08-23/24 is inert on this machine.

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
7. **Split `run_selftests.py`.** New 2026-08-25. It is a recorded 803-line offender, but the
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

15. **BUILT IS NOT LIVE is a hand-counted number, and hand-counting it has failed four times.**
    Found 2026-08-25 by the close meta-review's CHECK 2 (instance vs mechanism), and it is the
    sharpest durability gap of the session: **correcting the number was an INSTANCE fix.**
    The history is in the plan above - 2 of 6, 4 of 6, 5 of 6, and now 5 of 10 / 12 of 26. Three
    of those four were corrected by a consistency pass that re-derived the NUMERATOR and never
    once questioned the DENOMINATOR. The fourth was caught only because item 10's new check
    happened to print `1 wired clone config-checked` and that disagreed with the prose. **That is
    luck wearing the costume of a process**, and next session the number goes stale again the
    moment anything is committed.
    The mechanism is close to free, because the gate already exists: `hook-provenance` ALREADY
    compares the wired copies against the repo and already fails when they differ. It reports a
    verdict; it does not report a COUNT. Have it derive and print `N of M entry points stale, P of
    Q hooks/*.py`, with the entry-point population derived the way item 10 derives it -
    `settings.json` commands, plus `stop_dispatcher`'s table, plus the `core.hooksPath` shim's
    target - and the plan's sentence becomes checkable against a derived number instead of being
    re-counted by hand by whoever notices next.
    Do it AFTER item 2's pull: at that moment the true answer becomes 0 of 10, which is exactly
    when a wrong count is least likely to be noticed.

16. **`hook_health_check`'s selftest budget share should be revisited.** New 2026-08-25.
    Not urgent and NOT currently a problem - the item-10 split took it from 8.37s/84% back to
    **6.78s / 68%** of its 10.00s share, measured 02:31:55Z. Recorded because the 84% was reached
    by adding ONE battery, that file records 93% as the level where the mutation harness reported
    `baseline already RED` for six unrelated mutations, and the next addition starts from 68%
    rather than from the 6.4s the existing comments still assume.

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

18. **The SHIPPED consistency extractor's placeholder class fires on source-code literals.**
    Found 2026-08-26 by the close consistency pass, on itself. `skills/consistency-audit/scripts/
    audit.py` is a REGISTERED gate (`consistency-audit-skill` in `AUX_GATES`), so this is unbluff's
    own shipped code, not a note about a personal skill.
    PROVEN against the shipped copy: a file containing `x = []` reports **`[E] UNFILLED
    PLACEHOLDERS -> 2`**, flagging the bare `[]` alongside a real `[TODO]`. The class is written
    for prose deliverables, where `[TABLE]` / `[insert value]` are genuine defects; fed anything
    carrying code, every empty list, slice or subscript reads as an unfilled placeholder. It cost
    11 false candidates in the 2026-08-25 close and 0 real ones.
    Low materiality - it fails LOUD, as advisory candidates a human adjudicates, never a silent
    pass - but it is still a guard firing on correct work, which is the shape this repo says gets
    guards switched off. Fix: require a placeholder token to contain at least one letter, or skip
    the class for known code extensions. Whichever, probe BOTH directions: `[TODO]` must still
    fire and `[]` must not.

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
- **The `pre_push_gate_selftest.py` split (#41's remaining half).** 1192 lines and the largest
  file here, but splitting it is refactoring an instrument. Its seam and the reason it was not
  attempted are recorded in `file_size_baseline.json`.
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
