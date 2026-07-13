<!-- Thanks for contributing! Keep the invariants below - they are what make the suite safe to run every turn. -->

## What this changes


## Invariant checklist (every hook must keep these)

- [ ] **Fail-silent** - any unexpected error exits `0`; never blocks or crashes a session
- [ ] **Mechanical** - no LLM calls, no network, no telemetry
- [ ] **Stdlib-only** (Python 3.8+)
- [ ] **Conservative** - prefers silence over a false positive
- [ ] **Self-testing** - `--selftest` fixtures added/updated and passing (`python run_selftests.py`)
- [ ] Updated `CHANGELOG.md`, and (if adding a hook) `install.py` + `examples/settings.json` + the README table
