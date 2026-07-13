#!/usr/bin/env python3
"""Installer for unbluff.

Wires the suite into ~/.claude/settings.json and installs the meta-review skill. Safe by design:
it backs up settings.json before writing, writes atomically (temp file + os.replace, so the live
file is never left half-written), is idempotent (re-running replaces our entries, never duplicates
them), refuses to clobber a settings.json it cannot parse, and supports --dry-run and --uninstall.

The hooks are referenced IN PLACE from this repo, so `git pull` updates them with no re-install.

Usage:
    python install.py                       # install all 8 pieces (3 settings.json entries)
    python install.py --only show_your_proof   # (see --help) install a subset
    python install.py --without rate_prompt    # install everything except one
    python install.py --dry-run             # show exactly what would change; write nothing
    python install.py --uninstall           # remove this suite's entries (backs up first)
    python install.py --no-skill            # skip copying the meta-review skill

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
SKILL_SRC = os.path.join(REPO_ROOT, "skills", "meta-review")

CLAUDE_DIR = os.path.join(os.path.expanduser("~"), ".claude")
SETTINGS_PATH = os.path.join(CLAUDE_DIR, "settings.json")
SKILL_DEST = os.path.join(CLAUDE_DIR, "skills", "meta-review")

ID_PREFIX = "unbluff:"
PY = f'"{sys.executable}"'

# Short group names used by --only / --without, mapped to the event they wire.
GROUP_EVENTS = {"rate_prompt": "UserPromptSubmit",
                "hook_health": "SessionStart",
                "stop_dispatcher": "Stop"}

# Every hook file the suite depends on (the dispatcher imports the four Stop sub-hooks).
REQUIRED_HOOKS = ("rate_prompt.py", "hook_health_check.py", "stop_dispatcher.py",
                  "show_your_proof.py", "meta_audit_on_stop.py", "memory_hygiene_guard.py",
                  "fast_test_on_stop.py")


def _cmd(script: str) -> str:
    return f'{PY} "{os.path.join(HOOKS_DIR, script)}"'


def desired_groups() -> dict:
    """The hook groups this suite installs, keyed by event."""
    return {
        "UserPromptSubmit": {
            "hooks": [{"type": "command", "command": _cmd("rate_prompt.py"), "timeout": 10}],
            "id": ID_PREFIX + "rate-prompt",
            "description": "Rate each prompt X/10 and act on a sharpened rewrite (deterministic, $0).",
        },
        "SessionStart": {
            "matcher": "*",
            "hooks": [{"type": "command", "command": _cmd("hook_health_check.py")}],
            "id": ID_PREFIX + "hook-health",
            "description": "Validate configured hooks resolve; weekly-run each hook's selftest.",
        },
        "Stop": {
            "matcher": "*",
            "hooks": [{"type": "command", "command": _cmd("stop_dispatcher.py"), "timeout": 300}],
            "id": ID_PREFIX + "stop-dispatcher",
            "description": "Run show-your-proof / meta-audit / memory-hygiene / fast-test in one process.",
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
    if not os.path.isdir(SKILL_SRC):
        print(f"  ! skill source missing ({SKILL_SRC}); skipping")
        return
    if dry_run:
        print(f"  would copy skill -> {SKILL_DEST}")
        return
    os.makedirs(SKILL_DEST, exist_ok=True)
    shutil.copy2(os.path.join(SKILL_SRC, "SKILL.md"), os.path.join(SKILL_DEST, "SKILL.md"))
    print(f"  copied skill -> {SKILL_DEST}")


def remove_skill(dry_run: bool) -> None:
    if not os.path.isdir(SKILL_DEST):
        return
    if dry_run:
        print(f"  would remove skill <- {SKILL_DEST}")
        return
    shutil.rmtree(SKILL_DEST, ignore_errors=True)
    print(f"  removed skill <- {SKILL_DEST}")


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Install unbluff into ~/.claude")
    ap.add_argument("--dry-run", action="store_true", help="show changes without writing")
    ap.add_argument("--uninstall", action="store_true", help="remove this suite's entries")
    ap.add_argument("--no-skill", action="store_true", help="do not install/remove the meta-review skill")
    ap.add_argument("--only", default="", metavar="a,b",
                    help="install only these groups: " + ", ".join(GROUP_EVENTS))
    ap.add_argument("--without", default="", metavar="a,b",
                    help="install every group except these")
    args = ap.parse_args()

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
        missing = [s for s in REQUIRED_HOOKS if not os.path.exists(os.path.join(HOOKS_DIR, s))]
        if missing:
            sys.exit(f"ERROR: missing hook files in {HOOKS_DIR}: {missing}\n"
                     f"(Partial checkout? The Stop dispatcher needs all four sub-hooks.)")

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
