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

# (label, path parts under the repo root, extra argv). A FLOOR: every entry MUST exist and run.
AUX_GATES = (
    # the consistency-audit skill's mechanical extractor - ships in the repo, exposes a
    # --selftest, but lives outside hooks/ so the detection glob above cannot see it
    ("consistency-audit-skill", ("skills", "consistency-audit", "scripts", "audit.py"),
     ("--selftest",)),
    # examples/settings.json is what people copy when wiring by hand; it went stale twice
    ("examples-settings-fresh", ("tools", "regen_example_settings.py"), ("--check",)),
    # [INSTALL-TAUTOLOGY] install.py - the file a user literally RUNS - was a registered gate
    # NOWHERE and exposed no --selftest at all, which is how its partial-checkout guard sat
    # tautological (glob the directory, then assert those same files exist) through every
    # review while its comment called itself DERIVED. 9 of 25 hook files were unguarded, 5 of
    # them imported by production hooks.
    ("install-guard", ("install.py",), ("--selftest",)),
    # [800-LINE RULE] Enforced by NOTHING until 2026-08-14, and the count it was tracked with
    # was wrong: the plan carried a hand-maintained list of offenders that each session added
    # to, and nobody walked the tree - tools/no_regression.py at 805 lines was over the limit
    # and in no list at all. A RATCHET, not a hard fail: red-for-weeks gets disabled.
    # Registered as the MEASUREMENT, not --selftest. Registering the selftest was the first
    # version and it was WORTHLESS: the suite verified that the ratchet LOGIC works and never
    # applied it to the repo, so mutation_check.py grew 1377 -> 1399 with the suite reporting
    # 37/37 while the gate itself, run by hand, said FAIL. A gate wired in a mode that cannot
    # catch anything is this repo's own defect class, committed while building the gate for it.
    # (Contrast false-alarm-scorer, where --selftest IS the gate for a stated reason: its
    # measurement carries a known, adjudicated false alarm and would keep the suite red.)
    ("file-size", ("tools", "check_file_size.py"), ()),
    # [SHIP-BAR] Criterion 2's stopping rule, as a CONTROL rather than prose: no CRITICAL or
    # HIGH may be unbuilt, severities are DERIVED from the review report every run, and the
    # hand-adjudicated state ledger is RECONCILED against it - which is exactly the drift that
    # made "the remaining 8 findings" unverifiable (its list named five items marked BUILT).
    # MEASUREMENT, not --selftest, for the same reason as file-size above and found in the
    # same close ritual: registered as a selftest this verified that the stopping RULE works
    # while never once reading the real findings ledger. A stopping rule that never looks at
    # the findings is not a control, it is a unit test with a gate's name. Its logic stays
    # pinned by SHIPBAR-1..4, whose verify target IS the selftest.
    ("ship-bar", ("tools", "ship_bar_gate.py"), ()),
    # [SHIP-BAR enabler] The gate LEDGER's own retention rule. It recorded 1 of 5 tiers for
    # days, and the fix is not just "let other tiers write" - the cap was GLOBAL, so the
    # cheapest gate would evict the record of the 30-minute sweep as soon as both wrote.
    ("gate-ledger", ("tools", "gate_ledger.py"), ("--selftest",)),
    # [criterion 3] The false-alarm scorer is itself a CHECKING INSTRUMENT, and on 2026-08-12
    # every defect found after the adversarial pass was in an instrument rather than in the
    # product. Its --selftest is the gate. The MEASUREMENT is deliberately NOT the gate: a
    # known, recorded false alarm is a ledger row, and wiring it here would either turn the
    # suite permanently red or create pressure to delete the corpus entry that found it.
    ("false-alarm-scorer", ("tools", "score_false_alarms.py"), ("--selftest",)),
    # the README advertises a Python floor; CI only exercises files it actually runs
    ("python-floor", ("tools", "check_python_floor.py"), ()),
    # a hook can name a skill the repo does not ship (close_skills_guard shipped requiring
    # four while only three were installed); nothing connected those lists until this gate
    ("skill-deps", ("tools", "check_skill_deps.py"), ()),
    # the review-freshness gate's own scope check: it asked about 17 of 31 tracked .py files
    # and could not detect its own sabotage until P13 A1
    ("review-freshness-scope", ("tools", "check_review_freshness.py"), ("--selftest",)),
    # the README pastes a run_selftests transcript as EVIDENCE; it claimed 18 while the suite
    # ran 21. A stale paste reads exactly like a fresh one.
    ("readme-fresh", ("tools", "check_readme_fresh.py"), ()),
    # [P14 D2] Mutation entries pin what a fix ADDS. NOTHING in this repo pinned what a fix
    # TOOK AWAY. A rewrite of capped_report.py went blind to 10 of 14 cap spellings its own
    # predecessor caught while this suite printed 22/22, integration printed 30/30, and 92
    # of 94 mutations reported ALL CAUGHT. Measured at ~0.4s, so it belongs in the per-stop
    # path rather than CI-only.
    ("no-regression", ("tools", "no_regression.py"), ()),
    # [P14 A3] A stale COPY of these hooks ran every `git push` on the author's machine for
    # weeks - unbluff's own pushes included, gated by an outdated fail-open copy of unbluff's
    # own gate - while `git status` here stayed clean, because the copy lived outside the repo.
    # No gate in this repo read git's own wiring (core.hooksPath, .git/hooks), so nothing could
    # see it. This one asks provenance instead of directory-equality, so it keeps working after
    # the duplicate directory is deleted.
    # [MODE-CONTROL 2026-08-16] Was registered ("--selftest",) ALONE, so its enforcing
    # measurement - the half that actually reads git's wiring on this machine - was invoked by
    # nothing: not the suite, not CI, not the push path. An independent review found it; the
    # new enforcing_mode_gaps() control then flagged it on its first run. Both halves are
    # registered now, because they answer different questions: the measurement asks "is anything
    # foreign wired HERE", the selftest asks "could this gate still see an offender at all".
    ("hook-provenance", ("tools", "hook_divergence_report.py"), ()),
    ("hook-provenance-selftest", ("tools", "hook_divergence_report.py"), ("--selftest",)),
    # [P14 M1] A mutation entry finds its target by a literal string, so an unrelated fix that
    # edits that line disarms the mutation SILENTLY - it stays green everywhere except the full
    # ~25-minute sweep, which is CI-only. Measured 2026-08-05: the B3 encoding change broke
    # #20/23's anchor and every filtered run still reported clean. Sub-second, so it belongs
    # here rather than in CI, where the answer arrives a cycle late.
    ("mutation-anchors", ("tools", "check_mutation_anchors.py"), ()),
    # [P14 B1] Was exempted as "measurement, no pass/fail opinion of its own". That reasoning is
    # what let it double-count: it added NEGATIVE_CONTROLS to the negatives already inside
    # ENTRIES and printed "96 + 58 = 154 corpus entries" for a corpus of 125, doubling every
    # false-positive count it reported - in the tool the B1 ship-blocker is graded with.
    # Whether a scorer can count its own corpus IS a pass/fail question, and it is independent
    # of whatever guard is being scored.
    ("corpus-scorer", ("tools", "score_corpus.py"), ("--selftest",)),
)

