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
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# [C7 2026-08-20] MODULE SCOPE, and it was MISSING. selftest() imports its split-out sibling
# lazily (to avoid an import cycle), and the docstring there claimed this line already existed -
# it did not. `python tools/no_regression.py --selftest` worked only because running a file as a
# script puts its directory at sys.path[0]; `python -m tools.no_regression --selftest` raised
# ModuleNotFoundError. Every caller in this repo invokes it as a script, so nothing was red - the
# exact invocation-dependent shape the task #17 sweep hunts, introduced by the split that was
# fixing two OTHER defects, with a docstring asserting the mitigation was present. Found by the
# source-coverage pass asking whether a fix had created a new instance of the class it fixed.
sys.path.insert(0, HERE)

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

def repo_sibling_modules(mod, repo) -> dict:
    """{name: module} for the repo-local modules `mod` pulled into its own globals.

    A loaded version's DELEGATES, in other words. Used by shared_siblings() below to notice that
    the two sides of an A/B are executing the same code.
    """
    out = {}
    for value in vars(mod).values():
        if not isinstance(value, types.ModuleType):
            continue
        path = getattr(value, "__file__", "") or ""
        if path and os.path.abspath(path).startswith(os.path.abspath(repo) + os.sep):
            out[value.__name__] = value
    return out


def shared_siblings(prev, cur, repo) -> list:
    """Repo-local modules that BOTH versions resolved to the same object. Pure, so it is testable.

    [SELF-COMPARE 2026-08-19] The confound this exists to refuse. `load_version` imports each
    version under a unique module name, which isolates the two FILES - but not their imports. A
    unit that delegates (`return cap_shapes.slicing_offenders(...)`) has its real detector in a
    sibling, and `import cap_shapes` resolves through the ordinary module cache to the WORKING
    TREE copy for both sides. The predecessor then executes the code it is supposed to be a
    yardstick FOR, `lost` is empty by construction, and the gate reports OK for any regression.

    MEASURED on this repo, 2026-08-20: crippling `cap_shapes.slicing_offenders` so it keeps ~60%
    of what it saw moved BOTH sides together - "predecessor f77eefd4 saw 64 of 105, working tree
    sees 64" against 102/102 before - and `no-regression: OK`, exit 0. The tell is that the
    PREDECESSOR's score changed in response to a working-tree edit; a yardstick that moves when
    the thing it measures moves is not a yardstick. The gate went vacuous at fec8db9, a
    COMMENT-ONLY commit that rolled a delegate into history, and nothing noticed for weeks.
    """
    shared = set(repo_sibling_modules(prev, repo)) & set(repo_sibling_modules(cur, repo))
    p, c = repo_sibling_modules(prev, repo), repo_sibling_modules(cur, repo)
    return sorted(name for name in shared if p[name] is c[name])


