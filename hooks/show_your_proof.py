"""show-your-proof Stop hook for Claude Code.

What it does
------------
Fires (stderr + exit 2) when the assistant's LAST message in the current turn
makes a SUCCESS CLAIM ("it works", "tests pass", "verified", ...) while the
turn contains ZERO assistant tool_use blocks - i.e. an "it works" claim with
no verification run behind it. The nudge asks the model to show verification
or soften the claim. Fires at most once per session (marker file).

Why it is mechanical (no reasoning)
-----------------------------------
It only does string/regex matching against a fixed, tight phrase list and
counts tool_use blocks between the last real user prompt and the end of the
transcript tail. It never judges whether the claim is actually true - that is
the reasoner's job; this hook only surfaces the "claim with zero tool runs"
state. Conservative by design: silence is always acceptable, a false nudge
is not, so every ambiguous/exception path is silent (exit 0).

Guards (in order)
-----------------
1. Unparseable/absent stdin JSON            -> exit 0
2. payload['stop_hook_active'] truthy       -> exit 0 (never loop)
3. Once-per-session marker already present  -> exit 0 before evaluating
   (~/.claude/hooks/state/show_your_proof-<sid12>.done, overridable via
   UNBLUFF_STATE_DIR for testing; missing session_id -> 'nosession')
4. Missing/unreadable transcript_path       -> exit 0
5. Any exception anywhere                   -> exit 0 (broken hook must
   never block the user)

Parser notes (from observed transcript format)
----------------------------------------------
Each transcript line is JSON with a 'type' field ('user'/'assistant'/
'attachment'/'queue-operation'/'last-prompt'/'mode'/...). Only 'user' and
'assistant' entries carry a 'message' whose 'content' is a plain string or a
list of blocks ({'type':'text'|'tool_use'|'tool_result'|'thinking'}).
Unknown types, malformed lines, and sidechain (subagent) entries are skipped.
Synthetic user entries (e.g. '<task-notification>...') are not treated as
real prompts.
"""

from __future__ import annotations

import json
import os
import re
import sys

HOOK_NAME = "show_your_proof"
STATE_DIR_ENV = "UNBLUFF_STATE_DIR"
DEFAULT_STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "state")
SESSION_ID_PREFIX_LEN = 12
TAIL_LINE_COUNT = 120
TAIL_READ_BYTES = 512 * 1024

# Tight, word-boundary success-claim phrases (case-insensitive).
# Deliberately does NOT include bare "done"/"fixed"/"complete" (too noisy).
CLAIM_PHRASES = (
    r"it works",
    r"works now",
    r"working now",
    r"tests pass(?:ed)?",          # covers "tests pass", "tests passed", "all tests pass"
    r"all checks pass(?:ed)?",
    r"verified",
    r"confirmed working",
    r"fixed the bug",
    r"bug is fixed",
    r"now fixed",
    r"successfully fixed",
    r"successfully implemented",
    r"everything passes",
    r"build succeeds",
    r"build passes",
)
CLAIM_RE = re.compile(r"\b(?:" + "|".join(CLAIM_PHRASES) + r")\b", re.IGNORECASE)

# If any of these appear just before a matched phrase, the claim is negated
# ("not verified", "haven't confirmed it works") -> do not count it.
NEGATION_TOKENS = ("not ", "n't ", "never ", "cannot ", "unable ", "without ", "unless ")
NEGATION_WINDOW_CHARS = 20

# Plain-string user entries starting with these are synthetic, not real prompts.
META_PROMPT_PREFIXES = (
    "<task-notification>",
    "<system-reminder>",
    "<local-command",
    "<command-name>",
    "<bash-input>",
    "<bash-stdout>",
)

FIRE_MESSAGE_TEMPLATE = (
    "[show-your-proof] The last reply claims success ('{phrase}') but this "
    "turn ran no tools. Show verification (run the test/build/command) or "
    "soften the claim to what was actually verified."
)


def find_claim(text):
    """Return the matched success-claim phrase in text, or None.

    Skips matches preceded by a negation token within a small window.
    Pure function.
    """
    if not isinstance(text, str) or not text:
        return None
    for match in CLAIM_RE.finditer(text):
        start = match.start()
        window = text[max(0, start - NEGATION_WINDOW_CHARS):start].lower()
        if any(tok in window for tok in NEGATION_TOKENS):
            continue
        return match.group(0)
    return None


