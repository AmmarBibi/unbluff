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
# The two entries are the split-out selftest suites for the hooks whose bodies exceeded the
# 800-line rule (P12). They ARE the tests - a module whose only job is testing another one does
# not need one of its own - and giving them their own dispatch would make run_selftests execute
# both suites twice, doubling the slowest job in the gate.
KNOWN_NO_SELFTEST = frozenset({
    "fast_test_on_stop_selftest.py",
    "pre_push_gate_selftest.py",
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
_SELFTEST_TIMEOUT_S = 20
# AGGREGATE budget for one session's slice of the sweep. There was none: a 45s per-hook cap
# with 14 hooks and no total deadline, in a SessionStart hook that install.py registered with
# no `timeout` and therefore inherited the 60s host default. Measured warm on this machine:
# 34.7s total, 58% of that budget on a fast box, and the marker was written only AFTER the
# whole loop - so one overrun meant the sweep was killed, nothing was recorded, and it started
# from scratch next session, potentially never finishing. The sweep is now sliced and RESUMABLE:
# each hook's result is persisted the moment it is known.
_WEEKLY_BUDGET_S = 25
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
                elif shutil.which(exe) is None:
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
        for p in problems[:12]:
            print(f"  - {p}")
        if len(problems) > 12:
            print(f"  ... and {len(problems) - 12} more")
    else:
        print(f"[hook-health] OK - {n_cmd} hook commands verified{weekly_note}")
    return 0


def _selftest_malformed_config() -> list:
    """[P13 C4/C5] A malformed sub-tree must cost that sub-tree, never the whole report."""
    fails = []
    shapes = [
        {"hooks": "not-a-dict"},
        {"hooks": ["not-a-dict"]},
        {"hooks": {"Stop": "not-a-list"}},
        {"hooks": {"Stop": {"not": "a list"}}},
        {"hooks": {"Stop": [{"hooks": "not-a-list"}]}},
        {"hooks": {"Stop": [{"hooks": [{"command": {"a": 1}}]}]}},
        {"hooks": {"Stop": [{"hooks": [{"command": 42, "args": "not-a-list"}]}]}},
        {"hooks": {"Stop": [{"hooks": [{"command": None}]}]}},
        {"hooks": None},
        "not-a-dict-at-all",
    ]
    for shape in shapes:
        try:
            list(_iter_hook_commands(shape))
        except Exception as e:
            fails.append("_iter_hook_commands raised on %r: %r - one bad sub-tree discards "
                         "the entire hook-health report" % (shape, e))
    # a non-string command must be REPORTED, not merely survived: surviving in silence still
    # leaves the malformed entry unmentioned, which is half the defect.
    bad = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": 42}]}]}}
    try:
        n_cmd, problems = check_config(bad)
    except Exception as e:
        fails.append("check_config raised on a non-string command: %r" % (e,))
    else:
        if not any("not a string" in str(p_) for p_ in problems):
            fails.append("a non-string hook command was not reported: %r" % (problems,))
    return fails


def selftest() -> int:
    fails = []
    # 0. [finding 18] the weekly sweep must be DETECTED, not listed. The roster it replaced
    # excluded all four v1.3.0 hooks, so any of them could be broken outright while the line
    # printed at every SessionStart still read "weekly selftests 10/10 OK". run_selftests.py
    # had the identical roster; both now call selftestable_hooks(), so there is no twin left
    # to drift. Assert the OUTCOME (these names are swept) and the MECHANISM (a brand-new
    # self-testable hook is picked up with no edit to any list).
    _detected = {os.path.basename(p) for p in selftestable_hooks()}
    for _name in ("pre_push_gate.py", "close_skills_guard.py",
                  "duplicate_registration_check.py", "usage_snip_prompt.py"):
        if _name not in _detected:
            fails.append(f"weekly sweep does not cover {_name} - breaking it would still "
                         f"report all-green")
    if len(_detected) < len(_LOCAL_HOOKS_FLOOR):
        fails.append(f"detection ({len(_detected)}) found fewer hooks than the floor "
                     f"({len(_LOCAL_HOOKS_FLOOR)})")
    if floor_violations():
        fails.append(f"floor violations in the live hooks dir: {floor_violations()}")

    import tempfile
    with tempfile.TemporaryDirectory() as _d:
        with open(os.path.join(_d, "brand_new_hook.py"), "w", encoding="utf-8") as f:
            f.write('import sys\nif "--selftest" in sys.argv:\n    print("SELFTEST OK")\n')
        with open(os.path.join(_d, "argv_form_hook.py"), "w", encoding="utf-8") as f:
            f.write('def main(argv):\n    return 0\nif "--selftest" in argv:\n    pass\n')
        with open(os.path.join(_d, "no_selftest_hook.py"), "w", encoding="utf-8") as f:
            f.write('"""Mentions --selftest in prose only, so it must NOT be detected."""\n')
        _got = {os.path.basename(p) for p in selftestable_hooks(_d)}
        if _got != {"brand_new_hook.py", "argv_form_hook.py"}:
            fails.append(f"detection wrong on a synthetic dir: {sorted(_got)} "
                         f"(a prose mention must not count; both argv forms must)")
        if len(all_hook_files(_d)) != 3:
            fails.append("all_hook_files() is not counting the full denominator")
        # a hook with no selftest and no explicit opt-out must turn the gate red, not vanish
        if not any("no_selftest_hook.py" in v for v in floor_violations(_d)):
            fails.append("a hook with no selftest is silently dropped instead of flagged")

    # 0b. [finding 19] THE TWIN MUST NOT COME BACK. run_selftests.py held a byte-identical
    # copy of this detector's roster; one was fixed and the other was not, which is the whole
    # reason finding 18 survived to v1.3.0. Fixing both lists would leave the same trap for the
    # next person, so the durable property is that exactly ONE implementation exists - and
    # that is what this asserts. Any second `def has_selftest` or `_DISPATCH_RE` is a twin.
    _root = os.path.dirname(_HOOKS_DIR)
    _twins = []
    for _p in (all_hook_files() + sorted(glob.glob(os.path.join(_root, "*.py")))
               + sorted(glob.glob(os.path.join(_root, "tools", "*.py")))):
        if os.path.abspath(_p) == os.path.abspath(__file__):
            continue
        try:
            with open(_p, encoding="utf-8", errors="replace") as _f:
                _txt = _f.read()
        except OSError:
            continue
        # Anchored to a real definition at the start of a line. An unanchored substring match
        # fired on tools/mutation_check.py, whose mutation TABLE quotes these names as data -
        # a detector that cannot tell a definition from a string is its own false alarm.
        if re.search(r"^\s*def has_selftest\b", _txt, re.M) or \
                re.search(r"^\s*_DISPATCH_RE\s*=", _txt, re.M):
            _twins.append(os.path.basename(_p))
    if _twins:
        fails.append(f"a SECOND selftest detector exists in {_twins} - import "
                     f"selftestable_hooks() instead; two copies of one rule is the defect")

    # 0c. [plan item 38, corrected] "registered once, but from the wrong root". The live
    # config wired close_skills_guard and usage_snip_prompt to ~/.claude/hooks copies that
    # had DIVERGED from the repo, so a whole release of fixes never ran. No existing check
    # could see it: not a duplicate, not a missing file. Must be caught even when the stale
    # copy is byte-identical, because it will not stay identical.
    with tempfile.TemporaryDirectory() as _sd:
        _elsewhere = os.path.join(_sd, "elsewhere")
        os.makedirs(_elsewhere, exist_ok=True)
        _victim = os.path.basename(all_hook_files()[0])
        _stale = os.path.join(_elsewhere, _victim)
        with open(_stale, "w", encoding="utf-8") as f:
            f.write("# a DIVERGED copy of a hook this suite ships\n")
        _cfg = {"hooks": {"SessionStart": [{"hooks": [
            {"command": '"%s" "%s"' % (sys.executable, _stale)}]}]}}
        _probs = stale_root_registrations(_cfg)
        if not any(_victim in p for p in _probs):
            fails.append(f"a hook registered from the WRONG root ({_stale}) was not flagged")
        elif not any("DIFFERENT PROGRAMS" in p for p in _probs):
            fails.append(f"wrong-root registration flagged but divergence not named: {_probs}")
        # and a correctly-wired one must stay silent
        _ok_cfg = {"hooks": {"SessionStart": [{"hooks": [
            {"command": '"%s" "%s"' % (sys.executable, all_hook_files()[0])}]}]}}
        if stale_root_registrations(_ok_cfg):
            fails.append("false positive on a hook registered from its own directory")
        # a path with a SPACE must not slip past the tokenizer (same class as finding 21)
        _spaced_dir = os.path.join(_sd, "John Doe", "hooks")
        os.makedirs(_spaced_dir, exist_ok=True)
        _spaced = os.path.join(_spaced_dir, _victim)
        with open(_spaced, "w", encoding="utf-8") as f:
            f.write("# diverged\n")
        _sp_cfg = {"hooks": {"SessionStart": [{"hooks": [
            {"command": '"%s" "%s"' % (sys.executable, _spaced)}]}]}}
        if not any(_victim in p for p in stale_root_registrations(_sp_cfg)):
            fails.append("a wrong-root registration with a SPACE in the path was missed")

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
    # 5. args-style declaration: the script must be validated, not just the interpreter
    import tempfile
    missing = os.path.join(os.sep, "nope", "args_style_missing.py")
    args_cfg = {"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": sys.executable, "args": [missing]}]}]}}
    _, probs = check_config(args_cfg)
    if not any("missing script" in p for p in probs):
        fails.append("args-style missing script NOT caught (only `command` was read)")

    # 6. duplicate registration: same script name from two directories must be reported
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        for d in (d1, d2):
            with open(os.path.join(d, "dupe.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
        with open(os.path.join(d1, "solo.py"), "w", encoding="utf-8") as f:
            f.write("y = 1\n")
        dup_cfg = {"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": f'"{sys.executable}" "{os.path.join(d1, "dupe.py")}"'},
            {"type": "command", "command": sys.executable, "args": [os.path.join(d2, "dupe.py")]},
            {"type": "command", "command": f'"{sys.executable}" "{os.path.join(d1, "solo.py")}"'},
        ]}]}}
        _, probs = check_config(dup_cfg)
        if not any("dupe.py registered from 2 directories" in p for p in probs):
            fails.append(f"duplicate registration NOT caught: {probs}")
        if any("solo.py registered" in p for p in probs):
            fails.append("false positive: singly-registered hook flagged as duplicate")

    # 7. weekly selftest runner: catches a failing hook, marker written only on all-pass, counts pass/run
    with tempfile.TemporaryDirectory() as td:
        ok_hook = os.path.join(td, "ok_hook.py")
        bad_hook = os.path.join(td, "bad_hook.py")
        with open(ok_hook, "w", encoding="utf-8") as f:
            f.write("import sys; sys.exit(0)\n")
        with open(bad_hook, "w", encoding="utf-8") as f:
            f.write("print('SELFTEST FAIL: broken'); import sys; sys.exit(1)\n")
        state = os.path.join(td, "state")
        # a selftest that cannot RUN (exit SKIP_RC) is neither a pass nor a failure
        skip_hook = os.path.join(td, "skip_hook.py")
        with open(skip_hook, "w", encoding="utf-8") as f:
            f.write("print('SELFTEST SKIP: git unavailable'); import sys; sys.exit(77)\n")
        # Each sub-case gets its OWN state dir: the sweep is now resumable, so `done` persists
        # between calls sharing a state dir and the counts are cumulative by design.
        def _state(tag):
            return os.path.join(td, "state-" + tag)

        probs, n, n_passed, n_skipped, _ = run_weekly_selftests(
            [ok_hook, bad_hook], _state("a"))
        if n != 2 or n_passed != 1 or not any("bad_hook.py" in p for p in probs):
            fails.append(f"weekly runner counts wrong: n={n} passed={n_passed} probs={probs}")
        if os.path.exists(os.path.join(_state("a"), _WEEKLY_MARKER)):
            fails.append("weekly marker written despite a failure")
        # missing hook is reported but does not inflate the run count
        probs_m, n_m, passed_m, _, _ = run_weekly_selftests(
            [ok_hook, os.path.join(td, "gone.py")], _state("b"))
        if n_m != 1 or passed_m != 1 or not any("missing hook" in p for p in probs_m):
            fails.append(f"missing-hook accounting wrong: n={n_m} passed={passed_m} probs={probs_m}")
        # [finding 32] a SKIP must never be counted as a pass - that is how a gate evaporates
        probs_s, n_s, passed_s, skipped_s, _ = run_weekly_selftests(
            [ok_hook, skip_hook], _state("c"))
        if skipped_s != 1 or passed_s != 1 or n_s != 2:
            fails.append(f"skip accounting wrong: n={n_s} passed={passed_s} skipped={skipped_s}")
        if any("skip_hook" in p for p in probs_s):
            fails.append("a skip was reported as a failure rather than a skip")
        # [finding 32] and the CONSEQUENCE, not just the counts: the marker buys a week of
        # silence, and a skipped selftest verified nothing. Asserting only the counts let a
        # mutation that re-enabled the write survive - counts right, consequence wrong.
        if os.path.exists(os.path.join(_state("c"), _WEEKLY_MARKER)):
            fails.append("weekly marker written despite a SKIPPED selftest - a week of "
                         "silence bought for a hook nobody actually tested")
        probs2, n2, passed2, _, _ = run_weekly_selftests([ok_hook], _state("d"))
        if probs2 or n2 != 1 or passed2 != 1 \
                or not os.path.exists(os.path.join(_state("d"), _WEEKLY_MARKER)):
            fails.append(f"all-pass run did not write the marker: {probs2} n={n2} passed={passed2}")
        probs3, n3, _, _, _ = run_weekly_selftests([ok_hook], _state("d"))  # within week -> skip
        if n3 != 0:
            fails.append(f"weekly skip not honored: n={n3}")

        # [D11] AGGREGATE budget + RESUMABILITY. There was no total deadline: 14 hooks at a 45s
        # per-hook cap inside a SessionStart hook that inherited the 60s host default, with the
        # marker written only after the whole loop - so an overrun was killed having recorded
        # NOTHING and started from scratch next session, potentially never completing.
        if _SELFTEST_TIMEOUT_S >= _WEEKLY_BUDGET_S:
            fails.append(f"per-hook cap ({_SELFTEST_TIMEOUT_S}s) >= aggregate budget "
                         f"({_WEEKLY_BUDGET_S}s): one slow hook consumes the whole slice")
        slow = os.path.join(td, "slow_hook.py")
        with open(slow, "w", encoding="utf-8") as f:
            f.write("import time; time.sleep(3); print('SELFTEST OK')\n")
        slow2 = os.path.join(td, "slow2_hook.py")
        with open(slow2, "w", encoding="utf-8") as f:
            f.write("import time; time.sleep(3); print('SELFTEST OK')\n")
        st = _state("budget")
        p1, c1, ok1, _, left1 = run_weekly_selftests([slow, slow2, ok_hook], st, budget_s=1)
        if c1 != 1:
            fails.append(f"budget not enforced: ran {c1} hooks with a 1s aggregate budget")
        if left1 != 2:
            fails.append(f"incomplete sweep did not report what was LEFT: left={left1} - "
                         f"a shrinking sample must never be invisible")
        if os.path.exists(os.path.join(st, _WEEKLY_MARKER)):
            fails.append("marker written for an INCOMPLETE sweep - a week of false silence")
        if not os.path.exists(os.path.join(st, _WEEKLY_PROGRESS)):
            fails.append("no progress persisted - the next session restarts from scratch")
        # resume: the already-proved hook must NOT be re-run, and the sweep must finish
        p2, c2, ok2, _, left2 = run_weekly_selftests([slow, slow2, ok_hook], st, budget_s=60)
        if c2 != 3 or ok2 != 3:
            fails.append(f"resume did not complete the sweep: n={c2} passed={ok2} probs={p2}")
        if p2 or left2:
            fails.append(f"completed resume still reported problems: {p2} left={left2}")
        if not os.path.exists(os.path.join(st, _WEEKLY_MARKER)):
            fails.append("completed sweep did not write the marker")
        if os.path.exists(os.path.join(st, _WEEKLY_PROGRESS)):
            fails.append("progress file not cleared after a completed sweep")
    fails += _selftest_malformed_config()
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
