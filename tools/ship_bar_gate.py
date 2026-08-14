#!/usr/bin/env python3
"""SHIP-BAR-GATE: turn the v1.0 stopping rule from a promise into a control.

CRITERION 2, as amended 2026-08-12: "No CRITICAL or HIGH defect reachable by a user, where the
POPULATION is what the adversarial review + the R1/R2 rule define. MEDIUM/LOW ship with a
written WON'T-FIX or BACKLOG row." Before this file, that was prose - nothing stopped a v1.4.0
tag while a CRITICAL sat open, and the count of open findings was itself unverifiable (the
ledger's own list of "the remaining 8" named five items the same table marked BUILT).

WHAT IT REFUSES TO DO. It does NOT parse the prose ledger for severities. Prose drifts - this
repo has a standing rule about anchoring the CONDITION rather than the sentence, and five
mutation anchors have already drifted by quoting prose. Instead:

  * SEVERITY is DERIVED, every run, from the review report's own `## Confirmed` table. That
    table is the canonical record; re-reading it means a severity cannot rot by being retyped.
  * STATE (BUILT / SCHEDULED / FINALIZED-EXCLUSION) is the only hand-adjudicated field, and it
    lives in `docs/audits/findings.json`.
  * The two are RECONCILED on every run. A finding in the report but not the ledger, or vice
    versa, is a FAILURE - that is precisely how "the remaining 8" became unverifiable.

WHAT THIS GATE DOES NOT PROVE, stated so the PASS cannot be over-read. STATE is
hand-adjudicated. This gate proves that no CRITICAL or HIGH is *marked* anything other than
BUILT, and that the severities have not drifted from the report - it does NOT prove that a row
marked BUILT was actually fixed. A wrongly-entered BUILT passes silently, which is the same
shape as the "remaining 8" list that named five items the table already marked BUILT.
The durable closure is to require every BUILT row to name the MUTATION that pins it, and to
assert that mutation exists in the harness - then BUILT means "a test fails without the fix"
rather than "someone typed BUILT". SCHEDULED; see the coverage ledger.

A CRITICAL OR HIGH CANNOT BE EXCLUDED. `FINALIZED-EXCLUSION` rescues a MEDIUM or LOW only.
Allowing it at the top two severities would reopen the loophole the stopping rule closes: the
DoD says MEDIUM/LOW ship with a written row, and says nothing of the kind about CRITICAL/HIGH.
If a CRITICAL is genuinely not a defect, the honest move is to re-adjudicate its SEVERITY in
the report, where the change is visible - not to excuse it in the state column.
"""

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(REPO, "docs", "audits", "adversarial_review_2026-08-12.md")
FINDINGS = os.path.join(REPO, "docs", "audits", "findings.json")

BLOCKING = ("CRITICAL", "HIGH")
STATES = ("BUILT", "SCHEDULED", "FINALIZED-EXCLUSION")


def confirmed_from_report(path=REPORT) -> list:
    """[(severity, where, finding)] parsed from the report's own Confirmed table. DERIVED."""
    text = io.open(path, encoding="utf-8").read()
    if "## Confirmed" not in text:
        raise ValueError("no '## Confirmed' section in %s - the canonical severity table is "
                         "gone, and this gate cannot verify anything without it" % path)
    block = text.split("## Confirmed")[1].split("## Refuted")[0]
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or "sev (corrected)" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        sev = re.sub(r"[*`]", "", cells[0]).strip()
        if sev not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            continue
        rows.append((sev, re.sub(r"[`]", "", cells[4]).strip(), cells[3]))
    return rows


def load_findings(path=FINDINGS):
    """(scope, findings). The SCOPE is mandatory, and that is the point.

    [source-coverage 2026-08-14] This gate first shipped reading a bare list, and its PASS
    covered 24 findings while the 2026-08-06 guards review alone holds 42 severity-tagged rows
    including TEN HIGH. Those are legitimately out of population - the ledger carries a closed
    decision that guards disarmable by editing unbluff's own source are WON'T-FIX, which
    deletes exactly that set - but NOTHING IN THE DATA SAID SO. A gate that reports PASS over
    an undeclared subset of its stated population is the false-confidence defect this repo
    exists to catch, committed by the gate built to enforce the ship bar.
    So the file must declare what it covers and what it deliberately excludes, and the gate
    prints both. A missing scope is a hard failure, never a default.
    """
    with io.open(path, encoding="utf-8") as f:
        doc = json.load(f)
    if isinstance(doc, list):
        raise ValueError(
            "findings.json is a bare list with no SCOPE. It must be an object with 'scope' "
            "and 'findings', because a PASS over an undeclared population is worse than no "
            "gate - see the note on load_findings()")
    scope, rows = doc.get("scope"), doc.get("findings")
    if not isinstance(scope, dict) or not isinstance(rows, list):
        raise ValueError("findings.json needs a 'scope' object and a 'findings' list")
    for key in ("covers", "excludes", "exclusion_basis"):
        if not scope.get(key):
            raise ValueError("findings.json scope is missing %r - the population this gate "
                             "passes over must be stated, not assumed" % key)
    return scope, rows


