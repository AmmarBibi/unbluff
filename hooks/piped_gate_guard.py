"""piped-gate-guard (Claude Code PreToolUse hook) - a gate's exit code must survive the pipe.

`python run_selftests.py | tail -2` returns TAIL's exit status, not the suite's. The suite can
fail and the pipeline still reports success, so the agent reads the last two lines, sees a
green-looking string, and calls it passing. The evidence was discarded by the shell before
anyone looked at it.

MEASURED, 2026-08-06: the agent that built this did exactly that 8-10 times in one session,
on `run_selftests`, `no_regression` and `check_mutation_anchors`. Every instance was wrong as
a method. None happened to be wrong as an outcome, which is precisely why it survived a full
session of otherwise careful verification - a silent method error that keeps agreeing with the
truth is invisible until the day it does not.

WHY IT IS NARROW ON PURPOSE. Firing on any pipe would hit every `ls | head` and `grep | wc`,
and a guard that fires on correct work gets disabled - which is strictly worse than none
(finding B3-FP). So it fires only when a KNOWN GATE feeds a consumer that REPLACES the exit
status, and it stays quiet when the command already protects the status with `pipefail` or
`PIPESTATUS`.

Blocks (exit 2) rather than warns, because the fix is a five-character edit the agent can make
immediately, and a warning on a PreToolUse hook does not reliably reach the model.

Run with --selftest.
"""

from __future__ import annotations

import json
import os
import shlex
import sys

# A command whose exit code is EVIDENCE. Substring match against the whole segment, because a
# gate is invoked as `python tools/no_regression.py`, `py -3 run_selftests.py`, `pytest -q`,
# and `python hooks/x.py --selftest` - the interpreter and flags vary, the unit name does not.
GATE_TOKENS = (
    "run_selftests", "mutation_check", "no_regression", "check_mutation_anchors",
    "check_review_freshness", "check_readme_fresh", "check_python_floor", "check_skill_deps",
    "score_corpus", "hook_divergence_report", "compare_delivery_gate", "pytest", "--selftest",
)

# Consumers that REPLACE the pipeline's exit status with their own. `tee` is here because it
# returns its own status too; `sort`/`uniq` because a zero-row sort still exits 0.
STATUS_EATERS = (
    "head", "tail", "grep", "egrep", "fgrep", "wc", "sort", "uniq", "cut", "sed", "awk",
    "tee", "tr", "jq", "less", "more", "column", "rev", "xargs",
)

# The command already protects the status - say nothing.
PROTECTED = ("pipefail", "PIPESTATUS")


def _segments(command: str):
    """Pipeline segments, or None if the command cannot be parsed.

    shlex, not a split on '|', so a literal pipe inside quotes (`grep "a|b" f`) is a single
    token rather than a pipeline boundary, and `||` (which is not a pipe at all) does not
    masquerade as one.

    Returns None on a parse failure, and the caller stays QUIET on None. That is a deliberate
    fail-open and the only one in this file: this hook BLOCKS, and blocking a command nobody
    can parse would make the guard unusable on the first heredoc it meets. The blind spot is
    bounded and named rather than discovered later.
    """
    try:
        # punctuation_chars=True is load-bearing, not a refinement. Plain shlex.split() keeps
        # `2>&1|head` as ONE token when no space surrounds the pipe - and that spacing is the
        # common way this is actually typed. MEASURED against 15 verbatim commands from the
        # session that built this: the naive splitter caught 2 of 4 real offenders and was
        # silently blind to the other 2. A guard found blind by its own author's shell history
        # is the fail-open class this repo exists to catch, so the blindness is recorded here
        # rather than only fixed.
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    segments, current = [], []
    for tok in tokens:
        if tok == "|":
            segments.append(current)
            current = []
        else:
            current.append(tok)
    segments.append(current)
    return segments


