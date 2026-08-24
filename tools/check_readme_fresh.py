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
_SCEN_RE = re.compile(r"====\s*(\d+)/(\d+) scenarios passed\s*====")


def expected_scenarios():
    """(passed, total) of the newest recorded integration run. DERIVED, never remembered.

    [SCEN 2026-08-24] The README pastes the integration transcript under the line "Don't take the
    demos on faith - run it yourself", and that block was the ONE number in the file no gate read.
    It said `30/30` against a live 34, and it had been wrong before: p14_audit_findings.md:132
    filed the byte-identical defect at 26-vs-30 and p14_new_code_review.md:301 prescribed this
    very regex - then only the instance was patched and the gate was never built. Two audits, one
    prescription, no control; a third drift followed exactly as the standing rule predicts.

    Derived from the gate ledger rather than by counting `record(` call sites, because the count
    is not static: the J block emits four rows from two literal calls inside a loop, so an AST
    walk would confidently answer 32 and gate the README against a number that is simply wrong.
    The ledger row is written BY a real run and carries its own utc, which is also what
    meta-review CHECK 4 means by reading the ledger instead of reconstructing it. No row is a
    FAILURE, never a skip: "nobody has ever run it" and "it passes" must not look the same.
    """
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import gate_ledger
    row = gate_ledger.last_run("integration")
    if not row:
        return None
    try:
        return int(row["passed"]), int(row["total"])
    except (KeyError, TypeError, ValueError):
        return None


def claimed_scenarios(readme_text: str) -> list:
    return [(int(a), int(b)) for a, b in _SCEN_RE.findall(readme_text)]


def verdict_scenarios(readme_text: str, recorded) -> tuple:
    claims = claimed_scenarios(readme_text)
    # The presence of the LINE is a repository property and is checked everywhere. Its VALUE can
    # only be checked where a run happened, so the two are separated.
    if not claims:
        return 1, ("readme-scenarios: FAIL - README.md contains no 'N/M scenarios passed' line, "
                   "so the integration transcript it offers as evidence is ungated.")
    if recorded is None:
        # UNDETERMINED, not FAIL, and not OK. `docs/audits/gate_runs.json` is deliberately
        # untracked, so NO CI runner has a ledger - the first spelling of this gate failed
        # closed and reddened all 17 jobs on correct code, which is the environment-dependence
        # class this very session spent its day removing, reintroduced by the commit removing
        # it. Blocking on a ledger a runner cannot have is not strictness, it is a gate asking
        # the wrong machine. The repo already settled this exact dilemma for tools/
        # no_regression.py - "distinguishes 'I could not look' from 'there is nothing to look
        # at' and reports the former as UNDETERMINED rather than blocking", quoted in
        # .github/workflows/selftest.yml - so this follows that precedent rather than inventing
        # a second answer. Printed distinctly so it can never be read as a pass, and the
        # integration tier the value depends on is separately gated in CI by its own job.
        return 0, ("readme-scenarios: UNDETERMINED - README pastes %s and there is no "
                   "integration row in this checkout's gate ledger to check it against. NOT a "
                   "pass: run tests/test_integration.py locally before tagging a release."
                   % (claims,))
    passed, total = recorded
    bad = [c for c in claims if c != (passed, total)]
    if bad:
        return 1, ("readme-scenarios: FAIL - README pastes %s; the newest recorded integration "
                   "run is %d/%d. A stale paste reads exactly like a fresh one."
                   % (bad, passed, total))
    return 0, ("readme-scenarios: OK - README's %d/%d matches the newest recorded integration run"
               % (passed, total))


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


# Spelled-out forms the README actually uses. Digits are accepted too; the point is to gate the
# number, not to dictate the prose.
_WORD_NUMBERS = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
                 "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
                 "nineteen": 19, "twenty": 20, "twenty-one": 21, "twenty-two": 22,
                 "twenty-three": 23, "twenty-four": 24, "twenty-five": 25}
_PIECES_RE = re.compile(r"enables all ([a-z-]+|\d+) pieces")
_SECTION_RE = re.compile(r"^### (.+?) · ", re.M)


def expected_pieces() -> tuple:
    """(count, roster) of what a user actually gets, DERIVED from install.py and skills/.

    [#40] The third hand-maintained cardinality on this page, and the one that had drifted
    furthest: the README said "eighteen", its own What's-inside list held 17, and the code
    shipped 20. Three numbers, no two agreeing, because nothing compared them. Two of the three
    missing entries - piped_gate_guard and timing_claim_guard - are hooks that FIRE on a user's
    machine while being undocumented, which is the opposite of what this file is for.

    Also returns the ROSTER, not only the count. A count-only gate lets a name be dropped and
    another added in the same edit and calls it green - and the count-only version of this gate
    let `no-network: OK` fall out of the pasted transcript for a day without noticing.
    """
    import install
    from install import dispatcher_subhooks
    src = open(os.path.join(REPO, "install.py"), encoding="utf-8").read()
    wired = set(re.findall(r'_cmd\("([a-z_]+)\.py"\)', src))
    subs = {n[:-3] for n in dispatcher_subhooks(os.path.join(REPO, "hooks"))}
    # pre_push_gate is installed as a real git hook rather than a settings.json entry, so it is
    # invisible to both sets above while very much being a piece the user gets.
    hooks = wired | subs | {"pre_push_gate"}
    skills_dir = os.path.join(REPO, "skills")
    skills = {d for d in os.listdir(skills_dir)
              if os.path.isdir(os.path.join(skills_dir, d))}
    assert install  # imported for its side-effect-free module path; keeps linters honest
    return len(hooks | skills), (hooks | skills)


