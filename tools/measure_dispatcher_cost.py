#!/usr/bin/env python3
"""Plan item 37: MEASURE the ECC PostToolUse dispatcher migration before deciding.

ECC wires a number of individual `node -e ...` hook commands. Consolidating them behind its
own dispatcher may or may not repay editing a load-bearing settings.json. The decision needs
a number, not an intuition - so this produces one.

Method: count the PostToolUse commands actually registered, then time (a) the real per-hook
spawn cost by invoking each registered command with a synthetic PostToolUse payload, and
(b) a single dispatcher invocation with the same payload. Report the delta per tool call.

Reports only. It changes nothing and never edits settings.json.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "hooks"))
import capped_report  # noqa: E402

SETTINGS = os.path.expanduser("~/.claude/settings.json")
DISPATCHER = os.path.expanduser("~/.claude/scripts/hooks/posttooluse-dispatcher.js")
PAYLOAD = json.dumps({
    "session_id": "measure", "transcript_path": "", "cwd": os.getcwd(),
    "hook_event_name": "PostToolUse", "tool_name": "Read",
    "tool_input": {"file_path": os.path.abspath(__file__)},
    "tool_response": {"type": "text", "file": {"filePath": os.path.abspath(__file__)}},
})
REPS = 5


def registered(event: str) -> list:
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return []
    out = []
    for group in (cfg.get("hooks") or {}).get(event, []) or []:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []) or []:
            if isinstance(hook, dict) and hook.get("command"):
                out.append(hook)
    return out


def time_command(hook: dict) -> float | None:
    cmd = hook.get("command")
    args = [a for a in (hook.get("args") or []) if isinstance(a, str)]
    started = time.perf_counter()
    try:
        subprocess.run(([cmd] + args) if args else cmd, shell=not args,
                       input=PAYLOAD, capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return time.perf_counter() - started


def main() -> int:
    hooks = registered("PostToolUse")
    node_hooks = [h for h in hooks if "node -e" in (h.get("command") or "")]
    print(f"PostToolUse commands registered: {len(hooks)}  (node -e: {len(node_hooks)})")
    if not hooks:
        print("nothing registered; nothing to measure")
        return 0

    per_hook = []
    for hook in hooks:
        samples = [t for t in (time_command(hook) for _ in range(REPS)) if t is not None]
        if samples:
            per_hook.append((statistics.median(samples), (hook.get("command") or "")[:60]))
    if not per_hook:
        print("no command could be executed; cannot measure")
        return 0

    total = sum(t for t, _ in per_hook)
    slowest = max(t for t, _ in per_hook)
    # Report BOTH bounds rather than the scary one. Claude Code may run an event's hooks
    # concurrently, in which case wall-clock is the SLOWEST hook, not the sum; and matchers
    # mean not every hook fires on every tool. Quoting the sum as "per tool call" would be
    # an overstatement of the same kind this plan exists to catch.
    print(f"\nmedian per-command cost across {len(per_hook)} PostToolUse commands:")
    print(f"  serial upper bound (sum, if hooks run one after another): {total * 1000:.0f} ms")
    print(f"  parallel lower bound (slowest single hook):               {slowest * 1000:.0f} ms")
    print("  NOTE: matchers gate which hooks fire for a given tool, so the real figure for any")
    print("        one tool call is at or below these; both bounds are measured, not modelled.")
    # [R2-H4] This was `sorted(per_hook, reverse=True)[:8]` - a real, live, unrouted display
    # cap that printed the 8 slowest of len(per_hook) commands with no "+N more". It was
    # invisible to the cap guard for one reason only: the bound was an integer literal.
    # Routed through render() so the line names what it hid.
    for line in capped_report.render(
            [f"{t * 1000:7.0f} ms  {label}" for t, label in sorted(per_hook, reverse=True)],
            8, prefix="    ", noun="command"):
        print(line)

    node_total = sum(t for t, label in per_hook if "node -e" in label)
    node_max = max([t for t, label in per_hook if "node -e" in label] or [0])
    print(f"\n  ECC `node -e` spawns: {node_total * 1000:.0f} ms serial / "
          f"{node_max * 1000:.0f} ms parallel")

    if os.path.exists(DISPATCHER):
        samples = []
        for _ in range(REPS):
            started = time.perf_counter()
            try:
                subprocess.run(["node", DISPATCHER], input=PAYLOAD, capture_output=True,
                               text=True, timeout=60, encoding="utf-8", errors="replace")
                samples.append(time.perf_counter() - started)
            except (OSError, ValueError, subprocess.SubprocessError):
                break
        if samples:
            d = statistics.median(samples)
            print(f"\nsingle dispatcher invocation: {d * 1000:.0f} ms")
            # Decide on the CONSERVATIVE bound: if the saving holds even when the current
            # wiring is assumed to be fully parallel, the conclusion does not depend on a
            # guess about how the harness schedules hooks.
            best_case_saving = node_max - d
            worst_case_saving = node_total - d
            print(f"saving if hooks run in PARALLEL today: {best_case_saving * 1000:.0f} ms "
                  f"(the conservative case - decide on this one)")
            print(f"saving if hooks run SERIALLY today:    {worst_case_saving * 1000:.0f} ms")
            print("\nVERDICT: " + (
                "MIGRATE - the saving exceeds 250 ms per tool call even under the "
                "conservative parallel assumption, so the conclusion does not rest on how "
                "the harness schedules hooks"
                if best_case_saving > 0.25 else
                "DO NOT migrate - under the conservative assumption the saving is under "
                "250 ms and does not repay editing a load-bearing settings.json"))
        else:
            print("\ndispatcher could not be invoked (node missing?); no verdict")
    else:
        print(f"\ndispatcher not found at {DISPATCHER}; no verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
