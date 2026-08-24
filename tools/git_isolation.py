#!/usr/bin/env python3
"""Keep a selftest's temp git fixtures OFF the real repository, and prove they stayed off.

WHY THIS EXISTS (#46, escalated 2026-08-24). A git hook exports `GIT_DIR`, and `GIT_DIR`
OVERRIDES `git -C <tmpdir>`. Every fixture in this repo that builds a throwaway repository does
so with `git -C <tmp> ...` and inherits the hook's environment unchanged, so when the suite runs
where it actually ships - inside the pre-push hook - those fixtures operate on the REAL
repository instead.

This is not theory and it was not confined to one file. On 2026-08-24 the first real `git push`
of the v1.4.0 branch ran the suite from inside the hook, and:

  * `meta_audit_on_stop.py` line 543 ran `git init -q --bare <tmp>` -> the real repo's config
    gained `bare = true`, which makes `git status` in the main clone fail outright;
  * its lines 555-556 wrote `user.email=t@t` / `user.name=t` into the real config;
  * its line 557 wrote `f.txt` containing "x\n", line 560 committed it as "local only", and
    line 577 ran `git push -q -u origin HEAD:refs/heads/main` - which resolved `origin` to the
    real GitHub remote and PUBLISHED a one-file tree over the public default branch, where it
    stayed for eleven hours;
  * `pre_push_gate_selftest.py` line 1116 pointed the real `core.hooksPath` at a temp directory
    that was then deleted, silently disabling every hook on the machine;
  * `fast_test_on_stop_selftest.py` line 902 registered a linked worktree in the real repo;
  * `check_review_freshness.py` line 330 left a `fixture` commit behind.

The defect is therefore a CLASS with at least six instances, and patching call sites one file at
a time would leave the next fixture free to reintroduce it. Two mechanisms, both here:

  `scrub_environ()`  - remove the redirect variables ONCE, at the top of the orchestrator. Every
                       gate is spawned as a subprocess by run_selftests, so a single scrub in the
                       parent disinfects all of them and no fixture has to remember anything.
  `fingerprint()`    - a cheap, total snapshot of the mutable state the incident actually
                       damaged. run_selftests takes one before the sweep and after every gate, so
                       a fixture that escapes is caught AND NAMED rather than merely detected.

The scrub is prevention and the fingerprint is detection; neither substitutes for the other. A
scrub with no fingerprint is an unenforced assertion - exactly the shape of #47 - and a
fingerprint with no scrub reports the damage after it has already been pushed.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

# Every variable git exports into a hook that REDIRECTS where a later `git` command operates.
# Each one silently beats an explicit `-C <dir>`, which is what made the incident invisible: the
# fixtures all looked correct in isolation and were correct when run directly.
#
# Deliberately NOT scrubbed: GIT_CONFIG_GLOBAL / GIT_CONFIG_SYSTEM / GIT_CONFIG_NOSYSTEM. They
# redirect config READS, git does not export them to hooks, and this repo's own fixtures set them
# on purpose (see the WT-CAUSE note in pre_push_gate_selftest.py, which points GIT_CONFIG_GLOBAL
# at a synthetic config to reproduce a gpgsign failure). Scrubbing them would break a test that
# is doing the right thing.
GIT_REDIRECT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
)


def scrubbed_env(base=None) -> dict:
    """A COPY of `base` (default `os.environ`) with the redirect variables removed."""
    env = dict(os.environ if base is None else base)
    for var in GIT_REDIRECT_VARS:
        env.pop(var, None)
    return env


def scrub_environ() -> dict:
    """Remove the redirect variables from THIS process's environ. Returns what was removed.

    In-place rather than "build a clean env and pass it to each child" because the second form is
    a per-call-site obligation, and a per-call-site obligation is what failed: 43 git invocations
    across 15 files, of which the ones that did the damage passed no `env=` at all and simply
    inherited. Mutating `os.environ` covers the call sites that pass `env=dict(os.environ)`, the
    ones that pass nothing, and any added tomorrow by someone who never reads this file.

    Safe to do process-wide here because run_selftests spawns every gate as its own subprocess
    (`subprocess.run([sys.executable, path, "--selftest"])`), so this cannot race a sibling gate.
    Nothing in this repo READS these variables - the production code locates a repository with an
    explicit path in every case - so removing them changes no gate's answer.
    """
    removed = {}
    for var in GIT_REDIRECT_VARS:
        if var in os.environ:
            removed[var] = os.environ.pop(var)
    return removed


def _git(repo, *args, timeout=30):
    """Run git in `repo` with a scrubbed env. Returns stdout, or '' on any failure.

    Uses `scrubbed_env` rather than the ambient environment on purpose: a fingerprint taken
    through a hijacked GIT_DIR would describe the wrong repository and compare equal to itself
    while the real one was being rewritten.
    """
    try:
        p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, env=scrubbed_env())
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _digest(path):
    """sha256 of a file, or a marker. ABSENT and UNREADABLE are distinct on purpose."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except FileNotFoundError:
        return "ABSENT"
    except OSError:
        return "UNREADABLE"


