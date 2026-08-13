"""timing-claim-guard (Claude Code PostToolUse hook) - a duration without a control is not evidence.

A wall-clock number is confounded by whatever else the machine was doing. This repo has the
scars: four timing conclusions during the A8 work were REVERSED by an interleaved control; a
"~50-minute sweep" came from an impression formed while waiting and was withdrawn; "1.08s" was
a single unreplicated reading against a true 1.291s median; a shipped comment read "0.20s,
under 1% of the cap" for a selftest measured at 1.412s; and an adversarial reviewer reported
3.8-4.7s for that same 1.4s selftest purely because five agents were loading the box.

**Eight instances. The rule was written down after the first one.** It is known, it is
believed, and it gets applied to the number under scrutiny and then dropped for whichever one
feels too small to matter - which is the definition of something that needs a mechanism rather
than another reminder.

WHY IT IS NARROW, AND HOW NARROW WAS DECIDED. The first design was "fire on a duration with no
control marker". MEASURED against docs/V131_REVIEW_PLAN.md: **82 duration mentions, of which
only ~17 read as measurements and ~15 are declared caps and timeouts** (`25s cap`, `12.50s
budget`, `3s timeout`) - constants, not claims. That design would have fired on roughly 65 of
82 and been switched off inside a week, which is B3-FP's lesson and strictly worse than no
hook. So it fires ONLY when a duration sits next to a MEASUREMENT VERB and carries no control
marker. A cap is not a claim; a claim without a control is.

Fail-silent, once per session, exit 0 always - the same contract as its twin
`numbers_match_on_write`. It nudges; it never blocks.

Run with --selftest.
"""

from __future__ import annotations

import json
import os
import re
import sys

_HOOKS_DIR_TC = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR_TC not in sys.path:
    sys.path.insert(0, _HOOKS_DIR_TC)

# A number with a time unit. Bare integers are excluded - "12" is not a duration.
DURATION = re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|seconds?|min|mins|minutes?|hours?)\b",
                      re.I)

# The word that turns a number into a CLAIM about something observed. Without one of these the
# number is a cap, a budget, a timeout or a sleep - a declared constant, and not this hook's
# business.
MEASUREMENT_VERBS = re.compile(
    r"\b(measured|measure|took|takes|ran in|runs in|clocked|elapsed|benchmark(?:ed)?|"
    r"timed|latency of|completed in|finished in|down to|up from|now runs)\b", re.I)

# Evidence that the claim was controlled. Any one of these and the hook stays quiet.
CONTROL_MARKERS = re.compile(
    r"\b(median|mean|n\s*=\s*\d+|interleav\w*|control|spread|of\s+\d+\s+runs?|"
    r"\d+\s*runs?|p50|p95|percentile|stdev|std\s*dev|variance|quiet box)\b", re.I)

# There WAS a DECLARATION roster here (cap|budget|timeout|...), added as "belt and braces"
# beside the verb requirement. It was DEAD on arrival: it could only fire on a line with no
# measurement verb, and such a line had already been skipped one check earlier. Then
# AGAINST_A_BUDGET was added and the dead branch turned HARMFUL - it vetoed every match of the
# new trigger, because that trigger by construction sits next to a budget word. It cost one
# debugging cycle and the symptom was the hook staying blind to the exact line that prompted
# it. Removed rather than special-cased.
#
# This is AR-4's class - a branch dead the day it landed - reappearing one step later, inside
# the guard being written to enforce measurement discipline. Recorded because "belt and braces"
# is how it justified itself both times.

# The second trigger, and it exists because the FIRST version of this hook was blind to the
# exact line that prompted it: "selftest 1.08s of its 12.50s budget" states an OBSERVATION
# against a DECLARED cap and contains no measurement verb at all. `X of its Y <cap-word>` is a
# specific, decidable idiom - the first duration is always the observation - so it is added as
# its own narrow trigger rather than by loosening the verb requirement, which would have
# re-widened the hook to the ~65-of-82 design that measurement already rejected.
AGAINST_A_BUDGET = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|seconds?|min|mins|minutes?)\s+of\s+(?:its|the|a)\s+"
    r"\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|seconds?|min|mins|minutes?)", re.I)

MARKER_DIR = os.path.join(os.path.expanduser("~"), ".claude", "state")
DOC_EXT = (".md", ".txt", ".rst")


def claims(text: str) -> list:
    """[(line_no, line)] for every line stating a MEASURED duration with no control.

    Line-scoped on purpose: a control marker three paragraphs away does not make this
    sentence's number controlled, and requiring the reader to go find it is how "1.08s" got
    written two paragraphs below a correctly-controlled figure.
    """
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if not DURATION.search(line):
            continue
        if not (MEASUREMENT_VERBS.search(line) or AGAINST_A_BUDGET.search(line)):
            continue                      # a declared cap/budget/timeout, not a claim
        if CONTROL_MARKERS.search(line):
            continue                      # controlled - this is what we want people to write
        out.append((i, line.strip()))
    return out


