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


USER_MEDIA_BLOCK_TYPES = ("image", "document")


def has_user_media(content) -> bool:
    """True if content carries a user-authored media block (a pasted image or document)."""
    if not isinstance(content, list):
        return False
    return any(isinstance(b, dict) and b.get("type") in USER_MEDIA_BLOCK_TYPES
               for b in content)


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
    # [P13 D4] An image-ONLY prompt carries no text block at all, so a text-only shape test
    # read it as "not the user" and the turn boundary silently slid back to the PREVIOUS turn.
    # Every injection check above still runs first, so tool results and harness entries are
    # unaffected, and user([]) stays False.
    return first_text(content) is not None or has_user_media(content)


# ------------------------------------------------------------------ selftest

# --------------------------------------------------------------------------- the twin guard
#
# WHY THIS IS NOT A NAME LIST ANY MORE. The previous guard enumerated FOUR identifiers across
# three line-anchored regexes over ONE non-recursive directory, and an audit demonstrated 6 of 6
# novel twins passing it silently while all 5 controls were caught. The shape space it was
# enumerating is IDENTIFIER CHOICES - unbounded by construction, because the scenario it guards
# against is an author who did not know this module existed and therefore had no reason to pick
# its names. It could only ever catch a twin written by someone who already knew the canonical
# names, which is close to the population that would not have written a twin.
#
# The rule below is bounded by BEHAVIOUR instead. A second classifier has to answer "is this the
# user speaking?", and it cannot answer that without touching the transcript's own vocabulary -
# whatever it calls its variables. So: any file that touches that vocabulary and does NOT import
# this module is a candidate, and the exemption roster carries the few honest exceptions with a
# written reason each. N recorded exemptions is a healthy design; a guard that reports an
# unenumerated shape as CLEAN is not.

# FLOOR - the original four names, kept. The behavioural rule below MISSES a bare `def
# first_text` that contains no harness vocabulary of its own (measured: audit control C2), so
# the floor is not redundant. Floor plus derived ceiling is already this repo's house style;
# install.py, run_selftests.py and hook_health_check.py all made this same conversion.
_TWIN_CONSTANTS = ("META_PROMPT_PREFIXES", "SYNTHETIC_PREFIXES")
_TWIN_HELPERS = ("first_text", "is_synthetic")

# CEILING - the transcript's own vocabulary. A classifier that avoids all of these is not
# classifying transcripts.
_DISCRIMINATORS = ("isMeta", "sourceToolUseID", "toolUseResult")
_HARNESS_TAGS = ("<bash-stdout>", "<bash-stderr>", "<command-args>", "<command-name>",
                 "<system-reminder>", "[Request interrupted by user]",
                 "Base directory for this skill:", "This session is being continued",
                 "task-notification")

# Every entry needs a REASON, and an entry naming a file that no longer exists is itself
# reported - otherwise the roster rots into cover for whatever gets added next.
TWIN_EXEMPTIONS = {
    "tools/mutation_check.py":
        "mutates hook SOURCE, so it necessarily contains the marker strings it rewrites; it "
        "classifies nothing at runtime",
}
# The audit that designed this rule measured TWO exemptions (the other being
# tools/compare_delivery_gate.py). By the time the rule was built that file no longer touched
# any transcript vocabulary, so its entry was dead on arrival - which is exactly why an
# exemption roster needs a USED check and not only an EXISTS check.

_SKIP_DIRS = {"__pycache__", ".git", ".ruff_cache", ".pytest_cache", "node_modules", ".venv"}


def _bound_identifiers(tree) -> set:
    """Every name this module BINDS, in any syntax.

    Deliberately syntax-agnostic: the old guard anchored on `^\\s*NAME\\s*=` and on `^\\s*def `,
    so an annotated assignment (`SYNTHETIC_PREFIXES: tuple[str, ...] = ...`), a lambda bound to
    a name, and `async def is_synthetic` were all invisible. Asking the AST "what does this bind"
    covers those and the ones nobody has thought of yet.
    """
    import ast
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            out.add(node.id)
        elif isinstance(node, ast.alias):
            out.add((node.asname or node.name).split(".")[0])
    return out


