#!/usr/bin/env python3
"""Score every WIRED hook's FALSE-ALARM rate on ordinary correct work. [criterion 3]

"Each hook's FALSE-ALARM rate on ordinary correct code is MEASURED and recorded." A guard that
fires on correct code gets switched off, which is strictly worse than no guard - so this is the
criterion that decides whether the suite is good for anyone but its author.

WHAT THIS REPLACES. tools/score_corpus.py calls `guard.slicing_offenders(hooks_dir)` and nothing
else, so it scores exactly one detector and 0 of the 16 hooks install.py actually wires. The
guards criterion 3 cares about read a Claude Code EVENT PAYLOAD on stdin. This runs them that
way, through their real entry points.

FOUR RULES, each earned from a defect in this repo's own record:

 1. THROUGH THE REAL ENTRY POINT. A subprocess fed a payload on stdin, never an imported
    helper. Hollow-pin mode 3 is "helper tested, CALL SITE not", and FASTTEST-BLOCK's detector
    looked fine while the decision path hard-blocked seven repo shapes.

 2. FRESH STATE PER ENTRY. plan_defer_guard, numbers_match_on_write, timing_claim_guard,
    memory_hygiene_guard and meta_audit_on_stop all keep a once-per-(session, path) marker
    under UNBLUFF_STATE_DIR. Reuse one state dir and a hook fires ONCE and is silent forever
    after - which a scorer would report as a superb false-alarm rate. Every entry gets its own
    state dir, its own ledger and its own session id.

 3. A QUIET HOOK MUST PROVE IT LOOKED. Several hooks are OPT-IN and exit 0 without reading
    anything. So each hook's score is reported ONLY if at least one CONTROL for that hook
    actually fired in this run; otherwise the hook is UNMEASURED - never 0%. An extractor that
    finds nothing and an extractor pointed at the wrong place are the same output, and this
    repo has been burned by exactly that.

 4. PRINT THE DENOMINATOR, DERIVED. The roster comes from install.desired_groups(), not a list
    typed here - ROSTER-DERIVE found 7 of 25 hooks reaching a roster only because someone typed
    them. Anything EXCLUDED is printed WITH ITS REASON.

Usage:  python tools/score_false_alarms.py [--selftest]
"""

import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

sys.path.insert(0, os.path.join(REPO, "hooks"))

import duplicate_registration_check as dup     # noqa: E402
import false_alarm_corpus as corpus            # noqa: E402
import install                                 # noqa: E402

# rate_prompt is EXCLUDED, and loudly. It is not a guard: it injects a standing instruction on
# every prompt by design, so "it emitted output on correct work" is its success condition, not
# a false alarm. Scoring it would put a 100% rate in a table where every other row means the
# opposite. Named here with its reason rather than quietly dropped.
EXCLUDED = {
    "rate_prompt.py": "injects a standing instruction on EVERY prompt BY DESIGN - firing is "
                      "its success condition, not a false alarm",
}

# Events this corpus can drive today. SessionStart is NOT here: hook_health_check,
# duplicate_registration_check and usage_snip_prompt report on the MACHINE's configuration
# rather than on the user's work, so "ordinary correct code" is not their input at all and a
# corpus of edited files would score them vacuously. Declared, not silently skipped.
DRIVEN = ("PreToolUse", "PostToolUse", "Stop")
UNDRIVEN_REASON = ("SessionStart hooks audit the machine's own configuration, not the user's "
                   "work - they need a config corpus, not a code corpus")


def wired_scripts() -> dict:
    """{event: [script basename]} for everything install.py actually wires. DERIVED."""
    out = {}
    for event, group in install.desired_groups().items():
        names = []
        for entry in group.get("hooks", []):
            cmd = entry.get("command", "")
            for tok in cmd.replace("\\", "/").split('"'):
                if tok.strip().endswith(".py"):
                    names.append(os.path.basename(tok.strip()))
        out[event] = names
    return out


