"""A selftest that measures its own wall clock against the timeout that governs it.

THE DEFECT THIS PREVENTS, which really happened. hooks/fast_test_on_stop.py --selftest drifted
to 24.65s median against the 25s cap `hook_health_check` applies when it runs that same
selftest in its weekly sweep. Straddling the cap made it non-deterministic, so the sweep on
every installed machine intermittently reported a PASSING hook as "weekly selftest
ERRORED/timed out". Nothing detected it: the hook's own selftest printed SELFTEST OK,
run_selftests printed 22/22, and the only symptom was one integration scenario going red -
which was then misdiagnosed twice, because no artifact anywhere carried a DURATION.

The comment justifying the cap had even named the failure mode - "A cap a HEALTHY selftest
exceeds does not catch a broken hook, it manufactures 'ERRORED/timed out' for a passing one" -
and rested on a measurement that was two days stale. Prose cannot notice drift. This can.

THE ONE DECLARATION. SELFTEST_TIMEOUT_S lives HERE and nowhere else. hook_health_check imports
it and passes it as `timeout=` to the subprocess that kills a slow selftest, so the number a
hook budgets against IS the number that kills it. They cannot drift apart, because they are
one object.

The arrow points DOWN into a leaf that imports only stdlib - no cycle, exactly how
capped_report is already imported by six hooks including hook_health_check itself. And it
survives the installed layout: install.py never copies hooks/ (hooks are referenced in place
by absolute path), so a new hooks/*.py is present wherever the others are.

ENFORCED STRUCTURALLY, NOT BY DOCSTRING. redeclared_caps() AST-walks every hooks/*.py and
fails any module-level binding of a SELFTEST_TIMEOUT-ish name to a numeric literal;
governing_binding_ok() separately asserts hook_health_check's binding is still an attribute
read of this module. BOTH are needed - deleting the binding satisfies the first trivially.

AST rather than grep for the reason capped_report's guard is AST: a textual guard must contain
the pattern it forbids, and would then match itself.

FAIL CLOSED. A hook that cannot import this dies at import. A share outside (0,1] raises. There
is no env escape hatch and no default-on-error: an off switch is a fail-open wearing a
different hat.
"""

from __future__ import annotations

import ast
import glob
import os
import time

# The clock starts when the hook imports this, which every hook does at the top of its file.
# Measured under-estimate versus the subprocess wall the cap is really applied to: 0.05-0.11s,
# under 0.5% of the cap, against 50% headroom at the default share.
_T0 = time.time()

HERE = os.path.dirname(os.path.abspath(__file__))

# THE one declaration. hooks/hook_health_check.py reads this attribute; it does not restate
# the number. Changing it here changes both the budget and the kill.
SELFTEST_TIMEOUT_S = 25

# Half the cap by default. Measured 2026-08-02 across the selftestable hooks: the large
# majority finish at a few percent of the cap, so a CI runner several times slower than this
# machine still sits far below 50%. The hooks that need more carry a RECORDED share at their
# call site - N reviewed decisions with written reasons, which is the shape this repo settled
# on after a probe treated 6 false positives as disqualifying and bought an unbounded problem.
DEFAULT_SHARE = 0.5


def budget_s(share: float = DEFAULT_SHARE) -> float:
    """Seconds this selftest may take. Raises on a share outside (0, 1]."""
    if not isinstance(share, (int, float)) or not (0 < share <= 1):
        raise ValueError("share must be in (0, 1], got %r - a share above 1 would budget "
                         "MORE time than the cap that kills the process" % (share,))
    return SELFTEST_TIMEOUT_S * float(share)


def line(elapsed: float, share: float, name: str, over: bool) -> str:
    """One line, printed every run, pass or fail, naming both numbers and where they come from.

    A budget check that prints only on failure teaches nobody. Printing the measurement every
    time makes creep legible as a trend - 0.11s, then 6.45s, then 13.84s are all PASSING lines
    a reader can rank - instead of invisible until something snaps.
    """
    b = budget_s(share)
    pct = (100.0 * elapsed / b) if b else 0.0
    return ("[selftest-budget] %s %s %.2fs of %.2fs (share %.2f of the %ds cap "
            "hook_health_check applies per hook) - %d%% used"
            % ("OVER BUDGET" if over else "ok", name, elapsed, b, share,
               SELFTEST_TIMEOUT_S, round(pct)))


