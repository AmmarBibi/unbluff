# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

## [Unreleased]

### Added
- **`tools/ship_bar_gate.py` + `docs/audits/findings.json` - criterion 2's stopping rule is now
  a CONTROL, not prose.** Nothing previously stopped a v1.4.0 tag while a CRITICAL sat open, and
  the open-finding count was itself unverifiable: the ledger's list of "the remaining 8" named
  five items the same table marked BUILT. Registered as the `ship-bar` gate (suite 35 -> 36).
  **It refuses to parse prose.** SEVERITY is DERIVED, every run, from the review report's own
  `## Confirmed` table; STATE (BUILT / SCHEDULED / FINALIZED-EXCLUSION) is the only
  hand-adjudicated field; and the two are RECONCILED on every run, so a severity cannot be
  downgraded by retyping and a row cannot exist in one and not the other.
  **A CRITICAL or HIGH cannot be excluded.** `FINALIZED-EXCLUSION` rescues MEDIUM/LOW only -
  otherwise any blocking finding could be excused in the state column instead of re-adjudicated
  in the report where the change is visible. Pinned `SB-1` (the rule), `SB-2` (that loophole)
  and `SB-3` (the reconciliation).
  **First run, and it settles a disputed number mechanically:** 24 findings = 1 CRITICAL BUILT,
  4 HIGH BUILT, 11 MEDIUM BUILT, 1 MEDIUM FINALIZED-EXCLUSION, 4 MEDIUM + 3 LOW SCHEDULED.
  **PASS** - and **SEVEN** open rows, not eight; the eighth was a decision already taken.
- **`tools/gate_ledger.py` - the gate ledger now records more than one tier**, which is the
  ENABLER the ship bar's verify-before-pushing half was blocked on. The writer had lived inside
  `run_selftests.py` as a private function with the gate name HARDCODED, so exactly one of five
  tiers could record anything: measured 2026-08-13, 200 entries, all `run_selftests`, on a day
  that also ran the mutation sweep five times, the integration suite four times and a new
  criterion-3 scorer. `run_selftests`, `integration`, `false_alarm_scorer` and both
  `mutation_sweep` variants now record; a FILTERED sweep is recorded under its own gate name,
  because it proves nothing about the entries it skipped and a ship bar that conflated the two
  would accept a 3-entry run as a full sweep. Registered as the `gate-ledger` gate (suite
  34 -> 35). Pinned `GL-1`.
  **The cap is now PER GATE, and that is the load-bearing part.** The original kept the last 200
  entries GLOBALLY, so simply letting other tiers write would not have worked - `run_selftests`
  runs many times an hour and the sweep runs once or twice a day, so the cheapest gate would
  evict the record of the most expensive one, which is exactly the tier whose last-run date is
  worth having.
  **Two limits stated rather than discovered later:** the file is gitignored, so it records what
  THIS MACHINE ran - it never reaches CI, does not survive a clone, and a ship bar built on it
  enforces local discipline rather than producing a shared, auditable record. And the first
  version of this change used a 60-per-gate cap, which permanently discarded 140 of the file's
  200 historical rows on its first run; the cap now matches the previous global bound so a
  migration can only ever add history.
- **`tools/score_false_alarms.py` + `tests/false_alarm_corpus.py` - criterion 3 is now MEASURED
  rather than asserted.** The previous machinery (`tools/score_corpus.py`) calls
  `slicing_offenders(hooks_dir)` and scores exactly one detector - 0 of the 16 hooks `install.py`
  wires. Every guard criterion 3 cares about reads a Claude Code EVENT PAYLOAD on stdin, so this
  runs each one through its real entry point on a corpus of ordinary correct work.
  Registered as the `false-alarm-scorer` gate (suite 33 -> 34). The gate is its `--selftest`,
  not the measurement: a known false alarm is a ledger row, and gating on the score would either
  keep the suite red or create pressure to delete the corpus entry that found it.
  **First measurement, 15 ordinary entries + 5 controls:** `piped_gate_guard`, `plan_defer_guard`,
  `numbers_match_on_write` and `timing_claim_guard` all **0.0%**, each with a firing control.
  Four Stop-class hooks report **UNMEASURED** - they have no control yet, and the tool refuses to
  print 0% for a hook it has not shown to be reachable, because silence from an unreachable hook
  and silence from a correct one are the same output.