def load_with_siblings(path, tag, repo, sha, names, work):
    """Load `path`, resolving its repo-local imports to THEIR state at `sha`.

    [SELF-COMPARE 2026-08-19] Isolating the two FILES is not isolating the two VERSIONS. A unit
    that delegates keeps its detector in a sibling, and the predecessor's `import cap_shapes`
    resolves through the ordinary module cache to the working tree - so the yardstick is made of
    the very code it is meant to measure.

    The fix is a SEARCH PATH rather than seeded `sys.modules` entries, and that choice is
    load-bearing: the sibling has siblings of its own (`cap_shapes` imports `cap_types`), and a
    path entry resolves the whole transitive closure at `sha` without this function having to
    know the dependency order. Seeding module objects one at a time would resolve the first hop
    correctly and silently take the second from the working tree.

    A sibling absent at `sha` is left alone rather than faked: the predecessor genuinely did not
    have it, and inventing one would be a different program from the one that shipped.
    """
    sibdir = tempfile.mkdtemp(prefix="prevsib_", dir=work)
    materialised = []
    # [TRANSITIVE 2026-08-20] EVERY hook module at `sha`, not just the unit's direct imports.
    # The first version materialised only `names` - what the unit imports itself - and the leak
    # simply moved one hop down: capped_report imports cap_shapes, cap_shapes imports cap_types,
    # and cap_types was still resolved from the working tree. MEASURED: after two corpus
    # positives were added that only the CURRENT cap_types can detect, the PREDECESSOR detected
    # them too - 104 of 107 on both sides, where a genuine A/B gives 102 against 104. Half of an
    # isolation is not an isolation, so the whole directory comes across at that commit.
    listing = _git(repo, "ls-tree", "--name-only", "%s:hooks" % sha) or ""
    wanted = {n if n.endswith(".py") else "%s.py" % n
              for n in listing.split()} | {"%s.py" % n for n in names}
    for filename in sorted(wanted):
        if not filename.endswith(".py"):
            continue
        blob = _git(repo, "show", "%s:hooks/%s" % (sha, filename))
        if blob is None:
            continue
        with open(os.path.join(sibdir, filename), "w", encoding="utf-8") as fh:
            fh.write(blob)
        materialised.append(filename[:-3])
    saved = {n: sys.modules.pop(n, None) for n in materialised}
    sys.path.insert(0, sibdir)
    try:
        return load_version(path, tag)
    finally:
        # Leave the interpreter exactly as found: the predecessor's copies must not be visible to
        # anything that imports after this point, least of all to the working-tree version.
        if sibdir in sys.path:
            sys.path.remove(sibdir)
        for name in materialised:
            sys.modules.pop(name, None)
            if saved[name] is not None:
                sys.modules[name] = saved[name]


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
        # cur FIRST, because its repo-local imports are what the predecessor must be given its
        # own copies of. Then load prev against the sibling state at ITS commit.
        prev = load_with_siblings(prev_path, "prev", repo, sha,
                                  sorted(repo_sibling_modules(cur, repo)), work)

        # REFUSE a confounded A/B rather than issuing a verdict from one. See shared_siblings().
        shared = shared_siblings(prev, cur, repo)
        if shared:
            raise Broken(
                "both versions of %s resolve %s to the SAME working-tree module object, so the "
                "predecessor executes the code it is supposed to be a yardstick for. `lost` "
                "would be empty for any regression and the verdict would be a self-comparison. "
                "Register the unit where the detector actually lives, or give the predecessor "
                "its own copy of the sibling." % (rel, ", ".join(shared)))

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
            # The FULL sets, not just the deltas. _detected_now() promised "everything the
            # predecessor saw minus what was lost, plus anything gained" and could only return
            # `gained`, because the deltas were all compare() handed back - so a capability BOTH
            # versions detect was invisible to it and every such waiver filed as SETTLED.
            "prev_hits": sorted(prev_hits),
            "cur_hits": sorted(cur_hits),
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
    lost, plus anything gained.

    [STALE-TAUTOLOGY 2026-08-19] That sentence was correct and the code did not implement it: it
    returned `gained` alone, which is "detected now AND NOT detected before". A capability BOTH
    versions detect - the ordinary case for a waiver whose defect has been fixed - appeared in
    neither `lost` nor `gained`, so it fell through to SETTLED and could never be reported STALE.
    The waiver ledger could therefore never tell the caller to prune anything, which is the one
    job it has; `docs/V131_REVIEW_PLAN.md:1792` promises "the waiver goes STALE and BLOCKING the
    moment the corpus stops contradicting itself", and that trigger was dead.

    `cur_hits` is the direct answer and is now returned by compare(). The `gained` fallback keeps
    an older result dict readable rather than silently reporting nothing for it.
    """
    if "cur_hits" in res:
        return set(res["cur_hits"])
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
def selftest():
    """Delegates to tools/noregress_selftest.py - see that module for why the split exists.

    The import is deliberately INSIDE the function: noregress_selftest imports this module, so a
    module-scope import here would be a cycle. It is not the invocation-dependent kind this repo
    hunts - the sibling directory is put on sys.path explicitly at module scope, above.
    """
    from noregress_selftest import selftest as _selftest
    return _selftest()


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
