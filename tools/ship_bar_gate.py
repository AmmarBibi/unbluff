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

# [2026-08-16] Same fix as check_file_size.py, and for the same measured reason: this was
# `import gate_ledger` inside main()'s try/except, so it resolved only under `python
# tools/ship_bar_gate.py`. Any other invocation raised, the blanket except ate it, and the gate
# exited 0 having recorded nothing.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import gate_ledger
except ImportError as _e:                          # narrow: only the import, not the recording
    gate_ledger = None
    print("[ship-bar] NOTE: gate_ledger unavailable (%s) - this run will not be recorded" % _e)


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


def declared_count(path=REPORT):
    """The N the report itself claims in '## Confirmed (N)', or None if it does not say.

    [2026-08-16] The report's own declared total was parsed by NOTHING, so the gate printed two
    denominators in one PASS and reconciled neither. A heading that disagrees with the table
    beneath it means the table was edited and the heading was not - or the parser silently
    dropped a row whose shape it did not recognise, which is the failure that matters.
    """
    text = io.open(path, encoding="utf-8").read()
    m = re.search(r"^##\s+Confirmed\s*\((\d+)\)", text, re.M)
    return int(m.group(1)) if m else None


def reconcile(findings, report_rows, declared=None) -> list:
    """Problems that make the COUNT itself untrustworthy, before any verdict is given.

    A BIJECTION, as of 2026-08-16. It used to compare len() and then walk findings -> report
    only, matching on `where`, which is not unique. Review wf_f63b9ccf-816 confirmed three
    separate escapes through that (findings #3, #7, #10, #11):
      - a confirmed HIGH present in the report and ABSENT from findings.json passed, because
        nothing ever walked report -> findings;
      - a row could be swapped for a DUPLICATE of another row and the length still matched;
      - a HIGH could be laundered into a shippable MEDIUM by editing one field, because the
        severity histogram was printed but never compared.
    Comparing multisets of (severity, where) closes all three at once, and reports BOTH
    directions with counts rather than a single length mismatch.
    """
    problems = []
    report_ms = {}
    for sev, where, _f in report_rows:
        report_ms[(sev, where)] = report_ms.get((sev, where), 0) + 1
    findings_ms = {}
    for r in findings:
        key = (r.get("severity"), r.get("where"))
        findings_ms[key] = findings_ms.get(key, 0) + 1

    for key in sorted(set(report_ms) | set(findings_ms), key=lambda k: (str(k[0]), str(k[1]))):
        in_report, in_findings = report_ms.get(key, 0), findings_ms.get(key, 0)
        if in_report == in_findings:
            continue
        sev, where = key
        if in_findings < in_report:
            problems.append("the report has %d row(s) of [%s] %r and findings.json has %d - a "
                            "confirmed finding present in the canonical table and missing from "
                            "the ledger is UNADJUDICATED, not absent"
                            % (in_report, sev, where, in_findings))
        else:
            problems.append("findings.json has %d row(s) of [%s] %r and the report has %d - the "
                            "ledger claims an adjudication the canonical table does not carry"
                            % (in_findings, sev, where, in_report))

    if declared is not None and declared != len(report_rows):
        problems.append("the report's heading declares '## Confirmed (%d)' but %d row(s) parsed "
                        "out of its table - either the heading is stale or a row shape was "
                        "silently dropped by the parser, and both make the total a guess"
                        % (declared, len(report_rows)))

    for r in findings:
        st = r.get("state")
        if st not in STATES:
            problems.append("%s has state %r, not one of %r" % (r.get("id"), st, STATES))
        if r.get("severity") in BLOCKING and st == "FINALIZED-EXCLUSION":
            problems.append("%s is %s and marked FINALIZED-EXCLUSION - an exclusion cannot "
                            "rescue a CRITICAL or HIGH; re-adjudicate the SEVERITY in the "
                            "report instead" % (r.get("id"), r.get("severity")))
    # The old per-row `where` and severity-membership checks lived here. The multiset diff above
    # subsumes both and is strictly stronger: membership accepted ANY row sharing a `where`,
    # which is what let a duplicate stand in for a missing row.
    return problems


def _record(result: str, **fields) -> None:
    """ONE recording site for every exit path of main(), including the ones that cannot measure.

    [C1-CLASS 2026-08-20] Two of main()'s four exits returned without writing a row, so
    `gate_ledger.last_run("ship_bar")` kept serving the previous PASS for a gate that had just
    failed to run - and the push gate reads that ledger. The same shape was already fixed once in
    check_file_size.py; the task #17 sweep found it here and in score_false_alarms.py, which makes
    it a CLASS. Routing every exit through one helper is what stops the next exit path being added
    without one. The general control - proving the call is REACHED rather than merely present -
    is task #4(d); this makes the calls exist on every path so that control has something true to
    verify.
    """
    if gate_ledger is not None:
        gate_ledger.record("ship_bar", result, **fields)


