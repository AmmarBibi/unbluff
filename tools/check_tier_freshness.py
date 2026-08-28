#!/usr/bin/env python3
"""Has THIS WORKTREE verified each gate TIER since the code it covers last changed? [item 17]

WHY IT EXISTS. `tools/gate_ledger.py` records every gate run with a UTC stamp, so the data to
answer that question has existed for weeks. Nothing ASKED it. The gap was found by the close
completeness pass on 2026-08-26 as a SILENT one - the plan did not mention the `integration` tier
anywhere, so its freshness had never been scheduled OR excluded.

MEASURED, and it is why this is a gate and not a note: `integration` last ran
2026-08-24T18:42:34Z, predating every commit of a session that added two hook modules and two
`REQUIRED_HOOKS` entries `install.py` acts on. Re-running it returned 34/34, so nothing was
actually wrong - but "nothing was wrong" had been UNVERIFIED for a full session, and the only
mechanism that caught it was a human following the meta-review's CHECK 4 instruction to read a
JSON file by hand at the close.

FOUND ON ITS FIRST REAL RUN, which is the argument for it: `false_alarm_scorer` is declared in
RECORDING_TIERS and `unrecorded_tiers()` reports it as "still recording" - but that check is an
AST walk proving the CALL EXISTS, not that it ever EXECUTES. The tier is registered
`("--selftest",)` (adjudicated in SELFTEST_IS_THE_GATE), so the suite never reaches the enforcing
path where the call lives, and its newest row was EIGHT DAYS old while every gate was green.
Declared-and-present is not the same fact as recently-executed, and only this gate asks the
second one.

=============================================================================================
TRAP 1 - EXEMPTIONS, OR THIS GATE IS RED FOREVER AND GETS SWITCHED OFF.
=============================================================================================
`mutation_sweep` is KNOWN-STALE BY DESIGN and the plan has a section saying so: the full sweep
runs in CI on two platforms, and **a CI runner cannot write this local ledger**, so the newest
local row can permanently predate the fix that made the sweep green. A gate that is red forever
gets disabled, which is strictly worse than no gate - this repo has measured that four times in
two sessions. So the exemption is DECLARED, with its reason, in the same shape as NOT_A_GATE and
SELFTEST_IS_THE_GATE, and it is checked in BOTH directions: an exemption for a tier that is not
in RECORDING_TIERS is a failure, so the list cannot rot into cover.

NOTE the exemption is about where the tier CAN run, not about whether it is important. When the
sweep is run locally - as it was twice on 2026-08-28 - the local row IS current, and this gate
still PRINTS its status. Exempt means "cannot BLOCK", never "not shown".

=============================================================================================
TRAP 2 - PHRASING, AND IT IS LOAD-BEARING.
=============================================================================================
Every verdict says **"THIS WORKTREE has not verified <tier> since <commit>"**, never
"<tier> is stale". The ledger is gitignored and therefore per-worktree LOCAL state, deliberately
and by recorded design (item 21). A gate run proves something about the tree it ran in, so
"has THIS worktree verified this tier?" is the correct question and the per-worktree answer is
the right one - the two worktrees on this box legitimately disagree by ten days on one tier and
BOTH are correct. Stating a local record as a global fact is how the first write-up of item 21
concluded that a correct push-refusal was spurious.

=============================================================================================
MODES - a measurement by default, blocking only at a release. Same shape as review-freshness,
and for the same reason: after any commit, NO tier has verified that commit until it is re-run,
so a blocking default would fire on entirely correct work every single time.
=============================================================================================
  (default)   report every tier's status and return 0. A MEASUREMENT.
  --release   return 1 if any NON-EXEMPT tier has not been verified since HEAD.
"""

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from gate_registry import RECORDING_TIERS                       # noqa: E402
# [#46] The selftest below builds a throwaway git repository. Under a git hook - which is where
# this suite actually ships - git exports GIT_DIR, and GIT_DIR OVERRIDES `git -C <tmpdir>`, so an
# unscrubbed fixture silently operates on the REAL repository. Scrubbed at import, the same place
# and for the same reason as check_review_freshness.py:39, rather than at each call site: the
# damage in #46 came from call sites that passed no env at all, and a per-call-site obligation is
# precisely what failed.
from git_isolation import scrub_environ as _scrub_environ        # noqa: E402
_scrub_environ()

