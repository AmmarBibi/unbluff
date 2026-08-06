"""Block a change that stops detecting something its predecessor detected.

THE GAP THIS CLOSES. Mutation entries pin what a fix ADDS. Nothing in this repo pinned what
a fix TOOK AWAY. Measured on 2026-08-02: a rewrite of hooks/capped_report.py was blind to 10
of 14 cap spellings its own predecessor caught - with both controls holding - while
run_selftests printed 22/22, tests/test_integration.py printed 30/30, and 92 of 94 mutations
reported ALL CAUGHT. Every gate was green on code that had gone blinder.

HOW IT WORKS. Load the working-tree version and its predecessor into one process under
distinct module names, run BOTH over a shared corpus of planted fixtures, and diff the
detection sets. A capability present before and absent after blocks, unless a reason is on
record in tests/noregress_waivers.py.

FOUR THINGS THAT LOOK LIKE DETAILS AND ARE NOT:

1. THE PREDECESSOR IS THE FIRST *DIFFERING* BLOB, not HEAD~1 and not the last commit that
   touched the file. hooks/capped_report.py has exactly ONE commit in its whole history and
   that blob is byte-identical to the working tree. The entire 10-of-14 regression happened
   between two UNCOMMITTED rewrites. A "last commit touching this file" rule would have
   diffed two identical files and passed - this gate would have failed at exactly the job it
   exists for. Walking past identical blobs is load-bearing.

2. THE PROBE SELF-CALIBRATES PER VERSION. The 1dcf430 baseline sees a planted fixture only
   via slicing_offenders(<hooks dir>) - a flat glob - and the rewrite only via
   slicing_offenders(<repo root>) - a tree walk. A gate hard-coding either call measures the
   other version as detecting nothing, and would report a total loss that never happened.

3. A ZERO SCORE IS NEVER A PASS, and the two sides are NOT symmetric.
     PREV scores 0 -> the yardstick is unusable. Raise, print, emit NO verdict. A ruler that
                      measures nothing is a broken harness, not a clean tree.
     CUR  scores 0 -> total loss. FAIL, naming every capability the predecessor saw. The gate
                      cannot tell "capability removed" from "entrypoint renamed without
                      updating the registry" and must not guess - both need a human.

4. THE UNIT POPULATION IS DERIVED, THE REGISTRY ONLY SAYS HOW TO PROBE. A registry that could
   drop a unit from the question would be the fifth hardcoded roster this repo has had to dig
   out. Units with no corpus are printed as UNCOVERED with a coverage denominator, never as
   passing.

Run: python tools/no_regression.py            (the gate)
     python tools/no_regression.py --selftest (assertions A-E below)
"""

from __future__ import annotations

import argparse
import ast
import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# Directories a unit may live in. Derived population, not a roster of unit NAMES.
UNIT_ROOTS = ("hooks", "tools", "scripts", "skills")
SKIP_DIRS = frozenset({"__pycache__", ".git", ".venv", "venv", ".tox", "node_modules"})

# Entrypoints to try per probe family, by MEANING rather than signature. Order is
# irrelevant: every one is scored and the best wins.
PROBE_ENTRYPOINTS = {
    "cap_detector": ("slicing_offenders", "cap_sites", "sweep", "module_cap_sites"),
}

_SAMPLE = 8            # calibration sample size before escalating to the full positive set
_load_counter = [0]


class Broken(Exception):
    """The harness cannot measure. Never a verdict, always an error."""


# --------------------------------------------------------------------------------------
# loading two versions of one module into one process
# --------------------------------------------------------------------------------------

