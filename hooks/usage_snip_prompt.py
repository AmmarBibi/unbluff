"""usage-snip-prompt (Claude Code SessionStart hook) - make the budget question mechanical.

Claude has NO tool that can read the user's subscription quota (`/cost-report` reads a local token
log, not the plan). The only source is a snip the user pastes. That makes the ask depend on Claude
remembering a memory file - which is exactly the kind of thing that gets forgotten on the session
where it matters. This hook injects the instruction every session instead.

Deliberately CONDITIONAL: a hook cannot tell a one-line question from a 2M-token workflow, so it
tells Claude to ask only when the session actually turns heavy. That keeps trivial sessions quiet
while guaranteeing the ask lands before anything expensive.

Carries the hard rule with it: quota may shape SCHEDULING, never QUALITY. If the right tier is
exhausted, the answer is "wait for the reset" - never a weaker model, never a quietly smaller task.

Exits 0 always; stdout becomes additional session context. Run with --selftest.
"""

from __future__ import annotations

import json
import sys

NOTICE = """[usage-budget] You cannot read this user's subscription quota - no tool exposes it. \
The only source is a usage snip they paste.

BEFORE any of the following, ask them to paste their current usage limits (Opus 5 + Fable 5 weekly):
  - a Workflow / multi-agent fan-out, or any task you would flag as heavy
  - recommending or switching models
  - a plan whose steps span more than one model tier
Skip the ask for ordinary short sessions - do not nag.

HARD RULE once you have it: budget shapes SCHEDULING, never QUALITY. If a task genuinely needs a \
tier that is exhausted, say "wait for the reset" and give the timing. NEVER propose a weaker model \
for work that deserves a stronger one, and never quietly shrink a task to fit what is left. \
Real savings live in Workflow per-agent opts.model (cheap tier on high-volume fan-out, strong tier \
on synthesis), not in downgrading the main session."""


def main() -> int:
    try:
        json.load(sys.stdin)  # payload unused; consume it so the hook never blocks on stdin
    except (ValueError, OSError):
        pass
    sys.stdout.write(NOTICE + "\n")
    return 0


def selftest() -> int:
    fails = []
    if "wait for the reset" not in NOTICE:
        fails.append("notice lost the wait-for-reset rule")
    if "never" not in NOTICE.lower() or "QUALITY" not in NOTICE:
        fails.append("notice lost the quality-is-never-degraded rule")
    if "do not nag" not in NOTICE:
        fails.append("notice lost the conditional guard - it would fire on trivial sessions")
    # malformed / empty stdin must still exit 0 and still emit the notice
    import io
    real_in, real_out = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO("not json"), io.StringIO()
    try:
        rc, out = main(), sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = real_in, real_out
    if rc != 0:
        fails.append(f"must exit 0 on malformed stdin, got {rc}")
    if "usage-budget" not in out:
        fails.append("notice not emitted on malformed stdin")
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
