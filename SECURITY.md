# Security

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository:
**[Security → Report a vulnerability](https://github.com/AmmarBibi/unbluff/security/advisories/new)**.

That channel is private until an advisory is published. Please do not open a public issue for
anything that lets one repository's contents run code on someone else's machine.

Expect an acknowledgement within a week. This is a single-maintainer project, so there is no
formal SLA beyond that and pretending otherwise would be the kind of claim this repo exists to
object to.

## The execution model, stated plainly

unbluff runs your project's test command. That is the entire point of it, and it means the
security question is not "does unbluff execute code" - it does - but **whose code, and on whose
say-so**. There are two paths and they answer that differently, on purpose.

### At turn end (the Stop hook)

Auto-detect is ON. When source files change, the hook resolves a command in this order:

1. `.claude/fast-test.cmd` in the project - whatever you wrote there
2. `package.json` → `scripts.test` → `npm test --silent`
3. a pytest project → `"<python>" -m pytest -x -q`

Steps 2 and 3 execute **code from the repository**. `scripts.test` is an arbitrary shell command,
and pytest imports every `conftest.py` before it collects a single test - so a repository
containing nothing but a hostile `conftest.py` is enough.

This is allowed because opening Claude Code in a directory already implies enough trust to run
its tests - the agent is running commands there with your approval either way. What was missing
was not consent, it was **disclosure**: you never saw what would run. So before the first
auto-detected run in a project, the hook prints the actual untrusted surface to stderr - the
`scripts.test` body, or the `conftest.py` files that will be imported. Not the wrapper string,
which tells you nothing.

The notice is keyed on the disclosed content, not on the project. If a repository changes what
`scripts.test` runs, you are told again.

**To control it:** put your own command in `.claude/fast-test.cmd`, or remove the Stop hook from
`~/.claude/settings.json`.

### At push time (`pre-push`)

Auto-detect is **OFF** unless the repository opted in.

`--install-global` sets git's `core.hooksPath` machine-wide, so the gate fires in *every*
repository on the disk - including ones you cloned to read and never opened in Claude Code.
Nothing there implies consent, so nothing is auto-detected. Such a repository must say what to
run, explicitly:

```
echo "<your test command>" > .claude/pre-push.cmd
```

A repository where you ran `python hooks/pre_push_gate.py --install <repo>` keeps auto-detect:
that install is the consent, and the shim it writes is the record of it. Presence of *any*
`pre-push` hook is not enough - a husky or lefthook hook is somebody else's file, not your
opt-in.

When the gate declines for this reason it says so and **allows the push**. It never blocks on
"you did not configure me".

## What unbluff does not do

Split by whether a machine checks it, because "we don't do X" is worth very little when the only
thing stopping X is that nobody has done it yet. This project's own README once carried "no
network" as an unenforced badge, and a hook that opened a socket would have passed every gate.

**Enforced - a gate goes red if it stops being true:**

- **No network.** No telemetry, no update check, no analytics. `tools/check_no_network.py` fails
  the build on any AST-visible socket, HTTP client, or subprocess spawn of a network tool, over a
  DERIVED file population (59 files as of 2026-08-23, 0 reaches). It flagged itself on its first
  run and was narrowed with two negative controls, so it cannot silently revert to vacuous.

**Asserted but NOT yet enforced - true as far as the author knows, checked by nobody:**

- **No writes outside** the repository being checked and `~/.claude/hooks/state/`.
- **No credential access.** Nothing reads your keychain, environment secrets, or git credentials.

Those two are labelled rather than quietly listed alongside the first, because an unenforced claim
sitting next to an enforced one borrows its credibility. Both are scheduled as **#43**; until the
gates exist, treat them as the author's word and not as a guarantee. If you find a counterexample,
that is exactly what the reporting channel above is for.

## Bypass

`git push --no-verify` skips the push gate. It is git's own escape hatch and unbluff does not try
to close it - a gate you cannot get past when you need to is a gate people uninstall.
