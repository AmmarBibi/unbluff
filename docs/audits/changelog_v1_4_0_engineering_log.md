# v1.4.0 - engineering log

The working notes that were `[Unreleased]` in `CHANGELOG.md` until 2026-08-23. Moved here
rather than deleted: they are the best record of WHY each change exists, and at ~1,200
characters per bullet they are maintainer-depth, not reader-depth. `CHANGELOG.md` carries
the reader-facing version and links here.

Nothing below is edited. Some of it describes work that later changed; the release notes
are the current statement, this is the trail.

---
### Added
- **`tools/mutation_check.py` can now verify a pin through a gate's ENFORCING invocation, and
  through its OUTPUT - so `main()` is reachable and a fix that only SAYS something is pinnable.**
  Every entry in the table verified via `<unit> --selftest`, so no line in any gate's `main()`
  could be reached by a mutation at all; the 2026-08-16 meta-review lists six behaviours as
  fixed-but-UNPINNED for that single shared reason, two of them FLOORS whose entire purpose is
  to stop a gate that read NOTHING from printing OK. The pinning tool carried the defect class
  it exists to catch.
  `{"mode": "enforcing"}` derives the argv from `AUX_GATES` by `ast.literal_eval` - never a
  literal in the entry, because an entry carrying its own argv would assert the mode it WISHED
  for and could not notice a flip, which is a declared roster standing in for a derived one. It
  fails CLOSED on zero or ambiguous registrations rather than falling back to `--selftest`.
  MEASURED while building it: 5 of the 9 enforcing gates went RED at BASELINE until `docs/audits`
  and `examples` joined the copy roster (the roster has to contain what the gates READ), and the
  scratch tree is now a real git repo - 0.47s - because `population()` prefers `git ls-files` and
  in a plain tempdir that branch can never be taken, so a mutation of it takes the fallback,
  returns an identical answer and reports SURVIVED for a reason unrelated to the test.
  `{"marker": ...}` is the second half and not a convenience: a fix whose whole content is SAYING
  SOMETHING changes no exit code. The marker must be present in the BASELINE output (or the probe
  is not measuring what it claims) and absent after mutating, and when declared it is the WHOLE
  verdict - `FS-CANNOTRUN` exits 1 both with its guard and without it, so an rc-first rule would
  have reported CAUGHT for both while pinning nothing.
  Four pins added - `SHIPBAR-FLOOR`, `FS-FLOOR`, `FS-GIT-DERIVE`, `FS-CANNOTRUN` - and each was
  verified to FAIL when the guard it names is deleted, not merely to pass. That probe paid for
  itself immediately: `SHIPBAR-FLOOR` as first written **could not fail**, because
  `SHIPBAR-DECL`'s heading-vs-rows guard absorbed it; silencing `declared_count` in the same
  mutation isolates the floor, and only then does the gate print `ship-bar: PASS` over a ZERO-row
  population without it. Two of the six behaviours remain unpinned and need different mechanisms
  (a selftest that injects a raising calibrator; a planted wiring fixture) - recorded as open,
  not reported as done.
  **Then an independent adversarial review of that commit (8 lenses, 36 agents, 28 findings, 24
  refuted) found four more defects in it, and all four were real.** Recorded because the author
  wrote both the mechanism and its only probe, which is the one case where more care does not
  help - the author's probe set and the author's blind spot are the same object.
  - **Widening the copy roster ARMED a check that had been vacuous.** `docs/audits` puts
    `review_runs.json` into every scratch tree, which makes `check_review_freshness`'s ambient
    ORPHAN assertion live - and that assertion runs BEFORE its "not a git checkout" skip. Its unit
    roster is `UNIT_GLOBS`, which covers `scripts/*.py`; `COPY_TREES` did not. So the gate's own
    prescribed `--record --unit scripts/make_demos.py` would have turned five unrelated pins into
    HARNESS ERROR, 25 minutes into a sweep - and recording exactly that is what the next task's
    sweep of never-reviewed files does. Fixed by adding `scripts`, and GENERALLY by
    `check_mutation_anchors.roster_gaps()`, which DERIVES the copy roster's adequacy from
    `UNIT_GLOBS` rather than trusting two hand-kept lists to stay in step. Verified against the
    shipped roster: it names `scripts/*.py` before the fix and is silent after. Pinned `ROSTER-1`.
  - **The enforcing/selftest predicate was written as exact tuple equality, twice.** Every gate
    dispatches on MEMBERSHIP (`"--selftest" in sys.argv`), so `("--selftest", "")` was skipped by
    `enforcing_mode_gaps` AND accepted as enforcing by `enforcing_argv`, while the target ran its
    selftest - a one-token disarm of the mode control, reintroduced by the commit that was fixing
    the mode control. The rule now lives once, in `tools/gate_modes.py`, imported by both. Every
    pre-existing fixture used exactly `("--selftest",)`, so no case could tell the two spellings
    apart; three selftest-shaped-but-not-equal rows now do. Pinned `MODE-3`.
  - **`make_git_repo` leaked its scratch trees silently.** `git add -A` writes loose objects at
    mode 0444, `shutil.rmtree(..., ignore_errors=True)` cannot unlink them on Windows, and the
    error was discarded. MEASURED: 21 orphaned `unbluff-mut-*` trees, each holding nothing but a
    1.1 MB `.git`, 23 MB total - accumulated behind a clean summary line. `rmtree` now clears the
    read-only bit and retries, `purge_scratch()` sweeps what earlier runs left, and what still
    cannot be removed is PRINTED. "Do not fail" and "do not say" are different decisions.
