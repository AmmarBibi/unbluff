"""plan-defer-guard (Claude Code PostToolUse: Edit|Write|MultiEdit) - a soft-defer tripwire.

Complements meta_audit_on_stop, which catches UPPERCASE, un-tagged parked work at turn end.
This catches the class meta_audit deliberately ignores: the LOWERCASE "optional-forever" PHRASES
that read like a decision but silently mean never - `-> park`, `on demand`, `wait for a concrete
failing case`, `only on real user demand`, `deferred opportunistic`, `pick when value beats ...`.
Those markers slip past meta_audit (its regex treats lowercase 'park'/'defer' as prose, and its
allow-tags whitelist 'deprioritized'/'backlog'), so a badly-tagged deferral hides in plain sight.

When a plan/roadmap file (root or nested `*plan*.md` / `*roadmap*.md`) is written or edited, this
scans it ONCE per session for those phrases and, if any are present on a non-exempt line, writes a
short bullet list to stderr and exits 2 so Claude Code feeds it back. The point: reclassify each
into a scheduled item OR a finalized justified exclusion, so the plan has zero optional-forever
items. Reasoning about which belongs to the model/user - this is a mechanical grep, no judgment.

Guards (in order): unparseable stdin -> exit 0; not a plan/roadmap file -> exit 0; per-session
marker under UNBLUFF_STATE_DIR (default ~/.claude/hooks/state) -> fires at most once per session;
no findings / unreadable file / any exception -> silent exit 0. Mechanical, stdlib-only, fail-safe.
Run with --selftest to verify the mechanics (uses tempfile, never the real state dir).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
import time

HOOK_NAME = "plan_defer_guard"
DEFAULT_STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "state")
MAX_BULLET_LINES = 10
SNIPPET_LEN = 150
SESSION_ID_CHARS = 12

# The LOWERCASE optional-forever phrase class - specific phrasings, not bare words, so ordinary
# prose is not tripped. Case-insensitive. Deliberately does NOT include the UPPERCASE
# PARKED/DEFERRED/TODO markers - those are meta_audit_on_stop's job (zero overlap by design).
_MARKER_RE = re.compile(
    r"->\s*park\b"                       # "-> park"  (arrow-park, the classic optional-forever)
    r"|\bon[- ]demand\b"                 # "on demand" / "on-demand"
    r"|only on real user demand"
    r"|wait for a concrete"              # "wait for a concrete failing case"
    r"|deferred opportunistic"
    r"|pick when value beats"
    r"|\bsomeday\b"
    r"|\bmaybe later\b"
    r"|if time permits",
    re.IGNORECASE,
)

# A line that also carries one of these is a deliberate, recorded decision (reclassified or a
# finalized exclusion) - not an optional-forever hiding item, so it is exempt.
_EXEMPT_RE = re.compile(
    r"finalized|justified exclusion|no-defer|reclassif|was parked; now|now scheduled|"
    r"scheduled \(|completeness mandate|plan-defer-guard|source-coverage",
    re.IGNORECASE,
)

# Plan/roadmap file names this guard watches (basename, case-insensitive).
_PLAN_GLOBS = ("*plan*.md", "*roadmap*.md")


# A marker preceded by a negation within this many chars is the plan ASSERTING completeness
# ("NOT on-demand", "never on demand") - honest phrasing, not an optional-forever item. Mirrors
# show_your_proof's negation window so the guard rewards, not punishes, "NOT deferred".
_NEGATION_TOKENS = ("not ", "n't ", "never ", "without ")
_NEG_WINDOW = 16


def _negated(line: str, start: int) -> bool:
    """True if a negation token sits just before the marker match at `start`. Pure."""
    window = line[max(0, start - _NEG_WINDOW):start].lower()
    return any(tok in window for tok in _NEGATION_TOKENS)


def is_soft_defer_line(line: str) -> bool:
    """True iff the line carries a NON-negated optional-forever phrase AND is not an
    exempt/recorded decision. A marker that is negated ("NOT on-demand") does not count."""
    if _EXEMPT_RE.search(line):
        return False
    return any(not _negated(line, m.start()) for m in _MARKER_RE.finditer(line))


def is_plan_file(path: str) -> bool:
    base = os.path.basename(path or "").lower()
    return any(fnmatch.fnmatch(base, g) for g in _PLAN_GLOBS)


def scan_plan_text(name: str, text: str) -> list:
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if len(findings) >= MAX_BULLET_LINES:
            break
        if is_soft_defer_line(line):
            findings.append(f"{name}:{lineno}: {line.strip()[:SNIPPET_LEN]}")
    return findings


def build_message(name: str, findings: list) -> str:
    lines = [f"[plan-defer-guard] optional-forever language in {name}:"]
    lines.extend(f"- {item}" for item in findings)
    lines.append("Reclassify each into a SCHEDULED build item (materiality order) OR an explicit "
                 "FINALIZED justified exclusion - the plan must have zero optional-forever items. "
                 "(A grep only catches what the plan names; run the source-coverage skill for gaps "
                 "the plan does not mention.)")
    return "\n".join(lines) + "\n"


def marker_path(state_dir: str, session_id: str) -> str:
    sid = (str(session_id) if session_id else "nosession")[:SESSION_ID_CHARS]
    return os.path.join(state_dir, f"{HOOK_NAME}-{sid}.done")


def _tool_file(payload: dict) -> str:
    ti = payload.get("tool_input")
    return (ti.get("file_path") if isinstance(ti, dict) else "") or ""


def run(payload: dict, state_dir: str) -> tuple:
    """Core decision, testable in isolation: (exit_code, stderr_text).

    Writes the once-per-session marker into state_dir only when firing."""
    path = _tool_file(payload)
    if not is_plan_file(path):
        return 0, ""
    marker = marker_path(state_dir, payload.get("session_id") or "nosession")
    if os.path.exists(marker):  # already fired this session
        return 0, ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return 0, ""
    findings = scan_plan_text(os.path.basename(path), text)
    if not findings:
        return 0, ""
    os.makedirs(state_dir, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(f"fired {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    return 2, build_message(os.path.basename(path), findings)


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


def _selftest_line_cases() -> list:
    cases = [  # (line, expect_finding)
        ("| 9.9 | some item -> park.", True),
        ("| 9.8 | build only on demand later", True),
        ("| 9.7 | wait for a concrete failing case before building", True),
        ("| 9.6 | only on real user demand", True),
        ("| 9.5 | deferred opportunistic; pick when value beats next bug", True),
        ("| 9.4 | was parked; now scheduled 8.11", False),   # reclassified -> exempt
        ("| 9.3 | FINALIZED justified exclusion: not in corpus", False),
        ("| 9.2 | NO 'park' remains (completeness mandate)", False),
        ("| 9.15 | SCHEDULED as a real build item, NOT on-demand; ships next", False),  # negated
        ("| 9.12 | ships eagerly, never on demand", False),   # negated -> exempt
        ("| 9.1 | PARKED: uppercase is meta_audit's job, not ours", False),
        ("| 9.0 | ordinary roadmap prose with no marker", False),
    ]
    return [f"is_soft_defer_line({ln!r}) != {want}"
            for ln, want in cases if is_soft_defer_line(ln) is not want]


def _selftest_pipeline() -> list:
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as state:
        plan = os.path.join(d, "MASTER_PLAN.md")
        with open(plan, "w", encoding="utf-8") as f:
            f.write("| 1 | item -> park.\n| 2 | was parked; now scheduled\n")
        payload = {"session_id": "s-abc", "tool_input": {"file_path": plan}}
        code, msg = run(payload, state)  # SHOULD FIRE (line 1 only)
        if code != 2 or "MASTER_PLAN.md:1" not in msg or "[plan-defer-guard]" not in msg:
            fails.append(f"should-fire wrong: code={code} msg={msg!r}")
        if msg.count("\n- ") != 1:
            fails.append(f"expected exactly 1 bullet, got: {msg!r}")
        code2, msg2 = run(payload, state)  # same session -> silent
        if (code2, msg2) != (0, ""):
            fails.append(f"second fire same session: {code2} {msg2!r}")
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as state:
        clean = os.path.join(d, "ROADMAP.md")
        with open(clean, "w", encoding="utf-8") as f:
            f.write("| 1 | scheduled build\n| 2 | FINALIZED exclusion: n/a\n")
        code, msg = run({"session_id": "s2", "tool_input": {"file_path": clean}}, state)
        if (code, msg) != (0, ""):
            fails.append(f"clean plan fired: {code} {msg!r}")
        if os.listdir(state):
            fails.append("marker written on non-firing run")
        # non-plan file -> ignored even with a marker
        other = os.path.join(d, "notes.md")
        with open(other, "w", encoding="utf-8") as f:
            f.write("just build it -> park later\n")
        code, msg = run({"session_id": "s3", "tool_input": {"file_path": other}}, state)
        if (code, msg) != (0, ""):
            fails.append(f"non-plan file scanned: {code} {msg!r}")
    return fails


def selftest() -> int:
    fails = _selftest_line_cases() + _selftest_pipeline()
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
