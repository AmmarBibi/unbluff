#!/usr/bin/env python3
"""Every selftest that MUTATES git must be isolated, and the isolation must be REACHED.

WHY THIS IS A GATE (#46 item 4, 2026-08-25). Two mechanisms already exist in git_isolation.py -
`scrub_environ()` prevents, `fingerprint()` detects - and both were wired by hand, at the top of
a `main()`, guarded by nothing. Move that call into a helper nobody calls and all 41 gates stay
green while the protection is gone. That is an unenforced assertion protecting the fix for an
unenforced assertion, which is #47's shape one level down.

Three questions, each with its own denominator printed:

  1. POPULATION - which files run a MUTATING git verb from a --selftest path? Derived by AST from
     the source, never a hand-kept list. A list would rot the first time a fixture moves.
  2. REACHABILITY - is the scrub reached before those fixtures can run? Module-level or the first
     statement of the dispatch. A call sitting inside an uncalled helper does NOT count.
  3. DRIFT - the inline fallback lists (for a checkout with no tools/) must name EXACTLY
     git_isolation.GIT_REDIRECT_VARS. A fallback that scrubs six of seven variables is worse than
     none: it looks like protection and leaks the seventh.

STRUCTURAL, NOT TEXTUAL, and deliberately so. `unrecorded_tiers` was two substring tests until a
full sweep caught SITES-1 SURVIVED - a DOCSTRING satisfied one of them while the real call had
been renamed. This file's own source contains every needle it looks for: the literal
"scrub_environ", the verb "commit", and the whole GIT_REDIRECT_VARS tuple. A grep guard here
would pass by reading itself. An AST walk cannot be satisfied by a comment, a docstring, or a
dict key.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS = os.path.join(REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

from git_isolation import GIT_REDIRECT_VARS  # noqa: E402  (path set above)

# git verbs that WRITE. Read-only verbs (status, rev-parse, log, hash-object) are deliberately
# absent: fast_test_on_stop.py runs git and is read-only, so including them would put a file in
# the population that cannot corrupt anything - and a gate that demands work with no failure
# behind it is how gates get switched off.
MUTATING_VERBS = frozenset({
    "init", "commit", "checkout", "switch", "branch", "reset", "clone", "worktree",
    "config", "push", "merge", "update-ref", "am", "cherry-pick", "rebase", "tag",
})

# Matched by SHAPE, not by an exact roster. The first version was a frozenset of three exact
# names and it missed `_scrub_environ` - the alias its own companion script had just inserted
# into four files - so the gate reported four correctly-scrubbed files as UNISOLATED. A hardcoded
# name roster is the twin of the hardcoded file roster this gate exists to replace.
def _is_scrub_name(name: str) -> bool:
    return "scrub" in name.lower() or name == "_isolate_selftest"


def _py_files(root: str) -> list:
    out = []
    for sub in ("hooks", "tools"):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.endswith(".py"):
                out.append(os.path.join(d, name))
    return out


def _parse(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read()), None
    except (OSError, SyntaxError) as exc:      # fails CLOSED - unreadable is not clean
        return None, str(exc)


def mutating_verbs_in(tree) -> set:
    """Verb strings passed as ARGUMENTS to a call. Structural: a docstring cannot match."""
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        args = list(node.args)
        for kw in node.keywords:
            args.append(kw.value)
        flat = []
        for a in args:
            if isinstance(a, (ast.List, ast.Tuple)):
                flat.extend(a.elts)
            else:
                flat.append(a)
        for a in flat:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                if a.value in MUTATING_VERBS:
                    found.add(a.value)
    return found


def _is_scrub_call(node) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    if isinstance(f, ast.Name):
        return _is_scrub_name(f.id)
    if isinstance(f, ast.Attribute):
        return _is_scrub_name(f.attr)
    return False


def _pops_redirect_vars(node) -> set:
    """The inline fallback shape: `for _v in (...): os.environ.pop(_v)`. Returns the names."""
    names = set()
    if not isinstance(node, ast.For):
        return names
    it = node.iter
    if isinstance(it, (ast.Tuple, ast.List)):
        for e in it.elts:
            if isinstance(e, ast.Constant) and isinstance(e.value, str):
                names.add(e.value)
    if not names:
        return names
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr == "pop":
            return names
    return set()


def _scrub_reached(tree) -> tuple:
    """(reached, where). Only statements that RUN count - module level, or a Try at module level.

    A call inside a FunctionDef counts ONLY if that function is itself invoked at module level or
    from the __main__ dispatch, which is checked separately. This is the half item 4 named: the
    call must not be parkable inside an orphan helper.
    """
    fallback_names = set()

    def scan(body, where):
        for st in body:
            if isinstance(st, ast.Expr) and _is_scrub_call(st.value):
                return True, where
            if isinstance(st, ast.Try):
                ok, w = scan(st.body, where + "/try")
                for h in st.handlers:
                    for hs in ast.walk(h):
                        fallback_names.update(_pops_redirect_vars(hs))
                if ok:
                    return True, w
            if isinstance(st, ast.If):
                ok, w = scan(st.body, where + "/if")
                if ok:
                    return True, w
            for sub in ast.walk(st) if isinstance(st, ast.For) else ():
                fallback_names.update(_pops_redirect_vars(sub))
            if isinstance(st, ast.For):
                got = _pops_redirect_vars(st)
                if got:
                    fallback_names.update(got)
                    return True, where + "/inline-fallback"
        return False, ""

    reached, where = scan(tree.body, "module")
    return reached, where, fallback_names


def _dispatch_calls_scrub(tree) -> bool:
    """`if __name__ == "__main__":` block calls a scrub before dispatching."""
    for st in tree.body:
        if not isinstance(st, ast.If):
            continue
        src = ast.dump(st.test)
        if "__main__" not in src and "__name__" not in src:
            continue
        for sub in ast.walk(st):
            if _is_scrub_call(sub):
                return True
    return False


def _imported_modules(tree) -> set:
    """Bare module names this file imports, from either import form."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def audit(root: str = REPO) -> dict:
    res = {"examined": 0, "population": [], "unisolated": [], "drift": [], "unreadable": [],
           "orchestrator": None, "_scrubbed": set(), "_deferred": [], "delegated": []}
    for path in _py_files(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        tree, err = _parse(path)
        if tree is None:
            res["unreadable"].append((rel, err))
            continue
        res["examined"] += 1
        verbs = mutating_verbs_in(tree)
        src_has_selftest = "--selftest" in open(path, encoding="utf-8").read()
        if not verbs or not src_has_selftest:
            continue
        if rel == "tools/git_isolation.py":
            continue                       # the mechanism itself; its own --selftest covers it
        res["population"].append((rel, sorted(verbs)))
        reached, where, fb = _scrub_reached(tree)
        if not reached:
            reached = _dispatch_calls_scrub(tree)
        if not reached:
            # DELEGATION. A file whose --selftest hands off to a sibling module is covered when
            # that sibling scrubs at import - the import IS the call. Without this rule the gate
            # flags pre_push_gate.py, whose only mutating verb is production `config --global`
            # in install_global() and whose --selftest does `import pre_push_gate_selftest`,
            # which scrubs on line 22. Firing there would be firing on correct work, and this
            # gate exists to stop exactly that class.
            res["_deferred"].append((rel, _imported_modules(tree)))
            continue
        res["_scrubbed"].add(rel)
        if fb and set(fb) != set(GIT_REDIRECT_VARS):
            missing = sorted(set(GIT_REDIRECT_VARS) - set(fb))
            extra = sorted(set(fb) - set(GIT_REDIRECT_VARS))
            res["drift"].append((rel, missing, extra))

    # Resolve delegation once every file's own status is known - order-independent by
    # construction, so it cannot depend on which file the directory walk reached first.
    scrubbed_mods = {os.path.basename(p)[:-3] for p in res["_scrubbed"]}
    for rel, imports in res["_deferred"]:
        via = sorted(imports & scrubbed_mods)
        if via:
            res["delegated"].append((rel, via[0]))
        else:
            res["unisolated"].append(rel)

    # Item 4 proper: the orchestrator's own call must sit in main()'s DIRECT body.
    rs = os.path.join(root, "run_selftests.py")
    tree, err = _parse(rs)
    if tree is None:
        res["orchestrator"] = ("unreadable", err)
    else:
        found = False
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "main":
                for st in node.body:
                    if isinstance(st, ast.Assign) and _is_scrub_call(st.value):
                        found = True
                    if isinstance(st, ast.Expr) and _is_scrub_call(st.value):
                        found = True
        res["orchestrator"] = ("ok" if found else "MISSING", None)
    return res


def selftest() -> int:
    """Negative controls FIRST: a gate that cannot fail is not a gate."""
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as td:
        for sub in ("hooks", "tools"):
            os.makedirs(os.path.join(td, sub))
        # git_isolation stub so the import inside audit() is not needed - audit reads OUR module.
        bad = os.path.join(td, "hooks", "bad_hook.py")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write('import subprocess\n'
                     'def selftest():\n'
                     '    subprocess.run(["git", "-C", "/tmp/x", "commit", "-m", "x"])\n'
                     'if "--selftest" in []:\n    pass\n')
        r = audit(td)
        if "hooks/bad_hook.py" not in [p for p, _v in r["population"]]:
            fails.append("a file running `git commit` from a --selftest path was NOT put in the "
                         "population: %r - the gate cannot see its own subject" % (r["population"],))
        if "hooks/bad_hook.py" not in r["unisolated"]:
            fails.append("an UNSCRUBBED mutating selftest was not flagged: %r" % (r["unisolated"],))

        # CONTROL: the same file WITH a module-level scrub must NOT be flagged.
        good = os.path.join(td, "hooks", "good_hook.py")
        with open(good, "w", encoding="utf-8") as fh:
            fh.write('import subprocess\n'
                     'from git_isolation import scrub_environ\n'
                     'scrub_environ()\n'
                     'def selftest():\n'
                     '    subprocess.run(["git", "-C", "/tmp/x", "commit", "-m", "x"])\n'
                     'if "--selftest" in []:\n    pass\n')
        r2 = audit(td)
        if "hooks/good_hook.py" in r2["unisolated"]:
            fails.append("a correctly scrubbed file was flagged as unisolated - a gate that "
                         "fires on correct work gets disabled")

        # CONTROL: read-only git must NOT enter the population.
        ro = os.path.join(td, "hooks", "ro_hook.py")
        with open(ro, "w", encoding="utf-8") as fh:
            fh.write('import subprocess\n'
                     'def selftest():\n'
                     '    subprocess.run(["git", "status", "--porcelain"])\n'
                     'if "--selftest" in []:\n    pass\n')
        r3 = audit(td)
        if "hooks/ro_hook.py" in [p for p, _v in r3["population"]]:
            fails.append("a READ-ONLY git caller entered the mutating population; the gate would "
                         "demand isolation with no failure behind it")

        # CONTROL: a drifted fallback list must be caught.
        dr = os.path.join(td, "hooks", "drift_hook.py")
        with open(dr, "w", encoding="utf-8") as fh:
            fh.write('import os, subprocess\n'
                     'try:\n'
                     '    from git_isolation import scrub_environ\n'
                     '    scrub_environ()\n'
                     'except ImportError:\n'
                     '    for _v in ("GIT_DIR", "GIT_WORK_TREE"):\n'
                     '        os.environ.pop(_v, None)\n'
                     'def selftest():\n'
                     '    subprocess.run(["git", "-C", "/tmp/x", "commit", "-m", "x"])\n'
                     'if "--selftest" in []:\n    pass\n')
        r4 = audit(td)
        if "hooks/drift_hook.py" not in [d[0] for d in r4["drift"]]:
            fails.append("a fallback naming 2 of the %d redirect vars was NOT flagged as drift - "
                         "a partial scrub looks like protection and leaks the rest"
                         % len(GIT_REDIRECT_VARS))

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    r = audit()
    print("=" * 74)
    print("SELFTEST ISOLATION - is every git-MUTATING selftest scrubbed, and is the scrub REACHED?")
    print("=" * 74)
    print("  python files examined            : %d" % r["examined"])
    print("  redirect vars in the canonical set: %d" % len(GIT_REDIRECT_VARS))
    print("  MUTATING selftest population     : %d" % len(r["population"]))
    for rel, verbs in r["population"]:
        mark = "UNISOLATED" if rel in r["unisolated"] else "scrubbed"
        print("      %-42s %-11s %s" % (rel, mark, " ".join(verbs)))
    print("  orchestrator scrub in main()     : %s" % r["orchestrator"][0])

    fails = []
    if not r["population"]:
        fails.append("the population is EMPTY. Either every fixture stopped mutating git, or the "
                     "detector broke. A zero denominator is not a pass.")
    for rel in r["unisolated"]:
        fails.append("%s runs a mutating git verb from a --selftest path with no scrub REACHED. "
                     "Under a git hook its fixtures operate on the real repository (#46)." % rel)
    for rel, missing, extra in r["drift"]:
        fails.append("%s's inline fallback drifted from GIT_REDIRECT_VARS - missing %s, extra %s. "
                     "A partial scrub looks like protection and leaks the rest." % (rel, missing, extra))
    if r["orchestrator"][0] != "ok":
        fails.append("run_selftests.main() no longer calls a scrub in its DIRECT body (%s). That "
                     "is item 4's exact case: moved into an uncalled helper, every gate stays "
                     "green and the protection is gone." % r["orchestrator"][0])
    for rel, err in r["unreadable"]:
        fails.append("%s could not be parsed (%s); unreadable is not clean" % (rel, err))

    if fails:
        print()
        for f in fails:
            print("FAIL: %s" % f)
        return 1
    print("\nOK: %d mutating selftest(s), all scrubbed; orchestrator wiring intact."
          % len(r["population"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
