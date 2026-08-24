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
        # The HOOKS DIRECTORY, by name and content. Added 2026-08-24 after the integration
        # suite - which CI never reached, because install.py aborted first - failed on a
        # delegating shim that found a `# husky / npx --no-install husky-run pre-push` file in
        # the REAL repo's .git/hooks. It is byte-identical to the fixture written by
        # pre_push_gate_selftest.py:945 and its mtime is 01:55, inside the #46 corruption
        # window: a SEVENTH artifact that the incident report, the reflog sweep and this
        # fingerprint had all missed. `core.hooksPath` made it inert for git itself, which is
        # exactly why nothing noticed - but any code that resolves hooks the way the dispatcher
        # does still executed it. Samples are excluded: git ships them and they never change.
        "hooks=" + hashlib.sha256("\n".join(sorted(
            "%s:%s" % (n, _digest(os.path.join(common, "hooks", n)))
            for n in (os.listdir(os.path.join(common, "hooks"))
                      if os.path.isdir(os.path.join(common, "hooks")) else [])
            if not n.endswith(".sample")
        )).encode("utf-8")).hexdigest()[:16],
        # The index by its CONTENT (`ls-files -s` = mode, blob, stage, path), never by hashing
        # .git/index itself. MEASURED: hashing the file made this guard fire on a completely
        # clean run, because ordinary read-only commands - the ones this repo's own gates issue
        # by the dozen - rewrite the index's stat cache without changing a single tracked entry.
        # A guard that reddens correct work is disabled within a day, which is strictly worse
        # than no guard; this spelling still catches the incident, where a 935-byte fixture index
        # replaced the real one and every entry changed.
        "index=" + hashlib.sha256(
            (_git(repo, "ls-files", "-s") or "NONE").encode("utf-8")).hexdigest()[:16],
        # PATHS ONLY. `worktree list --porcelain` also prints `HEAD <sha>` and `branch <ref>`
        # per entry, so hashing it whole made this term move whenever head= or symref= moved -
        # and a field-deletion probe then showed head=, symref= AND refs= all SURVIVING
        # deletion, because this term was quietly covering for all three. Overlapping terms
        # cannot be individually pinned, and a term nothing can pin is indistinguishable from a
        # deleted one. Narrowed to the registration itself, which is the thing only this term
        # sees: `worktree add --detach` creates no ref at all.
        "worktrees=" + hashlib.sha256(
            "\n".join(sorted(
                ln for ln in (_git(repo, "worktree", "list", "--porcelain") or "").splitlines()
                if ln.startswith("worktree ")
            )).encode("utf-8")).hexdigest()[:16],
    ]
    return " ".join(parts)


