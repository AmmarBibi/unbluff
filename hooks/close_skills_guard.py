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

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

# ONE classifier for "is this the user speaking?" - show_your_proof imports the same
# module. Two implementations of one rule is what produced both hooks' defects.
import transcript_util  # noqa: E402  (path set above)

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


# NOTE: this hook deliberately keeps NO prefix list and NO _first_text of its own. It had
# both, show_your_proof had a different pair, and each was wrong in a way the other was not.
# The list lives in transcript_util.SYNTHETIC_PREFIXES; transcript_util's selftest fails if a
# second one reappears anywhere in hooks/.


def _is_genuine_user(entry) -> bool:
    """True iff this entry is the USER speaking - the SHARED classifier.

    Measured, not assumed. Across 138 real transcripts the harness marks genuine prompts with
    `origin: {"kind": "human"}` (396) and background injections with other kinds (150
    task-notification) or isMeta (72) - but 49 entries carried NO origin at all and 12 of those
    were genuine prompts, so origin alone cannot decide it. And origin cannot be checked FIRST
    either: the harness stamps kind=human on reminders a human indirectly caused.

    show_your_proof asked the identical question with a different, separately-wrong answer, so
    the rule now lives in transcript_util and both hooks import it. See that module for the
    order of the tests and why each one is load-bearing.
    """
    return transcript_util.is_genuine_user(entry)


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


# Tools that CHANGE the repository. A tool_result, a Read, a Bash query or a Skill call leaves the
# audited state exactly as the audits found it; these do not.
WRITE_TOOLS = frozenset({"write", "edit", "multiedit", "notebookedit"})


def _files_written(entry) -> list:
    """file_path of every repo-changing tool_use in this entry."""
    msg = entry.get("message") if isinstance(entry, dict) else None
    if not isinstance(msg, dict):
        msg = entry
    content = msg.get("content") if isinstance(msg, dict) else None
    out = []
    if isinstance(content, list):
        for block in content:
            if (isinstance(block, dict) and block.get("type") == "tool_use"
                    and str(block.get("name", "")).strip().lower() in WRITE_TOOLS):
                inp = block.get("input")
                fp = inp.get("file_path") if isinstance(inp, dict) else None
                if isinstance(fp, str) and fp.strip():
                    out.append(fp.strip())
    return out


def writes_after_close_skills(transcript_path: str) -> list:
    """Files written AFTER the last required-skill invocation, in the current closing stretch.

    [RECENCY 2026-08-24] The guard asked PRESENCE - "were all four skills invoked since the last
    genuine user message" - and that is satisfiable by an audit of a state that no longer exists.
    MEASURED, on this hook's own session: the four skills ran at 15:54, then four more commits
    landed - a code fix to a guard, a full re-cut of the plan, and a merge to `main` - and the
    guard still passed. Re-running the audits over that tail found FOUR defects, all authored
    after the ritual: a hook wired NOWHERE promoted to the plan's top item while calling itself
    live, the word "NOT" deleted from the standing check whose entire value is that word, an
    archived plan with no retirement banner, and a mutation run called green by grepping past its
    own FAIL line. The close certified a dead state, and the only reason anyone noticed is that
    the user asked.

    Presence is the wrong question; RECENCY is the question. Excludes the close artifact itself,
    which is by definition written last, and tolerates a repeated write of it. Everything here
    comes from the same scan `missing_close_skills` already walks - this is a comparison of two
    indices, not a second traversal of a different thing.
    """
    entries = list(_iter_entries(transcript_path))
    if not entries:
        return []                                    # no transcript -> cannot judge -> silent
    last_user = -1
    for i, e in enumerate(entries):
        if _is_genuine_user(e):
            last_user = i
    window = entries[last_user + 1:]

    last_skill = -1
    for i, e in enumerate(window):
        if _skills_invoked(e) & set(REQUIRED_SKILLS):
            last_skill = i
    if last_skill < 0:
        return []          # no skills ran at all - that is missing_close_skills' finding, not this one

    stale = []
    for e in window[last_skill + 1:]:
        for fp in _files_written(e):
            if not _target_file({"file_path": fp}):
                stale.append(fp)
    # De-duplicated but ORDER-PRESERVED: the first file written after the audits is the one that
    # tells you where the close actually ended.
    seen, ordered = set(), []
    for fp in stale:
        if fp not in seen:
            seen.add(fp)
            ordered.append(fp)
    return ordered