def run_entry(script: str, payload: dict, cwd: str, state: str, ledger: str, extra_env=None):
    """Run one hook through its real entry point. Returns (rc, stdout, stderr, ledger rows)."""
    env = dict(os.environ)
    env.update(entry_env(state, ledger))
    if extra_env:
        env.update(extra_env)
    try:
        p = subprocess.run([sys.executable, os.path.join(REPO, "hooks", script)],
                           input=json.dumps(payload), capture_output=True, text=True,
                           timeout=180, cwd=cwd, env=env, encoding="utf-8", errors="replace")
        rc, out, err = p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        # a hook that HANGS is the worst false alarm there is: it blocks the turn and says
        # nothing. Scored as a fire, never skipped.
        return (None, "", "TIMEOUT", [])
    rows = []
    if os.path.isfile(ledger):
        for line in open(ledger, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    return (rc, out, err, rows)


def unit_name(script: str) -> str:
    """The name a hook is scored under: its module stem. Unambiguous by construction.

    An earlier version scored dispatcher sub-hooks by the SHORT name their ledger uses
    ("defer", "timing") and directly-wired hooks by the script stem. Two spellings for one
    concept, and the corpus could not refer to both - the controls silently never matched and
    every row read UNMEASURED. One spelling, derived from the file.
    """
    return os.path.basename(script)[:-3] if script.endswith(".py") else script


def fired(rc, err) -> bool:
    """Did this hook OBJECT to the input?

    rc alone is WRONG and it cost a wrong conclusion before it was caught: timing_claim_guard
    is ADVISORY - it prints its finding to stderr and returns 0. Scoring by rc recorded it as
    silent on an input it had just objected to in full.

    That also corrects the fire LEDGER as evidence: the dispatchers record each sub-hook's rc,
    so a ledger reading `timing: 0` across 1252 invocations means "never BLOCKED", not "never
    fired". Retiring a guard on that number would have been retiring it on a false zero.
    """
    return rc not in (0, None) or bool((err or "").strip())


def entry_env(state: str, ledger: str) -> dict:
    """Every piece of hook state this tool redirects, so a measurement is REPRODUCIBLE.

    A FUNCTION rather than three inline assignments, so its guarantee can be asserted directly
    (see the selftest) instead of only by observing a hook's behaviour afterwards.

    UNBLUFF_PROJECTS_ROOT is the one that is easy to forget: memory_hygiene_guard resolves a
    per-project memory dir under it and it defaults to the REAL ~/.claude/projects, so leaving
    it unset made that hook's rate depend on whose machine ran the tool. Same class as the
    marker directory fixed in timing_claim_guard on the same day.
    """
    projects = os.path.join(os.path.dirname(state), "_projects")
    os.makedirs(projects, exist_ok=True)
    return {"UNBLUFF_STATE_DIR": state,
            "UNBLUFF_LEDGER_PATH": ledger,
            "UNBLUFF_PROJECTS_ROOT": projects}


def repeats_in_session(script, payload, cwd, state, ledger, extra_env=None) -> bool:
    """Does this hook object AGAIN on the same input, in the SAME session?

    A guard that objects once and then goes quiet is a NOTICE. One that repeats every turn is
    what actually gets a guard switched off - which is the behaviour criterion 3 exists to
    prevent. Reporting only the first invocation reports the harsher number and hides a
    deliberate design: memory_hygiene_guard's inconclusive notice measured 100% here purely
    because this tool gives every corpus entry a FRESH state dir, defeating the once-per-
    session marker that bounds it in real use. It was nearly "fixed" on that evidence.

    A FUNCTION, not an inline condition, so its probe and its mutation reach the same code -
    the first attempt pinned the call site while the selftest exercised a helper, the mutation
    SURVIVED, and the harness said so (hollow-pin mode 3: helper tested, CALL SITE not).
    """
    rc2, _out2, err2, _rows2 = run_entry(script, payload, cwd, state, ledger, extra_env)
    return fired(rc2, err2)


def scored_scripts() -> dict:
    """{event: [script]} - every hook a corpus entry can put in front of, DERIVED.

    Both the directly wired hooks (install.desired_groups) AND the dispatcher sub-hooks
    (install.dispatcher_subhooks, itself derived from the dispatchers' ASTs). The sub-hooks
    are scored as THEMSELVES rather than through the dispatcher's aggregate exit code,
    because that aggregate cannot say which sub-hook objected - and because an advisory
    sub-hook does not move it at all.
    """
    by_event = {}
    for event, group in install.desired_groups().items():
        names = []
        for entry in group.get("hooks", []):
            cmd = entry.get("command", "")
            for tok in cmd.replace("\\", "/").split('"'):
                if tok.strip().endswith(".py"):
                    names.append(os.path.basename(tok.strip()))
        # Each dispatcher's OWN sub-hooks, per dispatcher - not the merged set. Merging them
        # would score Stop's guards against a PostToolUse payload and inflate every
        # denominator with runs the event never routes.
        expanded = list(names)
        for n in names:
            for mod in dup.dispatched_modules(os.path.join(REPO, "hooks", n)):
                if mod + ".py" not in expanded:
                    expanded.append(mod + ".py")
        by_event[event] = expanded
    return by_event


def score():
    """(per_hook, controls, skipped) - the measurement. Writes nothing under the repo."""
    per_hook = {}      # hook -> {"exercised": n, "false_alarms": [entry names]}
    controls = {}      # hook -> {"total": n, "fired": n}
    entrypoint = {}
    wired = scored_scripts()
    for event in DRIVEN:
        entrypoint[event] = [n for n in wired.get(event, []) if n not in EXCLUDED]

    for name, event, must_fire, exercises, _why, build in corpus.ENTRIES:
        if event not in DRIVEN:
            continue
        for script in entrypoint.get(event, []):
            unit = unit_name(script)
            # An entry is scored ONLY against the hooks it claims to exercise. Without this
            # the same payload counts against every hook in the event, which inflates each
            # denominator with runs that prove nothing and dilutes every rate it prints.
            if unit not in exercises:
                continue
            with tempfile.TemporaryDirectory(prefix="unbluff-fa-") as td:
                state = os.path.join(td, "_state")
                os.makedirs(state, exist_ok=True)
                ledger = os.path.join(td, "_ledger.jsonl")
                # build() returns a payload, or (payload, extra_env) when the entry needs to
                # point a hook at a fixture root - kept optional so the 15 entries that need
                # no environment stay one-liners.
                built = build(td)
                payload, entry_env = built if isinstance(built, tuple) else (built, None)
                rc, _out, err, _rows = run_entry(script, payload, td, state, ledger, entry_env)
                did = fired(rc, err)
                if must_fire:
                    c = controls.setdefault(unit, {"total": 0, "fired": 0})
                    c["total"] += 1
                    c["fired"] += 1 if did else 0
                else:
                    h = per_hook.setdefault(unit, {"exercised": 0, "false_alarms": [],
                                                   "nags": []})
                    h["exercised"] += 1
                    if did:
                        h["false_alarms"].append((name, (err or "").strip()[:120]))
                        # DOES IT NAG? Re-run with the SAME state dir and session. Several
                        # guards suppress a repeat via a once-per-session marker, and that is
                        # the difference between a notice and the thing that gets a guard
                        # switched off. Measuring only the first invocation reports the
                        # harsher number and hides a deliberate design - which nearly cost a
                        # working guard on 2026-08-13.
                        if repeats_in_session(script, payload, td, state, ledger, entry_env):
                            h["nags"].append(name)
    return per_hook, controls, entrypoint


def rate_for(exercised: int, false_alarms: int, controls_fired: int) -> str:
    """The reported false-alarm rate, or UNMEASURED.

    A hook whose CONTROL never fired has not been shown to be REACHABLE, so its silence is not
    evidence of anything - it may simply never have run. Printing 0% there is precisely the
    failure this tool exists to prevent, and it nearly happened twice while this file was being
    written (a name mismatch, then a hook that ignored UNBLUFF_STATE_DIR). It is a function
    rather than an inline condition so that a mutation can prove the rule still bites.
    """
    if controls_fired <= 0 or exercised <= 0:
        return "UNMEASURED"
    return "%.1f%%" % (100.0 * false_alarms / exercised)


def main() -> int:
    per_hook, controls, entrypoint = score()
    negatives = [e for e in corpus.ENTRIES if not e[2]]
    positives = [e for e in corpus.ENTRIES if e[2]]

    print("== false-alarm rate on ordinary correct work ==")
    print("corpus: %d ordinary entr(ies) + %d control(s) = %d, across %d driven event(s) %r"
          % (len(negatives), len(positives), len(corpus.ENTRIES), len(DRIVEN), list(DRIVEN)))
    for event, names in entrypoint.items():
        print("  %-12s entry point(s): %s" % (event, ", ".join(names) or "(none)"))
    for script, why in EXCLUDED.items():
        print("  EXCLUDED %s - %s" % (script, why))
    print("  NOT DRIVEN: SessionStart - %s" % UNDRIVEN_REASON)
    print()

    # EVERY hook in the derived roster gets a row, including ones no corpus entry exercises.
    # [source-coverage 2026-08-13] Reporting only the hooks that HAPPEN to be covered made the
    # results table its own denominator: the roster held 11 and the table printed 8, so
    # post_tooluse_dispatcher, close_skills_guard and stop_dispatcher were absent rather than
    # visibly uncovered. A reader counting rows would infer the wrong population - which is the
    # exact failure rule 4 exists to prevent, committed by the tool that states rule 4.
    roster = sorted({unit_name(s) for names in entrypoint.values() for s in names})
    print("%-24s %10s %12s %14s  %s"
          % ("hook", "exercised", "FALSE ALARM", "rate", "control"))
    unmeasured, alarms, uncovered = [], [], []
    for hook in sorted(set(roster) | set(per_hook) | set(controls)):
        h = per_hook.get(hook, {"exercised": 0, "false_alarms": [], "nags": []})
        c = controls.get(hook, {"total": 0, "fired": 0})
        n, fa = h["exercised"], len(h["false_alarms"])
        rate = rate_for(n, fa, c["fired"])
        if rate == "UNMEASURED":
            unmeasured.append(hook)
        if fa:
            alarms.extend((hook, name, msg) for name, msg in h["false_alarms"])
        if n == 0 and c["total"] == 0:
            uncovered.append(hook)
            rate = "NO-CORPUS-ENTRY"
        print("%-24s %10d %12d %14s  %d/%d fired"
              % (hook, n, fa, rate, c["fired"], c["total"]))

    print()
    for hook, name, msg in alarms:
        nags = name in per_hook.get(hook, {}).get("nags", [])
        print("FALSE ALARM: %s fired on %r [%s] -> %s"
              % (hook, name,
                 "NAGS - repeats in the same session" if nags
                 else "once per session, then SILENT - a notice, not nagging",
                 msg or "(no message)"))
    for hook in unmeasured:
        if hook in uncovered:
            continue
        print("UNMEASURED: %s - no control fired, so a quiet result here is not evidence "
              "that it stays quiet; it may simply never have run" % hook)
    for hook in uncovered:
        print("NO CORPUS ENTRY: %s is WIRED but no corpus entry exercises it - it is not "
              "measured, and it is listed here so the table cannot become its own denominator"
              % hook)

    # A control that does not fire means the harness never reached the hook. Reporting a rate
    # anyway is the failure this tool exists to prevent, so it is an ERROR, not a footnote.
    dead = [h for h, c in controls.items() if c["fired"] == 0]
    if dead:
        print("\nHARNESS ERROR: control(s) for %r never fired - the payload shape is wrong or "
              "the hook is unreachable, and every quiet result above is an artefact" % dead)
        return 1
    # The three buckets are computed as SETS and asserted to partition the roster. They were
    # briefly subtracted as counts, and because an uncovered hook lands in BOTH `unmeasured`
    # and `uncovered` the subtraction double-counted and reported 1 MEASURED where there were
    # 4 - a denominator bug in the tool whose fourth rule is "print the denominator".
    no_entry = set(uncovered)
    unproven = set(unmeasured) - no_entry
    measured = set(roster) - unproven - no_entry
    assert len(measured) + len(unproven) + len(no_entry) == len(roster), "buckets must partition"
    print("\n%d wired hook(s) in the derived roster = %d MEASURED + %d UNMEASURED (no firing "
          "control) + %d NO CORPUS ENTRY; %d false alarm(s) on %d ordinary entr(ies)"
          % (len(roster), len(measured), len(unproven), len(no_entry),
             len(alarms), len(negatives)))
    # Criterion 3's numbers are a PUBLISHED claim, so when they were last measured has to be
    # answerable from the record rather than from a commit message.
    try:
        import gate_ledger
        gate_ledger.record("false_alarm_scorer", "FAIL" if alarms else "PASS",
                           measured=len(measured), unmeasured=len(unproven),
                           no_corpus_entry=len(no_entry), false_alarms=len(alarms),
                           nagging=len([1 for h in per_hook.values() if h.get("nags")]),
                           ordinary_entries=len(negatives))
    except Exception:
        pass
    return 1 if alarms else 0


def selftest() -> int:
    """The scorer is itself a checking instrument, so it gets checked.

    On 2026-08-12 EVERY defect found after the adversarial pass was in an instrument rather
    than in the product. The two failure modes that matter here are (a) reporting a rate for a
    hook that never ran, and (b) counting one corpus entry against a hook the event does not
    route to.
    """
    fails = []
    if not corpus.ENTRIES:
        fails.append("the corpus is EMPTY - the scorer would report a perfect score")
    names = [e[0] for e in corpus.ENTRIES]
    if len(names) != len(set(names)):
        fails.append("duplicate corpus entry name(s) - the report cannot name them apart")
    if not any(e[2] for e in corpus.ENTRIES):
        fails.append("the corpus has NO controls, so nothing proves the harness reaches any "
                     "hook and every 0%% it prints would be an artefact")
    for e in corpus.ENTRIES:
        if len(e) != 6:
            fails.append("corpus entry %r has %d field(s), expected 6" % (e[0], len(e)))
        elif not e[3]:
            fails.append("corpus entry %r declares no `exercises` hooks, so it is scored "
                         "against nothing" % (e[0],))

    # (a) a hook with no firing control must be UNMEASURED, never 0%. Asserted through the
    # REAL decision function - an earlier version of this check compared two local dicts to
    # each other and exercised none of the reporting code, i.e. it was decorative, which is
    # the defect class this repo exists to catch appearing inside its own new instrument.
    if rate_for(5, 0, 0) != "UNMEASURED":
        fails.append("a hook with 5 quiet runs and NO firing control was given a rate - "
                     "silence from an unreachable hook would read as a perfect score")
    if rate_for(0, 0, 3) != "UNMEASURED":
        fails.append("a hook that was never exercised was given a rate")
    if rate_for(5, 0, 1) != "0.0%":
        fails.append("a hook with a firing control and no false alarms must report 0.0%%")
    if rate_for(4, 1, 1) != "25.0%":
        fails.append("the rate arithmetic is wrong: 1 of 4 must be 25.0%%")

    # (b) an ADVISORY hook fires with rc 0 and a message. Scoring by rc alone recorded
    # timing_claim_guard as silent on an input it had just objected to in full, which is
    # also why a fire-ledger zero means "never BLOCKED" rather than "never fired".
    if not fired(0, "[timing-claim] 1 duration stated as MEASURED with no control"):
        fails.append("an ADVISORY fire (rc 0 + a message on stderr) was scored as silence - "
                     "every advisory guard would read as a perfect 0%")
    if fired(0, "   \n"):
        fails.append("whitespace on stderr was scored as a fire")
    if not fired(2, ""):
        fails.append("a BLOCKING rc with no message was scored as silence")

    # (c) NAG DETECTION, exercised against a real hook in each direction. A guard that objects
    # once and then goes quiet is a NOTICE; one that repeats every turn is what actually gets a
    # guard switched off. Reporting only the first invocation nearly cost a working guard on
    # 2026-08-13 - memory_hygiene_guard's inconclusive notice measured 100% because this tool
    # gives every entry a fresh state dir, which defeats the very suppression that bounds it.
    import tempfile as _tf
    with _tf.TemporaryDirectory(prefix="unbluff-nag-") as _td:
        _st = os.path.join(_td, "s")
        os.makedirs(_st, exist_ok=True)
        _lg = os.path.join(_td, "l.jsonl")
        # piped_gate_guard keeps NO session marker: it must object every single time.
        _pl = {"tool_name": "Bash",
               "tool_input": {"command": "python run_selftests.py | tail -2"}}
        run_entry("piped_gate_guard.py", _pl, _td, _st, _lg)          # first turn
        if not repeats_in_session("piped_gate_guard.py", _pl, _td, _st, _lg):
            fails.append("a guard with NO session marker was not detected as repeating - the "
                         "nag column would report every guard as a harmless one-off notice")
        # memory_hygiene_guard DOES keep one: it must go quiet on the second run.
        _pr = os.path.join(_td, "proj")
        os.makedirs(_pr, exist_ok=True)
        _mp = {"session_id": "nagcheck", "cwd": _td, "stop_hook_active": False}
        _env = {"UNBLUFF_PROJECTS_ROOT": _pr}
        run_entry("memory_hygiene_guard.py", _mp, _td, _st, _lg, _env)
        if repeats_in_session("memory_hygiene_guard.py", _mp, _td, _st, _lg, _env):
            fails.append("a guard WITH a once-per-session marker repeated on the second run - "
                         "either the marker broke or this probe is not sharing state")

    # (d) ISOLATION, which is what makes any of these numbers PORTABLE. Without it
    # memory_hygiene_guard resolves against the maintainer's real ~/.claude/projects, so the
    # answer depends on whose machine ran the tool - a regression nobody would notice, because
    # the table would still look perfectly reasonable.
    with _tf.TemporaryDirectory(prefix="unbluff-iso-") as _td2:
        _st2 = os.path.join(_td2, "state")
        _env2 = entry_env(_st2, os.path.join(_td2, "l.jsonl"))
        real_home = os.path.join(os.path.expanduser("~"), ".claude")
        for var in ("UNBLUFF_STATE_DIR", "UNBLUFF_LEDGER_PATH", "UNBLUFF_PROJECTS_ROOT"):
            if var not in _env2:
                fails.append("%s is not isolated - the hook would read or write the user's "
                             "real state, and the measurement would not reproduce" % var)
            elif os.path.abspath(_env2[var]).startswith(os.path.abspath(real_home)):
                fails.append("%s points INSIDE the real ~/.claude (%r)" % (var, _env2[var]))

    # the roster must be DERIVED and non-empty, or rule 4 is decorative
    wired = scored_scripts()
    if not wired.get("PreToolUse") or not wired.get("PostToolUse"):
        fails.append("scored_scripts() derived NOTHING for a driven event - the roster is not "
                     "coming from install.desired_groups()")
    if "piped_gate_guard.py" not in wired.get("PreToolUse", []):
        fails.append("the derived PreToolUse roster does not contain piped_gate_guard.py")
    # sub-hooks must be attributed to their OWN dispatcher's event, not merged
    if "plan_defer_guard.py" not in wired.get("PostToolUse", []):
        fails.append("PostToolUse did not expand to its dispatcher's sub-hooks")
    if "fast_test_on_stop.py" in wired.get("PostToolUse", []):
        fails.append("a Stop sub-hook was attributed to PostToolUse - the two dispatchers' "
                     "rosters were merged, which inflates every denominator")
    if "show_your_proof.py" not in wired.get("Stop", []):
        fails.append("Stop did not expand to its dispatcher's sub-hooks")

    # every hook a corpus entry NAMES must actually be in the derived roster for its event,
    # or the entry silently scores nothing at all
    for e in corpus.ENTRIES:
        if len(e) != 6:
            continue
        roster = {unit_name(s) for s in wired.get(e[1], [])}
        for hook in e[3]:
            if hook not in roster:
                fails.append("corpus entry %r exercises %r, which is not wired for %s - the "
                             "entry scores NOTHING and would look like a pass"
                             % (e[0], hook, e[1]))

    print("-- false-alarm scorer: %d corpus entr(ies) (%d control(s)), %d driven event(s)"
          % (len(corpus.ENTRIES), sum(1 for e in corpus.ENTRIES if e[2]), len(DRIVEN)))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
