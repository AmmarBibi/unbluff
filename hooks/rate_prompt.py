"""UserPromptSubmit hook: inject the "rate every prompt" standing instruction.

Behaviour:
  - Trivial acknowledgements (yes / ok / push / continue / approved / ...) are skipped, so
    one-word confirmations do not each get an X/10.
  - A "verbatim / use my exact words" escape hatch injects a literal-mode instruction instead.
  - Off-switch: set CLAUDE_RATE_PROMPTS=off (e.g. in ~/.claude/settings.json "env") to disable
    without editing or removing the hook.

Local and deterministic - it makes NO extra model call (no API round-trip); it prints a standing
instruction to stdout (which Claude Code adds to context) and the main model does the rating and
rewrite inline (a few tokens). Prints nothing when skipped. Run with --selftest to verify the routing logic.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

# Trivial acknowledgements - nothing to rate on a one-word confirmation.
_TRIVIAL = re.compile(
    r"^(y|n|k|kk|ok|okay|yes|yep|yeah|ya|no|nope|nah|sure|go|go ahead|do it|continue|resume|"
    r"next|push|pull|commit|stop|done|wait|hold on|thanks|thank you|ty|tysm|proceed|run it|"
    r"apply( both| all)?|approve[d]?|accept[ed]?|good|great|nice|perfect|cool|right|correct|"
    r"yes please|sounds good|lgtm|ship it)[.!\s]*$",
    re.IGNORECASE,
)

# Escape hatch: the user asked for their exact words - act verbatim, no rewrite.
_LITERAL = re.compile(
    r"\b(literal(?:ly)?|as written|exactly as i (?:said|wrote|asked)|verbatim|as-is|word for word|"
    r"do ?n'?t rewrite|no rewrite|use my (?:exact|literal)|my exact words)\b", re.IGNORECASE)

LITERAL_INSTRUCTION = (
    "Standing instruction (auto-injected): The user asked you to act on their EXACT words this "
    "turn - do NOT rewrite, reinterpret, or substitute an improved version. Still begin with a "
    "one-line rating (X/10), then carry out the literal prompt exactly as written."
)

RATE_INSTRUCTION = (
    "Standing instruction (auto-injected): Begin your reply with a one-line rating (X/10) of this "
    "prompt. Then ALWAYS show the improved '10/10' version of the prompt as the only content inside "
    "a fenced code block (triple backticks) on its own, with no rating, commentary, or extra "
    "backticks inside that block. Then ACT ON THAT IMPROVED VERSION rather than the literal wording "
    "- but the rewrite may ONLY sharpen and clarify the user's intent; it must never add scope, "
    "steps, or assumptions the user did not ask for. If the prompt is already near-optimal, say so "
    "briefly and proceed. For ambiguous, costly, or irreversible requests, show the improved prompt "
    "and confirm it with the user before acting."
)


def _as_text(prompt):
    """Coerce a payload 'prompt' field to text.

    [P13 C2] A non-str shape (None, a list of content blocks, a dict, a number) used to reach
    .strip() and raise an uncaught AttributeError. Every other stdin hook in this suite guards
    its payload; this one did not, so a shape change upstream would take it down rather than
    make it quiet - the opposite of the project's own "a broken hook must never block the
    user" rule.
    """
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):   # content-block form: [{"type": "text", "text": ...}, ...]
        return "".join(b.get("text", "") for b in prompt
                       if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def instruction_for(prompt):
    """Return the standing-instruction string to inject, or None to stay silent. Pure function."""
    prompt = _as_text(prompt).strip()
    if not prompt or _TRIVIAL.match(prompt):
        return None
    if _LITERAL.search(prompt):
        return LITERAL_INSTRUCTION
    return RATE_INSTRUCTION


def main():
    # Off-switch via env var (default on).
    if os.environ.get("CLAUDE_RATE_PROMPTS", "").strip().lower() == "off":
        return 0
    try:
        prompt = json.load(sys.stdin).get("prompt") or ""
    except Exception:
        prompt = ""
    text = instruction_for(prompt)
    if text:
        sys.stdout.write(text)
    return 0


def selftest():
    fails = []

    def check(name, cond):
        if not cond:
            fails.append(name)
        print(f"SELFTEST {'OK' if cond else 'FAIL'}: {name}")

    # trivial acknowledgements -> silent
    for t in ("ok", "yes", "push", "lgtm", "sure", "do it", "thanks", "proceed"):
        check(f"trivial {t!r} -> None", instruction_for(t) is None)
    # empty -> silent
    check("empty -> None", instruction_for("   ") is None)
    # verbatim escape hatch -> literal instruction
    for t in ("do X, verbatim", "use my exact words here", "don't rewrite: run the thing"):
        r = instruction_for(t)
        check(f"literal {t!r}", r is not None and "EXACT words" in r)
    # substantive prompt -> rate instruction
    r = instruction_for("fix the login bug in src/auth.py and add a test")
    check("substantive -> rate", r is not None and "one-line rating (X/10)" in r)

    # [P13 C2] non-string payload shapes must be survivable, not fatal
    for bad in (None, 5, {"a": 1}, [], [{"type": "image"}]):
        try:
            r = instruction_for(bad)
        except Exception as e:
            fails.append(f"instruction_for({bad!r}) raised {e!r}")
        else:
            check(f"non-string prompt {bad!r} -> None", r is None)
    r = instruction_for([{"type": "text", "text": "fix the login bug and add a test"}])
    check("content-block prompt is read, not dropped",
          r is not None and "one-line rating (X/10)" in r)

    # main() integration: off-switch silences even a substantive prompt.
    # [P13 C3] The OK/FAIL lines of these two checks used to be written into the StringIO that
    # stdout was redirected to, so the only two integration checks in this selftest reported
    # nothing at all - a failure here was invisible except as a count at the very end.
    _real_in, _real_out = sys.stdin, sys.stdout
    try:
        os.environ["CLAUDE_RATE_PROMPTS"] = "off"
        sys.stdin = io.StringIO(json.dumps({"prompt": "fix the parser"}))
        sys.stdout = io.StringIO()
        main()
        _off_output = sys.stdout.getvalue()
        sys.stdout = _real_out
        check("off-switch -> no output", _off_output == "")
        sys.stdout = io.StringIO()
        # on: substantive prompt emits the rate instruction
        os.environ.pop("CLAUDE_RATE_PROMPTS", None)
        sys.stdin = io.StringIO(json.dumps({"prompt": "fix the parser bug and confirm"}))
        sys.stdout = io.StringIO()
        main()
        _on_output = sys.stdout.getvalue()
        sys.stdout = _real_out
        check("on -> emits instruction", "one-line rating (X/10)" in _on_output)
    finally:
        sys.stdin, sys.stdout = _real_in, _real_out

    print("SELFTEST: ALL OK" if not fails else f"SELFTEST: FAILED ({len(fails)})")
    return 0 if not fails else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())
