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
# [ROSTER 2026-08-20] The five names on the last two lines were MISSING, and the gap was not
# visible from this file: a gate invoked with --selftest is covered by the "--selftest" token
# whatever it is called, so only the ENFORCING invocations fell through. DERIVED against
# run_selftests.AUX_GATES: 7 of the 16 rows had no name here, of which 3 are registered enforcing
# - regen_example_settings, check_file_size and ship_bar_gate. That last one is the ship bar, so
# `python tools/ship_bar_gate.py | tail -5` read as clean while the gate whose whole job is
# refusing to ship had its exit status eaten. selftest() now DERIVES this coverage from AUX_GATES
# and prints the denominator, so the next gate added cannot be silently uncovered.
GATE_TOKENS = (
    "run_selftests", "mutation_check", "no_regression", "check_mutation_anchors",
    "check_review_freshness", "check_readme_fresh", "check_python_floor", "check_skill_deps",
    "score_corpus", "hook_divergence_report", "compare_delivery_gate", "pytest", "--selftest",
    "ship_bar_gate", "check_file_size", "regen_example_settings", "gate_ledger",
    "check_no_network",
    "score_false_alarms",
    # Added with the gate itself, not after: piped_gate_guard
    # FAILED the moment selftest-isolation was registered, which is the roster-drift check
    # working. A gate its guard cannot see can be piped into `head` and silently ignored.
    "check_selftest_isolation",
)

# Consumers that REPLACE the pipeline's exit status with their own. `tee` is here because it
# returns its own status too; `sort`/`uniq` because a zero-row sort still exits 0.
STATUS_EATERS = (
    "head", "tail", "grep", "egrep", "fgrep", "wc", "sort", "uniq", "cut", "sed", "awk",
    "tee", "tr", "jq", "less", "more", "column", "rev", "xargs",
    # `findstr` is Windows' grep and a NATIVE executable, so it sets the pipeline's status in
    # any shell that can reach it. MEASURED 2026-08-13: the gate ran to completion and its
    # exit 3 became 0 - the silent-green shape, identical to `| grep`.
    "findstr",
)

# The command already protects the status - say nothing. `LASTEXITCODE` is PowerShell's
# equivalent of reading ${PIPESTATUS[0]}; it is meaningless in sh, so ONE tuple serves both
# dialects and the line below stays untouched (it is PG2's mutation anchor).
PROTECTED = ("pipefail", "PIPESTATUS", "LASTEXITCODE")

# [DISARM 2026-08-20] ...but WHERE the word appears decides whether it protects anything, and
# `any(p in command for p in PROTECTED)` did not ask. Any occurrence anywhere silenced a BLOCKING
# guard: in a comment, in a filename, or - the case that matters - AFTER the pipeline, where it
# does nothing at all. `python run_selftests.py | tail -2; set -o pipefail` is an ordinary
# ordering mistake, and this hook's own block message ("or `set -o pipefail` first") is what
# teaches the shape. An agent that takes the advice and writes it in the wrong place gets silence
# on the retry, with the suite's exit status still eaten.
#
# The two behave DIFFERENTLY and the rule has to as well:
#   `pipefail` is an option SET BEFOREHAND, so it only protects if it precedes the pipeline.
#   `PIPESTATUS` / `LASTEXITCODE` are READ AFTERWARDS - `cmd | tail; exit $LASTEXITCODE` is the
#   correct spelling - so position cannot be required of them.
# Split by dialect too: LASTEXITCODE is meaningless in sh and PIPESTATUS in PowerShell, so
# neither may silence the other's shell.
_PROTECTORS = {
    "bash": (("pipefail", "before"), ("PIPESTATUS", "anywhere")),
    "powershell": (("LASTEXITCODE", "anywhere"),),
}


def strip_comments(command: str) -> str:
    """`command` with shell comments removed, quotes respected.

    [M10 2026-08-25] The DISARM fix above made POSITION matter; it never asked whether the word
    was EXECUTABLE. A comment cannot set an option, so this silenced a blocking guard:

        # remember to set -o pipefail
        python run_selftests.py | tail -2

    `pipefail` sits in the head, before the pipe, so the guard went quiet while the suite's exit
    status was still eaten. The trailing form disarms the "anywhere" words the same way -
    `python gate.py | tail  # check PIPESTATUS` - so both are stripped, not only the first.

    Quote-aware, because over-stripping is its own failure mode: `echo "# pipefail"` is executable
    text, and a guard that fires on correct work is the thing this repo says gets guards switched
    off. A `#` opens a comment only at the start of a token - preceded by whitespace or line start
    - and never inside quotes, which is the rule a shell itself applies.
    """
    out = []
    for line in command.splitlines():
        buf, quote, prev = [], None, ""
        for ch in line:
            if quote:
                buf.append(ch)
                if ch == quote and prev != "\\":
                    quote = None
            elif ch in ("'", '"'):
                quote = ch
                buf.append(ch)
            elif ch == "#" and (not buf or buf[-1].isspace()):
                break                      # a comment runs to end of line
            else:
                buf.append(ch)
            prev = ch
        out.append("".join(buf))
    return "\n".join(out)


