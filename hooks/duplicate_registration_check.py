#!/usr/bin/env python3
"""duplicate-registration-check (SessionStart hook) - catch a hook wired more than once.

THE BUG THIS FIXES (found 2026-07-29): a hook registered from two different roots runs
twice per event. Observed live: rate_prompt fired twice on every prompt and
hook_health_check twice at session start, while hook_health_check itself reported
"OK - 32 hook commands verified" throughout, because it validates that commands RESOLVE
and has no notion of a command being registered twice.

TWO THINGS A NAIVE VERSION GETS WRONG:

1. It reads only `command`. Claude Code accepts the script either inlined in `command`
   or passed via an `args` array; this config uses BOTH styles. A `command`-only scan
   silently misses half the hooks.

2. It reports "duplicate" by FILENAME. That conflates two very different faults:
     - SAME FILE registered twice  -> redundant, the work is simply done twice.
     - DIFFERENT FILES, same name  -> two variant programs both wired. Far worse: if
       they share a state key they suppress each other and WHICH variant's logic applies
       depends on dispatch order; if they do not, both run with divergent behaviour.
   Verified 2026-07-29: all 8 collisions on this machine are the second kind - AST
   comparison showed zero of the pairs were functionally identical.

Also expands dispatcher fan-out: a dispatcher (post_tooluse_dispatcher, stop_dispatcher)
runs sibling modules listed in its own HOOKS tuple. plan_defer_guard was registered
directly from one root AND dispatched from the other - invisible to a settings-only scan.

Mechanical + fail-silent by design: unreadable settings / unparseable dispatcher / any
exception -> silent exit 0. A broken hook must never block the user.
Run with --selftest to verify the mechanics.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

SETTINGS = os.path.expanduser("~/.claude/settings.json")
PY_IN_STRING = re.compile(r"[^\"\s]*[/\\][A-Za-z0-9_.-]+\.py")


def _iter_commands(settings_path: str):
    """Yield every script path referenced by any hook, from `command` and `args`."""
    try:
        data = json.load(open(settings_path, encoding="utf-8"))
    except (OSError, ValueError):
        return
    for groups in (data.get("hooks") or {}).values():
        for group in groups or []:
            for hook in group.get("hooks", []) or []:
                parts = [hook.get("command") or ""]
                parts += [a for a in (hook.get("args") or []) if isinstance(a, str)]
                for part in parts:
                    for match in PY_IN_STRING.findall(part):
                        yield match.strip('"')


def _split(path: str) -> tuple[str, str]:
    norm = path.replace("\\", "/")
    head, _, tail = norm.rpartition("/")
    return head, tail


def _digest(path: str) -> str | None:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]
    except OSError:
        return None


def dispatched_modules(dispatcher_path: str) -> list[str]:
    """Module names in a dispatcher's HOOKS tuple, via AST (never imports it)."""
    try:
        tree = ast.parse(open(dispatcher_path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "HOOKS" for t in node.targets):
            continue
        for elt in getattr(node.value, "elts", []):
            parts = getattr(elt, "elts", [elt])
            if parts and isinstance(parts[0], ast.Constant) and isinstance(parts[0].value, str):
                names.append(parts[0].value)
    return names


def audit(settings_path: str | None = None) -> list[str]:
    """Return problem lines (empty == healthy).

    Resolves SETTINGS at CALL time, not definition time: a default of `=SETTINGS` binds the
    module constant when the function is defined, so overriding it (tests, alternate configs)
    silently has no effect. Found 2026-07-29 while probing the stdout path.
    """
    settings_path = settings_path or SETTINGS
    registered: dict[str, set[str]] = defaultdict(set)
    for path in _iter_commands(settings_path):
        head, tail = _split(path)
        registered[tail].add(head)

    effective: dict[str, set[str]] = {k: set(v) for k, v in registered.items()}
    for base, roots in list(registered.items()):
        if "dispatcher" not in base:
            continue
        for root in roots:
            for mod in dispatched_modules(os.path.join(root, base)):
                effective.setdefault(mod + ".py", set()).add(root + "|via " + base)

    problems: list[str] = []
    for base in sorted(effective):
        roots = sorted(effective[base])
        if len(roots) < 2:
            continue
        digests = {}
        for entry in roots:
            root = entry.split("|", 1)[0]
            digests[entry] = _digest(os.path.join(root, base))
        distinct = {d for d in digests.values() if d}
        kind = ("SAME FILE twice (redundant)" if len(distinct) == 1
                else "DIFFERENT PROGRAMS sharing a name (nondeterministic)")
        problems.append("%s - registered %d times - %s:" % (base, len(roots), kind))
        for entry in roots:
            root, _, via = entry.partition("|")
            problems.append("      <- %s%s  [sha %s]" % (
                root, (" (" + via + ")") if via else "", digests[entry] or "missing"))
    return problems


def _selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        a, b = os.path.join(td, "a"), os.path.join(td, "b")
        os.makedirs(a)
        os.makedirs(b)
        # same-name, DIFFERENT content -> must be reported as variant conflict
        open(os.path.join(a, "widget.py"), "w", encoding="utf-8").write("x = 1\n")
        open(os.path.join(b, "widget.py"), "w", encoding="utf-8").write("x = 2\n")
        # identical twin -> must be reported as redundant
        for root in (a, b):
            open(os.path.join(root, "twin.py"), "w", encoding="utf-8").write("y = 0\n")
        open(os.path.join(b, "x_dispatcher.py"), "w", encoding="utf-8").write(
            'HOOKS = (\n    ("widget", "w"),\n)\n')
        open(os.path.join(a, "solo.py"), "w", encoding="utf-8").write("z = 3\n")

        settings = os.path.join(td, "settings.json")
        # `with`, not json.dump(..., open(...)): an unclosed handle blocks TemporaryDirectory
        # cleanup on Windows and the retry path recurses to a RecursionError, which the
        # top-level fail-silent wrapper then swallows - a green-looking silent failure.
        with open(settings, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [
                {"command": os.path.join(a, "widget.py")},                 # inline style
                {"command": "python", "args": [os.path.join(b, "twin.py")]},   # args style
                {"command": os.path.join(a, "twin.py")},
                {"command": os.path.join(b, "x_dispatcher.py")},           # fan-out to widget
                {"command": os.path.join(a, "solo.py")},
            ]}]}}, fh)

        out = "\n".join(audit(settings))
        checks = [
            ("widget.py" in out and "DIFFERENT PROGRAMS" in out, "variant conflict not flagged"),
            ("twin.py" in out and "SAME FILE" in out, "args-style duplicate not detected"),
            ("solo.py" not in out, "false positive on singly-registered hook"),
        ]
        for ok, msg in checks:
            if not ok:
                print("SELFTEST FAIL: " + msg)
                print(out or "(nothing reported)")
                return 1

        # main() must actually REACH audit() and PRINT. Testing audit() alone leaves the
        # reporting path uncovered - and a late-bound default silently made SETTINGS
        # un-overridable, so this exact check failed to produce output on first attempt.
        import contextlib
        import io as _io
        global SETTINGS
        real, SETTINGS = SETTINGS, settings
        buf = _io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = main()
        finally:
            SETTINGS = real
        emitted = buf.getvalue()
        if rc != 0:
            print(f"SELFTEST FAIL: main() should exit 0 (advisory), got {rc}")
            return 1
        if "widget.py" not in emitted or "duplicate-registration" not in emitted:
            print("SELFTEST FAIL: main() did not print findings to STDOUT")
            print(repr(emitted))
            return 1
    print("SELFTEST PASS: variant conflict, args-style duplicate, dispatcher fan-out, "
          "no false positive, main() prints to stdout")
    return 0


