#!/usr/bin/env python3
"""The 800-line rule, DERIVED. Enforced by nothing until 2026-08-14.

The project's coding rule is 200-400 lines typical, 800 maximum. It was enforced by nobody, so
it degraded monotonically while every individual addition looked justified - three files on
2026-08-12, five by the close, six on 08-13.

WHY THIS EXISTS RATHER THAN A LIST IN THE PLAN. The count itself was WRONG, and wrong in the
direction that flatters: the plan carried a hand-maintained list of the offenders, each session
added the file it had just pushed over, and nobody ever walked the tree. `tools/no_regression.py`
at 805 lines was over the limit and appeared in NO list - it was found on 2026-08-14 by deriving
the set for the first time, while writing a report that repeated the hand-list's number.
A DECLARED ROSTER standing in for a DERIVED one is this repo's most-repeated defect
(INSTALL-TAUTOLOGY, ENTRY-GUARD, ROSTER-DERIVE, _SH_SITES_REQUIRED, and now this).

WHY IT DOES NOT SIMPLY FAIL. Failing today would make the suite permanently red on seven
known files, and a gate that is red for weeks gets ignored or disabled - the same disease as a
guard that fires on correct code. So it is a RATCHET: the current offenders are recorded with
their sizes, and the gate fails when a file NEWLY crosses 800, or when a recorded offender
GROWS. Shrinking one below its recorded size tightens the ratchet automatically; getting it
under 800 removes it. The debt is visible, bounded, and can only go down.
"""

import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(REPO, "docs", "audits", "file_size_baseline.json")
LIMIT = 800
SKIP_DIRS = (".git", "__pycache__", "node_modules", ".venv", "venv")

# [2026-08-16] Was `import gate_ledger` inside main()'s try/except, which resolved ONLY because
# `python tools/check_file_size.py` happens to put tools/ at sys.path[0]. Under `python -m` or
# any in-process import from another cwd it raised, the blanket except swallowed it, and the
# gate passed, exited 0 and recorded NOTHING - a tier silently missing from the ledger that a
# ship bar reads. Import once, at module scope, with the path set explicitly, and SAY SO when it
# fails instead of treating "could not record" as indistinguishable from "recorded".
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import gate_ledger
except ImportError as _e:                          # narrow: only the import, not the recording
    gate_ledger = None
    print("[file-size] NOTE: gate_ledger unavailable (%s) - this run will not be recorded" % _e)


def line_count(path: str) -> int:
    with io.open(path, encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def population(root: str = REPO) -> tuple:
    """(relpaths, source) for the .py files this gate judges. DERIVED, and it says HOW.

    [2026-08-16] The file list was derived by walking while the EXCLUSION list was declared
    (SKIP_DIRS), in the very file whose docstring calls a second roster this repo's most-repeated
    defect. Any virtualenv not spelled exactly ".venv" or "venv" - "env", ".env", "venv311" - put
    thousands of vendored library files into the population and false-failed the gate. Version
    control already knows what is ours, so ask it; the walk stays as a FALLBACK and the caller
    prints which one was used, because a silent fallback is how a derivation quietly stops being
    one.
    """
    try:
        out = subprocess.run(["git", "ls-files", "--", "*.py"], cwd=root, capture_output=True,
                             text=True, timeout=60)
        if out.returncode == 0 and out.stdout.strip():
            rels = [ln.strip().replace(os.sep, "/") for ln in out.stdout.splitlines()
                    if ln.strip()]
            return [r for r in rels if os.path.isfile(os.path.join(root, r))], "git"
    except (OSError, subprocess.SubprocessError):
        pass
    rels = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                full = os.path.join(dirpath, name)
                rels.append(os.path.relpath(full, root).replace(os.sep, "/"))
    return rels, "walk"


def measure(root: str = REPO) -> dict:
    """{relpath: lines}. Kept for callers that do not care which source the population came from."""
    return measure_with_source(root)[0]


def measure_with_source(root: str = REPO) -> tuple:
    rels, source = population(root)
    return {rel: line_count(os.path.join(root, rel)) for rel in rels}, source


def load_baseline(path: str = BASELINE) -> dict:
    """The recorded offenders only. Prefer read_baseline() - this cannot report WHY it is empty."""
    return read_baseline(path)[0]


def read_baseline(path: str = BASELINE) -> tuple:
    """(over_limit, status) where status is 'ok' | 'absent' | 'unreadable'.

    [2026-08-16] The previous version mapped BOTH failures to `{}`, which does not mean "no
    recorded offenders" - it means every recorded offender is now unrecorded, so all seven of
    them are reported as NEW offenders and the gate fails with seven substantive-looking
    findings. "I could not read the baseline" and "there are no offenders" must not be the same
    value; review wf_f63b9ccf-816 raised this twice (findings #25 and #30) from two lenses.
    """
    try:
        with io.open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}, "absent"
    except OSError:
        return {}, "unreadable"
    except ValueError:
        return {}, "unreadable"
    over = doc.get("over_limit") if isinstance(doc, dict) else None
    if not isinstance(over, dict):
        return {}, "unreadable"
    return over, "ok"


