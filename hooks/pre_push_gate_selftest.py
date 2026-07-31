"""Selftest suite for pre_push_gate.py - split out to keep the hook body under the 800-line rule.

Imported by pre_push_gate.py's `--selftest` dispatch; not a hook and not registered anywhere. It is
listed in hook_health_check.KNOWN_NO_SELFTEST because it IS the selftest - a module whose only
job is testing another one does not need one of its own, and the floor exists to force that
statement rather than let the omission pass unnoticed.

REBINDING RULE, and it is load-bearing: the parent's production code reads the PARENT module's
globals. A `global STATE_DIR` in this file would rebind a name here and leave production
reading the old one, so the test would keep passing while testing nothing - the precise silent
failure this repo exists to catch, and one this split could have introduced for free. Every
rebind therefore goes through `_m.<name> = ...`, and every read of a rebindable name through
`_m.<name>`.
"""

from __future__ import annotations

import pre_push_gate as _m

# Snapshot the parent's namespace so the test bodies can use bare names (including the
# underscored helpers `from x import *` would skip). READS only - see the rebinding rule above.
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})

def _selftest_undispatched_disclosure() -> list:
    """[P13 D8] --install-global may drop a hook name for cost, but never in silence."""
    fails = []
    cand = all_client_hook_candidates()
    dropped = set(undispatched_hook_names())
    dispatched = set(git_client_hook_names())
    # derived, not hardcoded: a name is either dispatched or disclosed as dropped
    unaccounted = sorted(cand - dispatched - dropped)
    if unaccounted:
        fails.append("client hook(s) neither dispatched nor disclosed as dropped: %r"
                     % (unaccounted,))
    if dropped & dispatched:
        fails.append("a name is both dispatched and reported dropped: %r"
                     % (sorted(dropped & dispatched),))
    # the guard that used to be blind: it diffed git_client_hook_names() - CLIENT_HOOKS, and
    # the exclusion happens on the LEFT of that difference, so an excluded name was invisible
    # to it by construction. This one starts from the UNSUBTRACTED set.
    if HIGH_FREQUENCY_HOOKS & cand and not dropped:
        fails.append("HIGH_FREQUENCY_HOOKS excludes a real client hook but "
                     "undispatched_hook_names() reports nothing - the disclosure is blind")
    return fails


