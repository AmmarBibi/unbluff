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
                  "piped_gate_guard.py")


def _cmd(script: str) -> str:
    return f'{PY} "{os.path.join(HOOKS_DIR, script)}"'


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
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": _cmd("piped_gate_guard.py"),
                       "timeout": 10}],
            "id": ID_PREFIX + "piped-gate",
            "description": "Block a Bash command that pipes a GATE into head/tail/grep, "
                           "because the pipeline returns the last command's exit status and "
                           "the gate's real result is discarded.",
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


def install_skill(dry_run: bool) -> None:
    for name in SKILL_NAMES:
        src = os.path.join(SKILLS_DIR, name)
        dest = os.path.join(SKILLS_DEST_DIR, name)
        if not os.path.isdir(src):
            # Not a warning. close_skills_guard is WIRED and requires all four by name, so
            # "skipping" here ships a hook that blocks every close with an unsatisfiable
            # demand. main()'s ENTRY-GUARD check normally catches this first; this is the
            # backstop for any other caller.
            sys.exit(f"ERROR: skill source missing ({src}) - refusing to install a partial set. "
                     f"close_skills_guard requires all of {list(SKILL_NAMES)}.")
        if dry_run:
            print(f"  would copy skill -> {dest}")
            continue
        # Copy the whole skill dir (SKILL.md + any bundled scripts/), not just SKILL.md.
        shutil.copytree(src, dest, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"  copied skill -> {dest}")


def remove_skill(dry_run: bool) -> None:
    for name in SKILL_NAMES:
        dest = os.path.join(SKILLS_DEST_DIR, name)
        if not os.path.isdir(dest):
            continue
        if dry_run:
            print(f"  would remove skill <- {dest}")
            continue
        shutil.rmtree(dest, ignore_errors=True)
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


def missing_hook_files(hooks_dir: str) -> list:
    """Hook files the installed configuration needs but which are NOT present.

    DERIVED FROM THE IMPORT CLOSURE of the wired entry points - never from a directory listing.

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
    required = _import_closure(hooks_dir, REQUIRED_HOOKS)
    return [s for s in sorted(required) if not os.path.exists(os.path.join(hooks_dir, s))]


def _import_closure(src_dir: str, seeds) -> set:
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
        mods = []
        for node in ast.walk(tree):   # ast.walk, so imports nested in functions count too
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
        for rel in sorted(_import_closure(scripts_dir, seeds)):
            if not os.path.exists(os.path.join(scripts_dir, rel)):
                missing.append(os.path.join(name, "scripts", rel))
    return missing


def selftest() -> int:
    """Verify the partial-checkout guard actually detects a partial checkout.

    install.py had NO selftest at all - the most user-facing file in the repo, the one a user
    literally runs, was a registered gate nowhere. That is why the defect below survived every
    review: nothing ever asked this file a question.
    """
    fails = []
    checked = 0
    with tempfile.TemporaryDirectory() as td:
        scratch = os.path.join(td, "hooks")
        shutil.copytree(HOOKS_DIR, scratch,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        # A full checkout must be clean, or every case below is meaningless.
        base = missing_hook_files(scratch)
        if base:
            fails.append("a COMPLETE hooks/ reported missing files %r - the guard's baseline is "
                         "broken, so nothing it says about a partial checkout can be trusted"
                         % (base,))

        # DERIVED, not a hand-picked victim: delete each hooks/*.py in turn and require the
        # guard to name it. A roster-shaped guard that is only ever probed with a name already
        # ON its roster proves nothing about the names that are not.
        names = sorted(f for f in os.listdir(scratch) if f.endswith(".py"))
        undetected = []
        for name in names:
            path = os.path.join(scratch, name)
            with open(path, "rb") as f:
                body = f.read()
            os.remove(path)
            try:
                checked += 1
                if name not in missing_hook_files(scratch):
                    undetected.append(name)
            finally:
                with open(path, "wb") as f:
                    f.write(body)
        if undetected:
            fails.append("the partial-checkout guard did NOT detect %d of %d deleted hook "
                         "file(s): %r. install would print 'Done.' over a checkout that cannot "
                         "run - the dispatchers import these at runtime"
                         % (len(undetected), len(names), undetected))

        # The sys.path blocking in _resolves_outside, pinned by the ONE case where it decides
        # the answer. For a DELETED file the blocking is inert - find_spec misses it either way -
        # so a probe that only deletes leaves that code unpinned, which is how unpinned code
        # ships. It matters TRANSITIVELY: with the hooks dir on sys.path and no blocking, a
        # PRESENT intermediate resolves as "external", is never traversed, and everything
        # reachable only through it drops out of the required set silently.
        #
        # Chain used, derived by picking a leaf reached only via present intermediates:
        # a wired hook -> capped_report -> cap_shapes -> cap_types.
        leaf = "cap_types.py"
        if os.path.exists(os.path.join(scratch, leaf)):
            with open(os.path.join(scratch, leaf), "rb") as f:
                body = f.read()
            os.remove(os.path.join(scratch, leaf))
            sys.path.insert(0, scratch)     # the state that makes the blocking load-bearing
            try:
                checked += 1
                if leaf not in missing_hook_files(scratch):
                    fails.append("with the hooks dir ON sys.path, a transitively-required file "
                                 "(%s, reached via capped_report -> cap_shapes) went UNDETECTED "
                                 "- the present intermediates resolved as external and were "
                                 "never traversed" % leaf)
            finally:
                sys.path.remove(scratch)
                with open(os.path.join(scratch, leaf), "wb") as f:
                    f.write(body)
        else:
            fails.append("the sys.path-blocking probe could not find its anchor %r - re-derive "
                         "the chain rather than leaving this case silently unrun" % leaf)

    # ENTRY-GUARD: the same probe against the OTHER thing install.py lands - the skills.
    skill_checked = 0
    with tempfile.TemporaryDirectory() as td:
        sk = os.path.join(td, "skills")
        shutil.copytree(SKILLS_DIR, sk,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if missing_skill_files(sk):
            fails.append("a COMPLETE skills/ reported missing files %r - baseline broken"
                         % (missing_skill_files(sk),))
        # DERIVED: every SKILL.md, and every bundled script reachable from one, deleted in turn.
        victims = []
        for name in SKILL_NAMES:
            victims.append(os.path.join(sk, name, "SKILL.md"))
            sdir = os.path.join(sk, name, "scripts")
            if os.path.isdir(sdir):
                victims += [os.path.join(sdir, f) for f in sorted(os.listdir(sdir))
                            if f.endswith(".py")]
        undetected_s = []
        for path in victims:
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                body = f.read()
            os.remove(path)
            try:
                skill_checked += 1
                if not missing_skill_files(sk):
                    undetected_s.append(os.path.relpath(path, sk))
            finally:
                with open(path, "wb") as f:
                    f.write(body)
        if undetected_s:
            fails.append("the skill guard did NOT detect %d of %d deleted skill file(s): %r. "
                         "install would exit 0 while close_skills_guard - a WIRED hook - "
                         "demands all of %r and blocks every session close"
                         % (len(undetected_s), len(victims), undetected_s, list(SKILL_NAMES)))

    # DENOMINATOR, printed: a guard probed with zero cases is indistinguishable from a guard
    # that passed, which is the failure this whole repo is about.
    print("  [install-guard] %d hook + %d skill deleted-file case(s) checked"
          % (checked, skill_checked))
    if not skill_checked:
        fails.append("the skill-guard probe ran ZERO cases - it is checking nothing")
    if not checked:
        fails.append("the partial-checkout probe ran ZERO cases - it is checking nothing")
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


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
