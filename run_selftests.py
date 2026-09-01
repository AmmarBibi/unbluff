#!/usr/bin/env python3
"""Run every self-testable hook's --selftest and exit nonzero if any fail.

Cross-platform (used by CI on Linux/macOS/Windows and locally).

Self-testability is DETECTED, not listed. A hardcoded roster silently drops any hook whose
author forgets to add it: `duplicate_registration_check` shipped with a full selftest and
CI printed "skip (no selftest)" while still reporting all-green (found 2026-07-29).
Detection looks for the actual dispatch (`"--selftest" in sys.argv`), not a prose mention,
so a docstring reference cannot cause a false positive. SELFTESTABLE stays as a FLOOR: a
name listed there must remain self-testable, and losing its dispatch is an error rather
than a silent skip.
"""

import ast
import datetime
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# [2026-08-14] The suite's own DURATION. It grew from ~56s to 109.1s in a day and
# silently approached the pre-push gate's 120s ceiling until that gate BLOCKED a correct
# push. Growth that is only discovered at the ceiling is growth nobody was watching, so
# it is recorded in the gate ledger beside the result.
import time as _time
_STARTED = _time.perf_counter()
sys.path.insert(0, os.path.join(HERE, "hooks"))
# tools/ too, for the ONE definition of "does this registration run the selftest or the
# measurement?". Two spellings of that rule is what let a ("--selftest", "") registration read as
# ENFORCING in enforcing_mode_gaps() and as the SELFTEST at the target - see tools/gate_modes.py.
sys.path.insert(0, os.path.join(HERE, "tools"))

# ONE detector, imported - not a second copy. This file and hook_health_check.py each carried
# the SAME hardcoded roster; run_selftests was converted to detection on 2026-07-29 and the
# twin in hook_health_check was left behind, so the SessionStart line kept reporting
# "weekly selftests 10/10 OK" while four hooks went unswept. Two implementations of one rule
# is the defect, so there is now one implementation and one import.
from hook_health_check import (  # noqa: E402  (path set above)
    KNOWN_NO_SELFTEST, SKIP_RC, all_hook_files, floor_violations, has_selftest,
    selftestable_hooks,
)
from gate_modes import is_selftest_argv  # noqa: E402  (path set above)
# [#46] The suite spawns fixtures that build throwaway git repositories. Under a git hook -
# which is where this suite actually ships - git exports GIT_DIR, GIT_DIR overrides
# `git -C <tmpdir>`, and every one of those fixtures silently operates on the REAL repository.
# Scrubbed HERE rather than at each fixture because the damage came from call sites that passed
# no env= at all: a per-call-site obligation is precisely what failed.
from git_isolation import fingerprint, scrub_environ  # noqa: E402  (path set above)

# [ITEM 7 / REGISTRY CUT 2026-08-28] The gate registry lives in tools/gate_registry.py.
# This import is also the RE-EXPORT contract: tools/check_readme_fresh.py:190 does
# `from run_selftests import AUX_GATES`, and run_selftests_selftest.py imports four of
# these five from here too. An imported name is a module attribute, so both keep working
# unchanged - deliberately, because breaking them would have been a second edit to a
# gate in the same commit that edits the certifying instrument.
#
# NOT re-exported by re-assignment (`AUX_GATES = gate_registry.AUX_GATES`). That spelling
# would leave an ast.Assign named AUX_GATES in this file whose value is an Attribute, so
# the two source-text readers would find the assignment, fail literal_eval, and report
# 'AUX_GATES is not a literal this harness can read' - a WORSE failure than not finding
# it, because it reads like corruption rather than like a move.
from gate_registry import (  # noqa: E402  (path set above)
    AUX_GATES, MACHINE_STATE, NOT_A_GATE, RECORDING_TIERS, SELFTEST_IS_THE_GATE,
)


def recorded_gate_names(src):
    """Gate names in the first argument of a `gate_ledger.record(...)` call, by AST.

    None (never an empty set) when the source will not parse: unparseable must read as FAILURE.
    Every string constant in that argument counts, because `mutation_check.py` legitimately
    writes `record("mutation_sweep_filtered" if args.only else "mutation_sweep", ...)` and a
    contiguous-substring test would call that correct line MISSING.
    """
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "record"
                and isinstance(fn.value, ast.Name) and fn.value.id == "gate_ledger"):
            continue
        if not node.args:
            continue
        for sub in ast.walk(node.args[0]):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                names.add(sub.value)
    return names