def parse_entries(lines):
    """Parse jsonl lines into transcript entries, defensively.

    Skips malformed lines, non-dict entries, and sidechain (subagent) entries.
    Pure function.
    """
    entries = []
    for line in lines:
        if not isinstance(line, str) or not line.strip():
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("isSidechain"):
            continue
        entries.append(obj)
    return entries


def get_content(entry):
    """Return the message content (str, list of blocks) or None. Pure."""
    message = entry.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, (str, list)):
        return content
    return None


def is_real_user_prompt(entry):
    """True if entry is a real (non-synthetic) user prompt. Pure.

    Real = 'user' type whose content is a plain string (not a known meta tag)
    or a block list containing a 'text' block and NO 'tool_result' block.
    """
    if entry.get("type") != "user":
        return False
    content = get_content(entry)
    if isinstance(content, str):
        stripped = content.lstrip()
        return not stripped.lower().startswith(META_PROMPT_PREFIXES)
    if isinstance(content, list):
        has_text = False
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_result":
                return False
            if block_type == "text":
                has_text = True
        return has_text
    return False


def count_tool_uses(entries):
    """Count assistant tool_use blocks across entries. Pure."""
    count = 0
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = get_content(entry)
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                count += 1
    return count


def last_assistant_text(entries):
    """Concatenate the text blocks of the LAST assistant entry. Pure."""
    for entry in reversed(entries):
        if entry.get("type") != "assistant":
            continue
        content = get_content(entry)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)
        return ""
    return ""


def evaluate_lines(lines):
    """Core decision from raw tail lines -> (should_fire, matched_phrase).

    Pure function; conservative: any missing piece means (False, '').
    """
    entries = parse_entries(lines)
    prompt_index = None
    for i in range(len(entries) - 1, -1, -1):
        if is_real_user_prompt(entries[i]):
            prompt_index = i
            break
    if prompt_index is None:
        # No real user prompt in the tail window: the turn is long and almost
        # certainly contains tool runs further back. Stay silent.
        return (False, "")
    turn_entries = entries[prompt_index:]
    if count_tool_uses(turn_entries) > 0:
        return (False, "")
    phrase = find_claim(last_assistant_text(turn_entries))
    if phrase is None:
        return (False, "")
    return (True, phrase)


def read_tail_lines(path, max_lines=TAIL_LINE_COUNT):
    """Read the last ~max_lines of a potentially huge file, cheaply."""
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - TAIL_READ_BYTES))
        data = handle.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    if size > TAIL_READ_BYTES and lines:
        lines = lines[1:]  # drop the possibly mid-line-truncated first line
    return lines[-max_lines:]


def main():
    # Guard 1: unparseable stdin -> silent exit 0.
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    # Guard 2: never loop.
    if payload.get("stop_hook_active"):
        return 0
    # Guard 3: once per session - marker check BEFORE evaluating.
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        session_id = "nosession"
    sid12 = session_id[:SESSION_ID_PREFIX_LEN]
    state_dir = os.environ.get(STATE_DIR_ENV) or DEFAULT_STATE_DIR
    marker_path = os.path.join(state_dir, "%s-%s.done" % (HOOK_NAME, sid12))
    if os.path.exists(marker_path):
        return 0
    # Guard 4: transcript must be present and readable.
    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return 0
    try:
        lines = read_tail_lines(transcript_path)
    except OSError:
        return 0
    should_fire, phrase = evaluate_lines(lines)
    if not should_fire:
        return 0
    # Record the marker first; if we cannot record once-per-session state,
    # stay silent rather than risk nagging on every Stop.
    try:
        os.makedirs(state_dir, exist_ok=True)
        with open(marker_path, "w", encoding="utf-8") as handle:
            handle.write("fired\n")
    except OSError:
        return 0
    sys.stderr.write(FIRE_MESSAGE_TEMPLATE.format(phrase=phrase) + "\n")
    return 2


