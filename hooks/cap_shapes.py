"""Which OPERATION silently shortens a reported collection - the C1-NEW cap detector.

THE REFRAMING, and it is the whole design. Two adversarial rounds built a detector that
enumerated the ways to SPELL a bound. Python's grammar does not bound that set, so the work
never terminated and an unenumerated spelling was reported CLEAN - it failed OPEN, which is
the exact failure unbluff exists to catch. That version was reverted at 2,101 lines.

So do not classify the bound at all. Classify the OPERATION. The ways to silently shorten a
sequence ARE grammar-closed and few - a slice, a break out of an accumulation loop,
itertools.islice/takewhile, del seq[n:], sorted()[:n], a comprehension index guard,
zip(xs, range(n)), heapq.nlargest, deque(maxlen=). Once the operation is the subject, the
bound's spelling stops mattering, and every cap-spelling variant is recovered at once rather
than one taxonomy entry at a time.

A site is flagged when ALL FIVE hold:

  1. a shortening operation applies to a COLLECTION, not a str/bytes, a counter or a clock
  2. the collection is REPORTED - it leaves the function as a list, not as a bool or a count
  3. it derives from CALLER-SUPPLIED data, not from I/O this function performed itself
  4. the shortening is SILENT - no raise on the bound path, not routed through keep()/render()
  5. the site is not in BOUND_EXEMPTIONS

Clauses 1-3 live in hooks/cap_types.py. Clauses 4-5 and every shape live here.

MEASURED against tests/cap_spelling_corpus.py, 132 entries: CAUGHT 93 of 96 on the corpus as
it stood when this was designed, FALSE-POS 0 of 29, against a predecessor at 31 of 96. The
three misses are not a shortfall - they are three pairs of corpus entries that are BYTE
IDENTICAL with opposite verdicts, so 93 with zero false positives is the arithmetic ceiling.
tools/score_corpus.py detects and prints those pairs, and the ceiling with them.

Python 3.8 floor: no ast.unparse (3.9+), no match statement.
"""

from __future__ import annotations

import ast
import glob
import os
import sys

_HOOKS_DIR_CS = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR_CS not in sys.path:
    sys.path.insert(0, _HOOKS_DIR_CS)
import cap_types  # noqa: E402
from cap_types import (Facts, POSITIONAL_FLOOR, _aggregated_nodes, _all_args,  # noqa: E402,F401
                       _call_name, _contains_exit, _import_aliases, _len_arg,
                       _loop_depths, _message_context_nodes, _name_of, _negative_constant,
                       _references, _small_int, _walk_skipping_functions, expr_kind)

SANCTIONED_MODULES = {"capped_report"}

BOUND_EXEMPTIONS = {
    # LIVE sites in this repo. The first two are resource bounds whose function reports its
    # own total. The THIRD is different in kind and is labelled as such rather than filed
    # under the same sentence - it is this detector's own measured FALSE POSITIVE.
    ("numbers_match_on_write", "index_sources", "collection"):
        "MAX_SOURCE_VALUES - anti-balloon bound on the source index; the caller reports the "
        "real figure separately (finding M2)",
    ("numbers_match_on_write", "matches_source", "collection"):
        "MAX_FILE_BYTES - per-file read bound, not a truncation of anything reported",
    ("fast_test_on_stop", "_has_collectible_tests", "collection"):
        "CAP-FP-1, a MEASURED false positive of this detector, not a sanctioned truncation. "
        "The site bounds a COUNTER (`seen`) and the function returns a tri-state bool, never "
        "a collection - clause 1 excludes 'a counter' and clause 2 excludes 'a bool', so by "
        "this module's own stated rules it should never have been flagged. Reduced to a "
        "minimal fixture and probed with controls in both directions: the same shape flags, "
        "the same shape with the bound removed is clean, and a genuine offender still flags "
        "with a DIFFERENT message ('slices to a bound ... render()' vs 'stops the scan at a "
        "bound ... keep()'), so the detector was live and looking. Toggling clause2/clause3 "
        "changes nothing for this site, which locates the defect in the 'stops the scan' "
        "branch not applying clauses 1-3. Classified V1.4-BACKLOG by the repo's own R1/R2 "
        "rule: R1 holds via the weekly sweep, R2 does NOT, because reaching it requires "
        "editing unbluff's own source - so it is developer-facing, not a criterion-3 "
        "user-facing false alarm. This entry is liveness-audited, so it reports itself as "
        "DEAD the moment the detector is fixed.",
}