- **`enforcing_mode_gaps()` in `run_selftests.py` - a gate's registered MODE is now DERIVED and
  checked, not trusted.** `AUX_GATES`' third element is the argv each gate is invoked with, and
  until now nothing anywhere read it. Registering a gate `("--selftest",)` instead of `()` makes
  it check its own logic and apply to nothing, while the suite, CI, `readme-fresh` and the
  mutation sweep all stay green - `readme-fresh` because a mode flip changes no cardinality, and
  the sweep because every mutation is verified via `<unit> --selftest`, which is identical in
  both modes. That is not hypothetical: it happened to `file-size` and `ship-bar` on 2026-08-14,
  was fixed BY HAND in both, and no control was built. An independent adversarial review
  (`wf_f63b9ccf-816`, 46 agents, 41 findings produced, 40 confirmed) reproduced it on a clean
  clone in ONE TOKEN - planting a 900-line offender and getting `file-size: OK` where the
  enforcing gate returns rc 1.
  The check reads each target's AST rather than its argv tuple: a row needs an explicit
  adjudication when it is registered `("--selftest",)`, the target defines a `selftest`, AND the
  target's `main()` can fail. "Can fail" is deliberately FAIL-SAFE - a `main` counts as able to
  fail unless EVERY exit path is a literal 0, because a first version counted only non-zero
  literal returns and claimed `mutation-anchors` and `install-guard` had no failure path at all.
  `SELFTEST_IS_THE_GATE` carries the reason for each legitimate case and is checked in BOTH
  directions, so an adjudication cannot rot into cover. Pinned by `MODE-1` (the one-token flip,
  against the live table) and `MODE-2` (the detector disarmed, against a synthetic tree).
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
- **`hook-provenance` was registered in `--selftest` mode, so its enforcing half ran nowhere.**
  Found by the 2026-08-16 review, then flagged by the new mode control on its first execution -
  a THIRD instance of the 08-14 defect, which the 08-14 close ritual did not catch. Its
  measurement - the half that reads git's actual wiring on this machine - was invoked by
  nothing: not the suite, not CI, not the push path. Both halves are registered now
  (`hook-provenance` enforcing, plus the paired `hook-provenance-selftest`, adjudicated in
  `SELFTEST_IS_THE_GATE`), and the enforcing run examines 56 hook commands where previously it
  examined none.
- **`hook_divergence_report` reported a broken parse and an inapplicable machine identically.**
  A zero denominator returned 0 with the same NOTE whether no wiring surface existed (a fresh CI
  checkout - genuinely inapplicable) or surfaces WERE read and produced no hook command at all
  (a broken parse wearing a clean result). Only the second is a defect; it now fails and names
  the surfaces it read.
- **`transcript_util`'s twin-classifier exemption followed the data.** It named
  `tools/mutation_check.py`; when the `MUTATIONS` table moved, the transcript vocabulary went
  with it, leaving the old entry as dead cover while the new file tripped the rule unexempted.
  The gate caught both halves in one run - the USED check earning its keep exactly as its own
  note predicted.

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

### Changed
- **`tools/mutation_check.py` split 1415 -> 377 lines**, with the `MUTATIONS` table moved to
  `tools/mutation_entries_a.py` (541) and `tools/mutation_entries_b.py` (538). Those four
  figures are the measurement **at the moment of the split**, and this session's own
  consistency audit caught them going stale within hours: later work added the
  `sys.path.insert` re-export fix and eleven more mutation entries, so the current sizes are
  387 / 541 / 604 and the table now holds 211 entries with 212 anchors, not the 200/201 the
  split preserved. Both readings are true of different instants, which is exactly why the
  instant is now stated - an undated measurement presented as a current fact is the drift this
  project exists to catch, and it does not stop being that when the author is the one drifting.
  This honours the
  standing instruction recorded in `file_size_baseline.json` on 2026-08-14 - "the next growth
  should be preceded by the split, not by another re-record" - rather than repeating the
  re-record loophole to fund growth in the very file that documents the loophole. The cut is at
  an entry boundary and order is unchanged, so all 200 entries and 201 anchors are preserved and
  the sweep iterates an identical list. `mutation_check.py` is removed from the offender
  baseline entirely, which TIGHTENS the ratchet. The re-export carries an explicit
  `sys.path.insert` rather than a bare sibling import, so `python -m tools.mutation_check` no
  longer silently empties the table - the review found that exact invocation-dependent-import
  defect elsewhere in the repo, and introducing a fresh instance of it to save two lines would
  have been a poor trade.
