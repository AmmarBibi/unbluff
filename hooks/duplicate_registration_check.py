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

# REUSED from the sibling guard, never re-declared. hook_health_check has recognised four hook
# extensions since v1.2; this file recognised one, so the repo simultaneously believed both that
# a .js hook is a hook and that it is not. A second copy of a roster is the exact defect these
# guards exist to catch, and it had already happened here.
_HD = os.path.dirname(os.path.abspath(__file__))
if _HD not in sys.path:
    sys.path.insert(0, _HD)
from hook_health_check import _SCRIPT_EXTS as SCRIPT_EXTS  # noqa: E402
# [P14 B3-P] Same discipline for the LAYER roster. Deriving which plugins actually contribute
# hooks is subtle enough - the authority is `enabledPlugins`, the locations are the filesystem,
# and neither alone is correct - that it lives in one module with its own planted fixtures
# rather than being re-derived here. See hook_layers.py for why this is not a glob.
import hook_layers  # noqa: E402
from hook_layers import settings_layers  # noqa: E402

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
    if not isinstance(text, str):
        return []
    try:
        toks = shlex.split(text, posix=False)   # posix=False: Windows backslashes survive
    except ValueError:
        toks = text.split()
    out = []
    prev = ""
    for t in toks:
        t = t.strip().strip('"').strip("'")
        # [P14 B3] EXTENSIONS ARE DERIVED, not the literal ".py" this used to test. Claude Code
        # hooks are language-agnostic and the repo's OWN sibling guard already declares four
        # extensions - so a .js, .ps1 or .sh hook wired twice yielded NO token, never entered
        # the `registered` dict, and could not reach the duplicate test at all. Non-extraction
        # was indistinguishable from non-duplication. Importing the sibling's tuple rather than
        # copying it means a fifth extension is learned in one place, not two.
        if t.lower().endswith(SCRIPT_EXTS):
            out.append(t)
        # `python -m package.module` carries no path token whatsoever, so the same hook wired
        # twice in module form was completely invisible. Normalised to a path so both spellings
        # land on one key and a mixed pair (one -m, one path) still collides.
        elif prev == "-m" and t and not t.startswith("-"):
            out.append(t.replace(".", "/") + ".py")
        prev = t
    return out


