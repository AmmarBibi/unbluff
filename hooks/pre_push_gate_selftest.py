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

import shutil

import pre_push_gate as _m

# Snapshot the parent's namespace so the test bodies can use bare names (including the
# underscored helpers `from x import *` would skip). READS only - see the rebinding rule above.
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})

# ------------------------------------------------------------- sh delegation accounting
# Three checks below execute a `#!/bin/sh` shim through an external shell. Each used to catch
# OSError, print "SELFTEST SKIP: sh unavailable" and CONTINUE - so on any box where `sh` is not
# on PATH, three of this gate's own tests verified NOTHING while the suite printed SELFTEST OK
# and exited 0, and run_selftests reported 32/32 over it.
#
# That box is not hypothetical and the skip is not rare. MEASURED 2026-08-09 on a stock Windows
# machine: `Get-Command sh` finds nothing, while THREE copies of sh.exe sit inside the Git
# install the same machine uses for every command this suite runs. All three sites skipped; the
# suite exited 0. The delegation paths are the ones that decide whether a user's own repo-local
# hooks keep firing, so "untested" here is not a small gap.
#
# A fixture that finds no case must FAIL, not pass. `_SH_SITES` records every delegation site
# and whether it actually RAN; selftest() prints the denominator and fails on any shortfall.
_SH_SITES = []

# The sites this suite is REQUIRED to exercise. Declared rather than derived because these are
# literal call sites, not a discoverable population - and a roster that is merely COUNTED
# cannot tell a deleted site from a skipped one. Set equality makes both red.
_SH_SITES_REQUIRED = frozenset({
    "dispatcher-delegation",   # 8b  - post-commit shim delegating to a repo-local hook
    "pre-push-dispatcher",     # 16  - the GLOBAL_SHIM pre-push branch that runs the gate
    "worktree-delegation",     # 17  - delegation from inside a linked worktree
})


def _sh_site(name, ran) -> None:
    """Record one sh-delegation site. Called exactly once per site, whatever the outcome.

    `ran` is TRI-STATE and the third value is load-bearing:
      True  - the delegation actually executed
      False - a shell was expected but the site did not run (a real failure)
      None  - UNAVAILABLE: the box cannot present this case at all (e.g. `git worktree` is not
              supported here), so the fixture was never built

    Collapsing None into False turns an environment incapability into a selftest FAILURE, which
    on such a box makes EVERY pre_push_gate mutation a HARNESS ERROR - the suite would report a
    defect in the code because of a missing feature in git. This repo already distinguishes the
    two everywhere else: `SKIP_RC` 77, and `no_regression`'s "I could not look" versus "there is
    nothing to look at" (see the CI-SHALLOW note in .github/workflows/selftest.yml). "A fixture
    that finds no case must FAIL" is about a fixture that LOOKED and found nothing - not about a
    box that cannot be asked the question.
    """
    _SH_SITES.append((name, None if ran is None else bool(ran)))


def _sh_delegation_fails(sites, required):
    """The failures implied by an sh-delegation ledger. PURE, so it can be driven directly.

    Inline in `selftest()` this logic could only ever be exercised on a machine with no shell at
    all - which is to say never, on any machine that gets as far as running this suite. Its
    failure branches would be permanently unreachable, and an unreachable guard is
    indistinguishable from a deleted one: a mutation removing it would survive on every runner.
    Extracted, `_selftest_sh_accounting` drives all three branches with synthetic ledgers on
    every platform, so deleting any of them goes red everywhere.

    Three states are kept apart on purpose - a site that SKIPPED, a site never REACHED, and a
    site nobody registered - because collapsing them is exactly how "3 of 3" would keep printing
    after a site had been deleted.
    """
    seen = {n for n, _ in sites}
    skipped = sorted(n for n, ok in sites if ok is False)
    unavailable = sorted(n for n, ok in sites if ok is None)
    missing = sorted(required - seen)
    extra = sorted(seen - required)
    fails = []
    if missing:
        fails.append("sh-delegation site(s) never REACHED: %r - the fixture found no case, so "
                     "this suite cannot say whether delegation works there" % (missing,))
    if extra:
        fails.append("unregistered sh-delegation site(s) %r - add them to _SH_SITES_REQUIRED, "
                     "or the roster under-counts while printing a full denominator" % (extra,))
    if skipped:
        fails.append("no POSIX shell was found, so sh delegation is UNTESTED at %d of %d "
                     "site(s): %r. These sites decide whether a user's own repo-local hooks "
                     "keep firing - a skip here is this suite reporting a pass over a question "
                     "it never asked" % (len(skipped), len(required), skipped))
    return fails


