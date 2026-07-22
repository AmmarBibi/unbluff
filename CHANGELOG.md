# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

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
  `plan_defer_guard` end to end. All 21 integration scenarios now pass on Linux/macOS/Windows.

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
