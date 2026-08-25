"""Is the git clone this machine actually RUNS HOOKS OUT OF still a sane repository?

[item 10, #46] The incident left the wired clone with `core.bare=true` on a repo that HAS a
working tree, a local `core.hooksPath` aimed at a DELETED temp directory - which silently
disables every git hook on the machine - and a `t@t` fixture identity. All three were repaired
BY HAND on 2026-08-24, and nothing anywhere asked. `git_isolation.fingerprint()` catches a
fixture mutating a repo DURING a sweep, which is the upstream cause, but no check ever asked
whether THIS MACHINE's wired clone is sane RIGHT NOW - so the exact state that sat there
unnoticed for a day would sit there unnoticed again. This is REMEMBER-vs-ENFORCE applied to a
repair done by hand.

Called by hook_health_check.main() at SessionStart, which is where "is the wiring healthy"
already lives. Split into its own module on 2026-08-25 because inlining it took that file to
861 lines, over the 800 limit and in no baseline - B3-P's precedent is to MOVE rather than
record the violation, and it is item 7's own finding arriving on the session that wrote item 7.

The repositories are DERIVED from the hook commands in settings.json and never named here: a
hardcoded path would check the author's machine and nobody else's.

Run with --selftest to verify the checks themselves. Every RED case is paired with a GREEN
control on a healthy repository, because a check that always fires proves nothing.
"""

from __future__ import annotations

import glob
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

# Script extensions a hook command may name. Kept in step with hook_health_check._SCRIPT_EXTS by
# IMPORTING it rather than restating it - a second copy of a vocabulary is the twin this suite
# has already been bitten by twice. The fallback exists only for a partial checkout and is a
# STATEMENT that the parent was unavailable, not a silently divergent list.
try:
    from hook_health_check import _SCRIPT_EXTS, _iter_hook_commands, _tokens
except ImportError:  # pragma: no cover - partial checkout
    _SCRIPT_EXTS = (".py", ".js", ".ps1", ".sh")

    def _tokens(command: str) -> list:
        try:
            raw = shlex.split(command, posix=False)
        except ValueError:
            raw = command.split()
        return [t.strip('"').strip("'") for t in raw if t.strip()]

    def _iter_hook_commands(cfg: dict):
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


# Git LOWERCASES config keys and `--get-regexp` matches the CANONICAL name, so the documented
# spelling `core.hooksPath` matches NOTHING. Derived 2026-08-25 by running the query against this
# machine, which HAS a global hooksPath: the first version of this pattern returned no row for it
# and would therefore have reported "not set" and passed, silently. An extractor that finds
# nothing must prove it looked in the right place - hence lowercase here and casefolded below.
_SANITY_KEYS = r"^(core\.bare|core\.hookspath|user\.email|user\.name)$"

# Matches the three call shapes this suite uses to write a fixture identity:
#   sh(repo, "config", "user.email", "t@t")        _git("config", "user.name", "t")
#   ("config", "user.email", "t@t")
# DERIVED from source rather than listed, so renaming the fixture identity cannot leave this
# check quietly hunting for a value that nothing writes any more.
_FIXTURE_ID_RE = re.compile(
    r"""["']config["']\s*,\s*["']user\.(?:email|name)["']\s*,\s*["']([^"']+)["']""")

# Own budget, stated next to the one it shares a SessionStart with: 6 + _WEEKLY_BUDGET_S (40)
# = 46, under the 60s host default these hooks inherit. A probe that runs out of budget is
# counted as SKIPPED and named, never quietly dropped.
_SANITY_BUDGET_S = 6
_SANITY_CALL_TIMEOUT_S = 5


def fixture_identities(roots: list = None) -> set:
    """Every git identity THIS SUITE's own fixtures can write - DERIVED by reading them.

    The population is exactly right by construction: an identity that no fixture here writes
    cannot have escaped from a fixture here. Verified 2026-08-25 against `git_isolation.py`'s
    own header, which names `user.email=t@t` / `user.name=t` as what the incident actually
    wrote - the scan over 50 files in hooks/ and tools/ returns exactly {"t@t", "t"}, from the
    3 files that write them.
    """
    # `is None`, NOT `or`. [P13 C5] is already recorded in this suite for exactly this: `or` only
    # rescues FALSY values, so `roots=[]` - the natural way to say "scan nothing" - would fall
    # through to the defaults and scan EVERYTHING, and the test asserting an empty scan stays
    # empty would have been asserting the opposite of what it read.
    dirs = ([_HOOKS_DIR, os.path.join(os.path.dirname(_HOOKS_DIR), "tools")]
            if roots is None else roots)
    out: set = set()
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(glob.escape(d), "*.py"))):
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    out.update(_FIXTURE_ID_RE.findall(f.read()))
            except OSError:
                continue
    return out


