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
import subprocess
import sys

HOOK_NAME = "close_skills_guard"
TARGET_BASENAME = "next_session_prompt.md"           # matched case-insensitively
REQUIRED_SKILLS = ("consistency-audit", "completeness-audit", "source-coverage", "meta-review")


def _target_file(tool_input: dict) -> bool:
    """True iff this Write/Edit targets docs/NEXT_SESSION_PROMPT.md (by basename, any dir)."""
    fp = (tool_input or {}).get("file_path") or ""
    return os.path.basename(str(fp)).lower() == TARGET_BASENAME


def _iter_entries(transcript_path: str):
    """Yield parsed JSONL OBJECTS from the transcript, skipping unparseable and non-object lines.

    The isinstance filter is load-bearing. A single malformed-but-parseable line - an
    interleaved write, a future harness record type that is not an object, a hand-repaired
    truncation - used to reach _is_genuine_user as a list, raise AttributeError, and get
    swallowed by main()'s catch-all. From that point every close-signal write passed in
    silence: the guard was decoration and nothing said so.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


# Text the HARNESS writes into a role=user entry. None of it is the user speaking, and each one
# wrongly reset the detection window - telling Claude to re-run four expensive audit skills
# after a correct close, and looping if another injection arrived during that stretch.
_SYNTHETIC_PREFIXES = (
    "[Request interrupted",
    "<command-name>", "<command-message>", "<command-args>", "<local-command-",
    "<system-reminder>", "<task-notification>", "<bash-input>", "<bash-stdout>",
    "<bash-stderr>", "Caveat:", "This session is being continued",
)


def _first_text(content) -> str | None:
    """The first text in this content, or None if it carries none.

    Scans ANY text block rather than content[0]. A prompt that leads with a pasted IMAGE has
    content [{image}, {text}], so the content[0] test read it as "not a user message" - the
    window never reset and the guard passed silently. usage_snip_prompt.py asks the user for a
    screenshot, so the two v1.3.0 hooks interlocked: the guard went blind on exactly the turn
    the other one requests. Verified against real transcripts.
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


def _is_synthetic(content) -> bool:
    text = _first_text(content)
    return text is not None and text.lstrip().startswith(_SYNTHETIC_PREFIXES)


def _is_genuine_user(entry) -> bool:
    """True iff this entry is the USER speaking - not a tool_result, not a harness injection.

    Two-tier by measurement, not by taste. Across 138 real transcripts the harness marks
    genuine prompts with `origin: {"kind": "human"}` (396 of them) and background injections
    with other kinds (150 task-notification) or isMeta (72). Where `origin` is present it is
    authoritative. But 49 entries carried NO origin at all, and 12 of those were genuine
    prompts ("continue", "yes go ahead") - so keying ONLY on origin would reject real user
    turns and fire the guard after a correct close. Hence origin first, shape second.
    """
    if not isinstance(entry, dict):
        return False
    if entry.get("isMeta") or entry.get("sourceToolUseID"):
        return False
    msg = entry.get("message")
    if not isinstance(msg, dict):
        msg = entry
    if msg.get("role") != "user":
        return False
    content = msg.get("content")

    # The synthetic filter runs FIRST, ahead of the origin shortcut. `origin.kind == "human"`
    # is not proof that the USER typed this: the harness stamps it on injections a human
    # indirectly caused, e.g. `<system-reminder>The user started your suggested background
    # task task_...`. Five such entries exist in this user's own transcripts. With the origin
    # check first, that returned True, ended the detection window, and made a CORRECT close
    # (all four skills invoked) exit 2 demanding all four be re-run - the guard's original
    # unsatisfiable failure mode, reintroduced through the field meant to prevent it. Every
    # class-17 fixture paired synthetic text with a missing or non-human origin, so the suite
    # reported OK throughout.
    if _is_synthetic(content):
        return False

    origin = entry.get("origin")
    if isinstance(origin, dict) and origin.get("kind"):
        # Authoritative for entries that are not already known-synthetic: 'human' is the user,
        # every other kind is the harness. A future kind is excluded by default - the safe way.
        return origin.get("kind") == "human"

    # A tool_result or an image-only entry has no text at all and is not a prompt.
    return _first_text(content) is not None


def _skills_invoked(entry: dict) -> set[str]:
    """The set of skill names invoked via the Skill tool in this entry's tool_use blocks."""
    msg = entry.get("message")
    if not isinstance(msg, dict):
        msg = entry
    content = msg.get("content")
    out: set[str] = set()
    if isinstance(content, list):
        for block in content:
            if (isinstance(block, dict) and block.get("type") == "tool_use"
                    and block.get("name") == "Skill"):
                inp = block.get("input")
                skill = inp.get("skill") if isinstance(inp, dict) else None
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