# gate name -> why it can never be required to be fresh IN THIS WORKTREE. Checked in BOTH
# directions by the selftest: a name here that is not a declared tier is a failure.
CANNOT_BLOCK = {
    "mutation_sweep":
        "the full sweep runs in CI on two platforms and a CI RUNNER CANNOT WRITE THIS LOCAL "
        "LEDGER, so the newest local row can permanently predate the code it verified. Requiring "
        "it to be fresh here would hold this gate red forever, and a gate that is red forever "
        "gets switched off. Its status is still PRINTED - exempt means cannot block, not hidden.",
}

VERIFIED, NOT_SINCE, NEVER, UNKNOWN = "VERIFIED", "NOT-SINCE", "NEVER", "UNKNOWN"


def _git(*args, **kw):
    """(stdout, error). Never raises - a gate that dies on a git hiccup answers nothing.

    `cwd=` targets another repository, which the selftest needs: it builds a throwaway repo with
    a commit at a KNOWN non-UTC offset, because the assertion below cannot depend on this repo's
    HEAD (see selftest).
    """
    cwd = kw.pop("cwd", None) or REPO
    if kw:
        return "", "unexpected keyword(s) %r" % sorted(kw)
    # TZ=UTC0 is LOAD-BEARING, not hygiene. `--date=format-local:` renders in the LOCAL zone, so
    # without it HEAD's commit date came back as "2026-08-28T03:08:30Z" for a commit made at
    # 03:08:30-04:00 - local time wearing a Z suffix, four hours early. That is a FAIL-OPEN
    # against UTC ledger stamps: a tier that ran at 07:07Z, genuinely BEFORE a 07:08Z commit,
    # compared as AFTER it and reported VERIFIED. Caught 2026-08-28 by reading this gate's own
    # first real output, NOT by its selftest, which used synthetic stamps and never called head().
    env = dict(os.environ)
    env["TZ"] = "UTC0"
    try:
        out = subprocess.run(["git", "-C", cwd] + list(args), stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True, env=env)
    except OSError as e:
        return "", "git could not be run (%s)" % e
    if out.returncode != 0:
        return "", (out.stderr or "").strip() or "git exited %d" % out.returncode
    return out.stdout.strip(), ""


def head() -> tuple:
    """(short_sha, iso8601_utc, error) for HEAD. UTC so it compares against ledger stamps."""
    sha, err = _git("rev-parse", "--short", "HEAD")
    if err:
        return "", "", err
    when, err = _git("show", "-s", "--format=%cd", "--date=format-local:%Y-%m-%dT%H:%M:%SZ",
                     "HEAD")
    if err:
        return sha, "", err
    return sha, when, ""


