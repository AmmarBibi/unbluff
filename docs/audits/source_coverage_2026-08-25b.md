# Source-coverage audit - 2026-08-25 (session 4)

Run against the **DESIGN**, not only the code, as instructed. The unit under audit is this
session's item 10 (`hooks/wired_clone_sanity.py` + `hooks/wired_clone_sanity_selftest.py`).

## STEP 1 - name the sources

"Done" for item 10 is defined against these, not against item 10's own description:

1. **`tools/git_isolation.py`'s header** - the authoritative account of the #46 incident,
   enumerating what was actually damaged, file and line.
2. **`git_isolation.fingerprint()`'s docstring** - the enumeration of the mutable state a runaway
   fixture can damage, written as *"each line is here because something changed it"*.
3. **`docs/audits/meta_review_2026-08-25.md` CHECK 2** - which created item 10.

## STEP 2 - enumerate the SOURCE, not the plan

The incident account lists **six** damage instances; `fingerprint()` groups the state into
**five** classes. Enumerated before looking at what item 10 does:

| # | source item | where the source names it |
|---|---|---|
| S1 | `git init --bare` set `bare = true` on the real repo | header, `meta_audit_on_stop:543` |
| S2 | `user.email=t@t` / `user.name=t` written to the real config | header, `:555-556` |
| S3 | a fixture commit made AND `git push` over the public default branch | header, `:557-577` |
| S4 | real `core.hooksPath` pointed at a temp dir that was then deleted | header, `pre_push_gate_selftest:1116` |
| S5 | a linked WORKTREE registered in the real repo | header, `fast_test_on_stop_selftest:902` |
| S6 | a `fixture` commit left behind | header, `check_review_freshness:330` |
| S7 | HEAD moved onto a fixture commit; `feature`/`wt` refs created; index replaced | `fingerprint()` docstring |
| S8 | stale `branch.<name>.*` config section | item 2's repair record |

## STEP 3 - reconcile

| source item | status |
|---|---|
| S1 `core.bare` on a worktree repo | **BUILT** - `repo_config_problems`, gated on `has_worktree` so a genuinely bare repo is left alone; probed both directions |
| S2 fixture identity | **BUILT** - `fixture_identities()` derives the vocabulary from the suite's own source; probed |
| S4 dead `core.hooksPath` | **BUILT** - resolves `~`, resolves relative against the worktree, `isdir` checked; probed with existing / relative / spaced controls |
| **S5 stray linked worktree** | **GAP -> SCHEDULED as item 14** |
| S3 / S6 stray commit or push | **FINALIZED EXCLUSION** - not decidable from standing state without a fixture-name roster; a user legitimately has local commits |
| S7 HEAD / index | **FINALIZED EXCLUSION** - transient working state; a standing check fires on correct work constantly |
| S7 refs (`feature`, `wt`) | **FINALIZED EXCLUSION** - needs a roster of fixture names, and a real branch called `feature` is not a defect |
| S8 stale `branch.*` section | **FINALIZED EXCLUSION** - harmless; unlike a dead hooksPath it disables nothing |

## The finding, and why it is the kind only this pass catches

**Item 10 built a standing check for ONE of the five classes `fingerprint()` names** - `config`,
and 3 of its 4 fields. Read from item 10's own text this looks complete: it says "the three
questions" and it answers all three. Read from the SOURCE, the three questions are one slice of a
five-class enumeration that the design document had already written down.

The gap is not that the other classes were considered and rejected - **it is that they were never
enumerated, so no decision about them was ever recorded.** A grep over the plan could not find
this, because the plan did not mention them. That is the whole definition of the failure mode.

**S5 is the one that is genuinely material**, and it is material for exactly the reason item 10
accepted S4: a linked worktree registered under a system temp directory that no longer exists is
silent, persistent residue pointing at a deleted path - the same shape as a dead `core.hooksPath`.
It is decidable with one read-only command, and it cannot false-alarm, because a live worktree's
path exists by definition. Verified on this machine 2026-08-25: two worktrees registered
(`unbluff` at `b6cc6cc`, `unbluff-enforcing` at `4072b51`), both present, so the check would be
green today and is being scheduled on its merits rather than on a live failure.

The other four are now **finalized exclusions with written reasons**, which is the state they
should have been in the moment item 10 was designed.

## STEP 4/5 - ledger + verify

Every S-item above has exactly one status. Item 14 is in the plan in materiality order, and the
exclusions carry their justifications inline rather than in this file alone, so they survive
without it. The plan carries no optional-forever language (see the completeness artifact).
