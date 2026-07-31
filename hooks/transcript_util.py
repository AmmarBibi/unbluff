"""Shared transcript-entry classification: is this the USER speaking, or the harness?

Two hooks ask this question - close_skills_guard (which reads it to bound the session-close
window) and show_your_proof (which reads it to bound the current turn) - and they answered it
with two different, separately-wrong implementations:

  * close_skills_guard checked content[0] only, so a prompt led by a pasted image was invisible;
    later it checked `origin` before the synthetic filter, so a `<system-reminder>` stamped
    origin=human ended the window.
  * show_your_proof applied its prefix list ONLY to the plain-string branch. Measured across
    139 real transcripts (28,396 user entries): 288 harness injections arrive as LIST content
    and 266 of those were accepted as real prompts, truncating the turn and producing false
    "this turn ran no tools" fires at turns that had run up to 6 tools.

Two implementations of one rule is the defect, so there is one implementation here and both
hooks import it. The prefix list is the UNION of what each hook knew separately, plus the
three the second review found in real transcripts that neither had.

Every rule here is structural rather than wording-dependent where possible: `isMeta` and
`sourceToolUseID` are set by the harness on injected entries and do not depend on any
particular phrasing. The prefix list is the fallback for entries that carry neither.
"""

from __future__ import annotations

import json
import sys

# Text the HARNESS writes into a role=user / type=user entry. None of it is the user typing.
# Matched case-insensitively against the FIRST text in the entry.
SYNTHETIC_PREFIXES = (
    "<task-notification>",
    "<system-reminder>",
    "<local-command",
    "<command-name>",
    "<command-message>",
    "<command-args>",
    "<bash-input>",
    "<bash-stdout>",
    "<bash-stderr>",
    "[request interrupted",
    "this session is being continued",
    "base directory for this skill",
)

# DELIBERATELY NOT in the list above: "caveat:", "continue from where you left off.",
# "[fast-test]", "[pre-push]", "[show-your-proof]" and friends.
#
# Those are PROSE a human can plausibly type - "Caveat: the API is rate limited", "continue
# from where you left off." is a perfectly ordinary instruction, and a user quoting a hook's
# output back at Claude starts a line with "[fast-test]". Classifying such a prompt as a
# harness injection means `last_user` never advances, so audits run BEFORE the close satisfy
# close_skills_guard and it exits 0 in silence - the exact failure it exists to prevent,
# triggered by the user typing an ordinary sentence.
#
# They bought nothing: all 80 instances of these strings in the real 139-transcript corpus
# already carry `isMeta` or `sourceToolUseID`, so the structural check catches every one. A
# prefix list can only ever cover wordings someone has already seen; the structural markers
# cover the rest. Keep this list to tags no human types.


def first_text(content) -> str | None:
    """The first text carried by this content, or None if it carries none.

    Scans ANY text block rather than content[0]: a prompt that leads with a pasted image has
    content [{image}, {text}], and a content[0] test reads that as "not a user message".
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    return text
    return None


def has_tool_result(content) -> bool:
    """True if this content carries a tool_result block - never a user prompt."""
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                return True
    return False


def is_synthetic(content) -> bool:
    """True if the entry's text is something the harness wrote, not the user."""
    text = first_text(content)
    return text is not None and text.lstrip().lower().startswith(SYNTHETIC_PREFIXES)


def is_harness_injected(entry) -> bool:
    """Structural marker, independent of wording: the harness sets these on injected entries."""
    return bool(entry.get("isMeta") or entry.get("sourceToolUseID"))


def get_content(entry):
    """The message content (str or list of blocks), or None."""
    message = entry.get("message")
    if not isinstance(message, dict):
        message = entry if isinstance(entry, dict) else {}
    content = message.get("content")
    return content if isinstance(content, (str, list)) else None


def _is_user_role(entry) -> bool:
    """Accept both entry shapes in use: a top-level `type` and/or message.role."""
    if entry.get("type") == "user":
        return True
    if entry.get("type") not in (None, "user"):
        return False
    message = entry.get("message")
    return isinstance(message, dict) and message.get("role") == "user"


def is_genuine_user(entry) -> bool:
    """True iff this entry is the USER speaking - not a tool result, not a harness injection.

    Order matters and is load-bearing:
      1. non-dict            -> not an entry at all (one such JSONL line used to raise and,
                                via a catch-all, silently disable a whole hook)
      2. isMeta / sourceToolUseID -> harness injection, whatever it says
      3. SYNTHETIC text      -> harness injection that carries no marker. BEFORE `origin`:
                                the harness stamps origin.kind=human on reminders a human
                                indirectly caused, and checking origin first made this
                                unreachable.
      4. origin.kind         -> authoritative when present; anything but "human" is not the
                                user, so a future kind is excluded by default
      5. shape               -> 12 genuine prompts in the measured sample carry NO origin, so
                                the shape test cannot be dropped: any text block, no
                                tool_result.
    """
    if not isinstance(entry, dict):
        return False
    if is_harness_injected(entry):
        return False
    if not _is_user_role(entry):
        return False
    content = get_content(entry)
    if has_tool_result(content):
        return False
    if is_synthetic(content):
        return False
    origin = entry.get("origin")
    if isinstance(origin, dict) and origin.get("kind"):
        return origin.get("kind") == "human"
    return first_text(content) is not None