# tools/*.py deliberately NOT gated here. Every name needs a reason, and the classification
# check below fails if a tool appears in neither list, or if a name here stops existing.
NOT_A_GATE = {
    "mutation_check.py",            # a gate, but minutes-long: CI runs it as its own job
    # [SPLIT 2026-08-16] Pure DATA - the mutation table, moved out of mutation_check.py when it
    # hit 1415 lines against the 800 limit. Not gates: they define no check and expose no
    # dispatch, and mutation_check re-exports their contents as MUTATIONS, so the gate that
    # runs them is the one already classified above.
    "mutation_entries_a.py",
    "mutation_entries_b.py",
    # [ROSTER-GLOB 2026-08-19] Pure DATA plus one predicate - the single definition of "does this
    # argv run the selftest or the measurement?", imported by this file and by mutation_check.
    # Not a gate: it defines no check and exposes no dispatch. The gates that USE it are the ones
    # already classified here.
    "gate_modes.py",
    "compare_delivery_gate.py",     # measurement, produces numbers for the plan
    "measure_dispatcher_cost.py",   # measurement
    # [P14 B1] grades a cap-guard against tests/cap_spelling_corpus.py and prints the
    # denominator. Measurement, not a gate: it scores whatever guard it is pointed at, so it
    # has no pass/fail opinion of its own. Kept in the repo because the C1-NEW rebuild is
    # graded with it and a scorer that lives only in a scratchpad is a measurement nobody can
    # reproduce.
    "make_hook_screenshot.py",      # docs asset generation
}