def unrecorded_tiers(root: str, tiers=RECORDING_TIERS) -> list:
    """Tiers that no longer call gate_ledger.record() under their declared gate name.

    [SITES-AST 2026-08-24] Was two INDEPENDENT substring tests - `"gate_ledger.record(" in src`
    and `'"<gate>"' in src` - and the full sweep, running for the first time since 2026-08-20,
    caught it: SITES-1 SURVIVED. `check_file_size.py:169` is a DOCSTRING containing
    `gate_ledger.last_run("file_size")`, so the second test was satisfied by PROSE while the real
    call on 178 had been renamed to `"not_file_size"`. The standing rule that a grep guard must
    never search for a literal it also contains, in its sharpest form: this guard's own source
    holds both needles, and `RECORDING_TIERS` above literally holds `"run_selftests"`. Now
    structural - an AST walk cannot be satisfied by a comment, a docstring or a dict key.
    """
    gone = []
    for rel, gate in sorted(tiers.items()):
        path = os.path.join(root, rel)
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
        except OSError:
            gone.append("%s (unreadable - a tier that cannot be read is not a tier that records)"
                        % rel)
            continue
        names = recorded_gate_names(src)
        if names is None:
            gone.append("%s (unparseable - a tier that cannot be read is not a tier that records)"
                        % rel)
        elif gate not in names:
            gone.append("%s (no gate_ledger.record(...) under the name %r; names recorded there: "
                        "%s)" % (rel, gate, sorted(names) or "none"))
    return gone


def enforcing_mode_gaps(root: str, gates=AUX_GATES, adjudicated=SELFTEST_IS_THE_GATE) -> tuple:
    """(unadjudicated, stale_adjudications) for gates registered in --selftest mode.

    DERIVES the mode from the target's source rather than trusting the argv tuple, which is the
    whole point: the tuple is what gets flipped. A row needs an adjudication when all three hold -
    it is registered ("--selftest",), the target defines a `selftest`, and the target's `main` can
    return non-zero. That last clause is what separates a real enforcing mode from a file whose
    non-selftest path only prints (gate_ledger) or cannot fail (score_corpus).

    can-fail is deliberately FAIL-SAFE: a `main` counts as able to fail unless EVERY exit path is
    a literal 0. A first version counted only `return <non-zero literal>` and reported that
    mutation-anchors and install-guard had no failure path at all, which is false - both return a
    variable. A detector that answers "no failure path" for a real gate is this repo's own defect
    class, so the uncertain case must resolve to "needs adjudication", never to "fine".

    Pure and root-parameterised, like missing_gates() above, so the selftest can build trees where
    the answer is known instead of asserting against the live repo only.
    """
    needs = []
    for label, parts, extra in gates:
        path = os.path.join(root, *parts)
        try:
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError):
            # An unreadable/unparseable gate is missing_gates()' and the gate's own problem, not
            # this one's. Never silently treat it as adjudicated.
            continue
        funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        # MEMBERSHIP, via the shared predicate. Exact tuple equality here meant ("--selftest", "")
        # skipped this check entirely while still running the target's selftest - a one-token
        # disarm of the mode control, found by an independent review on 2026-08-19.
        if not is_selftest_argv(extra) or "selftest" not in funcs:
            continue
        if _can_fail(funcs.get("main")):
            needs.append(label)
    return (sorted(set(needs) - set(adjudicated)),
            sorted(set(adjudicated) - set(needs)))


def _can_fail(fn) -> bool:
    """True unless every exit path of `fn` is provably a literal 0. See enforcing_mode_gaps."""
    if fn is None:
        return False
    for node in ast.walk(fn):
        if isinstance(node, ast.Return):
            if node.value is None or (isinstance(node.value, ast.Constant)
                                      and node.value.value in (0, None)):
                continue
            return True
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
            if name in ("exit", "_exit", "SystemExit") and node.args:
                first = node.args[0]
                if not (isinstance(first, ast.Constant) and first.value in (0, None)):
                    return True
    return False