def stale_baseline(sizes: dict, baseline: dict, limit: int = LIMIT) -> list:
    """Baseline entries that are no longer over the limit, or no longer exist at all.

    THE REVERSE WALK (finding #19). verdict() only ever inspects files that are CURRENTLY over
    the limit, so an entry that drops below it - or whose file is deleted - simply vanishes from
    the report while still inflating the recorded count. Observed live on 2026-08-16: after
    mutation_check.py was split, the gate printed "7 recorded offender(s)" and listed 6, with no
    SHRANK line and nothing flagged.
    """
    out = []
    for rel in sorted(baseline):
        if rel not in sizes:
            out.append((rel, "no longer exists"))
        elif sizes[rel] <= limit:
            out.append((rel, "is now %d lines, at or under the %d limit" % (sizes[rel], limit)))
    return out


def verdict(sizes: dict, baseline: dict, limit: int = LIMIT):
    """(new_offenders, grown, shrunk, still_over) - the ratchet, as a pure function.

    Pure so the rule can be asserted without writing files, and so a mutation reaches the same
    code the probe does.
    """
    new_offenders, grown, shrunk, still_over = [], [], [], []
    for rel, n in sorted(sizes.items()):
        if n <= limit:
            continue
        if rel not in baseline:
            new_offenders.append((rel, n))
        else:
            was = baseline[rel]
            still_over.append((rel, n, was))
            if n > was:
                grown.append((rel, n, was))
            elif n < was:
                shrunk.append((rel, n, was))
    return new_offenders, grown, shrunk, still_over


def main() -> int:
    sizes, source = measure_with_source()
    baseline, status = read_baseline()

    # "I could not look" is not "there is nothing to see". Without this, an unreadable baseline
    # reported all seven recorded offenders as NEW ones - seven substantive-looking failures
    # produced by a read error.
    if status == "unreadable":
        print("file-size: CANNOT RUN - the baseline at %s exists but could not be read or "
              "parsed. Every recorded offender would be reported as NEW, so no per-file verdict "
              "is given at all." % BASELINE)
        return 1

    # A FLOOR on the denominator, in main() rather than only in selftest(). Without it a walk
    # that silently narrowed - a bad glob, a cwd change, a git failure - would report "0 .py
    # file(s), no new offender" and PASS. The bound is deliberately loose; it exists to catch
    # collapse, not drift.
    if len(sizes) < 20:
        print("file-size: CANNOT RUN - only %d .py file(s) in the population (source: %s). A "
              "gate that examined almost nothing must not report OK." % (len(sizes), source))
        return 1

    new_offenders, grown, shrunk, still_over = verdict(sizes, baseline)
    stale = stale_baseline(sizes, baseline)

    print("file-size: %d .py file(s) in population (source: %s), limit %d, %d recorded "
          "offender(s)%s" % (len(sizes), source, LIMIT, len(baseline),
                             "" if status == "ok" else " [baseline %s]" % status))
    for rel, n, was in sorted(still_over, key=lambda t: -t[1]):
        mark = "GREW" if n > was else ("shrunk" if n < was else "same")
        print("  %-46s %5d  (baseline %d, %s)" % (rel, n, was, mark))
    for rel, n in new_offenders:
        print("file-size FAIL: %s is %d lines, over the %d limit and in no baseline - a NEW "
              "offender. Split it, or record it deliberately." % (rel, n, LIMIT))
    for rel, n, was in grown:
        print("file-size FAIL: %s grew %d -> %d, and it was ALREADY over the limit. The "
              "ratchet only turns one way." % (rel, was, n))
    if shrunk:
        print("file-size: %d recorded offender(s) SHRANK - re-record to tighten the ratchet: %s"
              % (len(shrunk), ", ".join("%s %d->%d" % (r, w, n) for r, n, w in shrunk)))
    # THE REVERSE WALK. A baseline entry that no longer qualifies used to vanish from the report
    # while still inflating the recorded count, so the printed denominator disagreed with the
    # printed list and nothing said why.
    for rel, why in stale:
        print("file-size: STALE baseline entry - %s %s. Remove it, or the recorded count "
              "overstates the debt and the ratchet has slack it never earned." % (rel, why))
    # RECORD ON EVERY EXIT PATH, with the REAL verdict. The record call used to sit below the
    # failure return with the result hardcoded "PASS", so this gate could not appear red in the
    # ledger at all: a failing run wrote nothing and last_run() kept returning the previous
    # PASS. Any ship bar built on that ledger reads a stale green. Found by review
    # wf_f63b9ccf-816 as two findings (#4, #15) against the two gates that shared the shape.
    failing = bool(new_offenders or grown)
    if gate_ledger is not None:
        gate_ledger.record("file_size", "FAIL" if failing else "PASS", walked=len(sizes),
                           over_limit=len(still_over), new=len(new_offenders),
                           grown=len(grown), shrunk=len(shrunk))
    if failing:
        print("file-size: FAIL")
        return 1
    print("file-size: OK - no new offender, none grew")
    return 0


