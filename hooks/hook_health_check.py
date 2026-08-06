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
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import capped_report  # noqa: E402  ONE way to cap a findings list, shared by six hooks
import selftest_budget  # noqa: E402  ONE declaration of the per-hook selftest cap

# How many problems the one-line health report prints before it says how many it held back.
MAX_PROBLEM_BULLETS = 12

# FLOOR, not a roster. These names must REMAIN self-testable; losing a --selftest dispatch is
# an error rather than a silent skip. Which hooks actually get swept is DETECTED below.
#
# This was a hardcoded roster and it drifted: all four v1.3.0 hooks (pre_push_gate,
# close_skills_guard, duplicate_registration_check, usage_snip_prompt) were absent, so the
# sweep could break any of them outright and still print "weekly selftests 10/10 OK" on the
# one line that is read at every SessionStart. run_selftests.py carried the IDENTICAL roster
# and was converted to detection on 2026-07-29 - this twin was left behind, which is why
# both now call the single detector below instead of keeping a list each.
_LOCAL_HOOKS_FLOOR = ("rate_prompt.py", "fast_test_on_stop.py", "show_your_proof.py",
                      "meta_audit_on_stop.py", "memory_hygiene_guard.py", "stop_dispatcher.py",
                      "hook_health_check.py", "plan_defer_guard.py", "post_tooluse_dispatcher.py",
                      "numbers_match_on_write.py")

# Matches a real membership test, in either form used in this repo:
#   "--selftest" in sys.argv   (most hooks)     "--selftest" in argv   (pre_push_gate)
# Requires the dispatch itself, so a docstring mentioning --selftest cannot false-positive.
_DISPATCH_RE = re.compile(r"""["']--selftest["']\s+in\s+(?:sys\.)?argv\b""")

# A hook that legitimately has no selftest goes here, explicitly. A FLOOR, not a filter:
# everything NOT listed here that lacks a --selftest turns the gate red rather than skipping
# in silence, so each entry is a statement somebody had to write down.
#
# The entries are the split-out selftest suites for the hooks whose bodies exceeded the
# 800-line rule (P12). They ARE the tests - a module whose only job is testing another one does
# not need one of its own - and giving them their own dispatch would make run_selftests execute
# those suites twice, doubling the slowest job in the gate.
KNOWN_NO_SELFTEST = frozenset({
    "fast_test_on_stop_selftest.py",
    "pre_push_gate_selftest.py",
    # Added 2026-08-06: HB-1 took this file to 858 lines. M3 had recorded it at 790 precisely
    # so the next addition would be a deliberate decision, and B3-P set the precedent that the
    # answer is to MOVE rather than log the violation. 536 + 359 now.
    "hook_health_check_selftest.py",
})

SKIP_RC = 77  # a selftest that could not run (no git/sh). Not a pass, not a failure.


