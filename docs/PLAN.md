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

**BUILT IS NOT LIVE, and right now they differ.** Measured three times and it has gone UP each
time, because every fix widens the gap until the clone can pull: **2 of 6** at 2026-08-24T22:06:53Z,
**4 of 6** at 23:06:35Z, and **5 of 6 at 2026-08-25T01:42:33Z** with the clone 44 commits behind
`origin/main`. Stale: `close_skills_guard`, `hook_health_check`, `fast_test_on_stop`,
`pre_push_gate`, and now `meta_audit_on_stop` - which item 3's scrub moved out of LIVE. Live:
`stop_dispatcher` alone.
That trajectory is the point, not the number: **this session made the live machine MORE stale, not
less**, and it will keep doing so until item 2's pull runs. Caught by the close consistency pass
re-deriving a figure the plan already carried, which is the only reason it is not still reading
"4 of 6".

The earlier count was not wrong when taken - it named only the two hooks built that afternoon, and
silently omitted the two whose fixes landed the session before. That is the same undercount shape
the plan warns about elsewhere: a measurement scoped to what the author was thinking about rather
than to the population. **The two it missed are the two that matter most to a user** - the
execution-model disclosure and the gate that bricks pushes on a moved clone.

**Item 2's config half is DONE (2026-08-24T23:05:49Z).** `core.bare`, the local `core.hooksPath`
pointing at a deleted temp dir, and the `t@t` identity are all unset, plus the stale
`branch.feat/enforcing-verify.*` section; the clone now resolves hooks to the global
`~/.claude/githooks` and its identity to `AmmarBibi <ammarbibi@hotmail.com>`, with a clean tree at
`b6cc6cc`. The full local config before the change is recorded in the commit message as the
rollback record. **The `git pull` itself remains blocked by the tool-permission classifier** - so
the clone is now REPAIRED BUT STILL BEHIND, and all four stale hooks stay inert until someone runs
that one command. Before this repair the pull would have failed anyway on `core.bare=true`; now it
is purely a permission away.

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
   **STILL YOURS TO DECIDE. Evidence refreshed 2026-08-25T01:15:51Z; the recommendation is now WIRE.**
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

8. **Nothing enforces that `--code-only` stays off the turn-end command** (was #47, ORPHANED by
   the 2026-08-24 re-cut and re-homed here 2026-08-25 by the close completeness pass).
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

9. **This session's four guards are hand-probed but NOT registered as mutation entries.** Found
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

**Undecided, deliberately:** whether the repo stays public. It is currently public and is also
the career artifact the old premise was built on. Parked by choice on 2026-08-24, not forgotten.

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

1. **Did this fix create a new instance of the class it fixed?** Caught a C7 instance introduced
   by the commit fixing C7 elsewhere - and on 2026-08-24 caught three more in one session,
   including a gate whose input does not exist in CI, built by the commit removing exactly that
   class of defect.
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