# [MODE-CONTROL] Labels whose --selftest registration IS the gate, each with the reason.
#
# WHY THIS EXISTS. AUX_GATES' third element is the argv a gate is invoked with, and until now
# NOTHING read it. Registering a gate ("--selftest",) instead of () makes it check its own logic
# and apply to nothing, while the suite, CI, readme-fresh and the mutation sweep all stay green -
# readme-fresh because a mode flip changes no cardinality, and the sweep because every mutation is
# verified via `<unit> --selftest`, which is identical in both modes. That is not hypothetical: it
# happened to file-size and ship-bar on 2026-08-14, was fixed BY HAND in both, and no control was
# built - so on 2026-08-16 an independent review reproduced it in one token on a clean clone,
# planting a 900-line offender and getting `file-size: OK`.
#
# The prose at the AUX_GATES entries above already explained which rows are deliberately
# --selftest. Prose is advisory; only a gate is a control (tooling-discipline 7.3). This dict is
# the same reasoning in a form `enforcing_mode_gaps()` can FAIL on, and it is checked in BOTH
# directions: a row that needs an adjudication and has none is a failure, and an adjudication for
# a row that no longer needs one is a failure too, so the list cannot rot into cover the way an
# exemption list does.
SELFTEST_IS_THE_GATE = {
    "consistency-audit-skill":
        "audit.py's enforcing mode requires --deliverable and --sources; this repo ships no "
        "deliverable to audit, so the selftest is the only runnable form of the gate",
    "install-guard":
        "install.py's enforcing mode INSTALLS into ~/.claude. Running it in the suite would "
        "mutate the developer's machine on every test run, so the guard's selftest is the gate",
    "false-alarm-scorer":
        "the measurement carries a known, adjudicated false alarm (a corpus row). Wiring it "
        "enforcing would either hold the suite permanently red or create pressure to delete the "
        "corpus entry that found it - see the entry comment above",
    "review-freshness-scope":
        "its enforcing mode is --release, which blocks only at a release; the default run is a "
        "measurement. The SCOPE check - does it ask about every tracked file - is the selftest",
    "hook-provenance-selftest":
        "the PAIRED row. Its enforcing form is registered separately as 'hook-provenance' with "
        "argv (), so both halves run; this row exists because the measurement cannot prove the "
        "gate can still SEE an offender on a machine that happens to have none wired",
}


# [RECORD-SITES] Which tiers must leave a row in the gate ledger, and under what gate name.
# The ship bar's verify-before-pushing half reads this ledger, so a tier that stops recording
# makes that gate read a STALE result rather than no result - the failure is silent and looks
# like success. Review wf_f63b9ccf-816 finding #40: deleting the recording from both gates left
# every gate, selftest and anchor check green. Checked in BOTH directions, like NOT_A_GATE.
RECORDING_TIERS = {
    "run_selftests.py": "run_selftests",
    os.path.join("tools", "mutation_check.py"): "mutation_sweep",
    os.path.join("tools", "ship_bar_gate.py"): "ship_bar",
    os.path.join("tools", "check_file_size.py"): "file_size",
    os.path.join("tools", "score_false_alarms.py"): "false_alarm_scorer",
    os.path.join("tests", "test_integration.py"): "integration",
}


