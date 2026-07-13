#!/usr/bin/env python3
"""memory-hygiene guard - Stop hook (stdlib only).

WHAT IT DOES
    On session Stop, mechanically scans the auto-memory directory of the
    CURRENT project (<projects_root>/<sanitized cwd>/memory) for signs of
    memory rot:
      - MEMORY.md (the index): bloated bullet lines (> 400 chars), commit-hash
        tokens next to commit/HEAD/push words, and evolving-state markers
        (NEXT=/NEXT: or "N tests pass").
      - Every other *.md memory file: NEXT ORDER / NEXT = lines, "N tests
        pass" counts, and commit-hash tokens - but ONLY outside sections
        marked HISTORICAL / STALE BY DEFINITION / quarantined (section-aware
        scan; a '## ' heading without those words re-arms the scan).
    If any finding exists it prints an actionable summary to stderr and exits
    2 (Claude Code feeds stderr back to the model), at most ONCE per session
    via a marker file in the state dir.

WHY IT IS MECHANICAL
    No reasoning, no LLM calls, no heuristics beyond fixed regexes and one
    fixed length threshold. It only SURFACES rot; deciding what moves out of
    memory is the human/model's job. Good hygiene: memory keeps pointers +
    durable facts; fast-evolving state (next steps, test counts, live commit
    hashes) belongs in your project's plan/docs, not the long-lived memory.

GUARDS (in this order)
    1. Unparseable/empty stdin              -> exit 0 silently.
    2. payload['stop_hook_active'] truthy   -> exit 0 (never loop).
    3. Once-per-session marker exists       -> exit 0 before evaluating.
    4. Memory dir for this cwd missing      -> exit 0.
    5. ANY unexpected exception             -> exit 0 silently (a broken hook
       must never block the user).

ENV OVERRIDES (used by tests so they never touch real state/memory)
    UNBLUFF_STATE_DIR      marker directory   (default ~/.claude/hooks/state)
    UNBLUFF_PROJECTS_ROOT  projects root      (default ~/.claude/projects)

SELFTEST
    python memory_hygiene_guard.py --selftest
    Pure-function fixtures (tempfile only; real state dir untouched).
"""

from __future__ import annotations

import json
import os
import re
import sys

HOOK_NAME = "memory_hygiene_guard"
INDEX_FILE = "MEMORY.md"
MAX_INDEX_BULLET_LEN = 400
MAX_FINDINGS_PER_FILE = 6
MAX_BULLETS_IN_MESSAGE = 12
SNIPPET_LEN = 120
SESSION_ID_LEN = 12

DEFAULT_STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "state")
DEFAULT_PROJECTS_ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")

# Commit-hash-like token; only flagged when a commit-ish word is also present
# on the same line (avoids false hits on random hex/decimal ids).
HASH_TOKEN_RE = re.compile(r"\b[0-9a-f]{7,10}\b")
HASH_CONTEXT_RE = re.compile(r"\b(?:commits?|HEAD|push(?:ed|es)?)\b", re.IGNORECASE)
# MEMORY.md evolving-state markers.
INDEX_EVOLVING_RE = re.compile(r"\bNEXT\s*[=:]|\b\d+\s*(?:tests?|pytest)\s+pass")
# Non-index memory files.
PLAIN_NEXT_RE = re.compile(r"\bNEXT ORDER\b|\bNEXT\s*=")
PLAIN_TESTS_RE = re.compile(r"\b\d+\s*(?:tests?|pytest)\s+pass")
# Section-quarantine triggers (case-insensitive, anywhere on the line).
QUARANTINE_RE = re.compile(r"HISTORICAL|STALE BY DEFINITION|quarantined", re.IGNORECASE)

FOOTER = (
    "Move evolving state to the project plan/docs; memory keeps pointers + "
    "durable facts only."
)


def sanitize_cwd(cwd: str) -> str:
    """Replicate Claude Code's project-dir sanitization: ':' '\\' '/' -> '-'."""
    return cwd.replace(":", "-").replace("\\", "-").replace("/", "-")