def missing_gates(root: str, gates=AUX_GATES) -> list:
    """Labels of AUX_GATES whose file is not present under `root`.

    Pure and root-parameterised so the selftest can build a tree where gates ARE missing. The
    old code asked `if os.path.exists(...)` inline and skipped in silence, so this question had
    no answer anywhere: a renamed tool removed its gate and the suite still printed all-green.
    """
    return [label for label, parts, _extra in gates
            if not os.path.exists(os.path.join(root, *parts))]


def classify_tools(tools_dir: str, gates=AUX_GATES, not_a_gate=NOT_A_GATE) -> tuple:
    """(unclassified, stale_exempt) for the tools/ directory.

    DETECTION with a floor: a new tool must be declared a gate or explicitly exempted, and an
    exemption naming a file that no longer exists is itself reported - otherwise the exemption
    list rots into cover for whatever gets added next.
    """
    gate_basenames = {parts[-1] for _l, parts, _e in gates if parts[0] == "tools"}
    present = {os.path.basename(p) for p in glob.glob(os.path.join(glob.escape(tools_dir), "*.py"))}
    return (sorted(present - gate_basenames - set(not_a_gate)),
            sorted(set(not_a_gate) - present))


def main():
    failed = []
    skipped = []
    excluded = []
    ran = 0
    # [#45] --code-only answers "is this CODE pushable", which is a different question from
    # "is this MACHINE wired correctly". Both are worth asking; only the first should decide a
    # push. Deliberately NOT the default: a bare run still answers the strictest question.
    code_only = "--code-only" in sys.argv
    hooks_dir = os.path.join(HERE, "hooks")

    # ------------------------------------------------------------------ [#46] repo integrity
    # PREVENTION. Done before a single gate is spawned, so every child inherits a clean
    # environment whether or not it remembers to ask for one.
    stripped = scrub_environ()
    if stripped:
        print(f"-- git isolation: stripped {sorted(stripped)} - a git hook exports these and "
              f"they OVERRIDE `git -C <tmpdir>`, which is how this suite's own fixtures "
              f"committed to the real repository and pushed one to GitHub (#46)")

    # DETECTION, because prevention that nothing checks is an unenforced assertion (#47's shape).
    # Snapshotted here and re-read after EVERY gate: a fixture that escapes is then named, not
    # merely noticed six gates later.
    baseline = fingerprint(HERE)
    if baseline == "FINGERPRINT-UNAVAILABLE":
        # Not a git checkout (a tarball install, say). The control cannot run - so it is
        # reported as a SKIP and counted, never silently omitted. CI must not skip.
        if os.environ.get("CI"):
            print("repo-integrity: FAIL (no git checkout to fingerprint, and CI must not skip)")
            failed.append("repo-integrity")
        else:
            print("repo-integrity: SKIPPED (not a git checkout - fixtures are unwatched here)")
            skipped.append("repo-integrity")
        baseline = None

    def check_repo_integrity(label):
        """Fail if `label` mutated this repository. Re-baselines so only the CULPRIT is blamed.

        Without the re-baseline one runaway fixture would redden every gate that ran after it,
        and a failure list naming 30 innocent gates is one nobody reads to the end.
        """
        nonlocal baseline
        if baseline is None:
            return
        now = fingerprint(HERE)
        if now == baseline:
            return
        print(f"FAIL: repo-integrity - `{label}` CHANGED THIS REPOSITORY. A selftest fixture "
              f"escaped onto the real tree; on 2026-08-24 this same class set core.bare, "
              f"repointed core.hooksPath at a temp directory, and pushed a one-file commit over "
              f"the public default branch.\n       before: {baseline}\n       after:  {now}")
        failed.append(f"repo-integrity:{label}")
        baseline = now

    # The floor turns "a hook with no selftest" into a RED build rather than a silent skip.
    # KNOWN_NO_SELFTEST is empty, so ADDING an untested hook is what breaks the gate.
    violations = floor_violations(hooks_dir)
    for v in violations:
        print(f"FAIL: {v}")
        failed.append(v.split(":")[1].strip().split()[0] if ":" in v else v)

    detected = selftestable_hooks(hooks_dir)
    total = len(all_hook_files(hooks_dir))
    print(f"-- sweeping {len(detected)} of {total} hook files "
          f"({len(KNOWN_NO_SELFTEST)} explicitly exempt)")
    for path in detected:
        name = os.path.splitext(os.path.basename(path))[0]
        ran += 1
        rc = subprocess.run([sys.executable, path, "--selftest"],
                            stdin=subprocess.DEVNULL).returncode
        check_repo_integrity(name)
        if rc == SKIP_RC:
            # A skip is NOT a pass. Under CI it is a failure: the whole point of running on
            # four Pythons x three OSes is that the assertions actually execute there.
            label = "SKIPPED"
            if os.environ.get("CI"):
                print(f"{name}: FAIL (selftest could not run, and CI must not skip)")
                failed.append(name)
                continue
            skipped.append(name)
        else:
            label = "OK" if rc == 0 else "FAIL"
            if rc != 0:
                failed.append(name)
        print(f"{name}: {label}")
    # Auxiliary gates: real checks that are not hook selftests. Each one used to be invoked
    # under a bare `if os.path.exists(...)` with no else, so RENAMING a tool silently deleted
    # its gate - `ran` just got smaller and there was no expected count to compare it against
    # (P13 A3). A missing gate file is now a FAILURE, which is the only reading that cannot be
    # mistaken for "nothing to check".
    for label, parts, extra in AUX_GATES:
        path = os.path.join(HERE, *parts)
        ran += 1
        if not os.path.exists(path):
            print(f"{label}: FAIL (gate file missing: {'/'.join(parts)} - a gate that cannot "
                  f"be found is not a gate that passed)")
            failed.append(label)
            continue
        rc = subprocess.run([sys.executable, path, *extra],
                            stdin=subprocess.DEVNULL).returncode
        check_repo_integrity(label)
        if rc == SKIP_RC:
            # Same contract as the hook selftests above: a skip is not a pass, and CI must
            # never skip - the point of running everywhere is that it actually executes.
            if os.environ.get("CI"):
                print(f"{label}: FAIL (gate could not run, and CI must not skip)")
                failed.append(label)
            else:
                print(f"{label}: SKIPPED")
                skipped.append(label)
            continue
        if rc != 0 and code_only and label in MACHINE_STATE:
            # [#45] It still RAN and it is still printed; only the VERDICT changes.
            print(f"{label}: FAIL (MACHINE-STATE, excluded from the --code-only verdict)")
            excluded.append(label)
            continue
        print(f"{label}: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append(label)

    # DETECTION, not just a list: every tools/*.py must be classified as a gate or explicitly
    # as not-a-gate. Adding a tool therefore forces the decision instead of defaulting to
    # "ungated and nobody noticed" - the same shape as KNOWN_NO_SELFTEST for the hooks.
    unclassified, stale_exempt = classify_tools(os.path.join(HERE, "tools"))
    if unclassified:
        print(f"FAIL: {len(unclassified)} file(s) in tools/ are classified neither as an "
              f"AUX_GATES entry nor in NOT_A_GATE: {unclassified}")
        failed.append("tools-classification")
    if stale_exempt:
        print(f"FAIL: NOT_A_GATE names {len(stale_exempt)} file(s) that no longer exist "
              f"(the exemption is rotting): {stale_exempt}")
        failed.append("tools-classification")

    # [MODE-CONTROL] The argv a gate is registered with, CHECKED rather than trusted. Print the
    # denominator every run: "0 gaps" is only meaningful beside how many rows were examined.
    unadjudicated, stale_adjudications = enforcing_mode_gaps(HERE)
    print(f"-- gate modes: {len(AUX_GATES)} row(s) examined, "
          f"{len(SELFTEST_IS_THE_GATE)} adjudicated as selftest-is-the-gate")
    if unadjudicated:
        print(f"FAIL: {len(unadjudicated)} gate(s) are registered ('--selftest',) but their "
              f"main() can fail - the enforcing mode exists and is NOT being run: "
              f"{unadjudicated}. Either register them enforcing, or add a reason to "
              f"SELFTEST_IS_THE_GATE saying why the selftest IS the gate.")
        failed.append("gate-modes")
    if stale_adjudications:
        print(f"FAIL: SELFTEST_IS_THE_GATE adjudicates {len(stale_adjudications)} row(s) that no "
              f"longer need it (renamed, re-registered, or the target changed): "
              f"{stale_adjudications}. Remove them, or the list rots into cover.")
        failed.append("gate-modes")

    # [RECORD-SITES] A tier that stops recording makes the ship bar read a STALE row instead of
    # no row - silent, and it looks like success. Denominator printed either way.
    unrecorded = unrecorded_tiers(HERE)
    print(f"-- ledger call sites: {len(RECORDING_TIERS)} tier(s) declared, "
          f"{len(RECORDING_TIERS) - len(unrecorded)} still recording")
    if unrecorded:
        print(f"FAIL: {len(unrecorded)} declared tier(s) no longer record to the gate ledger, so "
              f"last_run() would serve a stale result forever: {unrecorded}")
        failed.append("ledger-call-sites")

    # Informational every run, a BLOCKER only at release (--release). Printing it here is the
    # point: "CI green" and "reviewed since it last changed" are different questions, and the
    # second one had no answer at all until this ledger existed.
    fresh = os.path.join(HERE, "tools", "check_review_freshness.py")
    if os.path.exists(fresh):
        subprocess.run([sys.executable, fresh], stdin=subprocess.DEVNULL)

    record_gate_run(ran, failed, skipped, round(_time.perf_counter() - _STARTED, 1))
    # [#45] Printed BEFORE the verdict and unconditionally, so an excluded failure can never be
    # read as a clean run. A denominator that only appears on success is not a denominator.
    if excluded:
        print(f"\n{len(excluded)} MACHINE-STATE gate(s) FAILED and were excluded from this "
              f"verdict by --code-only: {excluded}")
        for lab in excluded:
            print(f"    {lab}: {MACHINE_STATE[lab]}")
        print("  These say something is wrong with THIS MACHINE, not with the code. Fix them, "
              "or run without --code-only to have them block.")
    if failed:
        print(f"\nFAILED ({len(failed)}/{ran}): {failed}")
        return 1
    # Always print the DENOMINATOR. "all 18 selftests passed" was true of whatever happened to
    # be listed, so a shrinking sample never looked wrong.
    note = f" ({len(skipped)} SKIPPED: {skipped})" if skipped else ""
    print(f"\nall {ran} selftests passed{note}")
    return 0


def record_gate_run(ran, failed, skipped=(), seconds=0.0):
    """Append this run to docs/audits/gate_runs.json.

    A gate that did not run leaves no trace in the code or the docs, so "were the gates
    green?" is unanswerable after the fact - you can only re-run and hope nothing changed
    in between. Reviewers then reconstruct it from memory, which is how eight eval
    batteries once went unexecuted while every review reported healthy. This makes the
    process auditable, not just the deliverable.

    Best-effort: never fails the run. An unwritable ledger must not turn a green suite red.
    """
    try:
        # [2026-08-13] Was an inline writer with the gate name HARDCODED here, which is why
        # exactly ONE of five tiers could ever be recorded. Now the shared ledger, which every
        # tier can call and which retains PER GATE - a global cap let this frequent gate evict
        # the record of the 30-minute sweep, i.e. the one whose last-run date actually matters.
        sys.path.insert(0, os.path.join(HERE, "tools"))
        import gate_ledger
        gate_ledger.record("run_selftests", "PASS" if not failed else "FAIL",
                           ran=ran, failed=sorted(failed), skipped=sorted(skipped),
                           seconds=seconds)
    except Exception:
        pass


# [item 7] The selftest lives in run_selftests_selftest.py - see that file's header for the
# three conditions the seam had to satisfy. Imported lazily so an ordinary suite run never pays
# for it, and so a missing sibling fails loudly ON THE SELFTEST PATH instead of taking the
# orchestrator down at import.
def selftest() -> int:
    try:
        from run_selftests_selftest import selftest as _run
    except ImportError as exc:
        print("SELFTEST FAILED: run_selftests_selftest.py could not be imported (%s). The "
              "battery is not optional - a selftest that cannot load is not one that passed."
              % exc)
        return 1
    return _run()


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
