# v1.3.1 plan - adversarial review findings

Source: 4-lens adversarial review, run `wf_b5ea865a-a33`, 2026-07-29. 43 agents, 39 findings, **34 confirmed**, 5 refuted.
Lenses: silent-failure, cross-platform, test-quality, adversarial-input. Every finding below survived a refuter instructed to default to `refuted=true`.

**Nothing here is optional.** Materiality sets the ORDER; every item is SCHEDULED to be built. Each is a real row in this file, not a pointer to a future one.

| Severity | Count |
|---|---|
| CRITICAL | 1 |
| HIGH | 20 |
| MEDIUM | 11 |
| LOW | 2 |

Confirmed findings by file: `hooks/pre_push_gate.py` 17, `hooks/duplicate_registration_check.py` 7, `hooks/close_skills_guard.py` 6, `hooks/hook_health_check.py` 1, `run_selftests.py` 1, `hooks/usage_snip_prompt.py` 1, `tests/test_integration.py` 1

## Working rules for the fix pass

1. **Regression test first.** Write the failing test, watch it fail, then fix. A fix without a test that fails beforehand is not verified - three tests written today asserted things the implementation could not violate.
2. **Mutation-test every fix.** Revert the fix on a scratch copy and confirm the suite goes red. If it stays green the test is decorative.
3. **CI is the only Unix check.** This machine is Windows; `os.chmod` exec bits are a no-op and path-case behaviour differs. Push and read the CI result before claiming a cross-platform fix works.
4. **Generalise, then check for the twin.** The roster bug below exists because one of two identical rosters was fixed. After each fix, grep for the same pattern elsewhere.

## P1 - `pre_push_gate`: active risk on this machine today

Installed globally via `core.hooksPath`, so every one of these is live in every repo right now. Two can make `git push` hang or refuse; one silently disables the gate entirely. Fix this group first.

### 1. [CRITICAL] A non-ASCII character anywhere in a repo's path silently disables the gate for that repo (Windows) or crashes it (POSIX C locale)

- **Where:** `hooks/pre_push_gate.py`:53
- **Lens:** cross-platform
- **What breaks:** Windows user with profile `C:\Users\José`. They run `pre_push_gate.py --install-global`, which reports every repo on the machine is now gated. In `C:\Users\José\dev\api`, tests fail. `git push` -> _repo_root returns `C:/Users/JosÃ©/dev/api`, resolve_command finds nothing under it, and the hook prints "'api' has no test command - nothing to verify, allowing push" and exits 0. Failing code ships; the gate has never run once since install and says so in language that reads like a healthy skip.
- **Fix:** Pass an explicit codec to every subprocess that returns paths: `encoding="utf-8", errors="surrogateescape"` on lines 53-54, 74, and 213 (surrogateescape round-trips back through os.* calls on POSIX; "replace" would corrupt the path). Widen the except clauses to include ValueError so a decode failure cannot escape as a traceback. Separately, add a positive assertion in _repo_root that the decoded root actually exists - `if not os.path.isdir(root): return None` - so a mis-decoded path becomes the honest "cannot determine the repo" case instead of a confident "this repo has no tests".

### 2. [HIGH] pre_push_gate claims "verified Ns ago, no source touched since" for repos whose source is outside SRC_EXT, and on any git failure or timeout, without re-running anything

- **Where:** `hooks/pre_push_gate.py`:80
- **Lens:** silent-failure
- **What breaks:** A Terraform or shell-tooling repo: tests pass, the gate records it, you then rewrite deploy.sh and schema.sql and break them, and push. The gate prints "verified 1s ago, no source touched since - allowing push" and never re-runs the suite - identical output to a genuine verified push. Reproduced above.
- **Fix:** Three separate changes, because they are three separate bugs sharing one sink: (1) check `r.returncode` in `newest_source_mtime` and return a distinct sentinel (e.g. `(None, None)`) for "could not determine", and have `gate()` treat that as UNKNOWN - run the tests, or at minimum say "could not enumerate sources - re-running to be safe"; (2) do the same for the OSError/timeout branch; (3) either widen SRC_EXT, or - better for a push-time gate - fall back to every non-ignored tracked file when no SRC_EXT path is found, and make the message name what it checked (`no .py/.js/... source touched since`) rather than the unqualified "no source touched since".

### 3. [HIGH] pre_push_gate never checks git's exit code: any git failure reads as "no source files" and the gate allows the push

- **Where:** `hooks/pre_push_gate.py`:77
- **Lens:** cross-platform
- **What breaks:** Repo has a recorded pass from any point in the past (fast_test_on_stop wrote one, or an earlier gate run did). A crashed editor leaves .git/index.lock behind. Developer edits source, tests now fail, runs `git push`. `git ls-files` exits 128; newest_source_mtime returns (0.0, None); passed_at > 0.0 so the gate short-circuits and prints "verified <N>s ago, no source touched since - allowing push." Broken code reaches the remote and the hook reported success.
- **Fix:** After the try/except in newest_source_mtime, fail CLOSED on a git error instead of returning the "nothing here" sentinel: `if r.returncode != 0: return time.time(), "<git ls-files failed>"`. Returning `now` guarantees `passed_at > newest` is False, so the gate runs the tests rather than trusting a stale pass. Equivalently, return a third state (e.g. None) that gate() treats as "cannot determine -> must run". Whichever shape, the invariant is that an unanswerable question must never resolve to the same value as "answered, nothing changed".

### 4. [HIGH] Source files whose names git C-quotes are invisible to the pre-push gate, so it allows an unverified push

- **Where:** `hooks/pre_push_gate.py`:79
- **Lens:** cross-platform
- **What breaks:** A repo with i18n fixtures or non-English source filenames (`données.py`, `模块.py`). Developer edits one of them, breaking the build. `git push` -> newest_source_mtime skips the quoted entry, sees only older ASCII files, finds the recorded pass newer than all of them, prints "verified 12s ago, no source touched since - allowing push" and exits 0. The broken file was never compiled or tested and the hook stated the opposite.
- **Fix:** Ask git not to quote in the first place: add `-z` to the ls-files invocation and split on `\0` (`r.stdout.split("\0")`), which disables C-quoting entirely and also makes newline-in-filename safe. Pair it with `encoding="utf-8", errors="surrogateescape"` so the bytes round-trip back into os.path calls. Then make the swallow honest: an OSError on a path git just listed should not silently mean "deleted"; count those and, if any remain, treat the scan as incomplete and run the tests rather than trusting the fast path. A file the gate cannot stat is a reason to verify, not a reason to skip.

### 5. [HIGH] The global dispatcher silently drops every repo-local git hook inside a linked worktree, and exits 0

- **Where:** `hooks/pre_push_gate.py`:202
- **Lens:** cross-platform
- **What breaks:** Repo uses a .git/hooks/pre-commit that runs a secret scanner. Developer creates a linked worktree (`git worktree add ../feat`) to run a second agent session. Inside it, `git rev-parse --git-dir` resolves to .git/worktrees/feat, the dispatcher finds no hook at .git/worktrees/feat/hooks/pre-commit, and exits 0 without delegating. Every commit made from that worktree bypasses the secret scanner, silently, for as long as the worktree exists.
- **Fix (as planned - SUPERSEDED, do not use):** ~~`hooksdir=`git rev-parse --git-path hooks`` and `local_hook="$hooksdir/$hook"`, keeping the `grep -q pre_push_gate.py` self-check for the recursive case.~~
- **CORRECTION 2026-07-30 (measured, not reasoned):** `--git-path hooks` is the WRONG primitive here and adopting it would have been a regression far worse than the bug. When `core.hooksPath` is set - which is precisely the condition under which this dispatcher runs at all - git answers `--git-path hooks` with the hooksPath itself. Measured on this machine in both a plain repo and a linked worktree: it returned `C:/Users/ammar/.claude/githooks` in **both** cases, never the repo's own hooks dir. So the planned fix would have made `grep -q pre_push_gate.py` match every time and disabled repo-local delegation in **every repo on the machine**, not just worktrees. The plan noted that hooksPath behaviour and drew the wrong conclusion from it - it treated the self-check as sufficient rather than seeing that the lookup itself never reaches the target.
- **Fix (applied):** `gitdir=`git rev-parse --git-common-dir`` and `local_hook="$gitdir/hooks/$hook"`. `--git-common-dir` is unaffected by `core.hooksPath`, returns `.git` in a normal repo and the HOST repo's `.git` from inside a linked worktree, and is submodule-correct. `install()` uses the same primitive via `_common_git_dir()`. Pinned by selftest case 17 (a real `git worktree add`, asserting the repo-local hook actually executed) and mutation `#5`, which reverts the shim to `--git-dir` and must go red.
- **Lesson:** the plan prescribed a fix it had not executed. Two of the three review lenses would have approved it on reading. Only running `git rev-parse --git-path hooks` under the live config exposed it - the same class of error as the tests that "asserted things the implementation could not violate".

### 6. [HIGH] pre_push_gate --install crashes in a linked worktree or submodule, and would install where git never looks

- **Where:** `hooks/pre_push_gate.py`:157
- **Lens:** cross-platform
- **What breaks:** A developer running parallel agent sessions in linked worktrees follows the README's per-repo instruction and runs `pre_push_gate.py --install .` from inside one. They get a Python traceback (FileNotFoundError on Windows, NotADirectoryError on Linux) instead of an actionable message, and the worktree stays ungated. In the variant where the write succeeds, they get "installed .../.git/hooks/pre-push" for a file git will never run.
- **Fix (applied):** Resolve the hooks directory through git rather than assuming the layout - but via `--git-common-dir`, **not** `--git-path hooks`; see the correction under finding 5, which applies identically here (under a live `core.hooksPath`, `--git-path hooks` would have made `--install` write into the global dispatcher directory and clobber the dispatchers themselves). `_common_git_dir()` joins the returned path against the repo root when it is relative. Correct for plain repos, linked worktrees and submodules alike. A layout that cannot be resolved produces the refusal "cannot resolve a git directory for &lt;target&gt;; use --install-global" instead of a traceback or a false success. Pinned by selftest case 18 (installs into a real linked worktree, then asserts the file landed where git actually looks) and mutation `#6`.

### 7. [HIGH] pre_push_gate's GLOBAL_SHIM pre-push branch is untested - deleting the only line that runs the gate leaves every test green and silently ungates every repo on the machine

- **Where:** `hooks/pre_push_gate.py`:199
- **Lens:** test-quality
- **What breaks:** A one-character edit to GLOBAL_SHIM (or a shell quoting change that makes the `if` never match) disables the pre-push gate in every repo on the machine at once. Nothing turns red; `git push` succeeds silently; the user believes untested source cannot reach the remote. Because core.hooksPath is global, the blast radius is every repo, not one.
- **Fix:** Extend case 8b: render a SECOND dispatcher under the name `pre-push` into the same temp dir, point it at this script, run it in the temp repo (which already has a failing `.claude/pre-push.cmd` from case 3) via `sh`, and assert the exit code is NONZERO and stderr contains '[pre-push] BLOCKED'. Then flip pre-push.cmd to a passing command and assert exit 0. That single addition covers the branch, the `< /dev/null` redirect, and the `|| exit $?` propagation.

### 8. [HIGH] pre_push_gate's selftest asserts exit codes only and never a single message - a gate that fires with no explanation, or allows a push with no warning, passes

- **Where:** `hooks/pre_push_gate.py`:249
- **Lens:** test-quality
- **What breaks:** A refactor drops or misroutes a stderr write. Pushes are then either blocked with no diagnosis (user reaches for --no-verify and stops trusting the gate) or, worse, allowed with no notice that nothing was verified - the gate reports success while guarding nothing.
- **Fix:** Capture stderr in the selftest (contextlib.redirect_stderr around each gate() call) and assert on both halves of every outcome: no-command -> (0, 'no test command'); failing -> (1, 'BLOCKED'); passing -> (0, 'tests passed'); fast path -> (0, 'no source touched since'); timeout -> (0, 'NOT verified'). The timeout branch (lines 133-136) currently has no test of any kind.

### 9. [HIGH] pre_push_gate has no top-level exception handler: a corrupt state file crashes it with a traceback and exit 1, so git REFUSES the push

- **Where:** `hooks/pre_push_gate.py`:98
- **Lens:** adversarial-input
- **What breaks:** Anything writes a non-object or a non-numeric `ts` into ~/.claude/hooks/state/fasttest-<hash>.json — a partial write, an unrelated tool sharing $UNBLUFF_STATE_DIR, a hand-edit. From then on EVERY `git push` in that repo dies with a Python traceback and exit 1. The user sees a stack trace from a tool they may not know is installed, with no [pre-push] prefix and no --no-verify hint.
- **Fix:** Validate the loaded state: `if not isinstance(st, dict): return 0.0`, and wrap the float coercion in try/except (TypeError, ValueError). Independently, give main() the same catch-all every other hook has — `except Exception: return 0` — so the gate can only ever block on a genuine non-zero test run, matching README:248 'Any unexpected error exits 0'.

### 10. [HIGH] pre_push_gate's timeout does not bound anything: a test that leaves a grandchild on the captured pipe hangs `git push` forever

- **Where:** `hooks/pre_push_gate.py`:131
- **Lens:** adversarial-input
- **What breaks:** A project's test command leaves anything alive on the pipe — a vitest/jest watcher, pytest-xdist workers, a gradle daemon, a dev server started by an integration test, an npm child that outlives its parent. `git push` blocks with no output and no timeout. The user has no signal that a hook is responsible; Ctrl-C is the only exit, and --no-verify only helps if they guess the cause.
- **Fix:** Use Popen + `communicate(timeout=...)`, and on timeout kill the whole process tree (Windows: `taskkill /T /F /PID`; POSIX: `start_new_session=True` + `os.killpg`), then drain with a second bounded communicate() in try/except. Guard the drain itself so a stuck pipe still lands on the ALLOW-with-warning path rather than hanging.

### 11. [HIGH] pre_push_gate ignores git's exit code, so when `git ls-files` fails it reports 'verified, no source touched since' and lets unverified failing code through

- **Where:** `hooks/pre_push_gate.py`:73
- **Lens:** adversarial-input
- **What breaks:** A corrupt/locked index, a concurrent git process, an unreadable working tree, or any git version/config error makes ls-files non-zero. The gate silently allows the push and tells the user the tree was verified. Failing, unverified source reaches the remote.
- **Fix:** Return a sentinel when git fails (`if r.returncode != 0: return float('inf'), '<git ls-files failed>'`) so the fast path cannot fire, and make `gate()` fall through to actually running the tests. If git is unusable at all, say so on stderr rather than claiming verification.

### 12. [HIGH] pre_push_gate's source-change detection ignores whole classes of source, then claims 'no source touched since'

- **Where:** `hooks/pre_push_gate.py`:80
- **Lens:** adversarial-input
- **What breaks:** A developer edits only a migration and a deploy script after the last green run. The gate short-circuits, announces verification, and the broken change is pushed.
- **Fix:** Two independent fixes. (1) Widen SRC_EXT (.cjs .mjs .sh .bash .zsh .ps1 .sql .proto .scala .dart .ex .exs .pl .lua .r .m .mm) and add extensionless build files (Makefile, Dockerfile, justfile) plus dependency manifests. (2) More robustly, drop the allowlist in the gate and use the newest mtime over ALL non-ignored tracked files, minus an explicit ignore list (docs, images) — an over-broad gate costs one extra test run, an under-broad one costs an unverified push. At minimum, soften the message to name what it checked.

## P2 - `close_skills_guard`: the close ritual is currently unguarded

An image-first prompt is not recognised as a user message, so the detection window never resets and the guard passes silently. Verified against real transcripts, including this project's own. `usage_snip_prompt` asks for a screenshot and this hook goes blind on the turn it arrives - the two v1.3.0 hooks interlock badly.

### 13. [HIGH] close_skills_guard: a human prompt that leads with a pasted image is not counted as a user message, so the detection window never resets and the guard silently passes

- **Where:** `hooks/close_skills_guard.py`:81
- **Lens:** silent-failure
- **What breaks:** Claude declares a premature close and runs all four audit skills. The user pastes a usage-limits screenshot with "continue" (the flow usage_snip_prompt.py asks for). Claude builds more, reaches the real end, writes docs/NEXT_SESSION_PROMPT.md. The guard exits 0 in silence - the exact temporal gap it was written to close. Reproduced above; the control with a plain-text "continue" fires correctly.
- **Fix:** Stop sniffing content shape. Use the metadata the harness already writes: treat an entry as a genuine prompt iff `(entry.get("origin") or {}).get("kind") == "human"` and not `isMeta`/`sourceToolUseID`; keep the current shape test only as a fallback for entries that carry no `origin`. If the shape test must stay, scan for ANY `type == "text"` block rather than only `content[0]`, and exclude the `[Request interrupted by user...]` synthetic. Add selftest cases for (a) image-then-text, (b) the interrupt marker, driven off the fixtures above.

### 14. [HIGH] MUTATION HOLE: close_skills_guard can be made to fire with an empty stderr and the entire gate stays GREEN - main() is never exercised by any test

- **Where:** `hooks/close_skills_guard.py`:145
- **Lens:** silent-failure
- **What breaks:** Any future edit that breaks the stderr write - a refactor of build_message, a stray `if`, a message that renders empty - ships green. The hook then exits 2 with no text: Claude Code wakes the model with nothing to act on, the user sees no reason, and the close proceeds. Identical in observable behaviour to the already-fixed 'fired but said nothing' defect.
- **Fix:** Add a main()-level case to `selftest()` mirroring duplicate_registration_check's: point sys.stdin at a StringIO payload, capture sys.stderr, call `main()`, and assert `rc == 2` AND that all four skill names appear in the captured stderr. Separately, extend tests/test_integration.py to iterate EVERY command in each installed hook group instead of indexing `hooks[0]` - that alone would also cover usage_snip_prompt end-to-end.

### 15. [HIGH] close_skills_guard.main() is exercised by neither its selftest nor the integration suite; deleting its message line keeps every gate green

- **Where:** `hooks/close_skills_guard.py`:146
- **Lens:** cross-platform
- **What breaks:** A future refactor of main() - reordering the stderr write, wrapping it in a condition, switching to a logger, or moving the message into a branch that the code path no longer reaches - lands. run_selftests.py prints SELFTEST OK for 18 selftests, test_integration.py passes 26 scenarios, and CI is green on all six platform/version combinations. In real use the guard fires at the session close with an empty message: Claude sees a bare non-zero exit with no instruction, cannot learn which of the four audit skills is missing, and the close ritual is blocked with no way to satisfy it.
- **Fix:** Add a selftest case that drives main() end to end for both outcomes, mirroring the pattern duplicate_registration_check already uses at its lines 176-197: feed a JSON payload through a patched sys.stdin, capture sys.stderr, and assert (a) rc == 2 AND the captured stderr is non-empty and names every missing skill, and (b) rc == 0 with empty stderr on the non-target-file path. Then close the wiring gap in tests/test_integration.py: iterate ALL commands in each installed hook group rather than indexing [0]/[1], so close_skills_guard, usage_snip_prompt, and pre_push_gate each get at least one real fire-and-assert scenario. The general invariant worth encoding once: for every hook that can exit non-zero, assert the message is non-empty at the same moment you assert the exit code.

### 16. [HIGH] close_skills_guard's entire main() is untested - the guard can be fully disarmed with all 44 gate assertions green

- **Where:** `hooks/close_skills_guard.py`:136
- **Lens:** test-quality
- **What breaks:** Any future edit to main() - a refactor that swallows the return code, a stray early return, a logging change that drops the stderr write - ships green. The hook then runs on every Edit/Write/MultiEdit, costs a process spawn, and reports nothing while Claude closes sessions without the four audit skills. That is the precise 'reports OK while guarding nothing' failure the suite exists to prevent.
- **Fix:** Add a subprocess-level selftest block that runs `[sys.executable, __file__]` with each scenario's payload on stdin and asserts the (returncode, stderr) PAIR - not just one of them. At minimum: fire case -> (2, message containing all four skill names); pass case -> (0, ""); malformed stdin -> (0, ""); non-dict stdin (e.g. `[]`) -> (0, ""). Then add an integration scenario that pulls `s["hooks"]["PostToolUse"][<unbluff group>]["hooks"][1]["command"]` and fires it with a temp transcript, asserting rc==2 and '[close_skills_guard]' in stderr - mirroring what C2/C3 already do for duplicate_registration_check.

### 17. [HIGH] close_skills_guard still counts harness-injected role=user entries as the user — wrongly BLOCKS the close after all four skills ran

- **Where:** `hooks/close_skills_guard.py`:72
- **Lens:** adversarial-input
- **What breaks:** Claude invokes all four audit skills, a background Stop-hook task-notification (or /compact, or an interrupt) is injected, Claude then writes docs/NEXT_SESSION_PROMPT.md. The hook exits 2 and tells Claude all four skills are missing. Claude re-runs four expensive audit skills; if another notification arrives during that stretch, it loops.
- **Fix:** Do not treat 'role == user' + plain text as sufficient. Reject an entry when isMeta/sourceToolUseID is set OR the first text block begins with a harness wrapper tag (`<command-name>`, `<command-message>`, `<local-command-`, `<system-reminder>`, `<task-notification>`, `<bash-input>`), or with `[Request interrupted`, `Caveat:`, `This session is being continued`. The real transcripts also carry `promptSource` on genuine prompts — keying on that is stronger than a marker denylist. Add one selftest per channel using the recorded shapes so the next injection type fails loudly.

## P3 - the health line is asserting something false

`hook_health_check._LOCAL_HOOKS` is a hardcoded roster excluding all four v1.3.0 hooks. `run_selftests.py` had the identical bug and was converted to detection on 2026-07-29; the twin roster in the on-machine gate was left behind. Breaking a hook outright still prints `weekly selftests 10/10 OK` - on the line read at every SessionStart.

### 18. [HIGH] hook_health_check's weekly selftest sweep uses a hardcoded roster that excludes all four v1.3.0 hooks - it prints "weekly selftests 10/10 OK" with a broken hook on disk

- **Where:** `hooks/hook_health_check.py`:29
- **Lens:** silent-failure
- **What breaks:** A `git pull` lands a bad `close_skills_guard.py` (or Python is upgraded and one of the four stops importing). Every subsequent SessionStart prints `[hook-health] OK - 30 hook commands verified, weekly selftests 10/10 OK`. The close-audit tripwire is dead for every session from then on and the health line asserts the opposite. Reproduced above.
- **Fix:** Replace the hardcoded `_LOCAL_HOOKS` with the same detection `run_selftests.py` now uses: glob `hooks/*.py` and select files whose text matches `["']--selftest["']\s+in\s+(?:sys\.)?argv`, keeping the current tuple only as a FLOOR (a listed name that loses its dispatch is an error, not a skip). Also make the summary line name what was NOT sampled (e.g. `weekly selftests 14/14 OK` vs `... 10/14 - 4 hooks have no selftest`), so a shrinking denominator is visible rather than silent. Pin it with a test that adds a new self-testable hook file and asserts the sweep count rises.

### 19. [MEDIUM] run_selftests' SELFTESTABLE floor omits all four v1.3.0 hooks, so losing a selftest dispatch is a silent skip plus an all-green report

- **Where:** `run_selftests.py`:26
- **Lens:** test-quality
- **What breaks:** A refactor that changes the dispatch idiom (e.g. moving to argparse, or `if args.selftest:`) silently removes a hook from the gate. CI stays green, the count quietly drops from 18 to 17, and the hook ships with zero verification - the exact regression the floor was added to prevent, now reoccurring for the four newest hooks.
- **Fix:** Add "duplicate_registration_check", "pre_push_gate", "close_skills_guard", "usage_snip_prompt" to SELFTESTABLE. Better: derive the floor mechanically - assert `detected_count >= len(glob(hooks/*.py)) - len(KNOWN_NO_SELFTEST)` with an explicit opt-out list, so adding a hook without a selftest is the thing that turns red, rather than adding a hook and forgetting the roster.

## P4 - `duplicate_registration_check` misses the commonest duplicate

Registrations collapse into a set of directories, so the same path registered twice reports clean. A space anywhere in a path disables both headline detections.

### 20. [HIGH] duplicate_registration_check cannot see the same script path registered twice - the collapse happens in a set, so the commonest double-fire reports as healthy