def report(share: float = DEFAULT_SHARE, name: str = "", t0: float = 0.0) -> list:
    """Print the budget line; return [] or [one problem string] to extend a hook's `fails`.

    Returning into the hook's existing fails list is deliberate: the problem then travels the
    SELFTEST FAIL: / nonzero-rc path every reader and every gate already follows, rather than
    needing a second channel nobody watches.
    """
    elapsed = time.time() - (t0 or _T0)
    over = elapsed > budget_s(share)
    print(line(elapsed, share, name or "selftest", over))
    if not over:
        return []
    return ["the selftest took %.2fs, over its %.2fs budget (share %.2f of the %ds cap "
            "hook_health_check applies when it runs this selftest in the weekly sweep). A "
            "selftest that outlives that cap is reported to users as ERRORED/timed out even "
            "when it passes."
            % (elapsed, budget_s(share), share, SELFTEST_TIMEOUT_S)]


# --------------------------------------------------------------------------------------
# the structural guards: one declaration, and it must still be the governing one
# --------------------------------------------------------------------------------------

_CAPISH = "SELFTEST_TIMEOUT"


def redeclared_caps(hooks_dir: str = HERE) -> list:
    """Problems for any hook that binds a SELFTEST_TIMEOUT-ish name to a NUMBER.

    This module is allowed to - it is the declaration. Everyone else must read it.
    An unparseable file is REPORTED, never skipped: a file the guard cannot read is a file
    the guard is not guarding, and silence there is the whole disease.
    """
    problems = []
    for path in sorted(glob.glob(os.path.join(glob.escape(hooks_dir), "*.py"))):
        if os.path.abspath(path) == os.path.abspath(__file__):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError) as exc:
            problems.append("cannot parse %s (%r), so its cap declarations are unchecked"
                            % (os.path.basename(path), exc))
            continue
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
                value = node.value
            else:
                continue
            if value is None or not isinstance(value, ast.Constant):
                continue
            if not isinstance(value.value, (int, float)) or isinstance(value.value, bool):
                continue
            for t in targets:
                if _CAPISH in t.id.upper():
                    problems.append(
                        "%s:%d declares %s = %r as its own literal. The cap must be READ from "
                        "selftest_budget.SELFTEST_TIMEOUT_S, or the number a hook budgets "
                        "against silently drifts from the number that kills it"
                        % (os.path.basename(path), t.lineno, t.id, value.value))
    return problems


def governing_binding_ok(hooks_dir: str = HERE) -> list:
    """hook_health_check must still take its cap from THIS module.

    Separate from redeclared_caps() because DELETING the binding passes that check trivially:
    no literal, no problem, and no cap either.
    """
    path = os.path.join(hooks_dir, "hook_health_check.py")
    if not os.path.isfile(path):
        return ["hook_health_check.py is missing, so nothing governs the per-hook cap"]
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError) as exc:
        return ["cannot parse hook_health_check.py (%r)" % exc]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and _CAPISH in t.id.upper():
                v = node.value
                if isinstance(v, ast.Attribute) and v.attr == "SELFTEST_TIMEOUT_S":
                    return []
                return ["hook_health_check.py:%d binds %s to something other than "
                        "selftest_budget.SELFTEST_TIMEOUT_S - the budget and the kill are no "
                        "longer the same number" % (t.lineno, t.id)]
    return ["hook_health_check.py no longer binds a per-hook cap at all, so the budget every "
            "hook measures against governs nothing"]


