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

_HOOKS_DIR_SB = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR_SB not in sys.path:
    sys.path.insert(0, _HOOKS_DIR_SB)
import cap_shapes  # noqa: E402  the C1-NEW detector
import selftest_budget  # noqa: E402  ONE declaration of the per-hook selftest cap

# The exemption roster moved to cap_shapes with the detector, and its KEY changed from
# (module, constant) to (module, qualname, kind). That is not cosmetic: a constant-keyed
# roster cannot separate a sanctioned COLLECTION bound from a DISPLAY cap on the SAME
# constant in the same file, and the corpus carries three must-flag entries that are exactly
# that. Re-exported here because this is the name the audit docs cite.
BOUND_EXEMPTIONS = cap_shapes.BOUND_EXEMPTIONS


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


def slicing_offenders(hooks_dir: str) -> list:
    """Hooks that silently shorten a REPORTED collection without going through this module.

    [P14 B1, C1-NEW] The implementation lives in cap_shapes/cap_types and this is a delegate,
    kept at this name because it is the DECLARED entrypoint in tests/noregress_registry.py -
    renaming it would make no_regression measure the predecessor as detecting nothing and
    report a total loss that never happened.

    What changed, and it is the whole design: the predecessor classified the BOUND - a
    module-level `MAX_*` constant used as a slice upper or a break comparator. Python's
    grammar does not bound the ways to spell a bound, so that design failed OPEN on every
    unenumerated spelling (import, class attribute, dict value, walrus, lowercase parameter,
    bare integer) and was reverted at 2,101 lines. C1-NEW classifies the OPERATION instead,
    which IS grammar-closed.

    MEASURED against tests/cap_spelling_corpus.py: predecessor 38 of 103 with 1 false
    positive; this 100 of 103 with 0. The 3 misses are byte-identical corpus pairs carrying
    opposite verdicts, so 100 with zero false positives is the arithmetic ceiling, not a
    shortfall - see tools/score_corpus.py, which now detects and prints those pairs.
    """
    return cap_shapes.slicing_offenders(hooks_dir)


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

    # [assume a fifth] no hook may grow its own cap again, and no exemption may outlive the
    # site it was written for. Both go through cap_shapes.verdict(), which is the DECISION -
    # asserted branch by branch in cap_shapes' own selftest, because MR-a recorded a gate
    # that was fully disarmable while every test exercising its DETECTOR stayed green.
    here = os.path.dirname(os.path.abspath(__file__))
    ok, lines = cap_shapes.verdict(slicing_offenders(here),
                                   cap_shapes.exemption_problems(here))
    if not ok:
        fails.extend(lines)

    # the guard must be able to SEE an offender - a structural check that matches nothing is
    # indistinguishable from a clean sweep, which is the failure this whole module is about.
    # cap_shapes' selftest plants one fixture per shape; this pins the DELEGATION itself,
    # which is the only thing this file still owns.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "planted.py"), "w", encoding="utf-8") as f:
            f.write("MAX_BULLETS = 12\n\n\ndef m(xs):\n    return xs[:MAX_BULLETS]\n")
        with open(os.path.join(td, "planted2.py"), "w", encoding="utf-8") as f:
            f.write("MAX_ITEMS = 12\n\n\ndef m(xs):\n    out = []\n    for x in xs:\n"
                    "        if len(out) >= MAX_ITEMS:\n            break\n"
                    "        out.append(x)\n    return out\n")
        planted = slicing_offenders(td)
        if not any(o.startswith("planted:") for o in planted):
            fails.append("slicing_offenders cannot see a planted display cap - the guard "
                         "matches nothing and would report any repo as clean")
        if not any(o.startswith("planted2:") for o in planted):
            fails.append("slicing_offenders cannot see a planted collection cap")

    # [P14 D1] default share. Measured 2026-08-02: 0.20s, under 1% of the cap. This is the
    # hook the 36s regression happened in, which is why it is wired first.
    fails += selftest_budget.report(name="capped_report")
    for f_ in fails:
        print("SELFTEST FAIL:", f_)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