# CORPUS fixtures, kept in a SEPARATE roster from the live one on purpose.
#
# tests/cap_spelling_corpus.py plants modules named numbers_match_on_write.py precisely to
# exercise this roster: two of its negative controls are structurally IDENTICAL to must-flag
# entries, so no structural rule can ever separate them and the roster stays load-bearing.
# They are named here, with the reason, rather than smuggled in as a name exception.
#
# They are held apart because exemption_problems() audits liveness against a real directory,
# and a fixture module is never IN one - lumping them together would report both as dead on
# every run, which is how a liveness check becomes noise and then gets deleted. These are
# audited by selftest(), which plants them.
FIXTURE_EXEMPTIONS = {
    ("numbers_match_on_write", "scan", "collection"):
        "corpus fixture neg_bound_exemption_collection - identical in shape to a true "
        "positive, separable only by roster",
    ("numbers_match_on_write", "run", "collection"):
        "corpus fixture neg_collection_cap_in_the_approved_function - same",
}

ALL_EXEMPTIONS = dict(BOUND_EXEMPTIONS)
ALL_EXEMPTIONS.update(FIXTURE_EXEMPTIONS)

_ITERTOOLS_SHORTENERS = {"islice", "takewhile"}
_HEAPQ_SHORTENERS = {"nlargest", "nsmallest"}


def _is_call_to(node, names, aliases):
    if not isinstance(node, ast.Call):
        return None
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr in names:
        return fn.attr
    if isinstance(fn, ast.Name):
        target = aliases.get(fn.id, fn.id)
        if target in names:
            return target
    return None

# ----------------------------------------------------------------------------------
# the shapes
# ----------------------------------------------------------------------------------

class Site(object):
    def __init__(self, kind, target, lineno, why, expr=None):
        self.kind = kind          # 'display' | 'collection'
        self.target = target      # the shortened NAME, or None when there is no bare name
        self.lineno = lineno
        self.why = why
        self.expr = expr          # the shortened EXPRESSION, for clause 1


def _structural_split_names(scope):
    """Names sliced BOTH [:k] and [k:] - a head/tail split loses nothing."""
    heads, tails = {}, {}
    for node in _walk_skipping_functions(scope):
        if not (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice)):
            continue
        name = _name_of(node.value)
        if name is None:
            continue
        sl = node.slice
        if sl.upper is not None and sl.lower is None:
            heads.setdefault(name, []).append(ast.dump(sl.upper))
        elif sl.lower is not None and sl.upper is None:
            tails.setdefault(name, []).append(ast.dump(sl.lower))
    return {n for n in heads if set(heads[n]) & set(tails.get(n, []))}


def _slice_sites(scope, aliases, facts, in_message):
    sites = []
    splits = _structural_split_names(scope)
    for node in _walk_skipping_functions(scope):
        if id(node) in in_message:
            continue
        if isinstance(node, ast.Delete):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Subscript) and isinstance(tgt.slice, ast.Slice)
                        and tgt.slice.lower is not None and tgt.slice.upper is None
                        and not _negative_constant(tgt.slice.lower)):
                    sites.append(Site("display", _name_of(tgt.value), node.lineno,
                                      "deletes the tail past a bound"))
            continue
        if not (isinstance(node, ast.Subscript)):
            continue
        target = _name_of(node.value)
        if target is not None and target in splits:
            continue
        sl = node.slice
        if isinstance(sl, ast.Slice):
            if sl.upper is not None and sl.lower is None:
                # xs[:-1] removes ONE element - a shrink step, not a cap to N
                if _negative_constant(sl.upper) or _small_int(sl.upper):
                    continue
                sites.append(Site("display", target, node.lineno, "slices to a bound",
                                  node.value))
            elif (sl.upper is None and _negative_constant(sl.lower)
                  and not _small_int(sl.lower.operand)):
                # a tail slice on a collection appended to OUTSIDE a loop is a retention
                # window the caller still owns, not a truncation of an accumulation
                if target in facts.appends_outside_loop and target not in facts.appends_in_loop:
                    continue
                sites.append(Site("display", target, node.lineno, "keeps only a tail",
                                  node.value))
        else:
            inner = sl.value if isinstance(sl, ast.Index) else sl
            if _is_call_to(inner, {"slice"}, aliases):
                sites.append(Site("display", target, node.lineno, "slices via slice()",
                                  node.value))
    return sites