- **Criterion 3's population is now FULLY measured: 11 of 11 wired hooks**, with a firing
  control each. Nine measure **0.0%**. The corpus holds 21 ordinary entries, but each hook's
  denominator is only the subset that DECLARES it (6, 2 or 1) - an entry is never counted
  against a hook the event does not route to, which would inflate every denominator and dilute
  every rate it prints. The two that fire -
  `memory_hygiene_guard` and the `stop_dispatcher` that surfaces it - do so **once per session
  and then go silent**, so the suite has **zero NAGGING false alarms**.
  The scorer now measures that distinction directly: every false alarm is re-run with the SAME
  state and session, because a guard that objects once is a NOTICE while one that repeats every
  turn is what actually gets a guard switched off. **This mattered immediately** - the
  `memory_hygiene_guard` notice measured 100% purely because the scorer gives each entry a fresh
  state dir, defeating the once-per-session marker that bounds it in real use. It was one step
  from being "fixed"; measurement over three consecutive turns (fires, silent, silent) refuted
  the defect. Recorded as a FINALIZED-EXCLUSION, not a scheduled fix.
  Also isolates `UNBLUFF_PROJECTS_ROOT` per entry - without it `memory_hygiene_guard` resolved
  against the maintainer's real `~/.claude/projects` and its result was not reproducible
  anywhere else.

### Fixed
- **`timing_claim_guard` was the only stateful hook that ignored `UNBLUFF_STATE_DIR`.** Its
  marker directory was a module-level constant overridden only inside its own selftest, so no
  harness could isolate it: the false-alarm scorer gave every corpus entry a fresh state dir,
  this hook ignored it, and one surviving marker silenced the control on every run after the
  first. Measuring it also WROTE INTO THE USER'S REAL `~/.claude/state`. Its default directory
  differed from its twins' as well (`~/.claude/state` against `~/.claude/hooks/state`). Now read
  at call time, like every other stateful hook.
  **This also corrects the fire ledger as evidence:** the dispatchers record each sub-hook's
  *exit code*, and this hook is ADVISORY - it reports on stderr and returns 0. A ledger reading
  `timing: 0` across 1252 invocations therefore means "never BLOCKED", not "never fired".
  Retiring a guard on that number would have been retiring it on a false zero.
