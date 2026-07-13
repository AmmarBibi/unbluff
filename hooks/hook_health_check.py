"""hook-health-check (Claude Code SessionStart hook) - a mechanical self-check.

A silently-broken hook is invisible until the behavior it guarded fails. At session start this
validates, in a few hundred ms, that:
  - ~/.claude/settings.json parses;
  - every hook command's executable resolves (an absolute path that exists, or a name on PATH);
  - every absolute script path referenced in a hook command exists on disk;
  - each self-testable hook in this suite still passes its own --selftest (run at most weekly).
Prints ONE line when healthy, a short warning list when not. ALWAYS exits 0 (never blocks a
session) - even on a hand-edited/malformed settings.json, it reports the problem instead of
crashing. Run with --selftest to verify the checker itself.

Config-agnostic: it does not know about any particular plugin or install layout. It just reads
whatever hooks you have configured and checks they resolve.
"""

from __future__ import annotations

import datetime
import json
import os
import shlex
import shutil
import subprocess
import sys

# Hooks in this suite that expose a --selftest (existence-check -> self-testing net).
_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCAL_HOOKS = ("rate_prompt.py", "fast_test_on_stop.py", "show_your_proof.py",
                "meta_audit_on_stop.py", "memory_hygiene_guard.py", "stop_dispatcher.py",
                "hook_health_check.py")
_STATE_DIR = os.environ.get("UNBLUFF_STATE_DIR") or os.path.join(
    os.path.expanduser("~"), ".claude", "hooks", "state")
_WEEKLY_MARKER = "hook-health-weekly-selftest.txt"
_SELFTEST_TIMEOUT_S = 45
_WEEK_DAYS = 7
_SCRIPT_EXTS = (".py", ".js", ".ps1", ".sh")


def _days_since(datestr: str) -> int:
    try:
        then = datetime.date.fromisoformat(datestr.strip())
        return (datetime.date.today() - then).days
    except ValueError:
        return 10_000  # unparseable -> due


def run_weekly_selftests(hook_paths: list[str], state_dir: str) -> tuple[list[str], int, int]:
    """Run each hook's --selftest at most once per week. Returns (problems, n_run, n_passed).

    The pass-marker is written ONLY when every selftest passes, so a failing safety net
    re-surfaces at every session start until it is fixed. n_run == 0 means 'not due'.
    'missing hook' problems are reported but do not count toward n_run/n_passed.
    """
    marker = os.path.join(state_dir, _WEEKLY_MARKER)
    try:
        with open(marker, encoding="utf-8") as f:
            if _days_since(f.read()) < _WEEK_DAYS:
                return [], 0, 0
    except OSError:
        pass  # no marker -> due
    problems: list[str] = []
    n = 0
    n_passed = 0
    for path in hook_paths:
        if not os.path.exists(path):
            problems.append(f"weekly selftest: missing hook {os.path.basename(path)}")
            continue
        n += 1
        try:
            proc = subprocess.run([sys.executable, path, "--selftest"],
                                  capture_output=True, text=True,
                                  timeout=_SELFTEST_TIMEOUT_S, stdin=subprocess.DEVNULL)
            if proc.returncode == 0:
                n_passed += 1
            else:
                tail = (proc.stdout or proc.stderr or "").strip().splitlines()
                problems.append(f"weekly selftest FAILED: {os.path.basename(path)}"
                                f" ({tail[-1][:90] if tail else 'no output'})")
        except (OSError, subprocess.SubprocessError):
            problems.append(f"weekly selftest ERRORED/timed out: {os.path.basename(path)}")
    if not problems:
        try:
            os.makedirs(state_dir, exist_ok=True)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(datetime.date.today().isoformat() + "\n")
        except OSError:
            pass
    return problems, n, n_passed


def _tokens(command: str) -> list[str]:
    """Best-effort split of a hook command string into tokens, quotes stripped."""
    try:
        raw = shlex.split(command, posix=False)
    except ValueError:
        raw = command.split()
    return [t.strip('"').strip("'") for t in raw if t.strip()]


def check_config(cfg: dict) -> tuple[int, list[str]]:
    """(n_commands, problems) for a parsed settings dict.

    Defensive against hand-edited / third-party settings.json: any group or hook entry that is
    not the expected shape is reported as a problem, never allowed to raise. Checks each hook
    command's executable resolves and that any ABSOLUTE script path it references exists.
    Relative script paths are left alone (resolved at runtime against an unknown cwd).
    """
    problems: list[str] = []
    n_cmd = 0
    hooks_cfg = cfg.get("hooks") if isinstance(cfg, dict) else None
    if hooks_cfg is None:
        return 0, problems
    if not isinstance(hooks_cfg, dict):
        return 0, ["'hooks' is not an object"]
    for event, groups in hooks_cfg.items():
        if not isinstance(groups, list):
            problems.append(f"{event}: hooks entry is not a list")
            continue
        for g in groups:
            if not isinstance(g, dict):
                problems.append(f"{event}: a hook group is not an object")
                continue
            entries = g.get("hooks", []) or []
            if not isinstance(entries, list):
                problems.append(f"{event}: group 'hooks' is not a list")
                continue
            for h in entries:
                if not isinstance(h, dict):
                    problems.append(f"{event}: a hook entry is not an object")
                    continue
                n_cmd += 1
                command = (h.get("command", "") or "").strip()
                if not command:
                    problems.append(f"{event}: empty hook command")
                    continue
                tokens = _tokens(command)
                exe = tokens[0] if tokens else ""
                if not exe:
                    problems.append(f"{event}: empty hook command")
                    continue
                if os.path.isabs(exe):
                    if not os.path.exists(exe):
                        problems.append(f"{event}: missing executable {exe}")
                elif shutil.which(exe) is None:
                    problems.append(f"{event}: executable not on PATH: {exe}")
                for tok in tokens[1:]:
                    if tok.lower().endswith(_SCRIPT_EXTS) and os.path.isabs(tok) and not os.path.exists(tok):
                        problems.append(f"{event}: missing script {tok}")
    # de-duplicate, keep order
    seen: set[str] = set()
    problems = [p for p in problems if not (p in seen or seen.add(p))]
    return n_cmd, problems


