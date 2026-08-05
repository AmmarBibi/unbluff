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


def main():
    path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(path)
    sys.dont_write_bytecode = True
    guard = load_guard(path)

    pos = [e for e in corpus.ENTRIES if e[2]]
    neg = [e for e in corpus.ENTRIES if not e[2]]
    extra_neg = list(getattr(corpus, "NEGATIVE_CONTROLS", ()) or ())

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
    for entry in list(neg) + [e for e in extra_neg if isinstance(e, tuple) and len(e) == 4]:
        name, rel, _mf, src = entry
        with tempfile.TemporaryDirectory() as td:
            r = run_entry(guard, rel, src, td)
        if isinstance(r, tuple):
            ncrash.append((name, r[1]))
        elif r:
            fp.append(name)
        else:
            clean.append(name)

    npos = len(pos)
    nneg = len(neg) + len([e for e in extra_neg if isinstance(e, tuple) and len(e) == 4])
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
    raise SystemExit(main())