def _is_gate_token(tok: str, gate: str) -> bool:
    """Does this ONE token invoke `gate`, as opposed to merely containing its name?

    Substring-matching the joined segment cannot tell a command from an argument:
    `grep "run_selftests|mutation_check" notes.txt | head` names two gates and runs neither.
    A gate is invoked as a SCRIPT PATH (`tools/no_regression.py`), a bare COMMAND (`pytest`),
    or a FLAG (`--selftest`) - so those are the only three shapes that count.
    """
    if tok.startswith("-"):
        return tok == gate
    if tok.endswith(".py"):
        return gate in os.path.basename(tok)
    return os.path.basename(tok) == gate


def piped_gates(command: str) -> list:
    """[(gate_token, eater)] for every gate whose exit status this command discards.

    A gate qualifies only when it is a PRODUCER - i.e. it appears in a segment that is not the
    last - because the final segment's status IS the pipeline's status and nothing is lost.
    `cat log | grep run_selftests` therefore stays quiet: the gate name is an argument there,
    not a command.
    """
    if any(p in command for p in PROTECTED):
        return []
    segments = _segments(command)
    if segments is None or len(segments) < 2:
        return []
    offenders, seen = [], set()
    for i, segment in enumerate(segments[:-1]):
        gate = next((g for tok in segment for g in GATE_TOKENS if _is_gate_token(tok, g)), None)
        if gate is None:
            continue
        # the eater is the FIRST command word of the next segment, resolved past a leading
        # env assignment or `sudo`-style prefix
        nxt = [t for t in segments[i + 1] if "=" not in t.split(" ")[0] or t.startswith("-")]
        eater = next((t for t in nxt if os.path.basename(t) in STATUS_EATERS), None)
        if eater is None:
            continue
        key = (gate, os.path.basename(eater))
        if key not in seen:
            seen.add(key)
            offenders.append(key)
    return offenders


def message(offenders) -> str:
    lines = ["[piped-gate] a gate's exit code is being discarded by the pipe."]
    for gate, eater in offenders:
        lines.append("  `%s` is piped into `%s`, so the pipeline returns %s's status, not the "
                     "gate's. The gate can FAIL and this command still succeed."
                     % (gate, eater, eater))
    lines.append("  Fix: capture it explicitly - `CMD > out.txt; echo \"EXIT=$?\"; tail out.txt`"
                 " - or `set -o pipefail` first, or read ${PIPESTATUS[0]}.")
    lines.append("  Reading the printed text instead of the exit code is not a substitute: a "
                 "gate that dies early prints nothing and looks identical to one that is quiet.")
    return "\n".join(lines)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    command = ((payload.get("tool_input") or {}) or {}).get("command")
    if not isinstance(command, str) or not command.strip():
        return 0
    offenders = piped_gates(command)
    if not offenders:
        return 0
    sys.stderr.write(message(offenders) + "\n")
    return 2


# --------------------------------------------------------------------------------------
# selftest - planted fixtures BOTH directions, and the DECISION path, not only the detector
# --------------------------------------------------------------------------------------

SHOULD_FIRE = (
    ("the exact shape measured in the session that built this",
     "python run_selftests.py 2>&1 | tail -2"),
    ("anchors piped to head", "python tools/check_mutation_anchors.py 2>&1 | head -1"),
    ("no_regression piped to grep", "python tools/no_regression.py 2>&1 | grep OK"),
    ("a hook selftest piped to tail", "python hooks/cap_shapes.py --selftest | tail -1"),
    ("pytest piped to tail", "pytest -q | tail -5"),
    ("gate is not the last segment", "python run_selftests.py | grep -v skip | wc -l"),
    ("cd prefix does not hide it", "cd /repo && python tools/score_corpus.py x y | head"),
    # NO SURROUNDING WHITESPACE - the shape actually typed most of the time, and the one a
    # plain shlex.split() was measured blind to.
    ("a pipe with no spaces around it", "python tools/check_mutation_anchors.py 2>&1|head -1"),
    ("no space on the left only", "python tools/no_regression.py 2>&1|grep OK"),
)

