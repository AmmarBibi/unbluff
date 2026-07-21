"""Index numeric values from a source-of-truth directory and match cited numbers.

The source data (CSVs, computed results, sweep outputs, JSON) is authoritative.
This module flattens every numeric token in that tree into a sorted, deduplicated
index with best-effort provenance, then answers "does this cited number match any
source value within tolerance?" - absorbing rounding via a relative tolerance and
handling percent<->fraction scale differences.

Mechanical only. It never decides a mismatch is a real error - it reports the
nearest source value and lets the audit (Claude) judge whether the gap is drift,
a derived quantity, or an acceptable rounding.
"""
from __future__ import annotations

import bisect
import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SOURCE_EXTS = {".csv", ".tsv", ".txt", ".dat", ".json", ".md", ".tab", ".out", ".log"}
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_VALUES = 500_000

_NUM_TOKEN_RE = re.compile(
    r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?"
)


@dataclass
class SourceIndex:
    values: List[float] = field(default_factory=list)   # sorted, unique
    provenance: Dict[float, str] = field(default_factory=dict)  # value -> "file:line"
    count: int = 0                                       # total tokens seen
    files: int = 0
    truncated: bool = False


def _iter_source_files(dirs: List[str]) -> List[str]:
    found: List[str] = []
    for root_dir in dirs:
        if os.path.isfile(root_dir):
            found.append(root_dir)
            continue
        for dirpath, _dirnames, filenames in os.walk(root_dir):
            for name in sorted(filenames):
                if os.path.splitext(name)[1].lower() in SOURCE_EXTS:
                    found.append(os.path.join(dirpath, name))
    return found


def _numbers_in_text(text: str):
    """Yield (value, line) for every numeric token in text."""
    line = 1
    pos = 0
    for match in _NUM_TOKEN_RE.finditer(text):
        line += text.count("\n", pos, match.start())
        pos = match.start()
        token = match.group(0).replace(",", "")
        try:
            yield float(token), line
        except ValueError:
            continue


def _numbers_in_json(obj, path="$"):
    """Yield (value, json-path) for every number in a parsed JSON structure."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield float(obj), path
    elif isinstance(obj, dict):
        for key, val in obj.items():
            yield from _numbers_in_json(val, "%s.%s" % (path, key))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            yield from _numbers_in_json(val, "%s[%d]" % (path, i))


def index_sources(dirs: List[str]) -> SourceIndex:
    """Build a numeric index over every source file under the given dirs/files."""
    idx = SourceIndex()
    unique: Dict[float, str] = {}
    for path in _iter_source_files(dirs):
        try:
            if os.path.getsize(path) > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        idx.files += 1
        rel = os.path.basename(path)
        try:
            if path.lower().endswith(".json"):
                with open(path, encoding="utf-8", errors="replace") as fh:
                    data = json.load(fh)
                pairs = _numbers_in_json(data)
            else:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    pairs = _numbers_in_text(fh.read())
            for value, loc in pairs:
                idx.count += 1
                if value not in unique:
                    unique[value] = "%s:%s" % (rel, loc)
                if len(unique) >= MAX_VALUES:
                    idx.truncated = True
                    break
        except (OSError, ValueError):
            continue
        if idx.truncated:
            break
    idx.provenance = unique
    idx.values = sorted(unique)
    return idx


def _nearest_within(values: List[float], query: float,
                    rel_tol: float, abs_tol: float) -> Optional[float]:
    """Return a source value within tolerance of query, or None."""
    if not values:
        return None
    pos = bisect.bisect_left(values, query)
    for cand in (pos - 1, pos, pos + 1):
        if 0 <= cand < len(values):
            v = values[cand]
            if abs(v - query) <= max(abs_tol, rel_tol * max(abs(v), abs(query))):
                return v
    return None


def match(number: float, idx: SourceIndex, rel_tol: float = 0.01,
          abs_tol: float = 1e-9, is_percent: bool = False
          ) -> Optional[Tuple[float, str]]:
    """Best source match for a cited number, or None.

    Tries the number as-is and, for percentages, its fraction form (45% ~ 0.45),
    so a prose percent matches a source stored either way.
    """
    candidates = [number]
    if is_percent:
        candidates.append(number / 100.0)
    elif abs(number) <= 1.0:
        candidates.append(number * 100.0)  # source may store the percent form
    for cand in candidates:
        found = _nearest_within(idx.values, cand, rel_tol, abs_tol)
        if found is not None:
            return found, idx.provenance.get(found, "?")
    return None


def nearest_value(number: float, idx: SourceIndex) -> Optional[float]:
    """The closest source value to `number` regardless of tolerance (for reporting)."""
    if not idx.values:
        return None
    pos = bisect.bisect_left(idx.values, number)
    best = None
    for cand in (pos - 1, pos, pos + 1):
        if 0 <= cand < len(idx.values):
            v = idx.values[cand]
            if best is None or abs(v - number) < abs(best - number):
                best = v
    return best
