"""PostToolUse-hook DISPATCHER - runs the local PostToolUse hooks in ONE process per edit.

The PostToolUse sibling of stop_dispatcher. Each PostToolUse entry in settings.json spawns its
own python process on every Edit/Write/MultiEdit; two hooks = two spawns per edit. This dispatcher
is registered as the single PostToolUse entry and calls each hook module in-process (their `main()`
contracts are unchanged - every hook stays independently runnable and --selftest-able). It appends
one line per run to the shared FIRE LEDGER (jsonl, auto-rotated), tagged event=PostToolUse, so
fire-rates/noise are observable over time.

Mechanics: read the payload once; for each hook module, point sys.stdin at a fresh StringIO of the
payload and call module.main(); a hook that raises counts as rc=0 (fail-silent, per the hooks' own
rule); stderr passes straight through (each hook prefixes its own messages). Exit 2 iff ANY hook
returned 2 (Claude Code then wakes the model with the combined stderr). Ordering: plan_defer_guard
(plan/roadmap language) before numbers_match_on_write (report numbers vs source). Model-agnostic,
stdlib-only, no LLM involvement anywhere.
"""
from __future__ import annotations

import importlib
import io
import json
import os
import sys
import time

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
LEDGER_ENV = "UNBLUFF_LEDGER_PATH"
DEFAULT_LEDGER = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "state", "fire_ledger.jsonl")
LEDGER_MAX_BYTES = 512 * 1024  # rotate to .1 beyond this

# (module_name, short_key) - cheap plan scan first, then the report numeric check.
HOOKS = (
    ("plan_defer_guard", "defer"),
    ("numbers_match_on_write", "numbers"),
)


def run_hooks(payload_text, hooks=HOOKS):
    """Run each hook module in-process against the same payload; return {key: rc}."""
    if HOOK_DIR not in sys.path:
        sys.path.insert(0, HOOK_DIR)
    results = {}
    real_stdin = sys.stdin
    try:
        for module_name, key in hooks:
            try:
                module = importlib.import_module(module_name)
                sys.stdin = io.StringIO(payload_text)
                rc = module.main()
                results[key] = rc if isinstance(rc, int) else 0
            except (Exception, SystemExit):  # a broken hook must not stop the others
                results[key] = 0
    finally:
        sys.stdin = real_stdin
    return results


def write_ledger(payload, results):
    """Append one observability line; rotate when large; never raise."""
    try:
        path = os.environ.get(LEDGER_ENV) or DEFAULT_LEDGER
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            if os.path.getsize(path) > LEDGER_MAX_BYTES:
                rotated = path + ".1"
                if os.path.exists(rotated):
                    os.remove(rotated)
                os.replace(path, rotated)
        except OSError:
            pass
        line = json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": "PostToolUse",
            "cwd": payload.get("cwd", ""),
            "results": results,
            "fired": sorted(k for k, rc in results.items() if rc == 2),
        })
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main():
    try:
        payload_text = sys.stdin.read()
        payload = json.loads(payload_text)
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0
    results = run_hooks(payload_text)
    write_ledger(payload, results)
    return 2 if any(rc == 2 for rc in results.values()) else 0


def selftest():
    import tempfile
    fails = []
    if HOOK_DIR not in sys.path:
        sys.path.insert(0, HOOK_DIR)
    # 1. every hook module imports and exposes a callable main
    for module_name, _key in HOOKS:
        try:
            module = importlib.import_module(module_name)
            if not callable(getattr(module, "main", None)):
                fails.append("%s.main missing/not callable" % module_name)
        except Exception as e:
            fails.append("%s import failed: %s" % (module_name, e))
    # 2. quiet path: a non-plan, non-report file with isolated state -> all rc 0
    with tempfile.TemporaryDirectory() as td:
        state = os.path.join(td, "state")
        env_keys = ("UNBLUFF_STATE_DIR", LEDGER_ENV)
        old = {k: os.environ.get(k) for k in env_keys}
        os.environ.update({"UNBLUFF_STATE_DIR": state, LEDGER_ENV: os.path.join(td, "ledger.jsonl")})
        try:
            other = os.path.join(td, "notes.txt")
            with open(other, "w", encoding="utf-8") as f:
                f.write("nothing here\n")
            results = run_hooks(json.dumps({"session_id": "ptu-quiet",
                                            "tool_input": {"file_path": other}}))
            if any(rc != 0 for rc in results.values()):
                fails.append("quiet path not quiet: %r" % results)
            # 3. firing path: a plan file with '-> park' makes plan_defer_guard fire through us
            plan = os.path.join(td, "MASTER_PLAN.md")
            with open(plan, "w", encoding="utf-8") as f:
                f.write("- low-pri thing -> park.\n")
            err, real_err = io.StringIO(), sys.stderr
            sys.stderr = err
            try:
                results2 = run_hooks(json.dumps({"session_id": "ptu-fire",
                                                 "tool_input": {"file_path": plan}}))
            finally:
                sys.stderr = real_err
            if results2.get("defer") != 2:
                fails.append("plan_defer_guard did not fire through dispatcher: %r" % results2)
            if "[plan-defer-guard]" not in err.getvalue():
                fails.append("defer stderr did not pass through dispatcher")
            write_ledger({"cwd": td}, results2)
            with open(os.environ[LEDGER_ENV], encoding="utf-8") as f:
                rec = json.loads(f.readlines()[-1])
            if rec.get("fired") != ["defer"] or rec.get("event") != "PostToolUse":
                fails.append("ledger line wrong: %r" % rec)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
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
    except Exception:
        raise SystemExit(0)  # a broken dispatcher must never block the user