def _is_protected(command: str, dialect: str = "bash") -> bool:
    """True if `command` genuinely guards the pipeline's status in `dialect`. See _PROTECTORS.

    Comments are stripped FIRST (M10): the question is whether this command protects the status,
    and a commented-out protector protects nothing.

    KNOWN LIMIT, adjudicated rather than left to be rediscovered. After stripping comments this is
    still a SUBSTRING test, so executable text that merely CONTAINS the word counts as protective:
    `echo "# pipefail"; python run_selftests.py | tail` reads as protected. Deliberate. Tightening
    it to `set -o pipefail` would reject the legitimate spellings (`set -euo pipefail`,
    `bash -o pipefail -c ...`) and start firing on correct work, which this repo holds to be worse
    than no guard at all. The residual exposure is small because the guard only speaks when a GATE
    TOKEN is present, so the word has to appear in a command that is already piping a gate.
    Pinned as PG-QUOTED so the choice cannot be reversed by accident.
    """
    command = strip_comments(command)
    head = command.split("|", 1)[0]
    for word, where in _PROTECTORS.get(dialect, _PROTECTORS["bash"]):
        if word in (head if where == "before" else command):
            return True
    return False

# --------------------------------------------------------------------------------------
# PowerShell [PGG-PS]. The SAME hook, a DIFFERENT failure - and the difference was MEASURED
# on 2026-08-13 across 15 consumers, not reasoned about, because reasoning gets it BACKWARDS.
#
# In sh, `gate | tail` returns TAIL's status: the gate FINISHES and its verdict is discarded.
# In PowerShell, $LASTEXITCODE is set only by NATIVE executables, so a CMDLET consumer leaves
# the gate's code intact - `gate | Select-String OK` still reports 3. MEASURED as preserving:
# Select-String, Measure-Object, Out-File, Tee-Object, Sort-Object, ForEach-Object,
# Where-Object, Out-Null, Out-String, Format-Table, Get-Unique, and Select-Object -Last/-Skip.
# Flagging any of them would be a false alarm, and a guard that fires on correct work is
# switched off within a week (B3-FP) - so the POSIX list is NOT reused unfiltered.
#
# Exactly TWO shapes destroy the evidence here:
#   1. `Select-Object -First N` / `-Index N`, and the shipped `select` alias. These TRUNCATE
#      the pipeline, which TEARS THE PRODUCER DOWN: measured $LASTEXITCODE = -1 with the
#      gate's completion marker ABSENT. Strictly worse than the sh case - the gate never
#      finished, so there is no verdict to discard. This is the shape V131 recorded by
#      accident (`-1` while the gate itself printed OK).
#   2. A NATIVE consumer, which sets $LASTEXITCODE itself exactly as in sh. `findstr` measured
#      STATUS-REPLACED: the gate ran to completion and its 3 became 0 - a silent green.
#
# TWO POSIX SPELLINGS ARE TRAPS HERE: `sort` and `tee` are ALIASES for Sort-Object and
# Tee-Object, both measured status-PRESERVING. They belong in STATUS_EATERS and are correct
# there; carrying them into PowerShell would false-alarm on correct work.
SHELL_TOOLS = ("Bash", "PowerShell")      # install.py DERIVES its PreToolUse matcher from this

PS_SELECT = ("select-object", "select")   # the cmdlet and its shipped alias
PS_TRUNCATING = ("-first", "-index")      # the parameters that tear the producer down


