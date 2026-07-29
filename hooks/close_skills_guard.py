"""close_skills_guard (GLOBAL Claude Code PostToolUse hook) - the four-close-skills tripwire.

THE BUG THIS FIXES (recurred twice on 2026-07-27): the close ritual = INVOKE the four audit skills
(consistency-audit / completeness-audit / source-coverage / meta-review) via the Skill tool at the
ACTUAL session end. The failure mode is temporal, not conceptual: Claude declares a PREMATURE close,
runs the four skills there, the user says "continue", Claude builds more, reaches the REAL end - and
skips the skills because they "already ran this session". So the skills fire at a self-declared close
and never re-fire at the verified end. A plain Stop hook cannot catch this (it fires every turn and
cannot tell a premature pause from the real end).

The reliable end-of-session SIGNAL is Claude WRITING docs/NEXT_SESSION_PROMPT.md (the standing close
protocol writes it). So this hook is a PostToolUse guard on Write/Edit/MultiEdit that fires ONLY when
that file is the target, and checks the session transcript: were all four audit skills invoked (via
the Skill tool) SINCE THE LAST GENUINE USER MESSAGE? A skill run BEFORE the last user turn (i.e. at an
earlier premature close, before the user's "continue") does NOT count - that is exactly the gap. If
any of the four is missing from the current closing stretch, it exits 2 with the missing list so
Claude re-invokes them before ending.

Mechanical + fail-silent by design: unparseable stdin / wrong file / no transcript / any exception ->
silent exit 0 (a broken hook must never block the user). Run with --selftest to verify the mechanics.
"""
from __future__ import annotations

import json
import os
import sys

HOOK_NAME = "close_skills_guard"
TARGET_BASENAME = "next_session_prompt.md"           # matched case-insensitively
REQUIRED_SKILLS = ("consistency-audit", "completeness-audit", "source-coverage", "meta-review")


def _target_file(tool_input: dict) -> bool:
    """True iff this Write/Edit targets docs/NEXT_SESSION_PROMPT.md (by basename, any dir)."""
    fp = (tool_input or {}).get("file_path") or ""
    return os.path.basename(str(fp)).lower() == TARGET_BASENAME


def _iter_entries(transcript_path: str):
    """Yield parsed JSONL entries from the transcript, skipping unparseable lines."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def _is_genuine_user(entry: dict) -> bool:
    """A real user prompt (content is a plain str, or its first block is type 'text') - NOT a
    tool_result (those are also role 'user' but carry a tool_result content block), and NOT a
    harness-injected entry.

    Invoking a Skill makes the harness inject that skill's instructions back into the
    transcript as a role='user' entry whose first block is plain text - structurally identical
    to a real prompt. Counting it as "the last user message" put every skill invoked BEFORE it
    outside the window, and the LAST skill invoked always injects after its own invocation. The
    guard therefore reported all four missing however many were actually run - unsatisfiable by
    construction (observed 2026-07-29 with all four invoked in one turn).

    Injected entries are marked isMeta=True and carry sourceToolUseID; a real prompt has
    neither. Structural, so it does not depend on the wording of any particular injection.
    """
    if entry.get("isMeta") or entry.get("sourceToolUseID"):
        return False
    msg = entry.get("message") or entry
    if msg.get("role") != "user":
        return False
    content = msg.get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list) and content and isinstance(content[0], dict):
        return content[0].get("type") == "text"
    return False


def _skills_invoked(entry: dict) -> set[str]:
    """The set of skill names invoked via the Skill tool in this entry's tool_use blocks."""
    msg = entry.get("message") or entry
    content = msg.get("content")
    out: set[str] = set()
    if isinstance(content, list):
        for block in content:
            if (isinstance(block, dict) and block.get("type") == "tool_use"
                    and block.get("name") == "Skill"):
                skill = (block.get("input") or {}).get("skill")
                if isinstance(skill, str):
                    out.add(skill.strip().lower())
    return out


def missing_close_skills(transcript_path: str) -> list[str]:
    """The required audit skills NOT invoked since the last genuine user message (order-preserved).
    Returns [] when all four are present in the current closing stretch."""
    entries = list(_iter_entries(transcript_path))
    if not entries:
        return []                                    # no transcript -> cannot judge -> silent
    # index just after the last genuine user message; if none, consider the whole transcript
    last_user = -1
    for i, e in enumerate(entries):
        if _is_genuine_user(e):
            last_user = i
    invoked: set[str] = set()
    for e in entries[last_user + 1:]:
        invoked |= _skills_invoked(e)
    return [s for s in REQUIRED_SKILLS if s not in invoked]


def build_message(missing: list[str]) -> str:
    return (
        f"[{HOOK_NAME}] You are writing NEXT_SESSION_PROMPT.md (the session-close signal) but these "
        f"canonical close-audit SKILLS were NOT invoked since the last user message: "
        f"{', '.join(missing)}. An earlier (premature-close) run does NOT count. INVOKE each missing "
        f"skill via the Skill tool now and act on its findings, THEN finish the close - never a "
        f"hand-rolled inline substitute.\n")


