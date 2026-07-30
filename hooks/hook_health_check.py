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

# A hook that legitimately has no selftest goes here, explicitly. Empty today: every hook in
# this suite is self-testable, so ADDING one without a selftest is what turns the gate red.
KNOWN_NO_SELFTEST = frozenset()

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
_SELFTEST_TIMEOUT_S = 45
_WEEK_DAYS = 7
_SCRIPT_EXTS = (".py", ".js", ".ps1", ".sh")


def _days_since(datestr: str) -> int:
    try:
        then = datetime.date.fromisoformat(datestr.strip())
        return (datetime.date.today() - then).days
    except ValueError:
        return 10_000  # unparseable -> due


def run_weekly_selftests(hook_paths: list[str], state_dir: str) -> tuple[list[str], int, int, int]:
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
                return [], 0, 0, 0
    except OSError:
        pass  # no marker -> due
    problems: list[str] = []
    n = 0
    n_passed = 0
    n_skipped = 0
    for path in hook_paths:
        if not os.path.exists(path):
            problems.append(f"weekly selftest: missing hook {os.path.basename(path)}")
            continue
        n += 1
        try:
            proc = subprocess.run([sys.executable, path, "--selftest"],
                                  capture_output=True, text=True,
                                  timeout=_SELFTEST_TIMEOUT_S, stdin=subprocess.DEVNULL,
                                  encoding="utf-8", errors="replace")
            if proc.returncode == 0:
                n_passed += 1
            elif proc.returncode == SKIP_RC:
                n_skipped += 1
            else:
                tail = (proc.stdout or proc.stderr or "").strip().splitlines()
                problems.append(f"weekly selftest FAILED: {os.path.basename(path)}"
                                f" ({tail[-1][:90] if tail else 'no output'})")
        except (OSError, subprocess.SubprocessError):
            problems.append(f"weekly selftest ERRORED/timed out: {os.path.basename(path)}")
    # The marker suppresses the sweep for a week, so it may only be written when the sweep
    # actually VERIFIED everything. A skipped selftest verified nothing; treating it as a pass
    # would buy a week of silence for a hook nobody tested - the same trade this whole plan
    # exists to stop. Re-check next session instead.
    if not problems and not n_skipped:
        try:
            os.makedirs(state_dir, exist_ok=True)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(datetime.date.today().isoformat() + "\n")
        except OSError:
            pass
    return problems, n, n_passed, n_skipped


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
    swept = selftestable_hooks()
    total_hooks = len(all_hook_files())
    weekly_problems, n_run, n_passed, n_skipped = run_weekly_selftests(swept, _STATE_DIR)
    problems += weekly_problems
    weekly_note = ""
    if n_run:
        # Name the DENOMINATOR. "weekly selftests 10/10 OK" was true and useless: it counted
        # only the hooks somebody had remembered to list, so a shrinking sample was invisible.
        weekly_note = f", weekly selftests {n_passed}/{n_run} OK"
        if n_skipped:
            weekly_note += f" ({n_skipped} could not run)"
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
        state = os.path.join(td, "state")
        probs, n, n_passed, n_skipped = run_weekly_selftests([ok_hook, bad_hook], state)
        if n != 2 or n_passed != 1 or not any("bad_hook.py" in p for p in probs):
            fails.append(f"weekly runner counts wrong: n={n} passed={n_passed} probs={probs}")
        if os.path.exists(os.path.join(state, _WEEKLY_MARKER)):
            fails.append("weekly marker written despite a failure")
        # missing hook is reported but does not inflate the run count
        probs_m, n_m, passed_m, _ = run_weekly_selftests(
            [ok_hook, os.path.join(td, "gone.py")], state)
        if n_m != 1 or passed_m != 1 or not any("missing hook" in p for p in probs_m):
            fails.append(f"missing-hook accounting wrong: n={n_m} passed={passed_m} probs={probs_m}")
        # [finding 32] a SKIP must never be counted as a pass - that is how a gate evaporates
        probs_s, n_s, passed_s, skipped_s = run_weekly_selftests([ok_hook, skip_hook], state)
        if skipped_s != 1 or passed_s != 1 or n_s != 2:
            fails.append(f"skip accounting wrong: n={n_s} passed={passed_s} skipped={skipped_s}")
        if any("skip_hook" in p for p in probs_s):
            fails.append("a skip was reported as a failure rather than a skip")
        probs2, n2, passed2, _ = run_weekly_selftests([ok_hook], state)
        if probs2 or n2 != 1 or passed2 != 1 or not os.path.exists(os.path.join(state, _WEEKLY_MARKER)):
            fails.append(f"all-pass run did not write the marker: {probs2} n={n2} passed={passed2}")
        probs3, n3, _, _ = run_weekly_selftests([ok_hook], state)  # within the week -> skip
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
