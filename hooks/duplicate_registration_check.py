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
import shlex
import sys
from collections import defaultdict

SETTINGS = os.path.expanduser("~/.claude/settings.json")

_UNKNOWN_KIND = ("UNKNOWN - at least one file could not be read, so sameness was NOT "
                 "determined; check both by hand before deleting either")


def _path_tokens(text: str) -> list[str]:
    """Every .py path in a command string, split the way a shell splits it.

    Replaces the regex `[^"\\s]*[/\\\\][A-Za-z0-9_.-]+\\.py`, whose leading `[^"\\s]*` cannot
    cross a space. `"C:\\Users\\John Doe\\.claude\\hooks\\rate_prompt.py"` therefore matched
    nothing usable, and BOTH headline detections went silent - for every user whose home
    directory contains a space, which on Windows is the ordinary case. No fixture used one,
    so the hook reported a clean bill on a machine where it was doing nothing at all.
    """
    try:
        toks = shlex.split(text, posix=False)   # posix=False: Windows backslashes survive
    except ValueError:
        toks = text.split()
    out = []
    for t in toks:
        t = t.strip().strip('"').strip("'")
        if t.lower().endswith(".py"):
            out.append(t)
    return out


def settings_layers(settings_path: str | None = None, cwd: str | None = None) -> list[str]:
    """Every settings file Claude Code merges, most-global first.

    Reading only ~/.claude/settings.json hid the commonest real double-wiring: the same hook
    in the user file AND in the project's .claude/settings.json. Both fire on every event,
    and the check printed nothing.
    """
    base = cwd or os.getcwd()
    out = [settings_path or SETTINGS]
    if not settings_path:
        out.append(os.path.join(os.path.expanduser("~"), ".claude", "settings.local.json"))
    out.append(os.path.join(base, ".claude", "settings.json"))
    out.append(os.path.join(base, ".claude", "settings.local.json"))
    seen, uniq = set(), []
    for p in out:
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def _iter_commands(settings_path: str):
    """Yield every script path referenced by any hook, from `command` and `args`.

    Yields DUPLICATES as duplicates - the caller must not collapse them (see audit)."""
    try:
        with open(settings_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    for groups in (data.get("hooks") or {}).values():
        for group in groups or []:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []) or []:
                if not isinstance(hook, dict):
                    continue
                for match in _path_tokens(hook.get("command") or ""):
                    yield match
                for arg in (hook.get("args") or []):
                    if not isinstance(arg, str):
                        continue
                    # An args entry is ALREADY one token; re-splitting it on whitespace is
                    # what broke paths with spaces. Only fall back to tokenizing when the
                    # entry plainly is not a bare path.
                    stripped = arg.strip().strip('"').strip("'")
                    if stripped.lower().endswith(".py"):
                        yield stripped
                    else:
                        for match in _path_tokens(arg):
                            yield match


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


