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

import fnmatch
import json
import os
import re
import subprocess
import sys
import time

HOOK_NAME = "meta_audit_on_stop"
DEFAULT_STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "state")
MAX_FINDINGS_PER_FILE = 8
MAX_BULLET_LINES = 12
SNIPPET_LEN = 140
GIT_TIMEOUT_S = 10
SESSION_ID_CHARS = 12

# Uppercase markers per spec, plus the capitalized 'Parked'/'Deferred' variants.
_MARKER_RE = re.compile(r"\b(?:PARKED?|Parked?|DEFER(?:RED)?|Defer(?:red)?|TODO|FIXME|UNSCHEDULED)\b")
# A line containing any of these (case-insensitive) is parked-and-RECORDED -> not a finding.
# Word-bounded so 'UNSCHEDULED' is not swallowed by 'scheduled' nor 'abandoned' by 'done'.
_ALLOW_TAGS = ("scheduled", "slotted", "decided", "done", "deprioritized", "closed",
               "set-aside", "retired", "declined", "no-go", "historical", "superseded", "backlog")
_ALLOW_RE = re.compile("|".join(rf"\b{re.escape(t)}\b" for t in _ALLOW_TAGS), re.IGNORECASE)


def is_hiding_line(line: str) -> bool:
    """True iff the line carries a parked/TODO marker AND no decision allow-tag."""
    if not _MARKER_RE.search(line):
        return False
    return not _ALLOW_RE.search(line)


def scan_plan_text(name: str, text: str) -> list[str]:
    """'name:lineno: <snippet>' findings for one plan file's text (capped per file)."""
    findings: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if len(findings) >= MAX_FINDINGS_PER_FILE:
            break
        if is_hiding_line(line):
            findings.append(f"{name}:{lineno}: {line.strip()[:SNIPPET_LEN]}")
    return findings


def find_plan_files(cwd: str) -> list[str]:
    """Repo-ROOT-only (no recursion) *PLAN*.md files, matched case-insensitively."""
    if not cwd or not os.path.isdir(cwd):
        return []
    try:
        names = sorted(os.listdir(cwd))
    except OSError:
        return []
    return [os.path.join(cwd, n) for n in names
            if fnmatch.fnmatch(n.lower(), "*plan*.md") and os.path.isfile(os.path.join(cwd, n))]


def count_unpushed(cwd: str) -> int:
    """Commits ahead of upstream, or 0 on any problem (no repo/no upstream/no git/timeout)."""
    if not cwd or not os.path.exists(os.path.join(cwd, ".git")):
        return 0
    try:
        proc = subprocess.run(["git", "-C", cwd, "rev-list", "--count", "@{u}..HEAD"],
                              capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return 0
    if proc.returncode != 0:
        return 0
    try:
        return max(0, int(proc.stdout.strip()))
    except ValueError:
        return 0


def _is_superseded(text: str) -> bool:
    """True iff the file declares itself SUPERSEDED in its first 5 lines (frozen history -
    its parked markers are historical record, not hiding work; nagging about them is noise)."""
    head = "\n".join(text.splitlines()[:5])
    return "superseded" in head.lower()


def collect_findings(cwd: str) -> list[str]:
    """All findings for a project dir: hiding plan lines first, then unpushed-commit count."""
    findings: list[str] = []
    for path in find_plan_files(cwd):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        if _is_superseded(text):
            continue
        findings.extend(scan_plan_text(os.path.basename(path), text))
    unpushed = count_unpushed(cwd)
    if unpushed > 0:
        findings.append(f"{unpushed} commit(s) unpushed (push only on user say-so - surface, not push)")
    return findings


def build_message(findings: list[str]) -> str:
    """The exact stderr text fed back to the model on fire."""
    lines = ["[meta-audit] parked/unpushed state at stop:"]
    lines.extend(f"- {item}" for item in findings[:MAX_BULLET_LINES])
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
    findings = collect_findings(payload.get("cwd") or "")
    if not findings:
        return 0, ""
    os.makedirs(state_dir, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(f"fired {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    return 2, build_message(findings)


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
    ]
    fails = [f"is_hiding_line({line!r}) != {want}"
             for line, want in cases if is_hiding_line(line) is not want]
    text = "\n".join("- TODO item %d" % i for i in range(20))
    got = scan_plan_text("PLAN.md", text)
    if len(got) != MAX_FINDINGS_PER_FILE:
        fails.append(f"per-file cap wrong: {len(got)} findings")
    if got and got[0] != "PLAN.md:1: - TODO item 0":
        fails.append(f"finding format wrong: {got[0]!r}")
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
    return fails


def selftest() -> int:
    fails = _selftest_line_cases() + _selftest_pipeline()
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