def selftest() -> int:
    fails = []
    # the RATCHET, both directions, through the real decision function
    base = {"a.py": 900}
    new, grown, shrunk, still = verdict({"a.py": 900, "b.py": 100}, base)
    if new or grown:
        fails.append("a recorded offender at its recorded size was reported as a regression")
    new, grown, _s, _o = verdict({"a.py": 901}, base)
    if not grown:
        fails.append("a recorded offender that GREW was accepted - the ratchet must only turn "
                     "one way, or the debt rises while the gate stays green")
    new, grown, _s, _o = verdict({"c.py": 801}, base)
    if not new:
        fails.append("a NEW file over the limit was accepted - which is exactly how "
                     "no_regression.py reached 805 lines while appearing in no list")
    if verdict({"c.py": 800}, base)[0]:
        fails.append("a file exactly AT the limit was flagged; the rule is 800 maximum")
    _n, _g, shrunk, _o = verdict({"a.py": 850}, base)
    if not shrunk:
        fails.append("a recorded offender that shrank was not reported, so the ratchet can "
                     "never be tightened")

    # measure() must DERIVE, and must actually find this repo's files
    sizes = measure()
    if len(sizes) < 20:
        fails.append("measure() walked only %d .py file(s) - it is not seeing the tree" %
                     len(sizes))
    if "tools/check_file_size.py" not in sizes:
        fails.append("measure() did not find this file; the walk is not rooted at the repo")
    if any("__pycache__" in k for k in sizes):
        fails.append("measure() descended into __pycache__ and would count generated files")

    # [2026-08-16] An INDEPENDENT expectation for line_count, not a round-trip of itself. The
    # golden compared measure() against measure()'s own implementation, so `return 0` left the
    # selftest AND the gate green with a healthy-looking denominator (finding #33).
    _probe = os.path.abspath(__file__)
    with open(_probe, "rb") as _fh:
        _raw = _fh.read()
    _independent = _raw.count(b"\n") + (0 if _raw.endswith(b"\n") else 1)
    if line_count(_probe) != _independent:
        fails.append("line_count() says %d for this file and a raw byte-level newline count "
                     "says %d - the golden must not be the implementation's own output"
                     % (line_count(_probe), _independent))

    # tri-state baseline: 'unreadable' must never look like 'no recorded offenders'
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        bad = os.path.join(td, "corrupt.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        if read_baseline(bad) != ({}, "unreadable"):
            fails.append("a corrupt baseline did not read as 'unreadable': %r"
                         % (read_baseline(bad),))
        if read_baseline(os.path.join(td, "nope.json")) != ({}, "absent"):
            fails.append("a missing baseline did not read as 'absent' - 'I could not look' and "
                         "'there is nothing to see' must not be the same value")
        ok = os.path.join(td, "ok.json")
        with open(ok, "w", encoding="utf-8") as fh:
            json.dump({"over_limit": {"x.py": 900}}, fh)
        if read_baseline(ok) != ({"x.py": 900}, "ok"):
            fails.append("a valid baseline did not read back cleanly: %r" % (read_baseline(ok),))

    # the REVERSE walk: a baseline entry that no longer qualifies must be named, not vanish
    _stale = stale_baseline({"kept.py": 900, "shrank.py": 10}, {"kept.py": 900, "shrank.py": 900,
                                                                "deleted.py": 900})
    _names = sorted(r for r, _why in _stale)
    if _names != ["deleted.py", "shrank.py"]:
        fails.append("stale_baseline() reported %r; an entry that dropped below the limit and "
                     "one whose file is gone must BOTH be named, or the recorded count "
                     "overstates the debt in silence" % (_names,))

    print("-- file-size: ratchet asserted 5 ways; tri-state baseline, reverse walk and an "
          "independent line count asserted; %d .py file(s) in population" % len(sizes))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