def _sh_delegation_line(sites, required) -> str:
    """The printed denominator line. PURE, so `_selftest_sh_accounting` can assert the NUMBER.

    The numerator is an INTERSECTION, not a subtraction. It used to be
    `len(required) - len(skipped) - len(missing)`, which under-reports as soon as an
    UNREGISTERED site is recorded as skipped (that name is not in `required`, so it was
    subtracted from a total it never belonged to) and can go NEGATIVE if a site is recorded
    twice. A denominator line that can print a wrong number is the exact thing this guard exists
    to prevent, so it is now computed from the set it is describing and pinned by a probe.
    """
    ran = {n for n, ok in sites if ok is True} & required
    skipped = sorted(n for n, ok in sites if ok is False)
    unavailable = sorted(n for n, ok in sites if ok is None)
    missing = sorted(required - {n for n, _ in sites})
    note = ""
    if skipped or missing:
        note += "; NOT executed: " + ", ".join(sorted(set(skipped + missing)))
    if unavailable:
        note += "; UNAVAILABLE on this box: " + ", ".join(unavailable)
    return "  [sh-delegation] %d of %d required site(s) executed%s" % (
        len(ran), len(required), note)


def _selftest_sh_accounting() -> list:
    """The delegation accounting must go red on each degraded ledger - on EVERY platform.

    This is the probe that makes the guard above mutation-testable. Without it the only machine
    that could prove the guard works is one with no shell, and such a machine never reaches
    here.
    """
    fails = []
    req = frozenset({"alpha", "beta"})
    # (label, ledger, must_fail, expected NUMERATOR in the printed line)
    # The numerator is asserted, not just the verdict: the printed denominator and the
    # adjudication are two different claims, and only the adjudication used to be probed.
    cases = [
        ("all executed", [("alpha", True), ("beta", True)], False, 2),
        ("one skipped", [("alpha", True), ("beta", False)], True, 1),
        ("one never reached", [("alpha", True)], True, 1),
        ("an unregistered site", [("alpha", True), ("beta", True), ("gamma", True)], True, 2),
        ("empty ledger", [], True, 0),
        # UNAVAILABLE is NOT a failure - the box cannot present the case. Collapsing this into
        # `skipped` turned a missing git feature into a red suite and every pre_push_gate
        # mutation into a HARNESS ERROR on such a box.
        ("one unavailable", [("alpha", True), ("beta", None)], False, 1),
        # The two ledgers that made the OLD subtraction-based numerator wrong. Both required
        # names ran, so the numerator is 2 in each; the old arithmetic printed 1 and 0.
        ("unregistered site recorded as skipped",
         [("alpha", True), ("beta", True), ("gamma", False)], True, 2),
        ("a site recorded twice", [("alpha", True), ("alpha", True), ("beta", True)], False, 2),
    ]
    for label, sites, want_fail, want_num in cases:
        got = _sh_delegation_fails(sites, req)
        if bool(got) != want_fail:
            fails.append("sh-accounting %r: expected %s, got %r"
                         % (label, "a failure" if want_fail else "no failure", got))
        line = _sh_delegation_line(sites, req)
        want_prefix = "  [sh-delegation] %d of %d required site(s) executed" % (want_num, len(req))
        if not line.startswith(want_prefix):
            fails.append("sh-accounting %r: printed line should start %r, got %r"
                         % (label, want_prefix, line))
    # DENOMINATOR, printed - a case list that silently emptied would otherwise read as a pass.
    print("  [sh-accounting] %d degraded-ledger case(s) checked (verdict + numerator)"
          % len(cases))
    if not cases:
        fails.append("the sh-accounting case list is EMPTY - this guard is checking nothing")
    return fails