def _kw(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _callee_sites(scope, aliases):
    sites = []
    for node in _walk_skipping_functions(scope):
        hit = _is_call_to(node, _ITERTOOLS_SHORTENERS, aliases)
        if hit and node.args:
            arg = node.args[-1] if hit == "takewhile" else node.args[0]
            sites.append(Site("display", _name_of(arg), node.lineno,
                              "shortens via %s" % hit, arg))
            continue
        hit = _is_call_to(node, _HEAPQ_SHORTENERS, aliases)
        if hit:
            arg = node.args[1] if len(node.args) > 1 else _kw(node, "iterable")
            sites.append(Site("display", _name_of(arg) if arg is not None else None,
                              node.lineno, "keeps only the top N via %s" % hit, arg))
            continue
        if _is_call_to(node, {"deque"}, aliases) and _kw(node, "maxlen") is not None:
            arg = node.args[0] if node.args else None
            sites.append(Site("display", _name_of(arg) if arg is not None else None,
                              node.lineno, "bounds the sequence with deque(maxlen=)", arg))
    return sites


def _enumerate_arg(node):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "enumerate" and node.args):
        return node.args[0]
    return None


def _zip_range_target(node, aliases):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and aliases.get(node.func.id, node.func.id) == "zip"):
        return None, False
    ranges = [a for a in node.args
              if isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
              and a.func.id == "range"]
    others = [a for a in node.args if a not in ranges]
    if ranges and others:
        return _name_of(others[0]), True
    return None, False


def _bounds_index(cond, idx):
    for node in ast.walk(cond):
        if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                and node.left.id == idx and node.ops
                and isinstance(node.ops[0], (ast.Lt, ast.LtE))):
            return not _small_int(node.comparators[0]) if node.comparators else True
    return False


def _comprehension_sites(scope, aliases):
    sites = []
    for node in _walk_skipping_functions(scope):
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            for gen in node.generators:
                tgt, ok = _zip_range_target(gen.iter, aliases)
                if ok:
                    sites.append(Site("display", tgt, node.lineno,
                                      "cuts the sequence with zip(range(...))", gen.iter))
                    continue
                inner = _enumerate_arg(gen.iter)
                if inner is None:
                    continue
                t = gen.target
                idx = (t.elts[0].id if isinstance(t, ast.Tuple) and t.elts
                       and isinstance(t.elts[0], ast.Name) else None)
                if idx is None:
                    continue
                for cond in gen.ifs:
                    if _bounds_index(cond, idx):
                        sites.append(Site("display", _name_of(inner), node.lineno,
                                          "drops everything past an index bound", inner))
                        break
        elif isinstance(node, ast.Call):
            tgt, ok = _zip_range_target(node, aliases)
            if ok:
                sites.append(Site("display", tgt, node.lineno,
                                  "cuts the sequence with zip(range(...))", node.args[0]))
    return sites

