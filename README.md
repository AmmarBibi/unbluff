# unbluff

**Stop Claude Code from bluffing.** A hook that catches it claiming *"it works"* when it ran nothing to check - plus a small suite of fail-silent self-verification hooks around it.

*An independent, unofficial community project. Not affiliated with or endorsed by Anthropic. Designed and directed by the author, implemented with AI assistance.*

[![CI](https://github.com/AmmarBibi/unbluff/actions/workflows/selftest.yml/badge.svg)](https://github.com/AmmarBibi/unbluff/actions/workflows/selftest.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Zero deps](https://img.shields.io/badge/dependencies-none%20(stdlib)-brightgreen.svg)](#design-principles)
[![Zero network](https://img.shields.io/badge/network-none-brightgreen.svg)](#design-principles)

Claude Code will happily tell you *"it works, tests pass"* right after editing three files and running nothing. **`show-your-proof`** catches exactly that, mechanically, the moment it happens - with zero dependencies, zero network calls, and zero LLM cost.

![show-your-proof catching an unverified success claim, then Claude actually running the test](docs/demo.gif)

```text
> Assistant: Fixed the race condition - it works now.

[show-your-proof] The last reply claims success ('it works') but this turn ran no
tools. Show verification (run the test/build/command) or soften the claim to what
was actually verified.
```

Claude gets the note and either runs the verification or downgrades the claim to what it actually checked. It fires **at most once per session**, only on a tight list of success phrases ("it works", "tests pass", "verified", "build passes", ...), and skips anything negated ("not verified yet"). Silence is the default; a false nudge is the only failure mode it works hard to avoid.

> It is not judging whether the claim is *true* - that is the model's job. It only surfaces the state "claimed success + ran nothing," which is exactly the state you want flagged.

## How this compares

| Project | What it is for |
|---------|----------------|
| [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) | Learn every hook event (a comprehensive reference) |
| [claude-code-prompt-improver](https://github.com/severity1/claude-code-prompt-improver) | A model-call prompt rewrite (adds latency, worth it for many) |
| **unbluff** | Mechanical, `$0`, zero-latency self-verification you install and forget |

The wedge: these hooks make **no model calls**, add **no latency**, send **nothing over the network**, and fail silent. They just catch a class of mistake at turn-end.

## The suite

`show-your-proof` is the headline. The rest are optional companions in the same spirit:

| Hook | Event | What it does |
|------|-------|--------------|
| **`show_your_proof`** | Stop | Nudges "it works / tests pass" claims made with zero tool runs. |
| `fast_test_on_stop` | Stop | When source changed, runs your fast tests and feeds failures back to Claude. |
| `meta_audit_on_stop` | Stop | Surfaces parked / deferred / TODO plan lines with no decision tag, plus unpushed-commit count. |
| `memory_hygiene_guard` | Stop | Flags rot in Claude Code auto-memory files (opinionated / optional). |
| `hook_health_check` | SessionStart | Verifies your hooks resolve and weekly-runs every hook's self-test. |
| `stop_dispatcher` | Stop | Runs the four Stop hooks in **one** process per turn and logs a rotating fire-ledger. |
| `rate_prompt` | UserPromptSubmit | *(bonus)* Makes Claude rate your prompt X/10 and act on a sharpened rewrite. See [below](#bonus-rate_prompt). |
| `meta-review` | *skill* | The reasoning pass that acts on what the hooks surface. |

## See it in action

**`fast_test_on_stop`** - when source changed, your fast tests run at turn-end and a failure comes straight back to Claude:

![fast_test_on_stop running the tests and catching a regression](docs/fast-test.gif)

The other Stop hooks surface their state as a line or two (real output shown):

**`meta_audit_on_stop`** - parked/deferred work with no decision tag, plus unpushed commits:

![meta_audit_on_stop output](docs/meta-audit.png)

**`memory_hygiene_guard`** - rot in Claude Code auto-memory files:

![memory_hygiene_guard output](docs/memory-hygiene.png)

**`hook_health_check`** - a health line at session start:

![hook_health_check output](docs/hook-health.png)

**`stop_dispatcher`** - runs all four Stop hooks in one process and logs a fire-ledger:

![stop_dispatcher fire-ledger](docs/stop-dispatcher.png)

## Install

```bash
git clone https://github.com/AmmarBibi/unbluff.git
cd unbluff

python install.py --dry-run   # preview exactly what will change
python install.py             # apply (backs up ~/.claude/settings.json first, writes atomically)
```

Then restart Claude Code (or start a new session). To reverse everything:

```bash
python install.py --uninstall
```

Want only some of it? The install is not all-or-nothing:

```bash
python install.py --only stop_dispatcher     # just the Stop-time verification hooks (incl. show-your-proof)
python install.py --without rate_prompt      # everything except the prompt rater
```

The installer references the hooks **in place**, so `git pull` updates them with no re-install.

### Try just the hero, by hand

Prefer to wire one hook and nothing else? Add this to `~/.claude/settings.json` (absolute path to your clone), and skip the rest:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "python \"/ABSOLUTE/PATH/TO/unbluff/hooks/show_your_proof.py\"" }
        ]
      }
    ]
  }
}
```

`show_your_proof.py` runs standalone - it does not need the dispatcher. See [`examples/settings.json`](examples/settings.json) for the full wiring.

## Per-project fast tests

`fast_test_on_stop` auto-detects `pytest` or a `package.json` test script. To point it at a specific fast subset, drop a `.claude/fast-test.cmd` in your project:

```text
# first non-comment line is the command; optional timeout/debounce (seconds)
timeout=120
debounce=600
pytest -x -q tests/unit
```

## The `meta-review` skill

Hooks are mechanical - they can *surface* state but cannot decide what is missing. `meta-review` is the other half: a deliberate reasoning pass (run at milestones or "am I missing anything?") that audits for parked-but-unscheduled work, instance-only fixes that lack a durable mechanism, optimization gaps, and things silently missing, then schedules or fixes each. The hooks find the smoke; the skill decides whether there is a fire.

![meta-review example report](docs/meta-review.png)

## Design principles

Every hook in this suite:

- **Fails silent.** Any unexpected error exits `0`. A broken hook can never block or crash your session.
- **Is mechanical.** Regex, counting, and file-existence checks only - no LLM calls, no network, no telemetry.
- **Is stdlib-only.** No dependencies. Python 3.8+.
- **Fires at most once per session** (where relevant) and is conservative - it would rather stay silent than nag.
- **Self-tests.** Run `python hooks/<name>.py --selftest`; fixtures never touch real state.

```bash
# verify the whole suite (this is exactly what CI runs)
python run_selftests.py
```

## Bonus: `rate_prompt`

A separate idea from the self-verification hooks, bundled because it is in the same "make Claude help itself" spirit. There are excellent prompt-improver hooks that call a model to rewrite your prompt and pay 30-50s of latency for it. `rate_prompt` takes the opposite approach: it makes **no model call of its own.** It injects a one-line standing instruction, and the model you are already talking to does the rating and rewrite inline, for free, instantly:

![rate_prompt scoring a prompt and rewriting it inline](docs/rate-prompt.gif)

It is opinionated and always-on, so it is a *bonus*, not the headline. It skips one-word confirmations ("ok", "yes", "push"), honors an escape hatch (say "verbatim" / "use my exact words" and it will not rewrite), and has an off-switch:

```bash
# in ~/.claude/settings.json "env", or your shell
CLAUDE_RATE_PROMPTS=off
```

Not into it? Install with `--without rate_prompt`.

## Known limitations

Honesty beats surprise:

- **`show_your_proof` keys off phrases, not truth.** It matches success-claim wording, so it can occasionally nudge on a non-code message that happens to say "it works." It is deliberately conservative and fires once per session, so the worst case is a single stray line - but it is a heuristic, not an oracle.
- **`rate_prompt` adds a rating block to every substantive reply.** Some people love the discipline; some find it noisy. That is what the off-switch (and `--without rate_prompt`) is for.
- **`memory_hygiene_guard` is opinionated.** It assumes the Claude Code auto-memory convention (`~/.claude/projects/<project>/memory`). If you do not use auto-memory, it simply stays silent.

## Requirements

- [Claude Code](https://code.claude.com/) with hooks enabled.
- Python 3.8+ on your PATH (the installer embeds the interpreter it was run with).
- CI runs the self-tests on Linux, macOS, and Windows across Python 3.8-3.12.

## FAQ

**Is this affiliated with Anthropic?** No. It is an independent, unofficial community project that targets Claude Code's public hooks interface.

**Did you write this by hand?** It was designed and directed by me and implemented with AI assistance, like most tooling people ship in 2026. The design decisions - the fail-silent invariants, the once-per-session guards, the test fixtures - are the point; the typing was the easy part.

**Will it slow Claude down?** No meaningful latency. `rate_prompt` makes no model call. The Stop hooks run once at turn-end in a single process; `fast_test_on_stop` only runs your tests when source changed and is debounced.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The one rule that matters: keep the hooks fail-silent, mechanical, stdlib-only, and self-testing.

## License

[MIT](LICENSE) (c) 2026 [AmmarBibi](https://github.com/AmmarBibi)

If this saved you from a confidently-wrong "it works," a star is appreciated.
