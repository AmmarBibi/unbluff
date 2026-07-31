"""ONE way to cap a findings list, for every hook that prints one.

Five hooks independently grew a bullet cap, and the fix for "a cap must say what it dropped"
was applied to exactly one of them (numbers_match, finding M2). The other four kept truncating:
meta_audit sliced to 12 with no notice at all, plan_defer_guard stopped COLLECTING at 10 with
no notice, memory_hygiene printed a "+N more" computed AFTER a silent per-file cap so the
number itself under-reported. Same defect, four survivors - the instance was fixed and the
class was not.

The distinction that matters, and the reason `keep()` exists at all:

  * a DISPLAY cap is fine - nobody reads 400 bullets - as long as the message says how many
    were held back.
  * a COLLECTION cap that `break`s out of the scan destroys the total, so the truncation
    notice can only ever under-report. You cannot say what you dropped if you stopped counting.

So: scan everything, count everything, print a bounded amount, and always name the real total.

Run with --selftest to check the helpers AND to sweep hooks/ for a hook that has grown its own
cap again (the "assume a fifth" guard, structural rather than textual - see slicing_offenders).
"""

from __future__ import annotations

import ast
import glob
import os
import sys

# (module, constant) pairs that are resource BOUNDS, not display caps: they exist to stop a
# pathological input ballooning memory, and the code that owns them reports its own totals
# separately. A FLOOR that forces a decision - a new cap that is neither routed through this
# module nor listed here is a selftest failure, not a silent truncation.
BOUND_EXEMPTIONS = {
    ("numbers_match_on_write", "MAX_FINDINGS_TRACKED"),   # anti-balloon, total reported via M2
    ("numbers_match_on_write", "MAX_SOURCE_VALUES"),      # source-index size bound
    ("numbers_match_on_write", "MAX_FILE_BYTES"),         # per-file read bound
}


def keep(items, limit: int) -> tuple[list, int]:
    """Return (kept, total). Materialises EVERYTHING so `total` is the real count.

    Use this instead of `break`ing out of a scan at `limit`: the break is what makes a
    truncation notice lie, because the count it reports is the count of what survived.
    """
    all_items = list(items)
    return all_items[:limit], len(all_items)


def render(findings, limit: int, *, prefix: str = "- ", noun: str = "finding",
           total: int | None = None) -> list[str]:
    """Bullet lines for `findings`, capped at `limit`, ALWAYS with a truncation notice.

    `total` overrides len(findings) for callers that capped during collection and know the
    real figure. The notice names both numbers so "12" can never again be read as "all".
    """
    shown = list(findings)[:limit]
    real_total = len(findings) if total is None else total
    lines = [f"{prefix}{item}" for item in shown]
    hidden = real_total - len(shown)
    if hidden > 0:
        lines.append(f"{prefix}...and {hidden} more {noun}(s) not shown "
                     f"({real_total} total, showing {len(shown)})")
    return lines


def _max_names(tree: ast.AST) -> set:
    """Module-level constants whose name marks them as a cap."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.startswith("MAX_"):
                    out.add(t.id)
    return out


def slicing_offenders(hooks_dir: str) -> list:
    """Hooks that cap a list against a MAX_* constant without going through this module.

    STRUCTURAL (walks the AST), not a grep. A textual guard would have to contain the very
    pattern it forbids, and this repo has already recorded one guard that could not fail
    because the string it searched for appeared in the guard itself.

    Flags two shapes:
      * `something[:MAX_FOO]`        - a display cap, which needs render()
      * `if len(x) >= MAX_FOO: break` - a collection cap, which needs keep()
    """
    offenders = []
    for path in sorted(glob.glob(os.path.join(hooks_dir, "*.py"))):
        module = os.path.splitext(os.path.basename(path))[0]
        if module == "capped_report":
            continue                      # this module is the sanctioned home for the pattern
        try:
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError):
            continue
        caps = _max_names(tree)
        if not caps:
            continue
        for node in ast.walk(tree):
            # display cap:  xs[:MAX_FOO]
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                upper = node.slice.upper
                if (isinstance(upper, ast.Name) and upper.id in caps
                        and (module, upper.id) not in BOUND_EXEMPTIONS):
                    offenders.append(f"{module}: slices to {upper.id} directly - use "
                                     f"capped_report.render() so the message names what it hid")
            # collection cap:  if len(xs) >= MAX_FOO: break
            if isinstance(node, ast.If) and any(isinstance(b, ast.Break) for b in node.body):
                for cmp_node in ast.walk(node.test):
                    if not isinstance(cmp_node, ast.Compare):
                        continue
                    for comparator in cmp_node.comparators:
                        if (isinstance(comparator, ast.Name) and comparator.id in caps
                                and (module, comparator.id) not in BOUND_EXEMPTIONS):
                            offenders.append(
                                f"{module}: breaks out of a scan at {comparator.id}, so the "
                                f"real total is destroyed and any '+N more' under-reports - "
                                f"use capped_report.keep()")
    return sorted(set(offenders))


def selftest() -> int:
    fails = []

    kept, total = keep(range(25), 10)
    if kept != list(range(10)) or total != 25:
        fails.append(f"keep() wrong: kept={kept[:3]}... total={total}")
    kept, total = keep([], 10)
    if kept != [] or total != 0:
        fails.append("keep() wrong on an empty scan")
    kept, total = keep(range(3), 10)
    if total != 3 or kept != [0, 1, 2]:
        fails.append("keep() altered a below-cap scan")

    lines = render([f"f{i}" for i in range(20)], 5)
    if len(lines) != 6:
        fails.append(f"render() produced {len(lines)} lines, expected 5 + a notice")
    if "15 more" not in lines[-1] or "20 total" not in lines[-1]:
        fails.append(f"render() truncation notice does not name both numbers: {lines[-1]!r}")
    if render(["a", "b"], 5) != ["- a", "- b"]:
        fails.append("render() added a notice when nothing was hidden")
    # the M2 case: capped during collection, so the caller supplies the REAL total
    lines = render(["a", "b"], 5, total=40)
    if "38 more" not in lines[-1] or "40 total" not in lines[-1]:
        fails.append(f"render(total=) ignored the caller's real total: {lines[-1]!r}")

    # [assume a fifth] no hook may grow its own cap again
    offenders = slicing_offenders(os.path.dirname(os.path.abspath(__file__)))
    for o in offenders:
        fails.append(o)

    # the guard must be able to SEE an offender - a structural check that matches nothing is
    # indistinguishable from a clean sweep, which is the failure this whole module is about
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "planted.py"), "w", encoding="utf-8") as f:
            f.write("MAX_BULLETS = 3\n\n\ndef m(xs):\n    return xs[:MAX_BULLETS]\n")
        with open(os.path.join(td, "planted2.py"), "w", encoding="utf-8") as f:
            f.write("MAX_ITEMS = 3\n\n\ndef m(xs):\n    out = []\n    for x in xs:\n"
                    "        if len(out) >= MAX_ITEMS:\n            break\n"
                    "        out.append(x)\n    return out\n")
        planted = slicing_offenders(td)
        if not any(o.startswith("planted:") for o in planted):
            fails.append("slicing_offenders cannot see a planted display cap - the guard "
                         "matches nothing and would report any repo as clean")
        if not any(o.startswith("planted2:") for o in planted):
            fails.append("slicing_offenders cannot see a planted collection cap")

    for f_ in fails:
        print("SELFTEST FAIL:", f_)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