def _sh_candidates(git_exe):
    """Every shell path worth probing for a given git location, nearest first. PURE.

    Separated from the filesystem so the WALK is testable without needing a machine that
    happens to have the awkward layout - see `_selftest_sh_candidates`. Left inside
    `_resolve_sh` it could only be checked on a box that presents the failing layout, and CI's
    Windows runner presents the benign one, so a mutation reverting the walk to a single level
    would have SURVIVED every job while being a real defect.
    """
    out = []
    if not git_exe:
        return out
    d = os.path.dirname(os.path.abspath(git_exe))
    for _ in range(4):  # bounded: no git layout nests its shell deeper than this
        # ORDER IS LOAD-BEARING: `bin/sh` before `usr/bin/sh`. Git for Windows ships BOTH, and
        # they are not equivalent - `bin/sh.exe` is the wrapper that sets up the environment,
        # `usr/bin/sh.exe` is the raw msys2 shell. MEASURED 2026-08-09 from a clean PowerShell
        # (NOT from inside a Git Bash session, which inherits the environment and hides the
        # difference - the first attempt at this measurement was confounded exactly that way):
        #   usr/bin/sh.exe  ->  COREUTILS_MISSING   (`ls` is not on PATH)
        #   bin/sh.exe      ->  COREUTILS_OK
        # `python` resolves under both, so the pre-push shim survives either way; anything using
        # coreutils does not. Picking the raw shell would run a user's repo-local hooks in an
        # environment git itself never gives them. Pinned by _selftest_sh_candidates, which
        # asserts the ORDER rather than mere membership - membership passed before this fix.
        for rel in (("bin", "sh"), ("usr", "bin", "sh"),
                    ("bin", "sh.exe"), ("usr", "bin", "sh.exe")):
            out.append(os.path.join(d, *rel))
        parent = os.path.dirname(d)
        if parent == d:  # filesystem root
            break
        d = parent
    return out


def _selftest_sh_candidates() -> list:
    """The candidate walk must reach the shell from every git layout a box can present.

    MEASURED 2026-08-09 on one stock install: git.exe exists at BOTH `<root>/cmd/git.exe` and
    `<root>/mingw64/bin/git.exe`, and which one PATH resolves first is not this code's choice.
    The obvious derivation `<dir of git>/../usr/bin/sh` is right for the first and WRONG for the
    second - it points into `mingw64`, which has no `usr/bin/sh` - so on a box carrying three
    copies of a shell it would report having none. This pins the walk that covers both, on every
    platform, without either layout needing to exist on the machine running it.
    """
    fails = []
    # Both the .exe (Windows) and extension-less (POSIX) shapes are asserted. The extension-less
    # pair used to be covered by NOTHING: every layout here named a `.exe`, so deleting
    # ("bin","sh") and ("usr","bin","sh") survived on every platform including both mutation
    # jobs - the candidate list was half-pinned while the guard printed a full denominator.
    layouts = {
        "cmd": (("R", "cmd", "git.exe"), ("R", "usr", "bin", "sh.exe")),
        "bin": (("R", "bin", "git.exe"), ("R", "usr", "bin", "sh.exe")),
        "mingw64": (("R", "mingw64", "bin", "git.exe"), ("R", "usr", "bin", "sh.exe")),
        "posix-usr": (("R", "usr", "bin", "git"), ("R", "usr", "bin", "sh")),
        "posix-local": (("R", "usr", "local", "bin", "git"), ("R", "bin", "sh")),
    }
    for label, (gparts, wparts) in sorted(layouts.items()):
        want = os.path.normpath(os.path.abspath(os.path.join(*wparts)))
        cands = [os.path.normpath(c)
                 for c in _sh_candidates(os.path.abspath(os.path.join(*gparts)))]
        if want not in cands:
            fails.append("git layout %r: the shell at %r is not among the %d candidate(s) "
                         "probed - a real install with this layout would report 'no shell "
                         "available' and skip three delegation tests" % (label, want, len(cands)))

    # ORDER, not just membership. `bin/sh` must be preferred over `usr/bin/sh`: on Git for
    # Windows the former sets up the environment and the latter does not (MEASURED - see
    # _sh_candidates). Asserting membership alone passed while the resolver picked the raw
    # shell, which is how that defect survived until an independent review found it.
    probe = [os.path.normpath(c)
             for c in _sh_candidates(os.path.abspath(os.path.join("R", "cmd", "git.exe")))]
    for wrapper, raw in ((("R", "bin", "sh.exe"), ("R", "usr", "bin", "sh.exe")),
                         (("R", "bin", "sh"), ("R", "usr", "bin", "sh"))):
        w = os.path.normpath(os.path.abspath(os.path.join(*wrapper)))
        r = os.path.normpath(os.path.abspath(os.path.join(*raw)))
        if w in probe and r in probe and probe.index(w) > probe.index(r):
            fails.append("candidate ORDER wrong: %r is probed before %r. On Git for Windows the "
                         "usr/bin shell runs WITHOUT git's coreutils on PATH, so a repo-local "
                         "hook using ls/grep/dirname would fail under it" % (r, w))

    # DENOMINATOR, printed - a layout list that silently emptied would otherwise read as a pass.
    print("  [sh-candidates] %d git layout(s) checked, order pinned" % len(layouts))
    if not layouts:
        fails.append("the sh-candidates layout list is EMPTY - this guard is checking nothing")
    return fails


