# Contributing

Thanks for your interest in improving `unbluff`.

## Principles (please keep these)

These are the invariants that make the suite safe to run on every turn. A change that breaks one of
them will not be merged:

1. **Fail-silent.** A hook must never block or crash the user's session. Any unexpected error exits `0`.
2. **Mechanical, not smart.** Hooks do regex/counting/existence checks only - no LLM calls, no network,
   no judgment. Judgment lives in the `meta-review` skill.
3. **Stdlib-only.** No third-party dependencies. Python 3.8+.
4. **Conservative.** When in doubt, stay silent. A missed nudge is fine; a false nudge on every turn is
   not.
5. **Self-testing.** Every hook keeps a `--selftest` with pure-function fixtures that never touch real
   state. New behavior needs new fixtures.

## Before you open a PR

```bash
# Run every hook's selftest (this is exactly what CI runs)
python run_selftests.py
```

- Keep each file focused and under ~400 lines.
- Update the `CHANGELOG.md` under an "Unreleased" heading.
- If you add a hook, wire it into `install.py`, `examples/settings.json`, and the README table.

## Reporting bugs

Open an issue with: your OS, Python version, the hook involved, and the smallest repro you can manage
(ideally a failing `--selftest` fixture).
