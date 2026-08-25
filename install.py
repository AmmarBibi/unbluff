#!/usr/bin/env python3
"""Installer for unbluff.

Wires the suite into ~/.claude/settings.json and installs its skills (meta-review, source-coverage,
consistency-audit, completeness-audit). Safe by design: it backs up settings.json before writing, writes atomically
(temp file + os.replace, so the live file is never left half-written), is idempotent (re-running
replaces our entries, never duplicates them), refuses to clobber a settings.json it cannot parse,
and supports --dry-run and --uninstall.

The hooks are referenced IN PLACE from this repo, so `git pull` updates them with no re-install.

Usage:
    python install.py                       # install all pieces (4 settings.json entries + skills)
    python install.py --only show_your_proof   # (see --help) install a subset
    python install.py --without rate_prompt    # install everything except one
    python install.py --dry-run             # show exactly what would change; write nothing
    python install.py --uninstall           # remove this suite's entries (backs up first)
    python install.py --no-skill            # skip copying the skills

Stdlib-only, cross-platform (Windows / macOS / Linux), Python 3.8+.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")
SKILLS_DIR = os.path.join(REPO_ROOT, "skills")
# close_skills_guard requires ALL FOUR by name; shipping three would install a hook that
# demands a skill the user never receives.
SKILL_NAMES = ("meta-review", "source-coverage", "consistency-audit", "completeness-audit")

CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
SETTINGS_PATH = os.path.join(CLAUDE_DIR, "settings.json")
SKILLS_DEST_DIR = os.path.join(CLAUDE_DIR, "skills")

ID_PREFIX = "unbluff:"
PY = f'"{sys.executable}"'

# Short group names used by --only / --without, mapped to the event they wire.
GROUP_EVENTS = {"rate_prompt": "UserPromptSubmit",
                "hook_health": "SessionStart",
                "duplicate_check": "SessionStart",
                "stop_dispatcher": "Stop",
                "posttooluse_dispatcher": "PostToolUse",
                "piped_gate": "PreToolUse"}

# Every hook file the suite depends on (each dispatcher imports its sub-hooks in-process).
REQUIRED_HOOKS = ("rate_prompt.py", "hook_health_check.py", "stop_dispatcher.py",
                  "show_your_proof.py", "meta_audit_on_stop.py", "memory_hygiene_guard.py",
                  "fast_test_on_stop.py", "post_tooluse_dispatcher.py", "plan_defer_guard.py",
                  "numbers_match_on_write.py", "duplicate_registration_check.py",
                  "close_skills_guard.py", "usage_snip_prompt.py", "pre_push_gate.py",
                  "timing_claim_guard.py",
                  "piped_gate_guard.py",
                  # [item 10, 2026-08-25] Declared in the FLOOR because the import closure cannot
                  # reach them: hook_health_check imports wired_clone_sanity inside a
                  # `try/except ImportError` so a partial checkout still gets a health line, and
                  # _catches_import_error correctly reads a guarded import as OPTIONAL. The
                  # fallback is right and stays; what is wrong is concluding the file is
                  # therefore expendable - without it the SessionStart machine-sanity check just
                  # stops happening. install.py's own partial-checkout selftest caught this on
                  # the first run (2 of 28 deleted files undetected), which is the floor doing
                  # the one job the roster docstring says only it can do.
                  "wired_clone_sanity.py",
                  "wired_clone_sanity_selftest.py")


def _cmd(script: str) -> str:
    return f'{PY} "{os.path.join(HOOKS_DIR, script)}"'


def shell_tool_matcher() -> str:
    """The PreToolUse matcher, DERIVED from piped_gate_guard's own SHELL_TOOLS.

    [PGG-PS] This was the literal string "Bash", and that is the whole defect: a ROSTER
    standing in for a CONCEPT (a shell), inside the guard built to catch discarded exit
    codes. On Windows PowerShell is the primary shell, so the guard was blind exactly where
    it was needed most - and nothing failed, because nothing asserted the matcher's VALUE.
    tests/test_integration.py compares the set of group IDs and never looks at this string.

    Reading the tuple from the guard means a shell this hook is WIRED for and a shell it can
    REASON about cannot drift apart. The alternative - a second tuple here - is the twin
    roster this repo has dug out four times (REQUIRED_HOOKS, _SH_SITES_REQUIRED, the
    integration count, ROSTER-DERIVE).
    """
    return "|".join(_load_guard_shell_tools())


def _load_guard_shell_tools() -> tuple:
    """piped_gate_guard.SHELL_TOOLS, read from the guard itself. Raises rather than guessing."""
    import importlib.util

    path = os.path.join(HOOKS_DIR, "piped_gate_guard.py")
    spec = importlib.util.spec_from_file_location("_unbluff_piped_gate_guard", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    tools = tuple(getattr(mod, "SHELL_TOOLS", ()))
    if not tools:
        raise ValueError("piped_gate_guard.SHELL_TOOLS is missing or empty - the guard would "
                         "be wired to nothing, which is PGG-PS with a different spelling")
    return tools


def desired_groups() -> dict:
    """The hook groups this suite installs, keyed by event."""
    return {
        "UserPromptSubmit": {
            "hooks": [{"type": "command", "command": _cmd("rate_prompt.py"), "timeout": 10}],
            "id": ID_PREFIX + "rate-prompt",
            "description": "Rate each prompt X/10 and act on a sharpened rewrite (no extra model call).",
        },
        "SessionStart": {
            "matcher": "*",
            # EXPLICIT timeout. Without one these inherit the host's 60s default, and the
            # weekly selftest sweep inside hook_health_check measured 34.7s warm on a fast
            # box - 58% of a budget nobody had declared. The sweep now has its own 25s
            # aggregate budget and is resumable, so this ceiling is headroom, not a target.
            "hooks": [{"type": "command", "command": _cmd("hook_health_check.py"),
                       "timeout": 90},
                      {"type": "command", "command": _cmd("duplicate_registration_check.py"),
                       "timeout": 30},
                      {"type": "command", "command": _cmd("usage_snip_prompt.py"),
                       "timeout": 10}],
            "id": ID_PREFIX + "hook-health",
            "description": "Validate configured hooks resolve; weekly-run each hook's selftest; "
                           "report any hook wired from more than one directory; ask for a usage "
                           "snip before budget-shaped work.",
        },
        "Stop": {
            "matcher": "*",
            "hooks": [{"type": "command", "command": _cmd("stop_dispatcher.py"), "timeout": 300}],
            "id": ID_PREFIX + "stop-dispatcher",
            "description": "Run show-your-proof / meta-audit / memory-hygiene / fast-test in one process.",
        },
        # EXPLICITLY registered. run_selftests derives its gate roster by scanning for a
        # --selftest, which is a BACKSTOP: two real gates were once invisible to name-pattern
        # detection because their filenames did not advertise them. A hook nobody wires is a
        # hook that does not exist, however green its selftest is.
        "PreToolUse": {
            "matcher": shell_tool_matcher(),
            "hooks": [{"type": "command", "command": _cmd("piped_gate_guard.py"),
                       "timeout": 10}],
            "id": ID_PREFIX + "piped-gate",
            "description": "Block a shell command that destroys a GATE's exit status - in sh "
                           "by piping it into head/tail/grep, in PowerShell by truncating it "
                           "with Select-Object -First, which tears the gate down before it "
                           "finishes.",
        },
        "PostToolUse": {
            "matcher": "Edit|Write|MultiEdit",
            "hooks": [{"type": "command", "command": _cmd("post_tooluse_dispatcher.py")},
                      {"type": "command", "command": _cmd("close_skills_guard.py")}],
            "id": ID_PREFIX + "posttooluse-dispatcher",
            "description": "On edits, run plan-defer-guard (optional-forever language) and "
                           "numbers-match (cited numbers vs source data) in one process; and "
                           "verify the close-audit skills actually ran at the real session end.",
        },
    }


def load_settings() -> dict:
    if not os.path.exists(SETTINGS_PATH):
        return {}
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"ERROR: {SETTINGS_PATH} exists but is unreadable/invalid JSON ({e}).\n"
                 f"Fix or move it, then re-run. (Refusing to overwrite it.)")
    if not isinstance(data, dict):
        sys.exit(f"ERROR: {SETTINGS_PATH} is valid JSON but not a JSON object.\n"
                 f"Refusing to overwrite it. Fix or move it, then re-run.")
    return data


def backup_settings() -> "str | None":
    if not os.path.exists(SETTINGS_PATH):
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dest = f"{SETTINGS_PATH}.bak-{stamp}"
    shutil.copy2(SETTINGS_PATH, dest)
    return dest


def _strip_ours(groups: list) -> list:
    """Drop any existing groups this suite previously added (by id prefix)."""
    return [g for g in groups if not (isinstance(g, dict)
            and str(g.get("id", "")).startswith(ID_PREFIX))]


def apply_changes(settings: dict, install: bool, events: set) -> dict:
    hooks = settings.setdefault("hooks", {})
    for event, group in desired_groups().items():
        if event not in events:
            continue  # leave unselected events untouched (non-destructive)
        existing = hooks.get(event)
        existing = existing if isinstance(existing, list) else []
        cleaned = _strip_ours(existing)
        if install:
            cleaned.append(group)
        if cleaned:
            hooks[event] = cleaned
        elif event in hooks:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    return settings


def write_settings(settings: dict) -> None:
    """Atomic write: dump to a temp file in the same dir, fsync, then os.replace."""
    os.makedirs(CLAUDE_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CLAUDE_DIR, prefix=".settings-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SETTINGS_PATH)  # atomic on the same filesystem
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


SKILL_MANIFEST = ".unbluff-manifest.json"


def _read_skill_manifest(dest: str):
    """The relative paths unbluff installed into `dest`, or None if it did not install it.

    None is the load-bearing answer: it means "this directory is not ours", and both install
    and uninstall must then keep their hands off it.
    """
    try:
        with open(os.path.join(dest, SKILL_MANIFEST), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("files"), list):
        return [str(x) for x in data["files"]]
    return None


def _skill_payload(src: str) -> list:
    """Relative paths install would copy from `src` - derived by walking it, not listed."""
    out = []
    for root, _dirs, files in os.walk(src):
        if "__pycache__" in root.replace("\\", "/").split("/"):
            continue
        for fn in files:
            if fn.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(root, fn), src).replace("\\", "/"))
    return sorted(out)


def install_skill(dry_run: bool, dest_root: str = None, src_root: str = None) -> None:
    dest_root = dest_root or SKILLS_DEST_DIR
    src_root = src_root or SKILLS_DIR
    for name in SKILL_NAMES:
        src = os.path.join(src_root, name)
        dest = os.path.join(dest_root, name)
        if not os.path.isdir(src):
            # Not a warning. close_skills_guard is WIRED and requires all four by name, so
            # "skipping" here ships a hook that blocks every close with an unsatisfiable
            # demand. main()'s ENTRY-GUARD check normally catches this first; this is the
            # backstop for any other caller.
            sys.exit(f"ERROR: skill source missing ({src}) - refusing to install a partial set. "
                     f"close_skills_guard requires all of {list(SKILL_NAMES)}.")
        # [SKILLDIR-DESTROY] Never merge into a directory unbluff did not create. `dirs_exist_ok`
        # silently overwrote same-named files inside a skill the user already had - the same
        # class of harm install() has always refused for a foreign pre-push hook, applied
        # nowhere here.
        if os.path.isdir(dest) and _read_skill_manifest(dest) is None:
            sys.exit(f"ERROR: {dest} already exists and was not installed by unbluff "
                     f"(no {SKILL_MANIFEST}). Refusing to overwrite it - move or delete it "
                     f"first if you want unbluff's '{name}' skill.")
        if dry_run:
            print(f"  would copy skill -> {dest}")
            continue
        # Copy the whole skill dir (SKILL.md + any bundled scripts/), not just SKILL.md.
        shutil.copytree(src, dest, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # The manifest is what makes uninstall precise: it removes exactly these paths and
        # leaves anything the user put here afterwards.
        with open(os.path.join(dest, SKILL_MANIFEST), "w", encoding="utf-8") as f:
            json.dump({"files": _skill_payload(src)}, f, indent=2)
        print(f"  copied skill -> {dest}")


def remove_skill(dry_run: bool, dest_root: str = None) -> None:
    dest_root = dest_root or SKILLS_DEST_DIR
    for name in SKILL_NAMES:
        dest = os.path.join(dest_root, name)
        if not os.path.isdir(dest):
            continue
        # [SKILLDIR-DESTROY] rmtree took the WHOLE directory, so uninstalling unbluff deleted a
        # skill the user had before unbluff existed - and `ignore_errors=True` meant it did so
        # in silence. Remove exactly what the manifest says we put there, nothing else.
        files = _read_skill_manifest(dest)
        if files is None:
            print(f"  ! {dest} has no {SKILL_MANIFEST} - NOT unbluff's, leaving it untouched")
            continue
        if dry_run:
            print(f"  would remove {len(files)} file(s) <- {dest}")
            continue
        for rel in files:
            try:
                os.remove(os.path.join(dest, *rel.split("/")))
            except OSError:
                pass
        try:
            os.remove(os.path.join(dest, SKILL_MANIFEST))
        except OSError:
            pass
        # Prune directories that are now empty, deepest first. A directory still holding the
        # user's own files simply survives - which is the entire point.
        for root, _dirs, _files in sorted(os.walk(dest), key=lambda t: -len(t[0])):
            try:
                os.rmdir(root)
            except OSError:
                pass
        if os.path.isdir(dest):
            print(f"  removed {len(files)} unbluff file(s) <- {dest} (kept your other files)")
        else:
            print(f"  removed skill <- {dest}")


def resolve_events(only: str, without: str) -> set:
    """Which events to install, from --only / --without (validated against GROUP_EVENTS)."""
    def parse(s):
        keys = [k.strip() for k in s.split(",") if k.strip()]
        bad = [k for k in keys if k not in GROUP_EVENTS]
        if bad:
            sys.exit(f"ERROR: unknown group(s) {bad}. Valid: {', '.join(GROUP_EVENTS)}")
        return keys
    if only:
        return {GROUP_EVENTS[k] for k in parse(only)}
    chosen = set(GROUP_EVENTS.values())
    for k in parse(without):
        chosen.discard(GROUP_EVENTS[k])
    return chosen


def _resolves_outside(name: str, blocked: set) -> bool:
    """True if `name` imports from OUTSIDE the hook dirs - i.e. stdlib or third-party.

    The hook directories are removed from `sys.path` for the lookup, which is the whole trick:
    with them on the path a PRESENT local module resolves and looks external, and the guard
    would stop requiring exactly the files it is supposed to be protecting.
    """
    import importlib.util
    saved = sys.path[:]
    sys.path = [p for p in sys.path
                if os.path.normcase(os.path.abspath(p or ".")) not in blocked]
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError, TypeError):
        return False
    finally:
        sys.path = saved


# The two hooks that load sub-hooks by NAME at runtime. Their rosters are the one part of the
# wiring an import walk cannot see, so they are read explicitly - and READ, not restated here.
_DISPATCHERS = ("stop_dispatcher.py", "post_tooluse_dispatcher.py")


def dispatcher_subhooks(hooks_dir: str) -> set:
    """Module files the dispatchers load by `importlib.import_module(<string>)`, DERIVED.

    [ROSTER-DERIVE] These 7 modules are invisible to `_import_closure`: a string handed to
    importlib is not an import statement, so an AST import walk cannot follow it. They reached
    the roster only because someone had typed them into `REQUIRED_HOOKS` - a DECLARED roster
    behind a docstring claiming the set was DERIVED, which is INSTALL-TAUTOLOGY's exact shape.
    Adding an 8th sub-hook and forgetting the tuple gave: `missing_hook_files() == []`,
    `--selftest` rc 0, and a dispatcher exiting 0 in silence while the hook never ran again.

    Both `HOOKS` tuples are literal tuples of literal strings, so the AST answers directly.
    A dispatcher that is itself missing yields nothing here - correctly, because its own
    absence is the louder failure and `REQUIRED_HOOKS` still reports it.
    """
    import ast          # function-local, matching _import_closure's existing idiom
    found = set()
    for disp in _DISPATCHERS:
        try:
            with open(os.path.join(hooks_dir, disp), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "HOOKS" for t in node.targets):
                continue
            for elt in getattr(node.value, "elts", []) or []:
                parts = getattr(elt, "elts", None) or [elt]
                first = parts[0] if parts else None
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    found.add(first.value + ".py")
    return found


def missing_hook_files(hooks_dir: str) -> list:
    """Hook files the installed configuration needs but which are NOT present.

    DERIVED FROM THE IMPORT CLOSURE of the wired entry points, UNIONED with the dispatchers'
    own sub-hook rosters (read from their ASTs) - never from a directory listing, and never
    from a hand-typed name. The second half is not decoration: 7 of the 25 hooks are loaded by
    `importlib.import_module(<string>)` and are structurally invisible to an import walk, so
    while the seed was `REQUIRED_HOOKS` alone this docstring's first word was false.

    [INSTALL-TAUTOLOGY, fixed 2026-08-09] The previous implementation globbed `hooks/*.py` into
    the required set and then asserted that each of those files exists. Those two statements are
    the same statement: a file the glob just found is a file that exists, so the globbed portion
    could never contribute a single missing name and the guard's real coverage was the hardcoded
    `REQUIRED_HOOKS` floor alone - 16 of 25 files, leaving 9 unguarded, 5 of them imported by
    production hooks. Deleting `hooks/transcript_util.py` let install print "Done." while
    `close_skills_guard` died with ModuleNotFoundError on the user's next turn. The comment above
    it called the check "DERIVED", which is precisely why nobody looked again.

    A directory listing can only ever answer "what is here". The question is "what does the code
    NEED", and only the imports know that - so the roster is walked out of the AST, and a module
    that fails to resolve with the hook dirs off `sys.path` is a LOCAL file that is missing,
    which is the one case a listing structurally cannot report.
    """
    # [ROSTER-DERIVE] Seed = the declared floor UNION the dispatchers' own rosters, read out of
    # their ASTs. `REQUIRED_HOOKS` stays as a floor rather than being deleted: it is the only
    # thing covering a dispatcher whose file is itself missing, when nothing can be derived
    # from it. The union is what makes the docstring above true.
    seed = tuple(sorted(set(REQUIRED_HOOKS) | dispatcher_subhooks(hooks_dir)))
    required = _import_closure(hooks_dir, seed)
    return [s for s in sorted(required) if not os.path.exists(os.path.join(hooks_dir, s))]


def _catches_import_error(handler) -> bool:
    """True if this `except` clause would swallow a failed import.

    A bare `except:` counts - it catches everything, so the import under it is optional
    whatever the author intended.
    """
    import ast
    names = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
    t = handler.type
    if t is None:
        return True
    if isinstance(t, ast.Name):
        return t.id in names
    if isinstance(t, ast.Tuple):
        return any(isinstance(e, ast.Name) and e.id in names for e in t.elts)
    return False


def _import_closure(src_dir: str, seeds, lazy_optional: bool = False) -> set:
    """`seeds` plus every local .py they import, transitively. ONE implementation, two callers.

    Shared by the hook roster and the skill-script roster because they are the same question
    asked of two directories, and a second copy of this walk is the twin defect this repo hunts.
    """
    import ast
    blocked = {os.path.normcase(os.path.abspath(src_dir)),
               os.path.normcase(os.path.abspath(HOOKS_DIR))}
    required = set(seeds)
    seen = set()
    queue = sorted(required)
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            with open(os.path.join(src_dir, name), encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue   # a file that is missing or unparsable is REPORTED by the caller
        # An import guarded by try/except ImportError is OPTIONAL BY DEFINITION and must never
        # be required. skills/consistency-audit/scripts/extract.py does exactly this for the
        # document readers (`try: import docx / except ImportError:`), which is correct design -
        # the tool degrades instead of refusing to start.
        #
        # MEASURED FAILURE, 2026-08-09 -> caught by CI on 2026-08-11: without this, the guard
        # asked `find_spec("docx")`, got None on a machine that does not have python-docx, and
        # reported `consistency-audit/scripts/docx.py` as a MISSING LOCAL FILE. It invented
        # three files that never existed and turned all 16 CI jobs red.
        #
        # It passed locally because THIS machine has those libraries installed, so the same code
        # took the opposite branch. That is the environment-dependence class - the probe below
        # is therefore synthetic, so it gives the same answer on every box.
        optional = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) and any(_catches_import_error(h)
                                                 for h in node.handlers):
                for stmt in node.body:
                    for sub in ast.walk(stmt):
                        if isinstance(sub, (ast.Import, ast.ImportFrom)):
                            optional.add(id(sub))
        # SECOND INSTANCE OF THE SAME CLASS, 2026-08-24, found by CI on the v1.4.0 PR. The
        # try/except rule above fixed `docx` and only `docx`. The PDF readers added for the
        # scanned-PDF fix import `fitz` (extract.py:157) and `pdfminer.high_level` (:163) at the
        # top of their own functions, with the failure handled by the CALLER's reader loop
        # (:172) rather than by a lexical `except ImportError` - an equally correct optional-
        # dependency idiom that the rule above does not recognise. So both fell through to
        # `_resolves_outside`, which asks find_spec: TRUE on the author's box (PyMuPDF and
        # pdfminer installed), FALSE on every runner. install.py then demanded
        # `consistency-audit/scripts/fitz.py` and `pdfminer.py` - files that exist nowhere - and
        # `sys.exit`ed. 15 of 17 CI jobs red, and any USER without both libraries could not
        # install unbluff at all.
        #
        # A LAZY IMPORT IS OPTIONAL BY CONVENTION, and the convention is checked, not assumed:
        # bundled siblings are imported at MODULE level in this repo (audit.py:37-38 `import
        # extract` / `import sources`), while every function-body import in skills/ is stdlib or
        # a third-party reader. Restricting the requirement to module-level imports removes the
        # find_spec environment dependence from the case that actually bites, instead of adding
        # a third special case for the next idiom. Both directions are pinned synthetically in
        # this file's --selftest, so the answer no longer depends on what is installed.
        # NOT global, and the first attempt at it was global and WRONG. Applied to hooks/ this
        # rule immediately hid 4 of 26 deleted files - `fast_test_disclosure.py`,
        # `fast_test_on_stop_selftest.py`, `hook_health_check_selftest.py`,
        # `pre_push_gate_selftest.py` - because the Stop and PostToolUse dispatchers import
        # their sub-hooks lazily BY DESIGN, and those are required local files. install.py's own
        # partial-checkout selftest caught it on the first run, which is the fix creating a new
        # instance of the class it fixes, caught by this repo's own guard.
        #
        # So the convention is declared per-population instead of assumed for both:
        #   hooks/   - lazy imports are REQUIRED (dispatchers load siblings inside functions)
        #   skills/  - lazy imports are OPTIONAL (siblings at module level, readers inside
        #              functions), so `lazy_optional=True` at that call site only.
        # One implementation, two callers, one explicit parameter - rather than two walks.
        if lazy_optional:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for sub in ast.walk(node):
                        if isinstance(sub, (ast.Import, ast.ImportFrom)):
                            optional.add(id(sub))

        mods = []
        for node in ast.walk(tree):   # module-level imports only; see the two rules above
            if id(node) in optional:
                continue
            if isinstance(node, ast.Import):
                mods += [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                mods.append(node.module.split(".")[0])
        for m in mods:
            cand = m + ".py"
            if cand in required or _resolves_outside(m, blocked):
                continue
            required.add(cand)
            queue.append(cand)
    return required


def missing_skill_files(skills_dir: str) -> list:
    """Skill files install.py will LAND on the user's machine but which are not present.

    [ENTRY-GUARD, the sibling of INSTALL-TAUTOLOGY - the ledger says fix them together]
    `install_skill()` printed "! skill source missing; skipping" and CONTINUED, so a checkout
    missing a skill directory installed cleanly and exited 0 - and then `close_skills_guard`,
    one of the eight WIRED hooks, demanded all four skills by name and blocked every session
    close with a demand the user could not satisfy. A warning is not a guard.

    Derived, and deliberately NOT from a directory listing: the required scripts are the ones a
    `SKILL.md` TELLS THE USER TO RUN, plus their import closure. Globbing `scripts/*.py` would
    reproduce INSTALL-TAUTOLOGY exactly - it would only ever find the files that are there.
    SKILL.md names `scripts/audit.py`; `audit.py` imports `extract` and `sources`; all three are
    therefore required, and none of the three is named in any hand-written list.
    """
    import re
    missing = []
    for name in SKILL_NAMES:
        md = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.exists(md):
            missing.append(os.path.join(name, "SKILL.md"))
            continue
        try:
            with open(md, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        seeds = sorted(set(re.findall(r"scripts/([A-Za-z0-9_]+\.py)", text)))
        if not seeds:
            continue
        scripts_dir = os.path.join(skills_dir, name, "scripts")
        # lazy_optional: a skill's bundled siblings are imported at module level (audit.py's
        # `import extract` / `import sources`); its document readers are imported inside the
        # function that uses them and are optional by design. Without this, `import fitz` and
        # `from pdfminer.high_level import ...` were demanded as scripts/fitz.py and
        # scripts/pdfminer.py, and install refused to run for any user lacking both libraries.
        for rel in sorted(_import_closure(scripts_dir, seeds, lazy_optional=True)):
            if not os.path.exists(os.path.join(scripts_dir, rel)):
                missing.append(os.path.join(name, "scripts", rel))
    return missing


def selftest() -> int:
    """Delegates to the sibling suite (see install_selftest.py).

    Split out 2026-08-24 so this file returns under the 800-line ratchet rather than taking the
    re-record loophole the size baseline explicitly names.
    """
    import install_selftest as _s
    return _s.selftest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Install unbluff into ~/.claude")
    ap.add_argument("--selftest", action="store_true",
                    help="verify the partial-checkout guard; exit 1 on failure")
    ap.add_argument("--dry-run", action="store_true", help="show changes without writing")
    ap.add_argument("--uninstall", action="store_true", help="remove this suite's entries")
    ap.add_argument("--no-skill", action="store_true", help="do not install/remove the skills")
    ap.add_argument("--only", default="", metavar="a,b",
                    help="install only these groups: " + ", ".join(GROUP_EVENTS))
    ap.add_argument("--without", default="", metavar="a,b",
                    help="install every group except these")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.only and args.without:
        sys.exit("ERROR: use --only or --without, not both.")

    install = not args.uninstall
    # Uninstall always sweeps every event; install honors --only/--without.
    events = set(GROUP_EVENTS.values()) if not install else resolve_events(args.only, args.without)

    verb = "Installing" if install else "Uninstalling"
    print(f"{verb} unbluff")
    print(f"  repo:     {REPO_ROOT}")
    print(f"  settings: {SETTINGS_PATH}")
    if install and events != set(GROUP_EVENTS.values()):
        print(f"  groups:   {sorted(events)}")

    # Sanity: the hook files must exist before we point settings at them.
    if install:
        missing = missing_hook_files(HOOKS_DIR)
        if missing:
            sys.exit(f"ERROR: missing hook files in {HOOKS_DIR}: {missing}\n"
                     f"(Partial checkout? The Stop and PostToolUse dispatchers import their sub-hooks.)")
        # ENTRY-GUARD: the skills are the OTHER thing install.py lands on the user's machine
        # (R1 clause 4). Missing ones used to warn and continue, which installs
        # close_skills_guard demanding a skill the user never received.
        if not args.no_skill:
            missing_skills = missing_skill_files(SKILLS_DIR)
            if missing_skills:
                sys.exit(f"ERROR: missing skill files in {SKILLS_DIR}: {missing_skills}\n"
                         f"(Partial checkout? close_skills_guard requires all of "
                         f"{list(SKILL_NAMES)} and would block every session close.)")

    settings = load_settings()
    updated = apply_changes(json.loads(json.dumps(settings)), install, events)  # work on a copy

    if args.dry_run:
        print("\n--dry-run: no files will be written. Planned settings.json 'hooks':\n")
        print(json.dumps(updated.get("hooks", {}), indent=2))
        if not args.no_skill:
            install_skill(dry_run=True) if install else remove_skill(dry_run=True)
        print("\nRe-run without --dry-run to apply.")
        return 0

    backup = backup_settings()
    if backup:
        print(f"  backed up settings -> {backup}")
    write_settings(updated)
    print(f"  wrote settings ({'added' if install else 'removed'} {len(events)} hook group(s))")

    if not args.no_skill:
        install_skill(dry_run=False) if install else remove_skill(dry_run=False)

    print("\nDone. Restart Claude Code (or start a new session) for changes to take effect.")
    if install:
        print("Tips:")
        print("  - Disable prompt rating without uninstalling: set env CLAUDE_RATE_PROMPTS=off")
        print("  - Per-project fast tests: add .claude/fast-test.cmd (see README)")
        print("  - Verify: python hooks/hook_health_check.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