def verdict(found, doc_count):
    """(should_speak, message) - PURE, so the selftest can exercise every branch.

    Extracted for the reason MR-a recorded: a gate whose every test drives the detector and
    none drives the decision can be disarmed with one token while staying green.
    """
    if not found:
        return False, ""
    lines = ["[timing-claim] %d duration(s) stated as MEASURED with no control, in %d doc(s)."
             % (len(found), doc_count)]
    for path, num, text in found:
        lines.append("  %s:%d  %s" % (os.path.basename(path), num, text[:150]))
    lines.append("  A wall-clock number is confounded by whatever else the box was doing. This "
                 "repo has EIGHT instances where an uncontrolled reading was later reversed or "
                 "corrected - including 1.08s against a true 1.291s median, and a reviewer "
                 "reading 3.8s for a 1.4s selftest because five agents were running.")
    lines.append("  Re-measure INTERLEAVED against a control on a quiet box, then say so: "
                 "'1.412s median (n=5, 1.375-1.462), control at 0.89x'. If it is a declared "
                 "cap rather than an observation, word it as one and this stays quiet.")
    return True, "\n".join(lines)


def _marker_dir() -> str:
    """Where the once-per-session marker lives.

    [MEASURED 2026-08-13] This was the ONLY stateful hook that ignored UNBLUFF_STATE_DIR.
    Every twin - plan_defer_guard, numbers_match_on_write, memory_hygiene_guard,
    meta_audit_on_stop, fast_test_on_stop - reads it; this one had a module-level constant
    overridden only inside its own selftest. Three consequences, all observed while building
    the false-alarm scorer:
      * NO harness could isolate it. The scorer gives every corpus entry a fresh state dir;
        this hook ignored it, so one marker survived between runs and silenced the CONTROL on
        every run after the first. The run reported UNMEASURED - and would have reported a
        false 0% if the control had been trusted any less.
      * Measuring it WROTE INTO THE USER'S REAL ~/.claude/state, the same pollution class as a
        selftest writing to the production fire ledger.
      * Its default directory also differed from its twins' (~/.claude/state against
        ~/.claude/hooks/state), so even a reader who knew about the variable looked in the
        wrong place.
    Read at CALL time, never import time, so a harness setting it per run is obeyed.
    """
    return os.environ.get("UNBLUFF_STATE_DIR") or MARKER_DIR


def _marker(session_id: str) -> str:
    sid = "".join(c for c in str(session_id or "nosession") if c.isalnum() or c in "-_")[:64]
    return os.path.join(_marker_dir(), "timingclaim-%s.json" % sid)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    path = ((payload.get("tool_input") or {}) or {}).get("file_path")
    if not isinstance(path, str) or not path.lower().endswith(DOC_EXT):
        return 0
    marker = _marker(payload.get("session_id"))
    if os.path.exists(marker):
        return 0                          # once per session, like its twin
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return 0
    found = [(path, n, ln) for n, ln in claims(text)]
    speak, msg = verdict(found, 1 if found else 0)
    if not speak:
        return 0
    try:
        os.makedirs(_marker_dir(), exist_ok=True)
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump({"fired": True}, fh)
    except OSError:
        pass
    sys.stderr.write(msg + "\n")
    return 0                              # advisory: it nudges, it never blocks


# --------------------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------------------

SHOULD_FIRE = (
    ("the exact claim this session got wrong", "selftest 1.08s of its 12.50s budget"),
    ("a bare measured figure", "Measured 2026-08-02: 0.20s, under 1% of the cap."),
    ("took N seconds", "the full sweep took 25 minutes"),
    ("ran in", "the gate ran in 0.087s"),
    ("down to", "the selftest is down to 17.2s"),
    ("completed in", "the battery completed in 96 minutes"),
)

SHOULD_STAY_QUIET = (
    ("a declared cap", "the 25s cap hook_health_check applies per hook"),
    ("a declared budget", "0.50 share of the 25s cap = a 12.50s budget"),
    ("a declared timeout", 'subprocess.run(..., timeout=400)  # 400s timeout'),
    ("a sleep", "the selftest spawns a 60s sleeper to verify the kill path"),
    ("a CONTROLLED claim with median and n", "1.412s median (n=5, 1.375-1.462)"),
    ("a CONTROLLED claim with interleaved", "measured 0.087s interleaved against a control"),
    ("a controlled claim naming the control", "took 1.29s, control at 0.89x"),
    ("a line with no duration at all", "the corpus holds 135 entries = 105 + 30"),
    ("a duration with no measurement verb", "the 3s timeout against a 60s sleeper"),
    ("a bare integer is not a duration", "12 findings across 5 files"),
)


