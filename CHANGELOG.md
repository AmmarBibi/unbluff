# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this project uses [SemVer](https://semver.org/).

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
