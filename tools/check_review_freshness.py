#!/usr/bin/env python3
"""Release gate: has every unit been adversarially reviewed SINCE it last changed?

v1.3.0 shipped CI-green and was declared closeable twice; an adversarial review then found 34
confirmed defects in it. The lesson - "CI green means the tests pass, not that they ask the
right questions" - lived only as a sentence in a handoff doc. A sentence is an instance fix.
This is the mechanism: `docs/audits/review_runs.json` records each review the way
`gate_runs.json` records selftest runs, and this reads it back.

DETECTION, not a roster: the unit list comes from the repo (hooks/*.py plus the top-level
entry points), never from the ledger. A ledger-driven list would silently stop asking about
any file nobody remembered to add - the exact failure that put two hardcoded rosters in this
release. A unit absent from the ledger is UNREVIEWED and reported, not skipped.

    python tools/check_review_freshness.py            # report; exit 0 unless --release
    python tools/check_review_freshness.py --release  # exit 1 if anything is stale/unreviewed
    python tools/check_review_freshness.py --record --unit hooks/x.py --run-id wf_... \\
        --lenses a,b --confirmed 3
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "docs", "audits", "review_runs.json")


# Tracked .py files deliberately NOT expected to carry an adversarial review. A FLOOR, not a
# filter: every entry needs a reason, and _selftest_scope prints the list so it cannot grow in
# silence. Empty is the correct state - if it stops being empty, that is a decision someone
# made on purpose.
EXEMPT: frozenset = frozenset()


def _tracked(repo: str = REPO) -> set | None:
    """Repo-tracked .py paths, or None when git cannot answer.

    None is a THIRD state, not an empty set - the same contract dirty_units() and last_change()
    already carry. An empty set would read as "the repo contains no Python", which is a passing
    answer to a question that was never asked.
    """
    try:
        r = subprocess.run(["git", "-C", repo, "ls-files", "-z", "--", "*.py"],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return {x.replace("\\", "/") for x in (r.stdout or "").split("\0") if x}


# Where reviewable Python lives. Widened from hooks/ + the two entry points, which asked about
# 17 of 31 tracked .py files and silently exempted the ENTIRE evidence base: tools/ (the gates
# and this very file), tests/, and the skill scripts install.py ships to the user's machine.
# The gate could not detect its own sabotage - proved by committing `def backdoor(): return 42`
# into tools/mutation_check.py with --release still exiting 0 (P13 A1).
UNIT_GLOBS = ("hooks/*.py", "tools/*.py", "tests/*.py", "scripts/*.py",
              "skills/*/scripts/*.py", "install.py", "run_selftests.py")


def units(repo: str = REPO) -> list:
    """Every unit a review is expected to cover, derived from the repo.

    Glob first, then intersect with `git ls-files` so untracked scratch files are not demanded.
    When git cannot answer, the glob SUPERSET stands rather than the empty set: over-asking is
    a noisy gate, under-asking is a false all-clear, and this module's own contract is that an
    unanswerable question is not a passing one.

    `repo` is a parameter so the selftest can BUILD the repo it needs. Reading the ambient tree
    made the check pass vacuously in any scratch copy - which is how the first version of this
    fix's own mutation came back SURVIVED.
    """
    found = set()
    for pattern in UNIT_GLOBS:
        for p in glob.glob(os.path.join(repo, *pattern.split("/"))):
            if os.path.isfile(p):
                found.add(os.path.relpath(p, repo).replace("\\", "/"))
    tracked = _tracked(repo)
    if tracked is not None:
        found &= tracked
    return sorted(found)


def load_ledger() -> list:
    try:
        with open(LEDGER, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def last_change(unit: str) -> str | None:
    """ISO date of the newest commit touching this unit, or None if git cannot say."""
    try:
        r = subprocess.run(["git", "-C", REPO, "log", "-1", "--format=%cI", "--", unit],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return (r.stdout or "").strip() or None


def _parse(ts: str):
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def dirty_units(unit_list: list) -> set:
    """Units with UNCOMMITTED changes in the working tree.

    last_change() reads commit history only, but --record stamps now() against the WORKING
    TREE the reviewer just read, and run_selftests invokes this on every gate run - i.e. mid
    development, with a dirty tree. Without this, appending `def backdoor(): return 42` to a
    reviewed hook leaves the gate printing "all units have an adversarial review newer than
    their last change" and exiting 0. Not solved by swapping in mtimes: the prescribed
    review -> record -> commit order would then flip every just-reviewed unit to STALE.
    """
    try:
        r = subprocess.run(["git", "-C", REPO, "status", "--porcelain", "-z", "--"] + unit_list,
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="surrogateescape")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    out = set()
    fields = (r.stdout or "").split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            i += 1
        out.add(path.replace("\\", "/"))
    return out


def evaluate() -> tuple[list, list, list, list]:
    """(stale, unreviewed, unknown, fresh) - each a list of (unit, detail) tuples.

    `unknown` is its own bucket because an unanswerable freshness question is not a passing
    one. Folding it into `fresh` made the release gate exit 0 having asked git nothing -
    reproduced with `git archive HEAD` into a scratch dir (the sdist / exported-release-tree
    case), where all 8 correctly-STALE units flipped to FRESH. That is the very contract this
    same fix round wrote into pre_push_gate.newest_source_mtime, broken in the tool built to
    enforce the lesson.
    """
    ledger = load_ledger()
    newest: dict = {}
    for entry in ledger:
        if not isinstance(entry, dict):
            continue
        unit, when = entry.get("unit"), _parse(entry.get("utc"))
        if not unit or when is None:
            continue
        if unit not in newest or when > newest[unit][0]:
            newest[unit] = (when, entry)

    all_units = units()
    # [HIGH-7] `dirty_units` returns None when git could not answer - NOT an empty set. The
    # empty set meant "nothing is dirty", identical to a clean tree, so --release exited 0
    # over uncommitted changes wherever git failed. Its twin `last_change()` was given exactly
    # this third state; this one was not. An unanswerable question is not a passing one.
    dirty = dirty_units(all_units)
    dirty_unknown = dirty is None
    if dirty_unknown:
        dirty = set()
    stale, unreviewed, unknown, fresh = [], [], [], []
    for unit in all_units:
        if unit not in newest:
            unreviewed.append((unit, "never adversarially reviewed"))
            continue
        reviewed_at, entry = newest[unit]
        raw = last_change(unit)
        changed = _parse(raw or "")
        if dirty_unknown:
            unknown.append((unit, "git could not report whether the working tree is dirty"))
        elif raw is None:
            unknown.append((unit, "git could not answer when this last changed "
                                  "(not a checkout, or git unavailable)"))
        elif changed is None:
            unknown.append((unit, f"git returned an unparseable date: {raw!r}"))
        elif unit in dirty:
            stale.append((unit, f"UNCOMMITTED changes in the working tree since the "
                                f"{reviewed_at.date()} review (run {entry.get('run_id', '?')})"))
        elif changed > reviewed_at:
            stale.append((unit, f"changed {changed.date()} but last reviewed "
                                f"{reviewed_at.date()} (run {entry.get('run_id', '?')})"))
        else:
            fresh.append((unit, f"reviewed {reviewed_at.date()}, unchanged since"))
    return stale, unreviewed, unknown, fresh


def record(args) -> int:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    history = load_ledger()
    stamp = args.utc or datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat()
    for unit in [u.strip().replace("\\", "/") for u in args.unit.split(",") if u.strip()]:
        history.append({
            "unit": unit,
            "run_id": args.run_id,
            "lenses": [x.strip() for x in (args.lenses or "").split(",") if x.strip()],
            "agents": args.agents,
            "findings": args.findings,
            "confirmed": args.confirmed,
            "utc": stamp,
        })
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(history[-500:], f, indent=2)
        f.write("\n")
    print(f"recorded {args.run_id} for {args.unit} at {stamp}")
    return 0


SKIP_RC = 77   # the suite's convention: "could not run", which is NOT a pass


def _scope_failures(repo: str, ledger: list, strict: bool = False) -> list:
    """[P13 A1] The gate must ask about every unit the repo actually has.

    Two independent invariants, neither satisfiable by a roster:

    1. ORPHAN CHECK - closes the loop between --record and units(). A review recorded for a
       unit the gate never asks about is a silent no-op: it prints "recorded", writes the
       ledger, and changes nothing. Three such orphans existed in the real ledger
       (tools/mutation_check.py, tools/check_review_freshness.py, tests/test_integration.py)
       while --release cheerfully exited 0.

    2. DENOMINATOR CHECK - scope derived from `git ls-files`, i.e. from the REPO rather than
       from this module's own globs, so it is not circular: widening the repo without widening
       UNIT_GLOBS fails here. EXEMPT is a floor, never a filter.

    Both take `repo`/`ledger` as arguments so the caller can build a fixture. The first draft
    read the ambient tree and its own mutation came back SURVIVED, because in a scratch copy
    there is no .git and no ledger, so every assertion was vacuous.
    """
    fails = []
    asked = set(units(repo))
    recorded = {e.get("unit") for e in ledger if isinstance(e, dict) and e.get("unit")}
    orphans = sorted(recorded - asked)
    if orphans:
        fails.append("reviews are recorded for %d unit(s) the gate never asks about, so "
                     "--record for them is a silent no-op: %s"
                     % (len(orphans), ", ".join(orphans)))
    tracked = _tracked(repo)
    if tracked is None:
        # Only the FIXTURE may treat this as a failure: there git was just used successfully,
        # so None means the code is broken. For the ambient repo - which is a plain temp dir
        # whenever the mutation harness copies the tree - it means "not a checkout here", and
        # the fixture has already asserted the logic. Say so; never pass in silence.
        if strict:
            fails.append("git could not list tracked files for the fixture repo")
        else:
            print("[review-freshness selftest] ambient scope check SKIPPED: %s is not a git "
                  "checkout (the hermetic fixture above is what asserts the logic)" % repo)
        return fails
    missing = sorted(p for p in tracked if p not in asked and p not in EXEMPT)
    if missing:
        fails.append("%d tracked .py file(s) are in the repo but the gate never asks whether "
                     "they were reviewed: %s" % (len(missing), ", ".join(missing)))
    return fails


def _selftest_fixture() -> list:
    """HERMETIC: build a repo whose shape is known, instead of reading the ambient one.

    The fixture puts a .py file in every directory UNIT_GLOBS is supposed to cover, plus an
    UNTRACKED one that must NOT be demanded, plus a ledger naming a unit outside the scope.
    Narrowing UNIT_GLOBS therefore fails here on any machine, in any directory.
    """
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as repo:
        def _git(*a):
            return subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True,
                                  timeout=60, stdin=subprocess.DEVNULL)
        try:
            if _git("init", "-q").returncode != 0:
                return [SKIP_RC]
        except (OSError, subprocess.SubprocessError):
            return [SKIP_RC]
        _git("config", "user.email", "t@t")
        _git("config", "user.name", "t")
        planted = ["hooks/h.py", "tools/t.py", "tests/test_x.py", "scripts/s.py",
                   "skills/demo/scripts/a.py", "install.py", "run_selftests.py"]
        for rel in planted:
            path = os.path.join(repo, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
        with open(os.path.join(repo, "untracked_scratch.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")     # never `git add`ed - must NOT be demanded
        _git("add", "-A")
        if _git("commit", "-q", "-m", "fixture").returncode != 0:
            return [SKIP_RC]

        asked = set(units(repo))
        for rel in planted:
            if rel not in asked:
                fails.append("units() does not ask about %s - a whole directory of the repo is "
                             "exempt from review with no one saying so" % rel)
        if "untracked_scratch.py" in asked:
            fails.append("units() demands a review of an UNTRACKED file")
        # the orphan invariant, against a ledger this test controls
        ledger = [{"unit": "tools/t.py", "utc": "2026-01-01T00:00:00+00:00"},
                  {"unit": "nowhere/ghost.py", "utc": "2026-01-01T00:00:00+00:00"}]
        got = _scope_failures(repo, ledger, strict=True)
        if not any("ghost.py" in g for g in got):
            fails.append("a review recorded for a unit outside the gate's scope was NOT "
                         "reported as an orphan: %r" % (got,))
        if any("tools/t.py" in g for g in got):
            fails.append("an in-scope recorded unit was wrongly called an orphan: %r" % (got,))

        # The THIRD STATE. A path git cannot even enter must yield None, not an empty set:
        # empty reads as "this repo contains no Python", which is a passing answer to a
        # question that was never asked, and it would make units() return the glob's full
        # superset intersected with nothing. Non-existent path, so it can never accidentally
        # BE a checkout (a temp dir could be, if TEMP sat inside one).
        if _tracked(os.path.join(repo, "no_such_dir_here")) is not None:
            fails.append("_tracked() returned a set for a path git cannot read - 'git could "
                         "not answer' is being reported as 'there is nothing to review'")
    return fails


def selftest() -> int:
    fixture = _selftest_fixture()
    if fixture == [SKIP_RC]:
        print("SELFTEST SKIP: git unavailable, scope cases untested")
        return SKIP_RC
    # The ambient repo is checked too - it is the one that actually ships - but the fixture
    # above is what makes the assertion hold in a scratch tree.
    fails = fixture + _scope_failures(REPO, load_ledger())
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--release", action="store_true",
                    help="exit 1 when any unit is stale or unreviewed")
    ap.add_argument("--record", action="store_true", help="append a review run to the ledger")
    ap.add_argument("--unit", default="", help="comma-separated repo-relative paths")
    ap.add_argument("--run-id", default="", help="the Workflow run id")
    ap.add_argument("--lenses", default="")
    ap.add_argument("--agents", type=int, default=0)
    ap.add_argument("--findings", type=int, default=0)
    ap.add_argument("--confirmed", type=int, default=0)
    ap.add_argument("--utc", default="", help="override the timestamp (tests)")
    args = ap.parse_args()

    if args.record:
        if not args.unit or not args.run_id:
            sys.exit("ERROR: --record needs --unit and --run-id")
        return record(args)

    stale, unreviewed, unknown, fresh = evaluate()
    total = len(stale) + len(unreviewed) + len(unknown) + len(fresh)
    # Always print the DENOMINATOR: "0 stale" is meaningless without knowing how many were asked.
    print(f"[review-freshness] {len(fresh)}/{total} units reviewed since their last change")
    for unit, why in stale:
        print(f"  STALE:      {unit} - {why}")
    for unit, why in unreviewed:
        print(f"  UNREVIEWED: {unit} - {why}")
    for unit, why in unknown:
        print(f"  UNKNOWN:    {unit} - {why}")
    if not stale and not unreviewed and not unknown:
        print("  all units have an adversarial review newer than their last change")
    if args.release and (stale or unreviewed or unknown):
        print(f"\nRELEASE BLOCKED: {len(stale)} stale, {len(unreviewed)} unreviewed, "
              f"{len(unknown)} unknown.")
        print("An unanswerable freshness question is not a passing one.")
        print("Run the adversarial-review skill over them, then record it with --record.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