def _resolve_sh():
    """A WORKING POSIX shell, found by asking the box. Returns (path or None, paths tried).

    Deliberately names no platform. The question is not "am I on Windows" - it is "does this
    machine have a shell that can run a `#!/bin/sh` shim", and only the machine can answer it.

    Order: `sh` on PATH; then git's own shell; then `bash`, which runs a `#!/bin/sh` script
    correctly. The git step is the one that matters, because git SHIPS a POSIX shell - it needs
    one for its own hooks - so any box that can run the git commands in this suite has a shell
    available even when PATH does not expose one.

    The ancestors of git's directory are WALKED rather than deriving the single
    `<dir of git>/../usr/bin/sh`, and that is load-bearing. MEASURED 2026-08-09 on a stock
    install: git.exe exists at BOTH `<root>/cmd/git.exe` (parent IS the root, so one level up
    works) and `<root>/mingw64/bin/git.exe` (parent is `mingw64`, which has no `usr/bin/sh.exe`
    - the root is two levels up). Which of them PATH resolves first is not this code's choice,
    so the one-level derivation would report "no shell available" on a machine carrying three
    copies of one.
    """
    tried = []

    def _works(path):
        """A path is not a shell until it BEHAVES like one.

        The probe asks for exit 7, not exit 0: a binary that ignores its arguments and exits
        cleanly would satisfy `-c "exit 0"`, and the entire point of this function is to refuse
        things that merely LOOK like a shell. Resolving a path is not the same as having one.
        """
        if not path:
            return False
        tried.append(path)
        try:
            return subprocess.run([path, "-c", "exit 7"], capture_output=True,
                                  timeout=30).returncode == 7
        except (OSError, subprocess.SubprocessError):
            return False

    cand = shutil.which("sh")
    if _works(cand):
        return cand, tried

    for c in _sh_candidates(shutil.which("git")):
        if os.path.isfile(c) and _works(c):
            return c, tried

    cand = shutil.which("bash")
    if _works(cand):
        return cand, tried

    return None, tried

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


