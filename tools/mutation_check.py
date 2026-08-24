#!/usr/bin/env python3
"""Mutation harness: revert each fix on a scratch copy and require the suite to go RED.

A test that stays green when you delete the code it covers is decorative. Three tests written
on 2026-07-29 asserted things the implementation could not violate, and the v1.3.0 release was
declared closeable twice while 34 defects sat in it - both because "the suite passes" was read
as "the suite asks the right questions". This turns that into a mechanical check.

Each mutation names the plan finding it reverts. A mutation whose suite stays GREEN is a
FAILURE of this harness: it means the regression test for that finding does not bite.

    python tools/mutation_check.py                 # every mutation
    python tools/mutation_check.py pre_push_gate   # only mutations for one hook

Mutations marked posix_only=True are skipped on Windows (os.chmod exec bits are a no-op
there), so they are the ones only CI can prove. posix_only="nt" is the mirror: windows-only
code that does not exist on POSIX, which must SKIP on Linux rather than report SURVIVED.
"""
from __future__ import annotations

import argparse
import ast
import glob
import os
import stat
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Source trees copied into each scratch tree. `hooks/` ALONE meant a fix in tools/ or in a
# top-level entry point could not be mutation-tested at all - the harness that certifies every
# other fix as pinned had a blind spot covering its own directory, and the review-freshness
# gate meant to notice such things omitted tools/ for the same reason (P13 A1). Both halves of
# the evidence base were unwatched at once.
# [CI-JOBS] `.github` joined the roster the moment a gate started DERIVING a fact from the
# workflow file. Without it the scratch tree is not a faithful copy of the repo, and any gate
# that reads the workflow goes red at BASELINE - which is not a mutation result at all, it is
# the harness measuring its own missing fixture. Found immediately rather than by inference,
# because the baseline now prints WHY (see BASE-WHY below); before that fix this would have
# read as a bare `rc=1`.
# [ENFORCING 2026-08-18] `docs/audits` and `examples` joined for the same reason `.github` did,
# and the reason was MEASURED rather than reasoned: with the old roster, 5 of the 9 gates
# registered in ENFORCING mode went RED at BASELINE in a scratch tree - ship-bar could not find
# findings.json, file-size could not find its baseline and reported six recorded offenders as
# NEW, examples-settings-fresh could not find examples/settings.json. A baseline that is already
# red makes every mutation verified through it prove nothing (see [HIGH-6] below).
# `docs/audits` and NOT `docs`: the audits subtree is 964K; the whole of docs/ is 5.3M of gifs
# and screenshots no gate reads, and it would be copied once per entry across a 200-entry sweep.
# [ROSTER-GLOB 2026-08-19] `scripts` joined after an independent review found that widening the
# roster had ARMED a check that used to be vacuous. `docs/audits` brings review_runs.json into
# every scratch tree, which makes check_review_freshness's ambient ORPHAN assertion live - and
# that assertion runs BEFORE its "not a git checkout" skip. Its unit roster is UNIT_GLOBS, which
# covers `scripts/*.py`; this roster did not. So the moment anyone runs the gate's own prescribed
# `--record --unit scripts/make_demos.py`, every scratch tree reports a unit the gate "never asks
# about" and five pre-existing pins turn into HARNESS ERROR. That record is not hypothetical: it
# is exactly what task #17's sweep of the never-reviewed files is going to do.
# The general fix is the guard in check_mutation_anchors.py, which DERIVES this roster's
# adequacy from UNIT_GLOBS instead of trusting that someone kept the two lists in step.
COPY_TREES = ("hooks", "tools", "tests", "skills", ".github", "docs/audits", "examples",
              "scripts")
# README.md is an INPUT to check_readme_fresh, not just documentation: without it that gate's
# main() returns "cannot read README.md" and never reaches its checks, so every mutation of
# that file died at baseline. The roster has to contain what the gates READ, not only what
# gets mutated - the same distinction `.github` above turned on.
#
# [ROOT-GLOB 2026-08-24] Expressed as PATTERNS, and `*.py` rather than a list of root filenames.
# The enumerated form went stale the moment install.py's selftest was split into a sibling: the
# scratch tree got install.py without install_selftest.py, `install.py --selftest` died with
# ModuleNotFoundError, and every one of the 10 install mutations reported HARNESS ERROR -
# twenty-five minutes of CI proving nothing, with a summary line that still totalled cleanly.
# check_mutation_anchors.roster_gaps() is deliberately PURE (it must accept planted rosters, or
# its own mutations survive), so it cannot glob the filesystem to decide adequacy. Keeping the
# roster in the same vocabulary as UNIT_GLOBS lets its membership test stay exact while the copy
# loop below does the expansion.
COPY_FILES = ("*.py", "README.md")