- **Where:** `hooks/duplicate_registration_check.py`:105
- **Lens:** silent-failure
- **What breaks:** A user runs install.py and also keeps a hand-wired copy of the same command from examples/settings.json in a second group with the id removed or renamed (install.py's `_strip_ours` only removes groups whose `id` starts with `unbluff:`). rate_prompt then fires twice on every prompt, and duplicate_registration_check prints nothing at SessionStart - a clean bill of health. Reproduced above.
- **Fix:** Count registrations, not distinct directories: key on the basename and accumulate a LIST of (directory, source-group) entries, reporting whenever `len(entries) >= 2` regardless of whether the directories match; keep the digest comparison to classify SAME FILE vs DIFFERENT PROGRAMS. Normalise directories with `os.path.normcase(os.path.realpath(...))` first so './' and case variants merge into a true SAME FILE report. Add the two silent cases above as selftest fixtures.

### 21. [HIGH] A space anywhere in a hook's path silently disables duplicate_registration_check's two headline detections

- **Where:** `hooks/duplicate_registration_check.py`:43
- **Lens:** cross-platform
- **What breaks:** User's Windows profile is `C:\Users\John Doe`. They install unbluff twice (once globally, once from a project clone) so rate_prompt.py is wired from two roots and fires twice per prompt - the exact bug this hook was written to catch. At every SessionStart duplicate_registration_check extracts `Doe\.claude\hooks\rate_prompt.py` from both, cannot open either to digest it, cannot expand any dispatcher, and prints either nothing or a misclassified "DIFFERENT PROGRAMS" line citing `Doe/.claude/hooks` with `[sha missing]`. The duplicate registration goes unfixed indefinitely while the check reports clean.
- **Fix:** Stop regex-scraping paths out of a joined command string. `_iter_commands` already has the structured data: for `args`, treat each element as a whole path (no regex at all); for `command`, tokenize with `shlex.split(cmd, posix=False)` and keep tokens ending in `.py`. Then normalize before keying: `os.path.normcase(os.path.abspath(os.path.expanduser(p)))` so `~`-relative, mixed-case (Windows), and relative spellings of one file collapse correctly and one file registered under two spellings is not reported as two programs. Finally, make the silence provable: if `_digest()` returns None for a path the audit is reasoning about, say so loudly rather than folding it into the "different programs" bucket - a path the checker cannot even open is a broken check, not a finding.

### 22. [HIGH] duplicate_registration_check goes completely silent when any hook path contains a space - no fixture anywhere uses one

- **Where:** `hooks/duplicate_registration_check.py`:43
- **Lens:** test-quality
- **What breaks:** A user clones unbluff into a path with a space (extremely common on Windows and on OneDrive-synced trees - and the author develops on Windows). SessionStart runs, the check prints nothing, and the user reads that as 'no duplicate registrations' while a hook is in fact wired twice and the dispatcher fan-out detection - the feature the hook was written for - is entirely dead.
- **Fix:** Stop regex-scraping the command string. Use `shlex.split(command, posix=False)` (or a Windows-aware splitter) to get real argv tokens, then keep tokens ending in .py; fall back to the regex only if splitting fails. Add selftest fixtures whose temp roots contain a space (`os.path.join(td, "My Repos", "hooks")`) covering all three cases proven above, and make `_digest` returning None a hard 'cannot classify' state rather than silently voting for SAME FILE.

### 23. [MEDIUM] duplicate_registration_check cannot see the same script registered twice from the SAME directory — the commonest duplicate

- **Where:** `hooks/duplicate_registration_check.py`:104
- **Lens:** adversarial-input
- **What breaks:** User hand-adds the README snippet for one hook, later runs install.py. Both entries survive. The hook fires twice per event; whichever copy runs first consumes the once-per-session marker. duplicate_registration_check exits 0 with no output, and hook_health_check reports all commands resolve.
- **Fix:** Count REGISTRATIONS, not distinct roots: keep a list (or Counter) of (root, event) occurrences and report when the total count for a basename exceeds 1, labelling same-path repeats 'SAME PATH registered N times'. Add a selftest for the same-root case — the current selftest only exercises two distinct roots, so this gap is untested by construction.

### 24. [MEDIUM] duplicate_registration_check reads only ~/.claude/settings.json, so user+project double-wiring is invisible

- **Where:** `hooks/duplicate_registration_check.py`:42
- **Lens:** adversarial-input
- **What breaks:** A repo checks in .claude/settings.json wiring plan_defer_guard from the project clone while ~/.claude/settings.json wires it from the global clone. Both fire on every edit; two variant programs share a state key. The SessionStart check prints nothing and the user reads that as healthy.
- **Fix:** Iterate over all settings layers that Claude Code merges — ~/.claude/settings.json, ~/.claude/settings.local.json, <project>/.claude/settings.json, <project>/.claude/settings.local.json (project root from the SessionStart payload's cwd) — and tag each finding with which file it came from. Report per-file provenance so 'two roots' and 'two layers' are distinguishable.

### 25. [MEDIUM] duplicate_registration_check asserts a same/different verdict it did not compute when a file's digest is unavailable

- **Where:** `hooks/duplicate_registration_check.py`:124
- **Lens:** adversarial-input
- **What breaks:** A hook file is unreadable in one of the two roots. The user sees 'SAME FILE twice (redundant)', treats it as cosmetic, and leaves two divergent programs wired — with a [sha missing] marker as the only, easily-missed clue.
- **Fix:** Add a third verdict for the undetermined case: if any digest is None, emit 'CANNOT COMPARE - <path> unreadable; treat as a possible variant conflict' rather than picking a side. Cover both sub-cases in the selftest, which today only exercises files that exist.

### 26. [LOW] duplicate_registration_check reads only ~/.claude/settings.json, so a hook wired at both user and project scope is invisible and the check prints a clean bill

- **Where:** `hooks/duplicate_registration_check.py`:42
- **Lens:** silent-failure
- **What breaks:** A project checks unbluff's PostToolUse group into its own .claude/settings.json for teammates, while the developer also has it installed at user scope. Both fire on every edit; the SessionStart duplicate check stays silent because it never opened the project file, and hook_health_check separately reports OK.
- **Fix:** Resolve the settings chain the way the harness does: audit `~/.claude/settings.json` plus, using the `cwd` field from the SessionStart payload the hook already receives on stdin, `<cwd>/.claude/settings.json` and `<cwd>/.claude/settings.local.json`, tagging each finding with the file it came from. If reading the payload is undesirable, at minimum print the scope that was checked so a clean result is not mistaken for a machine-wide all-clear.

## P5 - test-quality and remaining items

Mostly assertions that cannot fail, and entry points no test exercises. Lower blast radius, same class as the defects already found by mutation today.

### 27. [MEDIUM] pre_push_gate --install-global omits 7 documented client-side git hooks from CLIENT_HOOKS, silently killing repo-local hooks of those names - the exact breakage its own comment says the list prevents

- **Where:** `hooks/pre_push_gate.py`:185
- **Lens:** silent-failure
- **What breaks:** A user runs `--install-global` to gate every repo. A project that relies on `.git/hooks/pre-merge-commit` (or reference-transaction, or a git-p4 hook) silently stops running it from that moment on - no warning at install time, no error at merge time, and the install message actively reassures: "each repo's OWN .git/hooks/<name> still runs after the gate." Mechanism reproduced above with pre-commit as the isolated variable.
- **Fix:** Derive the list instead of hardcoding it: at install time enumerate the `*.sample` files in git's template dir (`git --exec-path`/templates/hooks) union the current tuple, or simply add the 7 missing names. Then add a selftest that asserts every hook name found in git's own template dir has a dispatcher written - so the next git release adding a hook turns the build red instead of silently narrowing coverage. Additionally, at `--install-global` time, scan existing repos' `.git/hooks` for any name with no dispatcher and refuse or warn loudly.

### 28. [MEDIUM] On Windows pre_push_gate and fast_test_on_stop key their shared state file differently, so the "one source of truth" claim is false

- **Where:** `hooks/pre_push_gate.py`:389
- **Lens:** cross-platform
- **What breaks:** On Windows, fast_test_on_stop finishes a 90-second passing run at turn end and records it under the backslash key. The developer immediately runs `git push` with nothing touched in between. pre_push_gate hashes the forward-slash root, finds no state file, reports "no passing run on record", and re-runs the full suite - the fast path the docstring promises never triggers. Conversely a pass recorded by the gate never suppresses fast_test_on_stop's next run.
- **Fix:** Canonicalize inside `_state_path` so every caller lands on the same key regardless of spelling: `key = os.path.normcase(os.path.abspath(os.path.realpath(cwd)))` before hashing (normcase already lowercases on Windows and converts separators; realpath additionally collapses symlinked and 8.3-short-name roots). Fixing it in the one shared helper covers both callers and any future one. Add a selftest asserting `_state_path(r'C:\a\b') == _state_path('C:/a/b')`, which fails today and would have caught this at authoring time.

### 29. [MEDIUM] usage_snip_prompt's main() is exercised only on the malformed-stdin branch; the valid-JSON path - 100% of real invocations - is uncovered

- **Where:** `hooks/usage_snip_prompt.py`:59
- **Lens:** test-quality
- **What breaks:** The budget instruction is silently never injected. Nothing errors, nothing turns red, and the hook that exists specifically to stop a forgettable-instruction failure mode fails in exactly that forgettable way - visible only by noticing the absence of text that was never guaranteed to appear.
- **Fix:** Drive the selftest through the SUCCESS branch too: `sys.stdin = io.StringIO(json.dumps({"session_id":"x","hook_event_name":"SessionStart","source":"startup"}))` and assert rc==0 AND the notice is on stdout. Keep the malformed case as a second assertion. Add an integration scenario firing SessionStart hooks[2] and asserting '[usage-budget]' in stdout with rc==0.

### 30. [MEDIUM] install()'s chmod on the per-repo pre-push hook is unasserted - the exact class of the already-found execute-bit defect, now in production code instead of a fixture

- **Where:** `hooks/pre_push_gate.py`:174
- **Lens:** test-quality
- **What breaks:** On Linux/macOS git refuses to execute a non-executable hook: it prints a warning at most and proceeds with the push. The gate is silently absent in every repo installed after such a regression, and the author - on Windows, where mode bits are ignored - would see nothing wrong locally and nothing red in CI.
- **Fix:** In case 8, after `install(r)`, assert `os.stat(dest).st_mode & stat.S_IXUSR` on platforms where it is meaningful (`if os.name != "nt"`), or unconditionally assert the chmod was requested by asserting the mode contains the execute bits when `os.name != "nt"`. Add an equivalent assertion for install_global() by pointing GLOBAL_HOOKS_DIR at a temp dir in the test.

### 31. [MEDIUM] The completeness-audit skill - the one added in v1.3.0 for close_skills_guard - is the only skill whose install and removal are asserted nowhere

- **Where:** `tests/test_integration.py`:59
- **Lens:** test-quality
- **What breaks:** install.py ships a hook that hard-requires four skills by name (close_skills_guard.py:30) while the user receives three. close_skills_guard then permanently reports a missing skill the user can never satisfy, with no error anywhere explaining why - the exact bug tools/check_skill_deps.py's docstring says was found on 2026-07-29 'after the hook had already been published'. The static gate cannot see it because SKILL_NAMES would still list all four.
- **Fix:** Make A5-A7 and G5 loop over the four names in install.SKILL_NAMES rather than hardcoding a subset, so any skill added to the tuple is automatically asserted installed and removed. That also makes the assertion self-maintaining for the next skill.

### 32. [MEDIUM] pre_push_gate's selftest reports OK having executed zero assertions when git is unavailable, and skips its only dispatcher test when sh is unavailable

- **Where:** `hooks/pre_push_gate.py`:265
- **Lens:** test-quality
- **What breaks:** In any container or CI image lacking git or sh, the pre-push gate's entire selftest evaporates while the suite, the console, and the durable gate ledger all report a clean 18/18 - a hook reporting healthy while verifying nothing. This is the same defect class the suite is built to expose, applied to the suite itself.
- **Fix:** Distinguish SKIP from PASS: return a dedicated code (e.g. 77) or print a machine-readable 'SELFTEST SKIP' marker that run_selftests parses and surfaces as `pre_push_gate: SKIPPED (git unavailable)`, counted separately from `ran` and recorded as such in gate_runs.json. Better still, treat a skip as a FAILURE on CI (where git and sh are guaranteed) via an env flag, so a silent skip can never be mistaken for verification.

### 33. [MEDIUM] One non-dict JSONL entry silently disables close_skills_guard entirely

- **Where:** `hooks/close_skills_guard.py`:57
- **Lens:** adversarial-input
- **What breaks:** A transcript acquires one malformed-but-parseable line (interleaved write, a future harness record type that is not an object, manual repair of a truncated file). Every subsequent close-signal write passes silently. The guard is now decoration and nothing says so.
- **Fix:** Filter in `_iter_entries`: `if isinstance(obj, dict): yield obj`. Add `isinstance(msg, dict)` and `isinstance(block.get('input'), dict)` checks. Separately, distinguish 'evaluated, all four present' from 'could not evaluate' — the latter deserves a one-line stderr note, because under the current design silence and health are indistinguishable, which is the failure mode the whole suite exists to attack.

### 34. [LOW] pre_push_gate and fast_test_on_stop key their shared state differently on Windows, so the advertised "already verified - allow instantly" fast path can never fire

- **Where:** `hooks/pre_push_gate.py`:94
- **Lens:** silent-failure
- **What breaks:** On Windows every push re-runs the full suite even when fast_test_on_stop verified the identical tree seconds earlier, and every `_record_pass` write is orphaned. Nothing reports the discrepancy; the two hooks each behave plausibly in isolation. Live proof above: two state files for one repo.
- **Fix:** Normalise the key at its single source: change `fast_test_on_stop._state_path` to hash `os.path.normcase(os.path.abspath(cwd)).replace('\\\\','/')` (or `os.path.realpath`) so separator and case variants converge, and add a selftest asserting `_state_path('C:/a/b') == _state_path('C:\\a\\b')`. Then add a cross-hook test that records a pass through fast_test_on_stop's own code path and asserts `pre_push_gate.last_pass` sees it.

## Refuted - kept as signal, not as work

A refuter killed these. A cluster of near-misses in one area is still information about that area.

- **(silent-failure)** MUTATION HOLE: pre_push_gate's last_pass can stop checking WHICH command passed and the whole gate stays GREEN
  - why refuted: REFUTED — the shipped code is correct and the claimed failure mechanism is backwards.

VERIFIED HALF: I reproduced the mutation in a scratch copy of HEAD (ff449ed). Deleting `or st.get("cmd") != cmd` at hooks/pre_push_gate.py:98 does survive: `python run_selftests.py` -> "all 18 selftests passed", `
- **(test-quality)** usage_snip_prompt's content assertions test vocabulary, not meaning - inverting the hard rule leaves the selftest green
  - why refuted: The mechanical claim reproduces, but it does not clear the bar for a defect.

WHAT I CONFIRMED (hooks/usage_snip_prompt.py:50-55): copying the hook to a scratchpad and rewriting "NEVER propose a weaker model" -> "ALWAYS propose a weaker model" yields SELFTEST OK / exit 0. A second inversion I tried,
- **(adversarial-input)** The installed shims fail CLOSED: if the baked-in interpreter path is gone, every push in every repo exits 127
  - why refuted: REFUTED as a defect of the class under review; severity corrected HIGH -> LOW (residual diagnostic-quality polish only).

MECHANICS CONFIRMED, CONCLUSION WRONG. I reproduced the reviewer's rc 127 exactly (temp repo, local core.hooksPath pointing at a GLOBAL_SHIM rendered with a dead interpreter; pla
- **(adversarial-input)** Malformed settings.json shapes make duplicate_registration_check exit 0 with no output
  - why refuted: REFUTED. The mechanical half of the claim reproduces exactly as described, but the failure scenario — the part that makes it a defect — is disproven by running the project's own code.

CONFIRMED MECHANICS (not in dispute): `_iter_commands` (hooks/duplicate_registration_check.py:52-59) wraps only `js
- **(adversarial-input)** The command scanner only matches script paths containing a separator, so bare-filename registrations are invisible
  - why refuted: REFUTED. The mechanical observation reproduces, but it is a deliberate, documented, project-wide scope boundary rather than a defect, and the reviewer never demonstrated a real configuration in which it hides a failure.

WHAT I CONFIRMED (the reviewer's repro is accurate)
Clean probe (shell-escaping

## P6 - carried items with a home here rather than in prose

These were raised during 2026-07-29 and are recorded as real rows so none of them lives only in a
chat transcript. Order is materiality; each is SCHEDULED.

### 35. Encode the durability lesson as a mechanism, not a sentence

- **Why:** v1.3.0 shipped CI-green and an adversarial review then found 34 confirmed defects in it.
  "CI green means the tests pass, not that they ask the right questions" is currently only prose in
  the handoff. A sentence in a doc is an instance fix; the next release will forget it.
- **Do:** record adversarial-review runs the way `gate_runs.json` records selftests - unit reviewed,
  run id, lens set, confirmed count, date - and make the release checklist read that ledger. A unit
  whose last review predates its most recent change is a release blocker.
- **DONE 2026-07-30.** `docs/audits/review_runs.json` is the ledger; `tools/check_review_freshness.py`
  reads it back. Units are DERIVED from the repo (`hooks/*.py` plus the top-level entry points),
  never from the ledger - a ledger-driven list would silently stop asking about any file nobody
  added, which is the exact failure that put two hardcoded rosters in this release. It prints every
  `run_selftests.py` run and BLOCKS only with `--release`.
- **It paid for itself on the first run.** Seeding it with the v1.3.0 review (`wf_b5ea865a-a33`)
  showed that review covered **6 of 14 hooks**. The other eight - `rate_prompt`, `show_your_proof`,
  `meta_audit_on_stop`, `memory_hygiene_guard`, `stop_dispatcher`, `plan_defer_guard`,
  `post_tooluse_dispatcher`, `numbers_match_on_write` - have NEVER been adversarially reviewed.
  Nothing recorded that before, because the review's scope was never written down next to the
  denominator. See item 45.

### 36. `delivery-gate` (ECC 2.1.0) vs unbluff behavioural comparison

- **Why:** ECC ships a hook occupying adjacent territory. Whether it genuinely overlaps or only
  shares vocabulary changes how unbluff is positioned, and nobody has run both.
- **Do:** build a shared fixture set (rationalised shortcut, unproven claim, clean turn, stale
  learning log) and run both hooks over each, comparing block/warn/pass verdicts. The harness
  doubles as unbluff's first cross-tool eval.
- **DONE 2026-07-30** - `tools/compare_delivery_gate.py`. Measured verdicts:

  | fixture | ECC delivery-gate | unbluff show_your_proof |
  |---|---|---|
  | rationalised shortcut | PASS | PASS |
  | unproven success claim | PASS | **BLOCK** |
  | same claim, WITH proof | PASS | PASS |
  | plain question, no claim | PASS | PASS |

- **VERDICT: no functional overlap - shared vocabulary, different territory.** They acted on the
  same fixture 0/4 times. ECC's gate tests ENVIRONMENT facts (learning-log mtime, disk space, a
  rationalisation regex); unbluff tests CLAIM-vs-EVIDENCE inside the turn. unbluff also
  discriminates rather than blanket-blocking: it blocks the unproven claim and passes the same
  claim once proof is present. Position unbluff as complementary, not competing.
- **The harness lied twice before it told the truth, and both are recorded in it.** (1) Scoring
  "any output" as WARN made ECC's unconditional `INFO:` line score WARN on all four fixtures -
  a 0/4 disagreement that was pure artefact. (2) The fixtures omitted the transcript's top-level
  `type` field, so show_your_proof skipped every entry and PASSed everything - a clean 4/4
  agreement that measured nothing. A comparison harness can be green and worthless in exactly the
  way a test suite can.

### 37. Measure the ECC PostToolUse dispatcher migration before deciding

- **Why:** ECC contributes roughly 28 individual hook spawns. Consolidating them may not repay
  touching a load-bearing `settings.json`. The decision needs a number, not an intuition.
- **Do:** time one tool call under the current wiring, then invoke `posttooluse-dispatcher.js`
  directly with the same synthetic payload. Decide from the delta.
- **DONE 2026-07-30** - `tools/measure_dispatcher_cost.py`, median of 5 reps on this machine:
  10 PostToolUse commands registered, 8 of them ECC `node -e` spawns.
  - ECC node spawns: **14.9 s serial / 6.1 s parallel** (both bounds measured; matchers gate which
    actually fire for a given tool, so the real figure sits at or below these)
  - single `posttooluse-dispatcher.js` invocation: **0.63 s**
  - saving under the CONSERVATIVE (fully-parallel) assumption: **5.4 s per tool call**
- **VERDICT: MIGRATE.** The saving clears the 250 ms bar by more than an order of magnitude even
  on the conservative bound, so the decision does not rest on a guess about how the harness
  schedules hooks. Deliberately reported as two bounds rather than the single scary 14.9 s figure.

### 38. Remove the superseded `~/.claude/hooks/*.py` copies

- **Why:** they are unregistered and inert, kept deliberately as a rollback while the merge settles.
  Leaving them indefinitely re-creates the two-root ambiguity this release existed to end.
- **Do:** after one clean stretch with no rollback needed, delete them and confirm
  `duplicate_registration_check` and `hook_health_check` stay green.
- **PREMISE WRONG - measured 2026-07-30.** They were NOT "unregistered and inert". Two were LIVE:
  `usage_snip_prompt.py` (SessionStart) and `close_skills_guard.py` (PostToolUse), both wired to
  the `~/.claude/hooks` copies. `tools/hook_divergence_report.py` scores those copies 89 and 471
  AST tokens from the repo - DIFFERENT PROGRAMS. **Every v1.3.1 fix to close_skills_guard was
  sitting in git while the old, buggy copy was the one actually running on this machine.**
  Deleting the files, as written, would have broken the live wiring instead of cleaning it up.
- **Why nothing caught it:** it is neither a duplicate nor a missing file.
  `duplicate_registration_check` saw exactly one registration for each (correct);
  `hook_health_check` saw a command resolving to a real script (also correct). "Registered once,
  but from the WRONG ROOT" was a state no check had a name for.
- **DONE 2026-07-30:** (a) both registrations re-pointed at the repo copies, settings.json backed
  up first, `hook-health` re-verified at 30 commands with no duplicates. Deliberately NOT via
  `install.py`: it strips entries whose id starts `unbluff:`, and these were hand-wired with
  `id=""`, so it would have ADDED a second registration rather than replacing them - manufacturing
  the very duplicate this suite exists to catch. (b) `hook_health_check.stale_root_registrations()`
  now names the state and fails on it, including when the stale copy is byte-identical (it will
  not stay identical) and when the path contains a space. The instance is fixed AND the class is
  now detectable.
- **Still open:** the `~/.claude/hooks/*.py` copies remain on disk as rollback, which the plan
  itself asks for ("after one clean stretch"). They are now genuinely unregistered, and the new
  gate makes a silent re-wiring impossible. Delete after one clean stretch.

### 39. Prune `memory/project_ghg_copilot.md` - DONE 2026-07-29

- **Why:** 150 KB with 71 evolving-state markers, while its own index line states canonical state
  lives in the GHG repo's `docs/MASTER_PLAN.md`. It contradicts its own instruction and is exactly
  what `memory_hygiene_guard` exists to flag.
- **Do:** in a session with the GHG repo open, classify every line DURABLE vs STATE, verify each
  durable claim still holds against the repo, and move live state into the plan rather than deleting
  it. Not to be done blind - an ambiguous line is kept and surfaced, not dropped.
- **Outcome:** completed in a separate GHG session on 2026-07-29. 150 KB -> 6.5 KB, 185 -> 108 lines,
  71 evolving-state markers -> 8, backup kept at `project_ghg_copilot.md.bak-2026-07-29`. No further
  action; recorded here so the next session does not redo it.

## P7 - found DURING the v1.3.1 fix pass

Scheduled here rather than left in prose. The working rule "after each fix, grep for the twin"
produced most of these; every one was live in v1.3.0 with CI green.

### 40. [HIGH] `fast_test_on_stop` had finding 10's unbounded-pipe bug identically - DONE

- **Where:** `hooks/fast_test_on_stop.py`:174 (pre-fix)
- **Found by:** the twin-grep rule, immediately after fixing finding 10 in `pre_push_gate`.
- **What breaks:** the same `subprocess.run(capture_output=True, timeout=)` that hung `git push`
  also ran the project's test command at every turn end. A vitest/jest watcher, a pytest-xdist
  worker or a dev server started by an integration test outlives its parent and holds the pipe,
  so the Stop hook hung the end of the turn - with no output and nothing naming the hook.
- **Fix:** the bounded runner now lives in `fast_test_on_stop` (`run_tests` + `_kill_tree`) and
  `pre_push_gate` imports it - the import only goes one way, so that is the only shared home.
  ONE implementation, both gates. Fixing only the instance would have left the Stop hook hanging.
- **Pinned by:** `fast_test_on_stop` selftest 5d (both hazards, at its own level so neither gate
  depends on the other's suite) and `pre_push_gate` case 14; mutation `fast_test_on_stop #10`.

### 41. [LOW - downgraded from MEDIUM after checking] `fast_test_on_stop`'s porcelain read: wrong paths and a crash risk, but detection was never lost - DONE

- **Where:** `hooks/fast_test_on_stop.py`:238,286 and `_changed_source_files`
- **Found by:** the twin-grep for finding 1 (the CRITICAL non-ASCII decode).
- **CORRECTION to my own first write-up of this item.** I initially recorded it as "a changed
  `données.py` is invisible, so the hook stays silent" - the same shape as finding 1. That is
  **wrong**, and worth recording rather than quietly fixing. Both call sites use the result as a
  BOOLEAN (`if not _changed_source_files(porcelain): return 0`), and a C-quoted
  `"donn\303\251es.py"` still ends in `.py`, so it still matched `SRC_EXT` and still counted as
  a change. Detection was intact. Overstating a finding is the same failure as missing one - it
  spends attention in the wrong place - so the severity is corrected here, not silently.
- **What was actually wrong:** (a) the returned PATHS were mangled strings no `os.path` call
  could open, so the function's stated contract was false and the first caller to use the paths
  for anything would inherit a silent bug; (b) `text=True` with no `encoding` decodes with cp1252
  on Windows, and cp1252 has undefined byte positions (0x81, 0x8D, 0x8F, 0x90, 0x9D), so a
  filename whose UTF-8 contains one raises `UnicodeDecodeError` - a `ValueError`, which the
  `except (OSError, subprocess.SubprocessError)` around the call does NOT catch. That crashes the
  Stop hook. Only reachable with `core.quotePath=false`, which is why it is LOW, not MEDIUM.
- **Fix (applied):** `encoding="utf-8", errors="surrogateescape"` on both calls, plus
  `--porcelain=v1 -z` and a NUL-field parser. `_changed_source_files` accepts both forms, so the
  newline fixtures still hold. A rename emits `XY NEW\0ORIG\0`, so the original name is consumed
  as its own field rather than parsed out of a `" -> "` substring a filename may legitimately
  contain. Pinned by selftest case 1b, including a rename and a non-ASCII path.

### 42. [MEDIUM] `close_skills_guard`'s selftest wrote every fixture to one filename - DONE

- **Where:** `hooks/close_skills_guard.py` `_mk()`
- **What breaks:** every fixture was written to `t.jsonl`, so a later scenario silently rewrote
  the transcript an earlier assertion still referenced. The new subprocess case read a transcript
  belonging to a different scenario and passed for the wrong reason. A test-harness defect of
  exactly the kind this plan exists to catch: green for a reason unrelated to the behaviour.
- **Fix:** one file per fixture (`t1.jsonl`, `t2.jsonl`, ...). Found only because the new case
  failed loudly first.

### 43. Mutation testing became a mechanism rather than a discipline - DONE

- **Where:** `tools/mutation_check.py` (new)
- **Why:** "mutation-test every fix" was a working rule a human had to remember. It is now a
  runnable harness: 21 mutations, each naming the finding it reverts, each required to turn the
  suite RED. A mutation that SURVIVES is reported as a failure naming the decorative test.
- **It already paid for itself three times** in this pass, catching decorative tests for
  findings 1b, 10 and 33 that had been written, run, and observed green.
- **Related:** item 35 (encode the durability lesson as a mechanism, not a sentence).

### 44. [MEDIUM] CI claimed a Python 3.8 floor on every platform but only ran 3.8 on Linux - DONE

- **Where:** `.github/workflows/selftest.yml`
- **Found by:** counting the jobs. The handoff and the plan both said "12 jobs: Linux/macOS/Windows
  x py3.8/3.9/3.11/3.12". The matrix is actually 3 OS x 3 versions plus a single ubuntu 3.8 entry,
  plus integration - **11 jobs**, with 3.8 verified on Linux only. A claim about coverage that
  nobody had counted, which is the same species as every other finding in this file.
- **What breaks:** the README advertises a 3.8 floor. `tools/check_python_floor.py` AST-parses at
  the floor, which catches syntax but not runtime behaviour, so a 3.8-only construct that
  misbehaves on Windows would ship green.
- **Fix (applied):** added `windows-latest / py3.8`. macOS 3.8 is deliberately absent -
  `setup-python` ships no 3.8 build for the arm64 `macos-latest` runners - and that absence is now
  a comment in the workflow so it reads as a decision rather than a gap.

### 45. [HIGH] Eight of fourteen hooks have NEVER been adversarially reviewed - OPEN

- **Found by:** item 35's ledger, on its first run.
- **What breaks:** the v1.3.0 adversarial review (`wf_b5ea865a-a33`) covered six units:
  `pre_push_gate`, `close_skills_guard`, `duplicate_registration_check`, `hook_health_check`,
  `fast_test_on_stop`, `usage_snip_prompt` (plus `run_selftests` and `install`). It found 34
  confirmed defects in those. The other eight hooks - `rate_prompt`, `show_your_proof`,
  `meta_audit_on_stop`, `memory_hygiene_guard`, `stop_dispatcher`, `plan_defer_guard`,
  `post_tooluse_dispatcher`, `numbers_match_on_write` - were never in scope and have never been
  reviewed at all. Given a 34-defect yield on the six that were, assuming the eight are clean is
  not a position anyone has evidence for.
- **Why it was invisible:** the review's SCOPE was never recorded next to the DENOMINATOR. "34
  confirmed findings" reads like a thorough audit until you ask "of how many units?".
- **Do:** run the same 4-lens adversarial review over the eight unreviewed hooks and record each
  in `docs/audits/review_runs.json`. Not folded into this release: it is a fresh review of
  different code, not a fix for a known defect, and `check_review_freshness.py --release` now
  reports it every run so it cannot be forgotten.

## Definition of done

- Every numbered item above is either fixed with a regression test that fails without the fix, or carries a written justification in this file for why it is not a defect.
- `python tools/mutation_check.py` reports every mutation CAUGHT (a survivor names a fix whose test does not bite).
- `run_selftests.py`, `tests/test_integration.py`, `tools/check_python_floor.py`, `tools/check_skill_deps.py` and `tools/regen_example_settings.py --check` all green.
- CI green on ubuntu/macos/windows x py3.8/3.9/3.11/3.12.
- A fresh `adversarial-review` run over the same unit returns no confirmed finding of a class already listed here.

## P8 - second adversarial review (run `wf_c2218ef3-6d2`, 2026-07-30)

Fresh 4-lens review over the units this pass changed. 21 agents. The lens agents produced
**25 raw findings; only 16 reached a refuter** (the workflow capped refutation at 4 per lens -
see P11). Of those 16, 13 survived a refuter defaulting to `refuted=true`, deduped to
**11 unique defects**. NINE were never adjudicated.

**Definition-of-done result: HOLDS.** Zero confirmed findings of a class already listed in P1-P7.
The three refuted findings were exactly the known-class re-reports (sh-absent selftest skips,
git-unanswerable in pre_push_gate, image-only prompt), which is the check working as intended.

**But 7 of the 11 were introduced BY the fixes**, concentrated in the newly-written verification
tooling - the tools whose green output is the evidence for everything else. That is the single
most important result of this pass and it is why the plan does not end at P7.

### FIXED in this pass

- **D1 [CRITICAL] `pre_push_gate` GLOBAL_SHIM + `reference-transaction`.** Finding 27's fix added
  `reference-transaction` to CLIENT_HOOKS; git fires it once per ref per transaction phase, and
  the shim forked `basename` + `git rev-parse` + `grep` every invocation. Measured: 100-tag
  `git fetch` 0.58s -> 106s (182x, 312 invocations); commit 0.26s -> 4.5s. `install_global()` sets
  core.hooksPath GLOBALLY, so this would have been machine-wide and permanent.
  **Was latent, not live** - `~/.claude/githooks` still held the 16 pre-fix dispatchers, so it
  would have landed on the next `--install-global`. Fixed on both axes, because the refuter showed
  the name alone was only ~54% of the cost: `HIGH_FREQUENCY_HOOKS` excludes it INSIDE
  `git_client_hook_names()` (removing it from the tuple would not work - the function unions git's
  own `*.sample` list), and the shim's common path now forks NOTHING.
  Removing the fork immediately exposed a second bug the selftest caught: `${0##*/}` strips only
  at `/`, so a dispatcher invoked with a Windows path kept the whole path as the hook name and
  every hook silently no-opped. Now stripped for both separators.
- **D2 [HIGH] `tools/mutation_check.py`.** A SKIP was invisible: `main()` bucketed only SURVIVED
  and HARNESS ERROR, so on Windows mutation #30 never ran and the last line still read
  "all mutations caught". Deleting the `os.chmod` it guards left the harness certifying every fix
  as pinned. Now prints the denominator ("25 of 26 executed, 1 skipped"), never claims all-green
  while anything is skipped, fails hard under `CI`, and validates the anchor BEFORE the skip so a
  drifted anchor cannot hide behind it.
- **D3 [HIGH] `tools/check_review_freshness.py`.** "git cannot answer" was bucketed as FRESH.
  Reproduced without stubbing via `git archive HEAD` into a scratch dir: all 8 correctly-STALE
  units flipped to FRESH. The release gate built to enforce "CI green is not enough" would itself
  have exited 0 having asked git nothing - the same contract this pass wrote into
  `newest_source_mtime`, broken in the tool written to encode the lesson. Now a fourth `unknown`
  bucket, excluded from the fresh numerator and blocking under `--release`.
- **D4 [HIGH] `tools/check_review_freshness.py`.** Freshness compared against the last COMMIT
  while `--record` stamps the WORKING TREE it just reviewed, and `run_selftests` invokes it mid
  development with a dirty tree. Appending `def backdoor(): return 42` to a reviewed hook left it
  reporting all-clear. Now `git status --porcelain -z` marks dirty units STALE. Deliberately not
  solved with mtimes: the prescribed review -> record -> commit order would flip just-reviewed
  units to STALE.

### D5-D7 - FIXED 2026-07-30 (second batch)

- **D5 [HIGH] `fast_test_on_stop.py`:270 - DONE.** `os.path.isdir(cwd/.git)` is False in a
  linked worktree or submodule (`.git` is a FILE there), so the Stop gate AND its
  `_notice_no_gate` safety net were both dead in every worktree - rc 0, empty stderr,
  indistinguishable from a clean passing turn. Reproduced: host rc=2, worktree rc=0 on identical
  config. Fixed with `is_git_worktree()` (`git rev-parse --is-inside-work-tree`, falling back to
  a filesystem probe only when git cannot run, so a missing git does not silently disable the
  gate everywhere).
  **The twin was real and was fixed generally, not copied.** `meta_audit_on_stop.py:78` used
  `os.path.exists` - which handles a worktree by accident but returns False for any
  SUBDIRECTORY of a repo, the normal cwd in a monorepo package. Both hooks now call the ONE
  function. Pinned by three mutations (`D5`, `D5b`, `D5-twin`), and the twin assertion is
  structural - it fails if this module ever grows a private `.git` probe again, rather than
  checking that a particular spelling is correct.
- **D6 [HIGH] `fast_test_on_stop.py`:86-94 - DONE.** One malformed `timeout=`/`debounce=` line
  made `_read_override` discard the COMMAND too, so `timeout=5m` yielded "no test command -
  nothing to verify, allowing push" for a repo that had deliberately configured a stricter
  gate. Now parsed per line: a bad value falls back to that field's default, the command
  survives, and stderr names the file and line number. Only an unreadable FILE may yield
  `cmd=None`, and that is said out loud too, because the file existing at all proves the repo
  intends to be gated.
  **Found while fixing it:** a typo'd option line with spaces (`timeout = 30`) did not match
  the `startswith("timeout=")` test, fell through to the `elif`, and became the COMMAND - i.e.
  it was handed to a shell and executed. Now recognised via `partition("=")` on the known keys.
- **D7 [HIGH] `pre_push_gate.py`:264-268 - DONE.** `install()` wrote to `<git-common-dir>/hooks`
  without reading `core.hooksPath`, which git honours INSTEAD with no fallback - so in a husky
  or lefthook repo it printed "installed ... gate command: npm test" and the repo was not gated,
  precisely the case `install_global()`'s own message prescribes `--install` for. `_hooks_dir_for()`
  now resolves where git will actually look and the success message names it.
  **Only the LOCAL setting is honoured, deliberately.** A global `core.hooksPath` is what
  `--install-global` sets; following it here would make `--install` write its shim into
  `~/.claude/githooks` and clobber the dispatchers themselves. That case is asserted directly,
  using this machine's live global setting. A foreign hook already present is still REFUSED
  rather than overwritten - asserted against a husky-shaped fixture.

### Still OPEN
- **D8-D11** - the remaining survivors (weekly-sweep aggregate time budget with no deadline and a
  marker written only after the whole loop; `duplicate_registration_check`'s selftest reading the
  invoking cwd's real `.claude/settings.json` so it is not hermetic; and two lower-severity items).
  Full detail in the run transcript: `subagents/workflows/wf_c2218ef3-6d2/journal.jsonl`.

### The lesson this round actually taught

The first review found 34 defects in code written normally. This review found 11 in code written
*specifically to fix those 34*, with regression tests and mutation testing applied throughout - and
7 were newly introduced, most of them in the verification tooling itself. Writing a tool to check
a property does not make the tool have that property. `check_review_freshness.py` shipped with the
exact "unanswerable collapses to pass" defect it exists to prevent, in the same commit that fixed
that defect elsewhere.

## P9 - item 45: the eight never-reviewed hooks (run `wf_3355090a-59e`, 2026-07-30)

21 agents, 4 lenses. The lens agents produced **43 raw findings; only 16 reached a refuter**
(the same 4-per-lens cap - see P11). All 16 adjudicated survived - none refuted, itself a
signal for files never looked at adversarially - deduping to 13 confirmed defects across 5
files. **TWENTY-SEVEN were never adjudicated**, the largest loss of the three passes. The three dispatcher/health files came back CLEAN.

| File | Confirmed | Worst |
|---|---|---|
| `numbers_match_on_write.py` | 6 | HIGH |
| `memory_hygiene_guard.py` | 3 | HIGH |
| `meta_audit_on_stop.py` | 2 | MEDIUM |
| `show_your_proof.py` | 1 | HIGH |
| `plan_defer_guard.py` | 1 | MEDIUM |
| `post_tooluse_dispatcher.py`, `stop_dispatcher.py`, `hook_health_check.py` | 0 | clean |

### FIXED

- **H1 `numbers_match_on_write` ref-prefix regex had no LEFT word boundary.** `.search()`ed
  against the 24 chars before every number, it matched the TAIL of any word: "p" swallowed
  `drop 0.85 kPa`, "no" swallowed `each 3.75 mm`, "v" swallowed `rev 1.75 s`. 35 of 38 common
  technical words hid the number after them, so a report of fabricated figures extracted ZERO
  cited numbers and passed clean. `(?<![A-Za-z])` added; `Figure 3` / `Table 2` / `eq. 4` still
  skipped, asserted both ways.
- **H2 a report inside a source dir was its own evidence.** `SOURCE_EXTS` includes `.md` and
  PostToolUse runs AFTER the write, so the fabricated number was in the index it was checked
  against. Worse, the index is SHARED: one fabricated `.md` in the source tree exempted that
  value for every report in the project. The report under check and everything matching the
  `reports` globs are now excluded, and the exclusion is folded into the cache key.
- **H3 `parse_config` did not strip trailing `#` comments.** The module's OWN documented
  config, pasted verbatim, produced a source path of `data  # dirs/files (relative to...`, a
  reports glob that can never match, `tol` silently reverting to the default, and
  `check_integers=False` where the user wrote `true`. No template ships, so the broken form was
  the only form a user could copy. The docstring config is now a test fixture.
- **H4 `memory_hygiene_guard.sanitize_cwd` implemented 3 of Claude Code's replacements.** Ground
  truth is `replace(/[^a-zA-Z0-9]/g,"-")` plus a 200-char truncate+hash. Any project path with
  a `_`, `.`, space, or over 200 chars resolved to a directory that does not exist, so the hook
  returned 0 on every Stop - permanently, silently. It worked on the author's machine and did
  nothing for anyone else. Now matches the real rule, and an unlocatable memory dir reports
  INCONCLUSIVE instead of passing.
- **H5 `memory_hygiene_guard.main()` had zero end-to-end coverage.** Three disabling mutations
  (`return 2`->`return 0`, `if not findings:`->`if True:`, dropping sanitize_cwd) each printed
  `memory_hygiene_guard: OK` under the full suite. It was the only Stop hook with no end-to-end
  path. `_selftest_main` now drives it through a temp projects root.
- **H6 `show_your_proof` accepted harness injections as real prompts - a TWIN of finding 17.**
  Its prefix list applied ONLY to the plain-string branch; the list branch accepted any block
  list with a text block and checked neither `isMeta` nor `sourceToolUseID`. Measured across
  139 transcripts / 28,396 user entries: 288 injections arrive as list content, **266 were
  accepted**, truncating the turn so the hook counted a fragment's tools - four verified
  stop-points would have fired "this turn ran no tools" at turns that ran 1-6 tools, and three
  transcripts selected this hook's OWN fed-back stderr as the prompt.
  **Fixed generally, not twice:** `hooks/transcript_util.py` is now the single classifier, and
  close_skills_guard imports it too. Both hooks' prefix lists are deleted; the shared module's
  selftest FAILS if a second list or classifier reappears anywhere in `hooks/`.
- **M6 `meta_audit_on_stop`'s twin guard could not fail - and I wrote it hours earlier.**
  `if "fast_test.is_git_worktree" not in src` greps the module's own source for a literal that
  appears *inside the assertion*, so it was present four times and three survived deleting the
  production call. The review mutation-tested it: swapping the probe for `.gitx` still printed
  SELFTEST OK. Replaced with a BEHAVIOURAL check - the shared probe is swapped for a recorder
  and the production path must actually call it. Pinned by mutation `M6`, which the regex
  cannot see.

### M1-M5 - FIXED 2026-07-31

- **M1 `numbers_match_on_write` - DONE.** - a typo'd `sources = reslts` yields an empty index, hits
  `if not values: return 0, ""`, and the EMPTY index is cached under the SHA-1 of the empty
  string, so later edits re-read it. A broken config is indistinguishable from opt-out. Fix:
  when `find_config` succeeds but sources resolve to nothing, say so once per session and do
  not cache an empty index.
- **M2 `numbers_match_on_write`:234 - DONE.** - `run()` breaks at MAX_BULLETS then reports
  `len(findings)` as the total: 40 unmatched numbers are announced as "12", with no truncation
  notice, and the marker then suppresses the hook for the session. `memory_hygiene_guard`
  already does this correctly - copy it.
- **M3 `numbers_match_on_write`:213 - DONE.** - line numbers via `text.count("\n", 0, start)` per match
  is O(numbers x filesize), and MAX_FILE_BYTES guards only SOURCE files. Measured 875 KB =
  25.2 s, 3.5 MB = killed at 120 s; a killed hook reads as rc 0, so the check is both blocking
  and not performed. Fix: bisect over precomputed newline offsets (3.5 MB -> 1.76 s) and cap
  the report read.
- **M4 `memory_hygiene_guard`:113 - DONE.** - the quarantine latch opens on ANY line containing
  "historical" and re-arms only on a literal `## `. 53 of 63 real memory files have no `## `
  heading at all, so one ordinary bullet would suppress the rest of the file for 84% of them.
  Latent: 0/63 currently contain a trigger word. Fix: only consult QUARANTINE_RE on heading
  lines; re-arm on any heading of the same or shallower depth.
- **M5 `plan_defer_guard`:157 - DONE.** - the once-per-session marker is keyed by session alone, but
  unlike meta_audit this hook scans ONE file per invocation. After firing on MASTER_PLAN.md,
  editing ROADMAP.md with three optional-forever markers returns `(0, "")` without opening it.
  `numbers_match_on_write.marker_path` already keys by (session, report) with this exact
  rationale in its docstring. Fix: key by `(session_id, sha1(abspath(path)))`.

### What this run says about the other numbers in this file

The first review found 34 defects in six units. This one found 13 in eight units that had
never been reviewed - including one HIGH (H6) that is the exact twin of a finding already fixed
in a sibling hook, and one (M6) in a guard written earlier the same day specifically to prevent
twins. "Never reviewed" was doing a lot of quiet work in this repo's health story.

### M1-M5 closing notes (2026-07-31)

All five fixed, each pinned by a mutation that fails without it. Two things worth recording:

- **M3's first perf assertion was itself decorative.** The bound was guessed at 12s; measured,
  the bisect runs the fixture in 0.33s and `count()`-per-match in 9.61s, so 12s sat ABOVE the
  quadratic time and the mutation survived. Retightened to 4.0s - 12x above linear, 2.4x below
  quadratic, so it still separates them on a much slower CI box. A performance assertion is
  worth exactly its measured margin; an unmeasured one is decoration with a number on it.
- **M4's first fixtures could not fire.** They used `NEXT:` while `PLAIN_NEXT_RE` matches
  `NEXT ORDER` or `NEXT=`, so all three latch cases returned empty and would have "passed" for
  the wrong reason had the assertions been written the other way round. Caught because the
  assertions were positive (this line MUST be found), not negative.

With P9 closed, every numbered item in this file is either fixed with a mutation-verified
regression test, or carries a written justification. `tools/check_review_freshness.py --release`
is the standing gate for whether that stays true.

## P10 - third adversarial pass (run `wf_a51d3013-715`, 2026-07-31)

21 agents, 4 lenses (regression-hunter, shared-module, silent-failure, test-quality) over the
19 units this session changed. The lens agents produced **28 raw findings; only 16 reached a
refuter**; of those, **15 survived**, deduped to 11 unique. **7 HIGH. Four were REGRESSIONS
introduced by this session's own fixes.** TWELVE were never adjudicated. Verdict from
the synthesis: not shippable as-is.

That is the headline result of the whole exercise: a third pass over code already reviewed
twice, and already carrying mutation-verified tests for every prior finding, still found seven
HIGH defects - most of them created by the fixes for the previous two rounds.

### FIXED (all 11)

- **HIGH-1 `hook_health_check`:169 - regression from D11.** `if name in done: continue` treated
  a persisted `"fail"` and `"skip"` as proved. A FAIL was skipped on the next session,
  `problems` came back empty, and the marker was written - **seven days of "[hook-health] OK"
  over a hook that had actually failed**. The mirror image was as bad: a SKIP (real -
  `pre_push_gate --selftest` exits 77 without git) blocks the marker forever while every hook
  is already in `done`, so the sweep is permanently due and permanently runs nothing. Now only
  `"pass"` is skipped, and the progress file is age-stamped so a slice that can never complete
  cannot freeze the recorded passes indefinitely.
- **HIGH-2 `numbers_match_on_write`:439 - the M1 fix was inert in production.** `main()` gated
  emission on `code == 2`, but `run()` deliberately returns `(0, message)` for the M1
  broken-config warning and the oversize-report skip. Both were discarded before reaching the
  user. The fix shipped, was mutation-pinned, and **never once reached a user** - because its
  test called `run()` directly and never went through `main()`.
- **HIGH-3 `transcript_util`:46 - regression from the H6 extraction.** The shared prefix list
  included PROSE: `"continue from where you left off."`, `"caveat:"`, `"[fast-test]"`. A human
  typing any of those is classified as a harness injection, `last_user` never advances, and
  audits run BEFORE the close satisfy `close_skills_guard` - the exact failure it exists to
  prevent, triggered by an ordinary sentence. All 80 real-corpus instances already carry
  `isMeta`, so the prose prefixes bought nothing. Deleted; the selftest that asserted the buggy
  behaviour now asserts the inverse.
- **HIGH-4 `fast_test_on_stop`:410,458** - `git status --porcelain -z` without `-uall` collapses
  a wholly-untracked directory to `?? src/`, whose extension is not in SRC_EXT, so adding a new
  module reads as "no source changed" on exactly the turn it is added. `pre_push_gate`
  disagreed with it (it uses `ls-files -cmo`). `-uall` added to both.
- **HIGH-5 `tools/mutation_check.py`:301** - `executed = len(MUTATIONS) - len(skipped)` ignored
  the `only` filter, so `mutation_check.py pre_push_gate` printed **"51 of 51 mutations
  executed, 0 skipped / all mutations caught"** after running two. The one line the entire
  evidence base rests on was arithmetic nonsense under the filter its own docstring advertises.
- **HIGH-6 `meta_audit_on_stop`:297** - the selftest's last assertion was about the REAL
  environment (`is_git_worktree(this file's dir)`), and `mutation_check` copies `hooks/` into a
  non-git tempdir, so the baseline was ALREADY RED there and mutations M6 and D5-twin were
  certified CAUGHT for an identity edit. Fixed on both sides: the assertion now builds the repo
  it needs, and `mutation_check` runs the UNMUTATED selftest first and reports
  `HARNESS ERROR: baseline already RED` rather than crediting a mutation.
- **HIGH-7 `tools/check_review_freshness.py`:89** - `dirty_units()` returned `set()` for both
  "clean" and "git could not answer", so `--release` exits 0 over uncommitted changes. Its twin
  `last_change()` had been given the `None` third state; this one had not. Same defect class,
  same file, one function apart.
- **MEDIUM-1 `install.py`:55** - `REQUIRED_HOOKS` was the THIRD hardcoded roster in this repo,
  and today's `transcript_util.py` was the only `hooks/*.py` missing from it. Derived now, tuple
  kept as a floor - the same conversion `run_selftests.py` and `hook_health_check.py` already had.
- **MEDIUM-2 `tools/mutation_check.py`:271** - any non-zero rc counted as CAUGHT, so `SKIP_RC=77`
  certified 13 `pre_push_gate` mutations as pinned on a machine without git. New UNPROVEN bucket.
- **LOW-1 `numbers_match_on_write`:349** - the `except Exception` fallback called
  `index_sources` without `exclude`, re-opening H2. A caller left behind when the parameter
  was added.
- **LOW-2 `fast_test_on_stop`:454** - `last.get("ts", 0)` on a poisoned state file raises;
  `stop_dispatcher` swallows it, so the Stop gate goes permanently dead in that repo. The
  hardening applied to `pre_push_gate.last_pass` (finding 9) was never applied to its twin
  reader of the SAME file.

### What three passes actually demonstrated

| Pass | Scope | Confirmed | Introduced by the previous pass |
|---|---|---|---|
| 1 (v1.3.0) | 6 of 14 hooks | 34 | - |
| 2 | the 6 fixed units | 11 | 7 |
| 3 | all 19 changed units | 11 | 4 |

Every round of fixes created defects at roughly a third the rate it removed them, and the new
ones concentrate in the verification tooling and in the seams between newly-shared modules.
Extraction into a shared module is not a neutral refactor: HIGH-3 and MEDIUM-1 both exist only
because `transcript_util` was created today. The rate is falling (7 then 4) but it is not zero,
which is the argument for the review-freshness gate being a standing release blocker rather
than a one-off.

## P11 - 48 findings ACROSS ALL THREE PASSES that were NEVER ADJUDICATED (CLOSED - see P13)

> **Status 2026-07-31: CLOSED.** All 48 reached a verdict in run wf_1a60d178-df1 - 26
> confirmed and fixed, 2 refuted, 7 already-fixed claims verified (2 of which had no test
> that bites, now pinned). The adjudication is recorded in P13 below; this section is kept
> as the record of what was open and why.

**Corrected 2026-07-31 by the consistency-audit close skill.** The first write-up of this
section blamed the third pass alone. Measured against all three journals, **every** review had
the same cap: the workflow script capped refutation at four findings per lens
(`.slice(0, 4)`), and 4 lenses x 4 = exactly 16 refuter calls in each run.

| Review | Raw produced | Adjudicated | NEVER adjudicated |
|---|---|---|---|
| P8 `wf_c2218ef3-6d2` | 25 | 16 | **9** |
| P9 `wf_3355090a-59e` (item 45) | 43 | 16 | **27** |
| P10 `wf_a51d3013-715` | 28 | 16 | **12** |
| **total** | **96** | **48** | **48** |

**Half of every finding this project's reviews produced was silently discarded**, and each
pass reported "16 raw findings" as though 16 were all there were. The plan asserted that in
three separate sections until this audit. The item-45 run is the worst: 43 produced, 27
dropped - and that was the review of the eight hooks that had never been examined at all.

The cap is in the harness, not the model: the lens agents did the work and their findings sit
in the journals. `.slice(0, 4)` MUST be removed, and any cap in a review harness must print
what it dropped, before the next pass runs.

**Mitigating, and verified:** later passes independently re-found and FIXED a number of these -
`fast_test_on_stop:270` (worktree, became D5), `check_review_freshness:94`/`:56` (became D3/D4),
`memory_hygiene:113` (M4), `plan_defer_guard:174` (M5), `numbers_match:234` (M2),
`numbers_match:324` (M1). That is luck plus overlap, not coverage.

### Never adjudicated and NOT since fixed - candidates, not confirmed defects

Each still needs refutation before it is treated as real. Grouped by file.

**`hooks/meta_audit_on_stop.py`** (the densest cluster; 5 of these are from the item-45 run)
- `:104` **HIGH** `count_unpushed` returns 0 for both "nothing unpushed" and "no upstream" -
  reproduced in a fresh repo: rc=128 -> 0, so a never-pushed branch looks identical to a clean
  tree. (Also reported at `:102` by a second lens.)
- `:48` the PARKED marker regex misses the bare uppercase `PARK`.
- `:53` the allow-tag list suppresses any line containing common words like `done`/`closed`.
- `:114` `_is_superseded` matches the substring anywhere in the first 5 lines, so an ACTIVE
  plan can be classed superseded.
- `:138` the unpushed-commit bullet is appended last and silently dropped by the bullet cap.

**`hooks/stop_dispatcher.py` / `post_tooluse_dispatcher.py`**
- `:53` both dispatchers record a hook that CRASHED as rc=0, and the fire ledger - the suite's
  own evidence of what fired - records the crash as a clean run.

**`hooks/rate_prompt.py`**
- `:57` a non-string `prompt` field crashes the hook with an uncaught AttributeError.
- `:105` the selftest swallows the OK/FAIL lines of its only two `main()` integration checks.

**`hooks/plan_defer_guard.py`**
- `:149` the bullet list truncates at 10 with no truncation notice (the M2 class, unfixed here).
- `:62` the `*plan*.md` glob matches unrelated files.
- `:222` two selftest cases pass vacuously - their fixture lines contain no marker.

**`hooks/numbers_match_on_write.py`**
- `:366`/`:313` a config whose `sources` key does not PARSE opts the project out silently (the
  M1 lesson applied at the resolve layer but not the parse layer).
- `:386` two selftest assertions cannot fail for the property they name.

**`hooks/memory_hygiene_guard.py`**
- `:192` the `+N more` count is computed after a silent per-file cap, so it under-reports.

**`hooks/hook_health_check.py`**
- `:350`/`:325`/`:224` `_iter_hook_commands` / `check_config` raise on a malformed `hooks`
  value or a non-string `command`, discarding the whole hook-health report.

**`hooks/duplicate_registration_check.py`**
- `:59` goes completely silent on a non-string `command`.
- `:390` the D9 `os.chdir` is not restored on the failure path, so a failing selftest exits
  with a cleanup traceback instead of its failure report.

**`hooks/pre_push_gate.py`**
- `:344` `HIGH_FREQUENCY_HOOKS` excludes `reference-transaction` from `--install-global`, which
  silently stops repo-local hooks of that name firing - the effect this file's own comment at
  `:318` forbids. (Caused by this session's CRITICAL perf fix.)
- `:863` the worktree install test asserts against `git rev-parse --git-path hooks`, the
  primitive P1 established is wrong under a live `core.hooksPath`.

**`hooks/fast_test_on_stop.py`**
- `:449` the two gates key the shared state file differently (session cwd vs repo toplevel), so
  the advertised fast path never fires from a subdirectory.
- `:102` the turn-end clamp `timeout: (5, 600)` is imposed on the PUSH gate, silently capping
  `timeout=1800` to 600 and making the remedy its own error message prescribes a no-op.

**`hooks/show_your_proof.py`**
- `:171` an image-ONLY user prompt is not treated as a turn boundary.

**`tools/check_review_freshness.py`**
- `:37` **VERIFIED** `units()` omits `tools/` and `tests/`: the ledger holds reviews for
  `tools/mutation_check.py`, `tools/check_review_freshness.py` and `tests/test_integration.py`
  that the gate never asks about, so `--record` for them is a no-op and `--release` can pass
  while the evidence tooling is unreviewed. Third instance of the hardcoded-roster class.
- `:83` an uncaught TypeError when a ledger entry has a non-string timestamp.

**`run_selftests.py` / `.github/workflows/selftest.yml`**
- `run_selftests.py:76` five auxiliary gates are invoked only `if os.path.exists(...)`, so a
  renamed tool silently removes the gate and `ran` drops with no expected count to compare.
- `selftest.yml:34` the mutation harness is invoked by NO automation, so a fix's test can
  become decorative between manual runs.

## P12 - meta-review, 2026-07-31 (close pass)

Run after the four close-audit skills. Each check measured, not asserted.

**Gate ledger (read, not reconstructed).** `docs/audits/gate_runs.json` holds 44 entries; the
last three are `run_selftests PASS ran=19 failed=[] skipped=[]`. `review_runs.json` holds 45
entries, latest `wf_a51d3013-715`. No gate tier is stale relative to the work.

**Parked-but-unscheduled: none.** The soft-defer sweep found one `PARK` hit and it is a quoted
regex marker name inside P11, not a deferral.

**Are this session's new mechanisms DURABLE or instance patches?** The question the user asked.

| mechanism | verdict |
|---|---|
| `transcript_util` | **DURABLE** - one classifier, both hooks import it, and its selftest FAILS if a second prefix list or classifier reappears anywhere in `hooks/`. |
| `check_review_freshness` | **PARTLY** - it is a real standing gate, but its own `units()` is the THIRD hardcoded roster (P11) and omits `tools/`+`tests/`, so it does not yet watch the tooling. Fix scheduled. |
| review ledger (`review_runs.json`) | **DURABLE** - written by `--record`, read by the gate, printed on every `run_selftests` run. |
| `mutation_check` | **WAS INSTANCE-ONLY - now fixed.** It was invoked by NO automation: it ran when someone remembered. A decorative test could reappear between manual runs, which is precisely the failure this repo exists to prevent. A `mutations` job is now in CI on ubuntu, which also executes the posix-only mutation #30 (the `install()` chmod) for the FIRST time anywhere - on Windows it can only ever report SKIPPED. `CI=true` additionally makes an UNPROVEN mutation fail the build. |

**Optimization - two files now exceed the 800-line rule. SCHEDULED, not parked:**
- `hooks/pre_push_gate.py` = 1038 lines (was ~430 at the start of the session)
- `hooks/fast_test_on_stop.py` = 821 lines
  Both grew by absorbing regression tests and shared helpers. The split is behaviour-preserving
  with the selftests as the safety net: move each hook's `selftest()` into a sibling
  `*_selftest.py` imported by the `--selftest` dispatch, leaving the hook body under 800.
  **DONE 2026-07-31** (see the P12 section at the end): 1113 -> 561 and 900 -> 539. It was
  not free - the move silently disarmed mutation #1b until the harness caught it.

**The durability lesson this session actually taught.** Three separate hardcoded rosters were
found (`run_selftests.SELFTESTABLE`, `hook_health_check._LOCAL_HOOKS`, `install.REQUIRED_HOOKS`)
plus a fourth in `check_review_freshness.units()`. Each was fixed by converting to detection
with the tuple kept as a floor. The general rule now has three independent enforcement points
(the `KNOWN_NO_SELFTEST` floor, the twin-guards in `hook_health_check` and `transcript_util`,
and the ledger denominator) - but `units()` shows the class is not yet extinct. Assume a fifth.

## P13 - the P11 backlog, ADJUDICATED (run `wf_1a60d178-df1`, 2026-07-31)

All 48 never-adjudicated findings reached a verdict. **35 claims, 35 verdicts, 0 dropped** -
one independent refuter per claim, no cap, and the workflow's own coverage block reconciled
findings produced against findings adjudicated before returning.

| | count |
|---|---|
| candidates refuted | 2 |
| candidates CONFIRMED and fixed | 26 |
| "already fixed by a later pass" - verified fixed | 7 |
| ...of those, with NO regression test that bites | **2** (now pinned, E1/E2) |
| new findings this pass produced | 3 (the cap family, D1b, finding 13's disarming) |

Refutation rate 2/28 = 7%, in line with the ~6% of earlier passes. The candidates were
candidates, and refuting them properly was not wasted work.

### Step 0 - the cap itself

The `.slice(0, 4)` lived in three throwaway per-session scripts, so patching those would have
been an instance fix to scripts that never run again. The durable home is the canonical harness
they were copied from, `~/.claude/skills/adversarial-review`:

- the template captures findings PRODUCED **before** any fan-out, reconciles that against
  findings ADJUDICATED, and logs a loud `COVERAGE GAP` when they differ;
- the returned `total` is the produced count, not the survivor count, so a caller reading one
  number cannot mistake a partial run for a complete one;
- `unadjudicated` is returned explicitly rather than being silently absent;
- SKILL.md gained a hard rule ("every finding reaches a refuter; never cap the fan-out"), an
  anti-pattern entry, and the incident table.

### REFUTED, with reasons

- **`check_review_freshness:83`** - "uncaught TypeError on a non-string ledger timestamp".
  `_parse()` coerces with `str(ts)` before `fromisoformat` AND catches `TypeError`. Two
  independent guards, neither stale. Corrected severity NONE.
- **`selftest.yml:34`** - "the mutation harness is invoked by no automation". False in the
  current tree: a top-level `mutations` job runs `tools/mutation_check.py` on ubuntu for every
  push and PR. The claim was true when written and was fixed in P12. Corrected severity NONE.

### CONFIRMED and fixed

| id | file | what was actually wrong |
|---|---|---|
| A1 | `tools/check_review_freshness.py` | `units()` asked about 17 of 31 tracked .py files - omitting `tools/`, `tests/` **and itself**, so the gate could not detect its own sabotage. Proved by committing a backdoor into `tools/mutation_check.py` with `--release` still exiting 0. Now `UNIT_GLOBS` intersected with `git ls-files` - 31/31 that day, 35 today as files were added. |
| A3 | `run_selftests.py` | five auxiliary gates invoked under a bare `if os.path.exists(...)`, so renaming a tool silently deleted its gate. A missing gate file is now a FAILURE, and every `tools/*.py` must be declared a gate or explicitly exempt. |
| B1 | `meta_audit_on_stop.py` | `count_unpushed` mapped "no upstream" (rc=128) to 0, the value that means "clean". A never-pushed branch was byte-identical to a synced tree for its whole pre-first-push life. Three states now. |
| B2 | `meta_audit_on_stop.py` | `PARKED?` requires the E: it matched the non-word "PARKE" and missed the bare "PARK". Rebuilt from a stem table; the selftest asserts every stem fires alone and no proper prefix does. |
| B3 | `meta_audit_on_stop.py` | a decision tag was matched anywhere in the line, so "TODO: make sure the socket is closed" was suppressed as already-decided. Tag position (ALL-CAPS or bracketed) is what the hook's own message always asked for. |
| B4 | `meta_audit_on_stop.py` | `_is_superseded` matched the word anywhere in the first 5 lines, so an ACTIVE plan saying "replaces PLAN_V2, which is superseded" was skipped whole. |
| B5 | `meta_audit_on_stop.py` | the unpushed bullet was appended LAST, so the display cap discarded it first - it vanished exactly when there was other work to report. |
| B6/B7/B8 | 4 hooks + `capped_report.py` | the cap was a family of five - see below. |
| C1 | both dispatchers | a hook that CRASHED was recorded as rc=0 in the fire ledger, so "checked and found nothing" and "raised and verified nothing" were the same record. Fixed in both twins in one commit. |
| C2/C3 | `rate_prompt.py` | a non-string `prompt` reached `.strip()` and raised (the only stdin hook with no payload guard); and the selftest's only two integration checks printed into the redirected StringIO, so both were invisible. |
| C4/C5 | `hook_health_check.py` | a malformed `hooks` container or a non-string `command` raised past the already-computed problem list and discarded the ENTIRE report. |
| C6/C7 | `duplicate_registration_check.py` | a non-string `command` silenced the whole audit; and the D9 `os.chdir` was restored only on the success path, so a FAILING selftest died in tempdir cleanup instead of printing why. |
| C8 | `numbers_match_on_write.py` | a config whose `sources` KEY never parsed opted the project out in silence - M1's lesson applied at the resolve layer but never at the parse layer. |
| D1/D1b | `plan_defer_guard.py`, `meta_audit_on_stop.py` | `*plan*.md` is a substring match, so `explanation.md` was a plan file. **Both** hooks had it. One predicate now, with a behavioural twin-guard. |
| D2 | `plan_defer_guard.py` | three selftest fixtures carried an exemption but no marker, so they asserted False against a function that returns False for any unmarked line - unfailable. |
| D3 | `numbers_match_on_write.py` | two assertions named the cross-reference and year gates while running in the mode where the bare-integer gate had already removed those numbers. |
| D4 | `transcript_util.py` | an image-ONLY prompt carries no text block, so the turn boundary slid back to the previous turn. |
| D5 | `fast_test_on_stop.py` | one option table for two gates silently clamped a push `timeout = 1800` to 600, making the remedy the gate's own error message prescribes a no-op. |
| D6 | `fast_test_on_stop.py` | the Stop gate keyed shared state on the SESSION dir, the push gate on the repo toplevel, so the advertised fast path never fired from a subdirectory. 28/34 canonicalised the key's SPELLING; the two gates were still keying different DIRECTORIES. |
| D7 | `pre_push_gate.py` | the worktree install test asserted against `git rev-parse --git-path hooks` - the primitive P1 established is wrong under a live `core.hooksPath`. The test used the broken primitive the production code was fixed to stop using. |
| D8 | `pre_push_gate.py` | `--install-global` drops `reference-transaction` for cost (measured: 0.9s to 100s+ on a 200-tag fetch, so the exclusion is CORRECT) while printing an unqualified promise that every repo-local hook still fires. The guard written to catch this diffed on the wrong side of the subtraction and was blind by construction. The exclusion stays; the silence is fixed. |
| E1/E2 | `tools/check_review_freshness.py` | D3/D4 were genuinely fixed, and **nothing pinned them**. Both third-state contracts now have a mutation that bites. |

### The bullet cap was a family of five

`meta_audit`, `plan_defer_guard`, `memory_hygiene_guard`, `numbers_match` and
`hook_health_check` each grew their own bullet cap. Finding M2 fixed the "say what you dropped"
rule in `numbers_match` **only**; the other four kept truncating - one with no notice at all,
one by stopping the scan at 10, one with a "+N more" computed after a silent per-file cap so
the number itself under-reported. The instance was fixed and the class was not, which is the
same shape as the four hardcoded rosters.

`hooks/capped_report.py` is now the single home, and it encodes the distinction that matters:
a DISPLAY cap is fine if it names what it hid, but a COLLECTION cap that `break`s destroys the
total - you cannot report what you dropped if you stopped counting.

Its selftest walks every hook's **AST** for a list capped against a `MAX_*` constant outside
the helper. Structural, not textual: a grep-based guard would have to contain the pattern it
forbids, and this repo has already recorded one guard that could not fail for exactly that
reason. It found all six offences across the four hooks, and it proves it can SEE a planted
offender - a matcher that matches nothing is indistinguishable from a clean sweep.

**Known scope limit, stated rather than implied:** the AST guard detects caps named `MAX_*`.
A cap written as a bare integer literal (`problems[:12]`) is not detected, because the
false-positive rate on `entry[:2]`-style slicing would make it useless. That one is caught by
review, not by this gate.

### Three findings this pass produced that P11 did not contain

1. **The cap family.** Found by the twin-grep after fixing B5, not by any reviewer.
2. **D1b** - `meta_audit` carried a twin of `plan_defer_guard`'s glob defect. Found by the same
   twin-grep discipline. That is the FIFTH instance of the shared-rule-in-two-places class the
   P12 note told us to assume.
3. **Finding 13 was silently disarmed by the fix for D4.** Adding `has_user_media()` gave the
   image-first fixture a second way to be recognised, so slicing `first_text` back to
   `content[:1]` stopped failing. The mutation harness caught it; a reader would not have. A
   non-media leading block now keeps 13 provable. **Fixing one finding can disarm the test for
   another, and only a mutation run makes that visible.**

Two other pre-existing mutations were broken by this session's own fixes and caught the same
way: `D9` (the C7 cwd restore ran too early, so the later hermeticity checks no longer ran from
the noisy directory) and the first draft of A1, whose selftest read the ambient tree and
therefore asserted nothing inside a scratch copy - its own mutation came back SURVIVED.

### The mutation harness could not reach its own directory

Before this pass the harness copied only `hooks/` into each scratch tree and resolved every
target as `hooks/<name>.py`. **No fix in `tools/` or in a top-level entry point could be
mutation-tested at all** - so the tool that certifies every other fix as pinned had a blind
spot covering itself, while the review-freshness gate that should have noticed omitted `tools/`
for the same reason. Both halves of the evidence base were unwatched simultaneously. It now
reaches any repo unit; A1/A1b/A3/A3b/E1/E2 are the first mutations ever applied outside
`hooks/`.

### P13 F - what only CI could see (and the premise that was wrong)

The handoff said "CI green". It was not: the `mutations` job added in P12 had **never
passed**. Its first ubuntu run reported three SURVIVED mutations that Windows catches every
time - which is exactly the reason that job was added, working as intended on its first
outing.

| mutation | why Windows caught it and Linux did not |
|---|---|
| `pre_push_gate #1` | dropping the explicit utf-8 codec is a literal no-op where the process locale is already UTF-8, so only a non-UTF-8 locale can fail. Fixed by asserting the INVARIANT (this module never falls back to the locale codec) alongside the behavioural case. |
| `fast_test #D10b` | `_win_job_kill_on_close()` already returns None on POSIX, so the edit changes nothing there. SURVIVED was a statement about the platform, not about the test. Now marked windows-only. |
| `fast_test #D10` | a timing race - see below. |

**The skip rule needed splitting.** Marking a mutation windows-only immediately exposed that
"CI must not skip" was written when every skip was runnable on *some* CI platform. An nt-only
mutation never is, on ubuntu. Skips are now two buckets: genuinely-skipped (still fails CI)
and not-runnable-on-this-platform (named in the denominator, never silent). A
`mutations-windows` job now exists so those are proven SOMEWHERE. An ubuntu-only mutation job
printing a clean summary over mutations it can never execute is this repo's own failure mode,
reproduced inside the harness built to detect it.

**D10 took three wrong guesses**, and all three were the same mistake: a blind sleep trying to
out-guess process start latency. The case proves `_kill_tree` really kills an orphaned
grandchild - the grandchild writes a marker AFTER sleeping, so the marker existing means it
outlived the kill. That only works if the check looks AFTER the moment a genuine survivor
would have written.

- 4s sleep against a 5s timeout: the grandchild finished on its own before any kill mattered.
  SURVIVED on ubuntu.
- 6s/4s and 9s/8s: the check ran BEFORE a survivor would have written, because the grandchild
  needs ~1.5s to start on Windows. SURVIVED there instead.

Both directions are one defect: **a test that passes because it measured at the wrong moment.**
It now polls, with the deadline anchored to the grandchild's own STARTED marker rather than to
a guessed duration, and it still fails loudly if the fixture never started.

The budget chase is worth recording too. Shaving the case to fit `hook_health_check`'s 20s
per-hook cap is what pushed it into the too-early failure; raising that cap alone tripped
hook_health's OWN invariant that the per-hook cap must stay below the aggregate slice - a good
guard catching a bad fix. Cap and aggregate moved together: 25 < 40 < the 60s SessionStart host
default, with the measurement written down rather than assumed.

### P12 - the 800-line split, and why it was not free

`pre_push_gate.py` 1113 -> 561, `fast_test_on_stop.py` 900 -> 539. Each `selftest()` now lives
in a sibling `*_selftest.py`, listed in `KNOWN_NO_SELFTEST` because it IS the test - and the
floor exists to make that an explicit statement rather than an omission nobody notices.

The refactor was **not** behaviour-preserving on the first attempt, and only one of the two
failures announced itself:

- **Loud:** `pre_push_gate`'s `main()` sits after its selftest functions, so it moved out with
  them. Immediate NameError.
- **Silent:** the selftests monkeypatch module globals. After the move,
  `globals()["_git"] = fake` rebinds a name in the SELFTEST module while `_repo_root` keeps
  reading the parent's - so the fake was never reached. Mutation `#1b` went from CAUGHT to
  SURVIVED: the test still passed, testing nothing. Same class for `global STATE_DIR` and
  `global project_root`. Every rebind now goes through `_m.<name>`, and the sibling's docstring
  states the rule as a rule.

A "behaviour-preserving refactor" whose safety net is the selftests is only as safe as the
proof that the selftests still bite. **That proof is the mutation run, not the green suite** -
the suite was green in both broken states.

### Final gate state

**Measured at commit 16c90bb, 2026-07-31 - point-in-time, not a standing claim.** These
numbers move whenever a gate or a hook is added, and a hand-written count in prose rots
exactly the way the README's did (it claimed 18 selftests while the suite ran 21). Run the
gates for the live figures; what follows is the record of that day.

- suite 21/21 (the two selftest siblings correctly exempted, not counted as run)
- integration 30/30
- mutations: 79 entries, 78 executed and ALL caught on Windows; 1 posix-only, named in the
  denominator and proven by the ubuntu job
- `check_review_freshness --release`: asked about **31/31** tracked .py files that day, up
  from 17. It has since grown to 35 as new files landed - which is the gate working.

## P14 - OPEN: the P13 session's own code, reviewed (run `wf_1b621b24-7ef`, 2026-08-01)

P13 fixed 26 defects and shipped ~2,900 lines with the suite, integration and CI all green.
Those lines had never been adversarially reviewed. They have now: **47 findings produced, 46
adjudicated, 42 CONFIRMED (10 HIGH, 22 MEDIUM, 10 LOW), 4 refuted, 1 DROPPED.**

Full record with per-finding evidence and fix sketches:
`docs/audits/p14_new_code_review.md`.

**The 1 dropped finding WAS open; it is now adjudicated CONFIRMED (see below).**
At the time this section was written it was open. The refuter for
`verify:ast-guard-completeness:1` died on a session usage limit. The coverage block reported
the gap rather than printing the survivor count as the total - the P13 Step 0 fix meeting a
real interruption and behaving correctly. P14 is not closeable until that candidate is
adjudicated.

**The confirmation rate is the finding.** 42 of 46, against ~7% in the P13 pass over
already-reviewed code. Every one of these landed while `run_selftests` said 22/22,
`test_integration` said 30/30 and CI said 14/14. New code plus a green suite is not evidence;
it is the absence of evidence, and this is the measurement that says so.

**The densest clusters, and why they are not a surprise:**

- `hooks/capped_report.py` (7 confirmed, incl. 2 HIGH) - the AST twin-guard written to
  enforce "assume a fifth" is itself blind to most cap spellings, and there is already an
  unrouted cap in `hook_health_check.py:470` that it reports as clean. The guard against
  instance-fixes was itself an instance fix.
- `tools/mutation_check.py` - the `executed` count omits `len(errors)`, and the SKIPPED-bucket
  branch is unreachable because both skip messages contain the word it tests for. The harness
  that proves every other test bites has arithmetic that contradicts its own error block.
- `run_selftests.py` - mutation A3 mutates `missing_gates()`, which `main()` never calls, so
  the missing-gate fix I added in P13 is pinned by a test that does not reach it.
- `hooks/meta_audit_on_stop.py` - `has_decision_tag` accepts an allow-word inside any
  parenthetical, markdown link, code span or URL, so a genuine hiding line is suppressed AND
  removed from the total.

**Not started.** No fix from this list has been applied. The session that produced it ran out
of context, and starting a partial pass over 42 findings - with the P13 evidence that fixes
here silently disarm each other's tests - would have been the wrong trade. Next session picks
this up with the audit doc as its work-list, HIGH first.
### P14 work order - SCHEDULED, not merely recorded

The audit doc enumerates the findings; this table is their HOME and their ORDER, so
that no cluster can be quietly skipped. Materiality decides sequence, never whether an
item ships. Every row must end as a mutation-verified fix or a written refutation.

| # | unit | HIGH | total | why here |
|---|---|---|---|---|
| 1 | `hooks/capped_report.py` | 4 | 8 | the guard the whole 'assume a fifth' rule rests on; a live unrouted cap already slips past it, so every other cap claim is unverified until this is fixed. **+1 HIGH from the adjudicated dropped candidate** - see `docs/audits/p14_triage.md` |
| 2 | `tools/mutation_check.py` | 2 | 9 | the harness that certifies every other fix; its `executed` count contradicts its own error block |
| 3 | `run_selftests.py` | 2 | 3 | mutation A3 targets a function main() never calls, so a P13 fix is pinned by a test that cannot reach it |
| 4 | `hooks/pre_push_gate_selftest.py` | 2 | 2 | see docs/audits/p14_new_code_review.md |
| 5 | `hooks/meta_audit_on_stop.py` | 1 | 6 | false negatives that REMOVE a hiding line from the reported total |
| 6 | `tools/check_review_freshness.py` | 0 | 8 | the release gate itself |
| 7 | `hooks/stop_dispatcher.py` | 0 | 2 | CRASH_RC is truthy and no test drives main() through a crash |
| 8 | `hooks/numbers_match_on_write.py` | 0 | 1 | see docs/audits/p14_new_code_review.md |
| 9 | `hooks/plan_defer_guard.py` | 0 | 1 | see docs/audits/p14_new_code_review.md |
| 10 | `tools/check_readme_fresh.py` | 0 | 1 | see docs/audits/p14_new_code_review.md |
| 11 | `hooks/transcript_util.py` | 0 | 2 | the twin-guard, plus **F-L8** - added 2026-08-02 by the consistency audit, which found the table summed to 43 against a stated backlog of 44. `p14_triage.md` said "add as LOW against `hooks/transcript_util.py`" and nobody did. The table built to stop a quiet skip was short by exactly the finding triage had added |
| 12 | `hooks/rate_prompt.py` | 0 | 1 | see docs/audits/p14_new_code_review.md |

**The dropped candidate is CLOSED: adjudicated CONFIRMED, HIGH, latent** (2026-08-01).
`verify:ast-guard-completeness:1` - a cap constant that is imported, annotated,
tuple-assigned or attribute-qualified is invisible to `slicing_offenders`; 5 of 6 spellings
blind, and `if not caps: continue` skips 13 of the 17 hook files. Evidence and the
corrected causal account are in `docs/audits/p14_triage.md`. It folds into row 1, which
is why row 1 now reads 4 HIGH / 8 total.

**The recovered first-run set is TRIAGED and MERGED** (2026-08-01). Overlap with the main
42 is **41 of 42 (97.6%)**, counted finding-by-finding rather than assumed. It yielded one
finding with no twin, one twin of the dropped candidate, and two severity ESCALATIONS where
the first run found live instances the main list called latent. **Merged backlog: 44 open -
11 HIGH, 24 MEDIUM, 9 LOW.** Full reconciliation table: `docs/audits/p14_triage.md`.

### P14 stopping rule - AGREED 2026-08-01, binding

P13 reviewed P11's code and found 26. P14 reviewed P13's and found 42. A pass over P14's
fixes will find more. "Review until a pass returns zero" is not a finish line, so P14
terminates by CONSTRUCTION instead:

1. **Severity bar - a SHIP gate, NOT a DONE gate.** v1.3.1 ships when **zero HIGH is open**.
   Every remaining MEDIUM and LOW gets a written owner and a scheduled row here, and is
   **STILL BUILT** - after the ship, in materiality order, but built. Materiality decides
   WHEN an item ships, never WHETHER it does. Nothing is closed by being logged.
2. **Recursion bound.** The P14 fix diff gets **exactly one** review pass, P15, scoped to
   that diff and not to the repo. P15's HIGHs block the ship; P15's MEDIUM and LOW are
   scheduled - which under rule 1 means scheduled TO BE BUILT, not parked. **There is no
   P16.** Termination does not depend on what P15 finds.

> **CLARIFICATION 2026-08-02, after the owner had to ask.** Earlier wording throughout this
> plan and in session summaries repeatedly said MEDIUM and LOW are "recorded with owners",
> which reads as logged-and-left. That is the optional-forever framing `plan_defer_guard`
> exists to catch, and it appeared in the stopping rule itself. **Zero HIGH is when the
> release goes out; it is not when the work stops.** A non-HIGH finding is not permission to
> stop - it is a position in the queue. The only way an item leaves this plan unbuilt is as
> an explicit FINALIZED EXCLUSION with a written justification, and there are currently none.

This is the rule the release is measured against. Changing it is a decision to record here,
not a judgement call to make mid-pass.

### P14 cluster 1 - `hooks/capped_report.py` - REVERTED 2026-08-02, findings OPEN again

> **CORRECTION.** An earlier version of this section read "CLOSED to the severity bar". That
> was written before the revert and is FALSE: `hooks/capped_report.py` is back at the
> `1dcf430` baseline, so all 8 original cluster-1 findings are OPEN again and the 8 residual
> rows below describe code that no longer exists. Left visible rather than deleted - a plan
> that quietly rewrites its own history is the same defect as a gate that quietly narrows.

**Why it was reverted.** Two fix rounds grew the detector from 180 lines / 1.2s to 2101
lines / 36.1s (11.7x and 30x, both MEASURED) to enumerate Python cap syntaxes. That set is
unbounded, so the work could not terminate - round 1 exercised 47 spellings, round 2 exercised
111, and the verifiers still demonstrated fresh blind spots after each. Worse, it failed
**OPEN**: an unenumerated shape was reported clean. Failing open is the exact defect this repo
exists to catch, so the guard had become an instance of the disease. It also exceeded the 25s
`_SELFTEST_TIMEOUT_S` of `hook_health_check`'s weekly sweep, which runs on every installed
user's machine - a shipped defect, not just a CI symptom.

**Kept from those two rounds** (real value, verified after the revert): the 5 live unrouted-cap
fixes in `hook_health_check.py`, `show_your_proof.py`, `measure_dispatcher_cost.py`,
`audit.py` and `extract.py`; `tests/cap_spelling_corpus.py` (111 labelled spellings,
self-checking, append-only) as the grader for whatever replaces the detector; the
`transcript_util` #13 anchor disambiguation (M-M12's live instance - the anchor MEASURABLY
matched twice); and every audit document.

**The rebuild is scheduled as C1-NEW below and has not started.**

Three rounds. Round 1 (`wf_7c6b33a8-265`, 13 agents) and round 2 (`wf_05787685-fee`,
11 agents) were adversarial fix workflows; round 3 was a direct fix of the one HIGH that
round 2's own acceptance test exposed. Full evidence - the 111-spelling taxonomy, the
123-hit false-positive budget, the exemption design, the measured int-literal policy and all
16 verifier verdicts - is in `docs/audits/p14_cluster1_evidence.md`.

**All 8 original findings were closed at the time, plus 7 round-2 findings and 1 round-3
finding** - then the detector carrying those fixes was REVERTED, so **all 8 are OPEN again**
and only the 5 live-cap fixes survive (commit `d641da7`). The original sentence here read
"All 8 original findings closed" with no qualifier; the P14 completeness audit flagged it as
false post-revert and directly contradicted by the correction box above. Corrected in place,
because a plan that quietly rewrites its own history is the same defect as a gate that
quietly narrows.

**What this cluster actually proved, and it is the most important result of P14.**
Round 1 closed 8 findings, passed 22/22 selftests, 30/30 integration and 92-of-94 mutations
ALL CAUGHT - and shipped two detection regressions plus a production crash. Measured against
the guard at `1dcf430` with a clean control, round 1's code was blind to **10 of 14** cap
spellings its own predecessor caught, and `--selftest` died with `ModuleNotFoundError` in the
installed layout, which is the only layout the hook ever runs in. **No gate in this repo
detects a fix that REMOVES detection.** Mutation entries pin what a fix adds; nothing pinned
what it took away. That is the argument for the P15 bound, and P15's brief MUST include an
explicit no-regression-versus-predecessor check as a named requirement.

| round | closed | introduced | caught by |
|---|---|---|---|
| 1 | 8 | 2 regressions | the adversarial verifiers, not the gates |
| 2 | 7 | 7 new defects (below) | the adversarial verifiers, not the gates |
| 3 | 1 (installed-layout crash) | 0 | round 2's own acceptance test |

#### Cluster-1 residuals - RETIRED as rows, kept as acceptance criteria

> **CORRECTION, from the P14 completeness audit.** Rows `C1-R1..R8` named
> `_body_changes_length`, `_callee_aliases`, `_cap_names`, `_BASELINE_FLOOR_NAMES`,
> `_is_size_measure`, `exemption_problems`, `_TAXONOMY` and `int_cap_sites`. **Every one has
> 0 hits repo-wide** and every line number cited is out of range for a 180-line file. They
> described the reverted detector. Two further claims in this section were FALSE: "All 8
> original findings closed" (contradicted by the correction box above) and "None of the below
> is HIGH, so cluster 1 meets the bar" (work-order row 1 carries 4 open HIGH). Retired rather
> than deleted, because the CLASSES they name are the acceptance criteria the rebuild must
> meet.

**Acceptance criteria for C1-NEW** (each was a real defect in the reverted detector; the
rebuild must not reintroduce it): a drop-until-under-cap loop must not go blind when the drop
is a rebind-slice; a callee renamed by assignment must still resolve; no branch may be dead
the day it lands; the no-regression floor must be DERIVED, not a roster of names; a
size-vs-collection split must not mis-branch a scan-truncating exit; `caps` must not be
module-scoped such that one function's default promotes a name file-wide; exemption keys must
separate scopes that share a name; and no docstring may state a coverage boundary it does not
have.

#### The fail-open premise is REPO-WIDE, not a `capped_report` mistake - B5 ANSWERED

Three guards audited, **three fail open**, each demonstrated with live controls:

| guard | shapes enumerated | novel shapes silent | controls caught | verdict |
|---|---|---|---|---|
| `capped_report` slicing_offenders | 47 -> 111 and still growing | many | yes | reverted |
| `transcript_util` twin-guard | **4** names, 3 line-anchored regexes, 1 non-recursive dir | **6 of 6** | 5 of 5 | rebuild fail-closed |
| `duplicate_registration_check` | **11** literals | **6 of 6** | 3 of 3 + in-fixture controls | rebuild fail-closed |

The `transcript_util` case is the sharpest argument in this whole pass: it enumerates
**identifier choices**, and the scenario it guards against is *an author who did not know
`transcript_util.py` existed* - who therefore had no reason to pick its names. The guard is
blind precisely in the case it was written for.

`duplicate_registration_check` is blind to `.js`, `.ps1` and `.sh` hooks wired twice - while
the repo's OWN sibling guard already declares `_SCRIPT_EXTS = (".py", ".js", ".ps1", ".sh")`
at `hook_health_check.py:137`. It is also blind to `python -m` module form, to any dispatcher
whose filename lacks the substring "dispatcher", to any dispatcher whose module list is not
literally named `HOOKS`, and to **7 plugin `hooks.json` files that exist on this machine right
now** and declare `PreToolUse`/`PostToolUse`/`Stop`/`UserPromptSubmit`.

#### RE-BASED PHASE ORDER - supersedes the 12-cluster table above

The old order put `capped_report` first because "a live unrouted cap already slips past it".
That rationale is spent: all 5 live caps are fixed and pushed in `d641da7`. The order below
is derived from what is now true.

| phase | contents | why it is here |
|---|---|---|
| **0 - FOUNDATION** | C1 gate ledger; B6 CI; D1; D2. **M1 anchor-drift gate DONE 2026-08-06 (`6807121`).** STILL OPEN: **A8** - promoted here, because a loaded box turns wall-clock budget failures into 14-of-98 HARNESS ERRORs and so blocks the verification loop itself | Nothing downstream is provable until gates leave traces and CI runs. D1/D2 are what stop the next cluster repeating cluster 1. M1 belongs here for the same reason: it makes a disarmed mutation cost 0.087s to find instead of a full sweep |
| **1 - THE CLASS FIX** | the fail-open family. **`transcript_util` twin-guard DONE, `duplicate_registration_check` DONE (`0c0dfb9`), and C1-NEW BUILT 2026-08-06 (`f77eefd`, `3dd82f4`) - its 4 HIGH remain OPEN pending the adversarial pass.** STILL OPEN: the roster-shaped checks (`run_selftests` `_DISPATCH_RE` + aux-gate-exit-0, `check_review_freshness` EXEMPT floor + narrowing fixture, `mutation_check` prose-substring bucket, N3) | ~15 findings, ONE principle. Fixing them separately is 15 chances to reintroduce the premise |
| **2 - VERIFIER OF VERIFIERS** | `mutation_check` remainder (9 findings, incl. **M-M12** now explicitly rowed); **SC1** - the measurement-tool exemption hole; and from the 2026-08-06 B1 build: **B1-AC3** (acceptance criterion 3 unverified for the two new modules), **B1-SCOPE** (`tools/` unswept), **B1-C2FLOW** (clause 2 does not follow flow through an assignment - the blocker for B1-SCOPE), and **MR-c** (six uncontrolled timing claims, no mechanism) | it certifies every other fix and nothing verifies it. SC1 sits here because a tool that produces numbers quoted in this plan is a verifier in everything but name |
| **3 - THE RELEASE GATE** | `check_review_freshness` (8 findings) | it decides whether v1.3.1 can ship, and sat at position 6 |
| **4 - INDEPENDENT BUGS** | the genuine one-offs, by severity: M2, M3, A4-narrow, A9, F-L8, C2, N2, **SC2** (mutation scratch-tree leak), and from 2026-08-06: **SC4** (`F-H3`'s unstated fix ORDER), **N3-DUP** (nothing notices a module defining a top-level name twice), **MR-d** (WITHDRAWN - the session straddled midnight; kept as a lesson about single-reading date claims) | |

**Release decision, 2026-08-02:** no interim version is cut. v1.3.1 ships once the fixes are
done, so users never see an intermediate guard. Recorded here rather than left in chat.

#### D1/D2 built - and D1 found a LIVE shipping defect while being designed

| id | sev | owner | item |
|---|---|---|---|
| D2 | - | **BUILT 2026-08-02** | `tools/no_regression.py`, wired as AUX gate 23. Blocks a change that stops detecting what its predecessor detected - the class NOTHING here caught. Acceptance proven both ways: the repaired round-2 detector passes (`rc=0`), a faithfully reconstructed regression **blocks with 31 of 31 lost**. 0.42s, so per-stop not CI-only. Two mutations, both CAUGHT |
| D1 | - | designed, **not yet wired** | `hooks/selftest_budget.py`. Inverts the dependency so the number a hook budgets against IS the number that kills it, enforced by AST (a textual guard must contain the pattern it forbids), mutation-tested 4/4 killed with a green control |
| **D1-FIND** | **HIGH** | phase 0, with D1 | **`fast_test_on_stop.py --selftest` already exceeds the 25s cap that governs it, on every installed machine.** MEASURED by me directly: 25.05s / 25.26s / 25.51s, three of three over, on an idle box; the design agent measured 24.36-25.43s over 7 runs. `hook_health_check` runs it with `timeout=_SELFTEST_TIMEOUT_S` and on timeout appends `weekly selftest ERRORED/timed out`, so a **passing** hook is intermittently reported as broken in the weekly sweep users actually run. The comment justifying the cap (`hook_health_check.py:118-124`) states the failure mode exactly - "A cap a HEALTHY selftest exceeds does not catch a broken hook, it manufactures 'ERRORED/timed out' for a passing one" - and rests on "Measured 2026-07-31: slowest is fast_test_on_stop at ~19.7s warm", which is stale. The code documented the trap and fell into it. Straddling 25s makes it non-deterministic, which is why nobody noticed. **Adopting D1 turns the suite RED on this until it is fixed - that is correct, not a blocker to route around.** Fix is its own decision: shrink the selftest's deliberate sleeps (`gc_sleep=9`, a 3s timeout against a 60s sleeper) or raise the cap and `_WEEKLY_BUDGET_S` together, and the sleeps are load-bearing (the D10 grandchild case must outlive the runner's own timeout to mean anything) |

| **D1-FIND-2** | **HIGH** | **FIXED 2026-08-02** | **The pre-push gate failed OPEN on timeout, and a test pinned that as the contract.** `pre_push_gate.py:243` printed "This push is NOT verified" and then `return 0`, allowing the push. The asymmetry was backwards: `rc != 0` (tests FAILED) blocked correctly, while `rc is None` (tests did not FINISH) was waved through - "didn't run" counted as "passed", in the gate that guards the repo. NOT hypothetical: it fired on the push of `8aec982`, which reached origin unverified. The suite legitimately grew to 23 gates, so the timeout was being exceeded routinely rather than rarely - the gate had become fail-open in the COMMON case, and a warning printed after the push has already happened warns nobody. **Worse, `pre_push_gate_selftest.py:388` asserted `rc_m != 0` - it REQUIRED the gate to allow the push, and labelled the case "timeout outcome message missing" as though only the wording were at stake.** Every review of that file read an assertion that looked like coverage and was in fact protecting the defect - a different failure from a decorative test: this one had teeth, pointed the wrong way. Now BLOCKS with the typed escape (`git push --no-verify`), and the assertion is inverted to pin it |
| **D1-FIND** | **FIXED 2026-08-02** | - | `fast_test_on_stop --selftest` measured 24.65s median against its 25s cap; now **17.20s**, 31% headroom. `gc_sleep=9` and the 3s runner timeout are UNCHANGED - they are the margin that makes SURVIVED mean anything, and the two previous attempts to shave them each produced a decorative test (4s vs 5s finished on its own on fast Linux; an 8s blind poll ran before a genuine survivor could write, on Windows). Only how DEATH is OBSERVED changed: the grandchild heartbeats while alive, so a stalled beat proves the kill positively in ~2s instead of inferring it from a ~12s absence. Verified by an INTERLEAVED A/B against the committed version under identical load: **-7.32s median**. That control overturned my own conclusion - I had measured 32s and decided the change made things worse; the 32s was ambient load from a concurrent push. Third time in this session a control reversed a timing conclusion I would otherwise have acted on |

| **D1** | - | **BUILT 2026-08-02, partially wired** | `hooks/selftest_budget.py`. ONE declaration of the cap; `hook_health_check` now READS it, so the number a hook budgets against IS the number that kills it. Two AST guards (`redeclared_caps`, `governing_binding_ok`) - both fired red against the real repo before passing, which is the only reason to trust them. Wired: `capped_report` (0.20s, default share), `hook_health_check` (6.53s, 0.40), `meta_audit_on_stop` (13.30s, 0.70). Coverage is DERIVED and printed every run: **3 of 18**, naming the 15 unwired. Not a roster |
| **D1-LIMIT** | **MEDIUM** | phase 0 | **A wall-clock budget cannot separate "this selftest got slower" from "this machine is busy", and `fast_test_on_stop` / `pre_push_gate` are DELIBERATELY unwired because of it.** Both measure ~17.1s clean (68% of the cap) but 30-105s while other selftests run. Root cause found: their selftests SPAWN 60s and 120s sleeper processes to verify the kill logic, so running them repeatedly loads the machine with the very processes being timed - 11 orphans were still resident after ~20 runs. Four separate timing conclusions in this session were confounded by exactly this, each caught only by a control. Wiring them at any share would ship a gate that fires on load rather than drift, and a flaky gate gets disabled - strictly worse than none. **The design needs a load-normalised measure** (a calibration probe run alongside, or CPU time rather than wall time) before those two can be budgeted. Recorded, printed in the coverage line, not silently skipped |
| **D1-FIND-3** | **MEDIUM** | phase 0 | Both `fast_test_on_stop` and `pre_push_gate` sit at ~68% of a cap that KILLS them - the same class as D1-FIND, two more instances. The fix is reducing their selftest duration the way `fast_test_on_stop` already was (24.65s -> 17.2s, by observing death directly instead of waiting out a 12s absence). `pre_push_gate` almost certainly carries the same waiting-for-absence pattern |
| **D1-FIND-4** | LOW | phase 4 | The kill-verification selftests LEAK long-lived sleeper processes: after ~20 runs, 11 orphaned pythons were still resident, and they persist 60-120s each. Worth establishing whether this is incomplete cleanup or inherent to testing kill logic - it degrades every subsequent measurement on the machine |

Two findings from BUILDING D2, both worth more than the code:

- **The regressing artifact was never preserved.** The first acceptance test failed correctly: `capped_report_r2_full.py` is the REPAIRED detector (round 2 fixed R2-H1 before ending), so it detects 96 of 96 where the baseline detects 31 - more, not less. The version measured at 10-of-14 blind exists nowhere, and the regression had to be RECONSTRUCTED via the exact edit R2-H1 describes. Labelled reconstructed, never presented as the original. **Preserve the failing artifact, not only the fix**, or the mechanism built to catch a defect cannot be tested against it.
- **The corpus is biased toward its author.** Predecessor scores 31 of 96 on a corpus the successor scores 96 of 96 on, because the successor wrote most of it. Only the 14 scalar-suffix entries are baseline-verified. This is the trap already named in this plan - "the taxonomy was written by the same agent that wrote the detector" - walked into anyway. The corpus needs entries derived from the PREDECESSOR's capabilities, not only the successor's.
- **My own new test was decorative and the mutation harness caught it in under a minute.** `no_regression` assertion D checked that an unusable predecessor raises `Broken`; mutation D2b SURVIVED, because with the guard deleted `compare()` still raises `Broken` from a different check and `except Broken: pass` swallowed it. Fixed to assert on the reason string; both mutations now CAUGHT.

#### Consistency audit - 71 claims tested, corrections applied 2026-08-02

The audit extracted and mechanically tested 71 checkable claims across the README, the plan
and the audit docs. Fixed in this commit:

| where | the claim | the measurement | action |
|---|---|---|---|
| `README.md:171` | "==== 26/26 scenarios passed ====" | the suite runs **30** | **fixed to 30/30.** It rotted 4 behind because `check_readme_fresh` regexes only `all (\\d+) selftests passed` - its own OK line says "README's 22 matches the 22 selftests", never mentioning scenarios. That is P14 finding M-M5, live, and the general fix stays scheduled in phase 3 |
| `README.md:149`, `:274` | "this is exactly what CI runs on Linux, macOS, and Windows" / "CI runs the self-tests + the integration test on Linux, macOS, and Windows across Python 3.8-3.12" | the `integration` job is `runs-on: ubuntu-latest`, ONE of 14 jobs. Python **3.10 runs on no platform at all**; macOS skips 3.8 | **both rewritten** to state the real matrix. Public-facing false claims about what the gates do, in a tool whose pitch is catching gates that lie |
| `docs/audits/p14_cluster1_evidence.md` | `fp_must_not_flag` declared **(107)** | the line is 1431 chars, JSON unterminated at char 1393, **at most 37 entries present**, no truncation notice | **generator fixed, doc regenerated: 107 declared, 107 emitted, verified equal.** I wrote a silent `[:1400]` slice that printed the full count beside a truncated body - the exact defect `capped_report` exists to abolish, inside the document written to stop evidence loss |
| work-order table | "Merged backlog: **44** open" | the table's own columns sum to **43** | **row 11 corrected to 2.** The missing item was F-L8, which `p14_triage.md` explicitly said to add and nobody did |

Recorded, not yet fixed (each has a home below or in the phase order):

| where | correction |
|---|---|
| plan `:949`, `:1121` | "`pre_push_gate.py` 1113 -> **561**". Swept every commit in history: **561 was never its line count**, as total or non-blank. It was 584 at the split commit and is 584 now. The other three numbers in that pair (1113, 900, 539) all check out |
| plan `:1178` | "there is already an unrouted cap in `hook_health_check.py:470` that it reports as clean" - present tense, but routed in `d641da7`. The same section's "Kept from those two rounds" paragraph says the opposite |
| plan `:1272` | "the **123**-hit false-positive budget" - the string "123" appears **zero** times in the evidence file, which records 107 |
| N3 | "the **five** flat `hooks/` rosters" cites **six** anchors, two of which are the opening and closing lines of one docstring on `selftestable_hooks` - a DETECTOR, not a roster - while the file's only real roster, `KNOWN_NO_SELFTEST`, is not cited at all |
| `p14_triage.md:39` | "skips **13 of the 17** hook files" was EXACT for `1dcf430` and is **11 of 17** at HEAD, because the retained live-cap fixes pulled two files into the examined set. Stale as a present-tense claim |
| `p14_new_code_review.md:235` | still reads "Status: TRIAGE REQUIRED, not merged". Triage completed 2026-08-01. Needs a visible correction note, as the plan carries |
| B6 | "CI has never run on any of this session's work" is now **false**: run `30733812757` on `d641da7` went **green on all 14 jobs**, which also means the 2 posix-only mutations Windows cannot run are proven by the ubuntu/macos jobs rather than proven nowhere |

#### RESTORED 2026-08-02 - rows my own re-base splice destroyed

The re-base above replaced a whole section by anchor, and silently removed five rows that
sat inside the replaced range but were not part of what I was replacing. Caught by the
close-out meta-review sweep, which checked that every finding id named in this session still
has a plan row. **The plan's own completeness was broken by a bulk edit to the plan** - the
same class as a `.slice()` that drops findings, committed in the document that records that
class. Restored below with current status rather than re-derived from memory.

| id | sev | status | item |
|---|---|---|---|
| B8 | MEDIUM | **DONE** | Re-test N1's flakiness claim. Done: 6 of 6 integration runs at 30/30, including the after-a-selftest ordering that was blamed. **N1 WITHDRAWN** - the 29/30 was two of my own defects. The round-1 implementer's contrary "29/30 on a clone of baseline" is recorded as UNREPRODUCED rather than quietly dropped |
| C2 | MEDIUM | **OPEN** | **Changes were kept in never-reviewed code.** Of the 5 live-cap fixes retained through the revert, `tools/measure_dispatcher_cost.py`, `skills/consistency-audit/scripts/audit.py` and `.../extract.py` are UNREVIEWED, and `show_your_proof.py` / `hook_health_check.py` are STALE. Green gates on never-reviewed code is this session's own thesis. Schedule an adversarial pass over the retained diff |
| C3 | - | recorded | Freshness is **5 of 35 units reviewed since their last change, 10 UNRESOLVED**; `--release` is correctly red. No action - recorded so the denominator stays visible |
| N2 | MEDIUM | **OPEN** | `skills/consistency-audit/scripts/sources.py:87` silently `continue`s past an oversized file AND skips `idx.files += 1`, so the denominator shrinks with no notice. Its twin at `numbers_match_on_write.py:393` prints an explicit "NOTHING was verified in it" |
| N6 | MEDIUM | **DONE for this session, class OPEN** | A completed workflow's evidence is not recorded until it is in the repo. Rounds 1-2 and the audit run existed only in OS temp; both are now persisted (`p14_cluster1_evidence.md`, `p14_audit_findings.md`). The DURABLE fix - `adversarial-review` persisting results before returning - is still open and lives with B4 |

#### Findings with NO home until now - found by the completeness audit (denominator 56)

| id | sev | owner | item |
|---|---|---|---|
| F-L8 | LOW | phase 4 | The `transcript_util` X6 residual. The main P14 run refuted the X5+X6 finding WHOLESALE; the first run's refuter agreed about the composition but kept a residual - X6 alone is a real surviving mutation, with two killing fixtures supplied. Recorded in `p14_triage.md` section 2a and never given a plan row |
| F-RB | MEDIUM | phase 0, with C1 | **The resume-boundary reconciliation gap.** A resumed Workflow re-ran its lenses instead of replaying them and returned only the second run's results, so a complete-looking denominator silently excluded 42 independent findings. `p14_triage.md` section 4 states it and explicitly says "no row above closes" it - and none did. Belongs with C1 (the gate ledger) because both are "the process left no trace" |

#### Rows that had a severity but no owner - now homed

| id | owner |
|---|---|
| B3 two-round rule | phase 0, alongside D1/D2 - it is a process gate, not a code fix |
| B4 fixture-coverage gate + evidence persistence | phase 0, alongside D1/D2 |
| D1 self-budgeting selftests | phase 0, FIRST - cheapest, and it catches a class already demonstrated twice |
| D2 no-regression-vs-predecessor gate | phase 0, second - the class NOTHING here catches |
| B7 escaping trap | **RESOLVED, not optional.** The audit flagged the "OR accept it as a judgement call" disjunction as the one genuine optional-forever row in P14. Decision: WIDEN the rule to any generated-code path (it has now fired twice - once in a heredoc, once in a Python string literal). Owner: phase 0 with B3/B4 |

#### Corrections to rows written against the reverted code

| id | correction |
|---|---|
| N3 | Said `capped_report.py` is "**2101 lines**, 2.6x the limit and the worst violator". It is **180**. MEASURED: **0 of 36 tracked .py files exceed 800 lines**, so the class has NO live instance today. The row stays HIGH anyway and stays in phase 1 - because the defect was never the line count, it was that **the rule is a roster with no detector**, so it re-breaks silently. The prescribed "split the fixture corpus" fix is withdrawn as moot |
| N4 | Moot as written. Baseline `_max_names` recognises exactly ONE form (module-level `ast.Assign` to a bare `ast.Name` starting `MAX_`), so the asymmetry it describes does not exist. Folded into C1-NEW |
| N5 | Said "`_cap_names` models 12 of Python's 24 binding forms". `_cap_names` does not exist; baseline `_max_names` models **ONE**. The row understated the gap by an order of magnitude in the direction that matters. Folded into C1-NEW |
| N1 | **WITHDRAWN.** Claimed the C1 integration scenario is environment-dependent. Re-tested deliberately: **6 of 6 runs at 30/30**, including the after-a-selftest ordering the dropped refuter blamed. The 29/30 was fully explained by two of my own defects (a `ModuleNotFoundError` in the installed layout, then a 36s selftest against a 25s timeout). Recorded honestly: the round-1 implementer claimed 29/30 on a clone of baseline `1dcf430` and **I could not reproduce it**; most likely that clone inherited an already-modified file |
| "Not started" | Now imprecise. `d641da7` applied two live instances named inside P14 findings (`hook_health_check.py:470`, and the `show_your_proof` tail-window cap) |
| show_your_proof docstring | **Was FALSE and is fixed in this commit.** It claimed the judgement was "written down in `capped_report.SIZE_EXEMPTIONS`" and that the site "is visible" to the guard. Neither is true post-revert. Found by the completeness audit; no gate caught it |


### PART A - the installed-hooks divergence, 2026-08-05. CLOSED except the rows below

Full evidence: `docs/audits/p14_partA_divergence_2026-08-05.md`. Headline: it was **11 shared
files diverging, not 2**; `install.py` was never at fault (the Claude Code surface pointed at
the repo all along); the stale copy ran from **git's** surface, because
`core.hooksPath` was set globally to a dispatcher that pinned
`~/.claude/hooks/pre_push_gate.py` - and `install()` writes its shim from
`os.path.abspath(__file__)`, so the copy that runs `--install` is the copy that gets pinned.
**unbluff had been gating its own pushes with a stale fail-open copy of its own gate since
2026-07-28.**

| id | sev | owner | item |
|---|---|---|---|
| A1 | - | **DONE** | Both-directions diff adjudicated. `read_source_globs`/`is_source` and `PUSH_MAX_TIMEOUT_S` **DISCARDED, not ported**: a 4-case A/B with a live control showed the deny-list covers `.json` AND `.tf` with no declaration, while the glob is blind one extension past whatever was declared. Nothing in the installed copy was worth porting upstream |
| A2 | - | **DONE** | Cause established: two wiring surfaces, two path conventions, nothing reconciling them. Not hand-editing (that came later) and not a second clone |
| A5 | - | **DONE** | Repaired: 22 dispatchers + 3 per-repo shims re-pointed at the repo, 12 stale files deleted, `state/` preserved, suite 25/25, live gate path exercised (`exit 0`) |
| A3 | - | **DONE** | `tools/hook_divergence_report.py` rebuilt from a report that "exits 0 always" into a PROVENANCE gate. Derived roster, both denominators printed, `--selftest` with planted offenders on both surfaces plus negative controls, 3 mutations all CAUGHT, AUX gate (suite 24 -> 25), README updated in the same change. **Historical control: 16 of 16 FOREIGN against the preserved pre-repair artefact** |
| A6 | LOW | **DONE** | Shim templates hardcoded `managed by ~/.claude/hooks/pre_push_gate.py` while exec-ing `{script}`. MEASURED harm: a grep for the stale path matched 22 of 22 correctly-installed dispatchers, so the check written to prove the stale copy was gone reported the opposite. Templated from `{script}`; pinned by a DERIVED `_selftest_shim_self_reference` (discovers templates by shape, prints its denominator); mutation `#A6` CAUGHT |
| **A4** | MEDIUM | **phase 4, SCHEDULED TO BE BUILT** | In-flight-thread hook. The GENERIC version is **declined with reasons** (see the audit doc): "was this output referenced?" is not mechanically decidable - every `Read` that informs an `Edit` would fire, and a hook that nags on correct behaviour gets disabled. The NARROW variant is a real, bounded gap and is scheduled: fire only when a turn ends with an **unadjudicated FAILURE signal** (a tool result carrying a non-zero exit or a `FAIL`/`SURVIVED`/`BLOCKED` marker) and nothing follows it. Mechanically decidable, names the command, matches the measured failure. NOT a twin of `show_your_proof`, which fires on the complementary condition (a success claim with ZERO tool runs) |
| **A8** | MEDIUM | phase 0, with D1-LIMIT | **D1-LIMIT has a THIRD instance and it is already SHIPPED.** `meta_audit_on_stop` is WIRED at 0.70 share and failed its budget at 30.50s vs 17.50s today. An interleaved A/B against an unmodified control showed **12.86s median, 1.0x the 13.30s plan baseline** - the box was at 97% CPU with foreign work. The previously named cases (`fast_test_on_stop`, `pre_push_gate`) are deliberately UNWIRED for this reason; this one is live, so the flakiness ships to users. No invariant weakened: the budget is right and the instrument is wrong. Strengthens the case for CPU time or a calibration probe before any further hook is budgeted on wall clock. **ESCALATED 2026-08-06 - the consequence is bigger than "a flaky selftest".** The post-M1 FULL mutation run came back with **14 of 98 mutations as `HARNESS ERROR: baseline already RED before mutating`** - `hook_health_check` x6, `meta_audit_on_stop` x7, `pre_push_gate` x1. Not one SURVIVED; every one of the 14 was a wall-clock BUDGET failure in the baseline selftest (`hook_health_check` 10.51s of 10.00s, `meta_audit_on_stop` 57.95s of 17.50s). Interleaved A/B with an untouched CONTROL, per this row's own method: **control `capped_report` 1.31s median vs 0.20s baseline = 6.5x; `hook_health_check` 1.6x; `meta_audit_on_stop` 4.0x** - the control inflated MORE than either subject, so the code is not slower and the box was the variable (`Win32_Processor` LoadPercentage **100**, `ollama` holding 2067s of CPU since the previous day, ~44 node hook processes). **So a loaded box does not merely flake one hook - it silently deletes 14% of the evidence base that certifies every other fix in this repo, and it does so while printing `0 SURVIVED`.** A reader checking only for SURVIVED reads that run as healthy. This makes A8 a blocker on the verification loop itself rather than a phase-4 tidy-up |
| A9 | LOW | phase 4 | The state-key divergence reappeared at the INSTALL boundary: repo `_state_key()` normalises to `c:/...`, the old copy hashed `cwd.lower()` with backslashes, so unbluff carried **two** `fasttest-*.json` ledgers. Findings 28/34 fixed inside one program and re-broken across two copies of it. Now moot (one copy), but the class - "a canonicalisation is only canonical within the program that defines it" - has no detector |

### PHASE 1 - the fail-open class fix. TWO of three guards rebuilt, 2026-08-05

The principle, applied once and reused: **fail CLOSED, bounded by a naming convention or a
behaviour rather than by syntax, with an exemption roster carrying a written reason per entry
and a liveness check in BOTH directions.** N recorded exemptions is a healthy design; an
unenumerated shape reported CLEAN is not.

| id | sev | status | item |
|---|---|---|---|
| B2 | HIGH | **DONE** | `transcript_util` twin-guard. Was 4 hardcoded names / 3 line-anchored regexes / 1 non-recursive dir. Now: the 4 names kept as a FLOOR (they catch a bare `def first_text` the behavioural rule misses - measured control C2, which is exactly why the audit said not to delete them) plus a BEHAVIOURAL ceiling (a file touching the transcript's own vocabulary and not importing this module), recursive over the whole repo, `_bound_identifiers` via AST so annotated assignment / lambda / `async def` are all seen. **MEASURED: 5/11 -> 11/11 (controls 5/5, novels 0/6 -> 6/6).** Planted-fixture selftest so mutations bite; denominator printed every run; unreadable files REPORTED, never skipped. Mutations B2a/B2b/B2c all CAUGHT |
| B3 | HIGH | **DONE** | `duplicate_registration_check`. Extensions now REUSED from `hook_health_check._SCRIPT_EXTS` rather than the hardcoded `".py"` - the repo simultaneously believed a `.js` hook both is and is not a hook. `python -m pkg.mod` normalised to a path. Dispatcher detection is behavioural (the AST is asked) instead of a filename substring, and the fan-out list may carry any ALL-CAPS name instead of literally `HOOKS`. Mutations B3a-B3e all CAUGHT |
| **B3-FP** | **HIGH, found by fixing B3** | **DONE** | **Making non-`.py` hooks visible exposed the opposite defect: the guard counted a basename across ALL events and matchers.** On the author's real config it then reported `observe-runner.js` (2 DISTINCT events) and `run-with-flags.js` (13 hits, one shared runner invoked with different flags) as duplicates - about 15 false alarms on a correct config. Shipping the extension fix alone would have produced a guard its owner disables, which is strictly worse than none. Identity is now (script + arguments + event + matcher), split at the script path so launcher flags (`pwsh -NoProfile -File x.ps1` vs `powershell -File x.ps1`) compare EQUAL while `runner.js --alpha` vs `--beta` compare DIFFERENT. Three distinct faults all still caught: variant conflict, identical re-wiring, and direct-plus-dispatcher on one event |
| B3-N | - | **CLOSED - historical note, nothing outstanding** | Recorded as a lesson, NOT as parked work: both defects below were introduced AND fixed within this session, so there is nothing left to build. Stated explicitly because "noted" in a status column is exactly the optional-forever framing this plan exists to catch, and an auditor should not have to guess. Two defects were introduced and caught by fixtures while building B3: the first `_invocation_key` re-split each `args` entry on whitespace, reintroducing findings 21/22 (a path with a space stops ending in `.py`); the second keyed on all non-script tokens, so `-NoProfile` counted as script work and the `.ps1` pair was missed. Both were caught by planted fixtures rather than by review - the argument for writing the fixture before the fix |
| **B1** | **HIGH x4** | **BUILT 2026-08-06 (`f77eefd`). The 4 HIGH are NOT adjudicated closed** | `capped_report` C1-NEW, built against the committed design: classify the OPERATION, not the BOUND. MEASURED - predecessor **38 of 105 with FALSE-POS 1**, C1-NEW **102 of 105 with FALSE-POS 0**, live `hooks/` sweeps clean, selftest **1.291s median of its 12.50s budget** (n=5, 1.275-1.355s, INTERLEAVED against a control - `check_readme_fresh` at 0.091s median vs the 0.099s M1 characterised, i.e. 0.92x, so the box was not loaded. A first single unreplicated reading said 1.08s and under-reported by 20%; the controlled figure is the one that stands. 9.7x headroom either way) (the reverted detector blew the same 25s cap at 36.1s on every installed machine). Split across `hooks/cap_types.py` (clause 1-3 evidence) and `hooks/cap_shapes.py` (the shapes, clauses 4-5, the roster and its liveness check) because one module arrived at **804 lines** - the same live 800-line violation `duplicate_registration_check` hit at 835 and fixed by MOVING code rather than logging it. Full mutation sweep re-run after the cluster: **115 entries, 113 CAUGHT, 2 posix, 0 SURVIVED, 0 HARNESS ERRORS**. **The 4 HIGH stay OPEN** until the adversarial pass runs - a corpus score is not a review, and "green gates on never-reviewed code is the absence of evidence" is this plan's own thesis. See "B1 build findings" below |

#### Source-coverage audit, 2026-08-05 - ONE gap found with no home in this plan

Reconciled `docs/audits/p14_audit_findings.md` (the B5 three-guard audit) item-by-item against
what B2/B3 actually built. `transcript_util`: all 6 blind shapes BUILT and fixtured, plus both
of the audit's structural recommendations (recursive glob, keep the 4 names as a FLOOR).
`duplicate_registration_check`: 6 of the 7 blind shapes BUILT. The seventh had never been
written into this plan at all - the exact failure a defer-grep cannot detect, because the plan
did not mention it.

| id | sev | owner | item |
|---|---|---|---|
| **B3-P** | **MEDIUM** | **DONE 2026-08-06** | **`settings_layers()` does not read plugin `hooks.json` files, so hooks declared by plugins are invisible to the duplicate audit.** MEASURED on this machine 2026-08-05: **7 plugin `hooks.json` files exist and 6 declare real events** - `hookify` (PreToolUse, PostToolUse, Stop, UserPromptSubmit), `security-guidance` (PostToolUse, SessionStart, Stop, UserPromptSubmit), `posthog` (PreToolUse, SessionEnd), `ralph-loop` (Stop), and two output-style plugins (SessionStart). `settings_layers()` returns exactly 4 paths, none of them a plugin. A hook double-wired between a plugin and `settings.json` therefore reports CLEAN - the same non-extraction-reads-as-non-duplication premise B3 just fixed for extensions, one layer up in the LAYER roster rather than the EXTENSION roster. Fix belongs with the other roster-shaped checks because it is the same shape: derive the layer list from the filesystem instead of listing it. **CORRECTION 2026-08-06, before any code was written - the premise above is WRONG in the direction that would have produced a false-alarm guard.** Two measurements: (1) **`~/.claude/settings.json` declares `enabledPlugins = {posthog@claude-plugins-official, plugin-dev@claude-plugins-official}` - only TWO plugins are enabled, and only ONE of them (`posthog`) has a `hooks.json` at all.** The other six files (`hookify`, `security-guidance`, `ralph-loop`, `claude-security`, two output-style) sit in the marketplace cache belonging to DISABLED plugins, so their hooks never fire. "6 declare real events" counted files on disk, not wirings in effect. A fix that globbed `plugins/**/hooks.json` would have injected six plugins' worth of phantom wirings and reported them as duplicates against `settings.json` - **B3-FP repeating exactly**, and B3-FP's own lesson is that a guard which false-alarms on a correct config gets disabled, which is strictly worse than none. (2) `~/.claude/hooks/hooks.json` looked like a large missed layer (21 commands, settings-shaped, `$schema` and all) but is **NOT** one: it shares **0 of 30** command strings with `settings.json`, and `hook_health_check`'s own SessionStart line this session reported "30 hook commands verified" - i.e. exactly the `settings.json` set. It is ECC's source template that gets installed INTO settings.json, not a layer Claude Code merges. Adding it would have double-counted every ECC hook. **So the live exposure is ONE enabled plugin, not seven files.** The general fix is unchanged and still right - derive layers rather than list them - but it must derive from the `enabledPlugins` AUTHORITY plus the filesystem, never from the filesystem alone, and the negative controls (a disabled plugin, a reference-schema file) are the load-bearing fixtures. **BUILT 2026-08-06** as `hooks/hook_layers.py` (enabled-plugin resolution + `settings_layers`, own selftest, suite 26 -> 27). Regression test written FIRST and watched FAIL ("a hook wired by an ENABLED PLUGIN and by settings.json was invisible \|\| (nothing reported)") before any fix existed. Matching is on PATH COMPONENTS, not substrings, and not on a known directory layout - the two layouts on one machine already differ (`plugins/cache/<market>/<name>/<version>/` vs `plugins/marketplaces/<market>/plugins/<name>/`), so encoding either would be a roster that breaks on the third. LIVE: `settings_layers()` 4 -> 5 paths, `2 enabled plugin(s), 7 hooks.json on disk, 1 merged as a layer`, live config still reports CLEAN (no false alarm). Mutations B3Pa (disabled plugins count as enabled), B3Pb (substring matching), B3Pc (layers not appended) all CAUGHT, and all 11 pre-existing `duplicate_registration_check` mutations still CAUGHT. **Two defects of my own, both caught by the machinery rather than by reading:** (1) the change pushed `duplicate_registration_check.py` to **835 lines - the first live violation of the 800-line rule in the repo**, which is N3's exact complaint ("the rule re-breaks silently"), so `settings_layers` was MOVED rather than the violation logged (792 / 278 now); (2) that move split the `SETTINGS` authority in two - the selftest patched the local alias while `settings_layers` read `hook_layers.SETTINGS`, so `main()` audited the REAL config and printed nothing. **That is A9's class exactly** ("a canonicalisation is only canonical within the program that defines it") reappearing at a module boundary I had just created. Fixed by resolving `hook_layers.SETTINGS` at call time, which is the contract `audit()`'s docstring already stated. The anchor-drift gate built an hour earlier caught the moved anchor in 0.087s |
| B3-S | LOW | **DONE** | The `.sh` blind shape was fixed by the `SCRIPT_EXTS` reuse but had **no fixture**, so it was working-by-accident rather than pinned. Fixture added (`bash x.sh` + `sh x.sh`) in the same pass that found this |

#### SHIP GATE STATUS, verified 2026-08-05 - v1.3.1 must NOT ship

> **SUPERSEDED 2026-08-06 by the RE-SCOPED ship gate.** The zero-HIGH gate this section
> enforces was retired by decision on 2026-08-06. Everything below remains TRUE as arithmetic -
> the 11 HIGH are still open and still counted - but "11 HIGH open" no longer means "does not
> ship". The current gate, its rule, and the SHIP-BLOCKING / V1.4-BACKLOG classification of all
> 21 open HIGH are in **"RE-SCOPED SHIP GATE, 2026-08-06"** at the end of this file. Read that
> one. This section is kept for the arithmetic and the two-accounting-systems warning, both of
> which the re-scope does not change.

Mechanically re-counted after this session's changes, because the ship gate is the one number
nobody should take on trust:

- The work-order table's 12 rows sum to **11 HIGH / 44 total**, matching the stated merged
  backlog exactly. (A prior audit caught this summing to 43 against a stated 44; it stays fixed.)
- **All 11 HIGH are still OPEN.** `capped_report` 4, `mutation_check` 2, `run_selftests` 2,
  `pre_push_gate_selftest` 2, `meta_audit_on_stop` 1. **This session closed none of them** -
  B2 and B3 belong to the B5 guard-audit family, which is tracked by the phase order, not by
  the 44-row work-order table, and `transcript_util`'s work-order row carries 0 HIGH.
- Therefore **zero-HIGH is not met and v1.3.1 does not ship.** Nothing in this session's rows
  should be read as moving the release closer to shippable; they move MEDIUM/LOW class work
  and one HIGH-severity live defect that was never in the backlog (the installed-hooks
  divergence) off the board.

**Two accounting systems coexist and must not be conflated:** the 44-finding work-order table
(from the P14 review plus the first-run triage) and the ~15-finding fail-open class family
(from the B5 guard audit). B2/B3 severities are assigned within the class family. Recorded so a
future reader does not add the two HIGH counts together or assume one subsumes the other.

**RE-COUNTED 2026-08-06, after commits `6807121` (M1), `cb1b600` (B3-P) and `7d789c3`
(score_corpus).** The paragraph above is stamped to the 2026-08-05 session; this is the current
statement:

- The work-order table still sums to **11 HIGH / 44 total** across 12 rows, mechanically
  re-counted today. Unchanged.
- **All 11 HIGH are STILL OPEN, and the 2026-08-06 session closed none of them either.**
  `capped_report` 4 (only B1's mandated FIRST MOVE - the corpus measurement - was done; the
  detector is not built), `mutation_check` 2 (M-M12 was MEASURED and given a row, not fixed),
  `run_selftests` 2 (gained two AUX-gate registrations, which close no finding),
  `pre_push_gate_selftest` 2, `meta_audit_on_stop` 1. **Zero-HIGH is not met; v1.3.1 still does
  not ship.**
- **A THIRD bucket now exists and must not be merged into either of the two above:** the
  **source-coverage findings of 2026-08-06** - `SC1` (measurement tools exempt from every gate)
  and `SC2` (mutation scratch-tree leak). They are new findings from today's audit, present in
  neither the 44-row table nor the B5 class family. Counting them into either would corrupt the
  ship-gate arithmetic in the exact way this note exists to prevent.
- **`M-M12` is NOT a new finding and adds nothing to any total.** It is one of the nine already
  counted in work-order row 2 (`tools/mutation_check.py`, 2 HIGH / 9); today it was merely given
  an explicit row instead of remaining an unnamed member of that nine.

#### Meta-review findings, 2026-08-06 - both PROBED out of this session's own work, both FIXED

Neither was visible by reading, and neither would have been caught by any test that existed.
Both were found by adversarially probing the guards built this session rather than by reviewing
them, which is the difference the meta-review keeps paying for.

| # | severity | what | status |
|---|---|---|---|
| **MR-a** | **HIGH** | **The anchor gate could be fully disarmed with every test green - finding #16 reproduced inside the guard written to prevent that class.** Changing `if problems:` to `if False:` in `check_mutation_anchors.main()` meant a drifted anchor could no longer fail the gate, while its own `--selftest` printed **SELFTEST OK** and BOTH M1 mutations still reported **CAUGHT** - because every test exercised `anchor_audit()` and nothing exercised the gate's own DECISION. The deliberate choice to keep the live audit out of the selftest (correct, it prevents self-triggering) removed the last thing that touched `main()`. | **FIXED**: decision extracted to a pure `verdict()` and every branch asserted - clean, drifted, zero-denominator, and the multi-match note on BOTH paths. This is exactly the pattern `check_readme_fresh.verdict()` already documents ("Pure, so the selftest can exercise EVERY branch... whose mutation therefore came back SURVIVED"); it simply was not applied here. Mutation `#MRa` CAUGHT. Re-probed after the fix: disarming the decision now goes RED |
| **MR-b** | **MEDIUM** | **`hook_layers` had its own false-alarm mode - the very thing it was written to avoid.** One ENABLED plugin present in BOTH the `plugins/cache/...` and `plugins/marketplaces/...` trees resolved to 2 files and merged BOTH, so the same hook was counted once per copy and a correct config would be reported as a DUPLICATE. Latent on this machine (`posthog` exists only in the cache) but real, and no fixture covered it. | **FIXED**: one deterministic copy is merged and the ambiguity is REPORTED (`report["ambiguous"]`) rather than resolved silently - which copy Claude Code loads is not knowable from here, so guessing without saying so would be the fail-open this module replaced. Fixture added for both halves. Mutation `#MRb` CAUGHT |

Also checked and clean: no soft-defer/optional-forever language remains live; the three rows
added today (`M-M12`, `SC1`, `SC2`) all carry real phase assignments; the work-order table still
sums to 11 HIGH / 44 total and **this session closed none of the 11**.

**Known limitation, recorded not fixed:** `enabledPlugins` is read only from the USER settings
file. A project-scope `.claude/settings.json` declaring it would be ignored (probed: yields 0
layers). That errs toward MISSING a layer rather than inventing one - the safe direction for a
duplicate guard - and whether Claude Code honours `enabledPlugins` at project scope is not
established here. Worth confirming before B3-P is called complete.

#### Meta-review findings, 2026-08-05 (post-commit `0c0dfb9`)

| id | sev | owner | item |
|---|---|---|---|
| **M1** | **MEDIUM** | **DONE 2026-08-06** | **A mutation anchor can be silently disarmed by an unrelated fix, and only a 25-minute FULL run notices.** Measured today: the B3 entry-encoding change broke `#20/23`'s anchor, making that mutation UNRUNNABLE. It surfaced as `HARNESS ERROR` - correctly, not silently - but ONLY on the full run; every filtered run reported clean, and the full suite is CI-only. My response was to re-anchor it and dry-check all 96 anchors BY HAND, once. That is an instance fix: nothing stops the next edit doing the same. **Durable version: an AUX gate that validates every mutation anchor against current sources - it ran in under a second in this session's scratchpad, against a 25-minute full run.** `mutation_check` already validates anchors internally (the "Validate the ANCHOR even when the mutation will be skipped" path); this exposes that as a standalone cheap gate. Note it takes the suite 25 -> 26 and turns `readme-fresh` RED, so the README transcript updates in the SAME commit. **BUILT 2026-08-06** as AUX gate 26, `tools/check_mutation_anchors.py`. ONE implementation, not a twin: the rule is `mutation_check.missing_anchors()` / `anchor_audit()` and `run()` was switched onto the same function. **0.087s median**, measured interleaved against a CONTROL (`readme-fresh`, 0.099s median, 5 rounds each), so the claim is not another uncontrolled wall-clock reading of the kind A8 is about; it is FASTER than an existing cheap gate. **The sweep it stands in for is characterised as ~25 minutes above, and that figure is NOT re-asserted here: an earlier draft of this row said "~50-minute" from an impression formed while waiting on runs, with no controlled measurement behind it - the exact thing A8 exists to forbid, written two sentences after applying the rule correctly to 0.087s. The honest statement is that the full sweep is minutes-to-tens-of-minutes, grows with every mutation added, and is load-sensitive; if a number is ever needed, measure it against a control first.** Prints the denominator every run (**99 anchors across 98 entries in 22 files as measured at build time on 2026-08-06; it necessarily GROWS with every mutation added, so this figure is a timestamped observation and not a current claim** - the live number is whatever the gate prints); fails CLOSED (an unreadable unit is a problem, never a skip, and keeps its anchors in the denominator). Watched FAIL on a real drifted anchor in the live tree, not only on fixtures: breaking `no_regression`'s `#D2b` anchor produced `FAIL - 1 of 97 ... tools/no_regression #D2b` at exit 1, then restored. Mutations M1a/M1b both CAUGHT. README updated in the same commit |
| M2 | LOW | phase 4 | **The gate ledger has a denominator of 1.** `docs/audits/gate_runs.json` records only `run_selftests` across 127 entries. `mutation_check` - run four times on 2026-08-05 and the evidence base for every fix claim in `0c0dfb9` - writes nothing to it, so "which gates actually ran" is answerable for one gate and unverified for the rest. This is the C1 gate-ledger row's remaining half: gates leave traces, but only one gate does |
| M3 | LOW | phase 4 | Two files are within 5% of the 800-line rule: `hook_health_check.py` **790** and `duplicate_registration_check.py` **760** (about 100 of those added on 2026-08-05). No file is over today, so there is no live violation - recorded so the next addition to either is a deliberate decision rather than the edit that quietly crosses the line. `pre_push_gate` already had to split its selftest out for exactly this reason |
| **M-M12** | **MEDIUM** | **phase 2, with the `mutation_check` remainder** | **Anchor UNIQUENESS, given an explicit row 2026-08-06 because it did not have one.** `mutation_check.py` and now `check_mutation_anchors.py` both state in shipped comments that this is "scheduled as M-M12 in cluster 2", and `p14_audit_findings.md` confirms the general fix is absent - but the only mention anywhere in THIS plan was a parenthetical at the cluster-1 line about `transcript_util` #13. Cluster 2 is a UNIT-level work-order row (`tools/mutation_check.py`, 2 HIGH / 9 total), so M-M12 was covered only by being one of an unnamed nine. That is the same shape the source-coverage audit caught as B3-P: a claim of "scheduled" that a defer-grep cannot verify because no row says it. The defect: anchors are validated by PRESENCE, so a `find` matching more than once silently mutates the FIRST site via `str.replace(..., 1)` - which may not be the intended one, making the mutation prove something about code nobody meant to test. **LIVE INSTANCE, measured 2026-08-06** by the M1 gate on its first run: `duplicate_registration_check #B3a` matches its source **2x**. M1 deliberately REPORTS the multi-match count without failing on it, so this row arrives already measured; enforcing it there would have been doing this work unlabelled |
| **SC1** | **MEDIUM** | **phase 2, with the `mutation_check` remainder** | **The measurement-tool exemption is a HOLE, and `score_corpus` was only its first instance.** `NOT_A_GATE` exempts tools from every gate on the grounds that they are "measurement, no pass/fail opinion of their own". `score_corpus.py` was exempted on exactly that reasoning and spent an unknown period double-counting every negative control, printing a denominator 23% too large in the tool that grades the ship-blocker (fixed 2026-08-06, `7d789c3`). **That fix was an INSTANCE fix.** Three tools remain in `NOT_A_GATE` with no `--selftest` at all: `compare_delivery_gate.py` (139 lines), `measure_dispatcher_cost.py` (145), `make_hook_screenshot.py` (100). The first two exist specifically to **produce numbers that are quoted in this plan**, so a defect in either corrupts plan figures exactly the way `score_corpus` corrupted B1's - silently, and in a tool nothing verifies. (`mutation_check.py` is also in `NOT_A_GATE` without a selftest, but it already has a home as the phase-2 verifier-of-verifiers row, so it is covered and not counted here.) The general fix is the same shape as every other roster in this repo: a tool that produces a number quoted anywhere must carry a selftest for its own arithmetic, and the exemption list must state which of those two categories each entry is in rather than lumping "produces numbers" together with "generates a PNG". **Found by the source-coverage audit 2026-08-06: the class had NO row - only the instance narrative.** **SECOND INSTANCE, same day, found by being asked "am I missing anything":** `score_corpus.py` also carried `REPO = r"C:\Users\ammar\Downloads\unbluff"`, a hardcoded absolute path. Harmless while it was an exempt measurement tool nobody but its author ran - and a **defect the moment this session promoted it to a gate**, because `run_selftests` runs in CI on Linux and macOS where that path does not exist. Reproduced before fixing: `exit 1, ModuleNotFoundError: No module named 'cap_spelling_corpus'`. Fixed (derived from `__file__`, verified from a relocated copy), pinned by a structural selftest assertion and mutation `#B1p`. **The general rule this yields, and the thing SC1 must build: promoting a tool to a gate CHANGES WHERE IT RUNS, so every machine-specific assumption inside it becomes a defect at that instant rather than gradually.** A gate must therefore be checked for machine-specific absolute paths as part of promotion, not after CI goes red |
| **SC2** | **LOW** | **phase 4** | **`mutation_check` leaks its scratch trees, and swallows the reason.** `shutil.rmtree(scratch, ignore_errors=True)` in `run()`'s `finally` is a literally-swallowed error in the harness that certifies every other fix. **MEASURED 2026-08-06: 22 orphaned `unbluff-mut-*` directories in `%TEMP%`, 16 MB total, dated Jul 31 through Aug 5** - so it leaks persistently across runs and days, not once. Most scratches DO get removed, so this is a partial failure (almost certainly Windows file-locking on a just-executed `.py`), which is the kind that never announces itself. `ignore_errors=True` is the right call for not failing a green run on a cleanup problem - but "do not fail" and "do not say" are different decisions, and this conflates them. Fix: retry briefly, then REPORT what could not be removed and how many, rather than discarding the exception. Also worth sweeping stale `unbluff-mut-*` at startup so the footprint is bounded. **Found by the source-coverage audit 2026-08-06: no row existed. `D1-FIND-4` covers leaked sleeper PROCESSES from the kill-verification selftests, which is a different leak in a different unit** |

#### B1 design brief - read this BEFORE writing any code

The brief's inverse rule ("flag every load of a cap-named constant not passed to
`capped_report.keep()`/`render()`") is the right SHAPE - it is bounded by the ~6-14 real cap
sites rather than by Python's grammar - but it is **not sufficient on its own**, and the corpus
proves it. Measured against `tests/cap_spelling_corpus.py` (125 entries: **96 must_flag, 29
must-stay-quiet**), the naive inverse rule flags these NEGATIVE controls:

- `neg_max_used_for_retries` - `for _ in range(MAX_RETRIES)`
- `neg_retry_while` / `neg_poll_while` / `neg_depth_while` - `while n < MAX_WAIT_SECONDS`
- `neg_max_used_as_loud_rejection` - `if len(rows) > MAX_ROWS: raise ValueError(...)`
- `neg_scalar_slice_rostered` / `neg_size_skip_rostered` - byte and size windows
- `neg_bound_exemption_collection` - the existing `BOUND_EXEMPTIONS` cases

All of those are CORRECT code. So the real problem is not "find the cap loads" - that part is
easy and genuinely unbounded-proof. The real problem is **discriminating a silent truncation of
a REPORTED LIST from a resource bound or a loud rejection**, and that is where both previous
rounds died.

Constraints the rebuild must respect, each already paid for:

1. **The predecessor floor is 31 of 96, measured today** by `tools/no_regression.py`
   (`predecessor f3ebc8f0 saw 31 of 96, working tree sees 31`). Falling below it is a
   detection regression and the gate will block it - which is the gate working.
2. **The corpus is BIASED toward the reverted detector**, which wrote most of it and scores
   96/96 where the baseline scores 31/96. **Only the 14 scalar-suffix entries are
   baseline-verified.** Derive new entries from the PREDECESSOR's capabilities too, or the
   grader keeps rewarding the design that was reverted.
3. **A `raise` is loud and therefore fine**; a `break`, a slice, or a `return` that quietly
   shortens a list that is later printed is the defect. Any rule that cannot tell those apart
   will either fail open or bury the user in false positives.
4. Selftest must stay inside `hook_health_check`'s 25s cap (`selftest_budget`), which the
   reverted detector blew at 36.1s - a shipped defect on every installed machine, not a CI
   symptom.
5. The 8 acceptance criteria in "Acceptance criteria for C1-NEW" above are each a real defect
   from the reverted version; re-read them before starting.

**Recommended first move:** do NOT start by writing a detector. Start by scoring the naive
inverse rule against all 125 corpus entries to get its true false-positive set, then design the
discrimination against that measured set. `tools/score_corpus.py` already
does the harness half.

**FIRST MOVE DONE 2026-08-06 - and it justified itself twice over.**

*The grader was broken.* `score_corpus.py` added `corpus.NEGATIVE_CONTROLS` to the negatives it
had already filtered out of `corpus.ENTRIES`. They are not "extra" - `MUST_FLAG +
NEGATIVE_CONTROLS == ENTRIES == 125` - so **every negative control was scored TWICE**. The tool
whose docstring reads "printing the DENOMINATOR" printed `96 positives + 58 negatives = 154
corpus entries` for a corpus of 125: inflated 23%, with every false-positive count doubled. It
survived because measurement tools were exempted from the gates (`NOT_A_GATE`) on the grounds
that they have "no pass/fail opinion of their own" - but whether a scorer can count its own
corpus is a pass/fail question entirely independent of the guard being scored. **Fixed,
de-duplicated by entry NAME (so a genuinely new control added only to `NEGATIVE_CONTROLS` is
still picked up rather than silently dropped), given a `--selftest`, promoted from `NOT_A_GATE`
to AUX gate `corpus-scorer` (suite 27 -> 28), and pinned by mutation `#B1s`.** This is the
verify-the-verifier lesson again: had B1 been graded before this was found, every
false-positive number in the design would have been twice its true value.

*The measured set is bigger than the brief's reasoned one.* Naive inverse rule, scored against a
correct denominator: **CAUGHT 67 of 96 positives, FALSE-POS 11 of 29 negatives** (well clear of
the 31/96 predecessor floor, so the floor is not the binding constraint - the false positives
are). The brief above predicts 8 negative controls by reasoning; the measurement finds **11**.
The three it did not name are `neg_read_derived_input_window_rostered`,
`neg_scalar_shrink_while`, and - most instructive - **`neg_collection_cap_in_the_approved_
function`**, a cap inside the sanctioned function that the rule flags anyway. The
discrimination must be designed against these 11, not the 8.

#### C1-NEW discrimination design, 2026-08-06 - designed against the MEASURED set

> **STAMP, added by the 2026-08-06 consistency audit AFTER B1 was built.** Every corpus
> figure in this section and in the B1 design brief above - "125 entries", "96 must_flag",
> "31 of 96", "67 of 96", "FALSE-POS 11 of 29", "only the 14 scalar-suffix entries are
> baseline-verified" - was measured BEFORE the corpus was widened, and is stale as a
> present-tense claim. Current figures: **135 entries = 105 must-flag + 30 negative
> controls**; predecessor **38 of 105 with FALSE-POS 1**; C1-NEW **102 of 105 with FALSE-POS
> 0**; **21** entries baseline-verified (14 scalar-suffix + 7 module-scope), not 14. The
> REASONING in this section is unchanged and still correct - it is the arithmetic that moved
> when the second predecessor-derived family landed. Stamped rather than rewritten, because a
> plan that quietly edits its own history is the same defect as a gate that quietly narrows.
>
> One figure here is not merely stale but was always about something else: **"CAUGHT 67 of 96,
> FALSE-POS 11 of 29" describes the NAIVE INVERSE RULE**, a hypothetical scored to design
> against. It was never the shipped guard, and "beat the 11 false positives" is therefore not
> the predecessor's record. **The shipped predecessor scores 31 of 96 with ONE false positive**
> (`neg_scalar_slice_rostered`), re-measured 2026-08-06. Recorded because the brief's binding
> constraint was read from the wrong baseline, and 3 of those 11 are unwinnable by
> construction - see B1-CEILING.

**The reframing, and it is the whole design.** Scoring the naive inverse rule did not just give
a false-positive set, it exposed that the rule *itself* still contains a spelling taxonomy. All
**29** of its misses are cap-SPELLING variants: the bound arriving as an import
(`from_import_bound`, `star_import_*`, `imported_bound_behind_a_plain_alias`), a class attribute,
a dict value, a walrus, a tuple/list target, a function-local, a lowercase parameter, or a bare
integer literal (every `int_*` entry). "Flag every load of a cap-NAMED constant" smuggles the
111-spelling problem back in through the definition of *cap-named* - the exact design that
failed open, wearing an inverse-shaped hat.

**So do not classify the BOUND at all. Classify the OPERATION on the reported collection.** The
ways to silently shorten a sequence in Python are grammar-closed and few - slice, `break` out of
an accumulation loop, `itertools.islice`/`takewhile`, `del seq[n:]`, `sorted(...)[:n]`, a
comprehension index guard, `zip(xs, range(n))` - roughly eight shapes, bounded by the grammar
rather than by anyone's imagination. Once the operation is the subject, the bound's spelling
becomes irrelevant, and all 29 misses are recovered for free rather than one taxonomy entry at
a time.

**The rule.** Flag a site when ALL five hold:

1. **A shortening operation** from the closed set above applies to a **collection** (not a
   `str`/`bytes` scalar, not a counter, not a clock).
2. The collection is **REPORTED** - it reaches a `return`, a print, or a rendered message.
3. The collection **derives from caller-supplied data** - a parameter, or an accumulation over
   one - rather than from I/O the function performed itself.
4. The shortening is **SILENT**: no `raise` on the bound path, and the true total is not
   reported alongside (the sanctioned `keep()`/`render()` path).
5. The site is **not exempted** (`BOUND_EXEMPTIONS`).

**Verified against all 11 measured false positives** - each is killed by a specific clause, not
by a name exception:

| negative control | killed by |
|---|---|
| `neg_max_used_for_retries`, `neg_retry_while`, `neg_poll_while`, `neg_depth_while` | (1) bounds a loop counter or a clock; no collection is shortened |
| `neg_scalar_slice_rostered`, `neg_scalar_shrink_while` | (1) the target is `str`, not a collection |
| `neg_max_used_as_loud_rejection` | (4) it `raise`s - loud, therefore fine |
| `neg_size_skip_rostered` | (1) `continue` keyed to `getsize(p)`, a property of the ITEM; it filters input, it does not truncate output |
| `neg_read_derived_input_window_rostered` | (3) `lines` comes from `handle.read()` inside the function - a read WINDOW, not a truncation of data the caller already had |
| `neg_bound_exemption_collection`, `neg_collection_cap_in_the_approved_function` | (5) roster only |

**Clause (3) is the load-bearing and least obvious one.** `lowercase_cap_parameter` (must flag)
and `neg_read_derived_input_window_rostered` (must stay quiet) BOTH take a cap as a parameter
with a default, so "the cap is a parameter" discriminates nothing - provenance of the shortened
collection is what separates them. Needs simple intra-function dataflow, not type inference.

**Three honest risks, recorded before any code is written:**

- **The last two negatives are structurally IDENTICAL to true positives** (`out = []`, append in
  a loop, `break` at a cap, `return out`). No structural rule can ever separate them, so an
  exemption roster stays load-bearing. Per B3's lesson that roster must be *verified*: an
  exemption that stops being needed has to be REPORTED, or it rots into cover for the next
  thing added. `transcript_util` already does exactly this with its used-check.
- **Clause (1)'s collection-vs-scalar test is where new false positives will appear.**
  `text = fh.read()` is a scalar; `problems: list[str]` and `out = []` are collections. Tractable,
  but it is a heuristic and must be scored, not assumed.
- **Grade every iteration with `tools/score_corpus.py`** against the full 125 and against the
  predecessor floor. The corpus is still biased toward the reverted detector (only the 14
  scalar-suffix entries are baseline-verified), so entries derived from the PREDECESSOR's
  capabilities are still owed before any score above 31/96 can be read as real progress.

**Exit condition for P14:** every row above closed to the severity bar, the dropped
candidate adjudicated (done), the recovered set triaged and merged (done), full mutation
suite re-run after EACH cluster (not just at the end - P13 proved three times that a fix
here disarms another finding's test while the suite stays green), CI green on all 14 jobs,
and `check_review_freshness --release` showing zero UNRESOLVED units.

#### B1 build findings, 2026-08-06 - a FOURTH accounting bucket

These are new findings produced by BUILDING C1-NEW. They belong to neither the 44-row
work-order table, nor the ~15-finding fail-open class family, nor the 2026-08-06
source-coverage findings (SC1, SC2). Counting them into any of the three would corrupt the
ship-gate arithmetic in exactly the way the note above exists to prevent.

| id | sev | owner | item |
|---|---|---|---|
| **B1-CEILING** | **MEDIUM** | **DONE 2026-08-06** | **The corpus asks the same question twice and demands different answers, so its headline denominator was never reachable.** MEASURED: **3 groups** of entries BYTE-IDENTICAL in `(rel_path, source)` that disagree on `must_flag` - `scalar_slice_without_a_roster_entry`/`neg_scalar_slice_rostered`, `size_skip_by_getsize`/`neg_size_skip_rostered`, `read_derived_input_window`/`neg_read_derived_input_window_rostered`. `score_corpus` plants ONE entry per fresh temp dir, so `(rel_path, source)` is the COMPLETE input a guard sees; no deterministic guard can satisfy both halves of any pair. **The ceiling is CAUGHT 102 of 105 at zero false positives, or 105 of 105 at 3+ false positives - never both** (figures stamped 2026-08-06; they move with every corpus addition, and `score_corpus` prints the live pair). This directly CORRECTS the C1-NEW design brief above, which maps those three negatives to clauses (1), (1) and (3) as though killing them were free: each of those clauses also silences the must-flag twin. The design's MECHANISM was right; its accounting was not, and the brief's "beat the false positives" target counted 3 unwinnable ones. **General fix, not an instance fix:** `score_corpus.contradictions()` DERIVES the groups and `main()` prints the reachable CEILING beside the raw denominator on every run, with planted fixtures in both directions (a real pair is reported; entries differing by path or agreeing on verdict are not) and mutation `#B1c`. Same class as that tool's double-count defect and as SC1 - a measurement tool exempted from the gates for having "no pass/fail opinion", while reporting a number nobody could trust. **The corpus itself is NOT edited**: it is APPEND-ONLY by contract, and deleting an entry or flipping a `must_flag` is the exact silent narrowing that contract exists to prevent |
| **B1-SCOPE** | **MEDIUM** | **phase 2, with the verifier-of-verifiers** | **The cap guard sweeps `hooks/` only; `tools/` has never been swept by anything.** The predecessor globs `hooks/*.py`, so C1-NEW kept that scope deliberately - widening it is a scope change, not part of B1, and `no_regression` must compare like with like. MEASURED by pointing the new detector at `tools/`: **4 sites**. **ADJUDICATED, and the headline is that the GUARD is not ready for that scope, not that `tools/` is dirty** - 1 plausibly real, 2 false positives of C1-NEW itself, 1 not adjudicated: (a) `check_review_freshness` `json.dump(history[-500:], ...)` silently drops ledger entries past 500 with no notice - plausibly REAL and adjacent to M2's gate-ledger row; (b) `hook_divergence_report` `"command": cmd[:200]` - a string truncated for display as a DICT VALUE, a FALSE POSITIVE, because the message rule recognises `%`-format, f-string and concatenation contexts and not this one; (c) `no_regression` `positives[:_SAMPLE]` - an 8-entry CALIBRATION sample that feeds a score and is never reported, a FALSE POSITIVE; (d) `mutation_check` - NOT adjudicated and NOT counted as real. **`skills/` and `scripts/` are also unswept and are NOT in this denominator, which is `tools/` alone** |
| **B1-C2FLOW** | **MEDIUM** | **phase 2, with B1-SCOPE** | **Clause 2 does not follow flow through an assignment.** `sample = xs[:N]` followed by a use that never reports `sample` reads as a reported cap, because the clause inspects the immediate expression context only. MEASURED effect on `hooks/` today: **none** - 0 false positives on the live sweep, 29 of 29 negative controls clean - but it is the dominant false-positive source the moment the scope widens, and it is the mechanical reason B1-SCOPE is a separate build rather than a one-line glob change. Fix is a small intra-function reaching-use pass: a DISPLAY site counts as reported only if the shortened value reaches a `return`, a `print`, or a name that does. Recorded with its measurement rather than folded into B1, because a rule that changes what counts as REPORTED must be scored against the corpus and mutation-covered like every other clause - doing that unlabelled inside a scope change is how cluster 1 reached 2,101 lines |
| **B1-WAIVER** | - | **DONE 2026-08-06** | `tests/noregress_waivers.py` carries its first entry: `hooks/capped_report.py / scalar_slice_without_a_roster_entry`. The predecessor detects it; C1-NEW does not, because clause 1 correctly reads `text = fh.read()` as a str. Its byte-identical twin `neg_scalar_slice_rostered` is the predecessor's single false positive, so the pair is unsatisfiable and the two guards simply took opposite halves - 1 unreachable positive traded for 0 false positives. `no_regression` prints the full reason on every run, and the waiver goes STALE and BLOCKING the moment the corpus stops contradicting itself, which is the correct trigger to revisit it |
| **B1-COUNT** | - | **correction, 2026-08-06** | Commit `f77eefd`'s message says "11 new mutations". MEASURED by parsing the table at `02bfb8b` and diffing ids: **10 genuinely new, plus 1 MOVED** - `capped_report #B8` became `cap_shapes #B8` when the detector moved, so it was re-anchored rather than added. Corrected here rather than by amending, and recorded because a mutation count is one of the numbers this plan quotes as evidence. The wrong figure was caught by the adjudicating parser rejecting its own expected denominator, not by review |

**Counts that MOVED on 2026-08-06 and must not be quoted stale**

- selftest suite: **28 -> 30** (`hooks/cap_shapes.py` and `hooks/cap_types.py` each carry one).
  `readme-fresh` went RED first and the README was updated in the same commit, as M1's was.
- mutation entries: **105 -> 116** (11 new, 1 moved). Anchors: **117 across 116 entries in 27 files**.
- corpus: **125 -> 135** entries = 105 must-flag + 30 negative controls, after a second
  predecessor-derived family (7 caps OUTSIDE any function). Every one of the previous 125
  wraps its cap in a `def`, so a rebuild that only looks inside functions loses all 7 while
  every gate prints parity - MEASURED with a control, an intermediate build was blind to
  **7 of 7** while the predecessor caught 7 of 7.
- `no_regression` unit population: **27 -> 29** units, still 1 with a corpus.
- `check_review_freshness`: two more UNREVIEWED units, so the ratio gets **worse**, not
  better, until the adversarial pass runs. Stated because a build that adds guard code
  without adding review coverage moves that denominator in the wrong direction by default.

**Ship gate, restated after this session.** All 11 HIGH remain OPEN and **v1.3.1 still does
not ship.** B1 being BUILT closes none of them: `capped_report`'s 4 HIGH are adjudicated by
an adversarial pass over the new code, not by a corpus score. `mutation_check` 2,
`run_selftests` 2, `pre_push_gate_selftest` 2, `meta_audit_on_stop` 1 are untouched by this
session.

#### Close-out audit findings, 2026-08-06 - the completeness audit found a REINTRODUCED defect

The consistency audit's findings are in `docs/audits/consistency_2026-08-06_b1.md`. The
completeness audit found something the corpus structurally could not:

| id | sev | owner | item |
|---|---|---|---|
| **B1-AC2** | **HIGH, found by the close-out audit** | **FIXED 2026-08-06** | **C1-NEW REINTRODUCED acceptance criterion 2 - "a callee renamed by assignment must still resolve" - and scored 100 of 103 anyway.** `_import_aliases` resolved `import x as y` and `from x import y as z` but NOT `take = itertools.islice`, so `list(take(xs, MAX))` was invisible. Found by PROBING the 8 acceptance criteria directly rather than by reading the code or trusting the score: every fixture and every one of the 132 corpus entries renamed a callee by IMPORT, so the import path was covered and the assignment path was blind **with the corpus score completely unmoved**. A corpus cannot see a shape it has no entry for, and a score that does not move is not evidence that nothing broke - which is the same lesson as D2's "no gate detects a fix that REMOVES detection", one level up: no gate detects a fix that never ADDED the detection its acceptance criteria required. Fixed by resolving assignment renames and chains (bounded at 3 passes, terminating by construction). Pinned three ways: a corpus family (`_ACCEPTANCE_ENTRIES`, a THIRD provenance - derived from the reverted detector's recorded defects, so biased toward neither guard), fixtures in both directions, and mutation `#B18` |
| **B1-AC2b** | - | **FIXED in the same pass** | **The first version of that fix was pinned by a DECORATIVE test, and the harness said so in seconds.** Mutation `#B18` came back **SURVIVED**: the fixtures lived in `cap_shapes`' selftest while the defect lives in `cap_types`, and mutating a unit runs THAT unit's selftest. A fixture in the wrong file is a decorative test with extra steps. Assertions moved into `cap_types.selftest()`, `#B18` now CAUGHT. Recorded because it is the second time this session that SURVIVED caught something review did not |
| **B1-DUP** | LOW | **FIXED 2026-08-06** | The script that split the 804-line module into `cap_types` + `cap_shapes` emitted `_contains_exit` and `_import_aliases` **twice** in `cap_types.py`. Harmless at runtime (identical bodies, the second wins) and invisible to every gate - no test, no linter and no selftest looks for a duplicated top-level def. Found while editing, confirmed by an AST count, both duplicates removed (489 -> 469 lines). The general version - a check that no module defines the same top-level name twice - is NOT scheduled here and is NOT claimed as covered; it is named so the gap is visible |

**The 8 acceptance criteria, probed rather than assumed.** 7 of 8 hold; the 8th was AC2 above.
AC1 (drop-until-under-cap where the drop is a rebind-slice) and AC1b (via `pop`) both flag;
AC5 (a scan-truncating exit must not mis-branch) flags; AC7 (exemption keys separate scopes
that share a name) flags a method named `run` while the module-level `run` stays exempt.
**AC6** - "`caps` must not be module-scoped such that one function's default promotes a name
file-wide" - is discharged BY CONSTRUCTION rather than by test: C1-NEW never builds a set of
cap names at all, so the defect has no surface. **AC3** ("no branch may be dead the day it
lands") and **AC4** ("the no-regression floor must be DERIVED") are NOT probed here: AC4
belongs to `no_regression`, which derives its floor by running the predecessor, and AC3 would
need a coverage run over the new modules. **AC3 is therefore the one criterion neither
verified nor scheduled by this session** - stated plainly rather than folded into a count of
7 of 8.

**Both gaps named above are SCHEDULED, not logged.** Naming a gap and leaving it homeless is
the soft-defer failure this audit exists to catch, and the paragraph above committed it twice
in its own last four lines.

| id | sev | owner | item |
|---|---|---|---|
| **B1-AC3** | **MEDIUM** | **phase 2, with the verifier-of-verifiers** | **Acceptance criterion 3, "no branch may be dead the day it lands", is UNVERIFIED for `cap_types` and `cap_shapes`.** It was a real defect in the reverted detector (two dead branches in `_cap_names`), and this build has 24 + 19 top-level definitions with no coverage measurement over any of them. Every rule has at least one fixture, which is necessary and not sufficient - a fixture proves a branch is reachable, not that every branch is. Fix: run a coverage pass over both modules driven by their own selftests plus the 135-entry corpus, and either exercise or delete each unreached branch. Sits in phase 2 because it is a verifier-of-verifiers question: the guard's own untested code is exactly the class this plan keeps finding |
| **N3-DUP** | LOW | **phase 4, with N3** | **No check anywhere notices a module defining the same top-level name twice.** MEASURED: the split that produced `cap_types.py` emitted `_contains_exit` and `_import_aliases` twice; the file imported, ran, passed its own selftest, passed all 30 suite gates and the python-floor parse check. Found by an incidental AST count while editing, not by any gate. Belongs with N3 because it is the same shape as the 800-line rule - a property everyone assumes is enforced and nothing enforces. Cheap: one AST pass over the derived unit roster, printing its denominator |

#### Source-coverage audit, 2026-08-06 (second pass) - 2 real gaps in 81 source ids

Method: every finding id named in the six source audit docs was extracted MECHANICALLY and
reconciled against this plan. A defer-grep over the plan cannot find what the plan never
mentions; enumerating ids out of the SOURCES and checking each against the plan can.
**81 distinct ids; 37 the plan never names; 35 adjudicated as not-gaps; 2 real.**

The 35: control labels from experiments (`C0`, `C1-C4`, `N7`, `M0`), fragments of the
`git diff -M05` / `-M50` flags, Q-section headings (`Q1`-`Q5`), a line reference (`L6`),
and range forms the plan carries as ranges rather than as individual ids (`C1-R2`..`C1-R8`
retired as `C1-R1..R8`; `N1-N4`; `R2-H2`/`R2-M3`, which ARE the union those 8 retired rows
cover). `F-M8` is explicitly dispositioned in `p14_triage.md` as "twin of the dropped
candidate; folds into row 1; no separate row" - and its content (`_max_names` sees only
`ast.Assign`, so imports, annotated assignments and attribute bounds are invisible) is
precisely what C1-NEW fixed, so it is now **BUILT**.

| id | sev | owner | item |
|---|---|---|---|
| **SC3** | **MEDIUM** | **BUILT 2026-08-06** | **A mutation the source RESERVED and nobody built, guarding the rule that every component of an exemption key must be load-bearing.** `p14_new_code_review.md` reproduced it in an isolated scratch tree: a two-line widening of the `BOUND_EXEMPTIONS` membership test blinds `slicing_offenders` to real offenders while `capped_report --selftest`, the whole suite and all three `capped_report` mutations stay green - "because nothing anywhere pins the (module, constant) pair". It named the fix (plant a fixture, add mutation `B9`) and **the plan never carried a row for it**, so it survived the revert, the rebuild and two prior audits. The key is now a TRIPLE, `(module, qualname, kind)`, so there are three ways to widen it and each now has its own control: a different function in an exempted module must still flag (qualname), a DISPLAY cap in an exempted function must still flag (kind), and the same qualname+kind in another module must still flag (module). Mutation **`cap_shapes #B19`** - the source calls it `B9`, an id already taken here by an unrelated `cap_shapes` entry - CAUGHT. **The general rule the source states and this plan should have carried: any exemption or allowlist keyed on a tuple must test that EVERY component of the key is load-bearing** |
| **SC4** | **LOW** | **phase 4, with the `fast_test_on_stop` work** | **A fix ORDER that no row states, and getting it wrong produces a SURVIVED mutation.** `p14_triage.md` records that `F-H3` "establishes a fix ORDER the main list does not state: fix `_child` FIRST, because adding `verify_unit` to mutation #10 alone just flips it to SURVIVED." The ordering constraint is real, is load-bearing for whether the mutation proves anything, and appears nowhere in this plan - the triage doc says in as many words that the main list does not state it, and no subsequent row added it. Recorded now so the constraint survives to whoever does that work |

**What this pass did NOT do, stated so the scope is not overread.** The three large source docs
(`p14_audit_findings.md` 100 KB, `p14_new_code_review.md` 87 KB, `p14_cluster1_evidence.md`
64 KB) were **not** re-enumerated prose-by-prose. The skill's procedure calls for a Workflow
fan-out to do that without skimming, and the usage snapshot needed to authorise one was not
available. The id-space reconciliation above is mechanical and COMPLETE for items that carry
an id; it is BLIND to a source requirement stated only in prose with no id. That is a real
coverage limit of this pass, not a clearance - and it is exactly how `SC3` hid, since its own
recommendation names an id (`B9`) that never existed.

#### Meta-review, 2026-08-06 (B1) - one class recurring SEVEN times, and six clean probes

**The probes came back clean, and that is worth stating with its denominator.** Prior
meta-reviews found MR-a (a gate fully disarmable with every test green) and MR-b (a
false-alarm mode in the guard written to avoid one) by PROBING rather than reading. The same
method against this session's guards, each in an isolated copy of the repo: **6 of 6
disarming edits were CAUGHT** - the `capped_report` delegate returning `[]`, `verdict()`
always saying OK, `exemption_problems()` returning nothing, the roster check bypassed, every
site suppressed, and clause 2 swallowing every display cap. Two of those exercise the
DECISION rather than the detector, which is precisely what MR-a proved was missing before.
A negative result, reported with what was tried.

| id | sev | owner | item |
|---|---|---|---|
| **MR-c** | **MEDIUM** | **phase 2, with the verifier-of-verifiers** | **An uncontrolled timing claim has now been written and corrected SIX times in this repo, and every fix has been an INSTANCE fix.** The record: four timing conclusions reversed by a control during the A8 work; "the ~50-minute sweep" caught by the 2026-08-05 consistency audit and withdrawn; and "1.08s" caught by today's, where the true figure is **1.291s median (n=5)** and the control proved the box was idle. The rule is written down, is known, and is applied correctly to the number under scrutiny - then dropped for whichever number feels too small to matter. **That pattern does not respond to another reminder; it needs a mechanism.** The mechanism is mechanically decidable and this repo already has its twin: `numbers_match_on_write` fires when a number written into a doc matches no source. The analogue: fire when a doc gains a DURATION (`\d+(\.\d+)?\s*(s\|ms\|sec\|seconds\|minutes?)`) that is not accompanied by a control marker (`median`, `n=`, `interleaved`, `control`, `spread`). Fail-silent, once per session, like its twin. Until it exists, the class WILL recur - it has six times |
| **MR-d** | - | **WITHDRAWN 2026-08-06, premise expired** | Filed as "every audit artifact of the last two sessions is dated `2026-08-06` while the system clock says `2026-08-05`". The measurement was correct when taken - `date -u` returned `2026-08-05T20:41:48Z` - but the session **straddled midnight**, and the clock has since rolled to `2026-08-06`. The labels were right and the finding was an artifact of when it was measured. Withdrawn rather than deleted, and recorded rather than quietly dropped, because a finding that evaporates on re-measurement is exactly the kind this plan asks to be shown (N1 is the precedent). **The transferable lesson is real and is kept: a date-derived claim taken once near a boundary is an uncontrolled measurement in the same way a wall-clock timing is** - the same class as MR-c, which sits directly above it. The correct check would have been to compare the artifact dates against the clock TWICE, or against the git commit timestamps, rather than against one reading |
| **MR-e** | LOW | phase 4, with M3 | `hooks/cap_shapes.py` grew **694 -> 739 lines** inside one session, purely from fixtures and controls added by the close-out audits. Not a violation (M3's watch band is 760+, where `duplicate_registration_check` sits at 792 and `hook_health_check` at 790) but the trajectory is the same one that put those two there, and the growth came from the healthiest possible source. Recorded so the next addition is a decision. The natural split, if needed, is the fixture tables out to a sibling |

**Gate ledger, read rather than reconstructed** (the check this skill insists on). 153 entries,
**exactly one distinct gate: `run_selftests`** - M2's finding, unchanged and already scheduled
for phase 4. The last entry is 90 seconds old, so the ledger is CURRENT for the one gate it
covers and blind for every other. `mutation_check` ran four times today and wrote nothing to
it, which is exactly M2's point.

**Durability check on this session's own fixes.** AC2 -> mutation `#B18` + a corpus family;
the exemption key -> three controls + mutation `#B19`; the duplicate definitions -> removed,
with the general check scheduled as `N3-DUP`; the corpus contradiction -> `score_corpus`
derives and prints it every run + mutation `#B1c`. **The one fix with no mechanism behind it
is the timing correction, which is MR-c above** - and it is the one that has recurred six times.

#### ADVERSARIAL REVIEW of the six guard files, 2026-08-06 - run `wf_91a48c61-20d`

**B1 is NOT clean. 30 CONFIRMED findings, 6 at HIGH after refuter correction.** Full write-up
with every finding, its failure scenario and its refuter's reasoning:
`docs/audits/adversarial_review_2026-08-06_guards.md`. 5 lenses (fail-open, disarmability,
false-alarm, roster-rot, grader-integrity), refuters UNCAPPED, 49 agents, **0 repo writes**
(tree diffed against a pre-run snapshot).

| id | sev | owner | item |
|---|---|---|---|
| **AR-GAP** | **HIGH** | **phase 1, BEFORE anything else in B1** | **The review is INCOMPLETE and must not be read as a clean bill. The `disarmability` lens NEVER RETURNED** - 4 of 5 lenses produced results. Its transcript ends at "Now the disarm probes on the never-probed units": it had finished `cap_shapes`/`cap_types` and stalled entering `hook_layers`, `check_mutation_anchors` and `score_corpus`, which have therefore had **no disarm probing at all**. That is the single most important lens for this repo - MR-a was a gate fully disarmable while every test stayed green. Per the skill's own rule, its findings are OPEN CANDIDATES, not absent. **Re-run that lens alone before B1's HIGH count is trusted.** The 44 findings that WERE produced were all adjudicated (44 of 44), so the gap is one whole lens, not a capped fan-out |
| **AR-1** | **HIGH** | phase 1 | **The grammar-closed claim - the whole design - is FALSE as implemented.** Two independent lenses landed on it. VERIFIED BY HAND: **`out[12:] = []` is INVISIBLE while its exact semantic twin `del out[12:]` is a shape**, because the slice-assignment Store path is never inspected. The fail-open lens reports 12 silent-shortening operations producing ZERO sites. This is precisely the disease that got the predecessor reverted, one level up: not an unenumerated cap SPELLING but an unenumerated shortening OPERATION. The claim in the module docstring and in the B1 row must be corrected, not just the code |
| **AR-2** | **HIGH** | phase 1, with B1-SCOPE | **86% false-positive rate on ordinary correct Python.** The false-alarm lens measured the guard against real third-party code. B3-FP's lesson is that a guard which fires on correct code gets disabled - strictly worse than none. This QUANTIFIES B1-SCOPE and B1-C2FLOW, which were recorded as unmeasured, and it means widening the sweep beyond `hooks/` is blocked, not merely deferred |
| **AR-3** | **HIGH** | phase 1 | `_routed()` is a two-name roster (`keep`/`render`) that exempts an ENTIRE function scope, so one sanctioned call disarms every unrelated cap in the same function. A roster-shaped fail-open inside the guard built to replace roster-shaped fail-opens |
| **AR-4** | **HIGH** | phase 1 | **A dead branch the day it landed** - the index-bounds-check exclusion is unreachable for every `while` loop, because the `While` path calls `_size_test_target(node.test, set())` with an empty `loop_vars`. This is acceptance criterion 3 (`B1-AC3`) not merely unverified but **VIOLATED**, and AC3 was the one criterion this session scheduled instead of checking |
| **AR-5** | **HIGH** | phase 1 | `_name_of` collapses an attribute chain to its root, so any method calling `self.<anything>.append()` marks `self` as a collection - clause 1 mis-typing at the root of a very common shape |
| **AR-6** | **MEDIUM x23, LOW x6** | phase 1-2 | The remaining 29 confirmed findings, each with a refuter verdict, in the audit doc. They cluster into: exemption granularity (function-level, not site-level), `exemption_problems()` failing open (it audits which keys were SEEN, not which VERDICTS would change), `score_corpus.main()` being unable to fail, `run_entry` making `rel_path` decorative, closed callee-name rosters, and four shipped docstrings quoting corpus scores that are now wrong |
| **AR-7** | - | **FIXED 2026-08-06** | **MR-c's EIGHTH instance, in shipped code, found by the review.** `capped_report.py` carried "Measured 2026-08-02: 0.20s, under 1% of the cap" and never updated it when the detector was rebuilt. Re-measured on a quiet box, interleaved against a control at 0.89x: **1.412s median (n=5, 1.375-1.462)**, i.e. ~7x stale. **The reviewer reported it as 20x stale from a 3.8-4.7s reading taken while five review agents loaded the box** - the finding was right and its magnitude was an A8 confound, so the corrected comment records the controlled figure and says why. Both halves of this repo's two timing lessons, in one finding |

**What this changes about the ship gate.** Nothing about the arithmetic - all 11 HIGH in the
work-order table were already open. But B1's own 4 HIGH are now joined by **6 more confirmed
HIGH from the review plus AR-GAP**, and none of them can be counted into the 44-row table, the
class family, the source-coverage bucket, or the B1 build bucket. **This is a FIFTH accounting
system: the adversarial-review findings.** They must not be summed with any of the other four.

**The honest summary of B1's status: BUILT, MEASURED AT THE CORPUS CEILING, AND NOT CORRECT.**
A corpus score of 102 of 105 with zero false positives is exactly what this repo means when it
says green gates on never-reviewed code are the absence of evidence - the corpus had no entry
for any of the six HIGH findings above, so it could not move when they were present.

#### CORRECTION to the adversarial-review rows above, same day - `AR-GAP` is WITHDRAWN

The run `wf_91a48c61-20d` **COMPLETED**. All 5 lenses returned; `coverage_complete: true`,
`dropped: 0`. The rows above were written from a journal snapshot taken while the run was
still live, and are superseded by these figures:

| | reported above | ACTUAL |
|---|---|---|
| lenses returned | 4 of 5 | **5 of 5** |
| findings produced | 44 | **59** (fail-open 7, false-alarm 18, grader-integrity 8, roster-rot 11, **disarmability 15**) |
| adjudicated | 44 | **59**, dropped 0 |
| CONFIRMED | 30 | **42** |
| confirmed HIGH | 6 | **10** |
| agents | 49 | 64, 0 errors, still **0 repo writes** |

| id | sev | owner | item |
|---|---|---|---|
| **AR-GAP** | - | **WITHDRAWN, same day** | Claimed the `disarmability` lens never returned and its findings must be treated as open candidates. FALSE: it returned 15 findings, 4 of them confirmed HIGH. The claim came from counting `started` vs `result` lines in `journal.jsonl` **while the workflow was still running** and reading the shortfall as a stall. **This is the same class as MR-c and MR-d - a single reading of a moving quantity, asserted as a fact** - and it is the third instance in one session, after the 1.08s timing and the date drift. The transferable rule: a coverage or progress number read from a live artifact is not a measurement until the producer has exited. Withdrawn rather than deleted, per the N1 precedent |
| **AR-8** | **HIGH** | **phase 1, at the very front** | **MR-a REPRODUCED, one level up, in the LIVE cap guard.** The `disarmability` lens found that the cap-guard DECISION is a one-token disarm with all 30 gates green. **This directly refutes the claim recorded earlier this session that "6 of 6 disarm probes were CAUGHT, so the guards are not MR-a-disarmable"** - those 6 probes were hand-written by the same agent that wrote the guard, and a more thorough independent lens found disarms they did not cover. The shared-assumption failure the whole adversarial-review method exists to break, demonstrated against my own probes |
| **AR-9** | **HIGH** | phase 1 | **`check_mutation_anchors.main()` is untested: two one-token edits disarm the anchor gate and it still prints OK.** That gate is M1, built specifically so a disarmed mutation costs 0.087s to find instead of a full sweep - and it is itself disarmable. MR-a's exact shape in the guard written after MR-a |
| **AR-10** | **HIGH** | phase 1 | Clause 4's raise-exemption can be widened to exempt any function containing a conditional `raise`, with every gate green |
| **AR-11** | **HIGH** | phase 1 | Four clause-1/2 vocabulary widenings each blind the guard with all 30 gates green - the `_SCALAR_CALLS` / `_AGGREGATORS` rosters are load-bearing and unpinned |

**AR-1's severity, corrected by its own refuter and worth carrying.** The finder rated it
CRITICAL over "12 silent-shortening operations". The refuter reproduced the core with a clean
A/B - `del out[12:]` flags, `out[12:] = []` does not, same line, same file - and then cut the
claim down: 2 of the 12 are impossible on the stated 3.8 floor, ~7 are contrived, **the
credible core is ONE idiomatic truncation plus two marginal ones**. It also established that
**the predecessor misses it too**, so this is a SHARED gap and not a regression - the rebuild
strictly dominates on this family. HIGH, not CRITICAL, and "12 operations" should not be
requoted.

**Final status: 42 confirmed findings, 10 HIGH.** B1 is BUILT, at the corpus ceiling, and NOT
CORRECT.

#### MR-c BUILT, and the push it blocked - 2026-08-06

Two rules from `tooling-discipline.md` are now enforced MECHANICALLY, because both had recurred
despite being written down:

| id | sev | owner | item |
|---|---|---|---|
| **MR-c** | - | **BUILT 2026-08-06 (`5b6986a`)** | `hooks/timing_claim_guard.py`. Flags a duration written as MEASURED with no control marker. Narrow BY MEASUREMENT: the first design would have fired on ~65 of 82 duration mentions in this plan and been disabled in a week; the shipped design fires on **18 of 109** duration lines across all 16 docs (17%), and the fires are genuine. Joins `post_tooluse_dispatcher`, advisory, once per session. TC1-TC4 CAUGHT. **A dead branch turned harmful while building it**: a DECLARATION roster added as "belt and braces" was unreachable on arrival, then began vetoing every match of the second trigger. AR-4's class, one step later, inside the guard written to enforce measurement discipline |
| **PG** | - | **BUILT 2026-08-06 (`3cea480`)** | `hooks/piped_gate_guard.py`, the suite's first PreToolUse hook. Blocks a Bash command piping a GATE into `head`/`tail`/`grep`, because the pipeline returns the last command's status and the gate's real result is discarded. Caught its own author 4 times in one session's command history, 0 false positives on 15 verbatim commands. Two defects found in it BY MEASURING: substring matching blocked a quoted grep argument, and plain `shlex.split()` was blind to `2>&1\|head` with no spaces - it caught 2 of 4 real offenders and was silently blind to the rest. PG1-PG5 CAUGHT |
| **A8-PP** | **RESOLVED 2026-08-06 - see the re-scoped ship-gate section below** | **phase 0, with A8** | **The pre-push gate now BLOCKS this repo's own pushes, and whether that is correct is UNMEASURABLE on this machine today.** The suite grew 30 -> 32 gates; `.claude/pre-push.cmd` caps it at 120s; the gate refused two verified commits with "tests exceeded 120s and were killed, so this push is NOT verified". **The gate is behaving correctly** - it declined to certify what it could not run. But every timing reading taken to adjudicate it is confounded: `run_selftests` measured 113.7s, 180.5s and 212.7s across runs while the CONTROL (`check_readme_fresh`, historically 0.099s) read **3.0x, 3.6x and 7.8x**, and `Win32_Processor` reports **LoadPercentage 100** with this session's own python processes idle. The suite failure in those runs was `meta_audit_on_stop` - **A8's named case, verbatim**. So: the cap may genuinely be too low for a 32-gate suite, or the box may simply be busy, and NOTHING here distinguishes them. **Not raising the cap on a confounded number, and not pushing with `--no-verify`** - both would be choosing a conclusion the evidence does not support. Re-measure on a genuinely quiet box, then either raise the cap deliberately or find what got slower. This is the third distinct consequence of A8 in one session, after 14 deleted mutations and a reviewer misreading a 1.4s selftest as 3.8s |

## RE-SCOPED SHIP GATE, 2026-08-06 - the gate a future reader must use

**THE GATE, by decision, replacing zero-HIGH:**

> v1.3.1 ships when there is **no HIGH in the SHIPPED HOOK PATH** - no defect a user can hit at
> runtime on their own machine, through a hook that actually fires for them.

Everything else - a gate disarmable only by an edit nobody will make, a dev-time tool, a
selftest of a selftest - moves to a **v1.4 backlog**. It stays SCHEDULED and gets built. It
stops blocking the release.

**WHY, measured.** Severity-bearing rows in this file went 18 -> 49 in a single day. The 11 HIGH
in the work-order table have been open since 2026-08-02 and this file states twice that the
sessions in between closed none of them; the last commit whose headline was CLOSING findings is
dated 2026-07-31. C1-NEW targeted four of the 11, closed zero, and added ten more. The mechanism
is structural, not a discipline failure: in a tool whose thesis is that checks lie, every new
guard is new surface for the same defect class, so zero-HIGH recedes faster than it can be
approached. **A gate that can never pass is not a gate** - the exact pattern this repo exists to
catch, running on this repo.

### The classification rule, stated so it can be refuted

A finding is **SHIP-BLOCKING** iff BOTH hold. Otherwise it is **V1.4-BACKLOG**.

- **R1 EXECUTION** - the defective code RUNS on an installed user's machine, via an entry point
  this repo wires or documents. The entry points, derived rather than listed:
  1. the 8 script paths `install.py:desired_groups()` writes into `~/.claude/settings.json`
     (parsed out of the AST, not transcribed): `rate_prompt`, `hook_health_check`,
     `duplicate_registration_check`, `usage_snip_prompt`, `stop_dispatcher`,
     `post_tooluse_dispatcher`, `close_skills_guard`, `piped_gate_guard`;
  2. `hooks/pre_push_gate.py` - NOT wired by `install.py`, but README documents it as a real git
     hook the user installs (`--install-global` sets `core.hooksPath`). Excluding it because
     `install.py` does not name it would be an artifact of the rule, not a fact about the user;
  3. **`hook_health_check`'s weekly sweep**, which runs `subprocess.run([sys.executable, path,
     "--selftest"])` over every `hooks/*.py` at SessionStart (`hook_health_check.py:223`). Every
     hook selftest therefore EXECUTES on a user's box, weekly. `tools/*` and `tests/*` are not
     swept.
- **R2 TRIGGER** - the input that exposes it is something the USER supplies: their repo, their
  `settings.json`, their plan documents, their transcript, their git state. NOT a modification
  of unbluff's own source.

**Neither half alone is sufficient, and this is the load-bearing part.** A pure import-closure
of the entry points above reaches **24 of 41 local modules** (17 dev-time; computed by an AST
walk over static imports plus the dispatchers' `importlib.import_module` string constants). That
closure includes the entire cap detector - `capped_report` is imported by five wired hooks. But
`capped_report` only CALLS `cap_shapes.slicing_offenders` / `verdict` / `exemption_problems`
from inside `selftest()`, and that selftest's subject is unbluff's own `hooks/` directory, whose
contents are byte-identical on every machine. A user who never edits unbluff's source cannot
change that verdict, so R1 is satisfied and R2 is not. Conversely R2 alone would admit
`tools/mutation_check.py`, which never runs on a user's machine at all.

### Counts - and the denominator

**SHIP-BLOCKING: 1 of 21. V1.4-BACKLOG: 20 of 21.**

The denominator is **21 = 11 + 10**, reconciled rather than assumed:

- **11** from the 44-row work-order table: `capped_report` 4, `mutation_check` 2,
  `run_selftests` 2, `pre_push_gate_selftest` 2, `meta_audit_on_stop` 1.
- **10** confirmed HIGH in `docs/audits/adversarial_review_2026-08-06_guards.md`
  (`{'HIGH': 10, 'MEDIUM': 26, 'LOW': 6}` of 42 confirmed). They appear in this plan as **nine**
  rows - AR-1..AR-11 minus AR-6 (MEDIUM x23 / LOW x6) and AR-7 (FIXED) - because **AR-1 merges
  two audit-doc HIGH findings**: doc #3 (`seq[n:] = []` invisible) and doc #5 (the
  grammar-closed claim). 9 plan rows carry 10 findings. AR-GAP is WITHDRAWN and carries none.

| # | id | unit | R1 runs on a user's box? | R2 user-supplied trigger? | bucket |
|---|---|---|---|---|---|
| 1 | W-CR1 | `hooks/capped_report.py` (detector: `_max_names` blind to AnnAssign/tuple targets) | yes, weekly `--selftest` sweep | **no** - needs a new cap added to unbluff's own `hooks/` | V1.4-BACKLOG |
| 2 | W-CR2 | `hooks/capped_report.py` (detector: bare-Name upper bound only; whole-file skip) | yes, same | **no** - same | V1.4-BACKLOG |
| 3 | W-CR3 | `hooks/capped_report.py` (detector: blind to 9 of 11 cap spellings) | yes, same | **no** - same | V1.4-BACKLOG |
| 4 | W-CR4 | `hooks/capped_report.py` (the adjudicated dropped candidate) | yes, same | **no** - same | V1.4-BACKLOG |
| 5 | W-MC1 | `tools/mutation_check.py` (#10 self-verifies) | **no** - `tools/` is neither wired nor swept | n/a | V1.4-BACKLOG |
| 6 | W-MC2 | `tools/mutation_check.py` (no verifier of its own) | **no** - same | n/a | V1.4-BACKLOG |
| 7 | W-RS1 | `run_selftests.py` (`missing_gates()` is dead code; A3 certifies an uncalled copy) | **no** - repo root, not wired, not swept | n/a | V1.4-BACKLOG |
| 8 | W-RS2 | `run_selftests.py` (`ran` counts hooks whose `--selftest` never executed) | **no** for `run_selftests` - **but see the twin note below** | no - needs a commented-out dispatch in unbluff's source | V1.4-BACKLOG |
| 9 | W-PP1 | `hooks/pre_push_gate_selftest.py` (`_child()` spawns the selftest module, not the hook) | **yes** - runs under `pre_push_gate --selftest` in the weekly sweep | **no** - subject is unbluff's own gate; the production push path is correct today | V1.4-BACKLOG |
| 10 | W-PP2 | `hooks/pre_push_gate_selftest.py` (`main()`'s fail-open handler pinned by no test) | **yes** - same | **no** - same | V1.4-BACKLOG |
| 11 | **W-MA1** | **`hooks/meta_audit_on_stop.py`** - `has_decision_tag` treats ANY bracketed prose containing an allow-word as a decision tag, silently suppressing a genuine hiding line AND removing it from the reported total | **YES** - Stop hook, every turn-end, via `stop_dispatcher` | **YES** - the user's own plan text, e.g. `- PARKED: port the (closed-loop) controller` | **SHIP-BLOCKING** |
| 12 | AR-9 (doc #1) | `tools/check_mutation_anchors.py` | **no** - `tools/` | n/a | V1.4-BACKLOG |
| 13 | AR-2 (doc #2) | `hooks/cap_shapes.py` - 86% false positives on ordinary correct Python | yes, weekly sweep | **no** - the guard only ever scans unbluff's own `hooks/`; "unshippable OUTSIDE `hooks/`" blocks a future widening, not a live path | V1.4-BACKLOG |
| 14 | AR-1a (doc #3) | `hooks/cap_shapes.py` - slice-assignment Store path never inspected | yes | **no** | V1.4-BACKLOG |
| 15 | AR-10 (doc #4) | `hooks/cap_shapes.py` - clause 4 raise-exemption widening | yes | **no** | V1.4-BACKLOG |
| 16 | AR-1b (doc #5) | `hooks/cap_shapes.py` - the grammar-closed claim is false | yes | **no** | V1.4-BACKLOG |
| 17 | AR-3 (doc #6) | `hooks/cap_shapes.py` - `_routed()` exempts a whole function scope | yes | **no** | V1.4-BACKLOG |
| 18 | AR-8 (doc #7) | `hooks/cap_shapes.py` `verdict()` - the LIVE decision is a one-token disarm | yes | **no** - a one-token edit to unbluff's source | V1.4-BACKLOG |
| 19 | AR-4 (doc #8) | `hooks/cap_shapes.py` - index-bounds exclusion dead for every `while` | yes | **no** | V1.4-BACKLOG |
| 20 | AR-5 (doc #9) | `hooks/cap_types.py` - `_name_of` collapses attribute chains | yes | **no** | V1.4-BACKLOG |
| 21 | AR-11 (doc #10) | `hooks/cap_types.py` - four clause-1/2 vocabulary widenings | yes | **no** | V1.4-BACKLOG |

**W-RS2's TWIN IS LIVE, and this is the finding the classification produced.** `run_selftests`
accepts `rc == 0` with zero output as proof that a hook's selftest executed. The IDENTICAL rule
is in `hook_health_check.run_weekly_selftests` - `if proc.returncode == 0: done[name] = "pass"`
at `hook_health_check.py:227`, with no output marker - and THAT one is a wired SessionStart hook
running on every user's machine. It stays V1.4-BACKLOG, because disarming it needs an edit to
unbluff's own source (R2 fails). But when W-RS2 is fixed in v1.4, **the fix must land in both
places in the same pass**, or the class survives in the copy that ships. Recorded here because
the estimate this classification replaced could not have surfaced it.

### The prior estimate: right answer, wrong reasons - and the reasons mattered

The estimate carried in was "roughly 1-2 ship-blocking", justified by "`meta_audit_on_stop` is a
real Stop hook while `mutation_check`, `run_selftests`, `pre_push_gate_selftest` and the cap
detector are dev-time". Tested rather than inherited: the ANSWER lands in the right place, and
**two of its four premises are false.**

- `pre_push_gate_selftest` is **not** dev-time. It executes on a user's machine every week, via
  `pre_push_gate --selftest` in the health sweep. It is backlog for the R2 reason, not the R1 one.
- the cap detector is **not** dev-time either. `capped_report` is imported by five wired hooks
  and its `--selftest` is subprocessed weekly on the user's box. It is backlog because its
  SUBJECT is unbluff's own source, not because it never runs.

The distinction is not pedantry: it is what surfaced W-RS2's live twin, and it is what decides
which v1.4 fixes ALSO need a user-runtime fix. An unverified estimate that happens to land on
the right number still cannot answer the next question.

### Accounting - the sixth axis is a LABEL, not a bucket

Five severity systems coexist and must never be summed: the 44-row work-order table (11 HIGH),
the fail-open class family, the source-coverage findings (SC1-SC4), the B1 build findings
(`B1-*`, MR-c/e), and the adversarial-review findings (AR-1..AR-11). SHIP-BLOCKING vs
V1.4-BACKLOG is a **sixth axis that cuts across all of them**. It relabels existing findings and
introduces none. The table above has 21 rows because there are 21 open HIGH, not because a new
bucket was opened.

### Resolved and new, same day

| id | sev | owner | item |
|---|---|---|---|
| **A8-PP** | - | **RESOLVED 2026-08-06** | **The cap was never the problem; the box was.** Re-measured on a quiet box after stopping `hsscp` and `ArmouryCrate` (the two named non-Claude CPU consumers; `LoadPercentage` went 100 -> ~10). Protocol fixed before the run: control x5, subject x1, control x5. CONTROL (`tools/check_readme_fresh.py`, characterised at 0.099s by M1): **0.086s median before (range 0.083-0.090)** and **0.082s median after (range 0.078-0.085)**, i.e. **0.87x and 0.83x** of that baseline - the box was quiet at BOTH ends, so the subject reading is a measurement rather than another confound. SUBJECT `run_selftests.py`, interleaved between those controls: **49.740s, rc=0, 32/32**. That is **41% of the 120s cap, 2.4x headroom** - the cap is NOT raised, and raising it on the earlier numbers would have meant acting on three readings (113.7s / 180.5s / 212.7s) whose controls read 3.0x / 3.6x / 7.8x. Independently corroborated by a different clock: the pre-push gate then ran the suite itself and reported "tests passed in 48s - allowing push". **Correction to the A8-PP row above: the 120s cap lives in `.claude/fast-test.cmd`, not `.claude/pre-push.cmd`** - the latter does not exist in this repo, so `pre_push_gate` falls through to `fast_test_on_stop.detect()`. Commits `3cea480`, `5b6986a`, `6b64549` PUSHED, no `--no-verify` |
| **CI-SHALLOW** | **HIGH - and it was RED, not latent** | **FIXED 2026-08-06 (`59fb389`)** | **CI was red on 11 of 11 jobs, every OS and every Python version, across two commits, on a tree that was green locally and passed the pre-push gate. No gate in this repo could see it; it was found by reading `gh run list`.** `actions/checkout@v4` fetches ONE commit. `no_regression` compares each unit against the newest committed blob that DIFFERS from the working tree; in a depth-1 tree that blob is unreachable, so `predecessor()` returned "no committed blob differs from the working tree". The DETECTOR half reads that correctly and prints `SKIPPED - UNCOVERED, not passing`. The WAIVER auditor read the identical condition as "has no predecessor at all, so nothing can be lost" and made it BLOCKING - asserting a fact about the repository that was false. REPRODUCED before fixing (`git clone --depth 1` of this repo exits 1 with the byte-identical message; the full clone exits 0), then again as a hermetic two-commit fixture. **The fix is two halves and neither is sufficient:** (1) `history_truncated()` asks git directly - `is-shallow-repository` plus the partial-clone configs, because a blobless clone hides objects the same way and only one of the two is famous - and `classify_waivers` gains a sixth state, UNKNOWN, non-blocking and printed on its own UNDETERMINED line; (2) all four CI jobs fetch full history, because half 1 alone would have turned CI green by making the gate verify NOTHING there, silently, on every run. `fetch-depth` is set on all four checkouts rather than on the jobs that run a history-dependent gate today, since "which job runs which gate" is exactly the roster this repo keeps finding rotted. TDD: test F written FIRST and watched FAIL on three separate assertions, with its own CONTROL half so a broken fixture cannot read as a fixed bug. Suite 32/32, anchors 127 -> 129 across 128 entries in 29 files, mutations CS1 and CS2 both CAUGHT. **No sixth accounting system is opened for this**: it is one new finding, found this session, counted nowhere in the 21 |

**Status of this section: the classification above has NOT yet had an independent pass.** Per
`tooling-discipline.md` section 6, a probe written by the author of the thing it probes is a
smoke test. The rule, the 21 rows and the two premise corrections were all derived by one agent,
and a ship gate is exactly the class - gate logic, author-written test - that section names as
requiring an independent lens BEFORE the unit is reported as sound. Treat the counts as
**PROPOSED** until that pass returns.