def _selftest_shim_self_reference() -> list:
    """Every path-shaped self-reference in a shim template must name the copy that will RUN.

    Both templates carried `managed by ~/.claude/hooks/pre_push_gate.py` as a hardcoded literal
    while the exec line was templated from `__file__`. Install from a clone and the shim
    documents a file it does not use - and that comment is the ONLY thing a human reads when
    auditing a git hook.

    MEASURED HARM, 2026-08-05: during the installed-hooks divergence repair,
    `grep -rl '.claude/hooks/pre_push_gate.py' ~/.claude/githooks` returned 22 of 22 AFTER a
    correct re-point, because it matched the comment. The check written to confirm the stale
    path was gone reported the exact opposite of the truth.

    DERIVED, not a patch to two strings: any module-level string that looks like a shell shim is
    discovered by shape and checked, so a third template is covered the day it lands. A bare
    filename token is allowed - GLOBAL_SHIM greps for one deliberately.
    """
    import re
    fails = []
    sentinel = "/SENTINEL/DIR/pre_push_gate.py"
    templates = {n: v for n, v in vars(_m).items()
                 if isinstance(v, str) and v.lstrip().startswith("#!/bin/sh")}
    # DENOMINATOR, printed: a roster-shaped check that silently found nothing is the failure
    # this whole guard family exists to abolish.
    print("  [shim-self-reference] %d shim template(s) checked: %s"
          % (len(templates), ", ".join(sorted(templates)) or "(none)"))
    if not templates:
        fails.append("no shim template found by shape - this guard is checking NOTHING; "
                     "if the templates were renamed or restructured, re-derive the selector")
    for name, body in sorted(templates.items()):
        try:
            rendered = body.format(py="/SENTINEL/python.exe", script=sentinel)
        except (KeyError, IndexError, ValueError) as e:
            fails.append("%s: cannot be rendered with (py, script): %r" % (name, e))
            continue
        refs = re.findall(r"[^\s\"']*pre_push_gate\.py", rendered)
        pathish = [r for r in refs if "/" in r or "\\" in r]
        wrong = sorted({r for r in pathish if r != sentinel})
        if wrong:
            fails.append("%s: names a DIFFERENT copy than it execs: %r, exec target is %r. "
                         "A reader auditing the installed hook is sent to the wrong file, and a "
                         "grep for the stale path matches a correctly-installed shim"
                         % (name, wrong, sentinel))
    return fails