_MK_SEQ = [0]


def _mk(transcript_lines: list[dict], tmp) -> str:
    # One file PER fixture. Writing them all to "t.jsonl" meant a later fixture silently
    # rewrote an earlier one still referenced by a pending assertion, so the subprocess case
    # was reading a transcript belonging to a different scenario and passing for the wrong
    # reason (found 2026-07-29 while adding the main() coverage).
    _MK_SEQ[0] += 1
    p = os.path.join(tmp, "t%d.jsonl" % _MK_SEQ[0])
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


# --- fixtures taken from REAL transcripts (138 scanned, 2026-07-29) -------------------------
# Measured distribution of non-tool_result user entries: 396 origin=human, 150
# origin=task-notification, 72 isMeta injections, and 49 with NO origin at all - of which 12
# were genuine prompts ("continue", "yes go ahead") and the rest interrupt markers, slash
# command wrappers and compact caveats. That 12 is why `origin` cannot be the ONLY test.

def _human(text):
    """A real prompt as the harness records it."""
    return {"origin": {"kind": "human"}, "promptSource": "sdk",
            "message": {"role": "user", "content": text}}


def _image_then_text(text, origin=True):
    """A pasted screenshot followed by text - exactly the flow usage_snip_prompt.py asks for."""
    e = {"message": {"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "x"}},
        {"type": "text", "text": text}]}}
    if origin:
        e["origin"] = {"kind": "human"}
    return e


def _task_notification():
    return {"origin": {"kind": "task-notification"},
            "message": {"role": "user", "content": [
                {"type": "text", "text": "<task-notification>agent finished</task-notification>"}]}}


def _interrupt():
    return {"message": {"role": "user",
                        "content": [{"type": "text", "text": "[Request interrupted by user]"}]}}


def _slash_command():
    return {"message": {"role": "user",
                        "content": "<command-name>/model</command-name>\n"
                                   "<command-message>model</command-message>"}}


def _compact_caveat():
    return {"message": {"role": "user",
                        "content": "This session is being continued from a previous "
                                   "conversation that ran out of context."}}