def unit_path(root: str, name: str) -> str:
    """Resolve a mutation target to a path under `root`.

    A bare name is a hook (`hooks/<name>.py`) - the original and still commonest form. A name
    containing "/" is repo-relative (`tools/check_review_freshness`), which is what lets this
    harness reach the gate tooling.

    A bare name that is NOT a hook falls back to the repo ROOT. Without that fallback the
    repo-root files `COPY_FILES` supplies - `install.py` and `run_selftests.py` at the time,
    every tracked root `*.py` now - had no addressable form at all: a bare name went to
    `hooks/`, and a repo-relative name needs a "/" they do not have.
    The harness copied them into every scratch tree and could not mutate either, so the single
    most user-facing file in the repo - the one a user actually runs - was uncoverable BY
    CONSTRUCTION while the summary line printed a clean total. That is the INSTALL-TAUTOLOGY
    shape again: a roster not derived from what the code does.

    `hooks/` is probed FIRST so every pre-existing entry resolves exactly as before - this is
    strictly additive, and a name present in both places keeps its old meaning rather than
    silently changing target.
    """
    if "/" in name:
        return os.path.normpath(os.path.join(root, *(name + ".py").split("/")))
    hooked = os.path.join(root, "hooks", name + ".py")
    if os.path.isfile(hooked):
        return hooked
    rooted = os.path.join(root, name + ".py")
    if os.path.isfile(rooted):
        return rooted
    return hooked  # absent either way: report against the conventional location


VERIFY_KEYS = ("unit", "mode", "marker")
VERIFY_MODES = ("selftest", "enforcing")


def verify_spec(verify) -> tuple:
    """(unit, mode, marker, error) from an entry's 6th field. FAILS CLOSED on anything unknown.

    Two accepted forms, and the plain string is unchanged so all pre-existing entries keep their
    exact meaning:

        ""  / "some_unit"        -> verify by `<unit> --selftest`      (the original contract)
        {"mode": "enforcing"}    -> verify by running the unit the way it is REGISTERED

    WHY A SECOND MODE EXISTS. Every pin in this table verified via `<unit> --selftest`, so no
    line in any gate's `main()` was reachable by a mutation - the 2026-08-16 meta-review lists
    six behaviours left unpinned for that one reason, among them two FLOORS whose entire job is
    to stop a gate that read NOTHING from reporting OK. A harness that cannot reach main() also
    cannot tell a gate registered in the wrong MODE from a working one, which is the defect an
    independent review reproduced on a clean clone in one token.

    `marker` is the other half, and it is not a convenience. A fix whose whole content is SAYING
    SOMETHING - printing which source a derivation used, printing that a control could not run -
    changes no exit code, so an rc-only harness certifies it as pinned while the mutation is
    inert. The contract is asserted in BOTH directions in run(): the BASELINE output must
    CONTAIN the marker (or the probe is not measuring what it claims) and the mutant must not.
    """
    if verify is None:
        verify = ""
    if isinstance(verify, str):
        return verify, "selftest", "", ""
    if not isinstance(verify, dict):
        return "", "", "", ("verify field is %r; it must be a unit name or a dict"
                            % type(verify).__name__)
    unknown = sorted(set(verify) - set(VERIFY_KEYS))
    if unknown:
        return "", "", "", ("verify dict has unknown key(s) %r - a typo'd key would otherwise "
                            "select the DEFAULT mode silently" % unknown)
    mode = verify.get("mode", "selftest")
    if mode not in VERIFY_MODES:
        return "", "", "", "verify mode %r is not one of %r" % (mode, VERIFY_MODES)
    return verify.get("unit", ""), mode, verify.get("marker", ""), ""