def audit(settings_path: str | None = None, cwd: str | None = None) -> list[str]:
    """Return problem lines (empty == healthy).

    Resolves SETTINGS at CALL time, not definition time: a default of `=SETTINGS` binds the
    module constant when the function is defined, so overriding it (tests, alternate configs)
    silently has no effect. Found 2026-07-29 while probing the stdout path.
    """
    # A LIST, not a set. Collapsing registrations into a set of directories made the
    # commonest double-fire - the SAME path wired twice - vanish before it could be counted,
    # so the check reported healthy for exactly the fault that motivated it (rate_prompt
    # firing twice on every prompt). Two entries must stay two entries.
    registered: dict[str, list[str]] = defaultdict(list)
    for layer in settings_layers(settings_path, cwd):
        label = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(layer)))) \
            or "?"
        scope = "user" if os.path.normcase(os.path.abspath(layer)) == \
            os.path.normcase(os.path.abspath(settings_path or SETTINGS)) else label
        for path in _iter_commands(layer):
            head, tail = _split(path)
            registered[tail].append("%s|%s|" % (head, scope))

    effective: dict[str, list[str]] = {k: list(v) for k, v in registered.items()}
    for base, entries in list(registered.items()):
        if "dispatcher" not in base:
            continue
        for entry in entries:
            root, scope, _ = entry.split("|", 2)
            for mod in dispatched_modules(os.path.join(root, base)):
                effective.setdefault(mod + ".py", []).append(
                    "%s|%s|via %s" % (root, scope, base))

    problems: list[str] = []
    for base in sorted(effective):
        entries = sorted(effective[base])
        if len(entries) < 2:
            continue
        digests = {}
        for i, entry in enumerate(entries):
            root = entry.split("|", 1)[0]
            digests[i] = _digest(os.path.join(root, base))
        values = list(digests.values())
        if any(v is None for v in values):
            # Do NOT drop the unknowns and compare what is left. One readable file plus one
            # missing one used to leave a single distinct digest and the report asserted
            # "SAME FILE twice (redundant)" - a verdict it had never computed, pointing the
            # reader at the wrong copy to delete.
            kind = _UNKNOWN_KIND
        elif len(set(values)) == 1:
            kind = "SAME FILE twice (redundant)"
        else:
            kind = "DIFFERENT PROGRAMS sharing a name (nondeterministic)"
        problems.append("%s - registered %d times - %s:" % (base, len(entries), kind))
        for i, entry in enumerate(entries):
            root, scope, via = entry.split("|", 2)
            problems.append("      <- %s [%s]%s  [sha %s]" % (
                root, scope, (" (" + via + ")") if via else "", digests[i] or "UNREADABLE"))
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

        fails = []
        out = "\n".join(audit(settings))
        checks = [
            ("widget.py" in out and "DIFFERENT PROGRAMS" in out, "variant conflict not flagged"),
            ("twin.py" in out and "SAME FILE" in out, "args-style duplicate not detected"),
            ("solo.py" not in out, "false positive on singly-registered hook"),
        ]
        for ok, msg in checks:
            if not ok:
                fails.append(msg + " || got: " + (out or "(nothing reported)")[:200])

        # ------------------------------------------------------- v1.3.1 regressions
        def _audit_of(entries, where=None, cwd=None):
            p = os.path.join(where or td, "s_%d.json" % len(os.listdir(where or td)))
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"hooks": {"Stop": [{"hooks": entries}]}}, fh)
            return "\n".join(audit(p, cwd=cwd)), p

        # (4) [findings 20, 23] THE COMMONEST DUPLICATE: the SAME path registered twice.
        # Registrations were collapsed into a SET of directories, so two identical entries
        # became one and the check reported a clean bill - for the exact double-fire that
        # motivated this hook (rate_prompt firing twice on every prompt).
        dup = os.path.join(a, "twice.py")
        with open(dup, "w", encoding="utf-8") as fh:
            fh.write("q = 1\n")
        out4, _ = _audit_of([{"command": dup}, {"command": dup}])
        if "twice.py" not in out4:
            fails.append("the same path registered TWICE was reported as healthy || " +
                         (out4 or "(nothing reported)")[:200])
        elif "2 times" not in out4:
            fails.append("same-path duplicate found but not counted: " + out4[:200])

        # (5) [findings 21, 22] a SPACE anywhere in a path killed BOTH headline detections.
        # `C:\Users\John Doe\...` is the common Windows case, and no fixture used one, so
        # the hook went completely silent for those users while reporting nothing wrong.
        spaced = os.path.join(td, "John Doe", "hooks")
        os.makedirs(spaced, exist_ok=True)
        s1 = os.path.join(spaced, "spaced.py")
        with open(s1, "w", encoding="utf-8") as fh:
            fh.write("s = 1\n")
        out5, _ = _audit_of([{"command": '"%s" "%s"' % (sys.executable, s1)},
                             {"command": "python", "args": [s1]}])
        if "spaced.py" not in out5:
            fails.append("a path containing a space silently disabled detection || " +
                         (out5 or "(nothing reported)")[:200])
        # Asserting only the FILENAME is not enough: the old regex still matched the fragment
        # after the space ("Doe\\hooks\\spaced.py"), so the duplicate was reported with a root
        # that does not exist - detected for the wrong reason, and unusable for fixing it.
        # The full directory must appear, and the digest must have been readable from it.
        elif spaced.replace("\\", "/") not in out5.replace("\\", "/"):
            fails.append("duplicate reported with a TRUNCATED root - the path was matched "
                         "from after the space || " + out5[:240])
        elif "UNREADABLE" in out5:
            fails.append("root parsed from a spaced path does not resolve to the real file || "
                         + out5[:240])

        # (6) [findings 24, 26] user + PROJECT scope. Reading only ~/.claude/settings.json
        # made the commonest real double-wiring invisible: the same hook in the user file
        # and in the project's .claude/settings.json. Both fire, every event.
        proj = os.path.join(td, "proj")
        os.makedirs(os.path.join(proj, ".claude"), exist_ok=True)
        shared = os.path.join(a, "shared.py")
        with open(shared, "w", encoding="utf-8") as fh:
            fh.write("sh = 1\n")
        with open(os.path.join(proj, ".claude", "settings.json"), "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [{"command": shared}]}]}}, fh)
        out6, _ = _audit_of([{"command": shared}], cwd=proj)
        if "shared.py" not in out6:
            fails.append("a hook wired at BOTH user and project scope was invisible || " +
                         (out6 or "(nothing reported)")[:200])

        # (7) [finding 25] when a file cannot be read, its digest is None. Those were
        # DISCARDED before the comparison, so one readable file plus one missing one left a
        # single distinct digest and the report asserted "SAME FILE twice (redundant)" - a
        # verdict it had not computed, steering the reader to delete the wrong copy.
        ghost = os.path.join(td, "ghost", "vanished.py")
        real_one = os.path.join(a, "vanished.py")
        with open(real_one, "w", encoding="utf-8") as fh:
            fh.write("v = 1\n")
        out7, _ = _audit_of([{"command": real_one}, {"command": ghost}])
        if "vanished.py" not in out7:
            fails.append("missing-file duplicate not reported at all: " + out7[:160])
        elif "SAME FILE" in out7:
            fails.append("asserted SAME FILE while a digest was unavailable - the verdict "
                         "was never computed || " + out7[:200])
        elif "UNKNOWN" not in out7 and "could not be read" not in out7:
            fails.append("no explicit unknown verdict for an unreadable file: " + out7[:200])

        if fails:
            for f in fails:
                print("SELFTEST FAIL: " + f)
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