# ------------------------------------------------------------------ selftest

def selftest() -> int:
    fails = []

    def check(entry, expected, label):
        got = is_genuine_user(entry)
        if got != expected:
            fails.append(f"{label}: expected genuine={expected}, got {got}")

    def user(content, **extra):
        e = {"type": "user", "message": {"role": "user", "content": content}}
        e.update(extra)
        return e

    check(user("please continue"), True, "plain string prompt")
    check(user([{"type": "text", "text": "please continue"}]), True, "text-block prompt")
    check(user([{"type": "image", "source": {}}, {"type": "text", "text": "here"}]), True,
          "IMAGE-FIRST prompt (content[0] is not text)")
    check(user("continue", origin={"kind": "human"}), True, "origin=human")
    check(user([{"type": "tool_result", "content": "out"}]), False, "tool_result")
    check(user("x", isMeta=True), False, "isMeta")
    check(user("x", sourceToolUseID="toolu_1"), False, "sourceToolUseID")
    check(user("hello", origin={"kind": "task-notification"}), False, "task-notification origin")
    check({"type": "assistant", "message": {"role": "assistant", "content": "hi"}}, False,
          "assistant entry")
    check([], False, "non-dict entry")
    check(user([]), False, "empty block list")

    # THE class that was wrong in BOTH hooks, in both content shapes.
    for prefix in ("<system-reminder>Some reminder</system-reminder>",
                   "<task-notification>done</task-notification>",
                   "Base directory for this skill: /x/y",
                   "[Request interrupted by user]",
                   "<command-name>/model</command-name>",
                   "<bash-input>ls</bash-input>"):
        check(user(prefix), False, f"synthetic as STRING: {prefix[:32]}")
        check(user([{"type": "text", "text": prefix}]), False,
              f"synthetic as BLOCK LIST: {prefix[:32]}")
        # and the one that slipped through: synthetic text stamped origin=human
        check(user([{"type": "text", "text": prefix}], origin={"kind": "human"}), False,
              f"synthetic + origin=human: {prefix[:32]}")

    # [HIGH-3] The inverse, which the prose prefixes broke: an ordinary human sentence that
    # merely BEGINS like harness output must still count as the user. Misclassifying it stops
    # `last_user` advancing, so audits run before the close satisfy close_skills_guard and it
    # exits 0 in silence - the very failure it exists to prevent, caused by normal typing.
    for human_prose in ("Continue from where you left off.",
                        "Caveat: the API is rate limited, so batch the calls.",
                        "[fast-test] fired again - can you look at why?",
                        "[pre-push] blocked me, what is it complaining about?"):
        check(user(human_prose), True, f"human prose must not read as harness: {human_prose[:34]}")
        check(user([{"type": "text", "text": human_prose}]), True,
              f"same as a block list: {human_prose[:34]}")
        # ...but the SAME text WITH a structural marker is still an injection
        check(user(human_prose, isMeta=True), False,
              f"isMeta still wins over prose: {human_prose[:30]}")

    # both hooks' entry shapes must work: with and without a top-level `type`
    check({"message": {"role": "user", "content": "hi"}}, True, "no top-level type")
    check({"type": "user", "message": {"role": "user", "content": "hi"}}, True, "with type")

    # THE TWIN MUST NOT COME BACK. This module exists because two hooks each kept their own
    # prefix list and their own classifier, and each was wrong in a way the other was not.
    # Fixing both lists would leave the same trap for the next person, so the durable property
    # asserted here is that exactly ONE implementation exists.
    import glob
    import os
    import re
    here = os.path.dirname(os.path.abspath(__file__))
    twins = []
    for path in sorted(glob.glob(os.path.join(here, "*.py"))):
        if os.path.abspath(path) == os.path.abspath(__file__):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError:
            continue
        # A real assignment at the start of a line - not a mention inside a string or comment,
        # which is how a previous twin-guard produced its own false alarm.
        if re.search(r"^\s*(?:_)?(?:META_PROMPT_PREFIXES|SYNTHETIC_PREFIXES)\s*=", src, re.M):
            twins.append(os.path.basename(path) + " (own prefix list)")
        if re.search(r"^\s*def _?first_text\b", src, re.M):
            twins.append(os.path.basename(path) + " (own first_text)")
        if re.search(r"^\s*def _?is_synthetic\b", src, re.M):
            twins.append(os.path.basename(path) + " (own is_synthetic)")
    if twins:
        fails.append("a SECOND transcript classifier exists in %s - import transcript_util "
                     "instead; two copies of one rule is the defect this module fixes" % twins)

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    json.dump({"module": "transcript_util", "usage": "imported by hooks"}, sys.stdout)
    raise SystemExit(0)