def _selftest() -> int:
    """Prove the scrub WORKS, by showing the unscrubbed case FAILING first.

    A probe that has not been shown to fail is not a probe (standing check 6). Four probes in this
    repo were invalid on first write and every one returned a comforting answer, so this asserts
    BOTH directions: with GIT_DIR set, a bare `git -C <tmp>` must be hijacked, and the scrubbed
    call must not be. If the first assertion ever stops holding, this file is guarding against
    something that no longer happens and the guard - not the code - is what needs revisiting.

    The check ledger is RECORDED AT RUNTIME and set-compared against REQUIRED_CHECKS. The first
    version printed a hand-written tuple of 7 names beside 9 `fails.append` sites, so deleting an
    entire check left the evidence line byte-identical - and the gate-0 evidence document cites
    one of those names as proof a regression is pinned. `_SH_SITES_REQUIRED` in
    pre_push_gate_selftest.py is the model, and its enforcing half is the set comparison, not the
    set literal.
    """
    import tempfile
    fails = []
    ran = []

    def ck(name):
        """Record that a check actually EXECUTED. A name that never runs is a deleted check."""
        ran.append(name)

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

        def fx(*args, **kw):
            """A fixture git command whose FAILURE is a failure, not a silent no-op.

            [M8] `config`, `add` and `commit` were previously unchecked. With an ambient
            `commit.gpgsign = true` and no usable key - a state this repo has already been bitten
            by, see [WT-CAUSE] in pre_push_gate_selftest.py - the commit no-ops, the fingerprint
            correctly does not move, and the suite reports "fingerprint did not change after a
            commit", sending the reader to rewrite a function that is working perfectly.
            """
            env = scrubbed_env()
            env.update(kw.pop("extra_env", {}) or {})
            r = subprocess.run(["git", "-C", victim, *args], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", env=env)
            if r.returncode != 0:
                fails.append("FIXTURE `git %s` failed (rc=%s): %s - this suite could not build "
                             "its own case, which is a failure here and never a passing skip"
                             % (" ".join(args), r.returncode,
                                (r.stderr or r.stdout or "").strip()[:160] or "<no output>"))
                return False
            return True

        def same_path(a, b):
            """Compare two paths as GIT resolves them.

            [H4] `os.path.normpath` does NOT expand an 8.3 short name, a junction or a subst
            drive; git does, via GetLongPathNameW. `tempfile` inherits %TEMP% verbatim, so on any
            box whose TEMP carries an alias this comparison failed on entirely correct code and
            printed "the mechanism behind #46 could not be reproduced" - an invitation to delete
            this branch's headline fix. `realpath` collapses all three spellings, which is the
            same conclusion fast_test_on_stop.py:627-631 already reached for the same reason.
            """
            return os.path.realpath(a).replace("\\", "/").lower() in \
                os.path.realpath(b).replace("\\", "/").lower()

        # 1. THE DEFECT, reproduced. With GIT_DIR pointed at `victim`, a command that names
        #    `fixture` explicitly must answer about `victim`. If this does NOT reproduce, the
        #    mechanism #46 was diagnosed from has changed and everything below is theatre.
        hijacked = dict(os.environ, GIT_DIR=victim_git)
        p = subprocess.run(["git", "-C", fixture, "rev-parse", "--absolute-git-dir"],
                           capture_output=True, text=True, env=hijacked)
        got = (p.stdout or "").strip()
        ck("git-dir-overrides-dash-C")
        if not got or not same_path(victim_git, got):
            fails.append("GIT_DIR no longer overrides `git -C` (got %r) - the mechanism behind "
                         "#46 could not be reproduced, so this guard is unproven" % (got,))

        # 2. THE FIX. Same command, scrubbed env, must answer about `fixture`.
        p2 = subprocess.run(["git", "-C", fixture, "rev-parse", "--absolute-git-dir"],
                            capture_output=True, text=True, env=scrubbed_env(hijacked))
        got2 = (p2.stdout or "").strip()
        ck("scrubbed-env-restores-targeting")
        if not got2 or not same_path(os.path.join(fixture, ".git"), got2):
            fails.append("scrubbed_env did not restore `git -C` targeting (got %r)" % (got2,))

        # 3. scrub_environ must actually empty this process's view, and report what it took.
        os.environ["GIT_DIR"] = victim_git
        os.environ["GIT_INDEX_FILE"] = os.path.join(victim_git, "index")
        removed = scrub_environ()
        ck("scrub-environ-empties-environ")
        if "GIT_DIR" in os.environ or "GIT_INDEX_FILE" in os.environ:
            fails.append("scrub_environ left a redirect variable in os.environ")
        if set(removed) != {"GIT_DIR", "GIT_INDEX_FILE"}:
            fails.append("scrub_environ misreported what it removed: %r" % (sorted(removed),))

        # 4. fingerprint must MOVE when the repo moves, and hold still when it does not.
        #    A fingerprint that never changes passes every comparison forever.
        before = fingerprint(victim)
        ck("fingerprint-stable-when-idle")
        if before == "FINGERPRINT-UNAVAILABLE":
            fails.append("fingerprint could not read a freshly initialised repo")
        if fingerprint(victim) != before:
            fails.append("fingerprint is not stable across two reads of an unchanged repo - it "
                         "would fire on every gate and be disabled within a day")

        # 4a. [M7] index=, pinned ALONE. Staging a file moves `ls-files -s` and nothing else -
        #     no ref, no symref, no config - so this is the only assertion that can tell the
        #     index term from a deleted one. The incident replaced the real index with a
        #     935-byte fixture index.
        idx_base = fingerprint(victim)
        with open(os.path.join(victim, "staged.txt"), "w", encoding="utf-8") as fh:
            fh.write("staged\n")
        fx("add", "-A")
        ck("fingerprint-sees-index")
        if fingerprint(victim) == idx_base:
            fails.append("fingerprint did not change when a file was STAGED - the index term is "
                         "dead, and a fixture index swapped over the real one would pass")

        # 4b. FIRES-ON-CORRECT-WORK, pinned. The first version of this fingerprint hashed
        #     .git/index directly and went red on a clean suite run, because read-only commands
        #     rewrite the index stat cache. Touching a tracked file and running `status`
        #     reproduces exactly that refresh with no tracked entry changed.
        settled = fingerprint(victim)
        os.utime(os.path.join(victim, "staged.txt"), None)
        fx("status", "--porcelain")
        ck("fingerprint-ignores-stat-refresh")
        if fingerprint(victim) != settled:
            fails.append("fingerprint moved after a stat-cache refresh with no tracked entry "
                         "changed - it would redden every clean run and be disabled within a day")

        # 4c. config=, pinned alone: the term that caught core.bare and core.hooksPath.
        fx("config", "core.hooksPath", "/tmp/whatever")
        ck("fingerprint-sees-hooksPath")
        if fingerprint(victim) == settled:
            fails.append("fingerprint did not change after core.hooksPath was set - the exact "
                         "corruption that silently disabled every hook on the machine")

        # 4d. hooks=, pinned ALONE. A fixture `pre-push` left in .git/hooks is what the
        #     integration suite tripped on, seventeen hours after the incident, and no other
        #     term sees it - core.hooksPath had made it inert for git, so even the config term
        #     could not infer it.
        hooks_base = fingerprint(victim)
        _hd = os.path.join(victim, ".git", "hooks")
        os.makedirs(_hd, exist_ok=True)
        with open(os.path.join(_hd, "pre-push"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexit 0\n")
        ck("fingerprint-sees-hooks-dir")
        if fingerprint(victim) == hooks_base:
            fails.append("fingerprint did not change when a hook file appeared in .git/hooks - "
                         "the hooks term is dead, and exactly such a fixture sat in the real "
                         "repository unnoticed by every other guard in this suite")

        # 5. and it must see a commit, which is what reached GitHub.
        mid = fingerprint(victim)
        author = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                  "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        with open(os.path.join(victim, "f.txt"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        fx("add", "-A")
        committed = fx("commit", "-qm", "local only", extra_env=author)
        ck("fingerprint-sees-commit")
        if committed and fingerprint(victim) == mid:
            fails.append("fingerprint did not change after a commit - the fixture commit that "
                         "was published to the public default branch would pass this gate")

        # 5a. [M7] symref=, pinned ALONE. The branch ref is created FIRST and fingerprinted, so
        #     the only thing the final move changes is which branch HEAD points at - which is
        #     precisely what the incident did to feat/enforcing-verify.
        if committed:
            # 5a. [M7] refs=, pinned ALONE. Creating a branch touches no worktree path, no
            #     index entry and no config, and leaves HEAD exactly where it was. The incident
            #     left two stray branches behind, so this is not a hypothetical term.
            pre_branch = fingerprint(victim)
            fx("branch", "other")
            branched = fingerprint(victim)
            ck("fingerprint-sees-refs")
            if branched == pre_branch:
                fails.append("fingerprint did not change when a branch ref was created - the "
                             "refs term is dead, and the incident left two stray branches")

            # 5b. [M7] symref=, pinned ALONE. The ref already exists by here, so the only thing
            #     this moves is which branch HEAD points at - precisely what the incident did
            #     to feat/enforcing-verify when it parked it on a fixture commit.
            fx("symbolic-ref", "HEAD", "refs/heads/other")
            ck("fingerprint-sees-symref")
            if fingerprint(victim) == branched:
                fails.append("fingerprint did not change when HEAD was moved to another branch "
                             "with no other edit - the symref term is dead")

            # 5c. [M7] head=, pinned ALONE - which requires a DETACHED head. While HEAD is a
            #     symref its sha is a FUNCTION of refs= and symref=, so no edit can move it
            #     alone and the term is genuinely redundant in that state. Detached, it stops
            #     being derived: `update-ref --no-deref` then moves the raw HEAD and nothing
            #     else, and a detached-HEAD move is invisible to every other term.
            first = (_git(victim, "rev-parse", "HEAD") or "").strip()
            with open(os.path.join(victim, "second.txt"), "w", encoding="utf-8") as fh:
                fh.write("second\n")
            fx("add", "-A")
            if first and fx("commit", "-qm", "second", extra_env=author):
                fx("checkout", "-q", "--detach")
                detached = fingerprint(victim)
                fx("update-ref", "--no-deref", "HEAD", first)
                ck("fingerprint-sees-head")
                if fingerprint(victim) == detached:
                    fails.append("fingerprint did not change when a DETACHED HEAD was moved - "
                                 "the head term is dead, and in a detached state no other term "
                                 "can see that move")

            # 5b. [M7] worktrees=, pinned ALONE. It is the ONLY term that detects incident
            #     instance #5 (fast_test_on_stop_selftest.py registering a linked worktree),
            #     because `worktree add --detach` creates no ref at all.
            wt_base = fingerprint(victim)
            wt_path = os.path.join(td, "linked")
            if fx("worktree", "add", "--detach", "-q", wt_path):
                ck("fingerprint-sees-worktree")
                if fingerprint(victim) == wt_base:
                    fails.append("fingerprint did not change when a linked worktree was "
                                 "registered - the worktrees term is dead, and that is the only "
                                 "term that sees a `worktree add --detach`, which creates no ref")

    # DECLARED and ENFORCED. The set comparison is the half that makes the roster load-bearing:
    # a deleted check no longer runs, so its name is absent from `ran`, so this goes red. A
    # renamed one shows up on both sides at once.
    REQUIRED_CHECKS = frozenset({
        "git-dir-overrides-dash-C", "scrubbed-env-restores-targeting",
        "scrub-environ-empties-environ", "fingerprint-stable-when-idle",
        "fingerprint-sees-index", "fingerprint-ignores-stat-refresh",
        "fingerprint-sees-hooksPath", "fingerprint-sees-hooks-dir", "fingerprint-sees-commit",
        "fingerprint-sees-refs", "fingerprint-sees-symref",
        "fingerprint-sees-head", "fingerprint-sees-worktree",
    })
    missing = sorted(REQUIRED_CHECKS - set(ran))
    unexpected = sorted(set(ran) - REQUIRED_CHECKS)
    if missing:
        fails.append("check(s) declared but never executed: %r - a check that does not run is a "
                     "deleted check, and the printed roster would not have shown it" % (missing,))
    if unexpected:
        fails.append("check(s) executed but not declared: %r - add them to REQUIRED_CHECKS or "
                     "the roster stops describing what this gate does" % (unexpected,))

    for f in fails:
        print("FAIL: %s" % f)
    print("git_isolation selftest: %d of %d declared check(s) executed [%s], %d failure(s)"
          % (len(set(ran)), len(REQUIRED_CHECKS), " ".join(sorted(set(ran))), len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))
    print(fingerprint(target))