def selftest() -> int:
    import tempfile
    fails = []

    # Resolved ONCE, and the candidates probed are printed: a resolver that silently found
    # nothing and a resolver that was never asked look identical in a wall of output.
    sh_exe, sh_tried = _resolve_sh()
    print("  [sh-delegation] shell: %s (%d candidate(s) probed: %s)"
          % (sh_exe or "NONE FOUND", len(sh_tried), ", ".join(sh_tried) or "(none)"))

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
        # A REAL pytest project, not just a directory named `tests`. [FASTTEST-BLOCK] A bare
        # dir used to be enough for fast_test.detect() to return pytest, so this case proved
        # the override beat a competing detection. Now a bare dir detects nothing, and the
        # case would have kept passing while proving only that an override beats NOTHING.
        os.makedirs(os.path.join(r, "tests"), exist_ok=True)
        with open(os.path.join(r, "tests", "test_probe.py"), "w", encoding="utf-8") as f:
            f.write("def test_probe():\n    assert True\n")
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

        # 3b. [FASTTEST-BLOCK] A pytest run that proved NOTHING must not be reported as a
        # failing test suite. This gate shares fast_test's detect(), so it shared the defect:
        # a Rust/Go/JS repo with a tests/ dir got `python -m pytest`, exited 5 (NOTHING
        # COLLECTED) and was told "BLOCKED - tests are failing". detect() now declines those,
        # and this pins the containment at THIS gate's own call site - fast_test's selftest
        # cannot cover it, because this is a second, independent consumer of the same rule.
        # SYNTHETIC, and it must stay that way. A real `python -m pytest` here can only run
        # where pytest is installed, which is nowhere in CI - nothing is pip-installed in any
        # workflow. Guarding it with a third-state skip left FTB-6 with NO catcher on the very
        # runner that executes the mutation job, and it came back SURVIVED on run 31526789857
        # while passing locally. A real subprocess that exits 5 and carries the bare word
        # `pytest` as an argv token asks the same question on every box: it is classified by
        # the command STRING, before execution, so no shell comment semantics are involved.
        with open(os.path.join(r, ".claude", "pre-push.cmd"), "w", encoding="utf-8") as f:
            f.write('"%s" -c "import sys; sys.exit(5)" pytest\n'
                    % sys.executable.replace("\\", "/"))
        with open(os.path.join(r, "app.py"), "w", encoding="utf-8") as f:
            f.write("x = 2\n")
        _real_err = sys.stderr
        sys.stderr = __import__("io").StringIO()
        try:
            _rc_nv = gate(r)
            _err_nv = sys.stderr.getvalue()
        finally:
            sys.stderr = _real_err
        if _rc_nv != 0:
            fails.append("a pytest run that collected NOTHING blocked the push (rc %r) - "
                         "the gate is reporting 'tests are failing' about code it never "
                         "tested: %r" % (_rc_nv, _err_nv[:200]))
        elif "NOTHING VERIFIED" not in _err_nv:
            fails.append("the push was allowed on a run that proved nothing, SILENTLY - "
                         "unverified now looks identical to verified: %r" % (_err_nv[:200],))

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
            if not sh_exe:
                return -1
            try:
                return subprocess.run([sh_exe, disp], cwd=r, capture_output=True,
                                      timeout=60).returncode
            except (OSError, subprocess.SubprocessError):
                return -1

        rc = _dispatch()
        _sh_site("dispatcher-delegation", rc != -1)
        if rc == -1:
            print("SELFTEST SKIP: no POSIX shell, dispatcher delegation untested (FAILS below)")
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
            # [P14 D1-FIND-2] This assertion USED TO READ `rc_m != 0 or "NOT verified" not in
            # err_m` - it REQUIRED the gate to ALLOW a push whose tests never finished, and
            # named the case "timeout outcome message missing" as though only the wording were
            # at stake. The test encoded the fail-open as the contract, which is why the defect
            # survived every review of this file. A timeout is "didn't run", and "didn't run"
            # is not "passed". It BLOCKS now, and this pins that.
            if rc_m != 1 or "BLOCKED" not in err_m or "--no-verify" not in err_m:
                fails.append("a timed-out run must BLOCK and name the typed escape, not warn "
                             "and allow: rc=%r err=%r" % (rc_m, err_m[:160]))

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
            p = None
            sh_ok = False
            if sh_exe:
                try:
                    p = subprocess.run([sh_exe, pp_disp], cwd=ppdir, capture_output=True,
                                       text=True, timeout=90, env=env, encoding="utf-8",
                                       errors="replace")
                    sh_ok = True
                except (OSError, subprocess.SubprocessError):
                    sh_ok = False
            _sh_site("pre-push-dispatcher", sh_ok)
            if not sh_ok:
                print("SELFTEST SKIP: no POSIX shell, pre-push dispatcher branch untested "
                      "(FAILS below)")
            else:
                if p.returncode == 0 or "BLOCKED" not in (p.stderr or ""):
                    fails.append("pre-push dispatcher did NOT run the gate on failing tests "
                                 "(rc=%r err=%r)" % (p.returncode, (p.stderr or "")[:160]))
                with open(ppcmd, "w", encoding="utf-8") as f:
                    f.write('python -c "pass"\n')
                p2 = subprocess.run([sh_exe, pp_disp], cwd=ppdir, capture_output=True, text=True,
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
                # UNAVAILABLE, not skipped: this box cannot build a linked worktree at all, so
                # the delegation case was never presented. Recording it False would make a
                # missing git feature read as a defect in this repo and turn every
                # pre_push_gate mutation into a HARNESS ERROR here.
                _sh_site("worktree-delegation", None)
                print("SELFTEST SKIP: git worktree unavailable (recorded UNAVAILABLE, not run)")
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
                wt_ran = False
                if sh_exe:
                    try:
                        subprocess.run([sh_exe, wdisp], cwd=wt_path, capture_output=True,
                                       timeout=60, env=env)
                        wt_ran = True
                    except (OSError, subprocess.SubprocessError):
                        wt_ran = False
                _sh_site("worktree-delegation", wt_ran)
                if not wt_ran:
                    print("SELFTEST SKIP: no POSIX shell, worktree delegation untested "
                          "(FAILS below)")
                elif not os.path.exists(os.path.join(wt_path, "WT_HOOK_RAN")):
                    fails.append("dispatcher did NOT delegate inside a linked worktree - "
                                 "every repo-local hook is silently bypassed there")
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

    # DENOMINATOR, printed: the sh-delegation sites must have RUN, not merely been attempted.
    # The adjudication itself lives in _sh_delegation_fails so it can be driven with synthetic
    # ledgers on a machine that HAS a shell - see the note there.
    print(_sh_delegation_line(_SH_SITES, _SH_SITES_REQUIRED))
    fails += _sh_delegation_fails(_SH_SITES, _SH_SITES_REQUIRED)

    fails += _selftest_sh_accounting()
    fails += _selftest_sh_candidates()
    fails += _selftest_undispatched_disclosure()
    fails += _selftest_shim_self_reference()
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1