def _iter_commands(settings_path: str, malformed: list | None = None):
    """Yield every script path referenced by any hook, from `command` and `args`.

    Yields DUPLICATES as duplicates - the caller must not collapse them (see audit)."""
    try:
        with open(settings_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return
    if not isinstance(data, dict):
        return
    for event, groups in (data.get("hooks") or {}).items():
        for group in groups or []:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher") or ""
            if not isinstance(matcher, str):
                matcher = repr(matcher)
            for hook in group.get("hooks", []) or []:
                if not isinstance(hook, dict):
                    continue
                cmd = hook.get("command")
                if cmd is not None and not isinstance(cmd, str):
                    # [P13 C6] Survive AND say so. shlex.split() on a non-str raises
                    # AttributeError, and _path_tokens caught only ValueError, so the hook went
                    # completely silent - reporting neither the malformed entry nor the
                    # duplicates it could still see. Silence from a checker is the one outcome
                    # indistinguishable from a clean bill of health.
                    if malformed is not None:
                        malformed.append("%s: hook 'command' is %s, not a string - this entry "
                                         "was skipped" % (os.path.basename(settings_path),
                                                          type(cmd).__name__))
                    continue
                # The ARGUMENTS are part of the identity, not noise. A shared runner wired to
                # one event several times with different flags is doing different work each
                # time; collapsing it to its filename reported 13 "duplicates" for one
                # correctly-wired ECC script. What is redundant is the same script run the same
                # WAY twice - see _fires() below.
                full = _invocation_key(cmd, hook.get("args"))
                for match in _path_tokens(cmd or ""):
                    yield (match, event, matcher, full)
                for arg in (hook.get("args") or []):
                    if not isinstance(arg, str):
                        continue
                    # An args entry is ALREADY one token; re-splitting it on whitespace is
                    # what broke paths with spaces. Only fall back to tokenizing when the
                    # entry plainly is not a bare path.
                    stripped = arg.strip().strip('"').strip("'")
                    if stripped.lower().endswith(SCRIPT_EXTS):
                        yield (stripped, event, matcher, full)
                    else:
                        for match in _path_tokens(arg):
                            yield (match, event, matcher, full)


def _invocation_key(cmd, args) -> str:
    """What makes two registrations the SAME work, ignoring how they were spelled.

    Keeps only the arguments that are NOT the interpreter and NOT the script itself. Two
    spellings of one invocation - `"python" "x.py"` and `command:"python", args:["x.py"]` -
    must compare EQUAL, because they run the same thing twice and that is the fault this guard
    exists for. A shared runner invoked as `runner.js --a` and `runner.js --b` must compare
    DIFFERENT, because it is doing different work each time; treating those as duplicates
    produced 13 false alarms for one correctly-wired script the moment non-.py extensions
    became visible.
    """
    # `command` is a shell string and must be SPLIT; each `args` entry is ALREADY one token and
    # must NOT be. Re-splitting an args entry on whitespace is findings 21/22 - it turns
    # `C:\Users\John Doe\hooks\x.py` into two tokens, so the path stops ending in .py, survives
    # as a bogus argument, and two spellings of one invocation stop comparing equal. This helper
    # reintroduced that defect on its first draft and the space fixture caught it.
    toks = []
    if isinstance(cmd, str):
        try:
            toks += shlex.split(cmd, posix=False)
        except ValueError:
            toks += cmd.split()
    for a in (args or []):
        if isinstance(a, (str, int, float)):
            toks.append(str(a))
    # Everything BEFORE the script is the launcher and its flags; everything AFTER is the work.
    # That split is what makes `pwsh -NoProfile -File x.ps1` and `powershell -File x.ps1` compare
    # EQUAL - two launchers running one script on one event, which double-fires - while
    # `runner.js --alpha` and `runner.js --beta` stay DIFFERENT. Keying on "all non-script
    # tokens" instead treats -NoProfile as script work and misses the .ps1 pair entirely.
    toks = [t.strip().strip('"').strip("'") for t in toks]
    cut = None
    for i, t in enumerate(toks):
        if t.lower().endswith(SCRIPT_EXTS):
            cut = i
            break
        if t == "-m" and i + 1 < len(toks):   # `-m pkg.mod` names the script without a path
            cut = i + 1
            break
    return " ".join(toks[cut + 1:]) if cut is not None else " ".join(toks[1:])


def _parts(entry: str) -> tuple:
    """(root, scope, via, event, matcher, full) - one place that knows the entry encoding."""
    bits = entry.split("|", 5)
    while len(bits) < 6:
        bits.append("")
    return tuple(bits)


def _fires(entries: list) -> tuple:
    """(is_problem, reason) for one basename's registrations.

    THE QUESTION IS "does this script run twice for ONE event", not "does this name appear
    twice anywhere". Merging every event and matcher before counting reported the same hook
    wired under Stop AND PreToolUse as a duplicate, though neither double-fires - and once
    non-.py extensions became visible it reported 13 "duplicates" for a single correctly-wired
    shared runner invoked with different flags. A guard that fires on a correct config gets
    disabled by its owner, which is strictly worse than no guard.

    Three genuinely distinct faults, all still caught:
      * VARIANT CONFLICT - one basename resolving to more than one directory. Event-independent:
        which file wins is nondeterministic regardless of when it fires.
      * REDUNDANT - the same script wired the same WAY (identical command+args) more than once
        for one (event, matcher). This is the fault that motivated the guard.
      * DOUBLE PATH - the same module reached both directly and through a dispatcher on one
        event. The commands differ, so an args comparison alone would miss it.
    """
    roots = {_parts(e)[0] for e in entries}
    if len(roots) > 1:
        return True, "variant conflict"
    by_slot = defaultdict(list)
    for e in entries:
        root, _scope, via, event, matcher, full = _parts(e)
        by_slot[(event, matcher)].append((full, bool(via)))
    for (_event, _matcher), rows in by_slot.items():
        if len(rows) < 2:
            continue
        if any(v for _f, v in rows):
            return True, "reached directly AND via a dispatcher on one event"
        counts = defaultdict(int)
        for f, _v in rows:
            counts[f] += 1
        if any(n > 1 for n in counts.values()):
            return True, "wired identically more than once for one event"
    return False, ""


def _split(path: str) -> tuple[str, str]:
    norm = path.replace("\\", "/")
    head, _, tail = norm.rpartition("/")
    return head, tail


def _digest(path: str) -> str | None:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]
    except OSError:
        return None