def _size_test_target(test, loop_vars, allow_item=False):
    """A comparison against len(x) -> x, or None when the comparison is not a cap.

    Three exclusions, every one of them measured against the LIVE hooks rather than reasoned:

      * an INDEX BOUNDS CHECK - `i + 1 < len(toks)`, `0 <= i < len(values)`. The collection's
        own length is the limit on an index, not a cap on the collection. The corpus has this
        shape only OUTSIDE a loop (neg_int_index_bounds_check), so it read as covered while
        two live sites went on tripping it.
      * a bound below the POSITIONAL FLOOR - `len(entries) < 2` is an arity check.
      * `len(loop_var)` - a property of the ITEM. Kept only when `allow_item`, because the
        corpus insists `if len(line) > MAX_LEN: continue` DOES silently drop reported rows.
    """
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        len_names, others = [], []
        for side in [node.left] + list(node.comparators):
            probe = side.value if isinstance(side, ast.NamedExpr) else side
            arg = _len_arg(probe)
            if arg is not None:
                len_names.append(_name_of(arg))
            else:
                others.append(probe)
        if not len_names or len_names[0] is None:
            continue
        if any(_references(o, loop_vars) for o in others):
            continue
        if others and all(_small_int(o) for o in others):
            continue
        name = len_names[0]
        if name in loop_vars:
            if allow_item:
                return name
            continue
        return name
    return None


def _pads_with_constants(loop, target):
    """`while len(bits) < 6: bits.append("")` GROWS a list to a minimum - nothing is dropped.

    Structurally identical to the corpus's while_test_cap (`out.append(next(it))`) except in
    what is appended: a constant has no source that could be truncated. Found live in
    duplicate_registration_check._parts.
    """
    appends = [c for c in _walk_skipping_functions(loop)
               if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
               and c.func.attr in ("append", "extend", "insert")
               and _name_of(c.func.value) == target]
    return bool(appends) and all(all(isinstance(a, ast.Constant) for a in c.args)
                                 for c in appends)


