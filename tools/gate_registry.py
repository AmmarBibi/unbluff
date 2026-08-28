#!/usr/bin/env python3
"""THE GATE REGISTRY - which gates exist, which tools are not gates, and how each is judged.

WHY THIS IS ITS OWN MODULE (item 7, 2026-08-28). These five constants are the part of the
suite that grows every time a gate is added, and they lived in `run_selftests.py`. On
2026-08-25 that file sat at 803 lines against the 800-line ratchet with SIX lines of
headroom, so registering one gate with its reasoning pushed the orchestrator over the limit
and the next person hit the same wall. Splitting `selftest()` out bought headroom but did
not fix the cause: adding a gate still edited the orchestrator. Now it does not.

THE TRAP, AND IT IS WHY THIS DOCSTRING IS LONG. Two instruments read `AUX_GATES` OUT OF
SOURCE TEXT rather than importing it, and both hardcode the filename they read:

  * `tools/mutation_check.py:aux_gates()` - `ast.literal_eval` of the assignment, deliberately,
    so the rows it reads belong to the SCRATCH tree actually under test rather than to the
    live checkout. This is the instrument that certifies every other fix in this repo.
  * `hooks/piped_gate_guard.py`'s selftest - the same walk, to DERIVE its gate-token coverage
    denominator instead of hardcoding a roster (a hardcoded one left 3 enforcing gates
    invisible, the ship bar among them).

Moving the assignment breaks both. Both FAIL CLOSED - `mutation_check` returns
"no AUX_GATES assignment in ...", `piped_gate_guard` appends "could not read AUX_GATES ...
this check must never pass by failing to look" - so the move surfaces as a red harness and
not as a silent pass. They were repointed at THIS file in the same commit.

The plan named only the first of those two. The second, and the pinned mutation `MODE-1`
whose anchor is an `AUX_GATES` row, were found by grepping for the name before cutting
rather than by discovering them mid-refactor.

WHY THE READERS WERE NOT UNIFIED BEHIND ONE HELPER, given that this repo's own rule is
"two implementations of one rule is the defect" (run_selftests.py:40). `piped_gate_guard` is
a SHIPPED hook: `install.py` copies it to `~/.claude/hooks/`, where `tools/` does not exist.
Unifying would mean a shipped hook importing from a directory that is absent at its install
location, so the single implementation would have to be a conditional import that behaves
differently in the two places it runs. That trades eight duplicated lines of `ast` walk for a
conditional whose two branches nothing exercises together. Recorded as a DECISION, not an
oversight: the duplication is the cheaper defect, and both copies fail closed.

`RECORDING_TIERS` uses `os.path.join`, so this module imports `os`. Only `AUX_GATES` is ever
`literal_eval`d, and it is kept a pure literal for exactly that reason - no names, no calls.
"""

import os

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
    # [NO-NETWORK 2026-08-22] The README's `network - none` badge and its "no network, no
    # telemetry" line were enforced by NOTHING - promise_inventory RM-03 recorded that a hook
    # opening a connection would pass this suite, every AUX_GATE, the integration test and the
    # mutation sweep. On a public repo taking PRs, the front page's strongest trust claim was the
    # one with no gate behind it. Registered ENFORCING (argv ()), not --selftest: the measurement
    # over the real tree IS the gate, and registering the selftest would verify the detector while
    # applying it to nothing - the 2026-08-14 defect this repo already paid for twice.
    ("no-network", ("tools", "check_no_network.py"), ()),
    # the README advertises a Python floor; CI only exercises files it actually runs
    ("python-floor", ("tools", "check_python_floor.py"), ()),
    # a hook can name a skill the repo does not ship (close_skills_guard shipped requiring
    # four while only three were installed); nothing connected those lists until this gate
    ("skill-deps", ("tools", "check_skill_deps.py"), ()),
    # the review-freshness gate's own scope check: it asked about 17 of 31 tracked .py files
    # and could not detect its own sabotage until P13 A1
    ("review-freshness-scope", ("tools", "check_review_freshness.py"), ("--selftest",)),
    # [item 17 2026-08-28] "Has THIS WORKTREE verified each gate TIER since the code it covers
    # last changed?" The ledger has carried the data for weeks and nothing ASKED it; the gap was
    # found as a SILENT one - the plan mentioned the `integration` tier nowhere, so its freshness
    # was never scheduled OR excluded. Registered --selftest for the reason written in
    # SELFTEST_IS_THE_GATE below: after any commit EVERY tier is legitimately unverified, so the
    # measurement cannot be the enforced form without firing on correct work every time.
    # THIS ROW IS ALSO THE FIRST GATE ADDED SINCE THE REGISTRY CUT, and it is the proof item 7
    # wanted: registering it touched this file and not run_selftests.py.
    ("tier-freshness", ("tools", "check_tier_freshness.py"), ("--selftest",)),
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
    # [#46 2026-08-24] The env scrub and the repo fingerprint that keep temp fixtures off the
    # real repository. Registered ('--selftest',) because the ENFORCING half is not a separate
    # process at all - main() below fingerprints this repo before the sweep and after every
    # single gate, so the measurement runs 40-odd times a run rather than once. What needs its
    # own row is the question the inline control cannot ask itself: can this guard still tell a
    # hijacked `git -C` from a clean one? Its selftest reproduces the GIT_DIR override FIRST and
    # fails if the mechanism cannot be reproduced, so a future git that changed this behaviour
    # turns the row red instead of leaving a guard that quietly protects against nothing.
    ("git-isolation", ("tools", "git_isolation.py"), ("--selftest",)),
    # [#46 item 4] git_isolation PROVIDES the scrub; this asks if anything REACHES it. ENFORCING
    # because the measurement is the point: it found 5 files a hand roster of 3 missed.
    ("selftest-isolation", ("tools", "check_selftest_isolation.py"), ()),
    ("selftest-isolation-selftest", ("tools", "check_selftest_isolation.py"), ("--selftest",)),
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
    # This file. The registry is DATA - it declares no check and exposes no dispatch,
    # so it is not a gate; the gates that READ it are registered above and below. It has
    # to name itself here or classify_tools() fails on an undeclared tools/ file, which
    # is the check working exactly as intended.
    "gate_registry.py",
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
    # [SPLIT 2026-08-20] The no-regression gate's selftest apparatus - fixtures and assertions
    # A-G. Not a gate: it defines no check of its own and exposes no dispatch; it IS the selftest
    # of tools/no_regression.py, which is classified as a gate above. Same relationship as
    # hooks/*_selftest.py to their hooks.
    "noregress_selftest.py",
    # [SPLIT 2026-08-26, item 15] The provenance gate's selftest apparatus - the planted-offender
    # battery, its negative controls, and the item-15 count probes. Not a gate: it defines no
    # check of its own and exposes no dispatch; it IS the selftest of
    # tools/hook_divergence_report.py, which is registered as a gate above and DELEGATES to it,
    # so the gate that runs it is already classified. Same relationship as noregress_selftest.py.
    "hook_divergence_selftest.py",
    "compare_delivery_gate.py",     # measurement, produces numbers for the plan
    "measure_dispatcher_cost.py",   # measurement
    # [P14 B1] grades a cap-guard against tests/cap_spelling_corpus.py and prints the
    # denominator. Measurement, not a gate: it scores whatever guard it is pointed at, so it
    # has no pass/fail opinion of its own. Kept in the repo because the C1-NEW rebuild is
    # graded with it and a scorer that lives only in a scratchpad is a measurement nobody can
    # reproduce.
    "make_hook_screenshot.py",      # docs asset generation
    # [item 24 2026-08-28] Pure VIEW code for hook-provenance's ledger series - it shapes the
    # recorded fields and formats the trend sentence. Not a gate: it declares no check, has no
    # pass/fail opinion and exposes no dispatch. The gate that USES it is `hook-provenance`,
    # registered above, and the gate_ledger.record() CALL deliberately stayed in
    # hook_divergence_report.py so RECORDING_TIERS keeps naming the real tier.
    "hook_divergence_trend.py",
}

