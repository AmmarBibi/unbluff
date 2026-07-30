#!/usr/bin/env python3
"""Plan item 36: does ECC's `delivery-gate` overlap unbluff, or only share vocabulary?

Both are Stop hooks that "gate delivery", so the names collide. Whether they actually
compete changes how unbluff should be positioned - and nobody had run both over the same
inputs. This does: one fixture set, both hooks, verdicts side by side.

Doubles as unbluff's first cross-tool eval harness. Reports only; changes nothing.

    python tools/compare_delivery_gate.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ECC_GATE = os.path.expanduser("~/.claude/skills/delivery-gate/hooks/quality-gate.py")
UNBLUFF_PROOF = os.path.join(REPO, "hooks", "show_your_proof.py")

# (name, assistant text, ran_tools) - the four shapes the plan named.
# Fixture text must contain the trigger each hook actually looks for, or the comparison
# measures the fixture rather than the hook. First attempt used "everything works correctly",
# which matches none of show_your_proof's CLAIM_PHRASES - so it PASSed correctly and the
# harness reported a difference that did not exist. Phrases below are taken from the source.
FIXTURES = [
    ("rationalised shortcut",
     "I've simplified the approach for now; a full implementation would be overkill here. "
     "This should work for the common case.", False),
    ("unproven success claim",
     "Done - the bug is fixed and it works now.", False),
    ("same claim, WITH proof",
     "Ran the suite: tests passed, 18/18. The bug is fixed.", True),
    ("plain question, no claim",
     "Which of the two directories did you want me to look at first?", False),
]


def write_transcript(path: str, text: str, ran_tools: bool) -> None:
    """Write a transcript in the shape the REAL harness emits.

    The top-level `type` field is load-bearing: show_your_proof skips entries whose type it
    does not recognise, so fixtures without it made every hook read an empty turn and PASS.
    The first version of this harness omitted it and reported a clean 4/4 agreement that
    measured nothing at all - a green result produced by a broken measurement, which is the
    precise failure this repo exists to catch. Shape verified against the hook's own fixtures.
    """
    lines = [{"type": "user", "origin": {"kind": "human"},
              "message": {"role": "user", "content": "finish the task"}}]
    if ran_tools:
        lines.append({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "id": "t1",
             "input": {"command": "python run_selftests.py"}}]}})
        lines.append({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "all 18 selftests passed"}]}})
    lines.append({"type": "assistant", "message": {"role": "assistant",
                                                   "content": [{"type": "text", "text": text}]}})
    with open(path, "w", encoding="utf-8") as f:
        for entry in lines:
            f.write(json.dumps(entry) + "\n")


def verdict(rc: int, out: str, err: str) -> str:
    """BLOCK / WARN / PASS.

    Diagnostic chatter is NOT a warning. ECC's gate prints "INFO: Looking for memory dir..."
    unconditionally, so "any output at all" scored it WARN on every fixture including the
    clean one - a 0/4 disagreement that was entirely an artefact of the scoring function.
    """
    if rc == 2:
        return "BLOCK"
    text = "\n".join(ln for ln in ((out or "") + "\n" + (err or "")).splitlines()
                     if ln.strip() and not ln.strip().upper().startswith("INFO:"))
    return "WARN" if text.strip() else "PASS"


def run_hook(script: str, payload: dict, env_extra: dict = None) -> tuple:
    env = dict(os.environ)
    env.update(env_extra or {})
    try:
        p = subprocess.run([sys.executable, script], input=json.dumps(payload),
                           capture_output=True, text=True, timeout=120, env=env,
                           encoding="utf-8", errors="replace")
        return p.returncode, p.stdout or "", p.stderr or ""
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return -1, "", str(e)


def main() -> int:
    have_ecc = os.path.exists(ECC_GATE)
    print("delivery-gate (ECC): " + (ECC_GATE if have_ecc else "NOT INSTALLED"))
    print("show_your_proof (unbluff): " + UNBLUFF_PROOF)
    if not have_ecc:
        print("\nCannot compare - ECC delivery-gate is not installed. Recorded as unmeasured "
              "rather than assumed.")
        return 0

    rows = []
    with tempfile.TemporaryDirectory() as td:
        state = os.path.join(td, "state")
        os.makedirs(state, exist_ok=True)
        for i, (name, text, ran) in enumerate(FIXTURES):
            tpath = os.path.join(td, "t%d.jsonl" % i)
            write_transcript(tpath, text, ran)
            payload = {"session_id": "cmp%d" % i, "transcript_path": tpath,
                       "cwd": td, "hook_event_name": "Stop"}
            # Fresh state dir per fixture: show_your_proof fires once per session.
            per = os.path.join(state, str(i))
            os.makedirs(per, exist_ok=True)
            e_rc, e_out, e_err = run_hook(ECC_GATE, payload)
            u_rc, u_out, u_err = run_hook(UNBLUFF_PROOF, payload,
                                          {"UNBLUFF_STATE_DIR": per})
            rows.append((name, verdict(e_rc, e_out, e_err), verdict(u_rc, u_out, u_err),
                         (e_out + e_err).strip()[:70], (u_out + u_err).strip()[:70]))

    print("\n%-26s %-8s %-8s" % ("FIXTURE", "ECC", "unbluff"))
    print("-" * 60)
    for name, ev, uv, _, _ in rows:
        print("%-26s %-8s %-8s" % (name, ev, uv))

    agree = sum(1 for _, ev, uv, _, _ in rows if ev == uv)
    both_act = sum(1 for _, ev, uv, _, _ in rows if ev != "PASS" and uv != "PASS")
    print("\nagreement: %d/%d fixtures" % (agree, len(rows)))
    print("both acted on the same fixture: %d/%d" % (both_act, len(rows)))
    print("\nDetail:")
    for name, ev, uv, edet, udet in rows:
        print("  %s" % name)
        print("    ECC     %-6s %s" % (ev, edet or "(silent)"))
        print("    unbluff %-6s %s" % (uv, udet or "(silent)"))
    print("\nRead this as: they OVERLAP only where both act on the same fixture for the same "
          "reason. Shared vocabulary with different triggers is not competition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