def selftest() -> int:
    import tempfile
    fails = []

    def _repo(stack):
        d = _tmpdir(stack)
        try:
            if subprocess.run(["git", "-C", d, "init", "-q"], capture_output=True).returncode:
                return None
        except (OSError, subprocess.SubprocessError):
            return None
        return d

    real_state = fast_test.STATE_DIR
    with __import__("contextlib").ExitStack() as stack:
        fast_test.STATE_DIR = _tmpdir(stack)
        r = _repo(stack)
        if r is None:
            # A skip is NOT a pass. Exiting 0 here made the whole gate evaporate on any image
            # without git while the ledger recorded a clean run (finding 32).
            print("SELFTEST SKIP: git unavailable")
            fast_test.STATE_DIR = real_state
            return SKIP_RC

        # 1. no command -> allow (a repo with no tests must not be un-pushable)
        if gate(r) != 0:
            fails.append("repo with no test command should allow the push")

        # 2. push-time override wins over fast_test_on_stop's detection, and carries its timeout
        os.makedirs(os.path.join(r, ".claude"), exist_ok=True)
        os.makedirs(os.path.join(r, "tests"), exist_ok=True)  # would make fast_test_on_stop pick pytest
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write("# strict gate\ntimeout=222\npython -c \"pass\"\n")
        cmd, t = resolve_command(r)
        if (cmd, t) != ('python -c "pass"', 222):
            fails.append(f"pre-push override not honored: {(cmd, t)}")

        # 3. failing tests BLOCK
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write("python -c \"import sys; sys.exit(1)\"\n")
        with open(os.path.join(r, "app.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        if gate(r) != 1:
            fails.append("failing tests must block the push")

        # 4. passing tests allow, and record state fast_test_on_stop can read
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write("python -c \"pass\"\n")
        if gate(r) != 0:
            fails.append("passing tests must allow the push")
        if last_pass(r, 'python -c "pass"') <= 0:
            fails.append("a fresh pass was not recorded to fast_test_on_stop state")

        # 5. the fast path: nothing touched since that pass -> no re-run
        before = last_pass(r, 'python -c "pass"')
        if gate(r) != 0 or last_pass(r, 'python -c "pass"') != before:
            fails.append("clean tree should short-circuit without re-running tests")

        # 6. touching source re-arms the gate
        time.sleep(0.01)
        os.utime(os.path.join(r, "app.py"), None)
        newest, where = newest_source_mtime(r)
        if where != "app.py" or newest <= 0:
            fails.append(f"newest source detection wrong: {(where, newest)}")
        if newest <= before:
            fails.append("a touched source file must read as newer than the last pass")

        # 7. a foreign pre-push hook is never overwritten
        dest = os.path.join(r, ".git", "hooks", "pre-push")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho someone elses hook\n")
        if install(r) != 1:
            fails.append("install must refuse to clobber a foreign pre-push hook")
        os.remove(dest)

        # 8b. the global dispatcher must DELEGATE to a repo's own hook, never replace it
        gdir = _tmpdir(stack)
        body = render_shim()
        disp = os.path.join(gdir, "post-commit")  # a non-pre-push name: pure delegation, no gate
        with open(disp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        marker = os.path.join(r, "LOCAL_HOOK_RAN").replace("\\", "/")
        localdir = os.path.join(r, ".git", "hooks")
        os.makedirs(localdir, exist_ok=True)
        local_hook = os.path.join(localdir, "post-commit")
        with open(local_hook, "w", encoding="utf-8", newline="\n") as f:
            f.write(f'#!/bin/sh\necho ran > "{marker}"\n')
        # The dispatcher invokes a repo-local hook as an executable, so it needs the execute
        # bit. Windows ignores mode bits entirely, which is why this passed on the authoring
        # machine and failed on EVERY Unix CI runner with exit 126 ("found but not
        # executable"), 2026-07-29. Fail-soft: a filesystem without mode bits still runs the
        # assertions below.
        try:
            mode = os.stat(local_hook).st_mode
            os.chmod(local_hook, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass

        def _dispatch() -> int:
            try:
                return subprocess.run(["sh", disp], cwd=r, capture_output=True, timeout=60).returncode
            except (OSError, subprocess.SubprocessError):
                return -1

        rc = _dispatch()
        if rc == -1:
            print("SELFTEST SKIP: sh unavailable, dispatcher delegation untested")
        else:
            if rc != 0:
                fails.append(f"dispatcher should exit 0 when delegating, got {rc}")
            if not os.path.exists(marker):
                fails.append("dispatcher did NOT run the repo's own hook - project hooks would break")
            # and with no repo-local hook it must still succeed quietly
            os.remove(os.path.join(localdir, "post-commit"))
            if _dispatch() != 0:
                fails.append("dispatcher should exit 0 when the repo has no hook of that name")

        # 8. install then uninstall round-trips
        if install(r) != 0 or not os.path.exists(dest):
            fails.append("install did not write the hook")
        elif "pre_push_gate.py" not in open(dest, encoding="utf-8").read():
            fails.append("installed shim does not point at this script")
        # 8c. [finding 30] git REFUSES to run a non-executable hook on POSIX and merely warns.
        # Windows ignores mode bits, so only CI can see a regression here - assert it there.
        if os.name != "nt" and os.path.exists(dest):
            if not os.stat(dest).st_mode & stat.S_IXUSR:
                fails.append("installed pre-push hook is not executable - git would skip it")
        if install(r, remove=True) != 0 or os.path.exists(dest):
            fails.append("uninstall did not remove the hook")

        # ---------------------------------------------------------------- v1.3.1 regressions
        env = dict(os.environ)
        env["UNBLUFF_STATE_DIR"] = fast_test.STATE_DIR  # child processes share the temp state

        def _child(cwd, timeout=60):
            """Run this script as git would, in `cwd`. (rc, stderr) or (None, '') if it hung."""
            try:
                p = subprocess.run([sys.executable, os.path.abspath(__file__)], cwd=cwd,
                                   capture_output=True, text=True, timeout=timeout, env=env,
                                   encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
                return p.returncode, p.stderr or ""
            except subprocess.TimeoutExpired:
                return None, ""
            except (OSError, subprocess.SubprocessError) as e:
                return -1, str(e)

        # 9a. [finding 1, CRITICAL] The BEHAVIOURAL case below can only fail where the
        # process locale is not UTF-8 - i.e. on Windows. On Linux, dropping the explicit codec
        # is a literal no-op, so CI reported this mutation as a decorative test twice while the
        # Windows run caught it every time. Assert the INVARIANT too, which holds everywhere:
        # git speaks UTF-8 on every platform and this module must never fall back to the
        # locale codec, whatever the locale happens to be on the machine running the suite.
        if _GIT_TEXT.get("encoding") != "utf-8":
            fails.append("_git() no longer pins an explicit utf-8 codec (%r) - on a non-UTF-8 "
                         "locale it decodes git's output with the locale codec, which turns a "
                         "non-ASCII repo path into one that does not exist and makes the gate "
                         "announce 'no test command' over unverified code" % (_GIT_TEXT,))
        if not _GIT_TEXT.get("errors"):
            fails.append("_git() no longer pins an error handler (%r) - an undecodable byte "
                         "then raises instead of round-tripping" % (_GIT_TEXT,))

        # 9. [finding 1, CRITICAL] a non-ASCII repo path must not silently disable the gate.
        # git emits UTF-8; decoding it with the Windows locale codec yields a path that does
        # not exist, so resolve_command finds nothing and the gate reports the healthy-sounding
        # "no test command - nothing to verify".
        uni_parent = _tmpdir(stack)
        uni = os.path.join(uni_parent, "José-café")
        try:
            os.makedirs(uni, exist_ok=True)
            uni_ok = subprocess.run(["git", "-C", uni, "init", "-q"],
                                    capture_output=True).returncode == 0
        except (OSError, subprocess.SubprocessError, UnicodeError):
            uni_ok = False
        if uni_ok:
            root_u = _repo_root(uni)
            if not root_u or not os.path.isdir(root_u):
                fails.append("non-ASCII repo path: _repo_root returned %r which is not a "
                             "directory - the gate would silently skip this repo" % (root_u,))
            else:
                os.makedirs(os.path.join(root_u, ".claude"), exist_ok=True)
                with open(os.path.join(root_u, ".claude", "pre-push.cmd"), "w",
                          encoding="utf-8") as f:
                    f.write('python -c "import sys; sys.exit(1)"\n')
                rc_u, err_u = _capture_gate(root_u)
                if rc_u != 1 or "BLOCKED" not in err_u:
                    fails.append("non-ASCII repo path: failing tests did NOT block "
                                 "(rc=%s err=%r)" % (rc_u, err_u[:120]))
        else:
            print("SELFTEST SKIP: could not create a non-ASCII repo path")

        # 10. [findings 3, 11] git failing must NEVER read the same as "nothing changed".
        # A locked index made ls-files exit 128, the gate saw (0.0, None), trusted a stale
        # pass and announced "verified - no source touched since".
        not_a_repo = _tmpdir(stack)
        newest_bad, where_bad = newest_source_mtime(not_a_repo)
        if newest_bad is not None:
            fails.append("git failure returned a real mtime (%r) instead of the UNKNOWN "
                         "sentinel - a stale pass would satisfy the fast path" % (newest_bad,))

        # 10b. [finding 1] a root git reports but which does not exist is an UNANSWERED
        # question, not "this repo has no tests". With the codec fixed this state is
        # unreachable on a healthy machine, so pin the guard directly - otherwise deleting it
        # is a mutation nothing catches, and the CRITICAL failure returns the moment any other
        # decode path regresses.
        class _FakeGit(object):
            returncode = 0
            stdout = os.path.join(not_a_repo, "definitely-not-a-directory")
            stderr = ""

        # Patch the PARENT module: _repo_root lives there and reads that module's `_git`.
        # After the P12 split, globals()["_git"] here rebinds a name in the selftest module
        # only, the fake is never reached, and the check passes while testing nothing. The
        # mutation harness caught exactly that (#1b came back SURVIVED) - which is the whole
        # reason a behaviour-preserving refactor still has to be mutation-verified.
        _real_git = _m._git
        _m._git = lambda *a, **k: _FakeGit()
        try:
            if _m._repo_root("anything") is not None:
                fails.append("_repo_root accepted a root that is not a directory - a "
                             "mis-decoded path would read as a healthy repo with no tests")
        finally:
            _m._git = _real_git

        # 11. [findings 2, 12] source outside SRC_EXT must still re-arm the gate.
        for extra in ("deploy.sh", "schema.sql", "Dockerfile"):
            with open(os.path.join(r, extra), "w", encoding="utf-8") as f:
                f.write("# x\n")
        newest_x, where_x = newest_source_mtime(r)
        if newest_x is None or where_x is None:
            fails.append("non-.py source: scan returned UNKNOWN unexpectedly")
        elif os.path.basename(str(where_x)) not in ("deploy.sh", "schema.sql", "Dockerfile"):
            fails.append("a changed shell/sql/Dockerfile is invisible to the gate (newest=%r) "
                         "- it would claim 'no source touched since'" % (where_x,))

        # 12. [finding 4] a non-ASCII source filename is C-quoted by git and was skipped
        # entirely, so editing it left the gate announcing a verified tree.
        quoted = "données.py"
        try:
            with open(os.path.join(r, quoted), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            made = True
        except (OSError, UnicodeError):
            made = False
        if made:
            time.sleep(0.01)
            os.utime(os.path.join(r, quoted), None)
            newest_q, where_q = newest_source_mtime(r)
            if newest_q is None:
                fails.append("non-ASCII source: scan returned UNKNOWN")
            elif os.path.basename(str(where_q or "")) != quoted:
                fails.append("C-quoted source file is invisible to the gate (newest=%r)"
                             % (where_q,))

        # 13. [finding 9] a corrupt state file must not crash the gate. It used to raise
        # through main(), so git REFUSED every push in that repo with a bare traceback.
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write('python -c "pass"\n')
        for junk in ('[]', '{"ts": "not-a-number", "rc": 0, "cmd": "python -c \\"pass\\""}',
                     'null', '{"ts": {"a": 1}, "rc": 0}'):
            with open(fast_test._state_path(r), "w", encoding="utf-8") as f:
                f.write(junk)
            try:
                if last_pass(r, 'python -c "pass"') != 0.0:
                    fails.append("corrupt state %r was trusted as a pass" % junk)
            except Exception as e:
                fails.append("corrupt state %r raised %r - git would refuse the push"
                             % (junk, e))
            rc_c, _ = _child(r)
            if rc_c not in (0, 1):
                fails.append("corrupt state %r made the hook exit %r (a traceback refuses "
                             "the push)" % (junk, rc_c))
        try:
            os.remove(fast_test._state_path(r))
        except OSError:
            pass

        # 14. [finding 10] a test that leaves a grandchild holding the captured pipe hung
        # `git push` forever: subprocess.run's timeout kills the direct child, then blocks
        # again draining a pipe nobody will close.
        hangdir = _repo(stack)
        if hangdir:
            os.makedirs(os.path.join(hangdir, ".claude"), exist_ok=True)
            with open(os.path.join(hangdir, ".claude", "pre-push.cmd"), "w",
                      encoding="utf-8") as f:
                f.write("timeout=5\n"
                        '"%s" -c "import subprocess,sys; '
                        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'])\"\n"
                        % sys.executable.replace("\\", "/"))
            with open(os.path.join(hangdir, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            # The command itself exits at once; a grandchild sleeps 120s holding the captured
            # pipe. subprocess.run's cleanup blocks on that pipe forever, so the ONLY property
            # worth asserting is that a verdict arrives promptly. Reverting run_tests to
            # subprocess.run makes _child time out and rc_h come back None.
            t0 = time.time()
            rc_h, err_h = _child(hangdir, timeout=45)
            elapsed = time.time() - t0
            if rc_h is None:
                fails.append("a test leaving a grandchild on the pipe HUNG the push "
                             "(no verdict within 45s)")
            elif rc_h not in (0, 1):
                fails.append("grandchild-on-pipe: expected a real verdict, got rc=%r err=%r"
                             % (rc_h, err_h[:160]))
            elif elapsed > 40:
                fails.append("grandchild-on-pipe: verdict took %.0fs - the pipe is not bounded"
                             % elapsed)

        # 15. [finding 8] every outcome must SAY something. A refactor that drops a stderr
        # write leaves a gate that blocks with no diagnosis, or allows with no warning.
        msgdir = _repo(stack)
        if msgdir:
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "no test command" not in err_m:
                fails.append("no-command outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            os.makedirs(os.path.join(msgdir, ".claude"), exist_ok=True)
            with open(os.path.join(msgdir, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            cmdfile = os.path.join(msgdir, ".claude", "pre-push.cmd")
            with open(cmdfile, "w", encoding="utf-8") as f:
                f.write('python -c "import sys; sys.exit(1)"\n')
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 1 or "BLOCKED" not in err_m:
                fails.append("failing outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            with open(cmdfile, "w", encoding="utf-8") as f:
                f.write('python -c "pass"\n')
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "tests passed" not in err_m:
                fails.append("passing outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "no source touched since" not in err_m:
                fails.append("fast-path outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))
            with open(cmdfile, "w", encoding="utf-8") as f:
                f.write('timeout=5\npython -c "import time; time.sleep(60)"\n')
            with open(os.path.join(msgdir, "app.py"), "a", encoding="utf-8") as f:
                f.write("y = 2\n")
            rc_m, err_m = _capture_gate(msgdir)
            if rc_m != 0 or "NOT verified" not in err_m:
                fails.append("timeout outcome message missing: rc=%r err=%r"
                             % (rc_m, err_m[:120]))

        # 16. [finding 7] the GLOBAL_SHIM's pre-push branch - the ONE line that runs the gate
        # in every repo on the machine - was covered by nothing. Deleting it stayed green.
        ppdir = _repo(stack)
        if ppdir:
            os.makedirs(os.path.join(ppdir, ".claude"), exist_ok=True)
            ppcmd = os.path.join(ppdir, ".claude", "pre-push.cmd")
            with open(ppcmd, "w", encoding="utf-8") as f:
                f.write('python -c "import sys; sys.exit(1)"\n')
            with open(os.path.join(ppdir, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            shim_dir = _tmpdir(stack)
            pp_disp = os.path.join(shim_dir, "pre-push")
            with open(pp_disp, "w", encoding="utf-8", newline="\n") as f:
                f.write(render_shim())
            try:
                p = subprocess.run(["sh", pp_disp], cwd=ppdir, capture_output=True, text=True,
                                   timeout=90, env=env, encoding="utf-8", errors="replace")
                sh_ok = True
            except (OSError, subprocess.SubprocessError):
                sh_ok = False
            if not sh_ok:
                print("SELFTEST SKIP: sh unavailable, pre-push dispatcher branch untested")
            else:
                if p.returncode == 0 or "BLOCKED" not in (p.stderr or ""):
                    fails.append("pre-push dispatcher did NOT run the gate on failing tests "
                                 "(rc=%r err=%r)" % (p.returncode, (p.stderr or "")[:160]))
                with open(ppcmd, "w", encoding="utf-8") as f:
                    f.write('python -c "pass"\n')
                p2 = subprocess.run(["sh", pp_disp], cwd=ppdir, capture_output=True, text=True,
                                    timeout=90, env=env, encoding="utf-8", errors="replace")
                if p2.returncode != 0:
                    fails.append("pre-push dispatcher blocked a passing repo (rc=%r err=%r)"
                                 % (p2.returncode, (p2.stderr or "")[:160]))

        # 17/18. [findings 5, 6] linked worktrees. `git rev-parse --git-dir` resolves to
        # .git/worktrees/<name>, so the dispatcher looked for hooks in a directory that has
        # none and silently skipped every repo-local hook; install() crashed outright.
        wt_host = _repo(stack)
        if wt_host:
            with open(os.path.join(wt_host, "seed.txt"), "w", encoding="utf-8") as f:
                f.write("seed\n")
            genv = dict(env)
            genv.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                         "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
            wt_ok = True
            for argv in (["add", "-A"], ["commit", "-qm", "seed"]):
                if subprocess.run(["git", "-C", wt_host] + argv, capture_output=True,
                                  env=genv).returncode:
                    wt_ok = False
            wt_path = os.path.join(_tmpdir(stack), "wt")
            if wt_ok and subprocess.run(["git", "-C", wt_host, "worktree", "add", "-q", wt_path],
                                        capture_output=True, env=genv).returncode:
                wt_ok = False
            if not wt_ok:
                print("SELFTEST SKIP: git worktree unavailable")
            else:
                # 17: the dispatcher must still delegate to the repo's own hook
                hooks_common = os.path.join(wt_host, ".git", "hooks")
                os.makedirs(hooks_common, exist_ok=True)
                wt_marker = os.path.join(wt_path, "WT_HOOK_RAN").replace("\\", "/")
                lh = os.path.join(hooks_common, "post-commit")
                with open(lh, "w", encoding="utf-8", newline="\n") as f:
                    f.write('#!/bin/sh\necho ran > "%s"\n' % wt_marker)
                try:
                    os.chmod(lh, os.stat(lh).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                except OSError:
                    pass
                wdisp_dir = _tmpdir(stack)
                wdisp = os.path.join(wdisp_dir, "post-commit")
                with open(wdisp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(render_shim())
                try:
                    subprocess.run(["sh", wdisp], cwd=wt_path, capture_output=True, timeout=60,
                                   env=env)
                    if not os.path.exists(os.path.join(wt_path, "WT_HOOK_RAN")):
                        fails.append("dispatcher did NOT delegate inside a linked worktree - "
                                     "every repo-local hook is silently bypassed there")
                except (OSError, subprocess.SubprocessError):
                    print("SELFTEST SKIP: sh unavailable, worktree delegation untested")
                # 18: --install must not crash, and must write where git actually looks
                rc_i = 99
                try:
                    rc_i = install(wt_path)
                except Exception as e:
                    fails.append("install() in a linked worktree RAISED %r" % (e,))
                if rc_i == 0:
                    # [P13 D7] Assert against the host repo's real hooks dir, computed
                    # LITERALLY (hooks_common, already known 30 lines above). This used to
                    # probe `git rev-parse --git-path hooks` - the one primitive finding P1
                    # established is WRONG here, because it answers with core.hooksPath
                    # whenever that is set, which is exactly the state of any machine that has
                    # run --install-global. The test was asserting against the broken
                    # primitive the production code was fixed to stop using, so on such a
                    # machine it could pass while install() had written nowhere git looks.
                    if not os.path.exists(os.path.join(hooks_common, "pre-push")):
                        fails.append("install() in a linked worktree did not write pre-push "
                                     "into the host repo's real hooks dir %r" % (hooks_common,))
                    install(wt_path, remove=True)

        # 19c. [D7] git honours core.hooksPath INSTEAD of $GIT_DIR/hooks, with no fallback.
        # install() wrote to <common-dir>/hooks regardless, so in a husky/lefthook repo it
        # printed "installed ... gate command: npm test" and the repo was NOT gated - exactly
        # the case install_global()'s own message tells you to use --install for.
        hp_repo = _repo(stack)
        if hp_repo:
            # (a) a repo with NO local hooksPath must still use .git/hooks - even though a
            # GLOBAL core.hooksPath is set on this machine. Writing into the global dispatcher
            # directory would clobber the dispatchers themselves.
            d_plain, via_hp = _hooks_dir_for(hp_repo)
            expected_plain = os.path.join(_common_git_dir(hp_repo) or "", "hooks")
            if via_hp or os.path.normcase(d_plain or "") != os.path.normcase(expected_plain):
                fails.append("a repo with no LOCAL core.hooksPath resolved to %r instead of "
                             "%r - a global hooksPath must not redirect --install"
                             % (d_plain, expected_plain))

            # (b) a repo WITH a local hooksPath must install where git actually looks
            custom = os.path.join(hp_repo, "myhooks")
            os.makedirs(custom, exist_ok=True)
            subprocess.run(["git", "-C", hp_repo, "config", "core.hooksPath",
                            custom.replace("\\", "/")], capture_output=True)
            d_hp, via_hp2 = _hooks_dir_for(hp_repo)
            if not via_hp2 or os.path.normcase(d_hp or "") != os.path.normcase(custom):
                fails.append("local core.hooksPath ignored: resolved %r, expected %r"
                             % (d_hp, custom))
            with open(os.path.join(hp_repo, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            if install(hp_repo) != 0:
                fails.append("install() failed in a repo with a local core.hooksPath")
            if not os.path.exists(os.path.join(custom, "pre-push")):
                fails.append("install() wrote where git will NOT look - the repo is not "
                             "gated but install reported success")
            if os.path.exists(os.path.join(hp_repo, ".git", "hooks", "pre-push")):
                fails.append("install() wrote to .git/hooks, which core.hooksPath overrides")
            install(hp_repo, remove=True)
            if os.path.exists(os.path.join(custom, "pre-push")):
                fails.append("uninstall did not remove the hook from core.hooksPath")

            # (c) a FOREIGN hook already there must be refused, never clobbered
            foreign = os.path.join(custom, "pre-push")
            with open(foreign, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n# husky\nnpx husky run pre-push\n")
            if install(hp_repo) == 0:
                fails.append("install() overwrote a foreign pre-push hook instead of refusing")
            with open(foreign, encoding="utf-8") as f:
                if "husky" not in f.read():
                    fails.append("install() CLOBBERED an existing husky hook")

        # 19b. [finding 34] CROSS-HOOK: a pass recorded by fast_test_on_stop's OWN entry point
        # must be visible to the gate. They advertise "one source of truth"; keyed differently
        # they each behaved plausibly in isolation while every push re-ran a suite that had
        # passed seconds earlier. Drive the real main(), not the helper.
        xr = _repo(stack)
        if xr:
            os.makedirs(os.path.join(xr, ".claude"), exist_ok=True)
            with open(os.path.join(xr, ".claude", "fast-test.cmd"), "w", encoding="utf-8") as f:
                f.write('debounce=0\npython -c "pass"\n')
            with open(os.path.join(xr, "app.py"), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            import io as _io
            real_in, real_err = sys.stdin, sys.stderr
            sys.stdin = _io.StringIO(json.dumps({"cwd": xr}))
            sys.stderr = _io.StringIO()
            try:
                fast_test.main()
            finally:
                sys.stdin, sys.stderr = real_in, real_err
            xroot = _repo_root(xr) or xr
            if last_pass(xroot, 'python -c "pass"') <= 0:
                fails.append("a pass recorded by fast_test_on_stop is invisible to the gate - "
                             "the shared state file is not actually shared "
                             "(cwd=%r root=%r)" % (xr, xroot))

        # 19. [finding 27] core.hooksPath REPLACES .git/hooks wholesale, so any client hook
        # name with no dispatcher silently stops firing everywhere. Derive the list from git
        # rather than trusting a tuple that has already drifted once.
        missing_names = sorted(set(git_client_hook_names()) - set(CLIENT_HOOKS))
        if missing_names:
            fails.append("git knows client hooks with no dispatcher: %s" % missing_names)

    fast_test.STATE_DIR = real_state
    fails += _selftest_undispatched_disclosure()
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1
