"""meta-audit (Claude Code Stop hook) - a mechanical parked-work backstop.

At turn end, ONCE per session, this surfaces two grep-level facts about the project:
  (a) plan files in the repo ROOT (*PLAN*.md, no recursion) containing parked/deferred/TODO
      style markers on lines that carry NO decision tag (SCHEDULED/DECIDED/BACKLOG/...), i.e.
      work that is parked-and-hiding rather than parked-and-recorded;
  (b) commits sitting unpushed ahead of the upstream (surfaced only - never pushed).
If either exists it writes a short bullet list to stderr and exits 2 so Claude Code feeds it
back to the model; the REASONING about what to do belongs to the model/user (pairs with the
meta-review skill). Mechanical by design: pure regex + allowlist + `git rev-list --count`,
no judgment calls.

Guards (in order): unparseable stdin -> exit 0; stop_hook_active -> exit 0 (never loop);
per-session marker file under UNBLUFF_STATE_DIR (default ~/.claude/hooks/state) -> fires at most
once per session; no plan files / no findings / no upstream / any exception -> silent exit 0.
Run with --selftest to verify the mechanics (uses tempfile, never the real state dir).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

# ONE repo probe for the whole suite. This hook used os.path.exists(cwd/.git) and
# fast_test_on_stop used os.path.isdir(cwd/.git): two spellings of one question, each wrong in
# a different way (D5). stop_dispatcher already imports both modules in-process, so the import
# costs nothing new.
import fast_test_on_stop as fast_test  # noqa: E402  (path set above)
import capped_report  # noqa: E402  ONE way to cap a findings list, shared by five hooks
import plan_defer_guard  # noqa: E402  ONE plan-file predicate; this module had a twin of it
import selftest_budget  # noqa: E402  ONE declaration of the per-hook selftest cap

HOOK_NAME = "meta_audit_on_stop"
DEFAULT_STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "state")
MAX_FINDINGS_PER_FILE = 8
MAX_BULLET_LINES = 12
SNIPPET_LEN = 140
GIT_TIMEOUT_S = 10
SESSION_ID_CHARS = 12

# Markers, built from a STEM TABLE rather than hand-spelled alternation. The hand-spelled
# version read `PARKED?`, which requires the E and makes only the D optional: it matched the
# non-word "PARKE" and missed the bare "PARK" that the project's own plans use. The defect is
# invisible in that spelling and visible in this one, and the selftest below asserts every stem
# fires on its own (P13 B2).
_MARKER_STEMS = (("PARK", "ED"), ("DEFER", "RED"), ("TODO", ""), ("FIXME", ""),
                 ("UNSCHEDULED", ""))


def _marker_pattern() -> str:
    alts = []
    for stem, suffix in _MARKER_STEMS:
        body = stem + (f"(?:{suffix})?" if suffix else "")
        alts.append(body)
        cap = stem.capitalize()
        alts.append(cap + (f"(?:{suffix.lower()})?" if suffix else ""))
    return r"\b(?:" + "|".join(alts) + r")\b"


_MARKER_RE = re.compile(_marker_pattern())

# A line carrying a decision TAG is parked-and-RECORDED -> not a finding. A tag is ALL-CAPS
# (SCHEDULED, BACKLOG) or bracketed ("(backlog)", "[decided: no-go]"). It is NOT any occurrence
# of the word anywhere in the sentence: the old whole-line case-insensitive match suppressed
# "- TODO: make sure the socket is closed on shutdown" and "- PARKED: port the closed-loop
# controller", i.e. it silently dropped genuine hiding work whose prose happened to contain a
# common word. build_message() has always told the user to "tag the line", so tag position is
# the contract the hook already claimed (P13 B3).
_ALLOW_TAGS = ("scheduled", "slotted", "decided", "done", "deprioritized", "closed",
               "set-aside", "retired", "declined", "no-go", "historical", "superseded", "backlog")
_TAG_ALT = "|".join(rf"\b{re.escape(t)}\b" for t in _ALLOW_TAGS)
_ALLOW_CAPS_RE = re.compile("|".join(rf"\b{re.escape(t.upper())}\b" for t in _ALLOW_TAGS))
# [W-MA1] The bracket must BE the tag, not merely CONTAIN the word. The `[^)\]]*` that used to
# sit before the alternation let an allow-word appear anywhere inside any parenthesis, so
# "- PARKED: port the (closed-loop) controller" read as a decision tag: a genuine hiding line
# in the USER's own plan, silently suppressed AND subtracted from the reported total. This is
# P13 B3's defect surviving in the branch P13 B3 did not cover.
#
# Two constraints, and the SECOND is the one that matters. Anchoring the tag to the head of the
# bracket is not enough on its own - the review that found this prescribed exactly that, and it
# still matches "(closed-loop)", because `closed` IS at the head. MEASURED against a 12-case
# matrix before adopting: the prescribed form scored 7 of 12 and failed on its own headline
# example. So the tag must also be FOLLOWED by a separator or the bracket's end, which is what
# separates the tag `(closed)` from the compound word `(closed-form)`.
_ALLOW_BRACKET_RE = re.compile(rf"[(\[]\s*(?:{_TAG_ALT})(?:[\s:,;][^)\]]{{0,40}})?\s*[)\]]",
                               re.IGNORECASE)


def has_decision_tag(line: str) -> bool:
    """True iff the line carries a decision tag IN TAG POSITION (all-caps or bracketed)."""
    return bool(_ALLOW_CAPS_RE.search(line) or _ALLOW_BRACKET_RE.search(line))


def is_hiding_line(line: str) -> bool:
    """True iff the line carries a parked/TODO marker AND no decision tag in tag position."""
    if not _MARKER_RE.search(line):
        return False
    return not has_decision_tag(line)


def scan_plan_text(name: str, text: str) -> tuple[list[str], int]:
    """('name:lineno: <snippet>' findings capped per file, TOTAL hiding lines in the file).

    Returns the real total alongside the capped list. The previous version `break`ed out of the
    loop at the cap, which destroyed the total - so any "+N more" downstream could only ever
    under-report what it hid.
    """
    hits = (f"{name}:{lineno}: {line.strip()[:SNIPPET_LEN]}"
            for lineno, line in enumerate(text.splitlines(), 1) if is_hiding_line(line))
    return capped_report.keep(hits, MAX_FINDINGS_PER_FILE)


def find_plan_files(cwd: str) -> list[str]:
    """Repo-ROOT-only (no recursion) plan/roadmap .md files.

    Uses plan_defer_guard.is_plan_file - the SHARED predicate. This module carried its own
    `fnmatch(n, "*plan*.md")`, which is a substring match: "explanation.md" is a plan file to
    it. Two spellings of one question, each wrong the same way (P13 D1)."""
    if not cwd or not os.path.isdir(cwd):
        return []
    try:
        names = sorted(os.listdir(cwd))
    except OSError:
        return []
    return [os.path.join(cwd, n) for n in names
            if plan_defer_guard.is_plan_file(n) and os.path.isfile(os.path.join(cwd, n))]


def _git(cwd: str, *args: str) -> str | None:
    """git stdout, or None when git could not answer. ONE error mapping for all call sites."""
    try:
        proc = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                              timeout=GIT_TIMEOUT_S, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def count_unpushed(cwd: str) -> int:
    """Commits that exist only on this machine, or 0 when there is genuinely nothing to push.

    `@{u}..HEAD` exits 128 when the branch has no upstream, and that was mapped to 0 - the same
    value as "clean and synced". A branch created with `git checkout -b` and never pushed was
    therefore byte-identical to a fully-pushed tree, for its entire pre-first-push life, which
    is exactly when the reminder is worth having (P13 B1).

    Three states, not two:
      * no remote configured at all -> nothing to push anywhere; 0 is correct and silence right
      * upstream set               -> commits ahead of it
      * remote exists, no upstream -> commits on NO remote-tracking ref, which is strictly
                                      worse than being ahead of one

    The repo probe is SHARED with fast_test_on_stop (D5's twin): two probes for one question
    is itself the defect.
    """
    if not cwd or not fast_test.is_git_worktree(cwd):
        return 0
    ahead = _git(cwd, "rev-list", "--count", "@{u}..HEAD")
    if ahead is None:
        remotes = _git(cwd, "remote")
        if remotes is None or not remotes.strip():
            return 0
        ahead = _git(cwd, "rev-list", "--count", "HEAD", "--not", "--remotes")
        if ahead is None:
            return 0
    try:
        return max(0, int(ahead.strip()))
    except ValueError:
        return 0


# A DECLARATION, not a mention: the token has to open a line (heading, bullet, blockquote,
# bold or a "Status:" prefix). `"superseded" in head.lower()` matched an ACTIVE plan whose
# header said "Replaces PLAN_V2.md, which is superseded" - and skipped the entire file (P13 B4).
_SUPERSEDED_DECL_RE = re.compile(
    r"^\s*(?:[#>*\-\s]*)(?:status\s*[:\-]\s*)?\**\s*superseded\b", re.IGNORECASE)


def _is_superseded(text: str) -> bool:
    """True iff one of the first 5 lines DECLARES the file superseded (frozen history - its
    parked markers are a historical record, not hiding work, so nagging about them is noise)."""
    return any(_SUPERSEDED_DECL_RE.match(line) for line in text.splitlines()[:5])


def collect_findings(cwd: str) -> tuple[list[str], int]:
    """(findings, real total) for a project dir.

    The unpushed bullet goes FIRST. It used to be appended last, which made it the first thing
    the display cap discarded - so the warning vanished precisely when there was other work to
    report. It is also the only finding here that is not repeatable on the next read: a plan
    line stays in the file, an unpushed commit is state the user needs told about now.
    """
    plan_findings: list[str] = []
    total = 0
    for path in find_plan_files(cwd):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        if _is_superseded(text):
            continue
        kept, file_total = scan_plan_text(os.path.basename(path), text)
        plan_findings.extend(kept)
        total += file_total
    unpushed = count_unpushed(cwd)
    head = ([f"{unpushed} commit(s) unpushed (push only on user say-so - surface, not push)"]
            if unpushed > 0 else [])
    return head + plan_findings, total + len(head)


def build_message(findings: list[str], total: int | None = None) -> str:
    """The exact stderr text fed back to the model on fire."""
    lines = ["[meta-audit] parked/unpushed state at stop:"]
    lines.extend(capped_report.render(findings, MAX_BULLET_LINES, total=total))
    lines.append("Schedule each named item into the plan order, or tag the line with its "
                 "decision (SCHEDULED/DECIDED/BACKLOG/...).")
    return "\n".join(lines) + "\n"


def marker_path(state_dir: str, session_id: str) -> str:
    sid = (str(session_id) if session_id else "nosession")[:SESSION_ID_CHARS]
    return os.path.join(state_dir, f"{HOOK_NAME}-{sid}.done")


def run(payload: dict, state_dir: str) -> tuple[int, str]:
    """Core decision, testable in isolation: (exit_code, stderr_text).

    Writes the once-per-session marker into state_dir only when firing.
    """
    if payload.get("stop_hook_active"):  # already continuing from a stop hook - never loop
        return 0, ""
    marker = marker_path(state_dir, payload.get("session_id") or "nosession")
    if os.path.exists(marker):  # already fired this session
        return 0, ""
    findings, total = collect_findings(payload.get("cwd") or "")
    if not findings:
        return 0, ""
    os.makedirs(state_dir, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(f"fired {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    return 2, build_message(findings, total)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        state_dir = os.environ.get("UNBLUFF_STATE_DIR") or DEFAULT_STATE_DIR
        code, message = run(payload, state_dir)
        if code == 2 and message:
            sys.stderr.write(message)
        return code
    except Exception:  # a broken hook must never block the user
        return 0


def _selftest_line_cases() -> list[str]:
    """Pure line-classifier fixtures. Returns failure strings."""
    cases = [  # (line, expect_finding)
        ("- PARKED: investigate cache misses", True),               # known SHOULD-FIRE
        ("- DEFERRED (SCHEDULED 2026-07-02): xyz", False),          # known should-NOT-fire
        ("TODO: rewrite the parser", True),
        ("FIXME later (backlog)", False),
        ("Deferred: revisit auth flow", True),
        ("Parked: rename module", True),
        ("- parked lowercase is prose, not a marker", False),
        ("UNSCHEDULED spike on cache layer", True),
        ("- DEFERRED (decided: no-go)", False),
        ("nothing interesting on this line", False),
        # [P13 B2] the bare stem. `PARKED?` required the E, so it matched the non-word
        # "PARKE" and missed "PARK" - the spelling the project's own plans use.
        ("- PARK: investigate cache misses", True),
        ("- Park: rename module", True),
        ("- PARKE: not a word", False),
        ("- PARK (SCHEDULED 2026-08-01): x", False),   # allow-tag still wins over the stem
        ("PARKING lot resurfacing", False),            # \b must still exclude longer words
        # [P13 B3] an allow-WORD in the item's own prose is not a decision TAG. Each of these
        # is genuine hiding work that the whole-line case-insensitive match used to suppress.
        ("- TODO: make sure the socket is closed on shutdown", True),
        ("- PARKED: port the closed-loop controller from the legacy branch", True),
        ("- FIXME: the export is not done when the user navigates away", True),
        ("- DEFERRED: drop the retired v1 endpoints", True),
        ("- TODO (done 2026-06-30): shipped", False),  # bracketed tag still suppresses
        ("- DEFERRED SCHEDULED for the 2026-08 milestone", False),   # all-caps tag, unbracketed
        # [W-MA1] The BRACKETED half of the same defect. P13 B3 fixed the unbracketed cases
        # directly above and left this branch with no fixture at all: _ALLOW_BRACKET_RE
        # accepted an allow-word ANYWHERE inside the brackets, so ordinary prose in
        # parentheses read as a decision TAG - and a hiding line suppressed this way is also
        # subtracted from the total, so the report under-counts as well as under-reports.
        # These fire through is_hiding_line(), the DECISION, not through the regex.
        ("- PARKED: port the (closed-loop) controller", True),
        ("- TODO: retry when the (done-for-now) flag flips", True),
        ("- PARKED: rewrite the (scheduled-task) runner", True),
        ("- TODO: audit every (historical-import) path", True),
        ("- PARKED: see notes (the loop is closed, mostly) about timing", True),
        # ...and a REAL bracketed tag must still suppress, in every shape the hook's own
        # message tells the user to write. Without these the fix could simply delete the
        # bracket branch and "pass".
        ("- PARKED: port the controller (backlog)", False),
        ("- PARKED: port the controller [decided: no-go]", False),
        ("- TODO: rewrite the parser (scheduled for v1.4)", False),
        ("- PARKED: skip (set-aside, revisit in Q3)", False),
    ]
    fails = [f"is_hiding_line({line!r}) != {want}"
             for line, want in cases if is_hiding_line(line) is not want]
    # [P13 B2, class-level] every stem must fire on its own, and no proper prefix of a stem
    # may fire. This is what catches a mis-grouped suffix however the pattern is respelled.
    for stem, suffix in _MARKER_STEMS:
        if not is_hiding_line(f"- {stem}: x"):
            fails.append(f"marker stem {stem!r} does not fire on its own")
        if suffix and not is_hiding_line(f"- {stem}{suffix}: x"):
            fails.append(f"marker stem {stem!r} does not fire with its suffix {suffix!r}")
        if len(stem) > 3 and is_hiding_line(f"- {stem[:-1]}: x"):
            fails.append(f"a proper prefix of {stem!r} fires - the suffix is mis-grouped")
    text = "\n".join("- TODO item %d" % i for i in range(20))
    got, total = scan_plan_text("PLAN.md", text)
    if len(got) != MAX_FINDINGS_PER_FILE:
        fails.append(f"per-file cap wrong: {len(got)} findings")
    if total != 20:
        fails.append(f"per-file scan reported total {total}, expected the real 20 - a cap that "
                     f"stops counting makes every downstream '+N more' under-report")
    if got and got[0] != "PLAN.md:1: - TODO item 0":
        fails.append(f"finding format wrong: {got[0]!r}")
    return fails


def _selftest_bullet_cap() -> list[str]:
    """[P13 B5] The cap must never eat the unpushed bullet, and must never truncate silently."""
    fails = []
    unpushed = "3 commit(s) unpushed (push only on user say-so - surface, not push)"
    overflow = [f"PLAN.md:{i}: - TODO {i}" for i in range(MAX_BULLET_LINES + 4)]

    msg = build_message([unpushed] + overflow, total=len(overflow) + 1)
    if unpushed not in msg:
        fails.append("the unpushed bullet was dropped by the display cap - it is the one "
                     "finding that is not repeatable on the next read")
    if "more finding(s) not shown" not in msg:
        fails.append(f"build_message truncated with no notice: {msg!r}")
    if str(len(overflow) + 1) not in msg:
        fails.append(f"the truncation notice does not name the real total: {msg!r}")
    short = build_message(["only one"], total=1)
    if "not shown" in short:
        fails.append(f"build_message invented a truncation notice: {short!r}")
    return fails


def _selftest_pipeline() -> list[str]:
    """End-to-end run() fixtures in tempfile dirs (never the real state dir)."""
    import tempfile
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as state:
        with open(os.path.join(proj, "PLAN.md"), "w", encoding="utf-8") as f:
            f.write("- PARKED: investigate cache misses\n- DEFERRED (SCHEDULED 2026-07-02): xyz\n")
        payload = {"session_id": "selftest-session-abc", "cwd": proj}
        code, msg = run(payload, state)  # SHOULD-FIRE
        if code != 2 or "PLAN.md:1" not in msg or "[meta-audit]" not in msg:
            fails.append(f"should-fire pipeline wrong: code={code} msg={msg!r}")
        if msg.count("\n- ") != 1:  # exactly one bullet: the hiding line, not the allowed one
            fails.append(f"expected exactly 1 bullet, got: {msg!r}")
        if not os.path.exists(marker_path(state, payload["session_id"])):
            fails.append("marker not written on fire")
        code2, msg2 = run(payload, state)  # same session again -> silent
        if (code2, msg2) != (0, ""):
            fails.append(f"second fire in same session: code={code2} msg={msg2!r}")
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as state:
        with open(os.path.join(proj, "PLAN.md"), "w", encoding="utf-8") as f:
            f.write("- DEFERRED (BACKLOG): xyz\n- TODO (done 2026-06-30): shipped\n")
        code, msg = run({"session_id": "s2", "cwd": proj}, state)  # should-NOT-fire
        if (code, msg) != (0, ""):
            fails.append(f"allowed-only plan fired: code={code} msg={msg!r}")
        if os.listdir(state):
            fails.append("marker written on a non-firing run")
        code, msg = run({"session_id": "s3", "cwd": proj, "stop_hook_active": True}, state)
        if (code, msg) != (0, ""):
            fails.append("stop_hook_active not honored")
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as state:
        with open(os.path.join(proj, "OLD_PLAN.md"), "w", encoding="utf-8") as f:
            f.write("# SUPERSEDED - historical only\n\n- PARKED: ancient item\n- TODO: never\n")
        code, msg = run({"session_id": "s4", "cwd": proj}, state)  # superseded file -> skipped
        if (code, msg) != (0, ""):
            fails.append(f"superseded plan file not skipped: code={code} msg={msg!r}")
    # [P13 B4] the counter-case: an ACTIVE plan that merely MENTIONS the word, in prose and in
    # a filename, must NOT be skipped. `"superseded" in head.lower()` skipped the whole file.
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as state:
        with open(os.path.join(proj, "MASTER_PLAN.md"), "w", encoding="utf-8") as f:
            f.write("# MASTER PLAN (v3) - ACTIVE\n"
                    "Status: ACTIVE\n"
                    "Replaces PLAN_V2.md, which is superseded as of 2026-07-01.\n"
                    "See also: archive/SUPERSEDED_PLAN_V1.md\n\n"
                    "- PARKED: investigate cache misses\n")
        code, msg = run({"session_id": "s5", "cwd": proj}, state)
        if code != 2 or "PARKED" not in msg:
            fails.append("an ACTIVE plan that only MENTIONS 'superseded' (in prose and in a "
                         f"filename) was skipped entirely: code={code} msg={msg!r}")
    return fails


def _selftest_repo_probe() -> list:
    """[D5 twin] The repo probe must be the SHARED one.

    This module used os.path.exists(cwd/.git) while fast_test_on_stop used os.path.isdir - two
    spellings of one question, each wrong in a different way, and only one of them was ever
    fixed. The durable property is not "this file's probe is correct" but "this file has no
    probe of its own", so that is what gets asserted. Structural, so it holds however the
    surrounding code is refactored.
    """
    fails = []
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        return [f"could not read own source for the twin check: {e}"]
    private_probe = re.search(
        r"os\.path\.(?:exists|isdir|isfile)\(\s*os\.path\.join\(\s*cwd\s*,\s*[\"']\.git[\"']",
        src)
    if private_probe:
        fails.append("meta_audit has its own .git probe again (%r) - call "
                     "fast_test.is_git_worktree instead; two probes for one question is the "
                     "defect" % (private_probe.group(0)[:60],))
    # BEHAVIOURAL, not textual. The previous check was `if "fast_test.is_git_worktree" not in
    # src` - and that literal appears in the assertion itself, so the string was present four
    # times and three survived deleting the production call. Mutation-tested by the review:
    # replacing the real probe with `os.path.exists(os.path.join(cwd, ".gitx"))` still printed
    # SELFTEST OK. A test that greps for a string it itself contains cannot fail.
    #
    # Instead: replace the shared probe with a recorder and require the production path to
    # actually call it. No comment, docstring or spelling variant can satisfy this.
    called = []
    real_probe = fast_test.is_git_worktree

    def _recording_probe(cwd):
        called.append(cwd)
        return False

    fast_test.is_git_worktree = _recording_probe
    try:
        count_unpushed(os.path.dirname(os.path.abspath(__file__)))
    except Exception as exc:
        fails.append(f"count_unpushed raised while probing: {exc!r}")
    finally:
        fast_test.is_git_worktree = real_probe
    if not called:
        fails.append("count_unpushed does not call the SHARED repo probe - it has grown its "
                     "own again, which is the twin this check exists to prevent")

    # [HIGH-6] HERMETIC. This asserted `is_git_worktree(this file's directory)` - a claim about
    # the REAL environment. mutation_check copies hooks/ into a plain tempdir with no .git, so
    # the baseline was ALREADY RED there and mutations M6 and D5-twin were certified CAUGHT for
    # an identity edit. A selftest that depends on where its file happens to live cannot
    # distinguish a broken probe from a scratch directory. Build the repo the test needs.
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        try:
            ok = _sp.run(["git", "-C", _td, "init", "-q"], capture_output=True,
                         timeout=60).returncode == 0
        except (OSError, _sp.SubprocessError):
            ok = False
        if not ok:
            print("SELFTEST SKIP: git unavailable, repo-probe cases untested")
        else:
            sub = os.path.join(_td, "pkg", "deep")
            os.makedirs(sub, exist_ok=True)
            if not fast_test.is_git_worktree(_td):
                fails.append("shared probe says a plain repo is not a work tree")
            if not fast_test.is_git_worktree(sub):
                fails.append("shared probe says a SUBDIRECTORY of a repo is not a work tree")
            with _tf.TemporaryDirectory() as _plain:
                if fast_test.is_git_worktree(_plain):
                    fails.append("shared probe says a non-repo directory IS a work tree")
    return fails


def _selftest_unpushed() -> list:
    """[P13 B1] HERMETIC: builds the four repo shapes, per the HIGH-6 lesson recorded above.

    The distinction under test is the one the old code could not express: "nothing to push"
    and "these commits exist on no remote at all" both returned 0.
    """
    import subprocess as _sp
    import tempfile as _tf
    fails = []
    with _tf.TemporaryDirectory() as td:
        def sh(cwd, *a):
            return _sp.run(["git", "-C", cwd, *a], capture_output=True, text=True, timeout=60,
                           stdin=_sp.DEVNULL)
        bare = os.path.join(td, "remote.git")
        try:
            if _sp.run(["git", "init", "-q", "--bare", bare], capture_output=True,
                       timeout=60).returncode != 0:
                print("SELFTEST SKIP: git unavailable, unpushed cases untested")
                return []
        except (OSError, _sp.SubprocessError):
            print("SELFTEST SKIP: git unavailable, unpushed cases untested")
            return []

        # A: a repo with NO remote at all -> genuinely nothing to push, silence is correct
        solo = os.path.join(td, "solo")
        os.makedirs(solo)
        sh(solo, "init", "-q")
        sh(solo, "config", "user.email", "t@t")
        sh(solo, "config", "user.name", "t")
        with open(os.path.join(solo, "f.txt"), "w", encoding="utf-8") as f:
            f.write("x\n")
        sh(solo, "add", "-A")
        sh(solo, "commit", "-q", "-m", "local only")
        if count_unpushed(solo) != 0:
            fails.append("a repo with no remote reported unpushed commits - there is nowhere "
                         "to push them, so this is a false positive")

        # B/C/D: a clone. synced -> 0; ahead of upstream -> N; branch never pushed -> N
        work = os.path.join(td, "work")
        if _sp.run(["git", "clone", "-q", bare, work], capture_output=True,
                   timeout=60).returncode != 0:
            print("SELFTEST SKIP: git clone unavailable, unpushed cases untested")
            return []
        sh(work, "config", "user.email", "t@t")
        sh(work, "config", "user.name", "t")
        with open(os.path.join(work, "f.txt"), "w", encoding="utf-8") as f:
            f.write("x\n")
        sh(work, "add", "-A")
        sh(work, "commit", "-q", "-m", "base")
        sh(work, "push", "-q", "-u", "origin", "HEAD:refs/heads/main")
        if count_unpushed(work) != 0:
            fails.append("a synced clone reported unpushed commits")
        with open(os.path.join(work, "g.txt"), "w", encoding="utf-8") as f:
            f.write("y\n")
        sh(work, "add", "-A")
        sh(work, "commit", "-q", "-m", "ahead of upstream")
        if count_unpushed(work) != 1:
            fails.append("a clone 1 commit ahead of its upstream did not report 1")
        # D: THE REGRESSION. New branch, never pushed, so `@{u}` fails with rc=128.
        sh(work, "checkout", "-q", "-b", "feature")
        with open(os.path.join(work, "h.txt"), "w", encoding="utf-8") as f:
            f.write("z\n")
        sh(work, "add", "-A")
        sh(work, "commit", "-q", "-m", "on a branch that was never pushed")
        got = count_unpushed(work)
        if got < 1:
            fails.append("a branch that was never pushed reported %r unpushed commits - its "
                         "commits exist on NO remote, which is strictly worse than being ahead "
                         "of one, yet it looked identical to a clean synced tree" % (got,))

        # [P13 B5] ORDERING, through collect_findings rather than through build_message: with
        # enough plan findings to overflow the display cap, the unpushed bullet must still be
        # in the rendered message. Appended last, it was the first thing the cap discarded -
        # the warning vanished exactly when there was other work to report.
        with open(os.path.join(work, "PLAN.md"), "w", encoding="utf-8") as f:
            f.write("\n".join("- TODO overflow item %d" % i
                              for i in range(MAX_BULLET_LINES + 6)) + "\n")
        findings, total = collect_findings(work)
        if not findings or "unpushed" not in findings[0]:
            fails.append("the unpushed bullet is not first in collect_findings, so the display "
                         "cap can discard it: %r" % (findings[:2],))
        msg = build_message(findings, total)
        if "unpushed" not in msg:
            fails.append("the unpushed warning was dropped from the rendered message by the "
                         "bullet cap: %r" % (msg,))
        if "not shown" not in msg:
            fails.append("more findings than the cap, but the message truncated in silence")
    return fails


def selftest() -> int:
    fails = (_selftest_line_cases() + _selftest_bullet_cap() + _selftest_pipeline()
             + _selftest_repo_probe() + _selftest_unpushed())
    # [P14 D1] share 0.70 = 17.5s. Measured 2026-08-02: 13.30s, 53% of the cap.
    fails += selftest_budget.report(0.70, "meta_audit_on_stop")
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
