#!/usr/bin/env python3
"""Regenerate examples/settings.json from install.py, so the two cannot drift.

examples/settings.json is what someone copies when they wire this by hand. It was
hand-maintained and went stale twice: once missing the whole PostToolUse group (fixed in
v1.2.1), and again when four hooks were added in v1.3.0. A copy-paste install then quietly
omits hooks - the worst kind of stale, because nothing errors.

This derives it from `install.py`'s `desired_groups()` - the single source of truth for what
gets wired - and substitutes a placeholder for the machine-specific path.

    python tools/regen_example_settings.py           # write
    python tools/regen_example_settings.py --check   # verify, exit 1 if stale (for CI)
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(HERE, "examples", "settings.json")
PLACEHOLDER = "/ABSOLUTE/PATH/TO/unbluff"


def build() -> dict:
    sys.path.insert(0, HERE)
    import install  # noqa: E402  (repo root added above)

    groups = install.desired_groups()
    out: dict = {"hooks": {}}
    for event, group in groups.items():
        g = json.loads(json.dumps(group))  # deep copy
        for hook in g.get("hooks", []):
            cmd = hook.get("command", "")
            # normalise the interpreter and the repo path to portable placeholders
            cmd = re.sub(r'^"[^"]*"|^\S+', "python", cmd, count=1)
            cmd = cmd.replace(HERE, PLACEHOLDER).replace(HERE.replace("\\", "/"), PLACEHOLDER)
            cmd = cmd.replace("\\", "/")
            hook["command"] = cmd
        out["hooks"][event] = [g]
    return out


def main() -> int:
    generated = build()
    if "--check" in sys.argv:
        try:
            with open(EXAMPLE, encoding="utf-8") as f:
                current = json.load(f)
        except (OSError, ValueError) as e:
            print(f"examples/settings.json unreadable: {e}")
            return 1
        if current != generated:
            print("examples/settings.json is STALE - run: python tools/regen_example_settings.py")
            return 1
        print("examples/settings.json matches install.py")
        return 0
    os.makedirs(os.path.dirname(EXAMPLE), exist_ok=True)
    with open(EXAMPLE, "w", encoding="utf-8") as f:
        json.dump(generated, f, indent=2)
        f.write("\n")
    n = sum(len(g[0].get("hooks", [])) for g in generated["hooks"].values())
    print(f"wrote {EXAMPLE} ({len(generated['hooks'])} groups, {n} commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
