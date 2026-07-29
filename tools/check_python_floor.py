#!/usr/bin/env python3
"""Verify every Python file still parses at the version floor the README advertises.

The badge says Python 3.8+. CI runs the suite on 3.8, which covers files CI *executes* -
but not `tools/` scripts, or any file only imported on a branch CI does not take. A single
`str | None` or `dict[str, int]` outside an annotation, in a file nobody runs on 3.8, breaks
the promise silently for anyone on an older interpreter.

`ast.parse(..., feature_version=...)` checks SYNTAX only. It cannot catch a stdlib API added
after the floor (e.g. `str.removeprefix`, 3.9), so it is a floor guard, not a full guarantee.

    python tools/check_python_floor.py            # check (exit 1 on violation)
    python tools/check_python_floor.py --floor 3.9
"""
from __future__ import annotations

import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def iter_py(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor", default="3.8", help="minimum supported version, e.g. 3.8")
    args = ap.parse_args()
    try:
        major, minor = (int(p) for p in args.floor.split(".", 1))
    except ValueError:
        print(f"bad --floor {args.floor!r}; expected like 3.8")
        return 1

    bad = []
    n = 0
    for path in iter_py(HERE):
        n += 1
        try:
            src = open(path, encoding="utf-8").read()
        except OSError as e:
            bad.append((path, f"unreadable: {e}"))
            continue
        try:
            ast.parse(src, feature_version=(major, minor))
        except SyntaxError as e:
            bad.append((path, f"line {e.lineno}: {e.msg}"))

    rel = lambda p: os.path.relpath(p, HERE).replace("\\", "/")  # noqa: E731
    if bad:
        print(f"python-floor: {len(bad)} file(s) do NOT parse as Python {args.floor}:")
        for path, msg in bad:
            print(f"  - {rel(path)}: {msg}")
        return 1
    print(f"python-floor: all {n} files parse as Python {args.floor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
