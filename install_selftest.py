"""Selftest suite for install.py - split out to keep the installer under the 800-line rule.

Imported by install.py's `--selftest` dispatch; not a hook and not registered anywhere. The
split follows the precedent already set by pre_push_gate.py / pre_push_gate_selftest.py, and it
was done rather than re-recording the size baseline a fourth time: that file states in its own
text that "RE-RECORDING IS THE LOOPHOLE IN THIS DESIGN" and that the next growth should be
preceded by the split. install.py had reached 1006 lines carrying the #46-adjacent
`_import_closure` fix and its pins; without the selftest it is back under the limit outright,
so it leaves the offender list instead of being re-recorded higher.

REBINDING RULE, inherited verbatim from the sibling split and equally load-bearing here: the
parent's production code reads the PARENT module's globals. A plain assignment to a name that
also exists in install.py would rebind it HERE and leave install.py reading the old one, so the
test would keep passing while testing nothing. Every rebind therefore goes through
`_m.<name> = ...`, and every read of a rebindable name through `_m.<name>`.
"""

from __future__ import annotations

import install as _m

# Snapshot the parent's namespace so the test body can use bare names (including the underscored
# helpers `from x import *` would skip). READS only - see the rebinding rule above.
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})


def selftest() -> int:
    """Verify the partial-checkout guard actually detects a partial checkout.

    install.py had NO selftest at all - the most user-facing file in the repo, the one a user
    literally runs, was a registered gate nowhere. That is why the defect below survived every
    review: nothing ever asked this file a question.
    """
    fails = []
    checked = 0
    with tempfile.TemporaryDirectory() as td:
        scratch = os.path.join(td, "hooks")
        shutil.copytree(HOOKS_DIR, scratch,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

        # A full checkout must be clean, or every case below is meaningless.
        base = missing_hook_files(scratch)
        if base:
            fails.append("a COMPLETE hooks/ reported missing files %r - the guard's baseline is "
                         "broken, so nothing it says about a partial checkout can be trusted"
                         % (base,))

        # DERIVED, not a hand-picked victim: delete each hooks/*.py in turn and require the
        # guard to name it. A roster-shaped guard that is only ever probed with a name already
        # ON its roster proves nothing about the names that are not.
        names = sorted(f for f in os.listdir(scratch) if f.endswith(".py"))
        undetected = []
        for name in names:
            path = os.path.join(scratch, name)
            with open(path, "rb") as f:
                body = f.read()
            os.remove(path)
            try:
                checked += 1
                if name not in missing_hook_files(scratch):
                    undetected.append(name)
            finally:
                with open(path, "wb") as f:
                    f.write(body)
        if undetected:
            fails.append("the partial-checkout guard did NOT detect %d of %d deleted hook "
                         "file(s): %r. install would print 'Done.' over a checkout that cannot "
                         "run - the dispatchers import these at runtime"
                         % (len(undetected), len(names), undetected))

        # The sys.path blocking in _resolves_outside, pinned by the ONE case where it decides
        # the answer. For a DELETED file the blocking is inert - find_spec misses it either way -
        # so a probe that only deletes leaves that code unpinned, which is how unpinned code
        # ships. It matters TRANSITIVELY: with the hooks dir on sys.path and no blocking, a
        # PRESENT intermediate resolves as "external", is never traversed, and everything
        # reachable only through it drops out of the required set silently.
        #
        # Chain used, derived by picking a leaf reached only via present intermediates:
        # a wired hook -> capped_report -> cap_shapes -> cap_types.
        leaf = "cap_types.py"
        if os.path.exists(os.path.join(scratch, leaf)):
            with open(os.path.join(scratch, leaf), "rb") as f:
                body = f.read()
            os.remove(os.path.join(scratch, leaf))
            sys.path.insert(0, scratch)     # the state that makes the blocking load-bearing
            try:
                checked += 1
                if leaf not in missing_hook_files(scratch):
                    fails.append("with the hooks dir ON sys.path, a transitively-required file "
                                 "(%s, reached via capped_report -> cap_shapes) went UNDETECTED "
                                 "- the present intermediates resolved as external and were "
                                 "never traversed" % leaf)
            finally:
                sys.path.remove(scratch)
                with open(os.path.join(scratch, leaf), "wb") as f:
                    f.write(body)
        else:
            fails.append("the sys.path-blocking probe could not find its anchor %r - re-derive "
                         "the chain rather than leaving this case silently unrun" % leaf)

    # ENTRY-GUARD: the same probe against the OTHER thing install.py lands - the skills.
    skill_checked = 0
    with tempfile.TemporaryDirectory() as td:
        sk = os.path.join(td, "skills")
        shutil.copytree(SKILLS_DIR, sk,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if missing_skill_files(sk):
            fails.append("a COMPLETE skills/ reported missing files %r - baseline broken"
                         % (missing_skill_files(sk),))
        # DERIVED: every SKILL.md, and every bundled script reachable from one, deleted in turn.
        victims = []
        for name in SKILL_NAMES:
            victims.append(os.path.join(sk, name, "SKILL.md"))
            sdir = os.path.join(sk, name, "scripts")
            if os.path.isdir(sdir):
                victims += [os.path.join(sdir, f) for f in sorted(os.listdir(sdir))
                            if f.endswith(".py")]
        undetected_s = []
        for path in victims:
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                body = f.read()
            os.remove(path)
            try:
                skill_checked += 1
                if not missing_skill_files(sk):
                    undetected_s.append(os.path.relpath(path, sk))
            finally:
                with open(path, "wb") as f:
                    f.write(body)
        if undetected_s:
            fails.append("the skill guard did NOT detect %d of %d deleted skill file(s): %r. "
                         "install would exit 0 while close_skills_guard - a WIRED hook - "
                         "demands all of %r and blocks every session close"
                         % (len(undetected_s), len(victims), undetected_s, list(SKILL_NAMES)))

    # The optional-import rule, probed SYNTHETICALLY so the answer does not depend on what
    # happens to be installed. The real defect was invisible on the authoring machine because
    # it HAD python-docx; CI did not, and reported three files that never existed. A probe
    # reading the real scripts would reproduce exactly that split.
    synth = 0
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "scripts")
        os.makedirs(d)
        with open(os.path.join(d, "seed.py"), "w", encoding="utf-8") as f:
            f.write("try:\n    import unbluff_absent_xyz\n"
                    "except ImportError:\n    unbluff_absent_xyz = None\n"
                    "import unbluff_present_xyz\n")
        with open(os.path.join(d, "unbluff_present_xyz.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        closure = _import_closure(d, ["seed.py"])
        synth += 1
        if "unbluff_absent_xyz.py" in closure:
            fails.append("an import guarded by try/except ImportError was treated as REQUIRED. "
                         "On any machine lacking that optional library the guard reports a file "
                         "that never existed as missing - this turned all 16 CI jobs red")
        # And the rule must not be OVER-applied: an unguarded local import is still required.
        synth += 1
        if "unbluff_present_xyz.py" not in closure:
            fails.append("an UNGUARDED local import was dropped from the closure - the "
                         "optional-import rule is over-applied and genuinely missing files "
                         "would go unreported, which is the defect this guard exists to catch")

    # [LAZY-SCOPE 2026-08-24] The SECOND instance of the optional-import class, and the two
    # populations disagree - so BOTH directions are pinned, synthetically, in one fixture.
    # skills/ imports its readers inside functions (fitz, pdfminer) and its siblings at module
    # level; hooks/ dispatchers import siblings inside functions on purpose. Getting this
    # backwards has already cost one CI-red release blocker AND, when first fixed globally,
    # silently hid 4 of 26 deleted hook files. Neither direction may be dropped.
    with tempfile.TemporaryDirectory() as td:
        d = os.path.join(td, "scripts")
        os.makedirs(d)
        with open(os.path.join(d, "seed.py"), "w", encoding="utf-8") as f:
            f.write("import unbluff_sibling_xyz\n\n\n"
                    "def _reader(p):\n    import unbluff_lazy_xyz\n"
                    "    return unbluff_lazy_xyz.read(p)\n")
        with open(os.path.join(d, "unbluff_sibling_xyz.py"), "w", encoding="utf-8") as f:
            f.write("x = 1\n")

        skill_closure = _import_closure(d, ["seed.py"], lazy_optional=True)
        synth += 1
        if "unbluff_lazy_xyz.py" in skill_closure:
            fails.append("a LAZY import was required under lazy_optional=True - this is the "
                         "`import fitz` case, and it made install.py sys.exit for every user "
                         "without PyMuPDF while turning 15 of 17 CI jobs red")
        synth += 1
        if "unbluff_sibling_xyz.py" not in skill_closure:
            fails.append("a MODULE-LEVEL sibling was dropped under lazy_optional=True - the "
                         "skill rule is over-applied and a genuinely missing bundled script "
                         "would install as a working skill that cannot run")

        hook_closure = _import_closure(d, ["seed.py"])
        synth += 1
        if "unbluff_lazy_xyz.py" not in hook_closure:
            fails.append("a LAZY import was treated as optional under the DEFAULT (hooks) "
                         "rule - the Stop and PostToolUse dispatchers import their sub-hooks "
                         "exactly this way, and this spelling hid 4 of 26 deleted hook files")

    # [SKILLDIR-DESTROY] The user's OWN data must survive both directions. Two distinct paths:
    # install merged over a pre-existing same-named skill dir (copytree dirs_exist_ok=True), and
    # uninstall rmtree'd the WHOLE directory - so uninstalling unbluff deleted a skill the user
    # had before unbluff existed. This repo already refuses to clobber a foreign pre-push hook;
    # skills had no equivalent rule.
    destroy = 0
    with tempfile.TemporaryDirectory() as td:
        dest_root = os.path.join(td, "skills")
        victim = os.path.join(dest_root, SKILL_NAMES[0])
        os.makedirs(victim)
        keep = os.path.join(victim, "MY_OWN_NOTES.md")
        with open(keep, "w", encoding="utf-8") as f:
            f.write("the user's own file, predating unbluff\n")

        # (a) install must NOT silently overwrite a directory it did not create.
        destroy += 1
        try:
            install_skill(False, dest_root=dest_root)
            refused = False
        except SystemExit:
            refused = True
        if not refused and not os.path.exists(keep):
            fails.append("install DESTROYED a pre-existing user file at %r - a same-named skill "
                         "directory the user owned was overwritten without warning" % keep)
        elif not refused:
            fails.append("install merged into a skill directory it did not create and did not "
                         "refuse - unbluff's own files now sit inside the user's skill")

        # (b) uninstall must never remove a directory unbluff did not install.
        destroy += 1
        remove_skill(False, dest_root=dest_root)
        if not os.path.exists(keep):
            fails.append("uninstall DELETED the user's own file at %r - rmtree removed a whole "
                         "directory unbluff never created. Uninstalling unbluff destroys a "
                         "skill that predates it" % keep)

    # (c)/(d) the round trip must still WORK - a fix that protects user data by breaking
    # uninstall is not a fix. Clean install -> uninstall leaves nothing; and a file the user
    # adds AFTER install survives while unbluff's own files go.
    with tempfile.TemporaryDirectory() as td:
        dest_root = os.path.join(td, "skills")
        install_skill(False, dest_root=dest_root)
        destroy += 1
        if not os.path.isfile(os.path.join(dest_root, SKILL_NAMES[0], "SKILL.md")):
            fails.append("clean install did not place SKILL.md - the round trip is broken")
        later = os.path.join(dest_root, SKILL_NAMES[0], "USER_ADDED_LATER.md")
        with open(later, "w", encoding="utf-8") as f:
            f.write("added by the user after installing\n")
        remove_skill(False, dest_root=dest_root)
        destroy += 1
        if os.path.exists(os.path.join(dest_root, SKILL_NAMES[0], "SKILL.md")):
            fails.append("uninstall left unbluff's own SKILL.md behind")
        if not os.path.exists(later):
            fails.append("uninstall deleted a file the user added AFTER install (%r) - the "
                         "manifest is not bounding the removal" % later)
        destroy += 1
        # and a skill with nothing user-owned must disappear entirely, or G5 in the
        # integration suite ('every installed skill removed') would go red.
        if os.path.isdir(os.path.join(dest_root, SKILL_NAMES[1])):
            fails.append("uninstall left an empty skill directory behind for %r - the prune "
                         "did not run" % SKILL_NAMES[1])

    # [ROSTER-DERIVE] The seed must be DERIVED, not declared. `REQUIRED_HOOKS` is hand-written,
    # and 7 of the 25 hooks reach the closure ONLY because someone typed them into it: the
    # dispatchers load their sub-hooks via `importlib.import_module(<string>)`, which an AST
    # import walk structurally cannot see. Coverage is correct TODAY and the DERIVATION is not -
    # INSTALL-TAUTOLOGY's exact shape one layer up, with the docstring again calling the roster
    # "DERIVED", which is why nobody looked.
    #
    # Demonstrated before the fix: adding an 8th sub-hook to `post_tooluse_dispatcher.HOOKS`
    # with its file absent gave `missing_hook_files() == []`, `install.py --selftest` rc 0
    # "SELFTEST OK", and a dispatcher exiting 0 in silence - the ModuleNotFoundError reached
    # only a JSONL ledger no user reads.
    roster_cases = 0
    try:
        derived = dispatcher_subhooks(HOOKS_DIR)
        roster_cases += 1
        if not derived:
            fails.append("dispatcher_subhooks() derived NOTHING - a seed of zero would make "
                         "this guard pass against any dispatcher roster")
        undeclared = sorted(n for n in derived if n not in set(REQUIRED_HOOKS))
        if undeclared:
            fails.append("dispatcher sub-hook(s) %s are wired by a dispatcher but absent from "
                         "REQUIRED_HOOKS - while the seed was DECLARED this was silent, which "
                         "is exactly how a roster rots" % (undeclared,))
        roster_cases += 1
        # A dispatcher roster entry whose FILE is missing must be REPORTED. Planted in a
        # scratch copy: the question is about a repo state this one is deliberately not in.
        rd = tempfile.mkdtemp()
        try:
            for fn in os.listdir(HOOKS_DIR):
                if fn.endswith(".py"):
                    shutil.copy(os.path.join(HOOKS_DIR, fn), os.path.join(rd, fn))
            disp = os.path.join(rd, "post_tooluse_dispatcher.py")
            with open(disp, encoding="utf-8") as fh:
                body = fh.read()
            planted = body.replace("HOOKS = (\n",
                                   "HOOKS = (\n    (\"newly_added_guard\", \"n\"),\n", 1)
            if planted == body:
                fails.append("could not plant a synthetic dispatcher roster entry - the "
                             "roster-drift case was NOT exercised, so it is unverified")
            else:
                with open(disp, "w", encoding="utf-8") as fh:
                    fh.write(planted)
                if "newly_added_guard.py" not in set(missing_hook_files(rd)):
                    fails.append("a dispatcher roster entry with NO file was not reported "
                                 "missing - install prints 'Done.', the selftest prints "
                                 "SELFTEST OK, and that hook never runs again")
                roster_cases += 1
        finally:
            shutil.rmtree(rd, ignore_errors=True)
    except Exception as exc:                      # a probe that dies has verified NOTHING
        fails.append("the roster-derivation probe raised %r, so it verified nothing" % (exc,))

    # [PGG-PS] The MATCHER's VALUE, which nothing asserted until 2026-08-13 - and that is
    # precisely why the guard shipped blind to PowerShell for its whole life.
    # tests/test_integration.py compares the SET OF GROUP IDS, so a matcher naming the wrong
    # shell is invisible to it: the group is present, correctly named, and routes nothing.
    matcher_cases = 0
    try:
        import re as _re

        pre = desired_groups()["PreToolUse"]["matcher"]
        guard_tools = _load_guard_shell_tools()
        for tool in guard_tools:
            matcher_cases += 1
            if not _re.fullmatch(pre, tool):
                fails.append("the PreToolUse matcher %r does not route the %r tool, so the "
                             "piped-gate guard NEVER RUNS for that shell's users - which is "
                             "PGG-PS verbatim" % (pre, tool))
        # the regression itself, named: the literal that shipped for months
        if pre == "Bash":
            fails.append("the PreToolUse matcher is the bare literal 'Bash' again - PGG-PS")
        # and the other direction, so widening cannot become 'route everything'
        if _re.fullmatch(pre, "Edit") or _re.fullmatch(pre, "Write"):
            matcher_cases += 1
            fails.append("the PreToolUse matcher %r routes a NON-shell tool - the guard would "
                         "run on every edit and its false-alarm rate stops meaning anything"
                         % (pre,))
    except Exception as exc:
        fails.append("the matcher probe raised %r, so it verified nothing" % (exc,))
    if not matcher_cases:
        fails.append("the matcher probe ran ZERO cases - it is checking nothing")

    # DENOMINATOR, printed: a guard probed with zero cases is indistinguishable from a guard
    # that passed, which is the failure this whole repo is about.
    print("  [install-guard] %d hook + %d skill deleted-file case(s), %d synthetic, "
          "%d user-data case(s), %d roster-derivation case(s), %d matcher case(s)"
          % (checked, skill_checked, synth, destroy, roster_cases, matcher_cases))
    if not roster_cases:
        fails.append("the roster-derivation probe ran ZERO cases - it is checking nothing")
    if not skill_checked:
        fails.append("the skill-guard probe ran ZERO cases - it is checking nothing")
    if not checked:
        fails.append("the partial-checkout probe ran ZERO cases - it is checking nothing")
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1