def _git_ro(repo: str, args: list):
    """Read-only git inside `repo`, with git's redirect variables removed from a COPY of the env.

    Returns (rc, stdout), or None when it could not be run SAFELY - which the caller surfaces as
    a skip and never as a pass. GIT_DIR beats an explicit `-C`, so an unscrubbed call from inside
    a git hook would answer about a DIFFERENT repository and report a clean verdict for a clone it
    never looked at - the #46 mechanism, aimed at the check built to detect #46's residue.

    On a partial checkout with no tools/git_isolation.py this returns None rather than carrying
    an inline copy of the variable list. A duplicated roster is a defect this suite has already
    paid for twice, and "could not check" is an honest answer where a silent second list is not.
    """
    try:
        _tools = os.path.join(os.path.dirname(_HOOKS_DIR), "tools")
        if _tools not in sys.path:
            sys.path.insert(0, _tools)
        from git_isolation import scrubbed_env
    except ImportError:
        return None
    if shutil.which("git") is None:
        return None
    try:
        proc = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True,
                              timeout=_SANITY_CALL_TIMEOUT_S, stdin=subprocess.DEVNULL,
                              encoding="utf-8", errors="replace", env=scrubbed_env())
        return proc.returncode, proc.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def wired_repos(cfg: dict, deadline: float = None) -> tuple:
    """(git top-levels this machine runs hooks OUT OF, n_examined, n_skipped) - DERIVED.

    Every ABSOLUTE script path in a hook command that exists on disk is asked which repository it
    belongs to. ALL FOUR script extensions are walked, not just .py: a denominator scoped to what
    the author happened to be thinking about is this repo's single most-repeated defect, and it
    has already cost a hand-derived roster of 3 where the gate found 8.

    KNOWN LIMIT, adjudicated rather than left to be rediscovered - **HHC-SETTINGS-ONLY**: this
    derives repositories from settings.json ALONE. Hooks reached by the OTHER two wiring paths on
    this machine are invisible to it: stop_dispatcher's children (meta_audit_on_stop,
    fast_test_on_stop) and the git `core.hooksPath` dispatcher's target (pre_push_gate). Measured
    2026-08-25T02:19:47Z - settings.json names 7 of the 10 entry points that actually run.
    It is a limit on the DENOMINATOR, not on the checks: every repo reached this way is asked
    about its EFFECTIVE config, so a global core.hooksPath aimed at a deleted directory is caught
    through whichever repo is examined. The residual exposure is a machine that wires unbluff
    through git hooks and NOT through settings.json, where this examines zero repositories - and
    it says so, because n_repos is printed rather than assumed.
    """
    dirs, seen = [], set()
    for cmd in _iter_hook_commands(cfg):
        for tok in _tokens(cmd):
            if not tok.lower().endswith(_SCRIPT_EXTS) or not os.path.isabs(tok):
                continue
            if not os.path.exists(tok):
                continue                  # already reported as a missing script by check_config
            d = os.path.dirname(os.path.abspath(tok))
            key = os.path.normcase(d)
            if key not in seen:
                seen.add(key)
                dirs.append(d)
    repos, skipped, rseen = [], 0, set()
    for d in dirs:
        if deadline is not None and time.monotonic() >= deadline:
            skipped += 1
            continue
        found = _repo_for(d)
        if found is None:
            skipped += 1
            continue
        if not found[0]:
            continue                  # not a git repository at all - not ours, and not a problem
        key = os.path.normcase(os.path.abspath(found[0]))
        if key not in rseen:
            rseen.add(key)
            repos.append(found)
    return repos, len(dirs), skipped


def _repo_for(d: str):
    """(repo_path, has_working_tree) for directory `d`; None if git could not be run safely.

    `rev-parse --show-toplevel` is the obvious call and it is EXACTLY WRONG here: on a repo
    marked `core.bare` it fails with "this operation must be run in a work tree" - which is
    precisely the state this check exists to find. The first version of this function used it,
    and the probe caught the consequence: the broken clone dropped out of the roster entirely
    and the whole check reported nothing. The defect made itself invisible to its own detector,
    which is this repo's signature failure and the reason the probe is written before the belief.

    `--absolute-git-dir` answers in BOTH states, so a repo stays visible while it is broken.

    has_working_tree is decided by the git dir being named `.git`, not by asking git - because
    asking git is what core.bare corrupts. A genuinely bare repository's git dir is the repo
    directory itself (`something.git`), so a real bare repo is correctly left alone and only a
    non-bare layout MARKED bare fires.
    """
    r = _git_ro(d, ["rev-parse", "--absolute-git-dir"])
    if r is None:
        return None
    rc, out = r
    gitdir = out.strip()
    if rc != 0 or not gitdir:
        return "", False
    norm = gitdir.replace("\\", "/").rstrip("/")
    classic = os.path.basename(norm).lower() == ".git"
    if classic:
        # A `.git` directory names its own worktree, so DO NOT spend a second subprocess asking.
        # This is not only a saving: `--show-toplevel` is the call that fails under core.bare, so
        # the layout answering for itself is also what keeps a broken repo visible. Measured -
        # it removes one git spawn per examined repo at every SessionStart, and took this hook's
        # selftest off 87% of its budget share, which the file records as the level that once
        # tipped the mutation harness into reporting `baseline already RED`.
        return os.path.dirname(norm), True
    t = _git_ro(d, ["rev-parse", "--show-toplevel"])
    top = t[1].strip() if (t is not None and t[0] == 0 and t[1].strip()) else ""
    return (top or gitdir), bool(top)


