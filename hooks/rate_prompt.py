"""UserPromptSubmit hook: inject the "rate every prompt" standing instruction.

Refinements over a naive inline printf:
  1. Trivial acknowledgements (yes / ok / push / continue / approved / ...) are skipped, so
     one-word confirmations do not each get an X/10.
  2. An env off-switch: set CLAUDE_RATE_PROMPTS=off (e.g. in ~/.claude/settings.json "env")
     to disable without editing or removing the hook.

Local, deterministic, $0, zero-latency - reads the hook JSON on stdin and prints a standing
instruction to stdout (which Claude Code adds to context). It makes NO model call of its own;
the main model does the rating/rewrite inline as part of its normal reply. Prints nothing when
skipped.
"""

import json
import os
import re
import sys

# Refinement 2: off-switch via env var (default on).
if os.environ.get("CLAUDE_RATE_PROMPTS", "").strip().lower() == "off":
    sys.exit(0)

try:
    prompt = (json.load(sys.stdin).get("prompt") or "").strip()
except Exception:
    prompt = ""

# Refinement 1: skip trivial acknowledgements - nothing to rate on a one-word confirmation.
_TRIVIAL = re.compile(
    r"^(y|n|k|kk|ok|okay|yes|yep|yeah|ya|no|nope|nah|sure|go|go ahead|do it|continue|resume|"
    r"next|push|pull|commit|stop|done|wait|hold on|thanks|thank you|ty|tysm|proceed|run it|"
    r"apply( both| all)?|approve[d]?|accept[ed]?|good|great|nice|perfect|cool|right|correct|"
    r"yes please|sounds good|lgtm|ship it)[.!\s]*$",
    re.IGNORECASE,
)
if not prompt or _TRIVIAL.match(prompt):
    sys.exit(0)

# Escape hatch: if the user asks for their exact words, act verbatim - no rewrite, no reinterpret.
_LITERAL = re.compile(
    r"\b(literal(?:ly)?|as written|exactly as i (?:said|wrote|asked)|verbatim|as-is|word for word|"
    r"do ?n'?t rewrite|no rewrite|use my (?:exact|literal)|my exact words)\b", re.IGNORECASE)
if _LITERAL.search(prompt):
    sys.stdout.write(
        "Standing instruction (auto-injected): The user asked you to act on their EXACT words this "
        "turn - do NOT rewrite, reinterpret, or substitute an improved version. Still begin with a "
        "one-line rating (X/10), then carry out the literal prompt exactly as written."
    )
    sys.exit(0)

sys.stdout.write(
    "Standing instruction (auto-injected): Begin your reply with a one-line rating (X/10) of this "
    "prompt. Then ALWAYS show the improved '10/10' version of the prompt as the only content inside "
    "a fenced code block (triple backticks) on its own, with no rating, commentary, or extra "
    "backticks inside that block. Then ACT ON THAT IMPROVED VERSION rather than the literal wording "
    "- but the rewrite may ONLY sharpen and clarify the user's intent; it must never add scope, "
    "steps, or assumptions the user did not ask for. If the prompt is already near-optimal, say so "
    "briefly and proceed. For ambiguous, costly, or irreversible requests, show the improved prompt "
    "and confirm it with the user before acting."
)