def violations(findings) -> list:
    """Rows that BLOCK the ship bar: CRITICAL or HIGH and not BUILT.

    A function so the rule itself is testable without a file - and so a mutation reaches the
    same code the probe does, which is the hollow-pin mode that has already bitten twice here.
    """
    out = []
    for r in findings:
        if r.get("severity") in BLOCKING and r.get("state") != "BUILT":
            out.append(r)
    return out


def reconcile(findings, report_rows) -> list:
    """Problems that make the COUNT itself untrustworthy, before any verdict is given."""
    problems = []
    if len(findings) != len(report_rows):
        problems.append("findings.json has %d row(s), the report's Confirmed table has %d - "
                        "one of them is stale, and the open-count cannot be trusted until "
                        "they agree" % (len(findings), len(report_rows)))
    by_where = {}
    for sev, where, _f in report_rows:
        by_where.setdefault(where, []).append(sev)
    for r in findings:
        st = r.get("state")
        if st not in STATES:
            problems.append("%s has state %r, not one of %r" % (r.get("id"), st, STATES))
        if r.get("severity") in BLOCKING and st == "FINALIZED-EXCLUSION":
            problems.append("%s is %s and marked FINALIZED-EXCLUSION - an exclusion cannot "
                            "rescue a CRITICAL or HIGH; re-adjudicate the SEVERITY in the "
                            "report instead" % (r.get("id"), r.get("severity")))
        where = r.get("where")
        if where not in by_where:
            problems.append("%s cites %r, which appears in no report row - severity is DERIVED "
                            "from the report, so a row that cannot be matched is unverified"
                            % (r.get("id"), where))
        elif r.get("severity") not in by_where[where]:
            problems.append("%s records severity %s but the report says %r for %s - the "
                            "hand-entered ledger has drifted from the canonical table"
                            % (r.get("id"), r.get("severity"), by_where[where], where))
    return problems


def main() -> int:
    try:
        scope, findings = load_findings()
        report_rows = confirmed_from_report()
    except (OSError, ValueError) as exc:
        print("ship-bar: CANNOT RUN - %s" % exc)
        return 1

    problems = reconcile(findings, report_rows)
    blocking = violations(findings)
    counts = {}
    for r in findings:
        counts.setdefault(r.get("severity"), {}).setdefault(r.get("state"), 0)
        counts[r["severity"]][r["state"]] += 1

    print("ship-bar: %d confirmed finding(s), reconciled against %d report row(s)"
          % (len(findings), len(report_rows)))
    print("  COVERS   : %s" % scope["covers"])
    print("  EXCLUDES : %s" % scope["excludes"])
    print("  BASIS    : %s" % scope["exclusion_basis"])
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if sev in counts:
            print("  %-9s %s" % (sev, dict(sorted(counts[sev].items()))))
    for p in problems:
        print("ship-bar RECONCILE FAIL:", p)
    for r in blocking:
        print("ship-bar BLOCK: %s [%s] is %s, not BUILT - %s"
              % (r.get("id"), r.get("severity"), r.get("state"), r.get("where")))
    if problems or blocking:
        print("ship-bar: FAIL - v1.0 cannot ship")
        return 1
    open_rows = [r for r in findings if r.get("state") == "SCHEDULED"]
    print("ship-bar: PASS - no CRITICAL or HIGH is unbuilt. %d MEDIUM/LOW ship as written "
          "rows (%s)" % (len(open_rows), ", ".join(sorted(r["id"] for r in open_rows))))
    try:
        import gate_ledger
        gate_ledger.record("ship_bar", "PASS", findings=len(findings),
                           blocking=len(blocking), scheduled=len(open_rows))
    except Exception:
        pass
    return 0