def _parse_config_z(out: str) -> list:
    """[(origin, key, value)] from `git config -z --show-origin --get-regexp`.

    The record shape is `origin NUL key LF value NUL`, DERIVED by running it rather than assumed.
    The value being NUL-terminated is the point: a hooksPath containing spaces survives intact,
    where a naive whitespace split would truncate it into a path that does not exist and raise a
    false alarm against a perfectly healthy machine.
    """
    fields = out.split("\0")
    rows = []
    for i in range(0, len(fields) - 1, 2):
        key, _, value = fields[i + 1].partition("\n")
        if key.strip():
            rows.append((fields[i], key.strip().lower(), value))
    return rows


def repo_config_problems(repo: str, fixtures: set, has_worktree: bool = True) -> list:
    """The three states #46 actually left behind, asked of ONE wired clone.

    `has_worktree` gates the core.bare question only. A genuinely bare repository is allowed to
    say so; the defect is a repo with a working tree MARKED bare, which is what makes `git
    status` fail there. Firing on a correct bare repo would be firing on correct work, and a
    guard that does that gets disabled - which costs more than the guard was ever worth.
    """
    r = _git_ro(repo, ["config", "-z", "--show-origin", "--get-regexp", _SANITY_KEYS])
    if r is None:
        return []                     # counted as a skip by the caller, never as a pass
    rc, out = r
    if rc not in (0, 1):              # rc 1 is "no key matched", a legitimate healthy answer
        return [f"machine sanity: could not read git config in {repo} (git exited {rc})"]
    problems, ident = [], {}
    for origin, key, value in _parse_config_z(out):
        where = origin.split(":", 1)[1] if origin.startswith("file:") else origin
        if (key == "core.bare" and has_worktree
                and value.strip().lower() in ("true", "yes", "on", "1")):
            problems.append(
                f"machine sanity: {repo} is marked core.bare={value.strip()} in {where}, but it "
                f"HAS a working tree - `git status` there fails outright. This is #46 residue. "
                f"Fix: git -C {repo} config --unset core.bare")
        elif key == "core.hookspath":
            resolved = os.path.expanduser(value.strip())
            if not os.path.isabs(resolved):
                resolved = os.path.join(repo, resolved)
            if not os.path.isdir(resolved):
                problems.append(
                    f"machine sanity: core.hooksPath (set in {where}) points at "
                    f"{value.strip()!r}, which is NOT a directory - git reads hooks from there "
                    f"INSTEAD of .git/hooks, with no fallback, so every git hook it governs is "
                    f"silently disabled. Fix: recreate it, or git config --unset core.hooksPath")
        elif key in ("user.email", "user.name"):
            ident[key] = value
    hits = sorted(k for k, v in ident.items() if v.strip() in fixtures)
    if hits:
        shown = ", ".join(f"{k}={ident[k].strip()!r}" for k in hits)
        problems.append(
            f"machine sanity: {repo} commits as {shown} - a TEST FIXTURE identity that this "
            f"suite's own fixtures write, so a fixture escaped into a real config (#46). Fix: "
            + "; ".join(f"git -C {repo} config --unset {k}" for k in hits))
    return problems


def _machine_sanity_problems(cfg: dict) -> tuple:
    problems = []
    fixtures = fixture_identities()
    if not fixtures:
        # An extractor that finds nothing must PROVE it looked in the right place. Staying silent
        # here would read exactly like "no fixture identity is in use anywhere", which is the
        # shape of a green result that cannot fail - the thing this whole suite exists to stop.
        problems.append("machine sanity: the fixture-identity scan matched NOTHING across hooks/ "
                        "and tools/ - the identity check is looking in the wrong place and is "
                        "not currently able to fire")
    deadline = time.monotonic() + _SANITY_BUDGET_S
    repos, _n_dirs, skipped = wired_repos(cfg, deadline)
    for repo, has_worktree in repos:
        if time.monotonic() >= deadline:
            skipped += 1
            continue
        problems += repo_config_problems(repo, fixtures, has_worktree)
    return problems, len(repos), skipped


def machine_sanity_problems(cfg: dict) -> tuple:
    """(problems, n_repos_checked, n_skipped) for every clone this machine wires hooks from.

    TOTAL by construction. This spawns subprocesses and parses their output, which is the same
    risk shape as [P13 C4] - where an unexpected input raised out of a generator and discarded
    the ENTIRE hook-health report, so the config malformed enough to be worth reporting was the
    exact config that silenced the reporter. A crash here costs this check and nothing else.
    """
    try:
        return _machine_sanity_problems(cfg)
    except Exception as e:               # noqa: BLE001 - see the docstring; total on purpose
        return [f"machine sanity: check crashed ({type(e).__name__}: {e})"], 0, 0


def selftest() -> int:
    """Delegates to the sibling suite (see wired_clone_sanity_selftest.py)."""
    import wired_clone_sanity_selftest as _s
    return _s.selftest()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(0)