def _ps_truncates(token: str) -> bool:
    """True if `token` is a PowerShell parameter that truncates Select-Object's input.

    [PS-ABBREV 2026-08-20] PowerShell accepts any UNAMBIGUOUS prefix of a parameter name, so
    `select -f 1` is `-First 1` and tears the producer down exactly as the full spelling does.
    Matching the full words only meant the shorthand an operator actually types was undetected -
    on the very shell this repo is developed on, where the file's own measurement (lines 71-76)
    records the PowerShell case as STRICTLY WORSE than the sh one: no verdict at all, not merely
    a replaced one.

    `-i` is deliberately NOT accepted: it is ambiguous with -InputObject, so PowerShell itself
    rejects it, and treating it as truncating would make the guard fire on a command that cannot
    run. A guard that fires on correct work is one its owner disables.
    """
    t = token.lower()
    if not t.startswith("-") or len(t) < 2:
        return False
    stem = t[1:]
    return any(full[1:].startswith(stem) for full in PS_TRUNCATING) and stem != "i"
PS_SAFE_ALIASES = ("sort", "tee")         # POSIX spellings that are SAFE cmdlets in PowerShell


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
    # A PowerShell command names a script `tools\check_mutation_anchors.py`. os.path.basename
    # splits on "\" ONLY when this hook happens to be running on Windows, so a backslash path
    # is invisible on Linux - normalise first, and the answer stops depending on the box the
    # guard runs on rather than the shell the command is written for.
    tok = tok.replace("\\", "/")
    if tok.startswith("-"):
        return tok == gate
    if tok.endswith(".py"):
        return gate in os.path.basename(tok)
    return os.path.basename(tok) == gate


def _base(tok: str) -> str:
    """Command name, separator-normalised, so the answer does not depend on the host OS."""
    return os.path.basename(tok.replace("\\", "/"))


def _eater(segment, dialect: str):
    """The consumer in `segment` that destroys a gate's evidence, or None.

    Returns (token, kind). The KIND is load-bearing because the two failures need different
    fixes and different words:
      "replaces"  the sh shape - the gate FINISHES and its exit code is overwritten
      "truncates" the PowerShell -First shape - the gate is TORN DOWN and never finishes
    """
    # resolved past a leading env assignment or `sudo`-style prefix
    words = [t for t in segment if "=" not in t.split(" ")[0] or t.startswith("-")]
    lowered = [_base(w.lower()) for w in words]
    if dialect == "powershell":
        if any(w in PS_SELECT for w in lowered) and any(_ps_truncates(w) for w in lowered):
            return (next(w for w, low in zip(words, lowered) if low in PS_SELECT), "truncates")
        for w, low in zip(words, lowered):
            if low in PS_SAFE_ALIASES:      # MEASURED status-preserving here - never flag
                continue
            if low in STATUS_EATERS:        # a NATIVE consumer behaves exactly as in sh
                return (w, "replaces")
        return None
    for w, low in zip(words, lowered):
        if low in STATUS_EATERS:
            return (w, "replaces")
    return None


def piped_gates(command: str, dialect: str = "bash") -> list:
    """[(gate_token, eater, kind)] for every gate whose evidence this command destroys.

    A gate qualifies only when it is a PRODUCER - i.e. it appears in a segment that is not the
    last - because the final segment's status IS the pipeline's status and nothing is lost.
    `cat log | grep run_selftests` therefore stays quiet: the gate name is an argument there,
    not a command.

    `dialect` defaults to "bash", which is what every caller got before PowerShell was covered
    at all: an unknown shell gets the STRICTER semantics rather than silently getting none.
    """
    if _is_protected(command, dialect):
        return []
    segments = _segments(command)
    if segments is None or len(segments) < 2:
        return []
    offenders, seen = [], set()
    for i, segment in enumerate(segments[:-1]):
        gate = next((g for tok in segment for g in GATE_TOKENS if _is_gate_token(tok, g)), None)
        if gate is None:
            continue
        found = _eater(segments[i + 1], dialect)
        if found is None:
            continue
        eater, kind = found
        key = (gate, _base(eater), kind)
        if key not in seen:
            seen.add(key)
            offenders.append(key)
    return offenders


