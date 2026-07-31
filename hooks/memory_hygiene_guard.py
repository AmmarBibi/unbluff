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


PROJECT_DIR_MAX = 200   # Claude Code truncates at 200, then appends "-" + a hash of the input


def sanitize_cwd(cwd: str) -> str:
    """Replicate Claude Code's project-dir sanitization.

    Ground truth from the shipped binary:
        replace(/[^a-zA-Z0-9]/g, "-"); if len <= 200 return it; else slice(0,200)+"-"+hash

    The previous version replaced only ':' '\\' and '/', and implemented no truncation at all.
    Any project path containing an underscore, a dot, a space, or exceeding 200 sanitized
    characters therefore resolved to a directory that does not exist, os.path.isdir failed,
    and main() returned 0 on every Stop - permanently, silently, indistinguishable from
    "this project's memory is clean". Reproduced: `my_project` returned 0 with seeded rot
    while `Downloads\\Claude` returned 2 - which is exactly why it looked healthy on the
    author's machine and did nothing for anyone whose path holds a `_`, `.` or space.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9]", "-", cwd)
    return sanitized if len(sanitized) <= PROJECT_DIR_MAX else sanitized[:PROJECT_DIR_MAX]


def resolve_memory_dir(projects_root: str, cwd: str):
    """(memory_dir, reason) - reason is None on success, else why it could not be located.

    The >200-char case appends "-<hash>" after the slice and that hash is not reproducible
    here, so it is resolved by PREFIX MATCH and only when the candidate is unique. Returning a
    reason instead of a path is what lets main() say "could not locate" rather than pass
    silently: a directory that cannot be found is an unanswered question, not a clean tree.
    """
    exact = os.path.join(projects_root, sanitize_cwd(cwd), "memory")
    if os.path.isdir(exact):
        return exact, None
    full = re.sub(r"[^a-zA-Z0-9]", "-", cwd)
    if len(full) <= PROJECT_DIR_MAX:
        return None, f"no memory dir for this project at {exact}"
    prefix = sanitize_cwd(cwd) + "-"
    try:
        names = [n for n in os.listdir(projects_root) if n.startswith(prefix)]
    except OSError as exc:
        return None, f"cannot read {projects_root} ({exc})"
    if len(names) != 1:
        return None, (f"{len(names)} candidate project dirs match the truncated name "
                      f"{prefix!r}; refusing to guess")
    candidate = os.path.join(projects_root, names[0], "memory")
    if not os.path.isdir(candidate):
        return None, f"no memory dir at {candidate}"
    return candidate, None


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
    memory_dir, why = resolve_memory_dir(projects_root, cwd)
    if memory_dir is None:
        # INCONCLUSIVE, not clean - but still advisory (exit 0), and said once per session so
        # it cannot nag. Silence here was the bug: a sanitization mismatch disabled the hook
        # permanently and looked exactly like a healthy project.
        if os.path.isdir(projects_root):
            try:
                os.makedirs(state_dir, exist_ok=True)
                with open(marker, "w", encoding="utf-8") as fh:
                    fh.write("inconclusive\n")
            except OSError:
                pass
            sys.stderr.write(f"[memory-hygiene] could not check this project's memory: {why}. "
                             f"Nothing was verified.\n")
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


def _selftest_main(check) -> None:
    """[H5] END-TO-END coverage of main(). There was NONE.

    selftest() called only the two pure-function helpers, and stop_dispatcher's own selftest
    reaches main() but never sets UNBLUFF_PROJECTS_ROOT, so it bailed at the memory-dir check
    before any logic ran. Three disabling mutations - `return 2` -> `return 0`,
    `if not findings:` -> `if True:`, and dropping sanitize_cwd - each printed
    "memory_hygiene_guard: OK" under the full run_selftests.py. The hook worked; nothing
    verified that it kept working. It was the only Stop hook with no end-to-end path.
    """
    import io
    import tempfile

    def drive(cwd, projects_root, state_dir):
        real_in, real_err = sys.stdin, sys.stderr
        real_root = os.environ.get("UNBLUFF_PROJECTS_ROOT")
        real_state = os.environ.get("UNBLUFF_STATE_DIR")
        sys.stdin = io.StringIO(json.dumps({"session_id": "mh-test", "cwd": cwd}))
        sys.stderr = io.StringIO()
        os.environ["UNBLUFF_PROJECTS_ROOT"] = projects_root
        os.environ["UNBLUFF_STATE_DIR"] = state_dir
        try:
            rc = main()
            return rc, sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stderr = real_in, real_err
            for key, val in (("UNBLUFF_PROJECTS_ROOT", real_root),
                             ("UNBLUFF_STATE_DIR", real_state)):
                if val is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = val

    with tempfile.TemporaryDirectory() as td:
        # A path with an underscore, a dot and a space - each of which the old sanitizer got
        # wrong, silently disabling the hook for every project whose path contains one.
        cwd = os.path.join(td, "my_project.v2 beta")
        os.makedirs(cwd, exist_ok=True)
        root = os.path.join(td, "projects")
        mem = os.path.join(root, sanitize_cwd(cwd), "memory")
        os.makedirs(mem, exist_ok=True)
        with open(os.path.join(mem, "MEMORY.md"), "w", encoding="utf-8") as fh:
            # Real rot per INDEX_EVOLVING_RE: an index bullet carrying evolving state.
            fh.write("# Memory Index\n\n- [Thing](thing.md) - NEXT: retry the vendor call; "
                     "18 tests pass as of today\n")

        state = os.path.join(td, "state1")
        rc, err = drive(cwd, root, state)
        check("main() fires on seeded rot in a path with _ . and space (rc 2)", rc == 2)
        check("main() names itself in the message", "[memory-hygiene]" in err)
        check("main() wrote the once-per-session marker",
              os.path.exists(_marker_path(state, "mh-test")))
        rc2, err2 = drive(cwd, root, state)
        check("main() is silent on the second call in the same session",
              rc2 == 0 and err2 == "")

        # a clean memory dir must NOT fire
        clean_cwd = os.path.join(td, "clean_project")
        os.makedirs(clean_cwd, exist_ok=True)
        clean_mem = os.path.join(root, sanitize_cwd(clean_cwd), "memory")
        os.makedirs(clean_mem, exist_ok=True)
        with open(os.path.join(clean_mem, "MEMORY.md"), "w", encoding="utf-8") as fh:
            fh.write("# Memory Index\n\n- [Thing](thing.md) - durable pointer\n")
        rc3, err3 = drive(clean_cwd, root, os.path.join(td, "state2"))
        check("main() stays silent on a clean memory dir", rc3 == 0 and err3 == "")

        # [H4] a project whose memory dir cannot be located is INCONCLUSIVE, not clean
        missing_cwd = os.path.join(td, "nonexistent_project")
        os.makedirs(missing_cwd, exist_ok=True)
        rc4, err4 = drive(missing_cwd, root, os.path.join(td, "state3"))
        check("unlocatable memory dir reports inconclusive rather than passing silently",
              rc4 == 0 and "could not check" in err4)

    # sanitization must match Claude Code's rule, not a three-character approximation
    check("sanitize_cwd replaces every non-alphanumeric",
          sanitize_cwd("C:/a_b.c d/e") == "C--a-b-c-d-e")
    check("sanitize_cwd truncates at 200",
          len(sanitize_cwd("x" * 400)) == PROJECT_DIR_MAX)


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
    _selftest_main(check)
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