def _counter_test(test, scope, loop_vars):
    counters = set(loop_vars)
    for node in _walk_skipping_functions(scope):
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            counters.add(node.target.id)
    for node in ast.walk(test):
        if not (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
                and node.left.id in counters and node.ops):
            continue
        # ORDER comparisons only. `t == "-m"` matches a loop variable against a literal - it
        # is a search test, not a bound, and reading it as one produced the single live false
        # positive left after the other five rules (duplicate_registration_check._invocation_
        # key, a loop that BREAKS on finding the script token and truncates nothing).
        if not isinstance(node.ops[0], (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
            continue
        return not any(_small_int(c) for c in node.comparators)
    return False


def _loop_var_names(node):
    out = set()
    tgt = getattr(node, "target", None)
    if tgt is not None:
        for sub in ast.walk(tgt):
            if isinstance(sub, ast.Name):
                out.add(sub.id)
    return out


def _loop_exit_sites(scope, facts):
    sites = []
    for node in _walk_skipping_functions(scope):
        if isinstance(node, ast.While):
            target = _size_test_target(node.test, set())
            # a while-size loop that REBINDS rather than mutates is a scalar shrink
            # (`while len(text) > N: text = text[:-1]`), not a collection cap
            if (target is not None and target in facts.mutated
                    and not _pads_with_constants(node, target)):
                sites.append(Site("collection", target, node.lineno,
                                  "loops until the collection is under a bound"))
            continue
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        loop_vars = _loop_var_names(node)
        iterated = _name_of(node.iter)
        if iterated is None:
            inner = _enumerate_arg(node.iter)
            iterated = _name_of(inner) if inner is not None else None
        for sub in _walk_skipping_functions(node):
            if not isinstance(sub, ast.If) or not _contains_exit(sub):
                continue
            target = _size_test_target(sub.test, loop_vars, allow_item=True)
            if target is None:
                if not _counter_test(sub.test, scope, loop_vars):
                    continue
                target = iterated
            sites.append(Site("collection", target, sub.lineno,
                              "stops the scan at a bound, destroying the real total"))
    return sites

# ----------------------------------------------------------------------------------
# per-module assembly
# ----------------------------------------------------------------------------------

def _function_scopes(tree):
    """Every def, PLUS the module body itself.

    The module body is not decoration. The predecessor walks the whole AST and has no notion
    of a function, so it flags `SHOWN = items[:MAX_FOO]` at module level; a successor that
    only ever looks inside defs LOSES that capability, and no corpus entry covers it - every
    one of the 125 wraps its cap in a function. That is exactly the predecessor-derived gap
    the plan says is still owed, found by asking what the OLD guard could do rather than by
    reading the corpus the NEW design wrote.
    """
    out = [("<module>", tree)]

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = (prefix + "." + child.name) if prefix else child.name
                out.append((qual, child))
                walk(child, qual)
            elif isinstance(child, ast.ClassDef):
                qual = (prefix + "." + child.name) if prefix else child.name
                walk(child, qual)
            else:
                walk(child, prefix)

    walk(tree, "")
    return out


def _routed(scope, aliases):
    for node in _walk_skipping_functions(scope):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr in ("keep", "render"):
                return True
            if isinstance(fn, ast.Name) and aliases.get(fn.id, fn.id) in ("keep", "render"):
                return True
    return False


def _raises_on_the_bound_path(scope):
    """Clause 4: a raise keyed to a size test is LOUD, and loud is fine."""
    for node in _walk_skipping_functions(scope):
        if not isinstance(node, ast.If):
            continue
        if _size_test_target(node.test, set()) is None:
            continue
        for sub in _walk_skipping_functions(node):
            if isinstance(sub, ast.Raise):
                return True
    return False


def _module_sites(module, tree, clause1, clause2, clause3, use_roster=True, keys=None):
    """Messages for one module. `keys` collects every (module, qual, kind) that reached the
    roster check, which is what makes the exemption LIVENESS audit possible."""
    aliases = _import_aliases(tree)
    problems = []
    for qual, scope in _function_scopes(tree):
        if _routed(scope, aliases) or _raises_on_the_bound_path(scope):
            continue
        facts = Facts(scope)
        in_message = _message_context_nodes(scope)
        aggregated = _aggregated_nodes(scope)
        sites = (_slice_sites(scope, aliases, facts, in_message)
                 + _callee_sites(scope, aliases)
                 + _comprehension_sites(scope, aliases) + _loop_exit_sites(scope, facts))
        for site in sites:
            key = (module, qual, site.kind)
            if keys is not None:
                keys.add(key)
            if use_roster and key in ALL_EXEMPTIONS:
                continue
            # clause 2 - a DISPLAY cap on a value that never leaves as a list hides nothing.
            # Never applied to collection caps: a break destroys the total for the caller too.
            if (clause2 and site.kind == "display" and site.expr is not None
                    and id(site.expr) in aggregated):
                continue
            if clause1:
                kind = (expr_kind(site.expr, facts) if site.expr is not None
                        else facts.kind(site.target))
                if kind == "scalar":
                    continue
            if clause3 and facts.io_derived(site.target):
                continue
            where = "module level" if qual == "<module>" else "%s()" % qual
            problems.append(
                "%s: %s %s at line %d - route it through capped_report.%s() so the "
                "message names what it hid"
                % (module, where, site.why, site.lineno,
                   "render" if site.kind == "display" else "keep"))
    return problems


def slicing_offenders(hooks_dir, clause1=True, clause2=True, clause3=True,
                      use_roster=True, keys=None):
    offenders = []
    for path in sorted(glob.glob(os.path.join(glob.escape(hooks_dir), "*.py"))):
        module = os.path.splitext(os.path.basename(path))[0]
        if module in SANCTIONED_MODULES:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            offenders.append("%s: UNREADABLE (%s) - nothing in it was checked" % (module, exc))
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            offenders.append("%s: does not parse (%s) - a file this guard cannot read is "
                             "REPORTED, never silently skipped" % (module, exc.msg))
            continue
        offenders.extend(_module_sites(module, tree, clause1, clause2, clause3,
                                       use_roster, keys))
    return sorted(set(offenders))


def exemption_problems(hooks_dir, roster=None):
    """Roster entries that are no longer NEEDED - the liveness half, in both directions.

    B3's lesson, and the plan states it as owed for this roster specifically: an exemption
    roster that is never pruned rots into pre-authorisation for whatever gets added next. So
    the roster is audited by REMOVING it and asking which of its entries the detector would
    actually have flagged. An entry nothing would flag is dead weight and is REPORTED.

    transcript_util's used-check is the model. The direction matters: this cannot fail open,
    because an entry that IS still needed simply does not appear here.

    Only BOUND_EXEMPTIONS is audited against a real directory. FIXTURE_EXEMPTIONS exist for
    corpus modules that are planted, never present in a live tree, so auditing them here
    would report them dead every run - they are audited by selftest(), which plants them.
    """
    roster = BOUND_EXEMPTIONS if roster is None else roster
    seen = set()
    slicing_offenders(hooks_dir, use_roster=False, keys=seen)
    problems = []
    for key in sorted(roster):
        if key not in seen:
            problems.append(
                "DEAD EXEMPTION %s / %s / %s - nothing at that site would be flagged even "
                "without it, so it is now cover rather than a decision. Prune it. (reason on "
                "record: %s)" % (key[0], key[1], key[2], roster[key]))
    return problems


def verdict(offenders, dead_exemptions):
    """(ok, lines) - the DECISION, pure so every branch can be asserted.

    Extracted for the reason MR-a recorded: the anchor gate could be fully disarmed with
    every test green, because every test exercised the audit and nothing exercised the
    decision. `if problems:` -> `if False:` is a one-token disarm, and only a pure verdict
    with all branches asserted catches it.
    """
    lines = list(offenders) + list(dead_exemptions)
    return (not lines), lines


# ----------------------------------------------------------------------------------
# selftest - PLANTED fixtures, one per shape, plus the negative control for each rule
# ----------------------------------------------------------------------------------

_SHOULD_FLAG = (
    ("head slice", "MAX_B = 12\ndef r(xs):\n    return xs[:MAX_B]\n"),
    ("tail slice on an accumulator",
     "MAX_B = 12\ndef r(xs):\n    out = []\n    for x in xs:\n        out.append(x)\n"
     "    return out[-MAX_B:]\n"),
    ("del tail", "def r(xs):\n    out = list(xs)\n    del out[12:]\n    return out\n"),
    ("islice", "import itertools\ndef r(xs):\n    return list(itertools.islice(xs, 12))\n"),
    ("takewhile", "import itertools\ndef r(xs):\n"
                  "    return list(itertools.takewhile(lambda p: p[0] < 10, enumerate(xs)))\n"),
    ("heapq.nlargest", "import heapq\ndef r(xs):\n    return heapq.nlargest(12, xs)\n"),
    ("deque(maxlen=)", "import collections\ndef r(xs):\n"
                       "    return collections.deque(xs, maxlen=12)\n"),
    ("comprehension index guard",
     "def r(xs):\n    return [x for i, x in enumerate(xs) if i < 12]\n"),
    ("zip(range(n))", "def r(xs):\n    return [x for _, x in zip(range(10), xs)]\n"),
    ("break out of an accumulation loop",
     "def r(xs):\n    out = []\n    for x in xs:\n        if len(out) >= 10:\n"
     "            break\n        out.append(x)\n    return out\n"),
    ("while-size accumulation",
     "def r(it):\n    out = []\n    while len(out) < 10:\n        out.append(next(it))\n"
     "    return out\n"),
    ("module level, outside any def",
     "MAX_B = 12\nROWS = list(range(50))\nSHOWN = ROWS[:MAX_B]\n"),
    # acceptance criterion 2. Every other fixture and every corpus entry renames a callee by
    # IMPORT, so the import path was covered and this one was blind - with the corpus score
    # unmoved, because a corpus cannot see a shape it has no entry for.
    ("callee renamed by ASSIGNMENT",
     "import itertools\ntake = itertools.islice\ndef r(xs):\n    return list(take(xs, 12))\n"),
    ("callee renamed through an assignment CHAIN",
     "import itertools\na = itertools.islice\nb = a\ndef r(xs):\n    return list(b(xs, 12))\n"),
    ("a file that does not parse", "MAX_B = 12\ndef r(xs)\n    return xs[:MAX_B]\n"),
)

_SHOULD_STAY_QUIET = (
    ("routed through render", "import capped_report\nMAX_B = 12\ndef r(xs):\n"
                              "    return capped_report.render(xs, MAX_B)\n"),
    ("loud rejection", "MAX_R = 5\ndef r(rows):\n    if len(rows) > MAX_R:\n"
                       "        raise ValueError('too many')\n    return rows\n"),
    ("message truncation via %",
     "def r(fails, msg):\n    fails.append('bad: %r' % (msg[:120],))\n    return fails\n"),
    ("message truncation via chained concatenation",
     "def r(fails, msg, out):\n    fails.append(msg + ' || got: ' + out[:200])\n"
     "    return fails\n"),
    ("index bounds check inside a loop",
     "def r(toks):\n    for i, t in enumerate(toks):\n"
     "        if i + 1 < len(toks):\n            return t\n    return None\n"),
    ("search break on a string equality",
     "def r(toks):\n    for i, t in enumerate(toks):\n        if t == '-m':\n"
     "            return i\n    return None\n"),
    ("padding a list up to a minimum",
     "def r(entry):\n    bits = entry.split('|')\n    while len(bits) < 6:\n"
     "        bits.append('')\n    return bits\n"),
    ("arity filter below the positional floor",
     "def r(rows):\n    out = []\n    for entry in rows:\n        if len(entry) < 4:\n"
     "            continue\n        out.append(entry)\n    return out\n"),
    ("positional head", "def r(entry):\n    return entry[:2], entry[2:]\n"),
    ("scalar read", "def r(fh):\n    text = fh.read()\n    return text[:200000]\n"),
    ("hash prefix", "import hashlib\ndef r(b):\n"
                    "    return hashlib.sha256(b).hexdigest()[:12]\n"),
    ("scalar shrink loop", "def r(text):\n    while len(text) > 100:\n"
                           "        text = text[:-1]\n    return text\n"),
    ("aggregated, never reported",
     "import re\nRE = re.compile('x')\ndef r(text):\n"
     "    return any(RE.match(ln) for ln in text.splitlines()[:5])\n"),
    ("read window this function performed itself",
     "def r(path, n=120):\n    with open(path, 'rb') as h:\n        data = h.read()\n"
     "    lines = data.decode('utf-8', 'replace').splitlines()\n    return lines[-n:]\n"),
    # the other half of acceptance criterion 2: resolving assignments must not INVENT a
    # shortener out of an unrelated rename, and a self-referential assignment must terminate
    ("an unrelated assignment rename",
     "import os\np = os.path\ndef r(xs):\n    return p.join(*xs)\n"),
    ("a self-referential assignment",
     "def r(xs):\n    a = a\n    return list(xs)\n"),
)


def _plant(tmp, source, name="planted.py"):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(source)
    return path


def selftest() -> int:
    import shutil
    import tempfile

    fails = []
    td = tempfile.mkdtemp(prefix="capshapes_")
    try:
        # Every shape must be SEEN. A structural guard that matches nothing is
        # indistinguishable from a clean sweep, which is the failure this module is about.
        for label, source in _SHOULD_FLAG:
            d = tempfile.mkdtemp(dir=td)
            _plant(d, source)
            if not slicing_offenders(d):
                fails.append("blind to a planted %s - the guard would report any repo clean"
                             % label)
        # ...and every rule that suppresses one must have its own control, or the rule is
        # untested and the next edit can delete it silently.
        for label, source in _SHOULD_STAY_QUIET:
            d = tempfile.mkdtemp(dir=td)
            _plant(d, source)
            got = slicing_offenders(d)
            if got:
                fails.append("FALSE POSITIVE on %s: %s" % (label, got[0][:150]))

        # An UNREADABLE file is reported, never skipped. Exercised by pointing the sweep at
        # a path that exists in the glob and cannot be opened - a directory named *.py.
        d = tempfile.mkdtemp(dir=td)
        os.makedirs(os.path.join(d, "notafile.py"))
        if not any("UNREADABLE" in o for o in slicing_offenders(d)):
            fails.append("an unreadable .py was silently skipped - fail-open is the premise "
                         "this rebuild replaces")

        # DECISION path, both directions. Not the detector - the thing that turns findings
        # into a pass or a fail (MR-a: a gate was fully disarmable with every test green).
        ok, lines = verdict([], [])
        if not ok or lines:
            fails.append("verdict() on a clean sweep must be ok with no lines, got %r"
                         % (lines,))
        ok, lines = verdict(["an offender"], [])
        if ok or lines != ["an offender"]:
            fails.append("verdict() must FAIL on an offender, got ok=%r" % (ok,))
        ok, lines = verdict([], ["a dead exemption"])
        if ok or lines != ["a dead exemption"]:
            fails.append("verdict() must FAIL on a dead exemption alone - an unpruned roster "
                         "is a finding in its own right, got ok=%r" % (ok,))
        ok, lines = verdict(["a"], ["b"])
        if ok or lines != ["a", "b"]:
            fails.append("verdict() must report BOTH kinds, got %r" % (lines,))

        # EXEMPTION LIVENESS, both directions.
        d = tempfile.mkdtemp(dir=td)
        _plant(d, "MAX_F = 200\ndef scan(xs):\n    out = []\n    for x in xs:\n"
                  "        if len(out) >= MAX_F:\n            break\n        out.append(x)\n"
                  "    return out\n", "numbers_match_on_write.py")
        if slicing_offenders(d):
            fails.append("the fixture exemption did not suppress its own site")
        # EVERY COMPONENT OF THE EXEMPTION KEY MUST BE LOAD-BEARING.
        # p14_new_code_review.md reserved a mutation for exactly this against the OLD
        # (module, constant) key: a two-line widening of the membership test blinded the
        # guard to real offenders while capped_report --selftest, the whole suite and all
        # three capped_report mutations stayed green, "because nothing anywhere pins the
        # (module, constant) pair". The key is now a TRIPLE, so there are three ways to widen
        # it and each needs its own control.
        exempt_mod = os.path.join(d, "numbers_match_on_write.py")
        with open(exempt_mod, "a", encoding="utf-8") as fh:
            fh.write("\n\ndef build_message(rows):\n    return rows[:200]\n")
        got = slicing_offenders(d)
        if not any("build_message" in o for o in got):
            fails.append("QUALNAME is not load-bearing: a DIFFERENT function in an exempted "
                         "module inherited the exemption, so widening the key to the module "
                         "would blind the guard with every test green")
        with open(exempt_mod, "a", encoding="utf-8") as fh:
            fh.write("\n\ndef scan_and_slice(xs):\n    out = []\n    for x in xs:\n"
                     "        if len(out) >= 200:\n            break\n        out.append(x)\n"
                     "    return out[:200]\n")
        got = slicing_offenders(d)
        if not any("scan_and_slice" in o and "render" in o for o in got):
            fails.append("KIND is not load-bearing: a DISPLAY cap was suppressed by a "
                         "COLLECTION exemption, which is the (module, constant) defect the "
                         "triple key replaced")
        d2 = tempfile.mkdtemp(dir=td)
        _plant(d2, "def scan(xs):\n    out = []\n    for x in xs:\n"
                   "        if len(out) >= 200:\n            break\n        out.append(x)\n"
                   "    return out\n", "other_module.py")
        if not slicing_offenders(d2):
            fails.append("MODULE is not load-bearing: the same qualname and kind in a "
                         "DIFFERENT module inherited the exemption")

        live = exemption_problems(d, FIXTURE_EXEMPTIONS)
        if any("/ scan /" in p for p in live):
            fails.append("a NEEDED exemption was reported dead - the liveness check would "
                         "nag on a correct roster, and a guard that nags gets disabled")
        if not any("/ run /" in p for p in live):
            fails.append("a DEAD exemption was NOT reported - the roster can rot into cover "
                         "for whatever is added next, which is B3's recorded lesson")

        # The live roster must be live. This is the assertion that goes red the day one of
        # the two real sites is fixed or moves, rather than the exemption quietly outliving
        # its reason.
        here = os.path.dirname(os.path.abspath(__file__))
        for problem in exemption_problems(here):
            fails.append(problem)

        print("-- cap-shapes: %d shape fixture(s), %d negative control(s), %d live "
              "exemption(s), %d fixture exemption(s)"
              % (len(_SHOULD_FLAG), len(_SHOULD_STAY_QUIET), len(BOUND_EXEMPTIONS),
                 len(FIXTURE_EXEMPTIONS)))
    finally:
        shutil.rmtree(td, ignore_errors=True)

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
