"""numbers-match (Claude Code PostToolUse: Edit|Write|MultiEdit) - a numeric-drift tripwire.

The numeric analogue of show_your_proof. Where show_your_proof catches a SUCCESS CLAIM made
with no tool run, this catches a CITED NUMBER made with no source: when a report/output file is
written, it extracts the measurement-like numbers in the prose and checks each against the values
in a configured source-data folder. Any cited number with no matching source value (within
tolerance) is surfaced - the mechanical half of a "consistency-drift" audit. The REASONING half
(is an unmatched number drift, a derived quantity, or definitional?) belongs to the model/user, the
way meta-review pairs with meta_audit; this hook only surfaces the "number with no source" state.

Opt-in, per project. It does NOTHING unless the project provides `.claude/number-sources.txt`
(found by walking up from the written file). That file names the source dir(s):

    # .claude/number-sources.txt
    sources = results, data            # dirs/files (relative to .claude's parent, or absolute)
    reports = *REPORT*.md, *results*.md  # optional basename globs; default report/result-ish names
    tol = 0.01                         # optional relative tolerance (default 1%, absorbs rounding)
    check_integers = false             # optional; default off (only decimals/%/sci/units checked)

Only text deliverables are checked (.md/.txt/.tex/.rst/.markdown) - binary docx/pdf are the
consistency-audit skill's job, keeping this hook a pure stdlib check. To avoid noise it skips
cross-references ("Figure 3", "Table 2", "[12]"), years, and (by default) bare integers, checking
only measurement-shaped values - the ones that actually drift.

Guards (in order): unparseable stdin -> exit 0; not a text report file -> exit 0; no config /
no sources -> exit 0 (opt-in); per-(session, report) marker under UNBLUFF_STATE_DIR -> fires at most
once per report file per session; nothing unmatched / unreadable / any exception -> silent exit 0.
The source index is cached (keyed by source mtimes) so a clean report is not re-indexed every edit.
Mechanical, stdlib-only, fail-safe. Run with --selftest to verify (tempfile, never the real state dir).
"""
from __future__ import annotations

import bisect
import fnmatch
import glob
import hashlib
import json
import os
import re
import sys
import time

HOOK_NAME = "numbers_match_on_write"
DEFAULT_STATE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "state")
CONFIG_NAME = "number-sources.txt"
SESSION_ID_CHARS = 12
MAX_BULLETS = 12
# Hard cap on findings COLLECTED (display is capped at MAX_BULLETS). Separate numbers so
# the reported total is real: capping collection at the display width made the message
# state 12 when there were 40 (M2).
MAX_FINDINGS_TRACKED = 500
SNIPPET_LEN = 90
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_VALUES = 300_000
DEFAULT_TOL = 0.01
DEFAULT_REPORT_GLOBS = ("*report*.md", "*report*.txt", "*results*.md", "*results*.txt",
                        "*report*.tex", "*findings*.md", "*summary*.md")
TEXT_EXTS = (".md", ".markdown", ".txt", ".tex", ".rst")
# This hook is intentionally a self-contained, lighter cousin of the consistency-audit skill's
# extractor (skills/consistency-audit/scripts/sources.py) - a hook must stay import-free so the
# dispatcher can load it in-process. Keep SOURCE_EXTS in sync with that module; the H3 parity
# scenario in tests/test_integration.py guards against silent drift.
SOURCE_EXTS = (".csv", ".tsv", ".txt", ".dat", ".json", ".md", ".tab", ".out", ".log")