def load_version(path, tag):
    """Import `path` under a unique module name so two versions can coexist."""
    _load_counter[0] += 1
    name = "_noregress_%s_%d" % (tag, _load_counter[0])
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Broken("cannot build an import spec for %s" % path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                       # noqa: BLE001 - any import error is fatal
        raise Broken("%s failed to import: %r" % (path, exc))
    return mod


# --------------------------------------------------------------------------------------
# what "the previous version" means
# --------------------------------------------------------------------------------------

def _git(repo, *args):
    proc = subprocess.run(("git", "-C", repo) + args, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return proc.stdout


def _norm(text):
    return text.replace("\r\n", "\n")


def history_truncated(repo):
    """Why this checkout cannot answer questions about the past, or None if it can.

    [CI-SHALLOW, 2026-08-06] `actions/checkout@v4` fetches ONE commit. Every "no committed
    blob differs" verdict in such a tree is an UNANSWERED QUESTION, not a finding: the
    differing blob exists on the remote and was simply never fetched. Conflating the two put
    11 of 11 CI jobs red on a commit that was green locally, and the failure text asserted a
    fact about the repository ("has no predecessor") that was false.

    Both truncation modes are asked about, because either one hides blobs and only one of
    them is the famous one: a `--depth` clone, and a partial (blobless/treeless) clone whose
    objects are fetched lazily from a promisor remote.
    """
    if (_git(repo, "rev-parse", "--is-shallow-repository") or "").strip() == "true":
        return "history is SHALLOW (a --depth clone), so an older blob is unreachable here"
    for key in ("remote.origin.partialclonefilter", "remote.origin.promisor"):
        if (_git(repo, "config", "--get", key) or "").strip():
            return ("history is a PARTIAL clone (%s), so an older blob may be unreachable here"
                    % key)
    return None


def predecessor(repo, rel, renamed_from=None):
    """(bytes, sha, reason) - the newest committed blob that DIFFERS from the working tree.

    Returns (None, None, reason) when there is nothing to compare against. That is a named
    SKIP, never a pass - and when the checkout itself cannot see the past, the reason SAYS SO
    rather than reporting the absence of evidence as evidence of absence.
    """
    live_path = os.path.join(repo, rel.replace("/", os.sep))
    if not os.path.isfile(live_path):
        return None, None, "unit is not in the working tree"
    with open(live_path, encoding="utf-8") as fh:
        current = _norm(fh.read())

    paths = [rel] + ([renamed_from] if renamed_from else [])
    seen_any_commit = False
    for path in paths:
        log = _git(repo, "log", "--follow", "--format=%H", "--", path)
        if not log:
            continue
        for sha in [s for s in log.split("\n") if s.strip()]:
            seen_any_commit = True
            blob = _git(repo, "show", "%s:%s" % (sha, path))
            if blob is None:
                continue
            if _norm(blob) != current:
                return blob, sha, None
    truncated = history_truncated(repo)
    if truncated:
        # UNANSWERABLE, not empty. Kept distinct from the two definite reasons below so a
        # caller can tell "I looked and there is nothing" from "I was not able to look".
        return None, None, truncated
    if not seen_any_commit:
        return None, None, "file has never been committed"
    return None, None, "no committed blob differs from the working tree"


# --------------------------------------------------------------------------------------
# deriving the unit population
# --------------------------------------------------------------------------------------

def derive_units(repo):
    """Every module exposing a --selftest. DERIVED by reading files, never listed."""
    out = []
    for root_name in UNIT_ROOTS:
        root = os.path.join(repo, root_name)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in sorted(filenames):
                if not fn.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding="utf-8") as fh:
                        text = fh.read()
                except OSError:
                    continue
                if "--selftest" not in text:
                    continue
                try:
                    tree = ast.parse(text)
                except SyntaxError:
                    continue
                names = set()
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        names.add(node.name)
                if names & {"selftest", "_selftest"}:
                    out.append(os.path.relpath(path, repo).replace(os.sep, "/"))
    return sorted(set(out))


# --------------------------------------------------------------------------------------
# the probe: score every (entrypoint, argument strategy) pair, keep the best
# --------------------------------------------------------------------------------------

def _plant(entry, base):
    """Materialise one corpus entry under `base`; return the planted file's directory."""
    _name, rel_path, _flag, source = entry
    dest = os.path.join(base, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(source)
    return os.path.dirname(dest)


def _call(fn, arg):
    """Invoke an entrypoint, tolerating the shapes these detectors actually use."""
    try:
        res = fn(arg)
    except TypeError:
        try:
            res = fn()
        except Exception:                          # noqa: BLE001
            return None
    except Exception:                              # noqa: BLE001
        return None
    if isinstance(res, tuple):
        res = res[0] if res else None
    try:
        return bool(res)
    except Exception:                              # noqa: BLE001
        return None


class Probe(object):
    """Finds how to make ONE version of a detector see a planted fixture."""

    def __init__(self, module, family, tag):
        self.module = module
        self.tag = tag
        self.entrypoints = []
        for name in PROBE_ENTRYPOINTS.get(family, ()):
            fn = getattr(module, name, None)
            if callable(fn):
                self.entrypoints.append((name, fn))
        self.choice = None

    def _score(self, name, fn, strategy, entries, trees):
        hits = 0
        for entry in entries:
            root, planted_dir = trees[entry[0]]
            arg = root if strategy == "root" else planted_dir
            if _call(fn, arg):
                hits += 1
        return hits

    def calibrate(self, positives, trees):
        """Pick the (entrypoint, strategy) that sees the most positives.

        Escalation is load-bearing: the round-1 regression's blind spot IS the first eight
        corpus positives, so an 8-case sample scores 0 for every combination and, without
        rescoring over the full set, the gate reports a total loss that did not happen.
        """
        if not self.entrypoints:
            raise Broken("%s exposes none of the known entrypoints for this probe family"
                         % self.tag)
        combos = [(n, f, s) for (n, f) in self.entrypoints for s in ("root", "dirname")]
        sample = positives[:_SAMPLE]
        best = (0, None)
        for name, fn, strategy in combos:
            score = self._score(name, fn, strategy, sample, trees)
            if score > best[0]:
                best = (score, (name, fn, strategy))
        if best[0] == 0 and len(positives) > len(sample):
            for name, fn, strategy in combos:
                score = self._score(name, fn, strategy, positives, trees)
                if score > best[0]:
                    best = (score, (name, fn, strategy))
        self.choice = best[1]
        return best[0]

    def detects(self, entry, trees):
        if self.choice is None:
            return False
        _name, fn, strategy = self.choice
        root, planted_dir = trees[entry[0]]
        return bool(_call(fn, root if strategy == "root" else planted_dir))

    def sound(self, empty_dir, capfree_dir):
        """Must stay silent on an empty tree AND on a cap-free file."""
        if self.choice is None:
            return False
        _name, fn, _strategy = self.choice
        return not _call(fn, empty_dir) and not _call(fn, capfree_dir)


# --------------------------------------------------------------------------------------
# the A/B
# --------------------------------------------------------------------------------------

_CAPFREE = "def plain(xs):\n    return list(xs)\n"


def compare(repo, rel, corpus_rel, family, renamed_from=None):
    """Run both versions over the corpus. Returns a dict; raises Broken if unmeasurable."""
    blob, sha, reason = predecessor(repo, rel, renamed_from)
    if blob is None:
        return {"unit": rel, "skipped": reason, "lost": [], "gained": [],
                "new_false_positives": [], "prev_sha": None}

    corpus_path = os.path.join(repo, corpus_rel.replace("/", os.sep))
    if not os.path.isfile(corpus_path):
        raise Broken("corpus %s does not exist" % corpus_rel)
    corpus = load_version(corpus_path, "corpus")
    entries = list(getattr(corpus, "ENTRIES", ()))
    if not entries:
        raise Broken("corpus %s exposes no ENTRIES" % corpus_rel)
    positives = [e for e in entries if e[2]]
    negatives = [e for e in entries if not e[2]]

    work = tempfile.mkdtemp(prefix="noregress_")
    try:
        prev_path = os.path.join(work, "prev_%s" % os.path.basename(rel))
        with open(prev_path, "w", encoding="utf-8") as fh:
            fh.write(blob)
        cur = load_version(os.path.join(repo, rel.replace("/", os.sep)), "cur")
        prev = load_version(prev_path, "prev")

        # ONE planted tree per entry, read by BOTH versions: halves filesystem cost and
        # removes the confound of the two sides reading different bytes.
        trees = {}
        for entry in entries:
            base = tempfile.mkdtemp(prefix="tree_", dir=work)
            trees[entry[0]] = (base, _plant(entry, base))
        empty_dir = tempfile.mkdtemp(prefix="empty_", dir=work)
        capfree_dir = tempfile.mkdtemp(prefix="capfree_", dir=work)
        with open(os.path.join(capfree_dir, "plain.py"), "w", encoding="utf-8") as fh:
            fh.write(_CAPFREE)

        p_prev = Probe(prev, family, "predecessor %s" % (sha or "")[:8])
        p_cur = Probe(cur, family, "working tree")
        prev_score = p_prev.calibrate(positives, trees)
        cur_score = p_cur.calibrate(positives, trees)

        if prev_score == 0:
            raise Broken(
                "the predecessor detects NOTHING under any entrypoint or strategy - the "
                "yardstick is unusable, so no verdict can be issued. Check the probe family "
                "for %s." % rel)
        if not p_prev.sound(empty_dir, capfree_dir):
            raise Broken("the predecessor fires on an empty tree or a cap-free file - the "
                         "harness is measuring noise, not detection")
        if cur_score and not p_cur.sound(empty_dir, capfree_dir):
            raise Broken("the working-tree version fires on an empty tree or a cap-free "
                         "file - the harness cannot separate detection from noise")

        prev_hits = set(e[0] for e in positives if p_prev.detects(e, trees))
        cur_hits = set(e[0] for e in positives if p_cur.detects(e, trees))
        new_fps = sorted(e[0] for e in negatives
                         if p_cur.detects(e, trees) and not p_prev.detects(e, trees))
        return {
            "unit": rel, "skipped": None, "prev_sha": sha,
            "prev_entry": p_prev.choice[0] if p_prev.choice else None,
            "cur_entry": p_cur.choice[0] if p_cur.choice else None,
            "positives": len(positives),
            "prev_detected": len(prev_hits), "cur_detected": len(cur_hits),
            "lost": sorted(prev_hits - cur_hits),
            "gained": sorted(cur_hits - prev_hits),
            "new_false_positives": new_fps,
            "total_loss": cur_score == 0,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------------------
# waivers
# --------------------------------------------------------------------------------------

def classify_waivers(waivers, results, units, corpora, repo=REPO):
    """(active, settled, problems, unknown) - see tests/noregress_waivers.py for the states.

    `unknown` is the sixth state and the reason this returns four lists rather than three:
    a checkout that cannot see the past cannot classify a waiver at all, and neither BLOCKING
    (which is what it used to do, and which put CI red on green code) nor silence (which
    would make the gate unfailable) is honest about that. It is reported and does not block.
    """
    active, settled, problems, unknown = [], [], [], []
    # Asked ONCE, and compared by identity with the reason predecessor() recorded, so this
    # never degrades into grepping the message text for a keyword.
    unanswerable = history_truncated(repo)
    by_unit = dict((r["unit"], r) for r in results)
    for w in waivers:
        unit, cap = w.get("unit"), w.get("capability")
        if unit not in units:
            problems.append("GHOST waiver: unit %r is not a unit this gate asks about" % unit)
            continue
        known = corpora.get(unit)
        if known is not None and cap not in known:
            problems.append("GHOST waiver: %s names capability %r, which is not in its corpus"
                            % (unit, cap))
            continue
        res = by_unit.get(unit)
        if res is not None and unanswerable and res.get("skipped") == unanswerable:
            unknown.append("%s / %s - state UNDETERMINED: %s. This run neither confirms nor "
                           "prunes the waiver; re-run against full history."
                           % (unit, cap, unanswerable))
            continue
        if res is None or res.get("skipped"):
            problems.append("UNUSED waiver: %s has no predecessor, so nothing can be lost "
                            "(%s)" % (unit, res.get("skipped") if res else "not compared"))
            continue
        if cap in res["lost"]:
            active.append("%s / %s - %s" % (unit, cap, w.get("reason", "no reason given")))
        elif cap in res.get("gained", []) or cap in _detected_now(res):
            problems.append("STALE waiver: %s / %s is detected again - prune it, a ledger "
                            "nobody prunes rots into pre-authorisation" % (unit, cap))
        else:
            settled.append("%s / %s - %s" % (unit, cap, w.get("reason", "no reason given")))
    return active, settled, problems, unknown


def _detected_now(res):
    """Capabilities the working tree sees: everything the predecessor saw minus what was
    lost, plus anything gained."""
    return set(res.get("gained", []))


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def _load_side(repo, rel):
    path = os.path.join(repo, rel.replace("/", os.sep))
    return load_version(path, "side")


def run(repo=REPO, verbose=True):
    units = derive_units(repo)
    try:
        registry = _load_side(repo, "tests/noregress_registry.py").REGISTRY
    except Exception as exc:                       # noqa: BLE001
        print("no-regression: cannot load the registry: %r" % exc)
        return 2
    try:
        waivers = _load_side(repo, "tests/noregress_waivers.py").WAIVERS
    except Exception as exc:                       # noqa: BLE001
        print("no-regression: cannot load the waiver ledger: %r" % exc)
        return 2

    fails, results, corpora = [], [], {}

    ghosts = sorted(u for u in registry if u not in units)
    for g in ghosts:
        fails.append("REGISTRY GHOST: %r is registered but is not a unit this gate finds. "
                     "A rename must update tests/noregress_registry.py - otherwise the gate "
                     "silently measures nothing." % g)

    covered = [u for u in units if u in registry]
    for unit in covered:
        cfg = registry[unit]
        try:
            res = compare(repo, unit, cfg["corpus"], cfg.get("probe", ""),
                          cfg.get("renamed_from"))
        except Broken as exc:
            fails.append("BROKEN HARNESS on %s: %s" % (unit, exc))
            continue
        results.append(res)
        corpus_path = os.path.join(repo, cfg["corpus"].replace("/", os.sep))
        if os.path.isfile(corpus_path):
            try:
                corpora[unit] = set(
                    e[0] for e in getattr(load_version(corpus_path, "cx"), "ENTRIES", ()))
            except Broken:
                corpora[unit] = set()

    active, settled, wproblems, wunknown = classify_waivers(waivers, results, units, corpora,
                                                            repo)
    fails.extend(wproblems)

    waived = set()
    for line in active:
        waived.add(tuple(line.split(" - ")[0].split(" / ")))

    for res in results:
        if res.get("skipped"):
            if verbose:
                print("-- %s SKIPPED: %s - UNCOVERED, not passing"
                      % (res["unit"], res["skipped"]))
            continue
        blocking = [c for c in res["lost"] if (res["unit"], c) not in waived]
        if verbose:
            print("-- %s: predecessor %s saw %d of %d, working tree sees %d "
                  "(entrypoints prev=%s cur=%s)"
                  % (res["unit"], (res["prev_sha"] or "?")[:8], res["prev_detected"],
                     res["positives"], res["cur_detected"],
                     res["prev_entry"], res["cur_entry"]))
            if res["gained"]:
                print("   gained %d: %s" % (len(res["gained"]), ", ".join(res["gained"][:6])))
            if res["new_false_positives"]:
                print("   NEW FALSE POSITIVES %d: %s"
                      % (len(res["new_false_positives"]),
                         ", ".join(res["new_false_positives"][:6])))
        if res.get("total_loss"):
            fails.append("TOTAL LOSS on %s: the working tree detects NOTHING the predecessor "
                         "detected (%d capabilities). Either the capability was removed or an "
                         "entrypoint was renamed without updating the registry - the gate "
                         "cannot tell these apart and will not guess."
                         % (res["unit"], res["prev_detected"]))
        elif blocking:
            fails.append("REGRESSION on %s: %d of %d capabilities the predecessor detected "
                         "are no longer detected: %s"
                         % (res["unit"], len(blocking), res["prev_detected"],
                            ", ".join(blocking)))

    if verbose:
        pct = (100 * len(covered) // len(units)) if units else 0
        print("-- coverage: %d of %d units have a corpus (%d%%); %d uncovered"
              % (len(covered), len(units), pct, len(units) - len(covered)))
        if len(covered) < len(units):
            missing = [u for u in units if u not in registry]
            print("   UNCOVERED (not passing): %s%s"
                  % (", ".join(missing[:8]), " ..." if len(missing) > 8 else ""))
        print("-- waivers: %d active, %d settled, %d problem(s), %d undetermined (of %d)"
              % (len(active), len(settled), len(wproblems), len(wunknown), len(waivers)))
        for line in active:
            print("   ACTIVE waiver: %s" % line)
        for line in wunknown:
            # Loud, because this is the state in which the gate verified nothing. Silence
            # here would make a truncated checkout indistinguishable from a clean run.
            print("   UNDETERMINED waiver: %s" % line)

    for f in fails:
        print("NO-REGRESSION FAIL:", f)
    print("no-regression: OK" if not fails else "no-regression: FAILED")
    return 0 if not fails else 1


# --------------------------------------------------------------------------------------
# selftest
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

    print("-- no-regression selftest: 6 assertions (A derive, B identical-blob walk, "
          "C narrowing caught, D unusable yardstick, E total loss, F shallow history)")
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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        return run()
    except Broken as exc:
        print("NO-REGRESSION BROKEN HARNESS:", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