def main() -> int:
    try:
        scope, findings = load_findings()
        report_rows = confirmed_from_report()
        declared = declared_count()
    except (OSError, ValueError) as exc:
        print("ship-bar: CANNOT RUN - %s" % exc)
        # RECORD ON THIS PATH TOO. Returning here wrote no row, so gate_ledger.last_run("ship_bar")
        # kept serving the previous PASS and any reader - including the push gate that consults
        # this ledger - saw a stale green for a gate that could not run at all. Same shape as the
        # defect already fixed in check_file_size; found in two more gates by the task #17 sweep,
        # which makes it a class rather than an instance. "Could not measure" is its own verdict
        # and must be distinguishable from "measured, and fine".
        _record("CANNOT_RUN", reason=str(exc)[:200])
        return 1

    # [2026-08-16] The FLOOR now lives here, in main(), not only in selftest(). It was asserted
    # exclusively in selftest() - which no registered invocation executes - so the stopping rule
    # would have passed over a ZERO-row population with the suite reporting green. A stopping
    # rule that cannot tell "nothing blocks" from "I read nothing" is not a control.
    if not findings or not report_rows:
        print("ship-bar: CANNOT RUN - parsed %d finding(s) and %d report row(s). A stopping "
              "rule over an empty population is not a PASS, it is a gate that read nothing."
              % (len(findings), len(report_rows)))
        _record("CANNOT_RUN", findings=len(findings), report_rows=len(report_rows))
        return 1

    problems = reconcile(findings, report_rows, declared=declared)
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
    # RECORD ON EVERY EXIT PATH with the REAL verdict - see the twin fix in check_file_size.py.
    # Recording only below the failure return, with "PASS" hardcoded, meant this gate could not
    # appear red in the ledger and last_run() kept serving a stale PASS after a failing run.
    open_rows = [r for r in findings if r.get("state") == "SCHEDULED"]
    failing = bool(problems or blocking)
    _record("FAIL" if failing else "PASS", findings=len(findings),
            report_rows=len(report_rows), problems=len(problems),
            blocking=len(blocking), scheduled=len(open_rows))
    if failing:
        print("ship-bar: FAIL - v1.0 cannot ship")
        return 1
    print("ship-bar: PASS - no CRITICAL or HIGH is unbuilt. %d MEDIUM/LOW ship as written "
          "rows (%s)" % (len(open_rows), ", ".join(sorted(r["id"] for r in open_rows))))
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

    # DRIFT: a hand-entered severity that disagrees with the report must FAIL.
    # [2026-08-16] This asserted `any("drifted" in p)` - the wording of the old one-directional
    # message. The bijection that replaced it reports the SAME defect more completely, as two
    # problems naming both sides, so the assertion now checks the BEHAVIOUR (both severities are
    # named) instead of a substring. Strictly stronger: the old text could be produced while the
    # report-side row went unmentioned, which is the direction that used to pass silently.
    probs = reconcile([{"id": "x", "severity": "LOW", "state": "BUILT", "where": "z"}],
                      [("CRITICAL", "z", "f")])
    if not (probs and any("CRITICAL" in p for p in probs) and any("LOW" in p for p in probs)):
        fails.append("a ledger severity that contradicts the canonical report was accepted, or "
                     "was reported without naming both the claimed and the canonical severity: "
                     "%r" % (probs,))

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

    # [BIJECTION 2026-08-16] The three escapes review wf_f63b9ccf-816 confirmed through the old
    # one-directional, non-unique-key reconcile. Each is asserted against the RULE, not the file.
    _rep = [("HIGH", "a.py", "finding A"), ("MEDIUM", "b.py", "finding B")]
    _led = [{"id": "1", "severity": "HIGH", "where": "a.py", "state": "BUILT"},
            {"id": "2", "severity": "MEDIUM", "where": "b.py", "state": "BUILT"}]
    if reconcile(_led, _rep):
        fails.append("a ledger that MATCHES the report was reported as a problem: %r"
                     % (reconcile(_led, _rep),))
    # (a) a confirmed row present in the report and absent from the ledger. The old code walked
    #     findings -> report only, so this direction passed silently.
    if not reconcile(_led[:1], _rep):
        fails.append("a report row missing from findings.json passed reconcile - the direction "
                     "report -> ledger is unchecked again, and an unadjudicated HIGH ships")
    # (b) a DUPLICATE standing in for a missing row. Lengths still match, so a count comparison
    #     cannot see it and `where`-membership accepted any row sharing the key.
    _dup = [dict(_led[0]), dict(_led[0], id="2")]
    if not reconcile(_dup, _rep):
        fails.append("a duplicated row substituted for a missing one passed reconcile - the "
                     "count matches, which is exactly why a count is not a reconciliation")
    # (c) severity laundering: one field edited turns a blocking HIGH into a shippable MEDIUM.
    _laundered = [dict(_led[0], severity="MEDIUM"), _led[1]]
    if not reconcile(_laundered, _rep):
        fails.append("a HIGH rewritten as MEDIUM in the ledger passed reconcile - severity is "
                     "supposed to be DERIVED from the report, so this is the whole design")
    # (d) the report's own declared total must be enforced, not just printed.
    if not reconcile(_led, _rep, declared=99):
        fails.append("a '## Confirmed (N)' heading disagreeing with its own table passed - the "
                     "gate printed two denominators and reconciled neither")

    # and the REAL report, when it is reachable (it is not, inside a mutation scratch tree)
    real = 0
    if os.path.isfile(REPORT):
        real = len(confirmed_from_report())
        if real < 20:
            fails.append("only %d confirmed row(s) parsed from the real report - the table "
                         "shape changed and every severity is unverified" % real)
        _declared = declared_count()
        if _declared is not None and _declared != real:
            fails.append("the real report declares %d confirmed but %d row(s) parse out of its "
                         "table" % (_declared, real))

    print("-- ship-bar: rule asserted both directions; bijection asserted 4 ways; real report %s"
          % ("%d row(s)" % real if real else "not reachable here (scratch tree)"))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
