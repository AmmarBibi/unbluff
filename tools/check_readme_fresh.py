#!/usr/bin/env python3
"""Gate: the selftest count the README advertises must match the one the suite actually runs.

The README pastes a `run_selftests.py` transcript ending in "all N selftests passed". That N
was 18 while the suite ran 21, and the three missing names were `capped_report`,
`transcript_util` and `review-freshness-scope` - i.e. the README under-reported the suite by
exactly the hooks added since someone last copied the output by hand.

Nobody notices a stale paste, because it looks like evidence. This repo already treats that
class as a defect everywhere else (numbers_match for reports, regen_example_settings for
examples/settings.json); the README's own headline number had no such gate, in the one file a
reader treats as the project's claim about itself.

DERIVED, never listed: the expected count comes from the same detector run_selftests uses, so
adding a hook updates it automatically and the README is what has to catch up.

    python tools/check_readme_fresh.py     # exit 1 on drift
"""
from __future__ import annotations

import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, REPO)

_CLAIM_RE = re.compile(r"all (\d+) selftests passed")


def expected_count() -> int:
    """What `run_selftests.py` will actually run: detected hooks + the auxiliary gates."""
    from hook_health_check import selftestable_hooks
    from run_selftests import AUX_GATES
    return len(selftestable_hooks(os.path.join(REPO, "hooks"))) + len(AUX_GATES)


def claimed_counts(readme_text: str) -> list:
    return [int(m) for m in _CLAIM_RE.findall(readme_text)]


def verdict(readme_text: str, want: int) -> tuple:
    """(exit_code, message) for a README body against the expected count. Pure, so the
    selftest can exercise EVERY branch - including the absent-claim one, which the first
    version left uncovered and whose mutation therefore came back SURVIVED."""
    claims = claimed_counts(readme_text)
    if not claims:
        # An ABSENT claim is not a passing one. If the transcript is removed or reworded this
        # gate would otherwise go quietly green while comparing nothing at all.
        return 1, ("readme-fresh: FAIL - README.md contains no 'all N selftests passed' line, "
                   "so this gate has nothing to compare (expected %d)" % want)
    bad = [n for n in claims if n != want]
    if bad:
        return 1, ("readme-fresh: FAIL - README claims %s selftest(s); the suite runs %d. The "
                   "pasted transcript is stale." % (bad, want))
    return 0, ("readme-fresh: OK - README's %d matches the %d selftests the suite runs"
               % (claims[0], want))


def main() -> int:
    path = os.path.join(REPO, "README.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("readme-fresh: FAIL - cannot read README.md (%s)" % e)
        return 1
    rc, msg = verdict(text, expected_count())
    print(msg)
    return rc


def selftest() -> int:
    fails = []
    if claimed_counts("all 18 selftests passed") != [18]:
        fails.append("claimed_counts did not read the number back")
    if claimed_counts("nothing here at all") != []:
        fails.append("claimed_counts invented a number")
    # every branch of the decision, including the one a stale-paste gate most needs
    if verdict("all 7 selftests passed", 7)[0] != 0:
        fails.append("a MATCHING claim was rejected")
    if verdict("all 7 selftests passed", 9)[0] != 1:
        fails.append("a STALE claim was accepted")
    rc_absent, msg_absent = verdict("this README says nothing about selftests", 9)
    if rc_absent != 1:
        fails.append("an ABSENT claim passed - the gate would go green while comparing "
                     "nothing, which is how a stale-paste check evaporates")
    if "nothing to compare" not in msg_absent:
        fails.append("the absent-claim message does not say what went wrong: %r" % (msg_absent,))
    want = expected_count()
    if want <= 0:
        fails.append("expected_count() derived %r - a zero denominator would make this gate "
                     "pass against any README" % (want,))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
