#!/usr/bin/env python3
"""consistency-audit CLI - the mechanical half of the deliverable drift audit.

Given a deliverable (docx/pdf/tex/md/...) and one or more source-data dirs, it:
  1. normalises the deliverable to text (format-agnostic),
  2. extracts every cited number, figure reference, caption and embed,
  3. cross-checks each number against the source index with tolerance,
  4. emits CANDIDATE discrepancies grouped into the four drift classes.

It never asserts a finding is a real error - it ranks candidates and hands them
to Claude, who does the reasoning half (is the claim supported? is the reading
consistent across sections?). See ../SKILL.md.

Usage:
    python audit.py --deliverable report.md --sources results,data [--json out.json]
    python audit.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract  # noqa: E402
import sources as src  # noqa: E402

_CLAIM_RE = extract.re.compile(
    r"\b(highest|lowest|max(?:imum)?|min(?:imum)?|best|worst|fastest|slowest|"
    r"largest|smallest|greatest|most|least|optimal|reduced?|increased?|"
    r"decreased?|improv\w+|better|worse|outperform\w*|exceeds?|within|"
    r"less than|greater than|more than|negligible|significant\w*)\b",
    extract.re.IGNORECASE,
)


def _split_list(value: str):
    return [p.strip() for p in value.split(",") if p.strip()]


def analyse(deliverable: str, source_dirs, rel_tol: float, abs_tol: float):
    """Return a structured result dict of candidate discrepancies."""
    text = extract.deliverable_to_text(deliverable)
    name = os.path.basename(deliverable)
    numbers = extract.find_numbers(text)
    idx = src.index_sources(source_dirs)

    unmatched = []
    checked = skipped_ref = skipped_year = 0
    for cite in numbers:
        if cite.ref_context:
            skipped_ref += 1
            continue
        if cite.looks_like_year:
            skipped_year += 1
            continue
        checked += 1
        hit = src.match(cite.value, idx, rel_tol, abs_tol, cite.is_percent)
        if hit is None:
            near = src.nearest_value(cite.value, idx)
            unmatched.append({
                "line": cite.line, "cited": cite.raw, "value": cite.value,
                "context": cite.context,
                "nearest_source": near,
            })

    figures = _figure_findings(text)
    tables = _table_findings(text)
    claims = _claim_candidates(text, {u["value"] for u in unmatched})
    placeholders = [{"line": ln, "text": t} for ln, t in extract.find_placeholders(text)]

    return {
        "deliverable": name,
        "source_files": idx.files, "source_values": len(idx.values),
        "source_truncated": idx.truncated,
        "numbers_total": len(numbers), "numbers_checked": checked,
        "skipped_reference": skipped_ref, "skipped_year": skipped_year,
        "unmatched_numbers": unmatched,
        "orphan_figures": figures["orphans"],
        "dangling_figure_refs": figures["dangling"],
        "uncaptioned_embeds": figures["uncaptioned_embeds"],
        "placeholders": placeholders,
        "table_structures": tables["structures"],
        "dangling_table_refs": tables["dangling"],
        "tables_referenced_not_rendered": tables["missing"],
        "claim_candidates": claims,
        "tolerance": {"rel": rel_tol, "abs": abs_tol},
    }


def _figure_findings(text: str):
    captions = extract.find_figure_captions(text)
    refs = extract.find_figure_refs(text)
    ref_lines = {}
    for num, line in refs:
        ref_lines.setdefault(num, []).append(line)
    orphans = []
    for num, (cap_line, cap_text) in sorted(captions.items()):
        other = [ln for ln in ref_lines.get(num, []) if ln != cap_line]
        if not other:
            orphans.append({"figure": num, "line": cap_line, "caption": cap_text})
    dangling = []
    for num, lines in sorted(ref_lines.items()):
        if num not in captions:
            dangling.append({"figure": num, "lines": sorted(set(lines))})
    return {"orphans": orphans, "dangling": dangling, "uncaptioned_embeds": []}


def _table_findings(text: str):
    """Table cross-refs with no caption, and 'Table N' cited/captioned but no table rendered.

    The complement of the figure checks, plus the placeholder-table case: a report can
    reference or caption 'Table N' while the actual table body was never filled in.
    """
    structures = extract.count_table_structures(text)
    captions = extract.find_table_captions(text)
    refs = extract.find_table_refs(text)
    ref_lines = {}
    for num, line in refs:
        ref_lines.setdefault(num, []).append(line)
    dangling = []
    for num, lines in sorted(ref_lines.items()):
        cap_line = captions[num][0] if num in captions else None
        other = [ln for ln in lines if ln != cap_line]
        if num not in captions and other:
            dangling.append({"table": num, "lines": sorted(set(other))})
    # Tables are referenced or captioned, but the deliverable renders no table at all
    # -> the bodies are missing/placeholder. (The prose promises a table; none exists.)
    missing = None
    if structures == 0 and (captions or ref_lines):
        promised = sorted(set(list(captions) + list(ref_lines)))
        missing = {"promised": promised,
                   "captions": sorted(captions),
                   "referenced": sorted(ref_lines)}
    return {"structures": structures, "dangling": dangling, "missing": missing}


def _claim_candidates(text: str, unmatched_values, cap: int = 15):
    """Comparative/superlative sentences whose number is unmatched or absent."""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if len(out) >= cap:
            break
        if not _CLAIM_RE.search(line):
            continue
        nums = extract.find_numbers(line)
        data_nums = [n for n in nums if not n.ref_context and not n.looks_like_year]
        if not data_nums:
            out.append({"line": lineno, "text": line.strip()[:200], "why": "no supporting number"})
        elif any(n.value in unmatched_values for n in data_nums):
            out.append({"line": lineno, "text": line.strip()[:200], "why": "number unmatched in source"})
    return out


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def render_text(r: dict) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("CONSISTENCY AUDIT (mechanical pass) - %s" % r["deliverable"])
    lines.append("=" * 72)
    lines.append(
        "Source index: %d value(s) from %d file(s)%s | tolerance rel=%.3g abs=%.3g"
        % (r["source_values"], r["source_files"],
           " [TRUNCATED]" if r["source_truncated"] else "",
           r["tolerance"]["rel"], r["tolerance"]["abs"]))
    lines.append(
        "Numbers: %d found, %d checked (%d reference-context, %d year skipped)"
        % (r["numbers_total"], r["numbers_checked"],
           r["skipped_reference"], r["skipped_year"]))
    lines.append("")

    lines.append("[A] NUMBERS WITH NO SOURCE MATCH  (possible stale/fabricated)  -> %d"
                 % len(r["unmatched_numbers"]))
    for u in r["unmatched_numbers"]:
        near = "none" if u["nearest_source"] is None else ("%g" % u["nearest_source"])
        lines.append("  L%-5s %-12s nearest source: %s" % (u["line"], u["cited"], near))
        lines.append("        ...%s..." % u["context"])
    if not r["unmatched_numbers"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("[B] FIGURES EMBEDDED/CAPTIONED BUT NEVER REFERENCED  -> %d"
                 % len(r["orphan_figures"]))
    for o in r["orphan_figures"]:
        lines.append("  Figure %s (caption L%s): %s" % (o["figure"], o["line"], o["caption"][:80]))
    if not r["orphan_figures"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("[C] FIGURE CROSS-REFS WITH NO MATCHING CAPTION  -> %d"
                 % len(r["dangling_figure_refs"]))
    for d in r["dangling_figure_refs"]:
        lines.append("  'Figure %s' referenced at L%s but no such caption"
                     % (d["figure"], ",".join(map(str, d["lines"]))))
    if not r["dangling_figure_refs"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("[D] CLAIM SENTENCES TO VERIFY BY REASONING (Claude's half)  -> %d"
                 % len(r["claim_candidates"]))
    for c in r["claim_candidates"]:
        lines.append("  L%-5s (%s) %s" % (c["line"], c["why"], c["text"]))
    if not r["claim_candidates"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("[E] UNFILLED PLACEHOLDERS LEFT IN THE DELIVERABLE  -> %d"
                 % len(r["placeholders"]))
    for p in r["placeholders"]:
        lines.append("  L%-5s %s" % (p["line"], p["text"]))
    if not r["placeholders"]:
        lines.append("  (none)")
    lines.append("")

    lines.append("[F] TABLES REFERENCED/CAPTIONED BUT NOT RENDERED  (%d table(s) found)"
                 % r["table_structures"])
    miss = r["tables_referenced_not_rendered"]
    if miss:
        lines.append("  Table(s) %s promised in prose but NO table is rendered in the "
                     "deliverable - likely placeholder/unfilled."
                     % ", ".join(miss["promised"]))
    for d in r["dangling_table_refs"]:
        lines.append("  'Table %s' referenced at L%s but no such caption"
                     % (d["table"], ",".join(map(str, d["lines"]))))
    if not miss and not r["dangling_table_refs"]:
        lines.append("  (none)")
    lines.append("")
    lines.append("NOTE: every item above is a CANDIDATE. A number may be legitimately "
                 "derived, rounded beyond tolerance, or definitional; a claim may hold. "
                 "Adjudicate each against the source and the surrounding argument.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Mechanical consistency-drift audit.")
    ap.add_argument("--deliverable", help="report/doc/slides file (docx/pdf/tex/md/...)")
    ap.add_argument("--sources", help="comma-separated source-data dirs or files")
    ap.add_argument("--rel-tol", type=float, default=0.01, help="relative tolerance (default 0.01)")
    ap.add_argument("--abs-tol", type=float, default=1e-9, help="absolute tolerance (default 1e-9)")
    ap.add_argument("--json", metavar="PATH", help="also write machine-readable JSON here")
    ap.add_argument("--selftest", action="store_true", help="run internal self-tests")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.deliverable or not args.sources:
        ap.error("--deliverable and --sources are required (or use --selftest)")

    try:
        result = analyse(args.deliverable, _split_list(args.sources),
                         args.rel_tol, args.abs_tol)
    except extract.ExtractError as exc:
        print("EXTRACTION FAILED: %s" % exc, file=sys.stderr)
        print("Provide a text/markdown export of the deliverable and re-run.", file=sys.stderr)
        return 3
    print(render_text(result))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print("\n(JSON written to %s)" % args.json)
    return 0


# --------------------------------------------------------------------------- #
# Self-test (pure fixtures, temp dirs; never touches real project data)
# --------------------------------------------------------------------------- #

def selftest() -> int:
    import tempfile
    fails = []

    # 1) number extraction + tagging
    nums = extract.find_numbers("Overshoot was 94.8% (see Figure 3) in 2021; settled in 8.65 s.")
    by_raw = {n.raw: n for n in nums}
    if "94.8%" not in by_raw or not by_raw["94.8%"].is_percent:
        fails.append("percent not tagged: %r" % list(by_raw))
    if "3" in by_raw and not by_raw["3"].ref_context:
        fails.append("Figure 3 not tagged ref_context")
    if not any(n.looks_like_year for n in nums):
        fails.append("year 2021 not tagged")

    # 2) tolerance matching absorbs rounding; unrelated number does not match
    idx = src.index_sources([_write_tmp_csv()])
    if src.match(94.8, idx, 0.01, 1e-9, is_percent=True) is None:
        fails.append("94.8%% should match source 94.7651 within 1%%")
    if src.match(91.2, idx, 0.01, 1e-9, is_percent=True) is not None:
        fails.append("91.2 should NOT match any source value")

    # 3) end-to-end analyse on a fixture deliverable
    with tempfile.TemporaryDirectory() as d:
        csv = os.path.join(d, "data.csv")
        with open(csv, "w", encoding="utf-8") as fh:
            fh.write("metric,value\novershoot,94.7651\nsettle,8.6542\n")
        rep = os.path.join(d, "report.md")
        with open(rep, "w", encoding="utf-8") as fh:
            fh.write("Overshoot was 94.8% and settling 8.65 s.\n"
                     "But the peak reached 55.5 units, the highest observed.\n"
                     "Figure 1: Step response.\n"
                     "As Figure 4 shows, it is stable.\n")
        r = analyse(rep, [csv], 0.01, 1e-9)
        if not any(abs(u["value"] - 55.5) < 1e-6 for u in r["unmatched_numbers"]):
            fails.append("55.5 should be flagged unmatched: %r" % r["unmatched_numbers"])
        if any(abs(u["value"] - 94.8) < 1e-6 for u in r["unmatched_numbers"]):
            fails.append("94.8 should have matched (rounding)")
        if not any(o["figure"] == "1" for o in r["orphan_figures"]):
            fails.append("Figure 1 should be orphan (captioned, never referenced)")
        if not any(dd["figure"] == "4" for dd in r["dangling_figure_refs"]):
            fails.append("Figure 4 should be a dangling ref (no caption)")
        if not r["claim_candidates"]:
            fails.append("'highest observed' claim should be a candidate")

    # 4) placeholders + table structure (the added mechanical checks)
    ph = [t for _, t in extract.find_placeholders(
        "Overshoot [TODO] and see Table 2 [insert value]. Cite [12] stays. [N/A] stays. "
        "[Table of contents](#toc) is a link.")]
    if "[TODO]" not in ph or not any("insert" in t.lower() for t in ph):
        fails.append("placeholders missed: %r" % ph)
    if any(t == "[12]" for t in ph) or any("N/A" in t for t in ph) or any("toc" in t.lower() for t in ph):
        fails.append("citation / N-A / md-link wrongly flagged: %r" % ph)
    if extract.find_figure_captions("Table 1: results\n"):
        fails.append("table caption leaked into figure captions (collision)")
    if extract.count_table_structures("| a | b |\n|---|---|\n| 1 | 2 |\n") != 1:
        fails.append("markdown table not counted")

    # 5) end-to-end: Table 3 promised but no table rendered (placeholder), Table 9 dangling
    with tempfile.TemporaryDirectory() as d:
        csv = os.path.join(d, "data.csv")
        with open(csv, "w", encoding="utf-8") as fh:
            fh.write("v\n1.0\n")
        rep = os.path.join(d, "report.md")
        with open(rep, "w", encoding="utf-8") as fh:
            fh.write("Results are summarised in Table 3.\n"
                     "Table 3: [TABLE TO BE INSERTED]\n"
                     "See also Table 9 for details.\n")
        r = analyse(rep, [csv], 0.01, 1e-9)
        if not r["placeholders"]:
            fails.append("placeholder table not flagged")
        if not r["tables_referenced_not_rendered"]:
            fails.append("Table 3 promised but not rendered should be flagged")
        if not any(dd["table"] == "9" for dd in r["dangling_table_refs"]):
            fails.append("Table 9 should be a dangling table ref")

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


def _write_tmp_csv():
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("Overshoot_pct,Settle_s\n94.7651206754795,8.65422622962963\n")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