def selftest() -> int:
    import io
    import subprocess
    import tempfile

    fails = []
    for label, line in SHOULD_FIRE:
        if not claims(line):
            fails.append("BLIND to %s: %r" % (label, line))
    for label, line in SHOULD_STAY_QUIET:
        if claims(line):
            fails.append("FALSE POSITIVE on %s: %r" % (label, line))

    # line scope: a control marker elsewhere in the doc must not launder an uncontrolled line
    doc = "the gate is 0.087s median (n=5) interleaved\n\nthe suite took 25 minutes\n"
    got = claims(doc)
    if len(got) != 1 or got[0][0] != 3:
        fails.append("control markers must be LINE-scoped, got %r" % (got,))

    # DECISION path, every branch - MR-a's lesson
    speak, msg = verdict([], 0)
    if speak or msg:
        fails.append("verdict() must stay silent on nothing found")
    speak, msg = verdict([("/x/plan.md", 7, "took 25 minutes")], 1)
    if not speak:
        fails.append("verdict() must SPEAK on an uncontrolled claim")
    for phrase in ("timing-claim", "plan.md:7", "interleaved", "quiet box"):
        if phrase not in msg.lower():
            fails.append("verdict() message lost %r" % phrase)

    # main(), driven end to end, both directions, with a real file and a real marker dir
    def drive(payload):
        real_in, real_err = sys.stdin, sys.stderr
        sys.stdin, sys.stderr = io.StringIO(payload), io.StringIO()
        try:
            return main(), sys.stderr.getvalue()
        finally:
            sys.stdin, sys.stderr = real_in, real_err

    td = tempfile.mkdtemp(prefix="timingclaim_")
    dirty = os.path.join(td, "notes.md")
    with open(dirty, "w", encoding="utf-8") as fh:
        fh.write("# notes\n\nthe sweep took 25 minutes\n")
    clean = os.path.join(td, "clean.md")
    with open(clean, "w", encoding="utf-8") as fh:
        fh.write("# notes\n\n1.412s median (n=5) interleaved against a control\n")
    code = os.path.join(td, "x.py")
    with open(code, "w", encoding="utf-8") as fh:
        fh.write("# took 25 minutes\n")

    def pl(p, sid):
        return json.dumps({"session_id": sid, "tool_name": "Write",
                           "tool_input": {"file_path": p}})

    # [MEASURED 2026-08-13] The env var is the ONLY isolation a harness has, and this hook was
    # the one that ignored it. Assert it BEFORE the override below, because that override sets
    # MARKER_DIR directly and would mask a regression that dropped the env lookup entirely -
    # a probe that cannot fail on the defect it exists for is the hollow-pin class this repo
    # keeps digging out (mode 1: green for an unrelated reason).
    _env_probe = os.path.join(td, "envstate")
    _real_env = os.environ.get("UNBLUFF_STATE_DIR")
    os.environ["UNBLUFF_STATE_DIR"] = _env_probe
    try:
        if os.path.dirname(_marker("envcheck")) != _env_probe:
            fails.append("UNBLUFF_STATE_DIR is IGNORED: the marker resolved to %r, not %r. No "
                         "harness can isolate this hook, and measuring it writes into the "
                         "user's real state dir" % (os.path.dirname(_marker("envcheck")),
                                                    _env_probe))
    finally:
        if _real_env is None:
            os.environ.pop("UNBLUFF_STATE_DIR", None)
        else:
            os.environ["UNBLUFF_STATE_DIR"] = _real_env

    global MARKER_DIR
    real_marker_dir = MARKER_DIR
    MARKER_DIR = os.path.join(td, "state")
    try:
        rc, err = drive(pl(dirty, "s1"))
        if rc != 0:
            fails.append("must never block, got rc=%r" % rc)
        if "timing-claim" not in err:
            fails.append("did not fire on an uncontrolled claim in a .md: %r" % err[:120])
        rc, err = drive(pl(dirty, "s1"))
        if err:
            fails.append("fired TWICE in one session - the once-per-session marker is dead")
        rc, err = drive(pl(clean, "s2"))
        if err:
            fails.append("fired on a CONTROLLED claim: %r" % err[:120])
        rc, err = drive(pl(code, "s3"))
        if err:
            fails.append("fired on a .py file - this hook is for docs")
        rc, err = drive(pl(os.path.join(td, "gone.md"), "s4"))
        if rc != 0 or err:
            fails.append("a missing file must be silent, got rc=%r err=%r" % (rc, err))
        for bad in ("not json", "", "[]", "null", '{"tool_input": null}',
                    '{"tool_input": {"file_path": 5}}'):
            rc, err = drive(bad)
            if rc != 0:
                fails.append("payload %r must exit 0, got %r" % (bad[:26], rc))
    finally:
        MARKER_DIR = real_marker_dir
        import shutil
        shutil.rmtree(td, ignore_errors=True)

    # through a real process, so __main__ dispatch is covered
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--selftest-noop"],
                          input='{"tool_input": {"file_path": "/nope.md"}}',
                          capture_output=True, text=True, timeout=60,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        fails.append("subprocess run must exit 0, got %s" % proc.returncode)

    print("-- timing-claim: %d fire fixture(s), %d quiet control(s); fires only on a duration "
          "beside a MEASUREMENT VERB with no control marker" % (len(SHOULD_FIRE),
                                                                len(SHOULD_STAY_QUIET)))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