def _snippet(line: str) -> str:
    """ASCII-safe first-120-chars snippet (console encoding must never throw)."""
    return "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in line)[:SNIPPET_LEN]


def _has_commit_hash(line: str) -> bool:
    return bool(HASH_TOKEN_RE.search(line)) and bool(HASH_CONTEXT_RE.search(line))


def scan_index_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Scan MEMORY.md index lines. Returns [(lineno, message)], capped."""
    findings: list[tuple[int, str]] = []
    for lineno, line in enumerate(lines, 1):
        if line.lstrip().startswith("- [") and len(line) > MAX_INDEX_BULLET_LEN:
            findings.append((lineno, "index line bloat - one short pointer per memory: " + _snippet(line)))
        elif _has_commit_hash(line):
            findings.append((lineno, "commit hash in index: " + _snippet(line)))
        elif INDEX_EVOLVING_RE.search(line):
            findings.append((lineno, "evolving state in index: " + _snippet(line)))
        if len(findings) >= MAX_FINDINGS_PER_FILE:
            break
    return findings


def scan_plain_lines(lines: list[str]) -> list[tuple[int, str]]:
    """Section-aware scan of a non-index memory file. Returns [(lineno, snippet)]."""
    findings: list[tuple[int, str]] = []
    in_quarantine = False
    for lineno, line in enumerate(lines, 1):
        if QUARANTINE_RE.search(line):
            in_quarantine = True
            continue
        if line.startswith("## "):
            in_quarantine = False
        if in_quarantine:
            continue
        if PLAIN_NEXT_RE.search(line) or PLAIN_TESTS_RE.search(line) or _has_commit_hash(line):
            findings.append((lineno, _snippet(line)))
            if len(findings) >= MAX_FINDINGS_PER_FILE:
                break
    return findings


def collect_findings(memory_dir: str) -> list[str]:
    """Scan all *.md files in memory_dir; return 'file:lineno: <msg>' strings."""
    try:
        names = sorted(os.listdir(memory_dir))
    except OSError:
        return []
    ordered = [n for n in names if n == INDEX_FILE] + [n for n in names if n != INDEX_FILE]
    findings: list[str] = []
    for name in ordered:
        if not name.lower().endswith(".md"):
            continue
        path = os.path.join(memory_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        pairs = scan_index_lines(lines) if name == INDEX_FILE else scan_plain_lines(lines)
        findings.extend(f"{name}:{lineno}: {message}" for lineno, message in pairs)
    return findings


def _marker_path(state_dir: str, session_id: object) -> str:
    sid = str(session_id or "").strip()
    sid = "".join(ch for ch in sid if ch.isalnum() or ch in "-_")[:SESSION_ID_LEN]
    if not sid:
        sid = "nosession"
    return os.path.join(state_dir, f"{HOOK_NAME}-{sid}.done")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("stop_hook_active"):
        return 0

    state_dir = os.environ.get("UNBLUFF_STATE_DIR") or DEFAULT_STATE_DIR
    marker = _marker_path(state_dir, payload.get("session_id"))
    if os.path.exists(marker):
        return 0

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return 0
    projects_root = os.environ.get("UNBLUFF_PROJECTS_ROOT") or DEFAULT_PROJECTS_ROOT
    memory_dir = os.path.join(projects_root, sanitize_cwd(cwd), "memory")
    if not os.path.isdir(memory_dir):
        return 0

    findings = collect_findings(memory_dir)
    if not findings:
        return 0

    os.makedirs(state_dir, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write("fired\n")

    out = ["[memory-hygiene] memory rot for this project:"]
    out.extend(f"  - {finding}" for finding in findings[:MAX_BULLETS_IN_MESSAGE])
    hidden = len(findings) - MAX_BULLETS_IN_MESSAGE
    if hidden > 0:
        out.append(f"  (+{hidden} more finding(s) not shown)")
    out.append(FOOTER)
    sys.stderr.write("\n".join(out) + "\n")
    return 2


# ----------------------------- selftest --------------------------------------


def _selftest_scans(check) -> None:
    """Pure-function fixture checks for the two scanners + sanitizer."""
    check("sanitize windows path", sanitize_cwd("C:\\Users\\a\\proj") == "C--Users-a-proj")
    check("sanitize posix path", sanitize_cwd("/home/a/proj") == "-home-a-proj")

    # MEMORY.md index fixtures.
    bloated = "- [Big](big.md) - " + "x" * 450
    got = scan_index_lines([bloated])
    check("SHOULD-FIRE index bloat >400", len(got) == 1 and "bloat" in got[0][1])
    got = scan_index_lines(["- [P](p.md) - fixed in commit abc1234 on main"])
    check("SHOULD-FIRE index commit hash + word", len(got) == 1 and got[0][0] == 1)
    got = scan_index_lines(["- [P](p.md) - request id deadbeef99 seen in logs"])
    check("should-NOT-fire bare hex token (no commit word)", got == [])
    got = scan_index_lines(["- [P](p.md) - NEXT: wire the API"])
    check("SHOULD-FIRE index NEXT:", len(got) == 1)
    got = scan_index_lines(["- [P](p.md) - 34 tests pass as of today"])
    check("SHOULD-FIRE index test count", len(got) == 1)
    got = scan_index_lines(["- [P](p.md) - short durable pointer, no rot"])
    check("should-NOT-fire clean index line", got == [])

    # Non-index (plain) fixtures with section awareness.
    got = scan_plain_lines(["# T", "NEXT ORDER: do x -> y"])
    check("SHOULD-FIRE plain NEXT ORDER outside quarantine", len(got) == 1 and got[0][0] == 2)
    got = scan_plain_lines(["# T", "## HISTORICAL BUILD LOG (quarantined)", "NEXT ORDER: do x -> y"])
    check("should-NOT-fire NEXT ORDER inside quarantine", got == [])
    got = scan_plain_lines(["## HISTORICAL", "NEXT = a", "## Current state", "NEXT = b"])
    check("SHOULD-FIRE after '## ' heading re-arms scan", len(got) == 1 and got[0][0] == 4)
    got = scan_plain_lines(["12 tests pass on branch main"])
    check("SHOULD-FIRE plain test count", len(got) == 1)
    got = scan_plain_lines(["pushed 9f8e7d6a5b to origin"])
    check("SHOULD-FIRE plain commit hash + push word", len(got) == 1)
    got = scan_plain_lines([f"NEXT = step {i}" for i in range(10)])
    check("cap 6 findings per file", len(got) == MAX_FINDINGS_PER_FILE)
    got = scan_plain_lines(["Durable fact: engine lives in src/."])
    check("should-NOT-fire clean plain line", got == [])


def _selftest_collect(check) -> None:
    """Integration fixtures via tempfile - never touches real state/memory."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        mem = os.path.join(tmp, "memory")
        os.makedirs(mem)
        with open(os.path.join(mem, "MEMORY.md"), "w", encoding="utf-8") as fh:
            fh.write("# Index\n\n- [P](p.md) - clean pointer\n")
        with open(os.path.join(mem, "p.md"), "w", encoding="utf-8") as fh:
            fh.write("# P\n\nDurable fact only.\n")
        check("should-NOT-fire collect on clean tree", collect_findings(mem) == [])

        with open(os.path.join(mem, "p.md"), "w", encoding="utf-8") as fh:
            fh.write("# P\n\nNEXT ORDER: do x -> y\n")
        got = collect_findings(mem)
        check(
            "SHOULD-FIRE collect on rot tree",
            len(got) == 1 and got[0].startswith("p.md:3: "),
        )


def selftest() -> int:
    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        if cond:
            print(f"SELFTEST OK: {name}")
        else:
            failures.append(name)
            print(f"SELFTEST FAIL: {name}")

    _selftest_scans(check)
    _selftest_collect(check)
    if failures:
        print(f"SELFTEST: FAILED ({len(failures)} failing check(s))")
        return 1
    print("SELFTEST: ALL OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        sys.exit(selftest())
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