def aux_gates(root: str) -> tuple:
    """(rows, error) - run_selftests' AUX_GATES, read from `root` with NO import side effects.

    `ast.literal_eval` rather than `import run_selftests`: importing it executes a module that
    inserts hooks/ on sys.path and pulls in the hook layer, inside a harness whose entire job is
    to run OTHER programs in a controlled tree. Reading it as data also means the registration
    that gets read is the one in the SCRATCH tree - the tree actually under test.
    """
    path = os.path.join(root, "run_selftests.py")
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError) as e:
        return (), "cannot read AUX_GATES from %s (%s)" % (path, e)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "AUX_GATES"
                                                for t in node.targets):
            try:
                return tuple(ast.literal_eval(node.value)), ""
            except ValueError as e:
                return (), "AUX_GATES is not a literal this harness can read (%s)" % e
    return (), "no AUX_GATES assignment in %s" % path


def enforcing_argv(root: str, target: str) -> tuple:
    """(argv, error) - the argv `target` is REGISTERED with, DERIVED from AUX_GATES.

    Never a literal in the mutation table. The whole point of this mode is that a gate wired
    ("--selftest",) applies to nothing while every other signal stays green; a mutation entry
    carrying its own hand-written argv would assert the mode it WISHED for and could not notice
    the flip - a declared roster standing in for a derived one, which is this repo's most
    repeated defect and the one `check_file_size` was built for.

    FAILS CLOSED, both ways. No enforcing registration is an error, not a fallback to
    `--selftest`: silently verifying the other mode is precisely how a mutation comes to prove
    nothing while reporting CAUGHT. Two enforcing registrations is an error too, because the
    entry would otherwise pick one by list order and the report could not say which.
    """
    rows, err = aux_gates(root)
    if err:
        return (), err
    want = os.path.normpath(os.path.abspath(target))
    hits = [(label, tuple(extra)) for label, parts, extra in rows
            if os.path.normpath(os.path.abspath(os.path.join(root, *parts))) == want]
    if not hits:
        return (), ("%s is in no AUX_GATES row, so it has no registered enforcing mode to "
                    "verify" % os.path.basename(target))
    # MEMBERSHIP via the shared predicate, never `extra != ("--selftest",)`. That spelling read
    # ("--selftest", "") as an ENFORCING registration and handed it back as the argv to verify
    # through - so the mutation would have run the gate's SELFTEST, the one thing this mode
    # exists to escape, while run_selftests skipped the row for the same reason. See gate_modes.
    enforcing = [(label, extra) for label, extra in hits if not is_selftest_argv(extra)]
    if not enforcing:
        return (), ("%s is registered ONLY as %r - there is no enforcing invocation to mutate "
                    "against. Register it enforcing, or verify this entry via the selftest"
                    % (os.path.basename(target), [e for _l, e in hits]))
    if len(enforcing) > 1:
        return (), ("%s has %d enforcing registrations (%r); the entry cannot say which one it "
                    "pins" % (os.path.basename(target), len(enforcing),
                              [lab for lab, _e in enforcing]))
    return enforcing[0][1], ""


def make_git_repo(scratch: str) -> str:
    """Make the scratch tree a real git repo. '' on success, else why not.

    An enforcing gate's SUBJECT is a repository, and several of them derive from git -
    `population()` prefers `git ls-files` and falls back to a walk. In a plain tempdir that
    preference can never be exercised, so a mutation of the git branch takes the fallback,
    produces an identical answer and reports SURVIVED for a reason that has nothing to do with
    the test. Measured at 0.47s per tree, and paid only by entries that ask for enforcing mode.

    The developer's own git config is excluded deliberately: a machine-dependent `core.hooksPath`
    or template dir would make this fixture mean something different on every box, and a harness
    whose fixture varies by machine cannot be used to adjudicate anything.
    """
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"]):
        try:
            p = subprocess.run(cmd, cwd=scratch, capture_output=True, text=True, timeout=120,
                               env=env, encoding="utf-8", errors="replace")
        except (OSError, subprocess.SubprocessError) as e:
            return "%s could not run (%s)" % (" ".join(cmd), e)
        if p.returncode != 0:
            return "%s exited %s: %s" % (" ".join(cmd), p.returncode,
                                         (p.stderr or p.stdout or "").strip()[:200])
    return ""


