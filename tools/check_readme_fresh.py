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
_JOBS_RE = re.compile(r"CI is (\d+) jobs")


def expected_jobs() -> int:
    """How many jobs CI actually runs, DERIVED from the workflow rather than remembered.

    [CI-JOBS] "CI is N jobs" is a second hand-maintained number in the same file as the one
    this gate already protects, and it has been wrong before - CHANGELOG records a period when
    README said 14. It was corrected by hand each time, which is the REMEMBER-vs-ENFORCE
    failure this repo has a standing rule about: prose is advisory, only a gate is a control.
    Adding the rich-path job made it 17 and I edited it by hand, which is exactly the moment to
    stop doing that.

    A job with a `strategy.matrix` contributes the PRODUCT of its matrix axes, not 1. Parsed
    with pyyaml where available, and by a deliberately narrow structural walk where it is not,
    because CI runners here pip-install nothing (see the RICH-CI job comment) and a gate that
    silently skips is the thing being guarded against.
    """
    path = os.path.join(REPO, ".github", "workflows", "selftest.yml")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    try:
        import yaml
    except ImportError:
        return _expected_jobs_no_yaml(text)
    jobs = (yaml.safe_load(text) or {}).get("jobs") or {}
    total = 0
    for spec in jobs.values():
        axes = ((spec or {}).get("strategy") or {}).get("matrix") or {}
        n = 1
        for key, values in axes.items():
            if key in ("include", "exclude"):
                continue
            if isinstance(values, list) and values:
                n *= len(values)
        n += len(axes.get("include") or [])
        n -= len(axes.get("exclude") or [])
        total += n
    return total


def _expected_jobs_no_yaml(text: str) -> int:
    """Structural fallback for runners without pyyaml - which is EVERY runner here, since no
    workflow pip-installs anything. Returns 0 when it cannot answer, and the caller treats 0 as
    a FAILURE, never a pass: "I could not look" must not read as "nothing was wrong".

    Narrow on purpose. It understands exactly the two matrix shapes this file uses - an inline
    `key: [a, b, c]` list and an `include:` / `exclude:` block of `- ` entries - and returns 0
    the moment it sees a `jobs:` section it cannot account for, rather than guessing low and
    reporting a confident wrong number.
    """
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.rstrip() == "jobs:")
    except StopIteration:
        return 0
    # job names sit at exactly two spaces of indent under `jobs:`
    bounds = [i for i in range(start + 1, len(lines))
              if re.match(r"^  [A-Za-z][\w-]*:\s*$", lines[i])]
    if not bounds:
        return 0
    bounds.append(len(lines))
    total = 0
    for j, begin in enumerate(bounds[:-1]):
        block = lines[begin + 1:bounds[j + 1]]
        n, axes_seen = 1, 0
        for k, ln in enumerate(block):
            m = re.match(r"^\s{8}([\w-]+):\s*\[(.+)\]\s*$", ln)
            if m and m.group(1) not in ("include", "exclude"):
                items = [p for p in (q.strip() for q in m.group(2).split(",")) if p]
                if not items:
                    return 0
                n *= len(items)
                axes_seen += 1
                continue
            m2 = re.match(r"^\s{8}(include|exclude):\s*$", ln)
            if m2:
                # count the `- ` entries that open each mapping in the block
                extra = 0
                for ln2 in block[k + 1:]:
                    if re.match(r"^\s{10}- ", ln2):
                        extra += 1
                    elif ln2.strip() and not ln2.startswith(" " * 12) \
                            and not ln2.lstrip().startswith("#"):
                        break
                n += extra if m2.group(1) == "include" else -extra
                axes_seen += 1
        total += n
    return total


def expected_count() -> int:
    """What `run_selftests.py` will actually run: detected hooks + the auxiliary gates."""
    from hook_health_check import selftestable_hooks
    from run_selftests import AUX_GATES
    return len(selftestable_hooks(os.path.join(REPO, "hooks"))) + len(AUX_GATES)


def claimed_counts(readme_text: str) -> list:
    return [int(m) for m in _CLAIM_RE.findall(readme_text)]


def claimed_jobs(readme_text: str) -> list:
    return [int(m) for m in _JOBS_RE.findall(readme_text)]


