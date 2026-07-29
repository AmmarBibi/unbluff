#!/usr/bin/env python3
"""Verify every skill a hook depends on is actually shipped and installed.

close_skills_guard names four skills in REQUIRED_SKILLS. The repo shipped three, and
install.py's SKILL_NAMES listed the same three - so installing unbluff produced a hook
that permanently reports a missing skill the user was never given, with no error anywhere
to explain it (found 2026-07-29, after the hook had already been published).

Nothing connected the three lists. This does: any `REQUIRED_SKILLS`-style tuple in a hook
must be a subset of both `skills/` on disk and `install.py`'s SKILL_NAMES.

    python tools/check_skill_deps.py     # exit 1 on a missing dependency
"""
from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(HERE, "hooks")
SKILLS = os.path.join(HERE, "skills")
DEP_NAMES = {"REQUIRED_SKILLS", "SKILLS", "CLOSE_SKILLS"}


def string_tuple(path: str, names: set) -> list:
    """String constants assigned to any of `names` at module level. AST only, no import."""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
            continue
        for elt in getattr(node.value, "elts", []):
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                out.append(elt.value)
    return out


def main() -> int:
    shipped = {d for d in os.listdir(SKILLS)
               if os.path.isfile(os.path.join(SKILLS, d, "SKILL.md"))} if os.path.isdir(SKILLS) else set()
    installed = set(string_tuple(os.path.join(HERE, "install.py"), {"SKILL_NAMES"}))

    problems = []
    checked = 0
    for name in sorted(os.listdir(HOOKS)) if os.path.isdir(HOOKS) else []:
        if not name.endswith(".py"):
            continue
        deps = string_tuple(os.path.join(HOOKS, name), DEP_NAMES)
        if not deps:
            continue
        checked += 1
        for dep in deps:
            if dep not in shipped:
                problems.append(f"{name} requires skill '{dep}' but skills/{dep}/SKILL.md is missing")
            elif dep not in installed:
                problems.append(f"{name} requires skill '{dep}' but install.py SKILL_NAMES omits it "
                                f"- it ships in the repo but is never installed")

    for skill in sorted(installed - shipped):
        problems.append(f"install.py SKILL_NAMES lists '{skill}' but skills/{skill}/SKILL.md is missing")

    if problems:
        print(f"skill-deps: {len(problems)} problem(s):")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"skill-deps: OK - {checked} hook(s) with skill dependencies, "
          f"{len(shipped)} shipped, {len(installed)} installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