def message(offenders) -> str:
    lines = ["[piped-gate] a gate's exit code is being discarded by the pipe."]
    for gate, eater, kind in offenders:
        if kind == "truncates":
            lines.append("  `%s` is piped into `%s`, which TRUNCATES the pipeline and tears "
                         "the gate down BEFORE IT FINISHES. Measured: $LASTEXITCODE = -1 with "
                         "the gate's own completion marker absent - there is no verdict to "
                         "read, not merely a discarded one." % (gate, eater))
        else:
            lines.append("  `%s` is piped into `%s`, so the pipeline returns %s's status, not "
                         "the gate's. The gate can FAIL and this command still succeed."
                         % (gate, eater, eater))
    lines.append("  Fix: capture it explicitly - `CMD > out.txt; echo \"EXIT=$?\"; tail out.txt`"
                 " - or `set -o pipefail` first, or read ${PIPESTATUS[0]}.")
    lines.append("  In PowerShell: run the gate on its own line and read $LASTEXITCODE. "
                 "`Select-Object -Last`, `Select-String` and `Measure-Object` are SAFE there "
                 "(measured); `-First` and `-Index` are not.")
    lines.append("  Reading the printed text instead of the exit code is not a substitute: a "
                 "gate that dies early prints nothing and looks identical to one that is quiet.")
    return "\n".join(lines)


def dialect(tool_name) -> str:
    """Which shell's semantics apply to this command.

    Derived from the payload's tool_name, matched against SHELL_TOOLS - the same tuple
    install.py builds its matcher from, so a shell this hook is WIRED for and a shell it can
    REASON about cannot drift apart. Anything unrecognised gets sh semantics: that is what
    every caller got before PowerShell was covered, so an unknown shell inherits the stricter
    behaviour rather than silently getting none.
    """
    if isinstance(tool_name, str) and tool_name.strip().lower() == "powershell":
        return "powershell"
    return "bash"


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
    offenders = piped_gates(command, dialect(payload.get("tool_name")))
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

# [PGG-PS] PowerShell. Every entry below is a MEASURED case, 2026-08-13, not a guess - the
# measurement is summarised at PS_SELECT above and it CONTRADICTED the prescribed fix, which
# named `Select-Object -Last` as a status-eater. It is not one.
PS_SHOULD_FIRE = (
    # the VERBATIM shape recorded in V131: -1 returned while the gate itself printed OK
    ("the shape that produced -1 in the record",
     r"python tools\check_mutation_anchors.py | Select-Object -First 1"),
    ("the `select` alias truncates identically", "python run_selftests.py | select -First 1"),
    ("-Index also tears the producer down", "python run_selftests.py | Select-Object -Index 0"),
    ("a NATIVE consumer replaces the status exactly as in sh",
     "python run_selftests.py | findstr OK"),
    ("forward slashes are the same command",
     "python tools/no_regression.py | Select-Object -First 1"),
    ("a hook selftest is a gate here too",
     r"python hooks\cap_shapes.py --selftest | Select-Object -First 1"),
)

# The criterion-3 half, and the reason this fix is NARROW. Each of these was measured to
# PRESERVE $LASTEXITCODE; firing on any of them would be a false alarm on correct work.
PS_SHOULD_STAY_QUIET = (
    ("-Last does NOT truncate (the prescribed fix was wrong here)",
     "python run_selftests.py | Select-Object -Last 5"),
    ("-Skip does not truncate", "python run_selftests.py | Select-Object -Skip 1"),
    ("Select-String is a cmdlet, not grep", "python run_selftests.py | Select-String OK"),
    ("Measure-Object is a cmdlet, not wc", "python run_selftests.py | Measure-Object -Line"),
    ("Out-File preserves the code", "python run_selftests.py | Out-File out.txt"),
    ("no gate in the pipeline at all", "Get-ChildItem | Select-Object -First 5"),
    ("$LASTEXITCODE is read explicitly",
     'python run_selftests.py | Select-Object -First 1; exit $LASTEXITCODE'),
)

# THE SHARPEST TEST OF THE FIX: the SAME command text, opposite verdicts by dialect. `sort`
# and `tee` are genuine status-eaters in sh and ALIASES for status-PRESERVING cmdlets in
# PowerShell, so a guard that reused one vocabulary for both must fail exactly here.
DIALECT_DIVERGES = (
    ("`tee` eats the status in sh, is Tee-Object in PowerShell",
     "python run_selftests.py | tee out.txt"),
    ("`sort` eats the status in sh, is Sort-Object in PowerShell",
     "python run_selftests.py | sort"),
)