def budget_coverage(hooks_dir: str = HERE) -> tuple:
    """(budgeted, selftestable, missing) - DERIVED by reading files, never a roster.

    A hook that does not call report() simply does not self-budget. That is a coverage gap,
    and this repo's rule is that a gap must be VISIBLE with its denominator rather than
    silently absent - the same reason no_regression prints "1 of 22 units (4%)". Listing the
    covered hooks in a tuple here would be the fifth hardcoded roster this repo has dug out.
    """
    selftestable, budgeted = [], []
    for path in sorted(glob.glob(os.path.join(glob.escape(hooks_dir), "*.py"))):
        name = os.path.basename(path)
        if os.path.abspath(path) == os.path.abspath(__file__):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        if "--selftest" not in text:
            continue
        if "def selftest" not in text and "def _selftest" not in text:
            continue
        selftestable.append(name)
        if "selftest_budget.report(" in text:
            budgeted.append(name)
    missing = [n for n in selftestable if n not in budgeted]
    return budgeted, selftestable, missing


def selftest() -> int:
    fails = []

    # the arithmetic
    if budget_s(0.5) != SELFTEST_TIMEOUT_S * 0.5:
        fails.append("budget_s(0.5) is not half the cap")
    for bad in (0, -1, 1.5, "x", None):
        try:
            budget_s(bad)
            fails.append("budget_s(%r) must raise - a share outside (0,1] is nonsense" % (bad,))
        except (ValueError, TypeError):
            pass

    # the line always names both numbers, in both states
    for over in (False, True):
        txt = line(1.23, 0.5, "demo", over)
        for token in ("1.23s", "%ds cap" % SELFTEST_TIMEOUT_S, "share 0.50", "demo"):
            if token not in txt:
                fails.append("the budget line omits %r in the over=%s state: %r"
                             % (token, over, txt))
    if "OVER BUDGET" not in line(99.0, 0.5, "d", True):
        fails.append("an over-budget line must say so in words, not only in a number")

    # report() returns a problem exactly when it is over, and prints either way
    if report(0.5, "under-budget-probe", t0=time.time()):
        fails.append("a fast selftest must produce no problem")
    if not report(0.5, "over-budget-probe", t0=time.time() - 999):
        fails.append("a selftest 999s old must produce a problem - this is the whole point")

    # the structural guards
    fails.extend(redeclared_caps())
    fails.extend(governing_binding_ok())

    # and the guards must be able to FAIL - a guard that cannot fire is decoration
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="sb_")
    try:
        with open(os.path.join(tmp, "rogue.py"), "w", encoding="utf-8") as fh:
            fh.write("_SELFTEST_TIMEOUT_S = 30\n")
        if not redeclared_caps(tmp):
            fails.append("redeclared_caps did not flag a planted literal re-declaration, so "
                         "it cannot detect the drift it exists for")
        with open(os.path.join(tmp, "hook_health_check.py"), "w", encoding="utf-8") as fh:
            fh.write("_SELFTEST_TIMEOUT_S = 25\n")
        if not governing_binding_ok(tmp):
            fails.append("governing_binding_ok accepted a hardcoded literal cap")
        with open(os.path.join(tmp, "hook_health_check.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        if not governing_binding_ok(tmp):
            fails.append("governing_binding_ok accepted a hook_health_check with NO cap "
                         "binding at all - deleting the binding must not pass")
        with open(os.path.join(tmp, "broken.py"), "w", encoding="utf-8") as fh:
            fh.write("def (:\n")
        if not any("cannot parse" in p for p in redeclared_caps(tmp)):
            fails.append("an unparseable hook was silently skipped rather than reported")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    _budgeted, _selftestable, _missing = budget_coverage()
    print("-- selftest_budget: cap %ds, default share %.2f, %d hook(s) checked for a "
          "re-declared cap" % (SELFTEST_TIMEOUT_S, DEFAULT_SHARE,
                               len(glob.glob(os.path.join(glob.escape(HERE), "*.py"))) - 1))
    print("-- budget coverage: %d of %d selftestable hook(s) self-budget"
          % (len(_budgeted), len(_selftestable)))
    if _missing:
        # NOT a failure, and deliberately so: an unwired hook is not lying about anything, it
        # simply is not covered yet. But it is printed with its denominator every run, because
        # the alternative - partial coverage that reads as full - is the defect this whole
        # module exists to prevent. Wiring the remainder is scheduled in the plan.
        print("   NOT self-budgeting (%d, scheduled): %s"
              % (len(_missing), ", ".join(_missing)))
    fails.extend(report(DEFAULT_SHARE, "selftest_budget"))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