def verdict_jobs(readme_text: str, want: int) -> tuple:
    """(exit_code, message) for README's "CI is N jobs" against the workflow itself.

    `want == 0` means the parser could not answer, and that FAILS. A gate that cannot see its
    subject must not report the same green as one that looked and found nothing wrong.
    """
    if want <= 0:
        return 1, ("readme-jobs: FAIL - could not derive the job count from "
                   ".github/workflows/selftest.yml, so this gate compared NOTHING. Not a pass.")
    claims = claimed_jobs(readme_text)
    if not claims:
        return 1, ("readme-jobs: FAIL - README.md contains no 'CI is N jobs' line, so this "
                   "gate has nothing to compare (the workflow defines %d)" % want)
    bad = [n for n in claims if n != want]
    if bad:
        return 1, ("readme-jobs: FAIL - README claims CI is %s job(s); the workflow defines "
                   "%d. Hand-maintained and therefore stale - it said 14 once before."
                   % (bad, want))
    return 0, ("readme-jobs: OK - README's %d matches the %d jobs the workflow defines"
               % (claims[0], want))


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
    rc_jobs, msg_jobs = verdict_jobs(text, expected_jobs())
    print(msg_jobs)
    return rc or rc_jobs


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
    # [CI-JOBS] The same four branches for the job-count half, plus the one that only this
    # half has: a parser that could not answer. All exercised, because an unexercised branch
    # in a gate is a branch that does not exist - this file's own `verdict` had exactly that
    # problem and its mutation came back SURVIVED.
    if claimed_jobs("CI is 12 jobs and more") != [12]:
        fails.append("claimed_jobs did not read the number back")
    if verdict_jobs("CI is 12 jobs", 12)[0] != 0:
        fails.append("a MATCHING job claim was rejected")
    if verdict_jobs("CI is 12 jobs", 17)[0] != 1:
        fails.append("a STALE job claim was accepted - README said 14 once already")
    if verdict_jobs("no claim here", 17)[0] != 1:
        fails.append("an ABSENT job claim passed, so the gate would compare nothing")
    rc_blind, msg_blind = verdict_jobs("CI is 17 jobs", 0)
    if rc_blind != 1:
        fails.append("a gate that could NOT DERIVE the job count reported the same green as "
                     "one that looked - 'I could not see' must never read as 'nothing wrong'")
    if "compared NOTHING" not in msg_blind:
        fails.append("the blind-parser message does not say it saw nothing: %r" % (msg_blind,))
    # the two derivations must AGREE, or one of them is lying and the gate is untrustworthy
    try:
        import io as _io
        _wf = _io.open(os.path.join(REPO, ".github", "workflows", "selftest.yml"),
                       encoding="utf-8").read()
        _fallback = _expected_jobs_no_yaml(_wf)
        if _fallback and _fallback != expected_jobs():
            fails.append("the yaml and no-yaml job counts DISAGREE (%d vs %d) - CI runs the "
                         "fallback, so the number this gate enforces would depend on which "
                         "machine ran it" % (_fallback, expected_jobs()))
    except OSError:
        # THIRD STATE, not a failure. This probe tests the two PARSERS agree; if the workflow
        # is absent there is nothing to parse and the question cannot be put. The GATE still
        # fails in that situation (verdict_jobs treats want<=0 as FAIL) - which is the right
        # split: a missing workflow is a real problem for the gate and a non-question for the
        # probe. Conflating them made every mutation of this file die at baseline.
        print("SELFTEST SKIP: no .github/workflows/selftest.yml here, so the two job-count "
              "parsers could not be cross-checked - NOT verified in this tree")
    # [CI-JOBS] The WIRING, not the helper. Every branch of verdict_jobs() above can be green
    # while main() never calls it - CI-JOBS-2 came back SURVIVED proving exactly that, the
    # third time this session a helper was tested and its call site was not. Drive main() and
    # require its own output to carry the line.
    _real_out = sys.stdout
    sys.stdout = __import__("io").StringIO()
    try:
        main()
        _main_out = sys.stdout.getvalue()
    finally:
        sys.stdout = _real_out
    if "readme-jobs:" not in _main_out:
        fails.append("main() never emitted a readme-jobs verdict, so the job-count gate is "
                     "UNWIRED - every branch of verdict_jobs() can pass while the number goes "
                     "unchecked: %r" % (_main_out[:200],))
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