def _imports_a_named_module(tree) -> bool:
    """Does this file import a module whose NAME is a value at runtime?

    That is what dispatching IS - `importlib.import_module(name)` - and it is the behavioural
    fact the roster SHAPE was standing in for. A guard that infers a behaviour from the shape
    of a constant is the class this repo exists to catch; it is only ever a proxy, and this
    one was measured wrong (see the caller).
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name in ("import_module", "__import__"):
            return True
    return False


def dispatched_modules(dispatcher_path: str) -> list[str]:
    """Module names in a dispatcher's fan-out list, via AST (never imports it).

    [P14 B3] This used to require the list be literally named `HOOKS`. The repo's own
    post_tooluse_dispatcher could be renamed to MODULES or PIPELINE and its whole fan-out went
    invisible - every module it dispatches would then be counted zero times instead of once,
    and a module wired BOTH directly and through the dispatcher stopped colliding. The name of
    a variable is not a fact about behaviour, so the shape is what is matched now: a
    module-level binding of a sequence whose elements start with a string, held to an
    ALL-CAPS name so ordinary local lists cannot be mistaken for a roster.
    """
    try:
        tree = ast.parse(open(dispatcher_path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return []
    # [PGG-PS fallout, MEASURED 2026-08-13] A file that never imports a module BY NAME cannot
    # dispatch to one. Without this clause the shape-match below is far too generous: EVERY
    # module-level ALL-CAPS tuple of strings reads as a fan-out roster, so `piped_gate_guard`'s
    # STATUS_EATERS made this hook believe in modules called head.py, tail.py and sort.py. That
    # was wrong SILENTLY - phantom names counted once each and collided with nothing - until a
    # name appeared in a SECOND vocabulary tuple in the same file, at which point the phantom
    # was reported as "registered 2 times" and integration scenario C2 (this hook is SILENT on
    # a clean install) went red. The false alarm was in the CHECKER, not the guard it read.
    #
    # The narrowing is BEHAVIOURAL, which is the argument the docstring above already makes for
    # not matching the name `HOOKS`: dispatching IS `import_module(<name>)`, so ask whether the
    # file does that rather than what its constants happen to look like.
    if not _imports_a_named_module(tree):
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        if not any(isinstance(t, ast.Name) and t.id.isupper() for t in targets):
            continue
        elts = getattr(node.value, "elts", None)
        if not elts:
            continue
        found = []
        for elt in elts:
            parts = getattr(elt, "elts", [elt])
            if parts and isinstance(parts[0], ast.Constant) and isinstance(parts[0].value, str):
                found.append(parts[0].value)
        # Only a list where EVERY element yields a module name is a fan-out roster; a mixed
        # constant tuple is some other module-level table.
        if found and len(found) == len(elts):
            names.extend(found)
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
    malformed: list[str] = []
    for layer in settings_layers(settings_path, cwd):
        label = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(layer)))) \
            or "?"
        scope = "user" if os.path.normcase(os.path.abspath(layer)) == \
            os.path.normcase(os.path.abspath(settings_path or hook_layers.SETTINGS)) else label
        for path, event, matcher, full in _iter_commands(layer, malformed):
            head, tail = _split(path)
            registered[tail].append("%s|%s||%s|%s|%s" % (head, scope, event, matcher, full))

    effective: dict[str, list[str]] = {k: list(v) for k, v in registered.items()}
    for base, entries in list(registered.items()):
        # [P14 B3] NO filename test. This was `if "dispatcher" not in base: continue` - a name
        # test standing in for a behaviour test, so the SAME file fanning out to the SAME
        # modules was expanded when called stop_dispatcher.py and invisible when called
        # fanout.py. Every registered script is now ASKED whether it has a fan-out roster, and
        # the AST answers; a file that has none costs one parse and yields nothing.
        if not base.lower().endswith(".py"):
            continue
        for entry in entries:
            root, scope, _via, event, matcher, _full = _parts(entry)
            for mod in dispatched_modules(os.path.join(root, base)):
                effective.setdefault(mod + ".py", []).append(
                    "%s|%s|via %s|%s|%s|%s" % (root, scope, base, event, matcher, "via " + base))

    problems: list[str] = list(malformed)
    for base in sorted(effective):
        entries = sorted(effective[base])
        if len(entries) < 2:
            continue
        fires, why = _fires(entries)
        if not fires:
            continue
        digests = {}
        for i, entry in enumerate(entries):
            root = _parts(entry)[0]
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
        problems.append("%s - registered %d times - %s (%s):"
                        % (base, len(entries), kind, why))
        for i, entry in enumerate(entries):
            root, scope, via = _parts(entry)[:3]
            problems.append("      <- %s [%s]%s  [sha %s]" % (
                root, scope, (" (" + via + ")") if via else "", digests[i] or "UNREADABLE"))
    return problems


def _selftest_shape_coverage() -> list:
    """[P14 B3] Every shape the guard was measurably blind to, planted, plus the controls.

    Without these the selftest passes on a clean config no matter what the extractor does, so
    every mutation of these fixes SURVIVES and the guard is decorative. The audit demonstrated
    6 of 6 novel shapes reported CLEAN while 3 of 3 enumerated shapes were caught - non-
    extraction was indistinguishable from non-duplication.

    The two CONTROLS matter as much as the positives: making non-.py hooks visible without
    fixing the counting key reported 13 duplicates for one correctly-wired shared runner, and a
    guard that fires on a correct config gets disabled.
    """
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as td:
        hooks = os.path.join(td, "hooks")
        os.makedirs(hooks)
        hermetic = os.path.join(td, "hermetic")
        os.makedirs(hermetic)
        n = [0]

        def script(name, body="x = 1\n"):
            p = os.path.join(hooks, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            return p

        def verdict(cfg):
            n[0] += 1
            p = os.path.join(td, "cfg%d.json" % n[0])
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"hooks": cfg}, fh)
            return "\n".join(audit(p, cwd=hermetic))

        def one(event, entries, matcher=None):
            g = {"hooks": entries}
            if matcher is not None:
                g["matcher"] = matcher
            return {event: [g]}

        js = script("notify.js", "// hook\n")
        out = verdict(one("Stop", [{"command": 'node "%s"' % js},
                                   {"command": 'node "%s"' % js}]))
        if "notify.js" not in out:
            fails.append("a .js hook wired twice is invisible - the sibling guard has "
                         "recognised four hook extensions since v1.2 || " + (out or "(silent)"))

        ps = script("notify.ps1", "# hook\n")
        out = verdict(one("Stop", [{"command": 'pwsh -NoProfile -File "%s"' % ps},
                                   {"command": 'powershell -File "%s"' % ps}]))
        if "notify.ps1" not in out:
            fails.append("a .ps1 hook wired twice is invisible || " + (out or "(silent)"))

        sh = script("notify.sh", "# hook\n")
        out = verdict(one("Stop", [{"command": 'bash "%s"' % sh},
                                   {"command": 'sh "%s"' % sh}]))
        if "notify.sh" not in out:
            fails.append("a .sh hook wired twice is invisible || " + (out or "(silent)"))

        out = verdict(one("Stop", [{"command": "python -m hooks.rate_prompt"},
                                   {"command": "python -m hooks.rate_prompt"}]))
        if "rate_prompt.py" not in out:
            fails.append("`python -m` module form is invisible - no .py token exists in the "
                         "command string at all || " + (out or "(silent)"))

        # a dispatcher whose FILENAME does not contain 'dispatcher', fanning out to a module
        # that is ALSO wired directly: two executions on one event
        # The fixtures below carry a real `import_module` call. That is not scaffolding to
        # satisfy the checker - it is what makes them DISPATCHERS. Before 2026-08-13 they were
        # a bare roster and nothing else, i.e. a file that declares sub-hooks and cannot
        # possibly run one, so they also passed for any file with an ALL-CAPS tuple of strings.
        # The property under test is unchanged and still asserted: NAMING (the filename, the
        # variable name) must not decide detection.
        w = script("widget.py")
        fan = script("fanout.py",
                     "import importlib\n"
                     "HOOKS = ((\"widget\", \"w\"),)\n"
                     "for _m, _ in HOOKS:\n"
                     "    importlib.import_module(_m)\n")
        out = verdict(one("Stop", [{"command": 'python "%s"' % w},
                                   {"command": 'python "%s"' % fan}]))
        if "widget.py" not in out:
            fails.append("a dispatcher whose filename lacks the substring 'dispatcher' fans "
                         "out invisibly - a name test standing in for a behaviour test || "
                         + (out or "(silent)"))

        w2 = script("gadget.py")
        pipe = script("stop_dispatcher2.py",
                      "import importlib\n"
                      "MODULES = ((\"gadget\", \"g\"),)\n"
                      "for _m, _ in MODULES:\n"
                      "    importlib.import_module(_m)\n")
        out = verdict(one("Stop", [{"command": 'python "%s"' % w2},
                                   {"command": 'python "%s"' % pipe}]))
        if "gadget.py" not in out:
            fails.append("a dispatcher whose module list is not literally named HOOKS fans out "
                         "invisibly || " + (out or "(silent)"))

        # ---- CONTROLS: a guard that flags these is unusable ----

        # [PGG-PS fallout] A VOCABULARY tuple is not a fan-out roster. This is the exact shape
        # that broke integration scenario C2 on 2026-08-13: `piped_gate_guard` holds
        # STATUS_EATERS and PS_SAFE_ALIASES, both ALL-CAPS tuples of strings, and `sort` is in
        # BOTH - so a phantom module `sort.py` was reported as "registered 2 times" by a hook
        # whose entire job is to be silent on a clean install. The two tuples here reproduce
        # that collision exactly; the file imports NOTHING, so it dispatches nothing.
        vocab = script("vocabulary.py",
                       "EATERS = (\"head\", \"tail\", \"sort\")\n"
                       "SAFE_ALIASES = (\"sort\", \"tee\")\n")
        out = verdict(one("Stop", [{"command": 'python "%s"' % vocab}]))
        if out.strip():
            fails.append("a module-level tuple of ORDINARY STRINGS was read as a dispatcher "
                         "fan-out roster, so a hook that imports nothing was reported as "
                         "double-registering a module that does not exist || " + out)

        solo = script("solo.py")
        out = verdict({"Stop": [{"hooks": [{"command": 'python "%s"' % solo}]}],
                       "PreToolUse": [{"hooks": [{"command": 'python "%s"' % solo}]}]})
        if "solo.py" in out:
            fails.append("the same hook under two DIFFERENT events was reported as a duplicate; "
                         "neither double-fires || " + out)

        runner = script("runner.js", "// shared\n")
        out = verdict(one("Stop", [{"command": 'node "%s" --alpha' % runner},
                                   {"command": 'node "%s" --beta' % runner},
                                   {"command": 'node "%s" --gamma' % runner}]))
        if "runner.js" in out:
            fails.append("a shared runner invoked with DIFFERENT flags was reported as a "
                         "duplicate - it does different work each time, and this false alarm "
                         "fired 13 times on the author's real config || " + out)
    return fails


def _selftest_malformed_command() -> list:
    """[P13 C6] A non-string `command` must be REPORTED, and must not silence the rest."""
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as td:
        real = os.path.join(td, "rate_prompt.py")
        with open(real, "w", encoding="utf-8") as fh:
            fh.write("x = 1" + chr(10))
        cfg = os.path.join(td, "settings.json")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [
                {"command": {"not": "a string"}},
                {"command": real},
                {"command": real},
            ]}]}}, fh)
        try:
            out = chr(10).join(audit(cfg, cwd=td))
        except Exception as e:
            fails.append("audit() raised on a non-string command: %r" % (e,))
            return fails
        if "not a string" not in out:
            fails.append("a malformed hook command was neither reported nor named: %r" % (out,))
        if "rate_prompt.py" not in out:
            fails.append("one malformed entry silenced the duplicates the hook could still "
                         "see - a checker that goes quiet looks exactly like a clean bill "
                         "of health: %r" % (out,))
    return fails


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
        # carries a real import_module call, because that is what makes it a DISPATCHER - see
        # the note beside the fanout.py fixture. Without it this file declares sub-hooks it
        # could never run, and every ALL-CAPS tuple of strings anywhere would match it.
        open(os.path.join(b, "x_dispatcher.py"), "w", encoding="utf-8").write(
            'import importlib\nHOOKS = (\n    ("widget", "w"),\n)\n'
            'for _m, _ in HOOKS:\n    importlib.import_module(_m)\n')
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
        # [D9] HERMETIC cwd. audit() merges <cwd>/.claude/settings*.json, and every fixture
        # call left cwd defaulting to os.getcwd() - so each assertion ran against the fixture
        # PLUS whatever real project config the process happened to sit in. Both directions
        # were reproduced: a cwd whose own config wires one hook twice made a correct fixture
        # FAIL, and a mutation that breaks the SAME-FILE/DIFFERENT-PROGRAMS classification
        # still printed SELFTEST PASS from that cwd, because the checks are substring tests
        # over the merged report. A test whose verdict depends on where it was launched is
        # measuring the machine, not the code.
        hermetic = os.path.join(td, "no_project_config")
        os.makedirs(hermetic, exist_ok=True)
        # An ambient project whose OWN config wires a hook twice, used as the process cwd for
        # every fixture below. Without a genuinely noisy cwd the hermeticity fix is untestable
        # on a tidy machine: removing it changes nothing and the mutation survives. Now any
        # call that forgets a hermetic cwd picks up `ambient_hook.py` and gets caught.
        noisy = os.path.join(td, "noisy_project")
        os.makedirs(os.path.join(noisy, ".claude"), exist_ok=True)
        loud = os.path.join(a, "ambient_hook.py")
        with open(loud, "w", encoding="utf-8") as fh:
            fh.write("amb = 1\n")
        with open(os.path.join(noisy, ".claude", "settings.json"), "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [{"command": loud}, {"command": loud}]}]}}, fh)
        _real_cwd = os.getcwd()
        # [P13 C7] try/finally. The restore used to sit ~130 lines below, on the SUCCESS path
        # only, so any failure in between left the process cwd inside a TemporaryDirectory -
        # whose cleanup then raised, replacing the selftest's own failure report with an
        # unrelated traceback. The report is destroyed exactly when it matters.
        os.chdir(noisy)
        try:
            out = "\n".join(audit(settings, cwd=hermetic))
            if "ambient_hook.py" in out:
                fails.append("audit() leaked the invoking cwd's project config despite an "
                             "explicit hermetic cwd")
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
                # cwd defaults to a directory with NO .claude, never os.getcwd() - see D9 above.
                out_ = "\n".join(audit(p, cwd=cwd or hermetic))
                if "ambient_hook.py" in out_:
                    fails.append("_audit_of leaked the invoking cwd's project config - the "
                                 "fixture verdict depends on where the test was launched (D9)")
                return out_, p

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

            # (6b) [B3-P] PLUGINS are a layer too, and were not read at all - so a hook wired
            # both by a plugin and by settings.json reported CLEAN. Same premise as (6), one
            # layer up: an EXTENSION roster became a LAYER roster.
            phome = os.path.join(td, "phome")
            plugged = os.path.join(a, "plugged.py")
            with open(plugged, "w", encoding="utf-8") as fh:
                fh.write("pl = 1\n")
            pdir = os.path.join(phome, "plugins", "cache", "mkt", "alpha", "1.0", "hooks")
            os.makedirs(pdir, exist_ok=True)
            with open(os.path.join(pdir, "hooks.json"), "w", encoding="utf-8") as fh:
                json.dump({"hooks": {"Stop": [{"hooks": [{"command": plugged}]}]}}, fh)
            psettings = os.path.join(phome, "settings.json")
            with open(psettings, "w", encoding="utf-8") as fh:
                json.dump({"enabledPlugins": {"alpha@mkt": True, "beta@mkt": False},
                           "hooks": {"Stop": [{"hooks": [{"command": plugged}]}]}}, fh)
            out6b = "\n".join(audit(psettings, cwd=hermetic))
            if "plugged.py" not in out6b:
                fails.append("a hook wired by an ENABLED PLUGIN and by settings.json was "
                             "invisible - plugins are not a layer || " +
                             (out6b or "(nothing reported)")[:200])

            # (6c) THE NEGATIVE CONTROL, and it is the load-bearing half. A DISABLED plugin's
            # hooks never fire. Reporting them would invent duplicates on a correct config -
            # measured 2026-08-06: 6 of 7 plugin hooks.json on the author's machine belong to
            # disabled plugins. That is B3-FP, whose lesson is that a guard which false-alarms
            # gets switched off, which is strictly worse than no guard at all.
            offdir = os.path.join(phome, "plugins", "marketplaces", "mkt", "plugins", "beta",
                                  "hooks")
            os.makedirs(offdir, exist_ok=True)
            offonly = os.path.join(a, "disabled_only.py")
            with open(offonly, "w", encoding="utf-8") as fh:
                fh.write("d = 1\n")
            with open(os.path.join(offdir, "hooks.json"), "w", encoding="utf-8") as fh:
                json.dump({"hooks": {"Stop": [{"hooks": [{"command": offonly},
                                                         {"command": offonly}]}]}}, fh)
            out6c = "\n".join(audit(psettings, cwd=hermetic))
            if "disabled_only.py" in out6c:
                fails.append("a DISABLED plugin's double-wiring was reported as a duplicate. "
                             "Its hooks never fire, so this is a false alarm on a correct "
                             "config || " + out6c[:240])

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

            # (8) [D9] HERMETICITY, asserted directly. Checking that the fixtures pass is not the
            # same as checking they are isolated: on a machine whose cwd happens to hold a clean
            # config, dropping the hermetic cwd changes nothing and the mutation survives. So build
            # an ambient project that DOES wire a hook twice, run a CLEAN fixture from inside it,
            # and require the report to stay clean. If the cwd layer leaks, this fails.
            clean_p = os.path.join(td, "clean_fixture.json")
            with open(clean_p, "w", encoding="utf-8") as fh:
                json.dump({"hooks": {"Stop": [{"hooks": [{"command": os.path.join(a, "solo.py")}]}]}},
                          fh)
            leaked = "\n".join(audit(clean_p, cwd=hermetic))
            if leaked.strip():
                fails.append("hermetic fixture was not clean: " + leaked[:160])
            ambient = "\n".join(audit(clean_p, cwd=noisy))
            if "ambient_hook.py" not in ambient:
                fails.append("the ambient-project fixture is not actually noisy - this test "
                             "cannot detect a cwd leak, so it proves nothing")
            from_noisy = "\n".join(audit(clean_p, cwd=hermetic))   # cwd IS noisy for this block
            if from_noisy.strip():
                fails.append("selftest is NOT hermetic - launching from a project whose own "
                             "config wires a hook twice contaminated a clean fixture: "
                             + from_noisy[:160])
        finally:
            # [P13 C7] Restore on EVERY exit path. The restore used to sit
            # only on the success path below, so the `return 1` that reports a
            # FAILING selftest left the process cwd inside a TemporaryDirectory -
            # whose cleanup then raised, replacing the failure report with an
            # unrelated traceback. The report is destroyed exactly when it matters.
            os.chdir(_real_cwd)

        fails += _selftest_malformed_command()
        fails += _selftest_shape_coverage()
        if fails:
            for f in fails:
                print("SELFTEST FAIL: " + f)
            return 1

        # main() must actually REACH audit() and PRINT. Testing audit() alone leaves the
        # reporting path uncovered - and a late-bound default silently made SETTINGS
        # un-overridable, so this exact check failed to produce output on first attempt.
        import contextlib
        import io as _io
        # Patch the ONE authority, in the module that owns it. Rebinding a local alias here
        # left settings_layers() still reading hook_layers.SETTINGS - a split brain that made
        # main() audit the REAL config and print nothing. That is A9's lesson exactly: a
        # canonicalisation is only canonical inside the program that defines it.
        real, hook_layers.SETTINGS = hook_layers.SETTINGS, settings
        buf = _io.StringIO()
        # main() correctly resolves the project layer from os.getcwd() - that IS the production
        # behaviour - so the TEST must control the cwd rather than the code. Without this the
        # check merged the launching project's real .claude/settings.json (D9).
        real_cwd = os.getcwd()
        try:
            os.chdir(hermetic)
            with contextlib.redirect_stdout(buf):
                rc = main()
        finally:
            os.chdir(real_cwd)
            hook_layers.SETTINGS = real
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
