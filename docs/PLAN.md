# unbluff - the plan

**Two pages, deliberately.** A briefing document that only grows stops being read, and the one
load-bearing line gets skipped. If this needs a third page, something in it is a GitHub issue.

> **BREACHED AND THEN REPAIRED, 2026-08-23.** This file reached 254 lines (from 110 at the start
> of that session - the "111" quoted in the session prompt was itself never derived, and was
> off by one). The cause was diagnosed rather than guessed: the gate count has been FROZEN at 11
> since 2026-08-22 and DONE went 0 -> 7, so the growth was not new scope, it was closing EVIDENCE
> being written into the rows instead of into `docs/audits/`. Closed rows are now one line plus a
> link; the evidence lives in `docs/audits/gate_evidence_2026-08-23.md`. Rule for anyone adding
> here: a row states the OUTCOME and points at the proof. It does not carry the proof.

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
0. **CRITICAL - `pre_push_gate_selftest.py` COMMITS TO THE REAL REPOSITORY when the suite runs
   from inside a git hook** (#46, found 2026-08-24). Numbered 0 because it precedes everything:
   until it is fixed, **every push from a worktree corrupts the repo**, so gates 9, 10 and 11
   cannot safely run. OBSERVED, not theorised - the first real `git push` of this branch left
   six fixture commits (`seed`, `local only`, `ahead of upstream`, `on a branch that was never
   pushed`, `seed`, `fixture`) in the reflog, moved `feat/enforcing-verify` off my work onto a
   FIXTURE commit `8f63aec`, created a stray branch `feature`, and replaced the index with a
   935-byte fixture index. Repaired non-destructively (`branch -f` + `symbolic-ref` +
   `read-tree`); nothing was lost, and `--hard` was never needed.
   MECHANISM PROVEN BY PROBE, not inferred: a git hook exports `GIT_DIR`, and `GIT_DIR` OVERRIDES
   `git -C <tmpdir>`. Probe output - with `GIT_DIR` set, `git -C <tmpdir> rev-parse
   --absolute-git-dir` returned `.../unbluff/.git/worktrees/unbluff-enforcing`. Every temp-repo
   fixture in that 1131-line selftest therefore operates on the real repository, and `grep`
   confirms it passes `dict(os.environ)` through with no scrubbing at any of its ~6 git call
   sites. PRESCRIBED FIX (a hypothesis until re-executed): strip `GIT_DIR`, `GIT_INDEX_FILE`,
   `GIT_WORK_TREE`, `GIT_OBJECT_DIRECTORY` and `GIT_COMMON_DIR` from the env of every git
   subprocess in a temp fixture, and add a gate that FAILS if any selftest leaves the repo's HEAD,
   index or branch refs changed - the tree-guard shape, which this repo does not currently have.
   Note the irony for the write-up: the defect was invisible in six direct suite runs and only
   appeared once the suite ran where it actually ships - inside the hook.
1. **Merge `main` into `feat/enforcing-verify`.** **DONE** `d89e3dc`. Baseline conflict resolved by RE-MEASURING the merged tree, which independently reproduced the planned union. See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-1).
2. **Fix the execution model** (#25) **DONE** `13a8845`. Disclosure of the untrusted surface (not the wrapper), no auto-detect for repos that never opted in, `SECURITY.md` shipped. See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-2).
3. **Prove the README subset** (#6, #28) **DONE** `1aed8cc`, and RE-CUT: the gate is claims the tests CONTRADICT, not an unenumerated ~30. Piece count AND roster now derived and gated. Criterion 1 survives as #6/#28, so `findings.json` needed no rewrite. See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-3).
4. **Mechanise the network claim** (#32a) **DONE 2026-08-22** `a80937c`. `tools/check_no_network.py`, population derived, fails closed. 59 files / 0 reaches (2026-08-23). See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-4).
5. **Fix the shipped skill that audits documents it never read** (#16) **DONE** `2200229`. A scanned PDF is refused with an OCR instruction instead of reported CLEAN; pinned as PDF-1. See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-5).
6. **Fix `check_file_size`'s live C1** (#31) **DONE 2026-08-22** `1d90cff`. Every exit routes through one `_record` helper, verified by induction. See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-6).
7. **Make the release notes publishable** (#29) **PARTIAL** `a9b5cc6`. Reader-facing `[1.4.0]` written, 19 KB of working notes moved verbatim to `docs/audits/changelog_v1_4_0_engineering_log.md`. **The retroactive v1.3.1 GitHub Release is NOT published - that is the user's call.** See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-7).
8. **Fix install/uninstall** (#30) **DONE** `31ec83e`. Fixed at the CLASS: both shims now fail loud-but-open when the clone has moved, instead of blocking every push on the machine. See [gate evidence](audits/gate_evidence_2026-08-23.md#gate-8).
9. **Independent adversarial review of this session's code** (#20). ELEVATED from "a gate" to a
   real pass: 1,215 lines of new Python, most of it guard logic, reviewed by nobody but its author.
   **#46 is the strongest argument yet for this gate**: it sat in the most-edited file on the
   branch, and no amount of self-review found it - running the code where it ships did.
10. **One clean full sweep at the release HEAD** (#37) and **CI green via a PR** (#26). No clean
    sweep exists for the current HEAD - the last one is six commits back - and no commit on this
    branch has ever run in CI. A PR is the only trigger: pushing the branch runs nothing.
11. **Tag v1.4.0**, then convert the ledger to GitHub issues.

## Phase 2 - post-release, as GitHub issues

#3, #4, #5, #7, #8, #13's pinning, #15, #17, #18, #19, #21, #22, #24, #33, #34, #35's residue.

**#6/#28 - criterion 1, the full claim inventory.** Added 2026-08-23 by the close completeness
audit, which found it had NO HOME. Gate 3 asserts "criterion 1 survives as a post-release issue"
and that assertion was load-bearing: the whole argument for re-cutting gate 3 was that the 42
excluded findings (10 HIGH) keep their route back BECAUSE the criterion survives. It was never
added to this roster, so for three hours it survived in prose only - which is the same orphaning
as the plan I rejected, arrived at by a different route. Denominator to carry forward: 243 claims
= README 152 (70 proven / 82 unproven) + `skills/*/SKILL.md` 91 (15 / 76). A1's open question -
whether an imperative instruction to an agent is a behavioural assertion, worth exactly the 76
unproven SKILL.md rows - is part of it and is still undecided.

**#40 is CLOSED (2026-08-23), not open.** Listed below as a finding for the record; the gate was
built in the same commit that found it. Left in place rather than deleted because the entry
explains why `check_readme_fresh` now checks a roster and not only a count.

**#44 (CLOSED 2026-08-23 in the same commit that found it): a mutation run wrote itself into the
gate ledger as a real failure.** Found by the close meta-review's CHECK 4, which is instructed to
READ the ledger rather than reconstruct it - and the ledger was lying. After probing the gate-8
shim fix, the newest `integration` row read FAIL 33/34 from a MUTATED tree, eight minutes after
the real tree passed 34/34. Anything reading the ledger to decide whether the gates passed - the
release process, a future session, this very skill - would have concluded integration fails at
HEAD. `gate_ledger.record()` now honours `UNBLUFF_LEDGER_OFF`; probes set it, nothing else does,
and the selftest asserts BOTH that it suppresses and that it is not sticky (a probe forgetting to
unset it would silently stop recording every real gate, which is the worse failure). Mutation-
probed: neutering the guard turns the selftest red. The polluted row was corrected by re-running
integration clean - 34/34 at 2026-08-23T15:09:18Z.

**#43 (new, 2026-08-23): two of `SECURITY.md`'s three trust claims are enforced by nothing.**
Found by the close source-coverage pass, which read the DESIGN rather than the code. "No network"
is gated by `check_no_network`; "no writes outside the repo and the state dir" and "no credential
access" are gated by nothing at all - grep across `tools/`, `hooks/`, `tests/` finds no check for
either. I wrote both into a security document in the same session, one file away from the gate
that exists precisely because the README's "no network" badge was once enforced by nothing. That
is standing check 1 firing for the SECOND time today on my own work. `SECURITY.md` now labels
them ASSERTED-NOT-ENFORCED rather than listing them beside the enforced one, which is the
honest interim; the gates themselves are this row. A no-writes gate is the easier of the two (AST
walk for `open(..., 'w')`, `os.remove`, `shutil` outside two roots, same shape as
`check_no_network`); credential access needs a roster of what counts (netrc, keyring, GIT_ASKPASS,
secret-shaped env reads) and negative controls before it is worth anything.

**#42 (new, 2026-08-23): `PLAN.md` and `CHANGELOG.md` cardinalities are gated by nothing.** The
close consistency audit caught "58 files" for the no-network population in BOTH, against a live
59 - broken the same day by this session's own new file, and copied into the new release notes by
re-using the plan's wording instead of re-deriving. Three README cardinalities are now derived and
gated (`readme-fresh`); the same numbers in the plan and the changelog have no control at all, so
this one was found by an audit rather than by a gate. Same REMEMBER-vs-ENFORCE shape as #40.

**#41 (new, 2026-08-23): the size ratchet is now steering where code goes, and that is a signal.**
Three files hit the cap in one session. `fast_test_on_stop.py` (851) and
`pre_push_gate_selftest.py` (1192) were re-recorded with reasons - the SECOND and THIRD
re-records against a baseline whose own note says the next growth should be preceded by a split.
`pre_push_gate.py` is at 792 of 800, eight lines of headroom. Gate 8's test went into
`tests/test_integration.py` partly because its natural home was full, which is the ratchet
choosing architecture. Two clean splits are available and both have precedent in this repo:
`install.py`'s `selftest()` is 299 of its 927 lines, and `pre_push_gate_selftest.py` is the
largest file here. Do them before the next feature, not after.

**#40 (new, 2026-08-23): `readme-fresh` checks the transcript's COUNT but never its ROSTER.**
Found while fixing the count for gate 2: the pasted transcript had been missing `no-network: OK`
since a80937c (gate 4) and nothing noticed, because the gate only compares "all N selftests
passed" against the suite size. It also carried `gate modes: 16 row(s)` against a live 17, which
no gate reads at all. A name can therefore be dropped from the evidence block silently. Belongs
with gate 3 - it is the MECHANISM for "the README says only true things", not a separate idea.

**#39 (FIXED 2026-08-24, and the finding INVERTED on the way): `hook-provenance` treated a linked
worktree as a foreign copy.** As filed it was a pure false positive - at `f1f309c` all 29 wired
references were byte-identical (`foreign=ad9b23e864e5 repo=ad9b23e864e5`, AST delta 0), flagged
only because a worktree's path is not the wired path. Fixed by asking git whether the two paths
share a common dir AND whether the bytes match; both required, so a separate clone or a genuinely
stale copy still fails, and any uncertainty fails closed.

**The fixed gate then found something real, which is the point of fixing it.** Foreign dropped
29 -> 22 and the surviving 22 are not worktree noise: `AST delta 66 tokens, DIFFERENT PROGRAMS`,
`foreign=ad9b23e864e5 repo=d6c2fcb0cac3`. Confirmed by hash - the wired file IS
`main:hooks/pre_push_gate.py`, and this branch differs by 91 insertions, i.e. exactly gates 2 and
8. **The pre-push gate live on this machine is the PRE-FIX version**: still auto-detecting in
every repo under `--install-global` (#25), still hard-blocking every push if the clone moves
(#30). Expected mid-release, and it resolves when this branch reaches `main`.

**#45 (new, 2026-08-24): a machine-state check is blocking a code push.** Consequence of the
above. The push gate runs `python run_selftests.py`, rc 1 while `hook-provenance` correctly
reports that drift - so the gate now BLOCKS the very push that would fix it. That is not a defect
in the code being pushed: it is a MACHINE-STATE question ("is this box wired to a current copy?")
sitting inside a CODE gate. **RESOLVED 2026-08-24 in `73e04bf`** - and the close completeness
audit caught this row still reading "none taken" three commits after one was. Taken: a
`MACHINE_STATE` roster in `run_selftests` plus `--code-only`, which excludes such gates from the
VERDICT and nothing else, declared through an explicit `.claude/pre-push.cmd`. The `--no-verify`
option was REJECTED: it disables every gate to route around one. Probed, not argued - with
`check_python_floor.py` replaced by `sys.exit(1)`, `--code-only` still returned rc 1.

**#47 (new, 2026-08-24, found by the close source-coverage pass reading the DESIGN):
`--code-only` is asserted to be "deliberately NOT the default" and nothing enforces it.**
`.claude/pre-push.cmd` says so in a comment; a comment is advisory. Adding `--code-only` to
`.claude/fast-test.cmd` would silently weaken the strictest check in the project and no gate
would notice - the same shape as the README's "no network" badge before `check_no_network`
existed. Fix: assert in `run_selftests --selftest` that the turn-end command does not carry
`--code-only`. Small, and it closes the loop the flag opened.

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
