# unbluff - the plan

**Scope changed 2026-08-24: this is a tool I use, not a product I ship.** The previous plan is
archived verbatim at [plan_v140_retired](audits/plan_v140_retired_2026-08-24.md) - 284 lines,
12 gates, written against a premise that no longer holds. Nothing was deleted; it was retired.

## Why it was re-cut, with the number that decided it

The old plan's premise was its own second paragraph: *"Public MIT repo, maintained partly as a
career artifact - which means an unpublished month delivers none of its point."* Every gate
descended from that. With no release, most of them serve nobody.

Measured on the v1.4.0 branch (`b6cc6cc...HEAD`, 2026-08-24T20:32:53Z), lines changed by area:

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

## The bar

**Does this make my sessions better?**

Replaces *"Would I defend this release under adversarial review?"*, which was a shipping bar. A
change that only makes the repo more defensible to a stranger is no longer worth doing.
Materiality still decides ORDER, never WHETHER - anything kept here gets built.

## Open - and this list is deliberately short

1. **Land the branch.** `feat/enforcing-verify` -> `main` via
   [PR #3](https://github.com/AmmarBibi/unbluff/pull/3). This is the whole point of the branch
   for a solo user: `main` currently still has (a) a moved or renamed clone **bricking every
   `git push` on the machine**, (b) the consistency-audit skill certifying a **scanned PDF as
   CLEAN** without reading it, (c) the pre-push gate **blocking correct pushes** (#45), and
   (d) the selftest that **corrupted the repo and pushed a one-file tree to public `main`**
   (#46). Merging also permanently clears `hook-provenance`, which fails today only because the
   wired copy is `main`'s older one.
2. **Repair the main clone's git config** - `core.bare=true`, a `core.hooksPath` pointing at a
   deleted temp directory (so **that repo's git hooks are all disabled right now**), a `t@t`
   identity, and a stale `[branch]` section. All four are #46 residue. Blocked on a
   tool-permission classifier; the command is in
   [gate 0 evidence](audits/gate0_evidence_2026-08-24.md) s6.
3. **Make the per-hook `--selftest` form isolated.** `python hooks/<name>.py --selftest` is not
   covered by the #46 fix, which lives at the `run_selftests` choke point. Real for solo use:
   it is how a single hook gets debugged, and under a git hook it writes to the real repo. The
   scrub belongs in a shared `--selftest` dispatch that does not exist yet.
4. **Pin the #46 control's own wiring** (gate 9's H3, half-built). `scrub_environ()` at the top
   of `main()` is guarded by nothing - moving it into an uncalled helper leaves all 41 gates
   green. `unrecorded_tiers` is the mechanism to copy.
5. **`piped_gate_guard` is disarmed by the word `pipefail` before the first pipe** (gate 9's
   M10, verified by execution). This one is a **live PreToolUse hook**, so it is the highest-value
   residue row: a DENY guard that silently allows.
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
  in instruments rather than in hooks, none of them changing a session. Full statements survive
  in [gate 9 review](audits/gate9_review_2026-08-24.md).
- **#42, #43, #6/#28 (the 243-claim inventory).** Claim-proofs and cardinality gates for
  documents nobody but me reads.
- **The `pre_push_gate_selftest.py` split (#41's remaining half).** 1192 lines and the largest
  file here, but splitting it is refactoring an instrument. Its seam and the reason it was not
  attempted are recorded in `file_size_baseline.json`.
- **`install_selftest.py` has never been adversarially reviewed.** 358 lines, split out
  2026-08-24. `check_review_freshness` will keep asking; that is fine and it can keep asking.

**Undecided, deliberately:** whether the repo stays public. It is currently public and is also
the career artifact the old premise was built on. Parked by choice on 2026-08-24, not forgotten.

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
4. **Is this surface actually LIVE?** A session went into `piped_gate_guard`, which is wired but
   had never fired. The 13%-of-the-branch measurement above is this check applied to a whole
   release.
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