def fingerprint(repo) -> str:
    """A total snapshot of the repository state a runaway fixture can damage.

    Covers exactly what the 2026-08-24 incident touched, and each line is here because something
    changed it:

      HEAD        - the fixture moved the branch onto a fixture commit
      refs        - it created `feature` and `wt`, and advanced the checked-out branch
      config      - it set core.bare, core.hooksPath, user.name and user.email
      index       - it replaced the index with a 935-byte fixture index
      worktrees   - it registered a linked worktree under the system temp directory

    Hashed as one opaque string rather than compared field-by-field: the caller's job is "did
    anything change", and a diff of the two strings is not what a gate needs to decide that. The
    fields are printed by `--selftest` for anyone who needs to see which one moved.

    Reads the config FILE rather than asking `git config --list`, because `git config` merges the
    global and system files, so a change to the machine's global config mid-suite would read as
    repo corruption. The incident wrote to the repo file, and that is what this watches.
    """
    common = (_git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") or "").strip()
    if not common:
        # Older git has no --path-format. Fall back, and fall back LOUD: a fingerprint that
        # quietly degrades to a constant would compare equal forever and the gate would pass
        # over any corruption at all - the failure mode this repo exists to catch.
        common = (_git(repo, "rev-parse", "--git-common-dir") or "").strip()
        if common and not os.path.isabs(common):
            common = os.path.join(repo, common)
    if not common:
        return "FINGERPRINT-UNAVAILABLE"

    parts = [
        "head=" + (_git(repo, "rev-parse", "HEAD") or "NONE").strip(),
        "symref=" + (_git(repo, "symbolic-ref", "-q", "HEAD") or "DETACHED").strip(),
        "refs=" + hashlib.sha256(
            (_git(repo, "for-each-ref", "--format=%(refname) %(objectname)") or "")
            .encode("utf-8")).hexdigest()[:16],
        "config=" + _digest(os.path.join(common, "config")),
        # The index by its CONTENT (`ls-files -s` = mode, blob, stage, path), never by hashing
        # .git/index itself. MEASURED: hashing the file made this guard fire on a completely
        # clean run, because ordinary read-only commands - the ones this repo's own gates issue
        # by the dozen - rewrite the index's stat cache without changing a single tracked entry.
        # A guard that reddens correct work is disabled within a day, which is strictly worse
        # than no guard; this spelling still catches the incident, where a 935-byte fixture index
        # replaced the real one and every entry changed.
        "index=" + hashlib.sha256(
            (_git(repo, "ls-files", "-s") or "NONE").encode("utf-8")).hexdigest()[:16],
        "worktrees=" + hashlib.sha256(
            (_git(repo, "worktree", "list", "--porcelain") or "").encode("utf-8")
        ).hexdigest()[:16],
    ]
    return " ".join(parts)


def _selftest() -> int:
    """Prove the scrub WORKS, by showing the unscrubbed case FAILING first.

    A probe that has not been shown to fail is not a probe (standing check 6). Four probes in this
    repo were invalid on first write and every one returned a comforting answer, so this asserts
    BOTH directions: with GIT_DIR set, a bare `git -C <tmp>` must be hijacked, and the scrubbed
    call must not be. If the first assertion ever stops holding, this file is guarding against
    something that no longer happens and the guard - not the code - is what needs revisiting.
    """
    import tempfile
    fails = []

    with tempfile.TemporaryDirectory() as td:
        victim = os.path.join(td, "victim")
        fixture = os.path.join(td, "fixture")
        for d in (victim, fixture):
            os.makedirs(d)
            if subprocess.run(["git", "-C", d, "init", "-q"], capture_output=True,
                              env=scrubbed_env()).returncode != 0:
                print("SELFTEST SKIP: git unavailable")
                return 77
        victim_git = os.path.join(victim, ".git")

        # 1. THE DEFECT, reproduced. With GIT_DIR pointed at `victim`, a command that names
        #    `fixture` explicitly must answer about `victim`. If this does NOT reproduce, the
        #    mechanism #46 was diagnosed from has changed and everything below is theatre.
        hijacked = dict(os.environ, GIT_DIR=victim_git)
        p = subprocess.run(["git", "-C", fixture, "rev-parse", "--absolute-git-dir"],
                           capture_output=True, text=True, env=hijacked)
        got = (p.stdout or "").strip().replace("\\", "/").lower()
        if os.path.normpath(victim_git).replace("\\", "/").lower() not in got:
            fails.append("GIT_DIR no longer overrides `git -C` (got %r) - the mechanism behind "
                         "#46 could not be reproduced, so this guard is unproven" % (got,))

        # 2. THE FIX. Same command, scrubbed env, must answer about `fixture`.
        p2 = subprocess.run(["git", "-C", fixture, "rev-parse", "--absolute-git-dir"],
                            capture_output=True, text=True, env=scrubbed_env(hijacked))
        got2 = (p2.stdout or "").strip().replace("\\", "/").lower()
        if os.path.normpath(os.path.join(fixture, ".git")).replace("\\", "/").lower() not in got2:
            fails.append("scrubbed_env did not restore `git -C` targeting (got %r)" % (got2,))

        # 3. scrub_environ must actually empty this process's view, and report what it took.
        os.environ["GIT_DIR"] = victim_git
        os.environ["GIT_INDEX_FILE"] = os.path.join(victim_git, "index")
        removed = scrub_environ()
        if "GIT_DIR" in os.environ or "GIT_INDEX_FILE" in os.environ:
            fails.append("scrub_environ left a redirect variable in os.environ")
        if set(removed) != {"GIT_DIR", "GIT_INDEX_FILE"}:
            fails.append("scrub_environ misreported what it removed: %r" % (sorted(removed),))

        # 4. fingerprint must MOVE when the repo moves, and hold still when it does not.
        #    A fingerprint that never changes passes every comparison forever.
        before = fingerprint(victim)
        if before == "FINGERPRINT-UNAVAILABLE":
            fails.append("fingerprint could not read a freshly initialised repo")
        if fingerprint(victim) != before:
            fails.append("fingerprint is not stable across two reads of an unchanged repo - it "
                         "would fire on every gate and be disabled within a day")
        # FIRES-ON-CORRECT-WORK, pinned. The first version of this fingerprint hashed .git/index
        # directly and went red on a clean suite run, because read-only commands rewrite the
        # index stat cache. Touching a tracked file and running `status` reproduces exactly that
        # refresh with no tracked entry changed, so this assertion is what stops the cheaper
        # spelling coming back.
        touched = os.path.join(victim, "f.txt")
        with open(touched, "w", encoding="utf-8") as fh:
            fh.write("x\n")
        subprocess.run(["git", "-C", victim, "add", "-A"], capture_output=True,
                       env=scrubbed_env())
        settled = fingerprint(victim)
        os.utime(touched, None)
        subprocess.run(["git", "-C", victim, "status", "--porcelain"], capture_output=True,
                       env=scrubbed_env())
        if fingerprint(victim) != settled:
            fails.append("fingerprint moved after a stat-cache refresh with no tracked entry "
                         "changed - it would redden every clean run and be disabled within a day")
        subprocess.run(["git", "-C", victim, "config", "core.hooksPath", "/tmp/whatever"],
                       capture_output=True, env=scrubbed_env())
        # Compared against `settled`, NOT `before`: the stat-cache check above legitimately
        # staged a file, so `before` is stale by here and asserting against it would pass for a
        # reason that has nothing to do with core.hooksPath.
        if fingerprint(victim) == settled:
            fails.append("fingerprint did not change after core.hooksPath was set - the exact "
                         "corruption that silently disabled every hook on the machine")

        # 5. and it must see a commit, which is what reached GitHub.
        mid = fingerprint(victim)
        with open(os.path.join(victim, "f.txt"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        cenv = scrubbed_env()
        cenv.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                     "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        subprocess.run(["git", "-C", victim, "add", "-A"], capture_output=True, env=cenv)
        subprocess.run(["git", "-C", victim, "commit", "-qm", "local only"],
                       capture_output=True, env=cenv)
        if fingerprint(victim) == mid:
            fails.append("fingerprint did not change after a commit - the fixture commit that "
                         "was published to the public default branch would pass this gate")

    # NAMED rather than counted. "5 check(s)" was already wrong one edit after it was written,
    # and a bare integer cannot tell a deleted check from a renamed one - the same reason
    # _SH_SITES_REQUIRED is a set and not a length.
    checks = ("git-dir-overrides-dash-C", "scrubbed-env-restores-targeting",
              "scrub-environ-empties-environ", "fingerprint-stable-when-idle",
              "fingerprint-ignores-stat-refresh", "fingerprint-sees-hooksPath",
              "fingerprint-sees-commit")
    for f in fails:
        print("FAIL: %s" % f)
    print("git_isolation selftest: %d check(s) [%s], %d failure(s)"
          % (len(checks), " ".join(checks), len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))
    print(fingerprint(target))
