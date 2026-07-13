"""Stop-hook DISPATCHER - runs the local Stop hooks in ONE process per turn-end.

Why: each Stop entry in settings.json spawns its own python process every turn-end; four
hooks = four spawns. This dispatcher is registered as the single Stop entry and calls each
hook module in-process (their `main()` contracts are unchanged - every hook remains
independently runnable and --selftest-able). Also appends one line per run to a small
FIRE LEDGER (jsonl, auto-rotated) so hook fire-rates/noise are observable over time.

Mechanics: read the payload once; for each hook module, point sys.stdin at a fresh
StringIO of the payload and call module.main(); a hook that raises counts as rc=0
(fail-silent, per the hooks' own rule); stderr passes straight through (each hook prefixes
its own messages). Exit 2 iff ANY hook returned 2 (Claude Code then wakes the model with
the combined stderr). Ordering: cheap scanners first, the test runner last (it may run tests).
Model-agnostic, stdlib-only, no LLM involvement anywhere.
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

# (module_name, short_key) - cheap scanners first, the test runner last.
HOOKS = (
    ("show_your_proof", "proof"),
    ("meta_audit_on_stop", "audit"),
    ("memory_hygiene_guard", "memory"),
    ("fast_test_on_stop", "test"),
)


def run_hooks(payload_text: str, hooks=HOOKS) -> dict[str, int]:
    """Run each hook module in-process against the same payload; return {key: rc}."""
    if HOOK_DIR not in sys.path:
        sys.path.insert(0, HOOK_DIR)
    results: dict[str, int] = {}
    real_stdin = sys.stdin
    try:
        for module_name, key in hooks:
            try:
                module = importlib.import_module(module_name)
                sys.stdin = io.StringIO(payload_text)
                rc = module.main()
                results[key] = rc if isinstance(rc, int) else 0
            except (Exception, SystemExit):  # a broken hook (even if it exits) must not stop the others
                results[key] = 0
    finally:
        sys.stdin = real_stdin
    return results


def write_ledger(payload: dict, results: dict[str, int]) -> None:
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
            "cwd": payload.get("cwd", ""),
            "results": results,
            "fired": sorted(k for k, rc in results.items() if rc == 2),
        })
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def main() -> int:
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


def selftest() -> int:
    import tempfile
    fails: list[str] = []
    if HOOK_DIR not in sys.path:
        sys.path.insert(0, HOOK_DIR)
    # 1. every hook module imports and exposes a callable main
    for module_name, _key in HOOKS:
        try:
            module = importlib.import_module(module_name)
            if not callable(getattr(module, "main", None)):
                fails.append(f"{module_name}.main missing/not callable")
        except Exception as e:
            fails.append(f"{module_name} import failed: {e}")
    # 2. quiet path: non-git temp cwd, isolated state dirs -> all rc 0, exit would be 0
    with tempfile.TemporaryDirectory() as td:
        state = os.path.join(td, "state")
        env_keys = ("UNBLUFF_STATE_DIR", LEDGER_ENV)
        old_env = {k: os.environ.get(k) for k in env_keys}
        os.environ.update({"UNBLUFF_STATE_DIR": state,
                           LEDGER_ENV: os.path.join(td, "ledger.jsonl")})
        try:
            payload = {"session_id": "dispatch-selftest-quiet", "cwd": td}
            results = run_hooks(json.dumps(payload))
            if any(rc != 0 for rc in results.values()):
                fails.append(f"quiet path not quiet: {results}")
            # 3. firing path: a PLAN.md with a hiding marker makes the audit hook fire (no git needed)
            with open(os.path.join(td, "PLAN.md"), "w", encoding="utf-8") as f:
                f.write("- PARKED: mystery item\n")
            payload2 = {"session_id": "dispatch-selftest-fire", "cwd": td}
            err = io.StringIO()
            real_err = sys.stderr
            sys.stderr = err
            try:
                results2 = run_hooks(json.dumps(payload2))
            finally:
                sys.stderr = real_err
            if results2.get("audit") != 2:
                fails.append(f"audit hook did not fire through dispatcher: {results2}")
            if "[meta-audit]" not in err.getvalue():
                fails.append("audit stderr did not pass through dispatcher")
            # 4. ledger written and parseable
            write_ledger(payload2, results2)
            with open(os.environ[LEDGER_ENV], encoding="utf-8") as f:
                rec = json.loads(f.readlines()[-1])
            if rec.get("fired") != ["audit"]:
                fails.append(f"ledger fired-list wrong: {rec}")
        finally:
            for k, v in old_env.items():
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