def twin_offenders(root: str | None = None) -> tuple:
    """(offenders, stats). FAILS CLOSED: an unreadable file is reported, never skipped."""
    import ast
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    root = root or os.path.dirname(here)          # the whole repo, not just hooks/
    me = os.path.abspath(__file__)

    offenders, unreadable_paths = [], []
    examined = imports_canonical = exempt = 0
    seen_rel, used_exemptions = set(), set()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            if os.path.abspath(path) == me:
                continue
            rel = os.path.relpath(path, root).replace("\\", "/")
            seen_rel.add(rel)
            examined += 1
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    src = fh.read()
                tree = ast.parse(src)
            except (OSError, SyntaxError):
                # NOT `continue`. A file the guard could not read is a file the guard has no
                # opinion about, and "no opinion" must never be reported as "clean".
                unreadable_paths.append(rel)
                continue

            bound = _bound_identifiers(tree)
            if "transcript_util" in bound:
                imports_canonical += 1
                continue

            why = []
            hit_names = {n for n in bound
                         if n.lstrip("_") in _TWIN_CONSTANTS or n.lstrip("_") in _TWIN_HELPERS}
            if hit_names:
                why.append("binds %s" % sorted(hit_names))
            marks = [m for m in _DISCRIMINATORS if m in src]
            tags = [t for t in _HARNESS_TAGS if t in src]
            if marks or tags:
                why.append("uses transcript vocabulary %s" % sorted(marks + tags)[:4])
            if not why:
                continue
            if rel in TWIN_EXEMPTIONS:
                exempt += 1
                used_exemptions.add(rel)
                continue
            offenders.append("%s (%s)" % (rel, "; ".join(why)))

    # LIVENESS, both directions. An entry naming a file that is gone is obvious rot; an entry
    # whose file no longer triggers the rule is the SAME rot and far harder to notice, because
    # the roster still looks purposeful. One of this roster's two original entries was already
    # in that state on the day it was written.
    problems = ["twin exemption %r names a file that does not exist - a roster entry that "
                "outlives its file is cover for the next one added" % rel
                for rel in sorted(TWIN_EXEMPTIONS) if rel not in seen_rel]
    problems += ["twin exemption %r is never needed - its file no longer trips the rule, so the "
                 "entry now only hides whatever that file becomes next" % rel
                 for rel in sorted(TWIN_EXEMPTIONS)
                 if rel in seen_rel and rel not in used_exemptions]

    return sorted(offenders), {
        "examined": examined, "imports_canonical": imports_canonical, "exempt": exempt,
        "unreadable": len(unreadable_paths), "unreadable_paths": sorted(unreadable_paths),
        "exemption_problems": problems, "root_label": os.path.basename(root) or root,
    }


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
    # [P13 D4] image-ONLY and document-only prompts are still the user speaking
    check(user([{"type": "image", "source": {}}]), True, "IMAGE-ONLY prompt (no text block)")
    check(user([{"type": "document", "source": {}}]), True, "DOCUMENT-ONLY prompt")
    check(user([{"type": "image", "source": {}}], isMeta=True), False,
          "image-only but harness-injected is still NOT the user")
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

    # THE GUARD MUST BE ABLE TO SEE AN OFFENDER. Without this the selftest passes on a clean
    # repo no matter what the detector does, so every mutation of it SURVIVES and the whole
    # guard is decorative - which is how the predecessor stayed blind to 6 of 6 novel twins
    # while printing OK. Each planted case below is a shape the old guard missed.
    import os as _os
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        _h = _os.path.join(_td, "hooks")
        _os.makedirs(_os.path.join(_h, "lib"))
        _os.makedirs(_os.path.join(_td, "tools"))
        _plant = {
            # a complete twin with every name changed - the shape the guard exists for
            "hooks/renamed.py": "HARNESS_TEXT_MARKERS = ('<bash-stdout>',)\n"
                                "def is_real_user_turn(e):\n"
                                "    return not e.get('isMeta')\n",
            # annotated assignment: the old line-anchored regex required `=` after the name
            "hooks/annotated.py": "SYNTHETIC_PREFIXES: tuple = ('<bash-stdout>',)\n",
            # bound without a plain `def`
            "hooks/lambdas.py": "first_text = lambda c: c[0]\n"
                                "async def is_synthetic(t):\n    return False\n",
            # one directory down: the old glob was hooks/*.py, non-recursive
            "hooks/lib/user_turns.py": "def scan(e):\n    return e.get('sourceToolUseID')\n",
            # a sibling directory entirely: the old scan never left hooks/
            "tools/turn_classifier.py": "SYNTHETIC_PREFIXES = ('<command-args>',)\n",
        }
        for _rel, _src in _plant.items():
            with open(_os.path.join(_td, _rel.replace("/", _os.sep)), "w",
                      encoding="utf-8") as _fh:
                _fh.write(_src)
        # NEGATIVE controls: a guard that flags everything proves nothing
        with open(_os.path.join(_h, "importer.py"), "w", encoding="utf-8") as _fh:
            _fh.write("import transcript_util\n"
                      "def go(e):\n    return transcript_util.is_genuine_user(e)\n")
        with open(_os.path.join(_h, "unrelated.py"), "w", encoding="utf-8") as _fh:
            _fh.write("def add(a, b):\n    return a + b\n")
        # an unparseable file must be REPORTED, never silently skipped
        with open(_os.path.join(_h, "broken.py"), "w", encoding="utf-8") as _fh:
            _fh.write("def (((\n")

        _found, _st = twin_offenders(_td)
        _blob = " ".join(_found)
        for _rel in _plant:
            if _rel not in _blob:
                fails.append("twin guard is BLIND to a planted %s - a detector that matches "
                             "nothing reports every repo as clean" % _rel)
        for _neg in ("importer.py", "unrelated.py"):
            if _neg in _blob:
                fails.append("twin guard flagged %s, which is not a twin - a guard that fires "
                             "on correct code gets disabled" % _neg)
        if _st["unreadable"] != 1:
            fails.append("an unparseable file was not reported as unreadable (%r); a file the "
                         "guard could not read must never count as clean" % (_st,))

    # THE TWIN MUST NOT COME BACK.
    twins, stats = twin_offenders()
    print("  [twin-guard] examined %d .py file(s) under %s: %d import this module, "
          "%d exempt, %d unreadable, %d offender(s)"
          % (stats["examined"], stats["root_label"], stats["imports_canonical"],
             stats["exempt"], stats["unreadable"], len(twins)))
    for problem in stats["exemption_problems"]:
        fails.append(problem)
    if stats["unreadable"]:
        fails.append("%d file(s) could not be parsed, so the twin question was NOT answered "
                     "for them: %r - an unread file is not a clean file"
                     % (stats["unreadable"], stats["unreadable_paths"]))
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
