"""Selftest suite for wired_clone_sanity.py - the item-10 machine-sanity checks.

Invoked by wired_clone_sanity.py's `--selftest` dispatch; not a hook and not registered anywhere.
That sentence is load-bearing and not decoration: check_selftest_isolation decides its safety
POPULATION as "has a mutating git verb AND the string `--selftest` appears in the file", so a
fixture-building module whose prose never happens to mention the flag is silently exempt from
the gate that checks it scrubs. This file builds real repositories with `init` and `config`
writes, and on first write it was invisible for exactly that reason. Recorded in docs/PLAN.md as
item 12: membership in that population should follow DELEGATION, the way the scrub already does,
rather than a prose mention.

Split out for the same reason as hook_health_check_selftest.py: the checks and their battery
together would put wired_clone_sanity.py over the 800-line rule, and B3-P's precedent is to
MOVE rather than record the violation.

It is listed in hook_health_check.KNOWN_NO_SELFTEST because it IS the selftest - a module whose
only job is testing another one does not need one of its own, and the floor exists to force that
statement rather than let the omission pass unnoticed.

REBINDING RULE, inherited verbatim from hook_health_check_selftest.py and load-bearing here for
a specific case: the parent's production code reads the PARENT module's globals, so assigning to
a bare name would rebind only this module's copy and leave production reading the old one - the
test would keep passing while testing nothing. The blind-extractor case below rebinds
`_FIXTURE_ID_RE`, and it goes through `_m.<name>` for exactly that reason.
"""

from __future__ import annotations

import os
import re
import shutil
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import wired_clone_sanity as _m  # noqa: E402