def evaluate(tiers=None, ledger_path=None, head_when=None, exempt=None) -> list:
    """[(gate, status, detail)] for every declared tier, sorted by gate name.

    A tier that cannot be READ is UNKNOWN, never VERIFIED. An unanswerable freshness question is
    not a passing one - that is this repo's most repeated defect, and the reason `read()` in
    gate_ledger was given three outcomes instead of two.
    """
    tiers = RECORDING_TIERS if tiers is None else tiers
    exempt = CANNOT_BLOCK if exempt is None else exempt
    try:
        import gate_ledger
        # Explicit path: gate_ledger's readers bind `path=LEDGER` at DEF time while record()
        # resolves it at CALL time, so a reassigned LEDGER is written and not read. See item 29.
        path = ledger_path or gate_ledger.LEDGER
    except Exception as e:
        return [(g, UNKNOWN, "the gate ledger could not be imported (%s), so THIS WORKTREE "
                             "cannot say when %s last ran" % (type(e).__name__, g))
                for g in sorted(set(tiers.values()))]
    rows = []
    for gate in sorted(set(tiers.values())):
        try:
            prev = gate_ledger.last_run(gate, path)
        except Exception as e:
            rows.append((gate, UNKNOWN, "the ledger could not be read (%s)" % type(e).__name__))
            continue
        if not prev:
            rows.append((gate, NEVER,
                         "THIS WORKTREE has NO recorded run of %s at all" % gate))
            continue
        when = prev.get("utc")
        if not when:
            rows.append((gate, UNKNOWN,
                         "THIS WORKTREE's newest %s row carries no timestamp" % gate))
            continue
        # String compare is correct here and deliberate: both sides are zero-padded ISO-8601 in
        # UTC, so lexical order IS chronological order. Parsing would add a dependency and a
        # timezone bug surface for no gain. The ledger writes "+00:00"; HEAD is formatted "Z";
        # both sort identically against a date prefix, which is the granularity that matters.
        if head_when and when[:19] < head_when[:19]:
            rows.append((gate, NOT_SINCE, "THIS WORKTREE has not verified %s since %s "
                                          "(last run %s, result %s)"
                         % (gate, head_when, when, prev.get("result", "?"))))
        else:
            rows.append((gate, VERIFIED, "last run %s, result %s"
                         % (when, prev.get("result", "?"))))
    return rows


def verdict(rows, exempt=None, release=False) -> tuple:
    """(rc, lines). Blocking is opt-in; the default run is a measurement."""
    exempt = CANNOT_BLOCK if exempt is None else exempt
    lines = []
    blocking = [(g, s, d) for g, s, d in rows
                if s in (NOT_SINCE, NEVER, UNKNOWN) and g not in exempt]
    if not release:
        return 0, lines
    if not blocking:
        lines.append("RELEASE OK: every non-exempt tier has been verified in THIS WORKTREE since "
                     "HEAD.")
        return 0, lines
    lines.append("RELEASE BLOCKED: %d non-exempt tier(s) have not been verified in THIS WORKTREE "
                 "since HEAD." % len(blocking))
    for g, s, d in blocking:
        lines.append("  %-10s %s" % (s, d))
    lines.append("Re-run them in THIS WORKTREE, or say in writing why the release does not need "
                 "them. An unanswerable freshness question is not a passing one.")
    return 1, lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--release", action="store_true",
                    help="block if a non-exempt tier has not been verified since HEAD")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    sha, when, err = head()
    rows = evaluate(head_when=when)
    # ALWAYS the denominator, and always the reference point. "0 stale" is meaningless without
    # knowing how many tiers were asked and what they were compared against.
    print("[tier-freshness] %d declared tier(s), compared against HEAD %s (%s)"
          % (len(rows), sha or "UNKNOWN", when or "commit date unavailable"))
    if err or not when:
        print("  NOTE: HEAD's commit date could not be read (%s), so NOTHING was compared. This "
              "is not a clean result." % (err or "no date"))
    for gate, status, detail in rows:
        mark = "exempt" if gate in CANNOT_BLOCK else ""
        print("  %-10s %-22s %s%s" % (status, gate, detail,
                                      "" if not mark else "  [%s]" % mark))
    for gate, why in sorted(CANNOT_BLOCK.items()):
        print("  EXEMPT %s: %s" % (gate, why))
    # The most likely MISREADING of this gate, said out loud rather than left for the next person
    # to rediscover: the normal order is run-the-suite THEN commit, so the moment a commit lands
    # every tier is NOT-SINCE by construction and none of them is "broken". That is why the
    # default is a measurement. --release is meant to be run AFTER the commit being shipped, so
    # that what gets verified is the exact tree that ships.
    if rows and all(s != VERIFIED for _g, s, _d in rows):
        print("  NOTE: every tier reads NOT-SINCE, which is what a fresh commit looks like - the "
              "usual order is verify-then-commit, so HEAD is newer than every run that verified "
              "its parent. Re-run at HEAD before a release; this is not evidence of a defect.")
    rc, lines = verdict(rows, release=args.release)
    for ln in lines:
        print(ln)
    if not args.release:
        print("  (measurement only - pass --release to make an unverified tier block)")
    return rc