def build_stale_message(stale: list) -> str:
    shown = ", ".join(stale[:4]) + (" (+%d more)" % (len(stale) - 4) if len(stale) > 4 else "")
    return (
        f"[{HOOK_NAME}] All four close-audit skills ran, but {len(stale)} file(s) were WRITTEN "
        f"AFTER the last one: {shown}. The audits therefore certified a state that no longer "
        f"exists - which is exactly how a close ritual passes while being wrong. Re-invoke the "
        f"four skills over the work authored SINCE they ran, then finish the close.\n")


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
    transcript = payload.get("transcript_path") or ""
    missing = missing_close_skills(transcript)
    if missing:
        return 2, build_message(missing)
    # PRESENCE satisfied. Now RECENCY - the audits must not predate the work they certify.
    stale = writes_after_close_skills(transcript)
    if stale:
        return 2, build_stale_message(stale)
    return 0, ""


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


def _nonmedia_then_text(text):
    """A NON-media block before the text, with no origin field.

    [P13 D4] This fixture exists to keep finding 13 ("first_text scans EVERY block, not just
    content[0]") provable. Adding has_user_media() gave the image-first fixture a second way to
    be recognised, so slicing first_text back to content[:1] stopped failing there - the fix
    for one finding quietly disarmed the test for another. A leading block that is neither text
    nor user media can ONLY be classified correctly by scanning past index 0.
    """
    return {"message": {"role": "user", "content": [
        {"type": "thinking", "thinking": "..."},
        {"type": "text", "text": text}]}}


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

        # ---------------------------------------------------------------- [RECENCY 2026-08-24]
        # PRESENCE was satisfiable by an audit of a state that no longer existed. MEASURED on
        # this hook's own session: four skills at 15:54, then a guard fix, a full plan re-cut and
        # a merge to main - guard PASSED, and re-auditing that tail found four defects, all
        # authored after the ritual. Each case below was observed on the real shape first.
        def _wrote(path):
            return {"message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Write", "input": {"file_path": path}}]}}

        def _rec(entries, label):
            p = _mk(entries, tmp)
            return run({"tool_input": {"file_path": "NEXT_SESSION_PROMPT.md"},
                        "transcript_path": p})[0], label

        code, _l = _rec([_user("wrap up"), *all4, _wrote("docs/PLAN.md")], "stale")
        if code != 2:
            fails.append("RECENCY: a file written AFTER the four skills must FIRE - the audits "
                         "certified a state that no longer exists (got %r)" % code)

        code, _l = _rec([_user("wrap up"), *all4, _wrote("docs/NEXT_SESSION_PROMPT.md")], "self")
        if code != 0:
            fails.append("RECENCY: writing the close artifact itself must NOT fire - it is by "
                         "definition written last (got %r)" % code)

        code, _l = _rec([_user("wrap up"), *all4, _wrote("docs/PLAN.md"), *all4], "reclosed")
        if code != 0:
            fails.append("RECENCY: re-running all four AFTER the write must re-close the window, "
                         "or the only way to satisfy this guard is to never edit again (got %r)"
                         % code)

        # A Read is not a state change. Without this, the guard fires on its own verification
        # pass and gets disabled within a day - which is strictly worse than no guard.
        code, _l = _rec([_user("wrap up"), *all4,
                         {"message": {"role": "assistant", "content": [
                             {"type": "tool_use", "name": "Read",
                              "input": {"file_path": "docs/PLAN.md"}}]}}], "read")
        if code != 0:
            fails.append("RECENCY: a Read after the skills must NOT fire (got %r)" % code)

        # PRESENCE keeps precedence: a missing skill is the louder finding and its message names
        # which ones, so recency must not mask it.
        code, _l = _rec([_user("wrap up"), *all4[:2], _wrote("docs/PLAN.md")], "both")
        if code != 2:
            fails.append("RECENCY must not mask a missing skill (got %r)" % code)

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

        # (8b) [finding 13, kept provable after P13 D4] a NON-media leading block. The
        # image-first fixture above can now pass via has_user_media(), so only this one still
        # proves first_text() scans past content[0].
        code, _ = _verdict([_human("wrap up"), *all4, _nonmedia_then_text("continue")],
                           "text-not-first prompt with no media block")
        if code != 2:
            fails.append("a user prompt whose text is not the FIRST content block was not "
                         "counted as the user - first_text() is only looking at content[0]")

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
            # isMeta as the ONLY signal: plain text, no recognisable prefix, no origin. The
            # structural marker has to stand on its own, because the prefix list can only ever
            # cover injections whose wording someone has already seen. Every other injection
            # fixture here starts with a known tag, so without this case the isMeta check was
            # untested - deleting it left the whole suite green.
            ([_human("continue"), *all4,
              {"isMeta": True, "message": {"role": "user",
                                           "content": "Proceed with the remaining work."}}],
             "isMeta injection with unrecognised wording"),
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