def has_selftest(path: str) -> bool:
    """True iff this file actually dispatches on --selftest (not merely mentions it)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return bool(_DISPATCH_RE.search(f.read()))
    except OSError:
        return False


def selftestable_hooks(hooks_dir: str = None) -> list:
    """Every hook file that dispatches on --selftest. DETECTION, not a list.

    A roster silently drops whatever nobody remembered to add, and still reports all-green -
    the denominator shrinks without the numerator ever looking wrong. This is the single
    detector; run_selftests.py imports it rather than keeping a second copy that can drift.
    """
    d = hooks_dir or _HOOKS_DIR
    return [p for p in sorted(glob.glob(os.path.join(d, "*.py"))) if has_selftest(p)]


def all_hook_files(hooks_dir: str = None) -> list:
    """Every hook file, self-testable or not - the DENOMINATOR, so a shrinking sample shows."""
    return sorted(glob.glob(os.path.join(hooks_dir or _HOOKS_DIR, "*.py")))


def floor_violations(hooks_dir: str = None) -> list:
    """Names in the floor that have gone missing or lost their --selftest dispatch."""
    d = hooks_dir or _HOOKS_DIR
    out = []
    for name in _LOCAL_HOOKS_FLOOR:
        p = os.path.join(d, name)
        if not os.path.exists(p):
            out.append(f"selftest floor: {name} is missing from {d}")
        elif not has_selftest(p):
            out.append(f"selftest floor: {name} no longer dispatches on --selftest")
    for p in all_hook_files(d):
        name = os.path.basename(p)
        if not has_selftest(p) and name not in KNOWN_NO_SELFTEST:
            out.append(f"selftest floor: {name} has no --selftest and is not in KNOWN_NO_SELFTEST")
    return out
_STATE_DIR = os.environ.get("UNBLUFF_STATE_DIR") or os.path.join(
    os.path.expanduser("~"), ".claude", "hooks", "state")
_WEEKLY_MARKER = "hook-health-weekly-selftest.txt"
_WEEKLY_PROGRESS = "hook-health-weekly-progress.json"
# Raised from 20 with the aggregate below, together. The suite legitimately grew: the D10
# grandchild case must outlive the runner's own timeout to mean anything, and shaving it to
# fit made the mutation survive on Windows - the test checked for the survivor marker before
# a real survivor would have written it. A cap a HEALTHY selftest exceeds does not catch a
# broken hook, it manufactures "ERRORED/timed out" for a passing one. Measured 2026-07-31:
# slowest is fast_test_on_stop at ~19.7s warm.
# [P14 D1] READ, never re-declared. This is the number passed as `timeout=` to the subprocess
# below, so the number every hook budgets against IS the number that kills it - they cannot
# drift apart, because they are one object. The literal that used to live here drifted from
# reality by 2 days and 5 seconds, and fast_test_on_stop quietly grew past it.
_SELFTEST_TIMEOUT_S = selftest_budget.SELFTEST_TIMEOUT_S
# AGGREGATE budget for one session's slice of the sweep. There was none: a 45s per-hook cap
# with 14 hooks and no total deadline, in a SessionStart hook that install.py registered with
# no `timeout` and therefore inherited the 60s host default. Measured warm on this machine:
# 34.7s total, 58% of that budget on a fast box, and the marker was written only AFTER the
# whole loop - so one overrun meant the sweep was killed, nothing was recorded, and it started
# from scratch next session, potentially never finishing. The sweep is now sliced and RESUMABLE:
# each hook's result is persisted the moment it is known.
_WEEKLY_BUDGET_S = 40   # must stay ABOVE _SELFTEST_TIMEOUT_S (asserted) and well under the
                        # 60s SessionStart host default; the sweep is sliced and resumable, so
                        # a slice that runs out simply continues next session.
_WEEK_DAYS = 7
_SCRIPT_EXTS = (".py", ".js", ".ps1", ".sh")


def _days_since(datestr: str) -> int:
    try:
        then = datetime.date.fromisoformat(datestr.strip())
        return (datetime.date.today() - then).days
    except ValueError:
        return 10_000  # unparseable -> due


def run_weekly_selftests(hook_paths: list[str], state_dir: str,
                         budget_s: int = _WEEKLY_BUDGET_S) -> tuple:
    """Run each hook's --selftest at most once per week.

    Returns (problems, n_run, n_passed, n_skipped). The pass-marker is written ONLY when every
    selftest passes, so a failing safety net re-surfaces at every session start until it is
    fixed. n_run == 0 means 'not due'. A selftest that exits SKIP_RC could not run at all
    (no git, no sh) - counted separately and surfaced, because a skip reported as a pass is
    how a gate evaporates without anyone noticing.
    """
    marker = os.path.join(state_dir, _WEEKLY_MARKER)
    try:
        with open(marker, encoding="utf-8") as f:
            if _days_since(f.read()) < _WEEK_DAYS:
                return [], 0, 0, 0, 0
    except OSError:
        pass  # no marker -> due

    progress_path = os.path.join(state_dir, _WEEKLY_PROGRESS)
    done = {}
    try:
        with open(progress_path, encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            # [HIGH-1] Age-stamp the slice. Without this, a sweep that can never complete -
            # e.g. a hook listed but missing, whose problem is appended without ever entering
            # `done` - freezes every recorded "pass" indefinitely, so those hooks are never
            # re-run again either. A partial slice older than the week it belongs to is stale
            # and starts over.
            started = saved.get("__started__")
            if isinstance(started, str) and _days_since(started) < _WEEK_DAYS:
                done = {k: v for k, v in saved.items() if k != "__started__"}
    except (OSError, ValueError):
        done = {}
    started_on = datetime.date.today().isoformat()

    def _persist():
        # After EVERY hook, not after the loop. The whole point is that a session killed
        # mid-sweep keeps what it proved instead of starting over forever.
        try:
            os.makedirs(state_dir, exist_ok=True)
            with open(progress_path, "w", encoding="utf-8") as fh:
                payload = dict(done)
                payload["__started__"] = started_on
                json.dump(payload, fh)
        except OSError:
            pass

    problems: list[str] = []
    deadline = time.monotonic() + budget_s
    remaining = 0
    for path in hook_paths:
        name = os.path.basename(path)
        if not os.path.exists(path):
            problems.append(f"weekly selftest: missing hook {name}")
            continue
        # ONLY a recorded PASS may be skipped. [HIGH-1, a regression from the D11 resumability
        # rewrite] `if name in done` treated a persisted "fail" and "skip" as proved: on the
        # next session the failing hook was skipped, `problems` came back empty, and the marker
        # at the bottom was written - buying SEVEN DAYS of "[hook-health] OK" over a hook that
        # had actually failed. The mirror image was just as bad: a "skip" blocks the marker
        # forever while every hook is already in `done`, so the sweep is permanently due and
        # permanently runs nothing. Re-running fail/skip re-appends their problem text, which
        # is what keeps the gate at the bottom closed.
        if done.get(name) == "pass":
            continue                      # already proved in an earlier slice
        if time.monotonic() >= deadline:
            remaining += 1                # out of budget: leave it for the next session
            continue
        try:
            proc = subprocess.run([sys.executable, path, "--selftest"],
                                  capture_output=True, text=True,
                                  timeout=_SELFTEST_TIMEOUT_S, stdin=subprocess.DEVNULL,
                                  encoding="utf-8", errors="replace")
            if proc.returncode == 0:
                done[name] = "pass"
            elif proc.returncode == SKIP_RC:
                done[name] = "skip"
            else:
                tail = (proc.stdout or proc.stderr or "").strip().splitlines()
                done[name] = "fail"
                problems.append(f"weekly selftest FAILED: {name}"
                                f" ({tail[-1][:90] if tail else 'no output'})")
        except (OSError, subprocess.SubprocessError):
            done[name] = "fail"
            problems.append(f"weekly selftest ERRORED/timed out: {name}")
        _persist()

    n = len(done)
    n_passed = sum(1 for v in done.values() if v == "pass")
    n_skipped = sum(1 for v in done.values() if v == "skip")
    if remaining:
        # NOT a problem: a sliced sweep in progress is the normal, designed state. It must be
        # VISIBLE though - main() prints it in the denominator - because "10/10 OK" while four
        # hooks were never reached is exactly the shrinking-sample lie this file exists to stop.
        return problems, n, n_passed, n_skipped, remaining

    # The marker suppresses the sweep for a week, so it may only be written when the sweep
    # actually VERIFIED everything. A skipped selftest verified nothing; treating it as a pass
    # would buy a week of silence for a hook nobody tested - the same trade this whole plan
    # exists to stop. Re-check next session instead.
    if not problems and not n_skipped:
        try:
            os.makedirs(state_dir, exist_ok=True)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(datetime.date.today().isoformat() + "\n")
            os.remove(progress_path)
        except OSError:
            pass
    return problems, n, n_passed, n_skipped, 0


def _tokens(command: str) -> list[str]:
    """Best-effort split of a hook command string into tokens, quotes stripped."""
    try:
        raw = shlex.split(command, posix=False)
    except ValueError:
        raw = command.split()
    return [t.strip('"').strip("'") for t in raw if t.strip()]


def _script_args(h: dict) -> list[str]:
    """Script paths from a hook entry's `args` array.

    Claude Code accepts the script either inlined in `command` ("python x.py") or passed
    separately as {"command": "python", "args": ["x.py"]}. Reading only `command` validates
    the interpreter and silently skips the script - a missing script in an `args` array was
    invisible to this checker (found 2026-07-29 on a config using both styles).
    """
    return [a for a in (h.get("args") or []) if isinstance(a, str) and a.strip()]


# [HB-1] Hook commands are run BY A SHELL, so its builtins are perfectly valid executables even
# though shutil.which() - which searches PATH for a FILE - cannot see them. `echo` is the
# canonical trivial hook and is a cmd.exe builtin on Windows, so a WORKING config was reported
# as broken on the one line the user reads at every SessionStart.
#
# These are FROZEN EXTERNAL VOCABULARIES, not rosters over this repo's code. A roster rots when
# it tracks something that changes; cmd.exe's builtin set and POSIX sh's are fixed by their
# specifications. A name absent here still has to resolve on PATH, so the check keeps its teeth.
_CMD_BUILTINS = frozenset("assoc break call cd chdir cls color copy date del dir echo endlocal "
                          "erase exit for ftype goto if md mkdir mklink move path pause popd "
                          "prompt pushd rd rem ren rename rmdir set setlocal shift start time "
                          "title type ver verify vol".split())
_SH_BUILTINS = frozenset(": . [ alias bg break cd command continue echo eval exec exit export "
                         "false fg getopts hash jobs kill printf pwd read readonly return set "
                         "shift test times trap true type ulimit umask unalias unset wait".split())


def is_shell_builtin(exe: str) -> bool:
    """True iff the shell that runs hook commands would resolve `exe` without touching PATH."""
    if os.name == "nt":
        # cmd.exe is case-insensitive, and `echo.` / `echo:` are the same builtin.
        return exe.lower().rstrip(".:") in _CMD_BUILTINS
    return exe in _SH_BUILTINS


def check_config(cfg: dict) -> tuple[int, list[str]]:
    """(n_commands, problems) for a parsed settings dict.

    Defensive against hand-edited / third-party settings.json: any group or hook entry that is
    not the expected shape is reported as a problem, never allowed to raise. Checks each hook
    command's executable resolves and that any ABSOLUTE script path it references exists
    (from `command` AND `args`). Relative script paths are left alone (resolved at runtime
    against an unknown cwd). Also reports any script registered from more than one directory:
    it will run more than once per event, and if the two copies differ, which one takes effect
    is nondeterministic.
    """
    problems: list[str] = []
    n_cmd = 0
    registrations: dict[str, set[str]] = {}
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
                # [P13 C5] `(x or "")` only rescues FALSY values, so None/0/[] fell through
                # to the empty-command message but a dict, a list or an int hit .strip() and
                # took the whole report down. Report the entry, keep the report.
                raw_command = h.get("command", "")
                if raw_command is not None and not isinstance(raw_command, str):
                    problems.append(f"{event}: hook 'command' is "
                                    f"{type(raw_command).__name__}, not a string - this entry "
                                    f"cannot be validated")
                    continue
                command = (raw_command or "").strip()
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
                elif shutil.which(exe) is None and not is_shell_builtin(exe):
                    problems.append(f"{event}: executable not on PATH: {exe}")
                for tok in tokens[1:] + _script_args(h):
                    if not tok.lower().endswith(_SCRIPT_EXTS):
                        continue
                    if os.path.isabs(tok):
                        if not os.path.exists(tok):
                            problems.append(f"{event}: missing script {tok}")
                        head, _, tail = tok.replace("\\", "/").rpartition("/")
                        registrations.setdefault(tail, set()).add(head)
    for name in sorted(registrations):
        roots = sorted(registrations[name])
        if len(roots) > 1:
            problems.append(
                f"{name} registered from {len(roots)} directories - it runs once per "
                f"registration: " + " | ".join(roots))
    # de-duplicate, keep order
    seen: set[str] = set()
    problems = [p for p in problems if not (p in seen or seen.add(p))]
    return n_cmd, problems


def stale_root_registrations(cfg: dict, hooks_dir: str = None) -> list:
    """Hooks of THIS suite registered from a directory other than the one they ship in.

    Measured on this machine 2026-07-30: usage_snip_prompt and close_skills_guard were still
    wired to ~/.claude/hooks copies that had diverged from the repo by 89 and 471 AST tokens.
    Every fix to close_skills_guard therefore sat in git while the OLD program actually ran.

    Nothing reported it, because it is not a duplicate and it is not a missing file:
      * duplicate_registration_check saw exactly one registration for each - correct
      * hook_health_check saw a command that resolves to a real script - also correct
    "Registered once, from the wrong root" was a state no check had a name for, and it is
    the failure mode that makes a whole release invisible on the machine it was written on.
    Deleting the stale copies fixes today; this names the state, so it cannot come back.
    """
    d = hooks_dir or _HOOKS_DIR
    ours = {os.path.basename(p): p for p in all_hook_files(d)}
    problems = []
    for cmd in _iter_hook_commands(cfg):
        for token in _script_tokens(cmd):
            name = os.path.basename(token)
            if name not in ours:
                continue
            reg_dir = os.path.dirname(os.path.abspath(token))
            if os.path.normcase(reg_dir) == os.path.normcase(os.path.abspath(d)):
                continue
            same = _same_file(token, ours[name])
            problems.append(
                "%s is registered from %s but this suite ships it in %s (%s)" % (
                    name, reg_dir, d,
                    "identical copy" if same else "THE TWO COPIES ARE DIFFERENT PROGRAMS - "
                                                  "your fixes are not the code that runs"))
    return problems


def _same_file(a: str, b: str) -> bool:
    try:
        with open(a, "rb") as fa, open(b, "rb") as fb:
            return fa.read() == fb.read()
    except OSError:
        return False


def _iter_hook_commands(cfg: dict):
    """[P13 C4] TOTAL over any settings shape: a malformed sub-tree costs you that sub-tree,
    never the report. Every container was assumed to be the right type, so a `hooks` value that
    was a string or a list, a group list that was a dict, or a non-list `args`, raised out of
    the generator - past check_config's already-computed problem list, past floor_violations and
    past the weekly-sweep line - and the ENTIRE hook-health report was discarded. A config
    malformed enough to be worth reporting was the exact config that silenced the reporter."""
    hooks_cfg = cfg.get("hooks") if isinstance(cfg, dict) else None
    if not isinstance(hooks_cfg, dict):
        return
    for groups in hooks_cfg.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            entries = group.get("hooks")
            if not isinstance(entries, list):
                continue
            for hook in entries:
                if not isinstance(hook, dict):
                    continue
                cmd = hook.get("command")
                parts = [cmd] if isinstance(cmd, str) else []
                args = hook.get("args")
                if isinstance(args, (list, tuple)):
                    parts += [a for a in args if isinstance(a, str)]
                for part in parts:
                    yield part


def _script_tokens(text: str) -> list:
    """The .py paths in a command string, shell-tokenized (spaces in paths survive)."""
    try:
        toks = shlex.split(text, posix=False)
    except ValueError:
        toks = text.split()
    return [t.strip().strip('"').strip("'") for t in toks
            if t.strip().strip('"').strip("'").lower().endswith(".py")]


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
    problems += floor_violations()
    problems += stale_root_registrations(cfg)
    swept = selftestable_hooks()
    total_hooks = len(all_hook_files())
    weekly_problems, n_run, n_passed, n_skipped, n_left = run_weekly_selftests(swept, _STATE_DIR)
    problems += weekly_problems
    weekly_note = ""
    if n_run:
        # Name the DENOMINATOR. "weekly selftests 10/10 OK" was true and useless: it counted
        # only the hooks somebody had remembered to list, so a shrinking sample was invisible.
        weekly_note = f", weekly selftests {n_passed}/{n_run} OK"
        if n_skipped:
            weekly_note += f" ({n_skipped} could not run)"
        if n_left:
            weekly_note += f", {n_left} left for the next session"
        gap = total_hooks - len(swept)
        if gap:
            weekly_note += f"; {gap} of {total_hooks} hooks have NO selftest"
    if problems:
        print(f"[hook-health] {len(problems)} problem(s) across {n_cmd} hook commands{weekly_note}:")
        # [C1] Was a hand-rolled display cap: `for p in problems[:12]` plus a separately
        # computed "... and N more". The literal 12 sat on three different lines, so an edit to
        # one of them would make the notice lie, and the cap guard was blind to the whole
        # shape. Routed through the ONE cap helper: identical output below the cap, same line
        # count above it, and the notice now names the total and the shown count too.
        for line in capped_report.render(problems, MAX_PROBLEM_BULLETS,
                                         prefix="  - ", noun="problem"):
            print(line)
    else:
        print(f"[hook-health] OK - {n_cmd} hook commands verified{weekly_note}")
    return 0


def selftest() -> int:
    """Delegates to the sibling suite (see hook_health_check_selftest.py)."""
    import hook_health_check_selftest as _s
    return _s.selftest()


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
