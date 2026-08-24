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

**BUILT IS NOT LIVE, and right now they differ.** First measured 2026-08-24T22:06:53Z as **2 of 6
wired hooks STALE**. **RE-DERIVED 2026-08-24T23:06:35Z: it is 4 of 6, and the clone is 44 commits
behind `origin/main`.** Stale: `close_skills_guard` (item 0), `hook_health_check` (the #46 scrub),
`fast_test_on_stop` (the #25 disclosure) and `pre_push_gate` (the #30 moved-clone fix). Live:
`meta_audit_on_stop`, `stop_dispatcher`.

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
1. **Land the branch.** `feat/enforcing-verify` -> `main` via
   [PR #3](https://github.com/AmmarBibi/unbluff/pull/3). This is the whole point of the branch
   for a solo user: `main` currently still has (a) a moved or renamed clone **bricking every
   `git push` on the machine**, (b) the consistency-audit skill certifying a **scanned PDF as
   CLEAN** without reading it, (c) the pre-push gate **blocking correct pushes** (#45), and
   (d) the selftest that **corrupted the repo and pushed a one-file tree to public `main`**
   (#46). Merging also permanently clears `hook-provenance`, which fails today only because the
   wired copy is `main`'s older one.
2. **Repair the main clone's git config.** **CONFIG HALF DONE 2026-08-24T23:05:49Z; the `git
   pull` is still blocked.** `core.bare=true`, a local `core.hooksPath` pointing at the deleted
   `%TEMP%/tmp7dq12juu/myhooks`, a `t@t` identity and a stale `branch.feat/enforcing-verify.*`
   section - all four #46 residue, all now unset, verified by re-reading the config and confirming
   the clone resolves to the global `~/.claude/githooks` as `AmmarBibi`, tree clean at `b6cc6cc`.
   Remaining, and it is one command: the clone is **44 commits behind `origin/main`** and cannot
   be advanced from here because `git pull` trips the tool-permission classifier. Until it runs,
   4 of 6 wired hooks are stale and every fix authored on 2026-08-23/24 is inert on this machine.

3. **Make the per-hook `--selftest` form isolated.** `python hooks/<name>.py --selftest` is not
   covered by the #46 fix, which lives at the `run_selftests` choke point. Real for solo use:
   it is how a single hook gets debugged, and under a git hook it writes to the real repo. The
   scrub belongs in a shared `--selftest` dispatch that does not exist yet.
4. **Pin the #46 control's own wiring** (gate 9's H3, half-built). `scrub_environ()` at the top
   of `main()` is guarded by nothing - moving it into an uncalled helper leaves all 41 gates
   green. `unrecorded_tiers` is the mechanism to copy.
5. **Decide whether to wire `piped_gate_guard` at all - and only then fix its `pipefail` disarm.**
   The re-cut originally listed this as "the highest-value residue row, a live PreToolUse hook".
   **That was false and the source-coverage pass caught it**: it is wired NOWHERE in
   `settings.json` (verified 21:20:34Z), so its defect currently costs nothing and fixing it
   first would have been this plan's own standing check 4 violated on line 70 of the plan that
   restates it.
   The decision is real, though, and the evidence is from this session rather than theory: I read
   `$?` after piping a gate into `head`/`tail` **twice today** and misread a FAIL as a pass both
   times. If it gets wired, gate 9's M10 becomes live immediately - `# remember set -o pipefail`
   on any earlier line silently turns the DENY into an allow - so wire and fix together, never
   wire alone.
6. **`fast_test_disclosure` records its marker before printing** (L3), so an unwritable state dir
   silences the #25 notice permanently. Small, and it is a hook that runs every turn.

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
