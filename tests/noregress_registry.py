"""How to probe a unit for the no-regression gate. NEVER which units count.

THE ONE RULE THIS FILE OBEYS
    A registry may say HOW to probe a unit. It may never decide WHICH units are asked
    about. The unit population in tools/no_regression.py is DERIVED by walking the repo
    for modules that expose a --selftest, and a unit missing from this file is reported
    as UNCOVERED with its reason printed - never as passing.

    That split is the whole point. This repo has been bitten repeatedly by a hardcoded
    roster silently shrinking a denominator: run_selftests.SELFTESTABLE,
    hook_health_check._LOCAL_HOOKS, install.REQUIRED_HOOKS and check_review_freshness.units()
    were all found the same way. A registry that could remove a unit from the question
    would be the fifth.

GHOSTS ARE BLOCKING
    An entry naming a path that does not exist fails the gate. That is what makes a rename
    impossible to do quietly: rename the unit without updating this file and the gate stops
    the push instead of silently measuring nothing.

ENTRY SHAPE
    "<repo-relative path>": {
        "corpus": <repo-relative path to a module exposing ENTRIES>,
        "probe":  <capability-family name, used to pick entrypoints by MEANING not signature>,
        "renamed_from": <previous repo-relative path, or None>,
    }

    `renamed_from` exists because git cannot resolve an uncommitted rename plus a rewrite:
    both `git log` and `git log --follow` return empty for the new path, and default rename
    detection reports add/delete when similarity is low. Recording the old path lets the
    predecessor walk continue across a rename the tooling cannot infer.
"""

from __future__ import annotations

REGISTRY = {
    "hooks/capped_report.py": {
        "corpus": "tests/cap_spelling_corpus.py",
        "probe": "cap_detector",
        "renamed_from": None,
    },
}