def selftest() -> int:
    fails = []
    # the RULE, both directions, through the real decision function
    if violations([{"id": "x", "severity": "CRITICAL", "state": "SCHEDULED"}]) == []:
        fails.append("an open CRITICAL did not block the ship bar")
    if violations([{"id": "x", "severity": "HIGH", "state": "SCHEDULED"}]) == []:
        fails.append("an open HIGH did not block the ship bar")
    if violations([{"id": "x", "severity": "MEDIUM", "state": "SCHEDULED"}]) != []:
        fails.append("a SCHEDULED MEDIUM blocked the ship bar - the amended criterion 2 says "
                     "MEDIUM/LOW ship as written rows, and a gate that blocks on them would "
                     "make the stopping rule unfalsifiable again")
    if violations([{"id": "x", "severity": "CRITICAL", "state": "BUILT"}]) != []:
        fails.append("a BUILT CRITICAL blocked the ship bar")

    # the LOOPHOLE: an exclusion must not rescue a CRITICAL/HIGH
    probs = reconcile([{"id": "x", "severity": "CRITICAL", "state": "FINALIZED-EXCLUSION",
                        "where": "z"}], [("CRITICAL", "z", "f")])
    if not any("cannot rescue" in p for p in probs):
        fails.append("a CRITICAL marked FINALIZED-EXCLUSION was accepted - that reopens the "
                     "loophole the stopping rule exists to close")

    # DRIFT: a hand-entered severity that disagrees with the report must FAIL
    probs = reconcile([{"id": "x", "severity": "LOW", "state": "BUILT", "where": "z"}],
                      [("CRITICAL", "z", "f")])
    if not any("drifted" in p for p in probs):
        fails.append("a ledger severity that contradicts the canonical report was accepted")

    # COUNT drift both ways
    if not any("row(s)" in p for p in reconcile([], [("LOW", "z", "f")])):
        fails.append("a findings.json missing a report row was accepted")

    # SCOPE IS MANDATORY. A bare list, or one missing an exclusion basis, must be REFUSED -
    # this gate's own first version passed over 24 findings while 42 more (10 of them HIGH)
    # sat outside an undeclared boundary.
    import tempfile as _tf2
    with _tf2.TemporaryDirectory(prefix="unbluff-scope-") as td2:
        bare = os.path.join(td2, "bare.json")
        io.open(bare, "w", encoding="utf-8").write(json.dumps([{"id": "x"}]))
        try:
            load_findings(bare)
            fails.append("a findings file with NO SCOPE was accepted - the gate would report "
                         "PASS over an undeclared population, which is worse than no gate")
        except ValueError:
            pass
        partial = os.path.join(td2, "partial.json")
        io.open(partial, "w", encoding="utf-8").write(json.dumps(
            {"scope": {"covers": "x", "excludes": "y"}, "findings": []}))
        try:
            load_findings(partial)
            fails.append("a scope with no exclusion_basis was accepted - an exclusion nobody "
                         "has to justify is how a population quietly shrinks")
        except ValueError:
            pass

    # The PARSER, against a SYNTHETIC report. Hermetic on purpose: the mutation harness copies
    # hooks/ tools/ tests/ skills/ .github/ and three root files - NOT docs/ - so a selftest
    # that reads the real report is RED in every scratch tree and every mutation here reports
    # "baseline already RED" instead of proving anything. Found exactly that way.
    import tempfile
    synthetic = (
        "# r\n\n## Confirmed (2)\n\n"
        "| sev (corrected) | finder said | lens | finding | file |\n"
        "|---|---|---|---|---|\n"
        "| **CRITICAL** | CRITICAL | l | a bad thing | `hooks/a.py:1` |\n"
        "| **LOW** | LOW | l | a small thing | `hooks/b.py:2` |\n\n"
        "## Refuted (0)\n")
    with tempfile.TemporaryDirectory(prefix="unbluff-sb-") as td:
        p = os.path.join(td, "r.md")
        io.open(p, "w", encoding="utf-8").write(synthetic)
        rows = confirmed_from_report(p)
        if len(rows) != 2:
            fails.append("the parser read %d row(s) from a 2-row table" % len(rows))
        elif [s for s, _w, _f in rows] != ["CRITICAL", "LOW"]:
            fails.append("the parser is not reading the SEVERITY column: got %r"
                         % ([s for s, _w, _f in rows],))
        # a report with no Confirmed table must FAIL LOUDLY, never yield zero rows quietly -
        # zero findings and an unreadable report are the same output otherwise
        empty = os.path.join(td, "empty.md")
        io.open(empty, "w", encoding="utf-8").write("# nothing here\n")
        try:
            confirmed_from_report(empty)
            fails.append("a report with NO Confirmed table parsed silently - the gate would "
                         "then reconcile against zero rows and pass on an empty ledger")
        except ValueError:
            pass

    # and the REAL report, when it is reachable (it is not, inside a mutation scratch tree)
    real = 0
    if os.path.isfile(REPORT):
        real = len(confirmed_from_report())
        if real < 20:
            fails.append("only %d confirmed row(s) parsed from the real report - the table "
                         "shape changed and every severity is unverified" % real)

    print("-- ship-bar: rule asserted both directions; synthetic parse OK; real report %s"
          % ("%d row(s)" % real if real else "not reachable here (scratch tree)"))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