def claimed_pieces(readme_text: str) -> list:
    out = []
    for m in _PIECES_RE.findall(readme_text):
        if m.isdigit():
            out.append(int(m))
        elif m in _WORD_NUMBERS:
            out.append(_WORD_NUMBERS[m])
        else:
            out.append(-1)      # an unparseable word is NOT a pass; see verdict_pieces
    return out


def _norm(name: str) -> str:
    return name.strip().replace("-", "_").lower()


def readme_roster(readme_text: str) -> set:
    return {_norm(n) for n in _SECTION_RE.findall(readme_text)}


def _matches(readme_name: str, code_name: str) -> bool:
    """README headings use display names (`numbers-match` for `numbers_match_on_write`)."""
    r, c = _norm(readme_name), _norm(code_name)
    return r == c or c.startswith(r + "_") or r.startswith(c + "_")


def verdict_pieces(readme_text: str, want: int, roster: set) -> tuple:
    """(exit_code, message) for the piece COUNT and the piece ROSTER together."""
    if want <= 0 or not roster:
        return 1, ("readme-pieces: FAIL - could not derive the piece roster, so this gate "
                   "compared NOTHING. Not a pass.")
    problems = []
    claims = claimed_pieces(readme_text)
    if not claims:
        problems.append("README has no 'enables all N pieces' line, so the count is ungated")
    elif -1 in claims:
        problems.append("the piece count is spelled with a word this gate cannot read; use a "
                        "digit or add it to _WORD_NUMBERS rather than leaving it unchecked")
    else:
        bad = [n for n in claims if n != want]
        if bad:
            problems.append("README claims %s piece(s); the code ships %d" % (bad, want))
    listed = readme_roster(readme_text)
    undocumented = sorted(c for c in roster
                          if not any(_matches(r, c) for r in listed))
    if undocumented:
        problems.append("shipped but absent from 'What's inside': %s" % (undocumented,))
    phantom = sorted(r for r in listed
                     if not any(_matches(r, c) for c in roster))
    if phantom:
        problems.append("documented but not shipped: %s" % (phantom,))
    if problems:
        return 1, "readme-pieces: FAIL - " + "; ".join(problems)
    return 0, ("readme-pieces: OK - README's %d matches the %d shipped piece(s), and every one "
               "of them has a section" % (claims[0], want))


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
    want_pieces, roster = expected_pieces()
    rc_pieces, msg_pieces = verdict_pieces(text, want_pieces, roster)
    print(msg_pieces)
    rc_scen, msg_scen = verdict_scenarios(text, expected_scenarios())
    print(msg_scen)
    return rc or rc_jobs or rc_pieces or rc_scen


def _selftest_pieces(fails: list) -> None:
    """[#40] Every branch of the piece gate, including the two that make it a ROSTER check
    rather than a second count check. Written before the README was corrected, so each branch
    was observed failing on the real file first."""
    ROSTER = {"alpha", "beta_hook", "meta-review"}
    OK = "enables all 3 pieces\n### alpha · Stop\n### beta · Stop\n### meta-review · skill\n"
    if claimed_pieces("enables all eighteen pieces") != [18]:
        fails.append("claimed_pieces cannot read a spelled number")
    if claimed_pieces("enables all 20 pieces") != [20]:
        fails.append("claimed_pieces cannot read a digit")
    if claimed_pieces("enables all frobnitz pieces") != [-1]:
        fails.append("an unreadable number word must not pass as absent")
    if verdict_pieces(OK, 3, ROSTER)[0] != 0:
        fails.append("a MATCHING count and roster was rejected: %r"
                     % (verdict_pieces(OK, 3, ROSTER)[1],))
    if verdict_pieces(OK.replace("all 3", "all 4"), 3, ROSTER)[0] != 1:
        fails.append("a STALE piece count was accepted")
    if verdict_pieces("enables all 3 pieces\n### alpha · Stop\n", 3, ROSTER)[0] != 1:
        fails.append("a shipped piece with NO section was accepted - the roster half of this "
                     "gate is doing nothing, which is exactly the #40 defect")
    if verdict_pieces(OK + "### ghost · Stop\n", 3, ROSTER)[0] != 1:
        fails.append("a documented-but-not-shipped section was accepted")
    if verdict_pieces(OK, 0, ROSTER)[0] != 1:
        fails.append("an underivable count reported the same green as a real comparison")
    if verdict_pieces(OK, 3, set())[0] != 1:
        fails.append("an empty roster reported the same green as a real comparison")
    if verdict_pieces("### alpha · Stop\n### beta · Stop\n### meta-review · skill\n",
                      3, ROSTER)[0] != 1:
        fails.append("an ABSENT piece count passed, so the gate would compare nothing")
    # the display-name alias the real README relies on
    if not _matches("numbers-match", "numbers_match_on_write"):
        fails.append("the display-name alias no longer matches numbers_match_on_write")
    if _matches("alpha", "beta_hook"):
        fails.append("_matches is too loose - unrelated names collide")


def selftest() -> int:
    fails = []
    _selftest_pieces(fails)
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