# [#45 2026-08-24] Labels whose SUBJECT is this machine's environment, not this repository's
# code. They are real gates and they run in every mode; what they are not is an opinion about
# whether a COMMIT is sound. Registered here rather than special-cased at the call site so that
# adding one is a deliberate, reviewable act with a written reason - the same shape as
# SELFTEST_IS_THE_GATE below, and for the same reason.
#
# WHY IT EXISTS. hook-provenance asks "is this box wired to a current copy of unbluff?". During
# any release the branch is legitimately AHEAD of the wired copy, so the gate correctly goes red
# and - because run_selftests is what .claude/pre-push.cmd runs - it BLOCKED the very push that
# would have fixed it. Measured 2026-08-24 at 1a0d649: 22 foreign refs, AST delta 66, the wired
# file confirmed by hash to be main:hooks/pre_push_gate.py, 91 insertions behind. A true finding
# about the machine, blocking a sound commit.
#
# THIS IS NOT A DISARM SWITCH, and the selftest proves it: under --code-only a CODE gate that
# fails still fails, and an excluded gate is still RUN, still PRINTED, and still named in the
# output with its reason. Only the verdict changes.
MACHINE_STATE = {
    "hook-provenance": "asks whether THIS MACHINE's wiring points at a current copy. A stale "
                       "wiring is worth knowing about and worth fixing, but it says nothing "
                       "about whether the commits being pushed are correct.",
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
    "tier-freshness":
        "same shape as review-freshness-scope, and for a MEASURED reason: the normal order is "
        "verify-then-commit, so the instant a commit lands EVERY tier is legitimately unverified "
        "at HEAD - observed 7 of 7 immediately after 0d9e8a5. Enforcing the measurement would "
        "therefore fire on entirely correct work every single time, and a guard that fires on "
        "correct work gets switched off. Its enforcing mode is --release, run AFTER the commit "
        "being shipped. The selftest is what carries the real assertions: that the detector SEES "
        "a tier eight days behind, does NOT flag one that ran after HEAD, treats a missing row "
        "as NEVER rather than fresh, keeps the per-worktree phrasing item 17 requires, and reads "
        "HEAD in UTC - that last one caught a live fail-open where local time wore a Z suffix",
    "selftest-isolation-selftest":
        "the PAIRED row; 'selftest-isolation' runs the measurement enforcing. This half asks "
        "what its subject cannot: can the detector still SEE an unscrubbed fixture? A blind "
        "detector reports a clean population exactly like a clean one.",
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
    # [item 24 2026-08-28] BUILT IS NOT LIVE needs a TRAJECTORY, not a point-in-time print, and
    # this row is what makes the recording enforced rather than merely present: unrecorded_tiers()
    # checks it by AST, in both directions, so deleting the call reddens the suite. The plan
    # asserted this gate "already calls into that path" - it did not, and had no ledger call at
    # all, which is why the row carried a confirm-don't-assume note.
    os.path.join("tools", "hook_divergence_report.py"): "hook_provenance",
}
