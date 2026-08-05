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

REPO = r"C:\Users\ammar\Downloads\unbluff"
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