# ---------------------------------------------------------------------------
# Selftest (pure-function fixtures; never touches the real state dir)
# ---------------------------------------------------------------------------

def _fixture_lines(*objs):
    return [json.dumps(o) for o in objs]


def _user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def _assistant_text(text):
    return {"type": "assistant",
            "message": {"role": "assistant",
                        "content": [{"type": "text", "text": text}]}}


def _assistant_tool_use():
    return {"type": "assistant",
            "message": {"role": "assistant",
                        "content": [{"type": "tool_use", "id": "toolu_01",
                                     "name": "Bash",
                                     "input": {"command": "pytest"}}]}}


def _tool_result_user():
    return {"type": "user",
            "message": {"role": "user",
                        "content": [{"type": "tool_result",
                                     "tool_use_id": "toolu_01",
                                     "content": "1 passed"}]}}


def _selftest_cases():
    """Return list of (name, lines, expected_fire). Pure fixtures."""
    claim = "I checked the code and it works now."
    return [
        ("claim_no_tools_SHOULD_FIRE",
         _fixture_lines(_user("fix the bug"), _assistant_text(claim)),
         True),
        ("claim_with_tool_use_should_NOT_fire",
         _fixture_lines(_user("fix the bug"), _assistant_tool_use(),
                        _tool_result_user(), _assistant_text(claim)),
         False),
        ("no_claim_should_NOT_fire",
         _fixture_lines(_user("fix the bug"),
                        _assistant_text("I refactored the module; please try it.")),
         False),
        ("negated_claim_should_NOT_fire",
         _fixture_lines(_user("fix the bug"),
                        _assistant_text("I have not verified this yet.")),
         False),
        ("bare_done_should_NOT_fire",
         _fixture_lines(_user("fix the bug"),
                        _assistant_text("Done. The change is complete and fixed.")),
         False),
        ("no_user_prompt_in_window_should_NOT_fire",
         _fixture_lines(_assistant_text(claim)),
         False),
        ("synthetic_prompt_only_should_NOT_fire",
         _fixture_lines(_assistant_tool_use(), _tool_result_user(),
                        _user("<task-notification>task done</task-notification>"),
                        _assistant_text(claim)),
         False),
        ("malformed_lines_should_NOT_fire",
         ["{not json", "", "42", json.dumps(["a", "list"])],
         False),
        ("tests_passed_claim_SHOULD_FIRE",
         _fixture_lines(_user("run the suite"),
                        _assistant_text("All tests passed, we are good.")),
         True),
        ("sidechain_claim_skipped_should_NOT_fire",
         _fixture_lines(
             _user("fix the bug"),
             dict(_assistant_text(claim), isSidechain=True)),
         False),
    ]


def selftest():
    import tempfile
    failures = 0
    for name, lines, expected in _selftest_cases():
        fired, phrase = evaluate_lines(lines)
        if fired == expected:
            print("SELFTEST OK: %s (fired=%s phrase=%r)" % (name, fired, phrase))
        else:
            failures += 1
            print("SELFTEST FAIL: %s expected fired=%s got fired=%s phrase=%r"
                  % (name, expected, fired, phrase))
    # File-based check of read_tail_lines via tempfile (never the real state dir).
    try:
        with tempfile.TemporaryDirectory() as tmp:
            transcript = os.path.join(tmp, "t.jsonl")
            fixture = _fixture_lines(
                _user("fix the bug"),
                _assistant_text("I checked the code and it works now."))
            with open(transcript, "w", encoding="utf-8") as handle:
                handle.write("\n".join(fixture) + "\n")
            fired, phrase = evaluate_lines(read_tail_lines(transcript))
            if fired and phrase:
                print("SELFTEST OK: tempfile_read_tail_SHOULD_FIRE (phrase=%r)" % phrase)
            else:
                failures += 1
                print("SELFTEST FAIL: tempfile_read_tail expected fire, got fired=%s" % fired)
    except Exception as exc:  # selftest itself must report, not crash
        failures += 1
        print("SELFTEST FAIL: tempfile case raised %r" % exc)
    if failures:
        print("SELFTEST FAIL: %d case(s) failed" % failures)
        return 1
    print("SELFTEST: ALL OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # broken hook must never block the user
