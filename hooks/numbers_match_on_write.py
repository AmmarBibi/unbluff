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
_REF_PREFIX_RE = re.compile(
    r"(?:figure|fig|table|tbl|section|sect|sec|equation|eqn|eq|chapter|chap|ch|appendix|"
    r"app|reference|ref|step|stage|part|phase|question|q|item|version|v|no|number|num|"
    r"line|page|pg|p|slide|footnote|note|eq\.)\.?\s*$",
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

def index_sources(dirs: "list[str]", root: str) -> "list[float]":
    """Sorted unique numeric values across the configured source dirs/files."""
    values = set()
    for entry in dirs:
        path = entry if os.path.isabs(entry) else os.path.join(root, entry)
        files = [path] if os.path.isfile(path) else _walk_source_files(path)
        for fpath in files:
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
        out.append((text.count("\n", 0, start) + 1, raw, value, is_percent))
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


def _cached_index(sources: "list[str]", root: str, state_dir: str) -> "list[float]":
    """index_sources with a small on-disk cache keyed by source paths + mtimes (fail-silent).

    A clean report re-runs the hook on every edit; without a cache each edit re-reads and
    re-parses the whole source tree. The cache is invalidated automatically when any source
    file's mtime changes, and stale cache files are pruned so state_dir does not grow.
    """
    try:
        parts = []
        for entry in sources:
            p = entry if os.path.isabs(entry) else os.path.join(root, entry)
            for f in ([p] if os.path.isfile(p) else _walk_source_files(p)):
                try:
                    parts.append("%s:%d" % (f, int(os.path.getmtime(f))))
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
        values = index_sources(sources, root)
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
        return index_sources(sources, root)


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
        with open(path, encoding="utf-8", errors="replace") as fh:
            report_text = fh.read()
    except OSError:
        return 0, ""
    values = _cached_index(cfg["sources"], root, state_dir)
    if not values:
        return 0, ""
    findings = []
    for line, raw, value, is_percent in cited_numbers(report_text, cfg["check_integers"]):
        if not matches_source(value, values, cfg["tol"], is_percent):
            snippet = _line_snippet(report_text, line)
            findings.append("%s:%d: %s   (%s)" % (os.path.basename(path), line, raw, snippet))
        if len(findings) >= MAX_BULLETS:
            break
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
        if code == 2 and message:
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
        code2, msg2 = run(payload, state)  # once per session
        if (code2, msg2) != (0, ""):
            fails.append("second fire same session: %s %r" % (code2, msg2))
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


def selftest() -> int:
    fails = _selftest_units() + _selftest_pipeline()
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