- **`PGG-PS` - the piped-gate guard did not exist for PowerShell users.** It was registered
  `matcher: "Bash"`, so on Windows - where PowerShell is the primary shell - the guard never ran
  at all, and its vocabulary was POSIX-only besides. Two independent halves, fixed and pinned
  separately because they fail separately: the **wiring** (`install.py` now DERIVES its
  PreToolUse matcher from `piped_gate_guard.SHELL_TOOLS`, so a shell the hook is wired for and a
  shell it can reason about cannot drift apart) and the **vocabulary** (`dialect()` selects
  PowerShell semantics from the payload's `tool_name`).
  **The prescribed fix was treated as a hypothesis and REJECTED on measurement.** It named
  `Select-Object -First/-Last` as PowerShell "status-eaters". Measured across 15 consumers on
  2026-08-13, PowerShell is the OPPOSITE of sh: `$LASTEXITCODE` is set only by NATIVE
  executables, so `Select-String`, `Measure-Object`, `Out-File`, `Tee-Object`, `Sort-Object`,
  `Get-Unique` and `Select-Object -Last/-Skip` all PRESERVE a gate's exit code. Flagging `-Last`
  would have built a criterion-3 false alarm into the fix for a criterion-2 defect. Exactly two
  shapes destroy the evidence: `Select-Object -First/-Index`, which TRUNCATES the pipeline and
  tears the gate down before it finishes (measured `$LASTEXITCODE = -1` with the gate's own
  completion marker absent - strictly worse than sh, because there is no verdict to discard),
  and a NATIVE consumer such as `findstr` (measured: the gate's exit 3 became 0, a silent
  green). `sort` and `tee` are ALIASES for status-preserving cmdlets in PowerShell and are
  exempted there while remaining eaters in sh. Pinned `PG6`, `PG7`, `PG8`, `PGG-PS-1`; `PG4`
  repointed after the fix deleted the line it anchored.
- **`duplicate_registration_check` read any ALL-CAPS tuple of strings as a dispatcher fan-out
  roster.** It therefore believed `piped_gate_guard` dispatched to modules named `head.py`,
  `tail.py` and `sort.py`. That was wrong SILENTLY - phantom names collided with nothing - until
  one name appeared in a second vocabulary tuple in the same file, at which point the phantom
  was reported as "registered 2 times" and the hook whose whole job is to be silent on a clean
  install went red (integration scenario C2). Narrowed BEHAVIOURALLY: a file that never calls
  `import_module` cannot dispatch to one. The three synthetic fixtures were roster-only files
  that could never have run a sub-hook; they now carry a real dispatch call, so they still
  prove that NAMING does not decide detection. Pinned `DR-VOCAB`.

## [1.3.1] - 2026-08-08

The 1.3.1 notes below were written on 2026-07-31 and the release was never tagged. Eight further
days went into it, summarised here first.

### Added
- **`hooks/piped_gate_guard.py`** (PreToolUse, the suite's first) - blocks a Bash command that
  pipes a GATE into `head`/`tail`/`grep`, because the pipeline returns the last command's status
  and the gate's real result is discarded. It caught its own author four times in one session's
  history. **Known limit, scheduled:** it is registered `matcher: "Bash"` and is therefore blind
  to PowerShell.
- **`hooks/timing_claim_guard.py`** - flags a duration written as MEASURED with no control marker.
  Narrow by measurement, not by taste: it fires on 18 of 109 duration lines across the docs.

### Fixed
- **`hook_health_check` no longer reports a WORKING hook as broken.** A shell builtin such as
  `echo` - the canonical trivial hook, and a cmd.exe builtin with no `echo.exe` - was reported as
  "executable not on PATH" at every SessionStart. A guard that fires on a correct config gets
  disabled, which is worse than none.
- **A bracket in the install path no longer blinds every sweep in the repo.** `glob` treats
  `[...]` as a character class, so a clone in `unbluff-main[1]` - the name Windows gives a
  re-downloaded zip - made the weekly sweep verify **0 of 22 hooks**, print OK, and write a marker
  suppressing itself for another week. Fixed at all 13 call sites in 9 files.
- **The weekly sweep re-verifies again.** Its age stamp was recomputed on every write, so one
  permanently-skipping hook - no `git` on PATH is enough - kept the slice young forever and every
  other hook's recorded pass was never re-checked, behind an `[hook-health] OK` line.
- **`meta_audit_on_stop` no longer goes silent on an active plan.** Two separate defects: a
  bracketed allow-word anywhere in a line ("port the (closed-loop) controller") suppressed a
  genuine parked item AND removed it from the reported total; and any of the first five lines
  merely OPENING with "superseded" froze the whole file, so a plan whose header said "Superseded
  approaches are documented below" was skipped at every turn end.
- **`consistency-audit` reads Word text boxes.** The docx reader preferred python-docx, which
  cannot see `w:txbxContent`, so **installing the recommended optional dependency made the audit
  read less** - the same document reported CLEAN as `.docx` and flagged a fabricated number as
  `.md`. One reader now. **Known limit:** headers, footers and footnotes are still not read.
- **`no_regression` works on a shallow clone.** `actions/checkout` fetches one commit, and the
  gate read "the predecessor blob is unreachable" as "there is no predecessor", turning 11 of 11
  CI jobs red on a tree that was green locally. It now distinguishes the two, and CI fetches
  history so the gate does real work rather than silently verifying nothing.

### Changed
- `hook_health_check`'s selftest moved to a sibling module to keep the hook body under the
  800-line rule; the suite count is unchanged.
- `tests/test_integration.py` derives the expected hook-group set from `install.py` instead of
  asserting a hardcoded count, and compares SETS rather than a number.

### Known and scheduled, not silently omitted
`BUDGET-1` (the largest hook's selftest runs at 90-96% of its share on a loaded box),
`ENC-1` (hooks print under the process codepage), `PDF-1` (three PDF readers, agreement
unasserted), `PGG-PS`, `INT-WIN`, `INT-MUT`, `ENTRY-GUARD`, and the v1.4 disarm findings
`AR-8`..`AR-11`. All carry a phase in `docs/V131_REVIEW_PLAN.md`.

### Verification
Suite 32/32; integration 30/30; 139 mutation anchors across 138 entries in 30 files; the full
mutation sweep proves **136 of 138 on each platform, 2 posix-only, 0 unproven, 0 SURVIVED**, with
CI green across 14 jobs on 11 OS/Python combinations. The ship gate for this release was
independently reviewed rather than self-certified: that review **refuted** the first
classification, and the four user-facing HIGHs it confirmed are the fixes listed above.

---

## [1.3.1 notes as written] - 2026-07-31

From adjudicating 48 review findings that four adversarial passes had produced and **never
resolved** - neither confirmed nor refuted - because the review harness itself capped
verification at four findings per lens. Half of every finding those reviews produced was
discarded in silence while each pass reported the survivor count as the finding count.

### Added
- **`hooks/capped_report.py`** - one implementation of "cap a findings list without lying about
  it", shared by five hooks that had each grown their own. It encodes the distinction that
  matters: a DISPLAY cap is fine if it names what it hid, but a COLLECTION cap that `break`s
  destroys the total, and you cannot report what you dropped if you stopped counting. Its
  selftest walks every hook's **AST** for a list capped against a `MAX_*` constant outside the
  helper - structural rather than textual, because a grep-based guard would have to contain the
  pattern it forbids.
- **`tools/check_readme_fresh.py`** - the README pastes a `run_selftests` transcript as
  evidence; it claimed 18 while the suite ran 21. A stale paste reads exactly like a fresh one.
- **`mutations-windows` CI job** - some mutations are meaningful only on Windows, so an
  ubuntu-only mutation job proved them nowhere while printing a clean summary.

### Fixed
- **`meta_audit_on_stop`** - `count_unpushed` mapped "no upstream" (rc=128) to `0`, the same
  value as "clean and synced", so a branch created with `git checkout -b` and never pushed was
  byte-identical to a fully-pushed tree for its entire pre-first-push life. The marker regex
  `PARKED?` requires the E: it matched the non-word "PARKE" and missed the bare "PARK". A
  decision tag was matched anywhere in the line, suppressing "TODO: make sure the socket is
  closed". `_is_superseded` matched the word anywhere in the first five lines, skipping an
  ACTIVE plan that merely said "replaces PLAN_V2, which is superseded". The unpushed bullet was
  appended last, so the display cap discarded it first.
- **`stop_dispatcher` / `post_tooluse_dispatcher`** - a hook that CRASHED was recorded as
  `rc=0` in the fire ledger, making "checked and found nothing" and "raised and verified
  nothing" the same record. Fixed in both twins.
- **`hook_health_check`, `duplicate_registration_check`, `rate_prompt`** - malformed input
  (a non-string `command`, a `hooks` value of the wrong type, a non-string `prompt`) either
  raised and discarded the whole report, or silenced the checker entirely. A checker that goes
  quiet is indistinguishable from one reporting a clean bill of health.
- **`numbers_match_on_write`** - a config whose `sources` key never PARSED opted the project
  out silently; the lesson had been applied at the resolve layer but not the parse layer.
- **`plan_defer_guard` / `meta_audit_on_stop`** - `*plan*.md` is a substring match, so
  `explanation.md` was a plan file. Both hooks carried it; there is now one predicate.
- **`fast_test_on_stop` / `pre_push_gate`** - one option table for two gates clamped a push
  `timeout = 1800` to 600, making the remedy the gate's own error message prescribes a no-op.
  The two gates also keyed their SHARED state file on different directories (session cwd vs
  repo toplevel), so the advertised fast path never fired from a subdirectory.
- **`transcript_util`** - an image-ONLY prompt carries no text block, so the turn boundary
  slid back to the previous turn.
- **`tools/check_review_freshness`** - `units()` asked about 17 of 31 tracked `.py` files,
  omitting `tools/`, `tests/` **and itself**: the gate could not detect its own sabotage.
  Proved by committing `def backdoor(): return 42` into `tools/mutation_check.py` with
  `--release` still exiting 0. Now derived from globs intersected with `git ls-files`.
- **`run_selftests`** - five auxiliary gates were invoked under a bare `if os.path.exists(...)`,
  so renaming a tool silently deleted its gate.
- **`tools/mutation_check`** - copied only `hooks/`, so no fix in `tools/` or a top-level entry
  point could be mutation-tested at all. The harness that certifies every other fix as pinned
  had a blind spot covering its own directory.

### Changed
- `pre_push_gate.py` (1113 -> 561) and `fast_test_on_stop.py` (900 -> 539) are back under the
  800-line rule, with each `selftest()` in a sibling `*_selftest.py`.
- Several regression tests that could not fail for the property they named were rewritten: two
  asserted gates that a prior gate had already made unreachable, three carried an exemption but
  no marker, and one selftest printed its results into a redirected `StringIO`.

### Notes
Three defects were introduced by this release's own fixes and caught by the mutation harness
rather than by review: a fix silently disarmed another finding's test, a `cwd` restore ran too
early and stopped a hermeticity check from testing anything, and the file split rebound a
monkeypatched name in the wrong module. Each left the suite green. A behaviour-preserving
refactor whose safety net is the selftests is only as safe as the proof that the selftests
still bite.

## [1.3.0] - 2026-07-29

From consolidating two diverged copies of this suite that were both wired into a single
`settings.json` - eight hooks registered twice, none of them the same file.

### Added
- **`duplicate_registration_check` · SessionStart.** Reports any hook wired from more than one
  directory. Reads both declaration styles (`command` and `args`), expands dispatcher fan-out, and
  SHA-256s each target to distinguish a redundant duplicate from two diverged variants sharing a
  filename. Advisory: prints to stdout, always exits 0.
- **`pre_push_gate` · git pre-push.** Never push source your tests have not seen. Closes the window
  `fast_test_on_stop`'s debounce leaves open, enforced by git rather than by a model. Reuses
  `fast_test_on_stop`'s detection and state file so both gates agree on what is verified.
  `--install-global` points `core.hooksPath` at your hooks dir to cover every repo.
- **`close_skills_guard` · PostToolUse.** Verifies the close-audit skills ran at the *real* session
  end. Catches the temporal failure a Stop hook cannot: audits run at a premature close, the user
  says "continue", and the genuine ending skips them because they "already ran this session".
- **`usage_snip_prompt` · SessionStart.** Injects the budget instruction every session rather than
  relying on the model remembering to ask, and encodes that budget shapes scheduling, never quality.
- **Gate-run ledger.** `run_selftests.py` now appends each run to `docs/audits/gate_runs.json`
  (timestamp, count, failures, verdict). A gate that did not run leaves no trace in the code or
  the docs, so "were the gates green?" was previously unanswerable after the fact and reviewers
  reconstructed it from memory. Best-effort and gitignored: an unwritable ledger never fails a run.
- **`completeness-audit` skill now ships.** `close_skills_guard` names four skills in
  REQUIRED_SKILLS; the repo shipped three and `install.py` installed three, so a fresh install
  produced a hook permanently reporting a skill the user was never given - with nothing anywhere
  to explain it.
- **`tools/check_skill_deps.py`.** Asserts every skill a hook requires is both shipped in `skills/`
  and listed in `install.py`'s SKILL_NAMES. Nothing connected those three lists before. Gated in
  `run_selftests.py`; mutation-verified against both failure modes.
- **meta-review: read the gate ledger.** Check 4 now instructs reading a recorded gate-run ledger
  rather than reconstructing from memory - a gate that never ran leaves no trace in the plan or the
  code, so the check is blind without a record. Degrades correctly: where a project records nothing,
  gate status is UNVERIFIED rather than assumed.
- **`tools/check_python_floor.py`.** Parses every file at the version floor the README
  advertises (3.8). CI runs the suite on 3.8, which covers files CI *executes* - not `tools/`
  scripts or branches CI never takes, so a single modern construct could break the promise
  silently. Gated in `run_selftests.py`.
- **`tools/regen_example_settings.py`.** Derives `examples/settings.json` from `install.py`'s
  `desired_groups()` instead of hand-maintaining it, with a `--check` mode gated in CI. That file
  is what people copy when wiring by hand, and it had gone stale twice - a copy-paste install then
  silently omits hooks, which nothing errors on.
- **`tools/make_hook_screenshot.py`.** Renders real hook output to a terminal-style PNG, so README
  images are regenerable build artifacts rather than screenshots someone must remember to retake.
- **`tools/hook_divergence_report.py`.** Regenerates AST token deltas, SHA digests, dispatcher
  fan-out sets and `STATE_DIR` resolution for any two hook directories, so divergence figures in
  documentation are reproducible rather than asserted.
- **`plan_defer_guard`: dangling-home detection.** Flags a plan that claims every gap is homed while
  still promising future items ("-> new item"). Neither half is a defect alone; the pairing is.
- **`fast_test_on_stop`: no-gate notice.** A repo with no detectable test command was silently
  skipped, making it indistinguishable from a passing run. It now says so once per project, and only
  when source actually changed.

### Fixed
- **`run_selftests.py` silently skipped hooks missing from a hardcoded roster.** A hook shipping a
  full selftest printed `skip (no selftest)` while CI still reported all-green. Self-testability is
  now DETECTED via the actual `"--selftest" in sys.argv` dispatch; `SELFTESTABLE` becomes a floor,
  and a listed hook that loses its dispatch is an error rather than a silent skip.
- **`skills/consistency-audit/scripts/audit.py` crashed on every real run on Windows.**
  `UnicodeEncodeError` on cp1252 when printing `->`, at render time *after* the analysis completed,
  so the mechanical pass had never finished on a Windows machine. `--selftest` did not catch it
  because that path emits no non-ASCII. Both streams now reconfigure to UTF-8 with `errors="replace"`.
- **`hook_health_check` never read `args`.** For `{"command": "python", "args": ["x.py"]}` it verified
  the interpreter and never checked that the script existed. It now also reports duplicate registrations.
- **`install.py` shipped a hardcoded `REQUIRED_HOOKS` roster** that omitted newly added hooks.
- **Python <3.12 portability:** the no-gate message no longer interpolates a backslash inside an
  f-string expression (a `SyntaxError` before PEP 701).

- **`close_skills_guard` was unsatisfiable by construction.** Invoking a Skill makes the harness
  inject that skill's instructions back into the transcript as a `role="user"` entry whose first
  block is plain text - structurally identical to a real prompt. It was counted as "the last user
  message", so every skill invoked BEFORE it fell outside the window; and the LAST skill invoked
  always injects after its own invocation. The guard therefore reported all four skills missing
  however many actually ran. Fixed structurally: injected entries carry `isMeta` /
  `sourceToolUseID`. Pinned with a regression fixture, mutation-verified.

### Notes
- Verified empirically: a `SessionStart` hook exiting 2 does **not** block the session (probed with a
  filesystem marker confirming the hook actually executed). Stdout from a SessionStart hook is
  observably surfaced; stderr was not demonstrable, so advisory hooks should `print()`.

## [1.2.1] - 2026-07-21

Fixes from a three-lens self-audit (meta-review / completeness / consistency) of the v1.2.0 release.

### Fixed
- **consistency-audit skill now regression-gated.** Its `scripts/audit.py --selftest` (which covers
  all six drift classes) lives outside `hooks/`, so `run_selftests.py` and CI never ran it - the
  flagship script could regress green. `run_selftests.py` now also runs it (11 selftests total).
- **Drift class (F) is per-table, not all-or-nothing.** It was gated on *total* tables == 0, so a
  captioned-but-empty "Table N" next to any real table was missed. Now a promised table with no
  rendered body near its caption is flagged even when other tables exist.
- **Drift class (B) now detects bare embeds.** `find_figure_embeds` was defined but never called
  (`uncaptioned_embeds` was hardcoded `[]`), so an embedded image with no caption and no "Figure N"
  reference was missed. It is now wired in and reported.
- **numbers-match fire marker is keyed by (session, report path).** Previously one report firing
  suppressed a *different* report's fabricated number for the rest of the session. The source index
  is also cached by source mtimes so a clean report is not re-walked on every edit.
- **Hook/skill `SOURCE_EXTS` drift resolved + guarded.** The hook lacked `.log`; aligned with the
  skill and added an `H3` integration scenario asserting parity so they cannot silently diverge.
- **Docs reconciled with the code:** README verification block `22/22 -> 24/24` scenarios (and
  `10 -> 11` selftests); `SKILL.md` + `audit.py` intro "four drift classes" -> "six"; `install.py`
  docstring/help "10 pieces" / "the meta-review skill" (singular) / "four sub-hooks" generalized.
- **Follow-ups from an adversarial verification of the above:** drift class (F) now detects a
  table's full rendered extent, so a caption placed *below* a (tall) table is no longer
  false-flagged as missing; the numbers-match source-index cache keys on nanosecond mtime + size
  (a sub-second source edit can no longer reuse a stale index).
- **Dev experience:** committed `.claude/fast-test.cmd` so the `fast_test_on_stop` hook runs
  `run_selftests.py` for this repo instead of falling back to `pytest` (which collects nothing here
  and reported a false "no tests ran" at stop).
- **Refreshed `.github/ISSUE_TEMPLATE/bug_report.yml`** component dropdown (stale since v1.0.0): it
  now lists every current hook + skill, not just `meta-review`.
- **`examples/settings.json`** was missing the PostToolUse group (stale since v1.1), so a copy-paste
  install would have omitted `plan_defer_guard` + `numbers-match`; added the dispatcher entry so the
  example matches the four groups `install.py` wires. Also reworded SKILL.md's drift-class (F) prose
  to the per-table framing the code now uses.

## [1.2.0] - 2026-07-21

Extends the anti-bluffing theme from claims to numbers: a report can confidently cite a value that
no longer appears anywhere in the data it was computed from. `show_your_proof` catches an unverified
*claim*; this catches an unsourced *number*.

### Added
- **`numbers-match`** (PostToolUse: Edit|Write|MultiEdit) - when a report/output file is written,
  extracts the measurement-shaped numbers in the prose and checks each against the numeric values in
  a configured source-data folder, warning for any cited number with no match within tolerance.
  Opt-in per project via `.claude/number-sources.txt` (names the `sources` dir(s), optional `reports`
  globs / `tol` / `check_integers`); silent with no config. Checks only text deliverables
  (`.md`/`.txt`/`.tex`); skips cross-references, years, and (by default) bare integers to stay
  low-noise; relative tolerance (default 1%) absorbs normal rounding. Fires once per session;
  fail-silent, stdlib-only, `--selftest`.
- **`post_tooluse_dispatcher`** - a PostToolUse sibling of `stop_dispatcher`: runs `plan_defer_guard`
  and `numbers_match_on_write` in one process per edit (one spawn, not two), with a shared
  fire-ledger line tagged `event=PostToolUse`. Each sub-hook stays independently runnable and
  `--selftest`-able; the installer now points the single PostToolUse entry at the dispatcher.
- **`consistency-audit`** skill - the reasoning half that pairs with `numbers-match`, the way
  `source-coverage` pairs with `plan_defer_guard`. Ships a bundled, format-agnostic extractor
  (docx/pdf/tex/md) that surfaces six drift classes - numbers with no source match, figures
  embedded but never referenced, cross-references with no matching caption, claims whose
  supporting number is absent, unfilled bracketed placeholders (`[TABLE]`/`[TODO]`/`[insert ...]`),
  and tables the prose promises ("Table N") but never renders - which the model then adjudicates
  against the data. The installer now copies a skill's whole directory (SKILL.md + any bundled
  `scripts/`), not just SKILL.md.
- `run_selftests.py` + CI now cover both new hook modules; the integration test fires `numbers-match`
  end to end (H2), confirms `plan_defer_guard` still fires through the new dispatcher (H1), and
  checks the `consistency-audit` skill installs with its scripts (A7).

### Design
- The mechanical/reasoning split holds: the `numbers-match` hook surfaces the "number with no
  source" *state*; the `consistency-audit` skill carries the judgment a hook cannot - is an
  unmatched number drift, a derivation, or a definition, is a figure orphaned, is a claim actually
  supported and consistent across sections. A grep can only confirm a number is missing, never
  that it is wrong.

## [1.1.1] - 2026-07-15

### Fixed
- CI integration test (`install -> fire -> uninstall`): the `A2` scenario hard-coded "three unbluff
  groups" and only checked the `meta-review` skill, so it went red after v1.1 correctly added a 4th
  group (`plan_defer_guard` on PostToolUse) and a 2nd skill (`source-coverage`). The shipped hook,
  skill, and installer were all correct - only the test's own expectation was stale. Updated the group
  count, added coverage for the `source-coverage` skill, and added a scenario that fires
  `plan_defer_guard` end to end. All 21 integration scenarios now pass in CI.

  **CORRECTION, 2026-08-09.** This entry originally ended "pass on Linux/macOS/Windows". That
  was false the day it was written and stayed false for eight weeks: the three-OS matrix
  belonged to the `selftest` job, while `integration` was `runs-on: ubuntu-latest` and had
  never executed on any other platform. The claim is corrected in place rather than deleted -
  a changelog that quietly edits away its own false statements is precisely the failure this
  project exists to catch. The `integration` job gained the three-OS matrix in commit `eab22f0`
  (released as v1.4.0); before that, Linux was the only platform on which any integration
  scenario had ever run.

## [1.1.0] - 2026-07-15

Closes a real blind spot found in the field: a plan can claim "everything is covered" while
(a) hiding deferrals in lowercase decision-shaped language `meta_audit_on_stop` treats as prose,
and (b) never mentioning whole families of the source's requirements at all - which no grep can find.

### Added
- **`plan_defer_guard`** (PostToolUse: Edit|Write|MultiEdit) - on a plan/roadmap edit, flags the
  LOWERCASE "optional-forever" phrases that read like a decision but mean never (`-> park`,
  `on demand`, `wait for a concrete failing case`, `only on real user demand`, `deferred
  opportunistic`, `pick when value beats ...`). These slip past `meta_audit_on_stop` by design (its
  markers are uppercase `PARKED/DEFERRED/TODO` and its allow-tags whitelist `deprioritized`/`backlog`),
  so a badly-tagged deferral hides in plain sight. Fires once per session; exempts already-reclassified
  / finalized-exclusion lines; fail-silent, stdlib-only, `--selftest`.
- **`source-coverage`** skill - the reasoning half: verify a plan covers 100% of its authoritative
  source(s) by reading the SOURCE and reconciling every item to BUILT | SCHEDULED | FINALIZED-EXCLUSION,
  refreshing a coverage ledger. Catches the dangerous gap a hook never can - content the plan does not
  mention. (Motivating case: a plan asserting "essentially all built" had silently dropped an entire
  method family; one source-coverage pass surfaced ~40 uncovered items.)
- `install.py` now wires both new pieces on a fresh install (a 4th settings.json entry for
  `plan_defer_guard`; both skills copied); `run_selftests.py` + CI now cover the new hook.

### Design
- The two-halves guarantee: a **mechanical hook** catches optional-forever language the plan *contains*;
  a **reasoning skill** catches source items the plan *omits*. A grep can only find what is written down.

## [1.0.0] - 2026-07-13

First public release.

### Added
- **`show_your_proof`** (Stop) - nudges when the last reply claims success ("it works", "tests pass",
  "verified") but the turn ran zero tools.
- **`rate_prompt`** (UserPromptSubmit) - injects a standing instruction that makes Claude rate each
  prompt X/10 and act on a sharpened rewrite. Makes no extra model call (no API round-trip); the inline
  rating costs a few tokens. Off-switch via `CLAUDE_RATE_PROMPTS=off`; skips one-word confirmations and honors a
  "verbatim/literal" escape hatch.
- **`fast_test_on_stop`** (Stop) - runs the project's fast tests when source changed and feeds a
  failure back to Claude. Auto-detects `.claude/fast-test.cmd`, `package.json` test script, or pytest.
- **`meta_audit_on_stop`** (Stop) - surfaces parked/deferred/TODO plan lines that carry no decision
  tag, plus unpushed-commit count (surfaced, never pushed).
- **`memory_hygiene_guard`** (Stop) - flags rot in Claude Code auto-memory files (index bloat, live
  commit hashes, evolving state that belongs in a plan). Opinionated / optional.
- **`hook_health_check`** (SessionStart) - validates that configured hook commands resolve and
  weekly-runs each hook's `--selftest`.
- **`stop_dispatcher`** - runs the four Stop hooks in one process per turn-end and writes a rotating
  fire-ledger for observability.
- **`meta-review`** skill - the reasoning pass that acts on what the hooks surface.
- Cross-platform `install.py` - `--dry-run`, `--uninstall`, `--only`/`--without` selective install,
  automatic settings.json backup, and atomic writes (temp file + `os.replace`, never a half-written file).
- `run_selftests.py` plus a GitHub Actions workflow running every hook's `--selftest` on Linux, macOS,
  and Windows across Python 3.8-3.12; issue and pull-request templates.

### Design
- Every hook is fail-silent (any error exits 0 and never blocks you), fires at most once per session
  where relevant, is stdlib-only, makes zero network calls, and ships with its own `--selftest`.