def _force_writable(func, path, _exc):
    """rmtree onerror: clear the read-only bit and retry once.

    `git add -A` writes loose objects at mode 0444. On Windows os.unlink refuses a read-only file,
    so `shutil.rmtree(..., ignore_errors=True)` failed on every enforcing entry and DISCARDED the
    error. MEASURED 2026-08-19, after one sweep: 21 orphaned `unbluff-mut-*` trees in %TEMP%,
    every one containing nothing but a 1.1 MB `.git`, 23 MB in total - while the harness printed a
    clean summary and exited 0. "Do not fail" and "do not say" are different decisions; this makes
    the cleanup work, and purge_scratch() below reports whatever it still cannot remove.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def purge_scratch(tmpdir: str = "") -> tuple:
    """(removed, left) - delete orphaned scratch trees from earlier runs. Bounded footprint.

    A leak that only ever grows is invisible until a disk is full; this makes each run clean up
    after the ones before it, and RETURN what it could not remove so main() can say so rather than
    leaving the reader to discover 23 MB of `.git` by accident.
    """
    root = tmpdir or tempfile.gettempdir()
    removed, left = 0, []
    try:
        names = os.listdir(root)
    except OSError:
        return 0, []
    for name in names:
        if not name.startswith("unbluff-mut-"):
            continue
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        shutil.rmtree(path, onerror=_force_writable)
        if os.path.exists(path):
            left.append(path)
        else:
            removed += 1
    return removed, left


def missing_anchors(live_text: str, edits) -> list:
    """The `find` strings in `edits` that no longer appear in `live_text`.

    ONE implementation, shared by `run()` below and by `tools/check_mutation_anchors.py`. A
    second copy of this rule in the standalone gate would be the twin defect this repo hunts:
    that gate exists to say something about what this harness actually does, and a gate whose
    rule has quietly diverged from the harness reports on a program nobody runs.
    """
    return [find for find, _replace in edits if find not in live_text]


# (unit, finding, description, [(find, replace), ...], posix_only[, verify_unit])
# `unit` is a hook name, or a repo-relative path like "tools/check_review_freshness".
# The table lives in two DATA modules. It reached 1415 lines inside this file against an
# 800-line limit, and the recorded decision in file_size_baseline.json was that the next growth
# be preceded by the split rather than absorbed by another re-record - a re-record is the
# loophole in the ratchet, and using it to fund the growth of the file that documents the
# loophole would have been the joke writing itself.
#
# Re-exported under the original name because every consumer - check_mutation_anchors.py, and
# this file's own anchor_audit/duplicate_ids - imports MUTATIONS from HERE. The split is
# therefore invisible downstream, which is the property that made it safe to do mechanically.
#
# The sys.path line is NOT boilerplate. A bare `import mutation_entries_a` resolves only because
# running `python tools/mutation_check.py` happens to put tools/ at sys.path[0]; under `python -m
# tools.mutation_check`, or any in-process import from a different cwd, it raises - and an
# ImportError here would empty the table this whole harness iterates. That is the exact defect
# the 2026-08-16 review found at ship_bar_gate.py:181 (an invocation-dependent sibling import
# whose failure is swallowed), so introducing a fresh instance of it while splitting the file
# would have been a poor trade for two saved lines.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gate_modes import is_selftest_argv  # noqa: E402  (path set directly above)
from mutation_entries_a import ENTRIES as _ENTRIES_A  # noqa: E402
from mutation_entries_b import ENTRIES as _ENTRIES_B  # noqa: E402

MUTATIONS = _ENTRIES_A + _ENTRIES_B


def anchor_audit(root: str = REPO, mutations=None) -> tuple:
    """(problems, anchors, units, multi) for every mutation anchor against CURRENT sources.

    [P14 M1] `run()` validates one entry's anchors on the way past. This asks the same question
    of the whole table in one cheap sweep, so a disarmed mutation surfaces in under a second
    instead of on the next ~25-minute full run - the gap that let the B3 entry-encoding change
    silently make `#20/23` unrunnable while every FILTERED run reported clean.

    Pure and root-parameterised so the gate's selftest can PLANT a drifted anchor. A selftest
    that could only audit the live repo would pass on a clean tree no matter what this function
    did, which is how every mutation of such a guard survives.

    Fails CLOSED. A unit that cannot be read is a PROBLEM, not a skip, and its anchors stay in
    the denominator - otherwise the total shrinks silently as units go missing and the sweep
    reads healthier the more of it has evaporated.

    `multi` is an OBSERVATION, not a failure: an anchor matching more than once means
    `str.replace(find, replace, 1)` mutates the FIRST site, which may not be the intended one.
    That is finding M-M12 in cluster 2; it is reported here so that row arrives already
    measured, and enforcing it here would be doing M-M12's work under M1's name.
    """
    if mutations is None:
        mutations = MUTATIONS
    problems, anchors, multi = [], 0, []
    units, cache = {}, {}
    for entry in mutations:
        unit, finding, edits = entry[0], entry[1], entry[3]
        path = unit_path(root, unit)
        units[path] = True
        anchors += len(edits)
        if path not in cache:
            try:
                with open(path, encoding="utf-8") as f:
                    cache[path] = (f.read(), None)
            except OSError as e:
                cache[path] = (None, e)
        text, err = cache[path]
        if text is None:
            problems.append("%s #%s: cannot read %s (%s) - a mutation naming a file that is "
                            "not there is as unrunnable as one whose anchor drifted"
                            % (unit, finding, os.path.relpath(path, root), err))
            continue
        for find in missing_anchors(text, edits):
            problems.append("%s #%s: anchor no longer matches %s: %r"
                            % (unit, finding, os.path.relpath(path, root), find[:70]))
        for find, _replace in edits:
            n = text.count(find)
            if n > 1:
                multi.append("%s #%s matches %dx" % (unit, finding, n))
    return problems, anchors, sorted(units), multi


def run(hook: str, finding: str, desc: str, edits, posix_only: bool, verify="") -> str:
    """Mutate `hook`, then run `verify` and require it to notice (default: the hook's own selftest).

    They differ when the defect lives in one file and the test that catches it lives in
    another - which is exactly the shape of a TWIN defect, so the harness has to express it.

    `verify` may also be a dict selecting ENFORCING mode and/or an output MARKER - see
    verify_spec(). In enforcing mode the verifier is invoked with the argv it is REGISTERED
    with, in a scratch tree that is a real git repo, with cwd set to that tree: an enforcing
    gate's subject is a repository, and if cwd stayed on the live repo the gate would read the
    developer's real tree while the mutation sat in the scratch one.
    """
    unit, mode, marker, spec_err = verify_spec(verify)
    if spec_err:
        return "HARNESS ERROR: %s" % spec_err
    # Validate the ANCHOR even when the mutation will be skipped. The early return used to
    # precede this, so a #30 anchor that had drifted was never checked on the authoring
    # machine and the harness still printed "all mutations caught".
    live = unit_path(REPO, hook)
    try:
        with open(live, encoding="utf-8") as f:
            live_text = f.read()
    except OSError as e:
        return "HARNESS ERROR: cannot read %s (%s)" % (hook, e)
    gone = missing_anchors(live_text, edits)
    if gone:
        return "HARNESS ERROR: mutation anchor not found: %r" % (gone[0][:70],)

    # `posix_only` is True for posix-only, or the string "nt" for windows-only. A mutation that
    # can only be MEANINGFUL on one platform must SKIP on the other, never report SURVIVED: a
    # no-op edit staying green says nothing about the test, and reading it as a decorative test
    # sent us hunting a defect that was not there (P13 F). A skip is reported and is not a pass.
    if posix_only is True and os.name == "nt":
        return "SKIPPED (posix only - this machine cannot run it; CI must)"
    if posix_only == "nt" and os.name != "nt":
        return "SKIPPED (windows only - the code it mutates does not exist on this platform)"
    scratch = tempfile.mkdtemp(prefix="unbluff-mut-")
    try:
        _ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for tree in COPY_TREES:
            parts = tree.split("/")          # nested entries: "docs/audits" is one SUBtree
            src = os.path.join(REPO, *parts)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(scratch, *parts), ignore=_ignore)
        # Patterns, expanded here. A literal name globs to itself, so plain entries still work.
        for pattern in COPY_FILES:
            for src in sorted(glob.glob(os.path.join(glob.escape(REPO), pattern))):
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(scratch, os.path.basename(src)))
        verify_target = unit_path(scratch, unit or hook)

        # The INVOCATION, chosen once and used for BOTH the baseline and the mutant. Deriving it
        # twice is how the two runs come to differ in something other than the mutation.
        argv, cwd = ["--selftest"], None
        if mode == "enforcing":
            argv, argv_err = enforcing_argv(scratch, verify_target)
            if argv_err:
                return "HARNESS ERROR: %s" % argv_err
            argv, cwd = list(argv), scratch
            git_err = make_git_repo(scratch)
            if git_err:
                return ("HARNESS ERROR: the scratch tree could not be made a git repo (%s), so "
                        "any git-derived path in the verifier would take its fallback and the "
                        "mutation would prove nothing about the derivation" % git_err)
        shown = " ".join(argv) or "(no argv - enforcing)"

        # [HIGH-6] BASELINE FIRST, on the UNMUTATED copy. If the verifying selftest is already
        # red in a scratch tree - e.g. meta_audit's asserted something about the REAL
        # environment that a non-git tempdir cannot satisfy - then EVERY mutation "fails" for
        # a reason unrelated to the mutation and the harness certifies them all as CAUGHT.
        # Two mutations (M6, D5-twin) were certified exactly that way.
        try:
            base = subprocess.run([sys.executable, verify_target] + argv,
                                  capture_output=True, text=True, timeout=400, cwd=cwd,
                                  stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
            base_out = (base.stdout or "") + (base.stderr or "")
            if base.returncode not in (0, 77):
                # [BASE-WHY] Say WHY, not just that. This reported only an rc, so a baseline-red
                # on a CI runner that does not reproduce locally was undiagnosable from the log
                # - measured 2026-08-12, run 31593005560: hook_health_check #C4 went red while
                # #C5 passed its baseline in the SAME SECOND, and the reason had to be inferred
                # from the neighbours rather than read. A checking instrument that cannot
                # explain its own failure is the defect class this repo exists to catch.
                tail = "\n".join(ln for ln in base_out.splitlines() if ln.strip())[-800:]
                return ("HARNESS ERROR: baseline already RED before mutating (%s %s "
                        "rc=%s) - this mutation would prove nothing. Baseline said:\n%s"
                        % (os.path.basename(verify_target), shown, base.returncode, tail))
            # The MARKER, asserted against the baseline BEFORE it is used to judge anything.
            # A marker the healthy run never prints would make every mutant "lose" it, and the
            # entry would report CAUGHT for as long as the string stayed misspelled - a probe
            # that cannot fail, which is the class this file exists to catch.
            if marker and marker not in base_out:
                return ("HARNESS ERROR: the baseline output does not contain the marker %r, so "
                        "its absence after mutating would prove nothing about the mutation"
                        % marker[:70])
        except subprocess.TimeoutExpired:
            return "HARNESS ERROR: baseline timed out before mutating"
        except (OSError, subprocess.SubprocessError) as e:
            return "HARNESS ERROR: baseline could not run (%s)" % e

        target = unit_path(scratch, hook)
        text = open(target, encoding="utf-8").read()
        for find, replace in edits:
            if find not in text:
                return "HARNESS ERROR: mutation anchor not found: %r" % (find[:70],)
            text = text.replace(find, replace, 1)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        target = verify_target
        try:
            p = subprocess.run([sys.executable, target] + argv, capture_output=True,
                               text=True, timeout=400, stdin=subprocess.DEVNULL, cwd=cwd,
                               encoding="utf-8", errors="replace")
            rc = p.returncode
        except subprocess.TimeoutExpired:
            return "CAUGHT (the mutated hook hung - the bound is real)"
        if rc == 77:
            # SKIP_RC. The verifying selftest could not RUN (no git/sh), so it asserted
            # nothing - counting a non-zero rc as "caught" certified 13 pre_push_gate
            # mutations as pinned on any machine without git.
            return "UNPROVEN (the verifying selftest could not run - rc 77)"
        if marker:
            # WHEN A MARKER IS DECLARED IT IS THE WHOLE VERDICT, and the rc is deliberately not
            # consulted. Reading "rc != 0 OR the marker vanished" as CAUGHT would have shipped a
            # pin that cannot fail: FS-CANNOTRUN exits 1 with the guard present (it says CANNOT
            # RUN) and exits 1 with the guard deleted (every recorded offender is re-reported as
            # NEW), so an rc-first rule reports CAUGHT for both and proves nothing about the
            # branch it names. The marker is the only thing that differs between them.
            out = (p.stdout or "") + (p.stderr or "")
            if marker not in out:
                return "CAUGHT (rc=%s, and the marker %r is gone)" % (rc, marker[:40])
            return ("SURVIVED - the test for finding %s is DECORATIVE (%r still printed at "
                    "rc=%s)" % (finding, marker[:40], rc))
        if rc == 0:
            return "SURVIVED - the test for finding %s is DECORATIVE" % finding
        return "CAUGHT (rc=%s)" % rc
    finally:
        # NOT ignore_errors=True. That swallowed every read-only git object make_git_repo creates
        # and leaked the whole scratch tree, silently. See _force_writable().
        shutil.rmtree(scratch, onerror=_force_writable)


def duplicate_ids() -> list:
    """(unit, finding) pairs that appear more than once.

    Two entries sharing an id make the report ambiguous and the CLI filter unable to name one
    of them - and it happened by accident the moment a second round of findings reused the
    D-series letters (P13). Cheap to check, impossible to notice by eye in an 80-entry table.
    """
    seen, dupes = set(), []
    for entry in MUTATIONS:
        key = (entry[0], entry[1])
        if key in seen:
            dupes.append(key)
        seen.add(key)
    return dupes


def main() -> int:
    # [#46] This harness spawns every unit's selftest AND builds its own git fixtures, and it is
    # a SECOND orchestrator: run_selftests' scrub does not reach it, because mutation_check is
    # registered NOT_A_GATE and runs from its own CI job. An adversarial review found the #46
    # fix reaching 1 of 4 such orchestrators while the evidence document claimed all four.
    # Scrubbed in main() rather than at module level because check_mutation_anchors.py imports
    # MUTATIONS from here, and a module that rewrites its importer's environment is its own
    # defect.
    from git_isolation import scrub_environ    # noqa: E402  (tools/ on sys.path above)
    scrub_environ()

    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default="", help="only mutations for this hook")
    args = ap.parse_args()
    dupes = duplicate_ids()
    if dupes:
        print("HARNESS ERROR: duplicate mutation ids %r - the report cannot name them apart"
              % (dupes,))
        return 1
    # Sweep what earlier runs leaked, and SAY what is left. A cleanup that cannot report its own
    # failure is how 23 MB of orphaned .git trees accumulated behind a clean summary line.
    _purged, _left = purge_scratch()
    if _purged:
        print("[mutation-check] removed %d orphaned scratch tree(s) from earlier runs" % _purged)
    if _left:
        print("[mutation-check] WARNING: %d scratch tree(s) could NOT be removed and are still "
              "on disk: %s" % (len(_left), ", ".join(_left[:5])))
    survivors = []
    errors = []
    skipped = []
    other_platform = []
    unproven = []
    filtered = 0
    for entry in MUTATIONS:
        hook, finding, desc, edits, posix_only = entry[:5]
        verify = entry[5] if len(entry) > 5 else ""
        # Match the bare name too: the unit may be written "./run_selftests" or
        # "tools/mutation_check", and a filter that only compared the full string made those
        # entries unreachable from the CLI - i.e. silently unrunnable, which is this file's
        # own failure mode.
        # verify may be a dict (enforcing mode), so the filter takes the UNIT out of the spec
        # rather than assuming a string. A filter that raised here would make every entry in
        # the new mode unreachable from the CLI - unrunnable, which is this file's own failure
        # mode and the reason [HIGH-5] below counts what it skipped.
        _vunit = verify_spec(verify)[0]
        _names = {hook, _vunit, hook.rsplit("/", 1)[-1], _vunit.rsplit("/", 1)[-1]}
        if args.only and args.only not in _names:
            # [HIGH-5] COUNT the filtered-out entries. They were recorded in no bucket while
            # the denominator stayed len(MUTATIONS), so `mutation_check.py pre_push_gate`
            # printed "51 of 51 mutations executed, 0 skipped / all mutations caught" after
            # running two. The one line the whole evidence base rests on was arithmetic
            # nonsense under the filter the docstring itself advertises.
            filtered += 1
            continue
        verdict = run(hook, finding, desc, edits, posix_only, verify)
        print("[%-28s #%-8s] %-58s -> %s" % (hook, finding, desc[:58], verdict))
        if verdict.startswith("SURVIVED"):
            survivors.append((hook, finding))
        elif verdict.startswith("HARNESS ERROR"):
            errors.append((hook, finding, verdict))
        elif verdict.startswith("SKIPPED"):
            # A skip is still not a pass, but a mutation marked for the OTHER platform can
            # never run here, so failing CI on it would just make the build permanently red.
            # It has to run on the other platform's job instead - which is why one now exists.
            (other_platform if "only" in verdict else skipped).append((hook, finding))
        elif verdict.startswith("UNPROVEN"):
            unproven.append((hook, finding))
    print()
    # ALWAYS print the denominator. "all mutations caught" was printed unqualified while a
    # posix-only mutation had never executed on this machine - so deleting the os.chmod it
    # guards left the harness certifying every fix as pinned. This file's output is the
    # evidence base for the whole fix round; it must not overstate what it ran.
    considered = len(MUTATIONS) - filtered
    executed = considered - len(skipped) - len(other_platform) - len(unproven)
    scope = " (filter %r: %d of %d entries considered)" % (args.only, considered,
                                                           len(MUTATIONS)) if args.only else ""
    print("%d of %d mutations executed, %d skipped, %d not-runnable-here, %d unproven%s"
          % (executed, considered, len(skipped), len(other_platform), len(unproven), scope))
    if unproven:
        print("UNPROVEN (%d): %s" % (len(unproven), unproven))
        print("  The verifying selftest could not RUN, so it asserted nothing.")
    if errors:
        print("HARNESS ERRORS (%d) - a mutation could not be applied, so nothing was proven:"
              % len(errors))
        for h, f, v in errors:
            print("  %s #%s: %s" % (h, f, v))
    if survivors:
        print("MUTATIONS SURVIVED (%d): %s" % (len(survivors), survivors))
        print("Each one names a fix whose regression test does not actually bite.")
    if other_platform:
        # Named, never silent: the denominator has to show these were not executed here.
        print("NOT RUNNABLE ON THIS PLATFORM (%d): %s" % (len(other_platform), other_platform))
        print("  These are proven by the OTHER platform's job, not by this one. If that job "
              "does not exist, they are proven NOWHERE.")
    if skipped:
        print("SKIPPED (%d): %s" % (len(skipped), skipped))
        print("  A skip is NOT a pass - these fixes are unproven on this machine.")
        if os.environ.get("CI"):
            print("  CI must not skip: failing.")
            return 1
    if unproven and os.environ.get("CI"):
        return 1
    if not survivors and not errors:
        if args.only:
            print("filtered run - this proves nothing about the %d entries not considered"
                  % filtered)
        elif skipped or unproven or other_platform:
            print("every EXECUTED mutation was caught; %d remain unproven here"
                  % (len(skipped) + len(unproven) + len(other_platform)))
        else:
            print("all mutations caught - every fix is pinned by a test that fails without it")
    # [2026-08-13] Record it. This is the tier the ledger most needed and least had: it runs
    # for ~30 minutes and therefore rarely, so "when did the sweep last pass?" was answerable
    # only from a scratchpad or someone's memory. A FILTERED run is recorded as its own gate
    # name - it proves nothing about the entries it skipped, and a ship bar that could not
    # tell the two apart would accept a 3-entry run as a full sweep.
    try:
        import gate_ledger
        gate_ledger.record("mutation_sweep_filtered" if args.only else "mutation_sweep",
                           "FAIL" if (survivors or errors) else "PASS",
                           executed=len(MUTATIONS) - filtered - len(skipped)
                           - len(other_platform),
                           survivors=len(survivors), errors=len(errors),
                           unproven=len(unproven), only=args.only or None)
    except Exception:                              # never let bookkeeping fail a gate
        pass
    return 1 if (survivors or errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
