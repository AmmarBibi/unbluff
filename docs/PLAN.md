# unbluff - the plan

**Two pages, deliberately.** A briefing document that only grows stops being read, and the one
load-bearing line gets skipped. If this needs a third page, something in it is a GitHub issue.

## What unbluff is

Claude Code hooks that make silence and success look different, **plus four skills**
(`meta-review`, `source-coverage`, `consistency-audit`, `completeness-audit`) that `install.py`
copies into `~/.claude/skills`. The skills are shipped surface, not internal tooling - forgetting
that hid a release blocker once already.

**In use**: 7 hook commands wired in `~/.claude/settings.json` plus a global `core.hooksPath`,
running live from `C:\Users\ammar\Downloads\unbluff`. Public MIT repo, maintained partly as a
career artifact - which means an unpublished month delivers none of its point.

Artifact version **v1.3.1** (tagged, unreleased; last GitHub *Release* is v1.2.1, 2026-07-22).
There is no v1.3.0 tag and never was. The old "v1.0 criteria" was a quality bar, not a version;
that framing is retired.

## The bar

**Would I defend this release under adversarial review?**

This replaces the previous rule ("false, dangerous, or broken on someone else's machine"), which
was a MINIMUM-honest bar written to stop a spiral - the backlog had gone 6 items to 37 while
nothing shipped. Bounding the spiral was right; shipping the minimum was not. Four things move
into Phase 1 under the real bar, and they are marked ELEVATED below.

Materiality still decides ORDER, never WHETHER.

## Phase 1 - what must be true before v1.4.0

1. **Merge `main` into `feat/enforcing-verify`.** Diverged 1 commit vs 12. Only overlapping file
   is `docs/audits/file_size_baseline.json`; resolve to the UNION (`pre_push_gate_selftest.py` =
   1131, `no_regression.py` removed), re-run the file-size gate. Safe to do FIRST: the branch
   touches neither `fast_test_on_stop.py` nor `pre_push_gate.py`, so it cannot collide with gate 2.
2. **Fix the execution model** (#25). DECIDED: auto-detect runs an untrusted repo's test entry
   point with no opt-in - a bare root `conftest.py` is enough, because pytest imports it. The two
   paths have different trust properties and get different answers:
   - turn end: KEEP auto-detect, add a one-time per-repo stderr notice naming the exact command
     before the first run. Trust is implied by opening Claude Code there; the missing piece is
     that the user never sees what will run.
   - `--install-global` pre-push: NO auto-detect. It fires in every repo on the machine with
     Claude Code closed, where nothing implies trust. Require an explicit `.claude/pre-push.cmd`.
   - ship a `SECURITY.md` stating the model and a private reporting route.
3. **Prove the README subset** (#6, #28). ELEVATED - this replaces "drop criterion 1". ~30 README
   rows, not all 243. Three front-page sentences are contradicted by the repo's own tests, and the
   installer cardinality is wrong ("4 entries" -> 5, "eighteen pieces"). Shipping a README the
   repository refutes is the one defect that would actually discredit a tool whose thesis is "do
   not take claims on faith". Also rewrite `findings.json`'s `exclusion_basis`, which names
   criterion 1 as the ONLY route back for 42 excluded findings (10 HIGH) - give them a real route.
4. **Mechanise the network claim** (#32a). ELEVATED. The README's strongest trust badge - "no
   network, no telemetry" - is enforced by nothing; a hook that opened a socket would pass every
   gate. An AST scan over `hooks/` and `tools/` is a small file and retires a whole class of
   unproven claim. On a public repo accepting PRs this is the cheapest high-value gate available.
5. **Fix the shipped skill that audits documents it never read** (#16). `consistency-audit`'s
   PyMuPDF branch returns unvalidated text, so a scanned PDF reports CLEAN.
6. **Fix `check_file_size`'s live C1** (#31). ELEVATED - I reported this class fixed there and it
   is not; two CANNOT-RUN exits still write no ledger row.
7. **Make the release notes publishable** (#29). `[Unreleased]` is 19 KB of internal workflow ids
   and agent telemetry. Settle v1.3.1: retroactive Release (recommended) rather than deleting a
   public tag.
8. **Fix install/uninstall** (#30). `--uninstall` cannot undo `--install-global`; following the
   README leaves every `git push` on the machine broken.
9. **Independent adversarial review of this session's code** (#20). ELEVATED from "a gate" to a
   real pass: 1,215 lines of new Python, most of it guard logic, reviewed by nobody but its author.
10. **One clean full sweep at the release HEAD** (#37) and **CI green via a PR** (#26). No clean
    sweep exists for the current HEAD - the last one is six commits back - and no commit on this
    branch has ever run in CI. A PR is the only trigger: pushing the branch runs nothing.
11. **Tag v1.4.0**, then convert the ledger to GitHub issues.

## Phase 2 - post-release, as GitHub issues

#3, #4, #5, #7, #8, #13's pinning, #15, #17, #18, #19, #21, #22, #24, #33, #34, #35's residue.

**#10 is SUPERSEDED** - it would restore a second competing order. Delete
`NEXT_SESSION_PROMPT.md` or reduce it to a pointer here.

**Convert the ledger to GitHub issues at release.** A 37-item list in a session tool is invisible,
dies with the session, and answers "what are we building?" to nobody. Public issues are durable,
honest, and read as a maintained project - which the local list serves not at all.

## Standing checks on every change

Each caught a real defect that nothing else did.

1. **Did this fix create a new instance of the class it fixed?** Caught a C7 instance introduced by
   the commit fixing C7 elsewhere.
2. **What would have to be true for this control to be UNABLE to fire?** Caught `load_with_siblings`
   failing open and `roster_gaps` accepting a non-existent tree.
3. **Is the number derived, and derived just now?** 30 of 53 claims checked failed - almost all of
   them true when written. Corollary: **no mutable count in a task title or a heading** - "10
   commits" rotted to 11 to 12 in one day. Counts live in the body, dated.
4. **Is this surface actually LIVE?** A session went into `piped_gate_guard`, which is not wired on
   the maintainer's machine and has never fired.
5. **Never edit while a gate is in flight.** Broken three times in one day, three sweeps discarded.
   Being mechanised as #21.
6. **A probe that has not been shown to FAIL is not a probe.** Four probes were invalid on first
   write - a no-op mutation, a `/tmp` copy that broke `REPO`, a `.bat` where Windows only searches
   `.exe`, a wrong-keyed extractor - and every one returned a COMFORTING answer. Show the probe
   failing before trusting it passing.
7. **An agent's finding is a hypothesis.** A confirmed "zero-interaction RCE" did not reproduce
   under three of my own probes. Verify before reporting, and before fixing.
