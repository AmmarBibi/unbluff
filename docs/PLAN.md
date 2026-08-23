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

1. **Merge `main` into `feat/enforcing-verify`.** **DONE 2026-08-23.** Diverged 1 vs 17 at the
   merge. Exactly one conflicting file as predicted; resolved by RE-MEASURING the merged tree
   rather than by picking a side, which independently reproduced the planned union
   (`pre_push_gate_selftest.py` 1131 - main grew it, the branch's 1109 was stale;
   `tools/no_regression.py` out at 719, under the 800 limit). file-size gate rc 0, 5 offenders.
   Suite 38/39 - `hook-provenance` only, and see #39: that is a worktree artifact, rc 0 in the
   main checkout with a byte-identical sha.
2. **Fix the execution model** (#25). **DONE 2026-08-23.** All three parts shipped; suite 39/40
   (`hook-provenance` only, see #39).
   - turn end: auto-detect KEPT, `hooks/fast_test_disclosure.py` added. **The plan said "naming
     the exact command" and that was wrong** - the exact commands are `npm test --silent` and
     `"<py>" -m pytest -x -q`, and neither names the untrusted part. It discloses the
     `scripts.test` BODY and the `conftest.py` files pytest imports. Keyed on the disclosed
     CONTENT, not the project, so a repo that changes what runs is disclosed again.
   - `--install-global` pre-push: auto-detect OFF unless `repo_opted_in()` - DERIVED from the
     presence of a shim naming `pre_push_gate.py`, so `--install` IS the consent record and there
     is no new state to drift. Declines loudly and ALLOWS the push.
   - `SECURITY.md` shipped.
   - Two defects found by probing rather than by review, both recorded because they generalise:
     (a) the disclosure import was first written inside `try/except ImportError`, which
     `install.py`'s `_import_closure` treats as OPTIONAL and drops from the install roster -
     MEASURED 26 unguarded vs 25 guarded, i.e. it would have been dead in silence on every
     installed machine; (b) a mutation SURVIVED because opt-in was tested only by presence, so a
     husky/lefthook `pre-push` counted as consent - scenario 15c now covers it. 4/4 killed after.
3. **Prove the README subset** (#6, #28). **PARTIAL.** ELEVATED - this replaces "drop criterion
   1": ~30 README rows, not all 243. DONE (8390060): the stale transcript (38 -> 39) and the
   installer cardinality ("4 entries" -> 5, with PreToolUse/piped_gate_guard finally named).
   REMAINING: the three front-page sentences the repo's own tests CONTRADICT, and rewriting
   `findings.json`'s `exclusion_basis`, which names criterion 1 as the ONLY route back for 42
   excluded findings (10 HIGH) - give them a real route before the criterion goes away.
4. **Mechanise the network claim** (#32a). **DONE 2026-08-22 (a80937c).** The README's strongest
   trust badge - "no network, no telemetry" - was enforced by nothing: a hook that opened a
   socket would have passed every gate. `tools/check_no_network.py` scans by AST (not grep - the
   file names every networking module and would flag itself), population DERIVED, fails closed,
   registered ENFORCING. 58 files / 0 reaches; pinned NONET-BLIND + NONET-FLOOR. It flagged
   ITSELF on its first tracked run - `frozenset({...})` is a Call - which is the fires-on-correct-
   work shape; fixed by restricting to real spawns, with two negative controls so it cannot
   silently revert. NOTE #32's other items (demo GIFs, upgrade path, CONTRIBUTING, 103 absolute
   home paths in docs) are NOT done and stay in Phase 2.
5. **Fix the shipped skill that audits documents it never read** (#16). `consistency-audit`'s
   PyMuPDF branch returns unvalidated text, so a scanned PDF reports CLEAN.
6. **Fix `check_file_size`'s live C1** (#31). **DONE 2026-08-22 (1d90cff)** - every exit now routes
   through one `_record` helper; verified BY INDUCTION (an unparseable baseline writes
   `CANNOT_RUN`), not by reading the diff.
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

**#40 (new, 2026-08-23): `readme-fresh` checks the transcript's COUNT but never its ROSTER.**
Found while fixing the count for gate 2: the pasted transcript had been missing `no-network: OK`
since a80937c (gate 4) and nothing noticed, because the gate only compares "all N selftests
passed" against the suite size. It also carried `gate modes: 16 row(s)` against a live 17, which
no gate reads at all. A name can therefore be dropped from the evidence block silently. Belongs
with gate 3 - it is the MECHANISM for "the README says only true things", not a separate idea.

**#39 (new, 2026-08-23): `hook-provenance` fires on correct work inside a git worktree.** Derived
at the gate-1 merge: rc 1 in `unbluff-enforcing`, rc 0 in the main checkout, `foreign=ad9b23e864e5
repo=ad9b23e864e5`, AST delta 0 - byte-identical, flagged only because the wired path is the main
checkout's. Not a release blocker (CI runs in a plain checkout), but it is standing check 6's own
failure shape in a shipped gate, so it does not get to stay unnamed.

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