def run(payload: dict) -> tuple[int, str]:
    """Core decision, testable in isolation: (exit_code, stderr_text)."""
    if not _target_file(payload.get("tool_input") or {}):
        return 0, ""                                 # not the close-signal file
    missing = missing_close_skills(payload.get("transcript_path") or "")
    if not missing:
        return 0, ""
    return 2, build_message(missing)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        code, message = run(payload)
        if code == 2 and message:
            sys.stderr.write(message)
        return code
    except Exception:                                # a broken hook must never block the user
        return 0


# ------------------------------------------------------------------ selftest

def _mk(transcript_lines: list[dict], tmp) -> str:
    p = os.path.join(tmp, "t.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for e in transcript_lines:
            f.write(json.dumps(e) + "\n")
    return p


def _user(text):
    return {"message": {"role": "user", "content": text}}


def _skill_injection(name):
    """How the harness echoes a Skill's body back: role=user, plain text, but isMeta."""
    return {"isMeta": True, "sourceToolUseID": "toolu_fixture",
            "message": {"role": "user",
                        "content": [{"type": "text",
                                     "text": "Base directory for this skill: /x/%s" % name}]}}


def _tool_result(text):
    return {"message": {"role": "user", "content": [{"type": "tool_result", "content": text}]}}


def _skill(name):
    return {"message": {"role": "assistant",
                        "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": name}}]}}


def selftest() -> int:
    import tempfile
    fails: list[str] = []
    all4 = [_skill(s) for s in REQUIRED_SKILLS]
    with tempfile.TemporaryDirectory() as tmp:
        # (4) REGRESSION: a Skill's injected body must not end the window. The harness echoes
        # each invoked skill's instructions back as a role=user plain-text entry, so the LAST
        # skill invoked always injects AFTER its own invocation. Counting that as the user's
        # message made the guard unsatisfiable - it reported all four missing however many ran
        # (observed live 2026-07-29). Injected entries carry isMeta / sourceToolUseID.
        injected = _mk([_user("wrap up"), *all4, _skill_injection("meta-review")], tmp)
        code, msg = run({"tool_input": {"file_path": "docs/NEXT_SESSION_PROMPT.md"},
                         "transcript_path": injected})
        if code != 0:
            fails.append("skill-injection entry ended the window: all four ran but got %r" % msg)

        # (1) THE BUG: 4 skills at a premature close, THEN a user 'continue', THEN a close with none.
        bug = _mk([_user("build stuff"), *all4, _user("continue"), _skill("simplify")], tmp)
        code, msg = run({"tool_input": {"file_path": "docs/NEXT_SESSION_PROMPT.md"},
                         "transcript_path": bug})
        if code != 2 or not all(s in msg for s in REQUIRED_SKILLS):
            fails.append(f"bug scenario should FIRE with all 4 missing: code={code} msg={msg!r}")

        # (2) correct close: 4 skills AFTER the last user message -> pass
        ok = _mk([_user("continue"), *all4, _tool_result("gate green")], tmp)
        code, msg = run({"tool_input": {"file_path": "C:/x/docs/NEXT_SESSION_PROMPT.md"},
                         "transcript_path": ok})
        if (code, msg) != (0, ""):
            fails.append(f"correct close should PASS: code={code} msg={msg!r}")

        # (3) partial: only 2 of 4 after last user -> FIRE, listing exactly the 2 missing
        part = _mk([_user("continue"), _skill("source-coverage"), _skill("meta-review")], tmp)
        code, msg = run({"tool_input": {"file_path": "NEXT_SESSION_PROMPT.md"},
                         "transcript_path": part})
        if code != 2 or "consistency-audit" not in msg or "completeness-audit" not in msg \
                or "source-coverage" in msg:
            fails.append(f"partial should FIRE with only the 2 missing: code={code} msg={msg!r}")

        # (4) different file -> silent, regardless of transcript
        code, msg = run({"tool_input": {"file_path": "src/module.py"}, "transcript_path": part})
        if (code, msg) != (0, ""):
            fails.append(f"non-target file must be silent: code={code} msg={msg!r}")

        # (5) missing transcript -> silent (cannot judge)
        code, msg = run({"tool_input": {"file_path": "NEXT_SESSION_PROMPT.md"},
                         "transcript_path": os.path.join(tmp, "nope.jsonl")})
        if (code, msg) != (0, ""):
            fails.append(f"missing transcript must be silent: code={code} msg={msg!r}")

        # (6) tool_result blocks (role user) must NOT be treated as genuine user messages
        tr = _mk([_user("continue"), *all4, _tool_result("some tool output")], tmp)
        code, _ = run({"tool_input": {"file_path": "NEXT_SESSION_PROMPT.md"}, "transcript_path": tr})
        if code != 0:
            fails.append("tool_result after skills wrongly reset the window (should PASS)")

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
