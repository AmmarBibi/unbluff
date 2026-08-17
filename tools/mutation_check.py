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
import os
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
COPY_TREES = ("hooks", "tools", "tests", "skills", ".github")
# README.md is an INPUT to check_readme_fresh, not just documentation: without it that gate's
# main() returns "cannot read README.md" and never reaches its checks, so every mutation of
# that file died at baseline. The roster has to contain what the gates READ, not only what
# gets mutated - the same distinction `.github` above turned on.
COPY_FILES = ("install.py", "run_selftests.py", "README.md")


def unit_path(root: str, name: str) -> str:
    """Resolve a mutation target to a path under `root`.

    A bare name is a hook (`hooks/<name>.py`) - the original and still commonest form. A name
    containing "/" is repo-relative (`tools/check_review_freshness`), which is what lets this
    harness reach the gate tooling.

    A bare name that is NOT a hook falls back to the repo ROOT. Without that fallback the two
    files in `COPY_FILES` - `install.py` and `run_selftests.py` - had no addressable form at
    all: a bare name went to `hooks/`, and a repo-relative name needs a "/" they do not have.
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

from mutation_entries_a import ENTRIES as _ENTRIES_A  # noqa: E402  (path set directly above)
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


def run(hook: str, finding: str, desc: str, edits, posix_only: bool, verify: str = "") -> str:
    """Mutate `hook`, then run `verify`'s selftest (default: the mutated hook's own).

    They differ when the defect lives in one file and the test that catches it lives in
    another - which is exactly the shape of a TWIN defect, so the harness has to express it.
    """
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
            src = os.path.join(REPO, tree)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(scratch, tree), ignore=_ignore)
        for name in COPY_FILES:
            src = os.path.join(REPO, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(scratch, name))
        verify_target = unit_path(scratch, verify or hook)

        # [HIGH-6] BASELINE FIRST, on the UNMUTATED copy. If the verifying selftest is already
        # red in a scratch tree - e.g. meta_audit's asserted something about the REAL
        # environment that a non-git tempdir cannot satisfy - then EVERY mutation "fails" for
        # a reason unrelated to the mutation and the harness certifies them all as CAUGHT.
        # Two mutations (M6, D5-twin) were certified exactly that way.
        try:
            base = subprocess.run([sys.executable, verify_target, "--selftest"],
                                  capture_output=True, text=True, timeout=400,
                                  stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
            if base.returncode not in (0, 77):
                # [BASE-WHY] Say WHY, not just that. This reported only an rc, so a baseline-red
                # on a CI runner that does not reproduce locally was undiagnosable from the log
                # - measured 2026-08-12, run 31593005560: hook_health_check #C4 went red while
                # #C5 passed its baseline in the SAME SECOND, and the reason had to be inferred
                # from the neighbours rather than read. A checking instrument that cannot
                # explain its own failure is the defect class this repo exists to catch.
                tail = "\n".join(
                    ln for ln in ((base.stdout or "") + (base.stderr or "")).splitlines()
                    if ln.strip())[-800:]
                return ("HARNESS ERROR: baseline already RED before mutating (%s --selftest "
                        "rc=%s) - this mutation would prove nothing. Baseline said:\n%s"
                        % (os.path.basename(verify_target), base.returncode, tail))
        except subprocess.TimeoutExpired:
            return "HARNESS ERROR: baseline selftest timed out before mutating"
        except (OSError, subprocess.SubprocessError) as e:
            return "HARNESS ERROR: baseline selftest could not run (%s)" % e

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
            p = subprocess.run([sys.executable, target, "--selftest"], capture_output=True,
                               text=True, timeout=400, stdin=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace")
            rc = p.returncode
        except subprocess.TimeoutExpired:
            return "CAUGHT (the mutated hook hung - the bound is real)"
        if rc == 0:
            return "SURVIVED - the test for finding %s is DECORATIVE" % finding
        if rc == 77:
            # SKIP_RC. The verifying selftest could not RUN (no git/sh), so it asserted
            # nothing - counting a non-zero rc as "caught" certified 13 pre_push_gate
            # mutations as pinned on any machine without git.
            return "UNPROVEN (the verifying selftest could not run - rc 77)"
        return "CAUGHT (rc=%s)" % rc
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


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
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default="", help="only mutations for this hook")
    args = ap.parse_args()
    dupes = duplicate_ids()
    if dupes:
        print("HARNESS ERROR: duplicate mutation ids %r - the report cannot name them apart"
              % (dupes,))
        return 1
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
        _names = {hook, verify, hook.rsplit("/", 1)[-1], verify.rsplit("/", 1)[-1]}
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
