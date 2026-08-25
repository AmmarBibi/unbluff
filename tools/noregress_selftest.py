#!/usr/bin/env python3
"""The no-regression gate's selftest apparatus - fixtures and assertions A-G.

Split out of tools/no_regression.py on 2026-08-20 because fixing the two HIGHs that task #17
found there took the file from 805 to 949 lines against a 800-line limit it was ALREADY over,
and this repo's recorded decision is that the next growth be PRECEDED by the split rather than
absorbed by another re-record - a re-record is the loophole in the ratchet. Follows the existing
hooks/*_selftest.py convention rather than inventing a second one.

A pure move: no assertion changed, so the split cannot quietly weaken what is checked. The
import list below is DERIVED (see scratchpad/split_noregress.py), not hand-typed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from no_regression import (  # noqa: E402  (path set directly above)
    Broken,
    _detected_now,
    _load_side,
    classify_waivers,
    compare,
    derive_units,
    predecessor,
    run,
    shared_siblings,
)

# [#46 item 4] Scrub git's redirect variables at import, before any fixture can run.
# Flagged by tools/check_selftest_isolation.py, which DERIVES this population from the AST.
# Reason this file is in the population: it CLONES, which under a poisoned GIT_DIR clones
# the REAL repository. Inserted after the last import's END line - a line regex put this
# block inside the multi-line `from no_regression import (...)` and broke the file.
from git_isolation import scrub_environ as _scrub_environ  # noqa: E402
_scrub_environ()

# --------------------------------------------------------------------------------------

def _scratch_repo():
    """A tiny git repo with a detector that is committed, then narrowed in the worktree."""
    base = tempfile.mkdtemp(prefix="nrself_")
    for d in ("hooks", "tests", "tools"):
        os.makedirs(os.path.join(base, d))
    det_v1 = (
        "import ast, glob, os\n\n\n"
        "def slicing_offenders(d):\n"
        "    out = []\n"
        "    for p in sorted(glob.glob(os.path.join(d, '*.py'))):\n"
        "        try:\n"
        "            t = ast.parse(open(p, encoding='utf-8').read())\n"
        "        except Exception:\n"
        "            continue\n"
        "        for n in ast.walk(t):\n"
        "            if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice):\n"
        "                u = n.slice.upper\n"
        "                if isinstance(u, ast.Name) and u.id.startswith('MAX_'):\n"
        "                    out.append(p)\n"
        "    return sorted(set(out))\n\n\n"
        "def selftest():\n    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    import sys\n"
        "    raise SystemExit(selftest() if '--selftest' in sys.argv else 0)\n")
    # v2 narrows: only MAX_B is a cap now, so MAX_A regresses.
    det_v2 = det_v1.replace("u.id.startswith('MAX_')", "u.id == 'MAX_B'")
    corpus = (
        "ENTRIES = (\n"
        "    ('a', 'hooks/a.py', True, 'MAX_A = 3\\ndef r(xs):\\n    return xs[:MAX_A]\\n'),\n"
        "    ('b', 'hooks/b.py', True, 'MAX_B = 3\\ndef r(xs):\\n    return xs[:MAX_B]\\n'),\n"
        "    ('n', 'hooks/n.py', False, 'def r(xs):\\n    return list(xs)\\n'),\n"
        ")\n")
    with open(os.path.join(base, "hooks", "det.py"), "w", encoding="utf-8") as fh:
        fh.write(det_v1)
    with open(os.path.join(base, "tests", "corpus.py"), "w", encoding="utf-8") as fh:
        fh.write(corpus)
    for cmd in (("init",), ("config", "user.email", "t@t"), ("config", "user.name", "t"),
                ("add", "-A"), ("commit", "-m", "v1")):
        subprocess.run(("git", "-C", base) + cmd, capture_output=True, text=True)
    return base, det_v2


def _shallow_fixture():
    """A repo whose unit REALLY regressed one commit ago, plus a --depth 1 clone of it.

    Two commits: v1 detects capabilities a+b, v2 detects only b. A waiver excuses 'a'. In the
    FULL clone the waiver is ACTIVE and the gate passes. In the SHALLOW clone the differing
    predecessor blob is one commit out of reach - it EXISTS, it is simply not fetched.
    """
    base = tempfile.mkdtemp(prefix="nrshal_")
    for d in ("hooks", "tests", "tools"):
        os.makedirs(os.path.join(base, d))
    det_v1 = (
        "import ast, glob, os\n\n\n"
        "def slicing_offenders(d):\n"
        "    out = []\n"
        "    for p in sorted(glob.glob(os.path.join(d, '*.py'))):\n"
        "        try:\n"
        "            t = ast.parse(open(p, encoding='utf-8').read())\n"
        "        except Exception:\n"
        "            continue\n"
        "        for n in ast.walk(t):\n"
        "            if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Slice):\n"
        "                u = n.slice.upper\n"
        "                if isinstance(u, ast.Name) and u.id.startswith('MAX_'):\n"
        "                    out.append(p)\n"
        "    return sorted(set(out))\n\n\n"
        "def selftest():\n    return 0\n\n\n"
        "if __name__ == '__main__':\n"
        "    import sys\n"
        "    raise SystemExit(selftest() if '--selftest' in sys.argv else 0)\n")
    det_v2 = det_v1.replace("u.id.startswith('MAX_')", "u.id == 'MAX_B'")
    files = {
        os.path.join("hooks", "det.py"): det_v1,
        os.path.join("tests", "corpus.py"):
            "ENTRIES = (\n"
            "    ('a', 'hooks/a.py', True, 'MAX_A = 3\\ndef r(xs):\\n    return xs[:MAX_A]\\n'),\n"
            "    ('b', 'hooks/b.py', True, 'MAX_B = 3\\ndef r(xs):\\n    return xs[:MAX_B]\\n'),\n"
            "    ('n', 'hooks/n.py', False, 'def r(xs):\\n    return list(xs)\\n'),\n"
            ")\n",
        os.path.join("tests", "noregress_registry.py"):
            "REGISTRY = {'hooks/det.py': {'corpus': 'tests/corpus.py',\n"
            "                            'probe': 'cap_detector'}}\n",
        os.path.join("tests", "noregress_waivers.py"):
            "WAIVERS = ({'unit': 'hooks/det.py', 'capability': 'a',\n"
            "            'narrowed_on': '2026-08-06',\n"
            "            'reason': 'detecting MAX_A was wrong - fixture'},)\n",
    }
    for rel, text in files.items():
        with open(os.path.join(base, rel), "w", encoding="utf-8") as fh:
            fh.write(text)
    for cmd in (("init",), ("config", "user.email", "t@t"), ("config", "user.name", "t"),
                ("add", "-A"), ("commit", "-m", "v1")):
        subprocess.run(("git", "-C", base) + cmd, capture_output=True, text=True)
    with open(os.path.join(base, "hooks", "det.py"), "w", encoding="utf-8") as fh:
        fh.write(det_v2)
    for cmd in (("add", "-A"), ("commit", "-m", "v2")):
        subprocess.run(("git", "-C", base) + cmd, capture_output=True, text=True)

    holder = tempfile.mkdtemp(prefix="nrclone_")
    shallow = os.path.join(holder, "r")
    subprocess.run(("git", "clone", "--depth", "1",
                    "file://" + base.replace(os.sep, "/"), shallow),
                   capture_output=True, text=True)
    return base, holder, shallow


def _selftest_shallow_history():
    """[CI-SHALLOW] 'I could not look' is not 'there is nothing to look at'.

    actions/checkout@v4 fetches ONE commit. On 2026-08-06 that made every one of 11 CI jobs
    red on a commit that was green locally: the differing predecessor was unreachable, the
    detector half of this module correctly said SKIPPED, and the waiver auditor read the same
    condition as "this unit has no predecessor" and blocked. A gate whose verdict depends on
    the DEPTH OF THE CHECKOUT is not measuring the code.

    The fix must not go the other way either: a shallow run that quietly returns 0 would be a
    gate that cannot fail. So the third state is REPORTED, and the CI checkout fetches history
    so the comparison is actually performed there.
    """
    fails = []
    base, holder, shallow = _shallow_fixture()
    try:
        if not os.path.isfile(os.path.join(shallow, "hooks", "det.py")):
            return ["F: the shallow clone fixture did not materialise - nothing was tested"]
        depth = subprocess.run(("git", "-C", shallow, "rev-list", "--count", "HEAD"),
                               capture_output=True, text=True).stdout.strip()
        if depth != "1":
            return ["F: the fixture clone is %s commits deep, so it does not reproduce "
                    "actions/checkout@v4 and proves nothing" % depth]

        # control: with full history the waiver is ACTIVE and the gate passes. If this fails
        # the fixture is wrong, not the code under test.
        if run(base, verbose=False) != 0:
            fails.append("F-control: the FULL-history repo must pass with the waiver active; "
                         "the fixture is broken, so the shallow half proves nothing")

        # the finding itself
        if run(shallow, verbose=False) != 0:
            fails.append("F: a --depth 1 checkout BLOCKS on an UNUSED waiver - the predecessor "
                         "is unreachable, not absent, and the gate must not convert an "
                         "unanswered question into a blocking verdict")

        # [STALE-TAUTOLOGY] _detected_now(), both directions, as a PURE assertion. The live gate
        # could not have caught this: it reports the same "1 settled" whether the rule is right
        # or wrong, because the waived capability happens not to be detected today. A fixture
        # where the answer is KNOWN is the only thing that can tell the two rules apart.
        if "a" not in _detected_now({"lost": [], "gained": [], "cur_hits": ["a", "b"]}):
            fails.append("G: _detected_now() misses a capability BOTH versions detect. That is "
                         "the ordinary shape of a waiver whose defect has since been fixed, and "
                         "it made every such waiver SETTLED and unprunable - the ledger's one job")
        if _detected_now({"lost": [], "gained": ["c"], "cur_hits": ["a", "c"]}) != {"a", "c"}:
            fails.append("G: _detected_now() is not returning what the working tree detects")
        if _detected_now({"lost": [], "gained": ["c"]}) != {"c"}:
            fails.append("G: the legacy fallback broke - an older result dict with no cur_hits "
                         "must still report what it can rather than silently reporting nothing")

        # [SELF-COMPARE] shared_siblings() must NAME a shared module object and stay silent on
        # genuinely separate ones. Asserted on synthetic modules, so it cannot pass by accident
        # on a repo that happens to be clean.
        _shared_a, _shared_b = types.ModuleType("s_a"), types.ModuleType("s_b")
        _shared_a.__file__ = os.path.join(shallow, "hooks", "s_a.py")
        _shared_b.__file__ = os.path.join(shallow, "hooks", "s_b.py")
        _prev_mod, _cur_mod = types.ModuleType("prev"), types.ModuleType("cur")
        _prev_mod.sib, _cur_mod.sib = _shared_a, _shared_a          # the SAME object: confounded
        if shared_siblings(_prev_mod, _cur_mod, shallow) != ["s_a"]:
            fails.append("G: shared_siblings() did not name a sibling both versions resolve to "
                         "the SAME object - the confound that made the A/B a self-comparison")
        _prev_mod.sib = _shared_b                                    # distinct copies: fine
        if shared_siblings(_prev_mod, _cur_mod, shallow):
            fails.append("G: shared_siblings() fired on two SEPARATE sibling modules - a guard "
                         "that flags a correct A/B is one its owner deletes")

        # ...and it must not have passed by pretending it verified something
        units = derive_units(shallow)
        res = compare(shallow, "hooks/det.py", "tests/corpus.py", "cap_detector")
        waivers = _load_side(shallow, "tests/noregress_waivers.py").WAIVERS
        classified = classify_waivers(waivers, [res], units, {"hooks/det.py": {"a", "b", "n"}},
                                      shallow)
        if len(classified) < 4:
            fails.append("F: classify_waivers still returns %d lists - there is no place to "
                         "report a waiver whose state could not be determined"
                         % len(classified))
        else:
            unknown = classified[3]
            if not unknown:
                fails.append("F: the shallow run reported NO unknown waiver - silence and "
                             "'verified' look identical, which is the failure this gate exists "
                             "to stop")
            elif not any("SHALLOW" in u for u in unknown):
                fails.append("F: the unknown state does not name shallow history as the "
                             "reason, so a reader cannot tell it from a real absence: %r"
                             % unknown)
        _b, _s, reason = predecessor(shallow, "hooks/det.py")
        if reason and "SHALLOW" not in reason:
            fails.append("F: predecessor() reported %r on a shallow clone - it must say the "
                         "history is truncated, not that no blob differs" % reason)
    finally:
        shutil.rmtree(base, ignore_errors=True)
        shutil.rmtree(holder, ignore_errors=True)
    return fails


def selftest():
    fails = []

    # A - the unit population is DERIVED, and finds a selftest-bearing module
    base, det_v2 = _scratch_repo()
    try:
        units = derive_units(base)
        if "hooks/det.py" not in units:
            fails.append("A: derive_units did not find hooks/det.py -> %s" % units)

        # B - predecessor walks PAST an identical blob rather than comparing a file to itself
        blob, sha, reason = predecessor(base, "hooks/det.py")
        if blob is not None or reason != "no committed blob differs from the working tree":
            fails.append("B: an unchanged file must yield NO predecessor, got sha=%s reason=%r"
                         % (sha, reason))

        # C - a real narrowing in the WORKING TREE is caught against the committed blob
        with open(os.path.join(base, "hooks", "det.py"), "w", encoding="utf-8") as fh:
            fh.write(det_v2)
        res = compare(base, "hooks/det.py", "tests/corpus.py", "cap_detector")
        if res.get("skipped"):
            fails.append("C: comparison skipped unexpectedly: %s" % res["skipped"])
        elif res["lost"] != ["a"]:
            fails.append("C: expected capability 'a' lost, got lost=%s prev=%s cur=%s"
                         % (res["lost"], res.get("prev_detected"), res.get("cur_detected")))

        # D - a predecessor that detects nothing is BROKEN, never a clean verdict
        with open(os.path.join(base, "tests", "empty_corpus.py"), "w", encoding="utf-8") as fh:
            fh.write("ENTRIES = (('z', 'hooks/z.py', True, 'x = 1\\n'),)\n")
        # Assert on the REASON, not just the exception type. The first version of this
        # caught any Broken and mutation D2b proved it decorative: with the prev_score
        # guard disabled, compare() still raises Broken from the soundness check further
        # down, so `except Broken: pass` passed while the guard it tested was gone.
        try:
            compare(base, "hooks/det.py", "tests/empty_corpus.py", "cap_detector")
            fails.append("D: a predecessor scoring 0 must raise Broken, not return a verdict")
        except Broken as exc:
            if "yardstick is unusable" not in str(exc):
                fails.append("D: a predecessor scoring 0 raised the WRONG Broken - expected "
                             "the unusable-yardstick reason, got %r" % str(exc)[:120])

        # E - a total loss is reported as such, not as a small regression
        with open(os.path.join(base, "hooks", "det.py"), "w", encoding="utf-8") as fh:
            fh.write(det_v1_blind())
        res = compare(base, "hooks/det.py", "tests/corpus.py", "cap_detector")
        if not res.get("total_loss"):
            fails.append("E: a version detecting nothing must be flagged total_loss, got %s"
                         % res)
    finally:
        shutil.rmtree(base, ignore_errors=True)

    fails += _selftest_shallow_history()

    print("-- no-regression selftest: 7 assertions (A derive, B identical-blob walk, "
          "C narrowing caught, D unusable yardstick, E total loss, F shallow history, "
          "G waiver-staleness + self-comparison)")
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


def det_v1_blind():
    return ("import ast, glob, os\n\n\n"
            "def slicing_offenders(d):\n    return []\n\n\n"
            "def selftest():\n    return 0\n\n\n"
            "if __name__ == '__main__':\n"
            "    import sys\n"
            "    raise SystemExit(selftest() if '--selftest' in sys.argv else 0)\n")
