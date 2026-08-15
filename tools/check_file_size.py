#!/usr/bin/env python3
"""The 800-line rule, DERIVED. Enforced by nothing until 2026-08-14.

The project's coding rule is 200-400 lines typical, 800 maximum. It was enforced by nobody, so
it degraded monotonically while every individual addition looked justified - three files on
2026-08-12, five by the close, six on 08-13.

WHY THIS EXISTS RATHER THAN A LIST IN THE PLAN. The count itself was WRONG, and wrong in the
direction that flatters: the plan carried a hand-maintained list of the offenders, each session
added the file it had just pushed over, and nobody ever walked the tree. `tools/no_regression.py`
at 805 lines was over the limit and appeared in NO list - it was found on 2026-08-14 by deriving
the set for the first time, while writing a report that repeated the hand-list's number.
A DECLARED ROSTER standing in for a DERIVED one is this repo's most-repeated defect
(INSTALL-TAUTOLOGY, ENTRY-GUARD, ROSTER-DERIVE, _SH_SITES_REQUIRED, and now this).

WHY IT DOES NOT SIMPLY FAIL. Failing today would make the suite permanently red on seven
known files, and a gate that is red for weeks gets ignored or disabled - the same disease as a
guard that fires on correct code. So it is a RATCHET: the current offenders are recorded with
their sizes, and the gate fails when a file NEWLY crosses 800, or when a recorded offender
GROWS. Shrinking one below its recorded size tightens the ratchet automatically; getting it
under 800 removes it. The debt is visible, bounded, and can only go down.
"""

import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "docs", "audits", "file_size_baseline.json")
LIMIT = 800
SKIP_DIRS = (".git", "__pycache__", "node_modules", ".venv", "venv")


def line_count(path: str) -> int:
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def measure(root: str = REPO) -> dict:
    """{relpath: lines} for every tracked-looking .py file. DERIVED by walking, never listed."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out[rel] = line_count(full)
    return out


def load_baseline(path: str = BASELINE) -> dict:
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f).get("over_limit", {})
    except (OSError, ValueError):
        return {}


def verdict(sizes: dict, baseline: dict, limit: int = LIMIT):
    """(new_offenders, grown, shrunk, still_over) - the ratchet, as a pure function.

    Pure so the rule can be asserted without writing files, and so a mutation reaches the same
    code the probe does.
    """
    new_offenders, grown, shrunk, still_over = [], [], [], []
    for rel, n in sorted(sizes.items()):
        if n <= limit:
            continue
        if rel not in baseline:
            new_offenders.append((rel, n))
        else:
            was = baseline[rel]
            still_over.append((rel, n, was))
            if n > was:
                grown.append((rel, n, was))
            elif n < was:
                shrunk.append((rel, n, was))
    return new_offenders, grown, shrunk, still_over


def main() -> int:
    sizes = measure()
    baseline = load_baseline()
    new_offenders, grown, shrunk, still_over = verdict(sizes, baseline)

    print("file-size: %d .py file(s) walked, limit %d, %d recorded offender(s)"
          % (len(sizes), LIMIT, len(baseline)))
    for rel, n, was in sorted(still_over, key=lambda t: -t[1]):
        mark = "GREW" if n > was else ("shrunk" if n < was else "same")
        print("  %-46s %5d  (baseline %d, %s)" % (rel, n, was, mark))
    for rel, n in new_offenders:
        print("file-size FAIL: %s is %d lines, over the %d limit and in no baseline - a NEW "
              "offender. Split it, or record it deliberately." % (rel, n, LIMIT))
    for rel, n, was in grown:
        print("file-size FAIL: %s grew %d -> %d, and it was ALREADY over the limit. The "
              "ratchet only turns one way." % (rel, was, n))
    if shrunk:
        print("file-size: %d recorded offender(s) SHRANK - re-record to tighten the ratchet: %s"
              % (len(shrunk), ", ".join("%s %d->%d" % (r, w, n) for r, n, w in shrunk)))
    if new_offenders or grown:
        print("file-size: FAIL")
        return 1
    print("file-size: OK - no new offender, none grew")
    try:
        import gate_ledger
        gate_ledger.record("file_size", "PASS", walked=len(sizes),
                           over_limit=len(still_over), new=0, grown=0)
    except Exception:
        pass
    return 0


def selftest() -> int:
    fails = []
    # the RATCHET, both directions, through the real decision function
    base = {"a.py": 900}
    new, grown, shrunk, still = verdict({"a.py": 900, "b.py": 100}, base)
    if new or grown:
        fails.append("a recorded offender at its recorded size was reported as a regression")
    new, grown, _s, _o = verdict({"a.py": 901}, base)
    if not grown:
        fails.append("a recorded offender that GREW was accepted - the ratchet must only turn "
                     "one way, or the debt rises while the gate stays green")
    new, grown, _s, _o = verdict({"c.py": 801}, base)
    if not new:
        fails.append("a NEW file over the limit was accepted - which is exactly how "
                     "no_regression.py reached 805 lines while appearing in no list")
    if verdict({"c.py": 800}, base)[0]:
        fails.append("a file exactly AT the limit was flagged; the rule is 800 maximum")
    _n, _g, shrunk, _o = verdict({"a.py": 850}, base)
    if not shrunk:
        fails.append("a recorded offender that shrank was not reported, so the ratchet can "
                     "never be tightened")

    # measure() must DERIVE, and must actually find this repo's files
    sizes = measure()
    if len(sizes) < 20:
        fails.append("measure() walked only %d .py file(s) - it is not seeing the tree" %
                     len(sizes))
    if "tools/check_file_size.py" not in sizes:
        fails.append("measure() did not find this file; the walk is not rooted at the repo")
    if any("__pycache__" in k for k in sizes):
        fails.append("measure() descended into __pycache__ and would count generated files")

    print("-- file-size: ratchet asserted 5 ways; %d .py file(s) walked" % len(sizes))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
