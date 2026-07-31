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

Fresh 4-lens review over the units this pass changed. 21 agents, 16 raw findings, 13 survived a
refuter defaulting to `refuted=true`, deduped to **11 unique defects**.

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

21 agents, 4 lenses, 16 raw findings - **all 16 survived refutation** (none refuted, which is
itself a signal: these files had never been looked at adversarially). Deduped to 13 confirmed
defects across 5 files. The three dispatcher/health files came back CLEAN.

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
19 units this session changed. 16 raw findings, **15 survived refutation**, deduped to 11
unique. **7 HIGH. Four were REGRESSIONS introduced by this session's own fixes.** Verdict from
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