SHOULD_STAY_QUIET = (
    ("an ordinary pipe with no gate", "ls -la | head -20"),
    ("grep piped to head", "grep -rn foo . | head -5"),
    ("a gate NOT piped", "python run_selftests.py"),
    ("a gate with its status captured", 'python run_selftests.py; echo "EXIT=$?"'),
    ("a gate redirected, not piped", "python run_selftests.py > out.txt 2>&1"),
    ("pipefail protects the status", "set -o pipefail; python run_selftests.py | tail -2"),
    ("PIPESTATUS protects the status",
     'python run_selftests.py | tail -2; echo "${PIPESTATUS[0]}"'),
    ("|| is not a pipe", "python run_selftests.py || echo failed"),
    ("a literal pipe inside quotes", 'grep "run_selftests|mutation_check" notes.txt | head'),
    ("the gate CONSUMES, it is not the producer", "cat log.txt | grep run_selftests"),
    ("|| with no spaces is still not a pipe", "python run_selftests.py||echo failed"),
    ("a no-space pipe with no gate in it", "ls -la|head -20"),
)


def selftest() -> int:
    import io
    import subprocess

    fails = []
    for label, cmd in SHOULD_FIRE:
        if not piped_gates(cmd):
            fails.append("BLIND to %s: %r" % (label, cmd))
    for label, cmd in SHOULD_STAY_QUIET:
        got = piped_gates(cmd)
        if got:
            fails.append("FALSE POSITIVE on %s: %r -> %r" % (label, cmd, got))

    # an unparseable command must stay QUIET - the one deliberate fail-open, asserted so it is
    # a decision on record rather than something a later reader discovers
    if _segments('echo "unterminated') is not None:
        fails.append("_segments claimed to parse an unterminated quote")
    if piped_gates('python run_selftests.py | tail "unterminated'):
        fails.append("an unparseable command must not BLOCK - this hook blocks, and blocking "
                     "what nobody can parse makes it unusable")

    # DECISION path, both directions, through main() - not just the detector. MR-a was a gate
    # whose every test exercised the audit while nothing exercised the decision.
    def drive(payload):
        real_in, real_err = sys.stdin, sys.stderr
        sys.stdin, sys.stderr = io.StringIO(payload), io.StringIO()
        try:
            return main(), sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stderr = real_in, real_err

    def pl(cmd):
        return json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})

    rc, err = drive(pl("python run_selftests.py 2>&1 | tail -2"))
    if rc != 2:
        fails.append("main() must BLOCK (rc 2) on a piped gate, got %r" % rc)
    if "piped-gate" not in err or "tail" not in err:
        fails.append("block message does not name the eater: %r" % err[:160])
    if "pipefail" not in err or "EXIT=$?" not in err:
        fails.append("block message does not state the fix")
    rc, err = drive(pl("ls | head -5"))
    if rc != 0 or err:
        fails.append("main() must be SILENT on an ordinary pipe, got rc=%r err=%r" % (rc, err))

    # malformed and hostile payloads must never block
    for bad in ("not json", "", "[]", "null", '{"tool_input": null}',
                '{"tool_input": {"command": 5}}', '{"tool_input": {}}'):
        rc, err = drive(bad)
        if rc != 0:
            fails.append("payload %r must exit 0, got %r" % (bad[:30], rc))

    # through a REAL process, so the __main__ dispatch is covered
    proc = subprocess.run([sys.executable, os.path.abspath(__file__)],
                          input=pl("python run_selftests.py | tail -2"),
                          capture_output=True, text=True, timeout=60,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 2 or "piped-gate" not in (proc.stderr or ""):
        fails.append("subprocess run wrong: rc=%s stderr=%r"
                     % (proc.returncode, (proc.stderr or "")[:140]))

    print("-- piped-gate: %d gate token(s), %d status-eater(s), %d fire fixture(s), "
          "%d quiet control(s)" % (len(GATE_TOKENS), len(STATUS_EATERS), len(SHOULD_FIRE),
                                   len(SHOULD_STAY_QUIET)))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