def unrecorded_tiers(root: str, tiers=RECORDING_TIERS) -> list:
    """Tiers that no longer call gate_ledger.record() under their declared gate name.

    Textual on purpose: the question is whether the CALL SITE still exists in the source, and an
    import-and-execute would run the tier. A tier whose recording is deleted still passes every
    other check in this repo, which is exactly why this one is cheap and textual.
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
        if "gate_ledger.record(" not in src or '"%s"' % gate not in src:
            gone.append("%s (no gate_ledger.record(...) under the name %r)" % (rel, gate))
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
    ran = 0
    hooks_dir = os.path.join(HERE, "hooks")

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


def selftest() -> int:
    """[P13 A3] HERMETIC checks for the two decisions that used to have no answer at all."""
    import tempfile
    fails = []

    # 1. a gate whose file is absent must be REPORTED, never skipped. An empty tree is the
    #    strongest form of "every tool was renamed", so every label must come back.
    with tempfile.TemporaryDirectory() as empty:
        got = missing_gates(empty)
        want = [label for label, _p, _e in AUX_GATES]
        if sorted(got) != sorted(want):
            fails.append("missing_gates() on an empty tree reported %r, expected all %d gate "
                         "labels %r - a gate file that is gone must not read as a pass"
                         % (got, len(want), want))
    # ...and the real tree must have none missing, or the suite is lying right now.
    live_missing = missing_gates(HERE)
    if live_missing:
        fails.append("AUX_GATES names %d gate(s) that do not exist in this repo: %r"
                     % (len(live_missing), live_missing))

    # 2. a tools/ file that is neither a gate nor exempt must be reported, and an exemption
    #    naming a vanished file must be reported too.
    with tempfile.TemporaryDirectory() as td:
        tools = os.path.join(td, "tools")
        os.makedirs(tools)
        for name in ("check_python_floor.py", "brand_new_tool.py"):
            with open(os.path.join(tools, name), "w", encoding="utf-8") as f:
                f.write("x = 1\n")
        unclassified, stale = classify_tools(tools, not_a_gate={"deleted_tool.py"})
        if unclassified != ["brand_new_tool.py"]:
            fails.append("classify_tools() did not flag an undeclared tool: %r" % (unclassified,))
        if stale != ["deleted_tool.py"]:
            fails.append("classify_tools() did not flag an exemption for a file that no longer "
                         "exists: %r" % (stale,))

    # 3. [MODE-CONTROL] the argv check itself. Asserted on a SYNTHETIC tree, so the assertion
    #    states what the rule is rather than restating whatever the live table happens to say -
    #    a golden that round-trips the current registration would pin nothing.
    with tempfile.TemporaryDirectory() as td:
        enforcing = os.path.join(td, "enforcing_gate.py")
        with open(enforcing, "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0\n\n\ndef main():\n    if 1:\n"
                    "        return 1\n    return 0\n")
        printer = os.path.join(td, "printer.py")           # gate_ledger's shape: no main() at all
        with open(printer, "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0\n")
        harmless = os.path.join(td, "harmless.py")         # a main() that cannot fail
        with open(harmless, "w", encoding="utf-8") as f:
            f.write("def selftest():\n    return 0\n\n\ndef main():\n    return 0\n")

        rows = (("enforcing", ("enforcing_gate.py",), ("--selftest",)),
                ("printer", ("printer.py",), ("--selftest",)),
                ("harmless", ("harmless.py",), ("--selftest",)))
        gaps, stale_adj = enforcing_mode_gaps(td, gates=rows, adjudicated={})
        if gaps != ["enforcing"]:
            fails.append("enforcing_mode_gaps() flagged %r, expected exactly ['enforcing'] - a "
                         "gate registered --selftest whose main() CAN fail is the 2026-08-14 "
                         "defect, and a printer or a can't-fail main is not" % (gaps,))
        if stale_adj:
            fails.append("enforcing_mode_gaps() invented a stale adjudication: %r" % (stale_adj,))

        # an adjudication silences it, and an adjudication for a row that does not need one is
        # itself reported - the exemption must not be able to rot
        gaps2, stale2 = enforcing_mode_gaps(td, gates=rows,
                                            adjudicated={"enforcing": "reason", "ghost": "gone"})
        if gaps2 != []:
            fails.append("an explicit adjudication did not silence the gap: %r" % (gaps2,))
        if stale2 != ["ghost"]:
            fails.append("a stale adjudication was not reported: %r" % (stale2,))

        # [ROSTER-GLOB 2026-08-19] THE SELFTEST-SHAPED-BUT-NOT-EQUAL ROW. Every fixture above
        # uses exactly ("--selftest",), so a detector written with `!= ("--selftest",)` and one
        # written with `"--selftest" in extra` agree on all of them - the cases could not tell the
        # two spellings apart, which is why the disarm survived until an independent review. The
        # target dispatches on MEMBERSHIP (`"--selftest" in sys.argv`), so this row runs the
        # selftest and must be adjudicated exactly like the plain one.
        for shape in (("--selftest", ""), ("--selftest", "-v"), ("-v", "--selftest")):
            padded = (("enforcing", ("enforcing_gate.py",), shape),)
            if enforcing_mode_gaps(td, gates=padded, adjudicated={})[0] != ["enforcing"]:
                fails.append("a registration of %r was not treated as running the SELFTEST. The "
                             "target dispatches on membership, so this row runs its selftest "
                             "while the gate's real measurement is invoked by nothing - a "
                             "one-token disarm of this very control" % (shape,))

        # THE MUTATION THIS EXISTS TO CATCH: flipping an ENFORCING row to --selftest must be
        # detected. This is the one-token edit that reproduced on a clean clone.
        flipped = (("enforcing", ("enforcing_gate.py",), ()),)
        if enforcing_mode_gaps(td, gates=flipped, adjudicated={})[0]:
            fails.append("an enforcing registration was reported as a gap - false positive")
        flipped_back = (("enforcing", ("enforcing_gate.py",), ("--selftest",)),)
        if enforcing_mode_gaps(td, gates=flipped_back, adjudicated={})[0] != ["enforcing"]:
            fails.append("flipping () -> ('--selftest',) went UNDETECTED, which is exactly the "
                         "one-token disarm this control exists to stop")

    # 4. [RECORD-SITES] the rule on a synthetic tree, then the live one. A tier whose recording
    #    is deleted keeps passing every other check in this repo, so this assertion is the only
    #    thing standing between "the ship bar reads a fresh row" and "it reads a stale one".
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "good.py")
        with open(good, "w", encoding="utf-8") as f:
            f.write('gate_ledger.record("mine", "PASS")\n')
        silent = os.path.join(td, "silent.py")
        with open(silent, "w", encoding="utf-8") as f:
            f.write('print("I am a tier that forgot to record")\n')
        wrong = os.path.join(td, "wrong.py")
        with open(wrong, "w", encoding="utf-8") as f:
            f.write('gate_ledger.record("somebody_elses_name", "PASS")\n')
        got = unrecorded_tiers(td, tiers={"good.py": "mine", "silent.py": "mine",
                                          "wrong.py": "mine", "absent.py": "mine"})
        flagged = sorted(g.split(" ")[0] for g in got)
        if flagged != ["absent.py", "silent.py", "wrong.py"]:
            fails.append("unrecorded_tiers() flagged %r; a tier that records under ANOTHER "
                         "gate's name, one that records nothing, and one that cannot be read "
                         "must all be reported, and a correct one must not" % (flagged,))

    live_unrecorded = unrecorded_tiers(HERE)
    if live_unrecorded:
        fails.append("%d declared tier(s) no longer record to the gate ledger: %r"
                     % (len(live_unrecorded), live_unrecorded))

    # ...and the live table must be clean right now, or the suite is lying about itself.
    live_gaps, live_stale = enforcing_mode_gaps(HERE)
    if live_gaps:
        fails.append("live AUX_GATES has %d unadjudicated --selftest registration(s): %r"
                     % (len(live_gaps), live_gaps))
    if live_stale:
        fails.append("live SELFTEST_IS_THE_GATE has %d stale adjudication(s): %r"
                     % (len(live_stale), live_stale))

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