# number: optional sign, thousands-grouped or plain int, optional fraction, optional exponent.
_NUMBER_RE = re.compile(
    r"(?<![\w.])(?P<sign>[-+]?)(?P<int>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?P<frac>\.\d+)?(?P<exp>[eE][-+]?\d+)?"
)
_UNIT_RE = re.compile(
    r"\s?("
    r"%|dB|Hz|kHz|MHz|GHz|rad/s|rad|deg|°|"
    r"ms|us|µs|ns|s\b|min\b|hrs?\b|"
    r"mm|cm|km|nm|µm|um|m\b|"
    r"kg|mg|g\b|kN|mN|N·m|Nm|N\b|"
    r"kPa|MPa|Pa|kW|mW|W\b|kV|mV|V\b|mA|A\b|x\b|X\b"
    r")"
)
# The (?<![A-Za-z]) is LOAD-BEARING. Without a left word boundary this alternation is
# .search()ed against the 24 characters before every number and matches the TAIL of any word:
# "p" swallows "drop 0.85 kPa", "no" swallows "each 3.75 mm", "v" swallows "rev 1.75 s",
# "q" swallows "group 7.25 kg". 35 of 38 common technical words hid the number that followed,
# so a report whose only figures were fabricated extracted ZERO cited numbers and the hook
# returned a clean pass. Still skips "see Figure 3", "Table 2", "eq. 4", "p. 7".
_REF_PREFIX_RE = re.compile(
    r"(?<![A-Za-z])"
    r"(?:figure|fig|table|tbl|section|sect|sec|equation|eqn|eq|chapter|chap|ch|appendix|"
    r"app|reference|ref|step|stage|part|phase|question|q|item|version|v|no|number|num|"
    r"line|page|pg|p|slide|footnote|note)\.?\s*$",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?")


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def find_config(file_path: str, cwd: str) -> "tuple[str, str] | None":
    """Return (config_path, project_root) by walking up from the file, else from cwd."""
    starts = []
    if file_path:
        starts.append(os.path.dirname(os.path.abspath(file_path)))
    if cwd:
        starts.append(os.path.abspath(cwd))
    seen = set()
    for start in starts:
        cur = start
        while cur and cur not in seen:
            seen.add(cur)
            cand = os.path.join(cur, ".claude", CONFIG_NAME)
            if os.path.isfile(cand):
                return cand, cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return None


def parse_config(text: str) -> dict:
    """Parse the tiny key=value config. Unknown keys ignored; robust to junk."""
    cfg = {"sources": [], "reports": [], "tol": DEFAULT_TOL, "check_integers": False}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        # Strip a TRAILING comment too. Only a leading '#' was treated as a comment, so the
        # module's own documented example - `sources = results, data  # dirs/files ...` -
        # parsed into source paths of "data  # dirs/files (relative to .claude's parent" and
        # "or absolute)", a reports glob that can never match, tol silently reverting to the
        # default, and check_integers=False where the user wrote true. No template ships, so
        # the documented form was the only form a user could copy.
        val = val.split("#", 1)[0]
        key, val = key.strip().lower(), val.strip()
        if key == "sources":
            cfg["sources"] = [p.strip() for p in val.split(",") if p.strip()]
        elif key == "reports":
            cfg["reports"] = [p.strip() for p in val.split(",") if p.strip()]
        elif key == "tol":
            try:
                cfg["tol"] = max(0.0, float(val))
            except ValueError:
                pass
        elif key == "check_integers":
            cfg["check_integers"] = val.lower() in ("1", "true", "yes", "on")
    return cfg


# --------------------------------------------------------------------------- #
# Source index + number extraction (mechanical)
# --------------------------------------------------------------------------- #

def index_sources(dirs: "list[str]", root: str, exclude=()) -> "list[float]":
    """Sorted unique numeric values across the configured source dirs/files.

    `exclude` holds absolute paths that must NOT be indexed - in practice the report under
    check and anything else the config calls a report. SOURCE_EXTS includes ".md" and
    PostToolUse runs AFTER the write, so a report living inside a configured source dir was
    indexed as its own evidence: every fabricated number matched itself and the hook returned
    a clean pass. The index is also SHARED, so one fabricated .md left in the source tree
    silently exempted that value for every report in the project.
    """
    skip = {os.path.normcase(os.path.abspath(p)) for p in exclude}
    values = set()
    for entry in dirs:
        path = entry if os.path.isabs(entry) else os.path.join(root, entry)
        files = [path] if os.path.isfile(path) else _walk_source_files(path)
        for fpath in files:
            if os.path.normcase(os.path.abspath(fpath)) in skip:
                continue
            try:
                if os.path.getsize(fpath) > MAX_FILE_BYTES:
                    continue
                with open(fpath, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            for tok in _TOKEN_RE.finditer(text):
                try:
                    values.add(float(tok.group(0).replace(",", "")))
                except ValueError:
                    continue
                if len(values) >= MAX_SOURCE_VALUES:
                    return sorted(values)
    return sorted(values)


def _walk_source_files(path: str) -> "list[str]":
    out = []
    if not os.path.isdir(path):
        return out
    for dirpath, _dirs, names in os.walk(path):
        for name in names:
            if os.path.splitext(name)[1].lower() in SOURCE_EXTS:
                out.append(os.path.join(dirpath, name))
    return out


def matches_source(value: float, values: "list[float]", tol: float, is_percent: bool) -> bool:
    """True if any source value is within relative tolerance of the cited number."""
    candidates = [value]
    if is_percent:
        candidates.append(value / 100.0)
    elif abs(value) <= 1.0:
        candidates.append(value * 100.0)
    for cand in candidates:
        pos = bisect.bisect_left(values, cand)
        for i in (pos - 1, pos, pos + 1):
            if 0 <= i < len(values):
                v = values[i]
                if abs(v - cand) <= max(1e-9, tol * max(abs(v), abs(cand))):
                    return True
    return False


def cited_numbers(text: str, check_integers: bool) -> "list[tuple[int, str, float, bool]]":
    """Measurement-like cited numbers as (line, raw, value, is_percent).

    Skips cross-reference/ordinal context, years, and (unless check_integers) bare integers.
    """
    # [M3] Line numbers by BISECT over precomputed newline offsets. This was
    # `text.count("\n", 0, start)` per match - O(matches x filesize), and MAX_FILE_BYTES
    # guarded only SOURCE files, never the report. Measured: 219 KB = 0.43s, 875 KB = 25.2s,
    # 3.5 MB = killed at 120s. A killed hook is treated as rc 0, so the check was
    # simultaneously blocking the turn and not being performed. Same measurement after the
    # bisect: 3.5 MB = 1.76s.
    newlines = []
    pos = text.find("\n")
    while pos != -1:
        newlines.append(pos)
        pos = text.find("\n", pos + 1)

    out = []
    for m in _NUMBER_RE.finditer(text):
        frac, exp = m.group("frac") or "", m.group("exp") or ""
        try:
            value = float("%s%s%s%s" % (m.group("sign") or "", m.group("int").replace(",", ""), frac, exp))
        except ValueError:
            continue
        start, end = m.start(), m.end()
        unit_m = _UNIT_RE.match(text, end)
        unit = unit_m.group(1) if unit_m else None
        raw = text[start:(unit_m.end() if unit_m else end)]
        is_percent = raw.rstrip().endswith("%") or unit == "%"
        has_decimal = bool(frac or exp)
        prefix = text[max(0, start - 24):start]
        if prefix[-24:].rstrip().endswith(("[", "#")) or _REF_PREFIX_RE.search(prefix[-24:]):
            continue  # cross-reference / ordinal
        if not has_decimal and unit is None and not is_percent:
            if not check_integers or (1900 <= value <= 2099):  # bare int / year
                continue
        out.append((bisect.bisect_right(newlines, start - 1) + 1, raw, value, is_percent))
    return out


# --------------------------------------------------------------------------- #
# Firing
# --------------------------------------------------------------------------- #

def _tool_file(payload: dict) -> str:
    ti = payload.get("tool_input")
    return (ti.get("file_path") if isinstance(ti, dict) else "") or ""


def is_report_file(path: str, globs: "list[str]") -> bool:
    if os.path.splitext(path)[1].lower() not in TEXT_EXTS:
        return False
    base = os.path.basename(path).lower()
    return any(fnmatch.fnmatch(base, g.lower()) for g in (globs or DEFAULT_REPORT_GLOBS))


def build_message(name: str, sources: "list[str]", findings: "list[str]") -> str:
    lines = ["[numbers-match] %d cited number(s) in %s have no match in the source data (%s):"
             % (len(findings), name, ", ".join(sources))]
    lines.extend("- " + f for f in findings[:MAX_BULLETS])
    hidden = len(findings) - MAX_BULLETS
    if hidden > 0:
        # Say what was truncated. The count above is now the REAL total, and the marker
        # suppresses this hook for the rest of the session, so an unannounced truncation
        # means those findings are never mentioned again.
        lines.append("  (+%d more not shown)" % hidden)
    lines.append("Verify each against the source-of-truth data (recompute/re-export) or correct the "
                 "prose. Numbers that are derived, rounded beyond tolerance, or definitional are fine "
                 "to keep - this is a mechanical check, not a judge.")
    return "\n".join(lines) + "\n"


def marker_path(state_dir: str, session_id, report_path: str = "") -> str:
    """Once-per-(session, report) marker. Keying by report path too means firing on report A
    does not suppress a fabricated number later written to report B in the same session."""
    sid = (str(session_id) if session_id else "nosession")[:SESSION_ID_CHARS]
    tag = "all"
    if report_path:
        tag = hashlib.sha1(os.path.abspath(report_path).encode("utf-8", "replace")).hexdigest()[:10]
    return os.path.join(state_dir, "%s-%s-%s.done" % (HOOK_NAME, sid, tag))


def _cached_index(sources: "list[str]", root: str, state_dir: str,
                  exclude=()) -> "list[float]":
    """index_sources with a small on-disk cache keyed by source paths + mtimes (fail-silent).

    A clean report re-runs the hook on every edit; without a cache each edit re-reads and
    re-parses the whole source tree. The cache is invalidated automatically when any source
    file's mtime changes, and stale cache files are pruned so state_dir does not grow.
    """
    _skip = {os.path.normcase(os.path.abspath(p)) for p in exclude}
    try:
        # The exclusion is folded into the cache KEY: two reports in the same source tree
        # exclude different files, so they must not share a cached index.
        parts = ["exclude:" + "|".join(sorted(_skip))]
        for entry in sources:
            p = entry if os.path.isabs(entry) else os.path.join(root, entry)
            for f in ([p] if os.path.isfile(p) else _walk_source_files(p)):
                if os.path.normcase(os.path.abspath(f)) in _skip:
                    continue
                try:
                    st = os.stat(f)
                    # nanosecond mtime + size: a sub-second content change (same whole
                    # second) still invalidates the cache, closing a false-negative window.
                    parts.append("%s:%d:%d" % (f, st.st_mtime_ns, st.st_size))
                except OSError:
                    pass
        key = hashlib.sha1("|".join(sorted(parts)).encode("utf-8", "replace")).hexdigest()[:16]
        cache = os.path.join(state_dir, "%s-index-%s.json" % (HOOK_NAME, key))
        try:
            with open(cache, encoding="utf-8") as fh:
                cached = json.load(fh)
            if isinstance(cached, list):
                return [float(v) for v in cached]
        except (OSError, ValueError):
            pass
        values = index_sources(sources, root, exclude)
        try:
            os.makedirs(state_dir, exist_ok=True)
            for old in glob.glob(os.path.join(state_dir, "%s-index-*.json" % HOOK_NAME)):
                if os.path.abspath(old) != os.path.abspath(cache):
                    try:
                        os.remove(old)
                    except OSError:
                        pass
            with open(cache, "w", encoding="utf-8") as fh:
                json.dump(values, fh)
        except OSError:
            pass
        return values
    except Exception:
        # LOW-1: `exclude` was dropped on this fallback, re-opening H2 (a report
        # validating against itself) whenever the cache path raised.
        return index_sources(sources, root, exclude)


def run(payload: dict, state_dir: str) -> "tuple[int, str]":
    """Core decision, testable in isolation: (exit_code, stderr_text)."""
    path = _tool_file(payload)
    if not path:
        return 0, ""
    found = find_config(path, payload.get("cwd") or "")
    if not found:
        return 0, ""
    config_path, root = found
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            cfg = parse_config(fh.read())
    except OSError:
        return 0, ""
    if not cfg["sources"] or not is_report_file(path, cfg["reports"]):
        return 0, ""
    marker = marker_path(state_dir, payload.get("session_id") or "nosession", path)
    if os.path.exists(marker):
        return 0, ""
    try:
        # [M3] MAX_FILE_BYTES guarded only SOURCE files; the report itself was read unbounded.
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return 0, ("[numbers-match] %s is larger than %d bytes; skipped. NOTHING was "
                       "verified in it.\n" % (os.path.basename(path), MAX_FILE_BYTES))
        with open(path, encoding="utf-8", errors="replace") as fh:
            report_text = fh.read()
    except OSError:
        return 0, ""
    # Exclude the report under check AND every other file the config calls a report: a
    # report is never evidence for itself, and a poisoned index is shared by all of them.
    excluded = [path]
    for entry in cfg["sources"]:
        base = entry if os.path.isabs(entry) else os.path.join(root, entry)
        for cand in ([base] if os.path.isfile(base) else _walk_source_files(base)):
            if is_report_file(cand, cfg["reports"]):
                excluded.append(cand)
    values = _cached_index(cfg["sources"], root, state_dir, excluded)
    if not values:
        # [M1] A config that RESOLVES TO NOTHING is a broken config, not an opt-out. A typo'd
        # `sources = reslts` produced zero values, hit this branch, and returned the same
        # clean-pass sentinel as a fully-verified report - while the empty index was cached
        # under the SHA-1 of the empty string, so every later edit re-read it. The project
        # believed it had a numeric tripwire that was checking nothing. `find_config`
        # succeeding is proof the project OPTED IN, so say so rather than pass silently.
        dead = [e for e in cfg["sources"]
                if not os.path.exists(e if os.path.isabs(e) else os.path.join(root, e))]
        return 0, ("[numbers-match] %s lists source path(s) that resolve to nothing: %s. "
                   "NOTHING was verified in %s.\n"
                   % (os.path.relpath(config_path, root), ", ".join(dead or cfg["sources"]),
                      os.path.basename(path)))
    # [M2] Collect ALL findings, truncate only the DISPLAY. The loop used to break at
    # MAX_BULLETS and then format len(findings) into "N cited number(s) ... have no match", so
    # a report with 40 unmatched numbers announced "12" with no truncation notice - and the
    # per-(session, report) marker then suppressed the hook for the rest of the session, so
    # the other 28 were never mentioned again. memory_hygiene_guard already does this right.
    findings = []
    for line, raw, value, is_percent in cited_numbers(report_text, cfg["check_integers"]):
        if not matches_source(value, values, cfg["tol"], is_percent):
            snippet = _line_snippet(report_text, line)
            findings.append("%s:%d: %s   (%s)" % (os.path.basename(path), line, raw, snippet))
            if len(findings) >= MAX_FINDINGS_TRACKED:
                break                      # hard cap so a pathological report cannot balloon
    if not findings:
        return 0, ""
    os.makedirs(state_dir, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write("fired %s\n" % time.strftime("%Y-%m-%dT%H:%M:%S"))
    return 2, build_message(os.path.basename(path), cfg["sources"], findings)


def _line_snippet(text: str, lineno: int) -> str:
    lines = text.splitlines()
    if 1 <= lineno <= len(lines):
        return " ".join(lines[lineno - 1].split())[:SNIPPET_LEN]
    return ""


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
        # [HIGH-2] Emit the message whatever the code. run() deliberately returns
        # (0, message) twice - the M1 "sources resolve to nothing, NOTHING was verified"
        # warning and the oversize-report skip - and gating emission on code==2 made both
        # inert in production while their tests, which call run() directly, stayed green.
        # The M1 fix shipped, was mutation-pinned, and never reached a single user.
        if message:
            sys.stderr.write(message)
        return code
    except Exception:  # a broken hook must never block the user
        return 0


# --------------------------------------------------------------------------- #
# Self-test (pure fixtures + tempfile pipeline; never touches the real state dir)
# --------------------------------------------------------------------------- #

def _selftest_units() -> "list[str]":
    fails = []
    vals = sorted({94.7651206754795, 8.65422622962963, 0.947})
    # rounding absorbed within tolerance
    if not matches_source(94.8, vals, 0.01, is_percent=True):
        fails.append("94.8% should match 94.7651 within 1%")
    if not matches_source(8.65, vals, 0.01, is_percent=False):
        fails.append("8.65 should match 8.6542 within 1%")
    if matches_source(91.2, vals, 0.01, is_percent=True):
        fails.append("91.2 should NOT match")
    # extraction gating
    cites = cited_numbers("Overshoot 94.8% at t=2.85 s; see Figure 3 and Table 2 in 2021.", False)
    raws = [c[1] for c in cites]
    if "94.8%" not in raws or "2.85 s" not in raws:
        fails.append("measurement numbers missing: %r" % raws)
    if "3" in raws or "2" in raws:
        fails.append("figure/table refs not skipped: %r" % raws)
    if any(c[2] == 2021 for c in cites):
        fails.append("year 2021 not skipped")
    if any(c[1] == "2" for c in cited_numbers("There are 2 modes.", False)):
        fails.append("bare integer not skipped by default")
    if not any(c[2] == 5 for c in cited_numbers("There are 5 modes.", True)):
        fails.append("check_integers=true should include bare integer 5")
    # config parse
    cfg = parse_config("# hi\nsources = results, data\ntol=0.02\ncheck_integers = true\n")
    if cfg["sources"] != ["results", "data"] or cfg["tol"] != 0.02 or not cfg["check_integers"]:
        fails.append("config parse wrong: %r" % cfg)
    return fails


def _selftest_pipeline() -> "list[str]":
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as state:
        os.makedirs(os.path.join(proj, ".claude"))
        os.makedirs(os.path.join(proj, "results"))
        with open(os.path.join(proj, "results", "sweep.csv"), "w", encoding="utf-8") as f:
            f.write("metric,value\novershoot,94.7651\nsettle,8.6542\n")
        with open(os.path.join(proj, ".claude", CONFIG_NAME), "w", encoding="utf-8") as f:
            f.write("sources = results\nreports = *REPORT*.md\n")
        report = os.path.join(proj, "REPORT.md")
        with open(report, "w", encoding="utf-8") as f:
            f.write("Overshoot was 94.8% and settling time 8.65 s.\n"
                    "But the peak stress was 512.4 MPa, the worst case.\n")
        payload = {"session_id": "nm-fire", "cwd": proj, "tool_input": {"file_path": report}}
        code, msg = run(payload, state)  # SHOULD FIRE on 512.4 only (94.8/8.65 match)
        if code != 2 or "512.4" not in msg or "[numbers-match]" not in msg:
            fails.append("should-fire wrong: code=%s msg=%r" % (code, msg))
        if "94.8" in msg or "8.65" in msg:
            fails.append("matched numbers wrongly flagged: %r" % msg)
        code2, msg2 = run(payload, state)  # same report, same session -> once per report
        if (code2, msg2) != (0, ""):
            fails.append("second fire same report/session: %s %r" % (code2, msg2))
        # a DIFFERENT report in the same session must still be checked (marker is per-path)
        report_b = os.path.join(proj, "SECOND_REPORT.md")
        with open(report_b, "w", encoding="utf-8") as f:
            f.write("Another figure: peak 777.7 MPa, unsourced.\n")
        payload_b = {"session_id": "nm-fire", "cwd": proj, "tool_input": {"file_path": report_b}}
        code_b, msg_b = run(payload_b, state)
        if code_b != 2 or "777.7" not in msg_b:
            fails.append("second distinct report should still be checked: %s %r" % (code_b, msg_b))
    # no config -> silent (opt-in)
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as state:
        report = os.path.join(proj, "REPORT.md")
        with open(report, "w", encoding="utf-8") as f:
            f.write("Value 999.9 units.\n")
        code, msg = run({"session_id": "s", "cwd": proj, "tool_input": {"file_path": report}}, state)
        if (code, msg) != (0, ""):
            fails.append("no-config should be silent: %s %r" % (code, msg))
    # non-report filename -> ignored even with config
    with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as state:
        os.makedirs(os.path.join(proj, ".claude"))
        os.makedirs(os.path.join(proj, "results"))
        with open(os.path.join(proj, "results", "d.csv"), "w", encoding="utf-8") as f:
            f.write("1.0\n")
        with open(os.path.join(proj, ".claude", CONFIG_NAME), "w", encoding="utf-8") as f:
            f.write("sources = results\n")
        notes = os.path.join(proj, "notes.md")
        with open(notes, "w", encoding="utf-8") as f:
            f.write("Random 42.42 value.\n")
        code, msg = run({"session_id": "s2", "cwd": proj, "tool_input": {"file_path": notes}}, state)
        if (code, msg) != (0, ""):
            fails.append("non-report file scanned: %s %r" % (code, msg))
        if os.listdir(state):
            fails.append("marker written on non-firing run")
    return fails


def _selftest_item45() -> list:
    """H1/H2/H3 from the 2026-07-30 review of the never-reviewed hooks."""
    import tempfile
    fails = []

    # H1: _REF_PREFIX_RE had no LEFT word boundary, so it matched the tail of any word and
    # swallowed the number after it. 35 of 38 common technical words hid their number, which
    # means a report of fabricated figures extracted nothing and passed clean.
    for phrase, want in (("drop 0.85 kPa", True), ("up 12.5%", True), ("each 3.75 mm", True),
                         ("group 7.25 kg", True), ("gap 0.25 mm", True), ("rev 1.75 s", True),
                         ("slope 0.42 rad", True), ("stop 3.5 s", True),
                         # genuine cross-references must STILL be skipped - `step` is one of
                         # them ("Step 2"), so a number right after it is correctly ignored.
                         ("see Figure 3", False), ("Table 2", False), ("eq. 4", False),
                         ("p. 7", False), ("Section 5", False), ("v 2", False),
                         ("step 2", False)):
        got = bool(cited_numbers(phrase, False))
        if got != want:
            fails.append("H1 ref-prefix: %r should%s yield a cited number, got %s"
                         % (phrase, "" if want else " NOT", got))

    # H3: a TRAILING comment must not become part of the value. The module's own documented
    # config is the fixture, verbatim - it was unparseable by its own parser.
    cfg = parse_config("sources = results, data            # dirs/files (relative)\n"
                       "reports = *REPORT*.md              # optional basename globs\n"
                       "tol = 0.05                         # optional relative tolerance\n"
                       "check_integers = true              # optional; default off\n")
    if cfg["sources"] != ["results", "data"]:
        fails.append("H3 config: trailing comment leaked into sources: %r" % (cfg["sources"],))
    if cfg["reports"] != ["*REPORT*.md"]:
        fails.append("H3 config: trailing comment leaked into reports: %r" % (cfg["reports"],))
    if abs(cfg["tol"] - 0.05) > 1e-9:
        fails.append("H3 config: tol silently reverted to the default: %r" % (cfg["tol"],))
    if cfg["check_integers"] is not True:
        fails.append("H3 config: check_integers=true was not honoured")

    # H2: a report living INSIDE a configured source dir must not be its own evidence.
    # SOURCE_EXTS includes .md and PostToolUse runs after the write, so it indexed itself.
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "proj")
        results = os.path.join(root, "results")
        os.makedirs(results, exist_ok=True)
        os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
        with open(os.path.join(root, ".claude", CONFIG_NAME), "w", encoding="utf-8") as fh:
            fh.write("sources = results\nreports = *report*.md\n")
        with open(os.path.join(results, "sweep.csv"), "w", encoding="utf-8") as fh:
            fh.write("run,val\n1,10.0\n2,20.0\n")
        report = os.path.join(results, "RESULTS_report.md")
        with open(report, "w", encoding="utf-8") as fh:
            fh.write("The measured stress was 512.4 MPa across the sweep.\n")
        state = os.path.join(td, "state")
        code, msg = run({"tool_input": {"file_path": report}, "cwd": root,
                         "session_id": "h2"}, state)
        if code != 2 or "512.4" not in msg:
            fails.append("H2: a report inside a source dir validated against ITSELF - "
                         "fabricated 512.4 passed (code=%s msg=%r)" % (code, msg[:120]))
        # and a second report must not be exempted by the first one's presence in the tree
        report2 = os.path.join(results, "other_report.md")
        with open(report2, "w", encoding="utf-8") as fh:
            fh.write("A different fabricated value: 512.4 MPa again.\n")
        code2, msg2 = run({"tool_input": {"file_path": report2}, "cwd": root,
                           "session_id": "h2b"}, state)
        if code2 != 2 or "512.4" not in msg2:
            fails.append("H2: one fabricated report in the source tree exempted its value "
                         "for every OTHER report (code=%s msg=%r)" % (code2, msg2[:120]))
    return fails


def _selftest_mediums() -> list:
    """M1/M2/M3 from the 2026-07-30 review."""
    import tempfile
    fails = []

    # M3: line numbering was O(matches x filesize). 875 KB measured at 25.2s, 3.5 MB killed at
    # 120s - and a killed hook reads as rc 0, so the check both blocked the turn and did not
    # run. Bisect makes this linear. A generous bound: the point is orders of magnitude.
    big = "\n".join("row %d: value %d.5 mm and %d.25 kg" % (i, i, i) for i in range(20000))
    t0 = time.time()
    got = cited_numbers(big, False)
    elapsed = time.time() - t0
    # Bound MEASURED, not guessed: on this fixture (826 KB, 40k matches) the bisect runs in
    # 0.33s and count()-per-match in 9.61s - a 29x gap. 4s sits 12x above the linear time and
    # 2.4x below the quadratic one, so it still separates them on a CI box several times
    # slower. The first bound tried was 12s, which sat ABOVE the quadratic time and let the
    # mutation survive - a perf assertion is only worth as much as its measured margin.
    if elapsed > 4.0:
        fails.append("M3: cited_numbers took %.1fs on a %d KB report (linear is ~0.3s here) - "
                     "line numbering is quadratic again" % (elapsed, len(big) // 1024))
    if not got:
        fails.append("M3: extracted nothing from the large fixture")
    else:
        # correctness of the bisect, not just its speed: first and last line numbers
        if got[0][0] != 1:
            fails.append("M3: first match reported on line %d, expected 1" % got[0][0])
        expected_last = big.count("\n") + 1
        if got[-1][0] != expected_last:
            fails.append("M3: last match on line %d, expected %d"
                         % (got[-1][0], expected_last))
    # a number on a known line lands on that line
    probe = "alpha\nbeta\ngamma 4.5 mm\ndelta\n"
    hits = cited_numbers(probe, False)
    if not hits or hits[0][0] != 3:
        fails.append("M3: line number wrong after the bisect rewrite: %r" % (hits,))

    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, "proj")
        os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
        os.makedirs(os.path.join(root, "results"), exist_ok=True)
        with open(os.path.join(root, "results", "d.csv"), "w", encoding="utf-8") as fh:
            fh.write("v\n1.0\n")

        # M2: the reported COUNT must be the real total, and truncation must be announced.
        with open(os.path.join(root, ".claude", CONFIG_NAME), "w", encoding="utf-8") as fh:
            fh.write("sources = results\nreports = *report*.md\n")
        many = os.path.join(root, "many_report.md")
        with open(many, "w", encoding="utf-8") as fh:
            for i in range(40):
                fh.write("Measured %d.75 mm on run %d.\n" % (100 + i, i))
        code, msg = run({"tool_input": {"file_path": many}, "cwd": root,
                         "session_id": "m2"}, os.path.join(td, "s1"))
        if code != 2:
            fails.append("M2: 40 unmatched numbers did not fire (code=%s)" % code)
        else:
            head = msg.splitlines()[0]
            if "12 cited number" in head:
                fails.append("M2: reported the DISPLAY cap as the total: %r" % head)
            if "40 cited number" not in head:
                fails.append("M2: total is not the real count: %r" % head)
            if "more not shown" not in msg:
                fails.append("M2: truncated the list with no notice - the marker then "
                             "suppresses the hook for the rest of the session")

        # M1: sources that resolve to NOTHING is a broken config, not an opt-out.
        with open(os.path.join(root, ".claude", CONFIG_NAME), "w", encoding="utf-8") as fh:
            fh.write("sources = reslts\nreports = *report*.md\n")   # typo
        bad = os.path.join(root, "typo_report.md")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("The measured value was 999.9 MPa.\n")
        code, msg = run({"tool_input": {"file_path": bad}, "cwd": root,
                         "session_id": "m1"}, os.path.join(td, "s2"))
        if not msg or "resolve to nothing" not in msg:
            fails.append("M1: a config whose sources resolve to nothing passed SILENTLY, "
                         "identical to a verified report (code=%s msg=%r)" % (code, msg[:120]))
    return fails


def selftest() -> int:
    fails = (_selftest_units() + _selftest_pipeline() + _selftest_item45()
             + _selftest_mediums())
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