def selftest() -> int:
    import io
    import subprocess

    fails = []

    # [DISARM] The protector must actually PROTECT. Both directions, both dialects - a guard that
    # any stray occurrence of a word can silence is not a guard, and one that ignores a real
    # `set -o pipefail` is one its owner deletes.
    # piped_gates() returns the OFFENDERS, so an empty list means "silenced".
    _gate = "python run_selftests.py | tail -2"
    if piped_gates("set -o pipefail; " + _gate):
        fails.append("a real `set -o pipefail` BEFORE the pipeline did not silence the guard")
    if piped_gates(_gate + "; echo ${PIPESTATUS[0]}"):
        fails.append("reading ${PIPESTATUS[0]} after the pipeline did not silence the guard")
    # [M10 2026-08-25] A COMMENTED protector protects nothing. This hook's own block message
    # teaches "or `set -o pipefail` first", so an agent taking the advice and writing it as a
    # reminder comment is the likely shape, not a contrived one.
    if not piped_gates("# remember to set -o pipefail\n" + _gate):
        fails.append("a `pipefail` inside a COMMENT before the pipeline silenced the guard (M10) "
                     "- a comment cannot set an option, and this hook's own message is what "
                     "teaches people to write that word in the first place")
    if not piped_gates(_gate + "  # check PIPESTATUS"):
        fails.append("a PIPESTATUS mentioned only in a TRAILING COMMENT silenced the guard (M10)")
    # [PG-QUOTED] The adjudicated KNOWN LIMIT, pinned so it cannot be reversed by accident: after
    # comment-stripping this is still a substring test, so executable text containing the word
    # reads as protective. Asserted in the direction it actually behaves, with the reason in
    # _is_protected's docstring - tightening it would start firing on correct work.
    if piped_gates('echo "# pipefail"; ' + _gate):
        fails.append("PG-QUOTED changed: a quoted `# pipefail` no longer reads as protective. "
                     "That may be an improvement, but it is a DELIBERATE limit - re-read "
                     "_is_protected's KNOWN LIMIT note before accepting it")
    # And the over-strip control: a quoted `#` must not eat a REAL protector that follows it.
    if piped_gates("echo '# hi' ; set -o pipefail ; " + _gate):
        fails.append("a quoted `#` swallowed the rest of the line, so a REAL `set -o pipefail` "
                     "after it stopped protecting - over-stripping fires on correct work")
    if not piped_gates(_gate + "; set -o pipefail"):
        fails.append("`set -o pipefail` written AFTER the pipeline still silenced the guard - it"
                     "protects nothing there, and this hook's own advice is what teaches the "
                     "shape")
    if not piped_gates("python run_selftests.py | tail -2  # remember pipefail"):
        fails.append("the word pipefail in a COMMENT silenced a blocking guard")
    if not piped_gates(_gate, dialect="bash"):
        fails.append("the unprotected control is not flagged - the cases above prove nothing")
    if not piped_gates("python run_selftests.py | tail -2; exit $LASTEXITCODE", dialect="bash"):
        fails.append("LASTEXITCODE - which is meaningless in sh - silenced the BASH guard")

    # [PS-ABBREV] the unambiguous abbreviations PowerShell actually accepts
    for spelling in ("-First", "-first", "-fir", "-f"):
        if not piped_gates("python run_selftests.py | select %s 1" % spelling,
                           dialect="powershell"):
            fails.append("PowerShell `select %s 1` was not detected as truncating; PowerShell "
                         "accepts any unambiguous prefix" % spelling)
    if piped_gates("python run_selftests.py | select -i 1", dialect="powershell"):
        fails.append("`-i` was treated as truncating - it is ambiguous with -InputObject, so "
                     "PowerShell rejects it and the guard would fire on a command that cannot run")

    # [ROSTER] coverage DERIVED from the gate registry, with the denominator printed. A hardcoded
    # GATE_TOKENS left 3 enforcing gates invisible, the ship bar among them.
    import ast
    _repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        _tree = ast.parse(io.open(os.path.join(_repo, "run_selftests.py"),
                                  encoding="utf-8").read())
        _rows = next(ast.literal_eval(n.value) for n in ast.walk(_tree)
                     if isinstance(n, ast.Assign)
                     and any(getattr(t, "id", "") == "AUX_GATES" for t in n.targets))
    except (OSError, SyntaxError, ValueError, StopIteration) as _exc:
        _rows = ()
        fails.append("could not read AUX_GATES to check gate coverage (%s) - this check must "
                     "never pass by failing to look" % _exc)
    _uncovered = []
    for _label, _parts, _extra in _rows:
        _invocation = "python %s %s | tail -1" % ("/".join(_parts), " ".join(_extra))
        if not piped_gates(_invocation):
            _uncovered.append(_label)
    if _uncovered:
        fails.append("%d of %d registered gate(s) are INVISIBLE to GATE_TOKENS, so piping them "
                     "into a status-eater is not blocked: %s"
                     % (len(_uncovered), len(_rows), ", ".join(_uncovered)))
    print("-- piped-gate: gate coverage %d of %d AUX_GATES row(s) detected"
          % (len(_rows) - len(_uncovered), len(_rows)))
    for label, cmd in SHOULD_FIRE:
        if not piped_gates(cmd):
            fails.append("BLIND to %s: %r" % (label, cmd))
    for label, cmd in SHOULD_STAY_QUIET:
        got = piped_gates(cmd)
        if got:
            fails.append("FALSE POSITIVE on %s: %r -> %r" % (label, cmd, got))

    # [PGG-PS] the same two directions under PowerShell semantics
    for label, cmd in PS_SHOULD_FIRE:
        if not piped_gates(cmd, "powershell"):
            fails.append("PS BLIND to %s: %r" % (label, cmd))
    for label, cmd in PS_SHOULD_STAY_QUIET:
        got = piped_gates(cmd, "powershell")
        if got:
            fails.append("PS FALSE POSITIVE on %s: %r -> %r" % (label, cmd, got))

    # the divergence itself, asserted in BOTH directions so neither dialect can quietly
    # inherit the other's vocabulary
    for label, cmd in DIALECT_DIVERGES:
        if not piped_gates(cmd, "bash"):
            fails.append("sh must still FIRE on %s: %r" % (label, cmd))
        if piped_gates(cmd, "powershell"):
            fails.append("PowerShell must stay QUIET on %s: %r" % (label, cmd))

    # the -First finding must be reported as a TRUNCATION, not as a replaced status: the two
    # need different fixes, and telling a user their code was discarded when it never ran is
    # the same class of false statement FTB-GATES was.
    ps_kinds = {k for _g, _e, k in piped_gates(
        "python run_selftests.py | Select-Object -First 1", "powershell")}
    if ps_kinds != {"truncates"}:
        fails.append("-First must be reported as 'truncates', got %r" % (ps_kinds,))
    sh_kinds = {k for _g, _e, k in piped_gates("python run_selftests.py | tail -2", "bash")}
    if sh_kinds != {"replaces"}:
        fails.append("a sh eater must be reported as 'replaces', got %r" % (sh_kinds,))

    # dialect() is the WIRING between install's matcher and this vocabulary. Assert it maps
    # every tool in SHELL_TOOLS to a dialect this hook actually implements - a tool wired but
    # unreasoned-about would be PGG-PS again, one shell along.
    if dialect("PowerShell") != "powershell" or dialect("powershell") != "powershell":
        fails.append("dialect() does not recognise PowerShell")
    if dialect("Bash") != "bash" or dialect(None) != "bash" or dialect(5) != "bash":
        fails.append("dialect() must fall back to sh semantics on anything unrecognised")

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

    def pl(cmd, tool="Bash"):
        return json.dumps({"tool_name": tool, "tool_input": {"command": cmd}})

    # [PGG-PS] the DECISION path under a PowerShell payload, not just the detector. This is
    # the half that did not exist: the hook was registered matcher "Bash", so for a PowerShell
    # user it never ran at all and its vocabulary was moot.
    rc, err = drive(pl(r"python tools\check_mutation_anchors.py | Select-Object -First 1",
                       "PowerShell"))
    if rc != 2:
        fails.append("main() must BLOCK a truncated gate in PowerShell, got rc=%r" % rc)
    if "TRUNCATES" not in err:
        fails.append("the PowerShell block must say the gate was TRUNCATED: %r" % err[:160])
    rc, err = drive(pl("python run_selftests.py | Select-Object -Last 5", "PowerShell"))
    if rc != 0 or err:
        fails.append("main() must stay SILENT on -Last in PowerShell (measured safe), "
                     "got rc=%r err=%r" % (rc, err[:120]))

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

    print("-- piped-gate: %d gate token(s), %d status-eater(s), %d shell(s) wired %r"
          % (len(GATE_TOKENS), len(STATUS_EATERS), len(SHELL_TOOLS), list(SHELL_TOOLS)))
    print("-- piped-gate: sh %d fire / %d quiet, PowerShell %d fire / %d quiet, "
          "%d dialect-divergence pair(s) asserted both ways"
          % (len(SHOULD_FIRE), len(SHOULD_STAY_QUIET), len(PS_SHOULD_FIRE),
             len(PS_SHOULD_STAY_QUIET), len(DIALECT_DIVERGES)))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
