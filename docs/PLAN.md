# unbluff - the plan

**Two pages, deliberately.** A briefing document that only grows stops being read, and the one
load-bearing line gets skipped (tooling-discipline 7.3). If this file needs a third page,
something in it belongs in a GitHub issue instead.

## What unbluff is

A set of Claude Code hooks that make silence and success look different. It is **in use**: 7 hook
commands wired in `~/.claude/settings.json` plus a global `core.hooksPath`, running live from
`C:\Users\ammar\Downloads\unbluff`. It is a public MIT repo, maintained partly as a career
artifact.

**Two numbering systems caused real confusion and one is now retired.** The artifact version is
**v1.3.1** (tagged, unreleased; last GitHub *Release* is v1.2.1, 2026-07-22). The old "v1.0
criteria" was a four-part QUALITY BAR, not a version. That framing is dead - see the stopping rule.

## The stopping rule (this is the point of the replan)

Before v1.4.0, work is in scope **only if it makes the published artifact false, dangerous, or
broken on a machine that is not the author's.** Everything else is a post-release issue.

This exists because the backlog went from 6 items to 32 in one session while nothing shipped. Every
one of the 32 is real. Most do not belong in front of a release.

## Phase 1 - ship v1.4.0

Ordered. Each line is a gate, not a suggestion.

1. **Merge `main` into `feat/enforcing-verify`.** They have diverged (1 commit vs 10). The only
   overlapping file is `docs/audits/file_size_baseline.json`, and it conflicts in both directions -
   resolve to the UNION (`pre_push_gate_selftest.py` = 1131, `no_regression.py` removed), then
   re-run the file-size gate. Do this FIRST; divergence only grows.
2. **Decide the shell-exec posture** (#25). `fast_test_on_stop` runs a command read from any cloned
   repo's `.claude/fast-test.cmd` through a shell, and `pre_push_gate` now does too. Releasing
   multiplies installs. Needs a SECURITY.md, a README warning, or an opt-in gate - a decision, not
   a code change.
3. **Fix what the repo itself refutes** (#28). Three README sentences are contradicted by the
   project's own tests; the installer cardinality is wrong ("4 entries" -> 5, "eighteen pieces").
   Ten minutes, and it is the salvageable core of the old criterion 1.
4. **Make the release notes publishable** (#29). `[Unreleased]` is 19 KB of internal workflow ids
   and agent telemetry. Also settle v1.3.1: retroactive Release, or delete the tag. (v1.3.0 does
   not exist - the earlier premise was wrong.)
5. **Fix install/uninstall** (#30). `--uninstall` cannot undo `--install-global`; following the
   README leaves every `git push` on the machine broken.
6. **Independent review of this session's code** (#20). 1,215 new lines of Python, most of it guard
   logic, none of it reviewed by anyone but its author.
7. **Push the branch and get CI green** (#26). None of the 10 commits has ever run in CI, and
   tagging currently triggers no CI at all.
8. **Tag and release.**

## Phase 2 - post-release, as GitHub issues

Everything else: #3, #4, #5, #7, #8, #13's pinning, #15-#19, #21, #22, #24, #27, #31, #32.

**Convert the task ledger to GitHub issues at release time.** A 32-item list in a session tool is
invisible, dies with the session, and answers "what are we building?" to nobody. The same list as
public issues is durable, is the honest answer to that question, and reads as a maintained project
- which is the career-artifact goal the local list serves not at all.

## Standing checks on every change

Written down because each one caught a real defect today that nothing else did.

1. **Did this fix create a new instance of the class it fixed?** Caught a C7 instance introduced by
   the commit that was fixing C7 elsewhere.
2. **What would have to be true for this control to be UNABLE to fire?** Caught `load_with_siblings`
   failing open and `roster_gaps` accepting a non-existent tree.
3. **Is the number derived, and derived just now?** 30 of 53 claims checked this session were
   imprecise or wrong - almost all of them numbers that were true when written.
4. **Is this surface actually LIVE?** `piped_gate_guard` was hardened for a session and is not wired
   on the author's machine.
5. **Never edit while a gate is in flight.** Broken three times in one day, costing three sweeps.
   Being mechanised as #21, because prose did not hold.

## Out of scope, decided

**The old criterion 1 (proving all 243 README claims) is dropped** - with one caveat that must be
settled first (#27): `findings.json` records criterion 1 as the ONLY route back for 42 excluded
findings, 10 of them HIGH. Dropping it makes that exclusion permanent. Keep a README-only subset
(item 3 above) rather than the full inventory.
