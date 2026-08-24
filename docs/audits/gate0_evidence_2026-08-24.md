# Gate 0 (#46) - evidence, and a correction to the diagnosis

All figures derived 2026-08-24 between 16:47Z and 17:35Z, in that session, against
`feat/enforcing-verify` at `daea7db`. Every one is dated next to what produced it, because a
staleness count in this very repo drifted 15 -> 16 between being drafted and being committed.

## 1. The ledger understated this. It reached GitHub.

`docs/PLAN.md` gate 0 recorded six fixture commits, a moved branch, a stray `feature` branch and a
replaced index - all local. The session prompt carried **"NEVER PUSHED"**. Both are false.

| derived at | fact |
|---|---|
| 16:48:26Z | `git ls-remote origin refs/heads/main` -> **`b70872c "local only"`** |
| 16:49:52Z | `git rev-list --count b6cc6cc..b70872c` -> **28** commits published beyond the real main |
| 16:52:49Z | `git ls-tree b70872c` -> **one file, `f.txt`**. `b6cc6cc` has 128, `daea7db` has 147 |
| 16:52:49Z | `git cat-file -p 587be6b4` -> `x\n` |
| 16:50:48Z | repo is PUBLIC, 2 stars, 0 forks, `pushedAt 2026-08-24T05:55:02Z` |
| 16:52:31Z | `actions/workflows` -> `total_count: 0`; `git ls-tree b70872c .github/workflows/` -> empty |
| 16:49:05Z | `git merge-base --is-ancestor b6cc6cc b70872c` -> rc **0** |

The last row is the good news and it decided the repair: the corrupted push was a **fast-forward,
not a force-push**, so no public history was destroyed and the fix was one force-push back. Tags
(`v1.3.1` = `56f8932`) and the five published Releases were untouched throughout.

The workflow row explains the silence: the fixture tree carried no `.github/workflows/`, so
GitHub saw a repository with no workflows and **no CI ran on the corrupted main at all**. Nothing
alerted. The public default branch of a repo maintained as a career artifact served a single
`f.txt` for **11 hours and 11 minutes** (05:55:02Z -> 17:06:22Z), and the only reason anyone
found out is that this session re-derived a state line instead of trusting it.

**Restored** 2026-08-24T17:06:22Z, `git push --force-with-lease=refs/heads/main:b70872c... origin
b6cc6cc:refs/heads/main`, rc 0, `+ b70872c...b6cc6cc ... (forced update)`. Verified at 17:06:57Z:
remote main `b6cc6cc`, 18 top-level entries, `actions/workflows total_count: 1`.

## 2. The diagnosis named the wrong file

`#46` and the prescribed fix both target `hooks/pre_push_gate_selftest.py` - "~6 call sites in a
1131-line file". That file is a real offender and it is **not** the one that did the damage.
`hooks/meta_audit_on_stop.py` accounts for the entire published incident by itself:

| line | code | artifact |
|---|---|---|
| 543 | `git init -q --bare <tmp>` | `core.bare = true` on the real repo - `git status` in the main clone became `fatal: this operation must be run in a work tree` |
| 555-556 | `config user.email t@t` / `user.name t` | `[user] email=t@t name=t` |
| 557 | writes `f.txt` = `"x\n"` | the one file published on main |
| 560 | `commit -q -m "local only"` | `b70872c` |
| 577 | `git push -q -u origin HEAD:refs/heads/main` | **the push to GitHub**, and `-u` wrote `[branch "feat/enforcing-verify"] merge = refs/heads/main` |
| 587-591 | `checkout -q -b feature` + commit | the stray `feature` branch |

Three more carry the same class: `pre_push_gate_selftest.py:1116` (`config core.hooksPath` ->
repointed the REAL `core.hooksPath` at `C:\...\Temp\tmp7dq12juu\myhooks`, a directory then
deleted, which **silently disabled every hook on the machine** and is why nothing blocked the
push); `fast_test_on_stop_selftest.py:895-902` (`commit -qm seed`, `worktree add` -> the `wt`
branch and a prunable worktree under the system temp dir); `check_review_freshness.py:318-330`
(the `fixture` commit). `hook_divergence_report.py:346-349` was caught by the new guard during
probe C, making **five** confirmed instances.