def _human_system_reminder():
    """A harness injection that ALSO carries origin.kind == 'human'.

    Not hypothetical: a sweep of 138 transcripts / ~350k entries found 5 real entries of this
    shape - `<system-reminder> The user started your suggested background task task_...`,
    stamped origin=human because a human did trigger the underlying action. It is still the
    harness talking, not a prompt, so it must not end the detection window.
    """
    return {"origin": {"kind": "human"}, "promptSource": "sdk",
            "message": {"role": "user", "content": [
                {"type": "text",
                 "text": "<system-reminder>The user started your suggested background task "
                         "task_abc123. Continue with your work.</system-reminder>"}]}}


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

        # ------------------------------------------------------------ v1.3.1 regressions
        def _verdict(entries, label):
            path = _mk(entries, tmp)
            try:
                return run({"tool_input": {"file_path": "docs/NEXT_SESSION_PROMPT.md"},
                            "transcript_path": path})
            except Exception as e:
                fails.append("%s RAISED %r - the guard is disabled for that session" % (label, e))
                return -1, ""

        # (7) [finding 13] THE BUG: a prompt whose first content block is an IMAGE is a
        # genuine user message. Not counting it left the detection window open across the
        # user's turn, so four skills run at a PREMATURE close still satisfied the real one -
        # the exact temporal gap this hook exists to close. usage_snip_prompt.py asks for a
        # screenshot, so the guard went blind on precisely the turn that flow produces.
        code, msg = _verdict([_human("wrap up"), *all4, _image_then_text("continue")],
                             "image-first prompt")
        if code != 2 or not all(s in msg for s in REQUIRED_SKILLS):
            fails.append("an image-first prompt did not end the detection window - the guard "
                         "passed silently (code=%s msg=%r)" % (code, msg[:120]))

        # (8) the same shape with NO origin field: 12 genuine prompts in the real transcripts
        # carry none, so the shape fallback has to reach the same verdict.
        code, _ = _verdict([_human("wrap up"), *all4, _image_then_text("continue", origin=False)],
                           "image-first prompt without origin")
        if code != 2:
            fails.append("image-first prompt with no origin field was not counted as the user")

        # (9-12) [finding 17] harness-injected role=user entries must NOT end the window.
        # Each of these wrongly BLOCKED a correct close, telling Claude to re-run four
        # expensive audit skills - and another injection during that stretch loops it.
        for entries, label in (
            ([_human("continue"), *all4, _interrupt()], "interrupt marker"),
            ([_human("continue"), *all4, _task_notification()], "task-notification"),
            ([_human("continue"), *all4, _slash_command()], "slash-command wrapper"),
            ([_human("continue"), *all4, _compact_caveat()], "compact caveat"),
            # [D8] The one that got through: a system-reminder stamped origin.kind=human.
            # The origin shortcut returned BEFORE the synthetic-prefix filter, so that filter
            # was unreachable for any entry carrying an origin - and every existing fixture
            # paired synthetic text with a missing or non-human origin, so the suite said OK.
            # Verified against 5 real entries in the user's own transcripts.
            ([_human("continue"), *all4, _human_system_reminder()], "human-stamped reminder"),
        ):
            code, msg = _verdict(entries, label)
            if code != 0:
                fails.append("%s was counted as the user and wrongly BLOCKED a correct close "
                             "(code=%s msg=%r)" % (label, code, msg[:100]))

        # (13) [finding 33] ONE malformed-but-parseable line must not disable the guard.
        # A non-dict entry raised out of _is_genuine_user, main()'s catch-all swallowed it,
        # and every close-signal write passed silently from then on.
        nd = os.path.join(tmp, "nondict.jsonl")
        with open(nd, "w", encoding="utf-8") as f:
            f.write(json.dumps(_human("build stuff")) + "\n")
            f.write("[]\n")                     # a JSON array, not an object
            f.write("12345\n")                  # a bare number
            for e in all4:
                f.write(json.dumps(e) + "\n")
            f.write(json.dumps(_human("continue")) + "\n")
            # ALSO after the last user message: entries before it are only ever read by the
            # genuine-user scan, entries after it are additionally fed to the skill scan. A
            # fixture with malformed lines on one side of that boundary leaves the other
            # unproven - which is how this test first passed with the filter deleted.
            f.write('"a bare string"\n')
            f.write("null\n")
            f.write(json.dumps(_skill("simplify")) + "\n")
        try:
            code, msg = run({"tool_input": {"file_path": "docs/NEXT_SESSION_PROMPT.md"},
                             "transcript_path": nd})
        except Exception as e:
            code, msg = -1, repr(e)
        if code != 2:
            fails.append("one non-dict JSONL line disabled the guard entirely (code=%s %r)"
                         % (code, msg[:120]))

        # (14) [findings 14, 15, 16] main() itself - exercised by NO test until now. The guard
        # could be fully disarmed (message dropped, return code swallowed) with every gate
        # green. Assert the (exit code, message) PAIR, never one without the other.
        import contextlib
        import io as _io

        def _main_with(payload):
            real_in, real_err = sys.stdin, sys.stderr
            sys.stdin = _io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))
            err = _io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    rc = main()
            finally:
                sys.stdin, sys.stderr = real_in, real_err
            return rc, err.getvalue()

        fire = _mk([_human("build"), *all4, _human("continue"), _skill("simplify")], tmp)
        rc, err = _main_with({"tool_input": {"file_path": "docs/NEXT_SESSION_PROMPT.md"},
                              "transcript_path": fire})
        if rc != 2:
            fails.append(f"main() fire case should exit 2, got {rc}")
        if not err.strip() or not all(s in err for s in REQUIRED_SKILLS):
            fails.append("main() fired with a message that does not name every missing skill: "
                         "%r" % (err[:160],))
        if HOOK_NAME not in err:
            fails.append("main()'s message is unattributable - no hook name in it")

        passing = _mk([_human("continue"), *all4], tmp)
        rc, err = _main_with({"tool_input": {"file_path": "docs/NEXT_SESSION_PROMPT.md"},
                              "transcript_path": passing})
        if (rc, err) != (0, ""):
            fails.append(f"main() pass case should be silent 0, got {(rc, err[:100])}")

        rc, err = _main_with({"tool_input": {"file_path": "src/module.py"},
                              "transcript_path": fire})
        if (rc, err) != (0, ""):
            fails.append(f"main() on a non-target file should be silent 0, got {(rc, err[:80])}")

        for bad in ("not json at all", "[]", "null", '"a string"'):
            rc, err = _main_with(bad)
            if (rc, err) != (0, ""):
                fails.append(f"main() on malformed stdin {bad!r} should be silent 0, "
                             f"got {(rc, err[:80])}")

        # (15) and the same through a REAL process, so the __main__ dispatch is covered too:
        # an in-process call cannot catch a broken `if __name__` block.
        proc = subprocess.run([sys.executable, os.path.abspath(__file__)],
                              input=json.dumps({"tool_input": {
                                  "file_path": "docs/NEXT_SESSION_PROMPT.md"},
                                  "transcript_path": fire}),
                              capture_output=True, text=True, timeout=60,
                              encoding="utf-8", errors="replace")
        if proc.returncode != 2 or not all(s in (proc.stderr or "") for s in REQUIRED_SKILLS):
            fails.append("subprocess fire case wrong: rc=%s stderr=%r"
                         % (proc.returncode, (proc.stderr or "")[:160]))

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