# SCRUB AT IMPORT, not inside selftest(). The first version called scrub_environ() at the top of
# selftest() and check_selftest_isolation correctly reported UNISOLATED: a scrub reachable only
# through a function it cannot prove is invoked is item 4's own named failure ("moved into an
# uncalled helper and all 41 gates stay green"). At import it runs before any fixture code in
# this module can execute, which is the property that actually matters, and it is what every
# sibling here already does - the gate's delegation rule is written around "the import IS the
# call". No inline copy of GIT_REDIRECT_VARS: a duplicated roster is the defect this suite has
# paid for twice, so an unimportable mechanism becomes a SKIP that says so.
_TOOLS = os.path.join(os.path.dirname(_HOOKS_DIR), "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
try:
    from git_isolation import scrub_environ, scrubbed_env  # noqa: E402
    scrub_environ()
    _ISOLATED = True
except ImportError:  # pragma: no cover - partial checkout
    _ISOLATED = False


def _m_skip_rc() -> int:
    """SKIP_RC as hook_health_check declares it - READ, never re-declared, so the two cannot
    drift into a skip that one orchestrator reads as a pass and the other as a failure."""
    try:
        from hook_health_check import SKIP_RC
        return SKIP_RC
    except ImportError:
        return 77


def selftest() -> int:
    """[item 10] The three states #46 left on the wired clone must each turn this RED.

    Every RED case is paired with a GREEN control on a healthy repository, because a check that
    always fires proves nothing and a guard that fires on correct work gets disabled. The
    controls are not decoration: they are half the cases here.

    THE CASE THAT PAID FOR THIS FILE. The first version derived the repository with `rev-parse
    --show-toplevel`, which FAILS on a repo marked core.bare - so the broken clone dropped out of
    the roster entirely, the check reported nothing, and the healthy-repo control still passed.
    The defect made itself invisible to its own detector. It was caught by writing this battery
    BEFORE believing the check, and `core.bare is still in the roster` below is the pin for it.

    Fixtures build real repositories, so the environment is scrubbed first (#46: GIT_DIR beats
    `git -C`). No inline copy of the redirect-variable list is kept here - a duplicated roster is
    the defect this suite has paid for twice - so if git_isolation cannot be imported the cases
    are SKIPPED and say so, rather than running unscrubbed against the real repository.

    COST, MEASURED 2026-08-25 rather than estimated, and this is the second reading because the
    first one was made obsolete by the split it argued for. While these cases lived inside
    hook_health_check_selftest.py they cost **1.56s** and took that hook to **8.37s of its
    10.00s share (84%)** - close to the 93% that file records as the level where the mutation
    harness reported `baseline already RED` for six unrelated mutations. The 800-line rule forced
    the split for an unrelated reason, and the split fixed this too: hook_health_check is back to
    **6.78s / 68%** and this battery runs on its own budget at **1.78s** (measured 02:31:55Z).
    It is spawn-bound - ~40 git spawns at ~32ms - and cannot be stubbed the way
    _selftest_slice_age_stamp_is_not_refreshed stubs its spawns, because there the decision under
    test was NOT the spawn, and here the git config read IS the decision under test.
    """
    import os
    import subprocess
    import tempfile

    # SKIP_RC, never 0. A skip reported as a pass is how a gate evaporates without anyone
    # noticing - the same rule hook_health_check applies to its weekly sweep. Both paths SAY
    # what they could not do; neither claims the checks were verified.
    if not _ISOLATED:
        print("SELFTEST SKIPPED: tools/git_isolation.py is not importable, and these cases will "
              "not build git fixtures unscrubbed (#46)")
        return _m_skip_rc()
    if shutil.which("git") is None:
        print("SELFTEST SKIPPED: no git on PATH, so the machine-sanity cases cannot run")
        return _m_skip_rc()
    env = scrubbed_env()
    fails = []
    cases = []

    # THIS FILE MUST CONTRIBUTE NOTHING TO THE FIXTURE VOCABULARY, and the keys are composed to
    # guarantee it. fixture_identities() scans hooks/*.py and tools/*.py as TEXT, and this file
    # is in hooks/ - so writing the config-call shape out in full, with the control's address as
    # a bare literal, made the extractor derive THAT as a fixture identity, and the check then
    # fired on the very control meant to prove it does not fire on correct work. Five controls
    # went red at once. (This comment cannot spell the shape out either, for the same reason -
    # the first draft of it did, and left the file still contributing one identity.)
    # A grep guard must never search for a literal it contains. Same hazard, same file, same
    # technique as `_flag = "--" + "selftest"` above, which exists for the identical reason.
    # Pinned below by `this file contributes zero identities`, so it cannot come back quietly.
    _EMAIL, _NAME = "user." + "email", "user." + "name"
    _REAL_EMAIL, _REAL_NAME = "real.person@" + "example.com", "Real " + "Person"
    _FIX_EMAIL, _FIX_NAME = "t" + "@t", "t"

    def git(repo, *args):
        subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True,
                       env=env, stdin=subprocess.DEVNULL)

    def cfg_for(script):
        return {"hooks": {"SessionStart": [{"hooks": [
            {"type": "command", "command": 'python "%s"' % script}]}]}}

    def want(label, red, cfg, needle=""):
        """`red` says whether this state MUST produce a problem. Both directions are asserted."""
        cases.append((label, red))
        probs, n_repos, _skipped = _m.machine_sanity_problems(cfg)
        if n_repos != 1:
            fails.append(f"machine sanity: {label} examined {n_repos} repos, not 1 - the case "
                         f"is vacuous and would pass however the check behaved")
            return
        if red and not probs:
            fails.append(f"machine sanity: {label} did NOT fire")
        elif red and needle and not any(needle in p for p in probs):
            fails.append(f"machine sanity: {label} fired without naming {needle!r}: {probs}")
        elif not red and probs:
            fails.append(f"machine sanity: {label} fired on CORRECT work: {probs}")

    with tempfile.TemporaryDirectory() as tmp:
        repo = os.path.join(tmp, "wt")
        os.makedirs(repo)
        git(repo, "init", "-q")
        git(repo, "config", _EMAIL, _REAL_EMAIL)
        git(repo, "config", _NAME, _REAL_NAME)
        script = os.path.join(repo, "somehook.py")
        with open(script, "w", encoding="utf-8") as f:
            f.write("# a hook\n")
        cfg = cfg_for(script)

        want("healthy repo", False, cfg)

        # 1. core.bare on a repo that HAS a working tree - and it must stay VISIBLE while broken
        git(repo, "config", "core.bare", "true")
        want("core.bare=true on a worktree", True, cfg, "--unset core.bare")
        git(repo, "config", "core.bare", "false")
        want("CONTROL core.bare=false", False, cfg)
        git(repo, "config", "--unset", "core.bare")

        # 2. core.hooksPath at a directory that does not exist
        dead = os.path.join(tmp, "deleted_temp", "myhooks").replace("\\", "/")
        git(repo, "config", "core.hooksPath", dead)
        want("core.hooksPath at a deleted dir", True, cfg, "silently disabled")
        os.makedirs(dead)
        want("CONTROL hooksPath that exists", False, cfg)
        spaced = os.path.join(tmp, "dir with spaces", "hooks here")
        os.makedirs(spaced)
        git(repo, "config", "core.hooksPath", spaced.replace("\\", "/"))
        # Pins the NUL-record parse: a whitespace split would truncate this to a path that does
        # not exist and raise a false alarm against a perfectly healthy machine.
        want("CONTROL hooksPath containing spaces", False, cfg)
        git(repo, "config", "core.hooksPath", "relhooks")
        os.makedirs(os.path.join(repo, "relhooks"))
        want("CONTROL relative hooksPath that exists", False, cfg)
        git(repo, "config", "--unset", "core.hooksPath")

        # 3. a fixture identity that escaped into a real config
        git(repo, "config", _EMAIL, _FIX_EMAIL)
        git(repo, "config", _NAME, _FIX_NAME)
        want("fixture identity in a real config", True, cfg, "FIXTURE")
        git(repo, "config", _EMAIL, _REAL_EMAIL)
        git(repo, "config", _NAME, _REAL_NAME)
        want("CONTROL a real identity", False, cfg)

        # 4. a GENUINELY bare repository is allowed to be bare
        bare = os.path.join(tmp, "genuine.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], capture_output=True, env=env)
        bscript = os.path.join(bare, "hooks", "somehook.py")
        os.makedirs(os.path.dirname(bscript), exist_ok=True)
        with open(bscript, "w", encoding="utf-8") as f:
            f.write("# a hook inside a genuinely bare repo\n")
        want("CONTROL a genuinely bare repo", False, cfg_for(bscript))

        # 5. the extractor must prove it looked in the right place
        _vocab = _m.fixture_identities()
        if not {_FIX_EMAIL, _FIX_NAME} <= _vocab:
            fails.append("machine sanity: fixture_identities() no longer derives the identities "
                         f"#46 actually wrote: {sorted(_vocab)}")
        # A SUPERSET, not equality: adding a legitimate new fixture identity somewhere in the
        # suite is correct work, and a guard that reddens on correct work gets disabled.
        # THE PIN for the hazard above - this file must contribute NOTHING to the vocabulary.
        # Equality caught the contamination once; this catches it forever without the brittleness.
        _self_only = _m.fixture_identities(roots=[])
        _here = _m.fixture_identities(roots=[os.path.dirname(os.path.abspath(__file__))])
        if _REAL_EMAIL in _here or _REAL_NAME in _here:
            fails.append("machine sanity: this selftest file has put its CONTROL identity into "
                         "the fixture vocabulary - the check will now fire on the control that "
                         "proves it does not fire on correct work. Compose the call, do not "
                         "write the shape out in full. (a grep guard must never search for a "
                         "literal it contains)")
        if _self_only:
            fails.append(f"machine sanity: an EMPTY root list derived {sorted(_self_only)} - "
                         f"fixture_identities is reading somewhere it was not asked to")
        # Rebind through `_m`, per this file's REBINDING RULE - the production code reads the
        # PARENT's global, so a bare assignment here would test this module's copy and nothing else.
        _saved = _m._FIXTURE_ID_RE
        try:
            # `(?!)` - a lookahead that can never succeed. The first version neutered with a
            # sentinel WORD, and the sentinel was a literal in this file, which the extractor
            # scans: findall on a group-less pattern returns WHOLE MATCHES, so the "blind"
            # extractor derived exactly one identity - its own sentinel - and was never blind.
            # The case then reported that production "passes silently", which is a finding about
            # the probe wearing the costume of a finding about the code. A probe not shown to
            # FAIL is not a probe; the assertion below is what shows it.
            _m._FIXTURE_ID_RE = re.compile(r"(?!)")
            if _m.fixture_identities() != set():
                fails.append("machine sanity: the blind-extractor CONTROL is not controlling - "
                             f"neutering left {sorted(_m.fixture_identities())} behind, so "
                             f"whatever it reports next is about the probe, not the check")
            else:
                blind, _n, _s = _m.machine_sanity_problems(cfg)
                if not any("looking in the wrong place" in p for p in blind):
                    fails.append("machine sanity: an extractor that matches NOTHING passes "
                                 "silently instead of reporting that it cannot fire")
        finally:
            _m._FIXTURE_ID_RE = _saved

    # 6. TOTAL over a malformed settings tree [P13 C4]: this check may cost itself, never the report
    for bad in ({"hooks": "not-a-dict"}, {"hooks": {"S": "x"}}, {"hooks": {"S": [None]}},
                {"hooks": {"S": [{"hooks": [{"command": 17}]}]}}, {}):
        try:
            out = _m.machine_sanity_problems(bad)
            if not (isinstance(out, tuple) and len(out) == 3):
                fails.append(f"machine sanity: bad shape {bad} returned {out!r}")
        except Exception as e:  # noqa: BLE001 - the whole point is that it cannot raise
            fails.append(f"machine sanity: {bad} RAISED {e!r} - it would discard the whole report")
    for _f in fails:
        print("SELFTEST FAIL: " + _f)
    # Name the DENOMINATOR, and name how many of the cases are CONTROLS. A battery that only
    # ever asserts "it fired" cannot tell a working check from one that fires at everything, and
    # rc=0 with NO OUTPUT is W-RS2's exact shape: run_selftests would count a gate that verified
    # nothing. Both halves are printed for every run, pass or fail.
    _red = sum(1 for _lbl, _r in cases if _r)
    print("SELFTEST %s - %d state(s) asserted (%d must fire, %d controls that must NOT), "
          "plus %d extractor and %d totality case(s)"
          % ("OK" if not fails else "FAILED", len(cases), _red, len(cases) - _red, 3, 5))
    return 1 if fails else 0


if __name__ == "__main__":
    rc = selftest()
    print("SELFTEST OK" if rc == 0 else "SELFTEST FAILED")
    raise SystemExit(rc)