**A sixth artifact, and a correction to this document.** An independent adversarial review
(gate 9, 49 agents) found that an earlier revision of this paragraph claimed
`mutation_check.py:221`, `noregress_selftest.py:74`, `tests/false_alarm_corpus.py:98` and
`tests/test_integration.py:199` were "covered by the same fix". **That was false for three of the
four**, and it was false inside the document that adjudicates the CRITICAL as DONE - the exact
unverified-claim shape this project exists to catch, committed while writing the fix for it. Only
`false_alarm_corpus.py` was genuinely covered, via the `false-alarm-scorer` AUX row. The choke
point covers everything run_selftests SPAWNS; it does not reach an orchestrator that runs on its
own. Three more were therefore scrubbed explicitly, and they are separate entry points, not call
sites:

| orchestrator | reached by | fix |
|---|---|---|
| `tools/mutation_check.py` | its own CI job; `NOT_A_GATE` | `scrub_environ()` at the top of `main()` |
| `tests/test_integration.py` | its own CI job; the README's copy-paste line | `_scrubbed_environ()` feeding `git()` |
| `hooks/hook_health_check.py:236` | **ships to end users** as a SessionStart hook | `scrub_environ()` before the weekly sweep |

The last is the one that mattered most and the one nobody had looked at: it sweeps every hook's
selftest on a USER's machine, over a USER's repository.

A prescribed fix is a hypothesis. This one was re-executed and found to be aimed at the wrong
target and scoped an order of magnitude too small: applied literally it would have left
`git init --bare` and `git push -u origin HEAD:refs/heads/main` completely untouched, so the
next push would have republished `f.txt` and re-bared the repo.

## 3. The fix, and why it is at the choke point

`run_selftests.py` spawns every gate as its own subprocess. One scrub in the parent therefore
disinfects all 41 of them, and - decisively - it covers the call sites that pass **no `env=` at
all** and simply inherit, which is what every damaging line above did. Patching call sites is a
per-call-site obligation, and a per-call-site obligation is exactly what failed across 43 git
invocations in 15 files.

- `tools/git_isolation.py` (new, registered as the `git-isolation` AUX_GATE):
  `scrub_environ()` removes the seven redirect variables from the process environment;
  `fingerprint()` snapshots HEAD, symref, all refs, the repo config file, index CONTENT and the
  worktree list.
- `run_selftests.main()` scrubs before spawning anything, fingerprints this repo before the
  sweep, and re-checks **after every single gate**, re-baselining each time so the culprit is
  NAMED rather than every subsequent gate being reddened.

## 4. Probes - and the first two rounds were invalid

Standing check 6: a probe that has not been shown to FAIL is not a probe. Run against a
sacrificial clone with `origin` REMOVED and verified removed, because line 577 is a `git push -u
origin` and a clone that kept its origin would have pushed the fixture straight back into the
real repository.

| probe | expectation | result |
|---|---|---|
| A - offender direct, `GIT_DIR` set | victim MUST change | PASS: `config` and `worktrees` moved |
| B - via `run_selftests`, scrub active | victim MUST NOT change | PASS: fingerprint byte-identical |
| C - via `run_selftests`, scrub neutered | guard MUST fire and NAME the culprit | PASS: named `fast_test_on_stop`, `meta_audit_on_stop`, `hook-provenance-selftest` |

**Round 1 was invalid and said so loudly.** The probe built its victim with `git clone`, which
carries committed HEAD only - so probe B tested the PRE-FIX code and reported "still corrupting"
(a true statement about code that was not under test), and probe C died on a
`tools/git_isolation.py` that did not exist in the clone. Fixed by overlaying the working tree
onto the clone: the clone supplies history, the working tree supplies the code under test. A
check that looks in the wrong place returns a comforting answer - this one returned an alarming
one, which is the only reason it was caught.