def selftest() -> int:
    """The detector must SEE a stale tier and must NOT invent one. Both directions, plus scope."""
    import json
    import tempfile
    fails = []

    def ledger(rows):
        d = tempfile.mkdtemp(prefix="unbluff-tierfresh-")
        p = os.path.join(d, "gate_runs.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rows, f)
        return p

    tiers = {"a.py": "alpha", "b.py": "beta"}
    HEADW = "2026-08-28T12:00:00Z"

    # SHOULD FIRE: a run that predates HEAD
    p = ledger([{"gate": "alpha", "utc": "2026-08-20T09:00:00+00:00", "result": "PASS"},
                {"gate": "beta", "utc": "2026-08-28T13:00:00+00:00", "result": "PASS"}])
    got = dict((g, s) for g, s, _ in evaluate(tiers, p, HEADW, {}))
    if got.get("alpha") != NOT_SINCE:
        fails.append("a tier last run EIGHT DAYS before HEAD was not reported NOT-SINCE: %r"
                     % (got,))
    if got.get("beta") != VERIFIED:
        fails.append("a tier run AFTER HEAD was misreported as unverified: %r" % (got,))

    # PHRASING is the item's load-bearing requirement, so assert it rather than trusting it.
    detail = [d for g, _s, d in evaluate(tiers, p, HEADW, {}) if g == "alpha"][0]
    if "THIS WORKTREE has not verified" not in detail:
        fails.append("the verdict does not say THIS WORKTREE: %r" % detail)
    if "is stale" in detail:
        fails.append("the verdict says '<tier> is stale', which states a per-worktree record as "
                     "a global fact - the exact phrasing item 17 forbids: %r" % detail)

    # A tier with NO row must be NEVER, not VERIFIED - absence is not freshness.
    got = dict((g, s) for g, s, _ in evaluate({"c.py": "gamma"}, p, HEADW, {}))
    if got.get("gamma") != NEVER:
        fails.append("a tier with no recorded run at all was not reported NEVER: %r" % (got,))

    # An UNREADABLE ledger must be UNKNOWN, never VERIFIED.
    got = dict((g, s) for g, s, _ in evaluate(tiers, os.path.join(p, "nope", "x.json"),
                                              HEADW, {}))
    if set(got.values()) != {NEVER} and UNKNOWN not in set(got.values()):
        fails.append("an unreadable ledger did not fail closed: %r" % (got,))

    # BLOCKING is opt-in, and the exemption must actually exempt.
    rows = evaluate(tiers, p, HEADW, {})
    rc, _ = verdict(rows, {}, release=False)
    if rc != 0:
        fails.append("the DEFAULT run blocked; it must be a measurement or it fires on every "
                     "correct commit and gets switched off")
    rc, _ = verdict(rows, {}, release=True)
    if rc != 1:
        fails.append("--release did not block on a tier that has not been verified since HEAD")
    rc, _ = verdict(rows, {"alpha": "exempt for a written reason"}, release=True)
    if rc != 0:
        fails.append("an EXEMPT tier still blocked, so the exemption does nothing and this gate "
                     "would be red forever")

    # BOTH DIRECTIONS on the exemption roster: an exemption for a tier that is not declared is
    # cover, and a roster that cannot rot is the whole point of writing it down.
    unknown = sorted(set(CANNOT_BLOCK) - set(RECORDING_TIERS.values()))
    if unknown:
        fails.append("CANNOT_BLOCK exempts %r, which is in no RECORDING_TIERS row. An exemption "
                     "for a tier that does not exist is cover, not an adjudication." % unknown)
    for gate, why in CANNOT_BLOCK.items():
        if len(why) < 40:
            fails.append("CANNOT_BLOCK[%r] has no real reason written. An exemption without a "
                         "reason is the thing this roster exists to prevent." % gate)

    # head() MUST return UTC, and this assertion exists because the first version did NOT and the
    # synthetic-timestamp cases above all passed anyway. `--date=format-local:` renders the LOCAL
    # zone, so a commit at 03:08:30-04:00 came back as "03:08:30Z" - four hours early, which
    # compares as AFTER a UTC ledger stamp it actually precedes. A fail-open, in the direction
    # that reports UNVERIFIED work as VERIFIED. Checked against git's own %cI, which carries a
    # real offset, so this cannot agree with a wrong answer the way a second local read would.
    # THE UTC ASSERTION, and it is SELF-CONTAINED for a reason the sweep taught.
    #
    # v1 compared head() against this repo's own %cI. Mutation TF-UTC (delete `env["TZ"]="UTC0"`)
    # SURVIVED against it, twice. The cause was not the comparison - that comparison bites fine
    # against a real checkout, verified by hand. The cause is that mutation_check builds its
    # scratch tree with `git init -q` and `git add -A` and NEVER COMMITS, so `git show -s HEAD`
    # fails there, and v1 printed "the assertion did NOT run" and carried on. A SKIP SCORED AS A
    # PASS - the exact defect this repo hunts everywhere else, inside the probe meant to catch a
    # different one. The sweep saw it and no other signal did.
    #
    # So the assertion now builds its OWN repository with a commit at a KNOWN non-UTC offset.
    # It depends on nothing outside itself, cannot be skipped by an absent HEAD, and the
    # difference it looks for exists on every machine including a UTC one.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="unbluff-tf-utc-") as _td:
        # -05:00 is fixed in the fixture, so the expected UTC value is arithmetic, not a lookup.
        stamp, want_utc = "2026-01-02T03:04:05-05:00", "2026-01-02T08:04:05Z"
        env = dict(os.environ)
        env.update(GIT_COMMITTER_DATE=stamp, GIT_AUTHOR_DATE=stamp,
                   GIT_COMMITTER_NAME="t", GIT_AUTHOR_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t", GIT_AUTHOR_EMAIL="t@t")
        ok = True
        for cmd in (["init", "-q"], ["add", "-A"],
                    ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x",
                     "--allow-empty"]):
            r = subprocess.run(["git", "-C", _td] + cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, universal_newlines=True, env=env)
            if r.returncode != 0:
                fails.append("the UTC assertion could not build its fixture (%s: %s). It must "
                             "not be silently skipped - a skip scored as a pass is what let "
                             "TF-UTC survive twice." % (" ".join(cmd), (r.stderr or "").strip()))
                ok = False
                break
        if ok:
            got, gerr = _git("show", "-s", "--format=%cd",
                             "--date=format-local:%Y-%m-%dT%H:%M:%SZ", "HEAD", cwd=_td)
            if gerr or not got:
                fails.append("the UTC fixture produced no commit date (%s) - NOT a pass" % gerr)
            elif got[:19] != want_utc[:19]:
                fails.append("head()'s date format returned %r for a commit made at %s; in UTC "
                             "that is %s. LOCAL time labelled Z compares as LATER than it is, so "
                             "a tier that ran BEFORE a commit reports VERIFIED against it."
                             % (got, stamp, want_utc))

    print("-- tier-freshness: %d declared tier(s), %d exempt with a written reason; "
          "detector probed BOTH ways (sees an 8-day-old tier, does not flag a fresh one); "
          "date format asserted UTC against a self-built commit at a known -05:00 offset"
          % (len(set(RECORDING_TIERS.values())), len(CANNOT_BLOCK)))
    if fails:
        for f in fails:
            print("SELFTEST FAIL: %s" % f)
        return 1
    print("SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