def main() -> int:
    sp = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    try:
        with open(sp, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print("[hook-health] no ~/.claude/settings.json found (nothing to check)")
        return 0
    except (OSError, ValueError) as e:
        print(f"[hook-health] WARNING: settings.json unreadable/unparseable: {e}")
        return 0
    if not isinstance(cfg, dict):
        print("[hook-health] WARNING: settings.json is not a JSON object")
        return 0
    n_cmd, problems = check_config(cfg)
    weekly_problems, n_run, n_passed = run_weekly_selftests(
        [os.path.join(_HOOKS_DIR, name) for name in _LOCAL_HOOKS], _STATE_DIR)
    problems += weekly_problems
    weekly_note = f", weekly selftests {n_passed}/{n_run} OK" if n_run else ""
    if problems:
        print(f"[hook-health] {len(problems)} problem(s) across {n_cmd} hook commands{weekly_note}:")
        for p in problems[:12]:
            print(f"  - {p}")
        if len(problems) > 12:
            print(f"  ... and {len(problems) - 12} more")
    else:
        print(f"[hook-health] OK - {n_cmd} hook commands verified{weekly_note}")
    return 0


def selftest() -> int:
    fails = []
    # 1. a known-good config shape: python exe + this very script as an absolute arg
    good = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                           "command": f'"{sys.executable}" "{os.path.abspath(__file__)}"'}]}]}}
    _, probs = check_config(good)
    if probs:
        fails.append(f"good config flagged: {probs}")
    # 2. a missing absolute script MUST be caught
    bad = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                          "command": f'"{sys.executable}" "{os.path.join(os.sep, "nope", "missing_hook_xyz.py")}"'}]}]}}
    _, probs = check_config(bad)
    if not any("missing script" in p for p in probs):
        fails.append("missing script NOT caught")
    # 3. a missing absolute executable MUST be caught
    bad2 = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                           "command": os.path.join(os.sep, "nope", "ghost.exe") + " run"}]}]}}
    _, probs = check_config(bad2)
    if not any("missing executable" in p for p in probs):
        fails.append("missing executable NOT caught")
    # 4. malformed configs MUST be reported, never raise (the whole point of this hook)
    for label, malformed in [
        ("hooks-is-list", {"hooks": [1, 2, 3]}),
        ("group-not-dict", {"hooks": {"Stop": ["oops"]}}),
        ("entry-not-dict", {"hooks": {"Stop": [{"hooks": ["oops"]}]}}),
        ("group-hooks-not-list", {"hooks": {"Stop": [{"hooks": {"bad": 1}}]}}),
    ]:
        try:
            _, probs = check_config(malformed)
            if not probs:
                fails.append(f"malformed config '{label}' produced no problem")
        except Exception as e:  # must never raise
            fails.append(f"malformed config '{label}' RAISED {e!r}")
    # 5. weekly selftest runner: catches a failing hook, marker written only on all-pass, counts pass/run
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        ok_hook = os.path.join(td, "ok_hook.py")
        bad_hook = os.path.join(td, "bad_hook.py")
        with open(ok_hook, "w", encoding="utf-8") as f:
            f.write("import sys; sys.exit(0)\n")
        with open(bad_hook, "w", encoding="utf-8") as f:
            f.write("print('SELFTEST FAIL: broken'); import sys; sys.exit(1)\n")
        state = os.path.join(td, "state")
        probs, n, n_passed = run_weekly_selftests([ok_hook, bad_hook], state)
        if n != 2 or n_passed != 1 or not any("bad_hook.py" in p for p in probs):
            fails.append(f"weekly runner counts wrong: n={n} passed={n_passed} probs={probs}")
        if os.path.exists(os.path.join(state, _WEEKLY_MARKER)):
            fails.append("weekly marker written despite a failure")
        # missing hook is reported but does not inflate the run count
        probs_m, n_m, passed_m = run_weekly_selftests([ok_hook, os.path.join(td, "gone.py")], state)
        if n_m != 1 or passed_m != 1 or not any("missing hook" in p for p in probs_m):
            fails.append(f"missing-hook accounting wrong: n={n_m} passed={passed_m} probs={probs_m}")
        probs2, n2, passed2 = run_weekly_selftests([ok_hook], state)
        if probs2 or n2 != 1 or passed2 != 1 or not os.path.exists(os.path.join(state, _WEEKLY_MARKER)):
            fails.append(f"all-pass run did not write the marker: {probs2} n={n2} passed={passed2}")
        probs3, n3, _ = run_weekly_selftests([ok_hook], state)  # now within the week -> skip
        if n3 != 0:
            fails.append(f"weekly skip not honored: n={n3}")
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:  # the health check itself must never block a session
        print(f"[hook-health] WARNING: self-check crashed: {e}")
        raise SystemExit(0)