**Round 2 found a defect in the guard itself.** Probe B still failed, on `index` alone. The
fingerprint hashed `.git/index` directly, and ordinary read-only git commands - which this
repo's own gates issue by the dozen - rewrite the index stat cache without changing one tracked
entry. The guard reddened a clean run. A guard that fires on correct work is disabled within a
day, which is strictly worse than no guard. Now compares `git ls-files -s` (mode, blob, stage,
path), which still catches the incident's 935-byte fixture index where every entry changed. The
regression is pinned by `fingerprint-ignores-stat-refresh`, which touches a tracked file, runs
`status`, and asserts the fingerprint held still.

`git_isolation --selftest` was mutation-probed: neutering the redirect roster on a scratch copy
turned it red (3 failures, rc 1) while check 1 - the reproduction of the `GIT_DIR` override -
still passed, which is what proves the reproduction is independent of the fix.

## 5. Refs deleted with this commit, recorded here first

They were `#46`'s evidence and are preserved as text rather than as live refs.

- `feature` = `5d5f3d7` ("fixture") <- `68b6b38` ("seed") <- `cfea2b4` ("on a branch that was
  never pushed") <- `8f63aec`
- `wt` = `68b6b38` ("seed")
- prunable worktree registration: `C:/Users/ammar/AppData/Local/Temp/tmpclp9mtd7/wt`
- `origin/main` and `origin/HEAD` tracking refs had followed the corrupted remote to `b70872c`;
  both now correctly track `b6cc6cc`.
- Published-then-removed fixture commits: `eae6080` ("seed"), `b70872c` ("local only").

## 5b. A SEVENTH artifact, found 17 hours later by running the suite CI could not reach

`C:\Users\ammar\Downloads\unbluff\.git\hooks\pre-push`, mtime **2026-08-24 01:55**, containing:

```sh
#!/bin/sh
# husky
npx --no-install husky-run pre-push
```

Byte-identical to the fixture written by `pre_push_gate_selftest.py:945`. This repo has no
`package.json` and no `.husky`, so it is unambiguously incident residue - and it survived the
reflog sweep, the ref cleanup, the fingerprint, and this document's own section 5, all of which
were written believing the cleanup complete.

It was found because `tests/test_integration.py` reported **33/34**, `J2 global stale shim ALLOWS
the push` failing with rc 1. The shim fails open on the missing gate exactly as gate 8 claims,
then delegates to the repo's own hook via `--git-common-dir` - and found this one, which exits
nonzero because `npx husky-run` is not installed. So the failure was residue, not a defect:
gate 8's claim stands, and `34/34` was restored by deleting the file, with a backup taken first.

Two lessons, both already this repo's own rules:

* **`core.hooksPath` made it INERT FOR GIT, which is why nothing noticed.** Every guard that asks
  git "what runs on push?" got the hijacked answer. Only code that resolves the hooks directory
  structurally - as the dispatcher does - ever saw it.
* **The integration suite is the only thing that looked.** It is not part of `run_selftests`, and
  in CI it had aborted at `A1 install` before reaching `J2`. A tier that cannot run is a tier that
  found nothing, and its silence read as agreement for seventeen hours.

`fingerprint()` gained a `hooks=` term in response, pinned by `fingerprint-sees-hooks-dir` and
mutation-verified: **7 of 7 terms now go red when deleted**, up from 3 of 6 when the review filed
M7.

## 6. Still open at the time of writing

`git config` writes to `C:\Users\ammar\Downloads\unbluff\.git\config` are blocked by this
session's tool-permission classifier, so **four config repairs are NOT yet applied**:
`core.bare=false`, unset `core.hooksPath`, unset `user.name`/`user.email`, remove
`[branch "feat/enforcing-verify"]`. Until `core.hooksPath` is restored the machine's hooks stay
disabled - which is currently the only reason a push cannot re-trigger the incident, and is
therefore a safety net that must be removed only AFTER this fix lands. The corrupted config was
backed up before any change was attempted.