def main() -> int:
    # NOTE: --selftest is dispatched in __main__, NOT here. When main() dispatched it,
    # the selftest's own main() integration check re-entered _selftest() (sys.argv still
    # held --selftest) and recursed until RecursionError, which the fail-silent wrapper
    # below swallowed into a silent exit 0 - a selftest that printed nothing and "passed".
    try:
        problems = audit()
    except Exception:
        return 0  # fail-silent
    if not problems:
        return 0
    # STDOUT, not stderr. Measured 2026-07-29 with a probe hook + headless `claude -p`:
    #   - a SessionStart hook exiting 2 does NOT block the session (proven with a
    #     filesystem marker confirming the hook actually executed), so exit 0 is not a
    #     workaround - it is simply correct for an advisory check.
    #   - stdout from a SessionStart hook is observably surfaced ("SessionStart hook
    #     success: ..."); stderr visibility was NOT demonstrable. hook_health_check has
    #     always used print(), and its line does appear. Match the pattern that is proven
    #     to be seen rather than the one that merely looks conventional.
    print("[duplicate-registration] a hook is wired more than once:")
    for line in problems:
        print("  " + line)
    print("  Fix: keep exactly one registration per hook. If the copies differ, merge them "
          "first - whichever runs first can consume the other's once-per-session marker.")
    return 0


if __name__ == "__main__":
    # The selftest is deliberately NOT fail-silent: a broken safety net must be loud when
    # you ask it to prove itself, even though it stays silent in normal operation.
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
