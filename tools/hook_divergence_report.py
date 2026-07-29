#!/usr/bin/env python3
"""Compare two directories holding copies of this hook suite, and prove how they differ.

Use it when the same hooks exist in more than one place - a working copy plus an installed
copy, a fork, a vendored snapshot - and you need to know whether they are the same PROGRAM
or merely the same FILENAMES. Filenames and line counts both mislead: two files can share a
name and behave differently, and a large diff can be pure refactoring with identical
behaviour. This reports AST token deltas, SHA digests, dispatcher fan-out sets and STATE_DIR
resolution, so a divergence claim is regenerated from source rather than asserted.

STATE_DIR matters most: two variants resolving to the SAME state directory can consume each
other's once-per-session markers, so whichever runs first silently suppresses the other.

    python tools/hook_divergence_report.py [--roots A B] [--json out.json]

Default roots are the two this project was consolidated from. Any two directories work.
Exits 0 always; it is a report, not a gate.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from collections import Counter

DEFAULT_ROOTS = [os.path.expanduser("~/.claude/hooks"),
                 os.path.expanduser("~/Downloads/unbluff/hooks")]


def strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    return tree


def parse(path: str):
    try:
        return strip_docstrings(ast.parse(open(path, encoding="utf-8").read()))
    except (OSError, SyntaxError):
        return None


def tokens(tree: ast.AST) -> Counter:
    """Behavioural vocabulary: names, defs, attributes, string constants."""
    c: Counter = Counter()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            c["name:" + n.id] += 1
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            c["def:" + n.name] += 1
        elif isinstance(n, ast.Attribute):
            c["attr:" + n.attr] += 1
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            c["str:" + (n.value[:60])] += 1
    return c


def sha(path: str) -> str | None:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]
    except OSError:
        return None


def hooks_tuple(path: str):
    tree = parse(path)
    if tree is None:
        return None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "HOOKS" for t in n.targets):
            out = []
            for e in getattr(n.value, "elts", []):
                parts = getattr(e, "elts", [e])
                if parts and isinstance(parts[0], ast.Constant):
                    out.append(parts[0].value)
            return out
    return None


def state_expr(path: str) -> str | None:
    try:
        src = open(path, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"^\s*(?:_)?STATE_DIR\s*=.*(?:\n\s+.*)?$", src, re.M)
    return " ".join(m.group(0).split()) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs=2, default=DEFAULT_ROOTS)
    ap.add_argument("--json")
    args = ap.parse_args()
    a_root, b_root = args.roots
    a_label, b_label = (os.path.basename(os.path.dirname(r)) or r for r in (a_root, b_root))

    def listpy(root):
        return {f for f in os.listdir(root) if f.endswith(".py")} if os.path.isdir(root) else set()

    a_files, b_files = listpy(a_root), listpy(b_root)
    shared = sorted(a_files & b_files)

    report = {"roots": {a_label: a_root, b_label: b_root}, "pairs": [],
              "only_in": {a_label: sorted(a_files - b_files), b_label: sorted(b_files - a_files)},
              "dispatchers": {}, "state_dirs": {}}

    print("=" * 76)
    print("HOOK DIVERGENCE REPORT")
    print("=" * 76)
    print(f"  {a_label:<10} {a_root}")
    print(f"  {b_label:<10} {b_root}")

    print(f"\n{'FILE':<32}{'AST DELTA':>11}  {'SHA A':<14}{'SHA B':<14} VERDICT")
    print("-" * 76)
    for f in shared:
        pa, pb = os.path.join(a_root, f), os.path.join(b_root, f)
        ta, tb = parse(pa), parse(pb)
        if ta is None or tb is None:
            continue
        toks_a, toks_b = tokens(ta), tokens(tb)
        delta = sum((toks_a - toks_b).values()) + sum((toks_b - toks_a).values())
        sa, sb = sha(pa), sha(pb)
        identical_ast = ast.dump(ta) == ast.dump(tb)
        verdict = ("IDENTICAL" if identical_ast else
                   "same-file" if sa == sb else "DIFFERENT PROGRAMS")
        print(f"{f:<32}{delta:>11}  {sa or '-':<14}{sb or '-':<14} {verdict}")
        report["pairs"].append({"file": f, "ast_token_delta": delta, "sha": {a_label: sa, b_label: sb},
                                "ast_identical": identical_ast, "verdict": verdict})

    print(f"\nonly in {a_label}: {', '.join(report['only_in'][a_label]) or '(none)'}")
    print(f"only in {b_label}: {', '.join(report['only_in'][b_label]) or '(none)'}")

    print("\nDISPATCHER FAN-OUT")
    print("-" * 76)
    for root, label in ((a_root, a_label), (b_root, b_label)):
        for f in sorted(listpy(root)):
            if "dispatcher" not in f:
                continue
            h = hooks_tuple(os.path.join(root, f))
            if h is not None:
                print(f"  {label:<10} {f:<30} -> {h}")
                report["dispatchers"][f"{label}/{f}"] = h

    print("\nSTATE_DIR RESOLUTION (shared state = variants can suppress each other)")
    print("-" * 76)
    for f in shared:
        exprs = {}
        for root, label in ((a_root, a_label), (b_root, b_label)):
            e = state_expr(os.path.join(root, f))
            if e:
                exprs[label] = e
        if exprs:
            report["state_dirs"][f] = exprs
            print(f"  {f}")
            for label, e in exprs.items():
                print(f"     {label:<10} {e[:90]}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nJSON written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
