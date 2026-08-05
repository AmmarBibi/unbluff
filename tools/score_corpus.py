#!/usr/bin/env python3
"""Score a cap-guard against tests/cap_spelling_corpus.py, printing the DENOMINATOR.

Plants each entry in a fresh temp dir at its declared rel_path, runs the guard's
slicing_offenders() over the hooks dir of that tree, and records flagged/not.

Nothing is written under the repo. Usage:
    python score_corpus.py <path-to-capped_report.py> [label]
"""
import importlib.util
import os
import sys
import tempfile

# DERIVED from this file's location, never hardcoded. It was an absolute Windows path, which was
# survivable only while this file was an exempt measurement tool nobody ran but its author. The
# moment it became AUX gate `corpus-scorer` (2026-08-06) it started running in CI on Linux and
# macOS, where that path does not exist and the corpus import dies at module load - `exit 1,
# ModuleNotFoundError: No module named 'cap_spelling_corpus'`, reproduced before this fix.
# Promoting a tool to a gate changes where it runs; anything machine-specific in it becomes a
# defect at that moment, not gradually.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tests"))
import cap_spelling_corpus as corpus  # noqa: E402


def load_guard(path):
    # capped_report imports selftest_budget from its own directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec = importlib.util.spec_from_file_location("guard_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["guard_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def run_entry(guard, rel_path, source, td):
    full = os.path.join(td, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(source)
    hooks_dir = os.path.join(td, os.path.dirname(rel_path).replace("/", os.sep))
    try:
        return bool(guard.slicing_offenders(hooks_dir))
    except Exception as e:                       # a guard that CRASHES is not a guard that passed
        return ("CRASH", type(e).__name__)


def split_corpus(entries=None, extra=None):
    """(positives, negatives) with NO entry counted twice.

    [P14 B1] This used to add `corpus.NEGATIVE_CONTROLS` to the negatives already filtered out
    of `corpus.ENTRIES`. They are not "extra" - `MUST_FLAG + NEGATIVE_CONTROLS == ENTRIES`, so
    every negative control was scored TWICE. The tool whose docstring is "printing the
    DENOMINATOR" printed `96 positives + 58 negatives = 154 corpus entries` for a corpus of 125,
    inflating it by 23% and doubling every false-positive count it reported.

    Nothing caught it because measurement tools are exempted from the gates (`NOT_A_GATE`) on the
    grounds that they have no pass/fail opinion - but "did I count the corpus correctly" is a
    pass/fail question that has nothing to do with the guard being scored. Hence the selftest
    below, and hence this being a gate now.

    De-duplicated by IDENTITY (the entry name), not by object, so a genuinely new control added
    only to NEGATIVE_CONTROLS is still picked up rather than silently dropped.
    """
    entries = list(corpus.ENTRIES if entries is None else entries)
    extra = list((getattr(corpus, "NEGATIVE_CONTROLS", ()) or ()) if extra is None else extra)
    pos = [e for e in entries if e[2]]
    neg, seen = [], set()
    for e in [x for x in entries if not x[2]] + [x for x in extra
                                                 if isinstance(x, tuple) and len(x) == 4]:
        if e[0] in seen:
            continue
        seen.add(e[0])
        neg.append(e)
    return pos, neg


def contradictions(entries=None):
    """Groups of entries that are the SAME INPUT with OPPOSITE verdicts.

    [P14 B1, 2026-08-06] `run_entry` plants ONE entry in a fresh temp dir and calls
    slicing_offenders(dirname). So (rel_path, source) IS the complete input a guard sees.
    Two entries sharing it and disagreeing on must_flag ask a deterministic guard the same
    question twice and require different answers - no guard can satisfy both, ever.

    MEASURED when this was written: THREE such pairs, so CAUGHT 100 of 103 at zero false
    positives is the arithmetic CEILING and not a shortfall. Before this existed the tool
    printed 103 as though it were reachable, and a reader comparing 100 against it would
    conclude the guard had a gap it does not have.

    This is the same class as the double-counting defect fixed above and as SC1: a
    measurement tool was exempted from the gates for having "no pass/fail opinion", while
    quietly reporting a denominator nobody could trust. Whether a grader's own questions are
    answerable is not an opinion.
    """
    entries = list(corpus.ENTRIES if entries is None else entries)
    groups = {}
    for e in entries:
        groups.setdefault((e[1], e[3]), []).append((e[0], e[2]))
    out = []
    for (rel, src), members in groups.items():
        if len({mf for _n, mf in members}) > 1:
            out.append((rel, src, sorted(members)))
    return sorted(out, key=lambda g: sorted(n for n, _ in g[2]))


def ceiling(pos, neg, groups):
    """(max CAUGHT at zero false positives, min FALSE-POS at full CAUGHT)."""
    blocked_pos = sum(1 for _r, _s, ms in groups for _n, mf in ms if mf)
    blocked_neg = sum(1 for _r, _s, ms in groups for _n, mf in ms if not mf)
    return len(pos) - blocked_pos, blocked_neg


def selftest():
    """The arithmetic this tool exists to report. A scorer that miscounts the corpus makes every
    number derived from it wrong in the same direction, silently."""
    fails = []
    pos, neg = split_corpus()
    total = len(corpus.ENTRIES)
    if len(pos) + len(neg) != total:
        fails.append("split_corpus yields %d + %d = %d, but the corpus has %d entries. A scorer "
                     "that cannot count its own corpus reports a denominator nobody can trust"
                     % (len(pos), len(neg), len(pos) + len(neg), total))
    names = [e[0] for e in pos] + [e[0] for e in neg]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        fails.append("%d entr(ies) scored TWICE: %r - this is the exact defect that reported "
                     "154 entries for a 125-entry corpus" % (len(dupes), dupes[:6]))

    # PLANTED: an overlapping "extra" list must not double-count, and a genuinely new control in
    # it must still be picked up. Both directions, because fixing one by dropping `extra`
    # entirely would pass the first check while silently losing controls.
    ents = [("p1", "hooks/f.py", True, ""), ("n1", "hooks/f.py", False, "")]
    _p, n = split_corpus(ents, [("n1", "hooks/f.py", False, ""), ("n2", "hooks/f.py", False, "")])
    got = sorted(e[0] for e in n)
    if got != ["n1", "n2"]:
        fails.append("overlapping NEGATIVE_CONTROLS handling is wrong: got %r, expected "
                     "['n1','n2'] - n1 must appear once, n2 must not be dropped" % (got,))

    # REPO must be DERIVED, not a literal. Asserted structurally rather than by grepping this
    # file for a path pattern - a guard that searches for a literal it contains is a defect this
    # repo has already recorded once. A hardcoded path that happens to be correct on the author's
    # machine passes every local check and only fails in CI, on the other two platforms.
    # PLANTED, both directions. A contradiction detector that finds nothing is
    # indistinguishable from a consistent corpus, and that is exactly how the real three
    # pairs sat unnoticed while the tool printed an unreachable denominator.
    same = ("hooks/f.py", "x = 1\n")
    got = contradictions([("a", same[0], True, same[1]), ("b", same[0], False, same[1])])
    if len(got) != 1 or [n for n, _ in got[0][2]] != ["a", "b"]:
        fails.append("a byte-identical pair with opposite verdicts was NOT reported: %r"
                     % (got,))
    quiet = contradictions([("a", same[0], True, same[1]),
                            ("b", "hooks/g.py", False, same[1]),
                            ("c", same[0], True, same[1])])
    if quiet:
        fails.append("entries that differ by PATH, or agree on must_flag, are not "
                     "contradictions - reporting them would make the check noise: %r"
                     % (quiet,))
    top, minfp = ceiling([1, 2, 3], [4, 5], [(same[0], same[1], [("a", True), ("b", False)])])
    if (top, minfp) != (2, 1):
        fails.append("ceiling() is wrong: got %r, expected (2, 1) - one blocked positive and "
                     "one blocked negative" % ((top, minfp),))

    want = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.normcase(REPO) != os.path.normcase(want):
        fails.append("REPO is %r, not this file's own repo root %r. A machine-specific path in a "
                     "GATE is red on every platform but one - measured: 'ModuleNotFoundError: "
                     "No module named cap_spelling_corpus'" % (REPO, want))

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


def main():
    path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(path)
    sys.dont_write_bytecode = True
    guard = load_guard(path)

    pos, neg = split_corpus()

    caught, missed, crashed = [], [], []
    for name, rel, _mf, src in pos:
        with tempfile.TemporaryDirectory() as td:
            r = run_entry(guard, rel, src, td)
        if isinstance(r, tuple):
            crashed.append((name, r[1]))
        elif r:
            caught.append(name)
        else:
            missed.append(name)

    fp, clean, ncrash = [], [], []
    for name, rel, _mf, src in neg:
        with tempfile.TemporaryDirectory() as td:
            r = run_entry(guard, rel, src, td)
        if isinstance(r, tuple):
            ncrash.append((name, r[1]))
        elif r:
            fp.append(name)
        else:
            clean.append(name)

    npos, nneg = len(pos), len(neg)
    print("=" * 72)
    print(f"GUARD: {label}")
    print("=" * 72)
    print(f"POSITIVES (must_flag=True):  CAUGHT {len(caught)}/{npos}   "
          f"MISSED {len(missed)}   CRASHED {len(crashed)}")
    print(f"NEGATIVES (must stay quiet): CLEAN  {len(clean)}/{nneg}   "
          f"FALSE-POS {len(fp)}   CRASHED {len(ncrash)}")
    print(f"DENOMINATOR: {npos} positives + {nneg} negatives = {npos + nneg} corpus entries")
    groups = contradictions()
    if groups:
        top, minfp = ceiling(pos, neg, groups)
        print(f"CEILING:     CAUGHT {top}/{npos} at zero false positives, or {npos}/{npos} "
              f"at {minfp}+ false positives - NEVER both.")
        print(f"             {len(groups)} contradictory input group(s): entries that are "
              f"byte-identical in (rel_path, source) and disagree on must_flag. A guard sees "
              f"one input and is asked for two answers.")
        for rel, _src, members in groups:
            names = ", ".join("%s=%s" % (n, mf) for n, mf in members)
            print(f"               {rel}: {names}")
    if crashed:
        print(f"\nCRASHES on positives ({len(crashed)}): {crashed[:8]}")
    if ncrash:
        print(f"CRASHES on negatives ({len(ncrash)}): {ncrash[:8]}")
    print(f"\nMISSED ({len(missed)}):")
    for n in missed:
        print("   -", n)
    if fp:
        print(f"\nFALSE POSITIVES ({len(fp)}):")
        for n in fp:
            print("   -", n)


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
