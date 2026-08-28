"""The `hook-provenance` selftest battery. Split out of hook_divergence_report.py 2026-08-26.

WHY IT IS A SEPARATE FILE. Item 15 added the derived BUILT-IS-NOT-LIVE count and the probes
that hold it honest, taking hook_divergence_report.py from 546 to 925 lines - a NEW file-size
offender. The baseline records the same instruction three times: the next growth is preceded by
a SPLIT, not by another re-record. This follows the pre_push_gate / pre_push_gate_selftest and
install / install_selftest precedent.

THE REBINDING RULE, same as those two. Everything here READS the parent's module-level names;
nothing rebinds one. A moved function that assigned to a parent global would bind a copy in
THIS module instead and the parent would never see it - checked before the cut (no `global`
statements in the moved body) and it must stay true.

THE ANCHORS DID NOT MOVE. Pinned mutations A3a/A3b/A3c anchor lines of `_git_hook_dirs`,
`_strip_shell_comments` and `provenance` - all production code, all still in the parent. The
seam was chosen so that no pinned anchor crosses it, which is the trap that stopped the
fast_test_on_stop split (FTB-2) and the pre_push_gate_selftest one (_SH_SITES).

Run it the way it has always been run - `python tools/hook_divergence_report.py --selftest`.
That still works; the parent delegates here.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Imported, never re-implemented: a second copy of any of these is the twin defect this repo
# keeps paying for, and `_same_program` in particular exists because a duplicated comparison
# rule drifted from the one that mattered.
from hook_divergence_report import (  # noqa: E402
    REPO_ROOT,
    _git_hook_dirs,
    _same_program,
    _same_repo_same_bytes,
    dispatcher_children,
    entry_points,
    norm,
    provenance,
    staleness,
    sync_phrase,
)

# [#46 item 4] Scrub git's redirect variables at import, before any fixture can run. This file
# is where the mutating verbs now live - `git init` and `git config --local` - so the scrub has
# to be HERE, and tools/check_selftest_isolation.py re-derived its population and said so the
# moment the split moved them. Importing the parent above already scrubs, but that is a
# transitive accident of the current import order and this module is independently runnable;
# a scrub that only works because of who imported you is not isolation. No ImportError
# fallback, matching the parent: git_isolation is a SIBLING in tools/, so if it is missing this
# file is broken anyway and failing loudly at import is the honest outcome.
from git_isolation import scrub_environ as _scrub_environ  # noqa: E402
_scrub_environ()


def _selftest_item24() -> list:
    """[item 24] The LEDGER view: field shaping and the trend sentence.

    These assertions existed as throwaway scratchpad probes when item 24 landed, which is
    REMEMBER rather than ENFORCE - the split tooling-discipline 7.3 is about, and the reason a
    warning gets skipped while a test goes red. `hook_divergence_trend.py` ships no `--selftest`
    of its own and is classified NOT_A_GATE, so it is covered HERE, through the gate that uses
    it, rather than by registering a second gate for a view module.

    The load-bearing case is the first: a run with no population must record ABSENT plus a
    reason, never 0. A literal 0 in a SERIES is worse than in a printout - every fresh CI checkout
    would deposit a row reading "perfectly clean" forever, and the trend would be built out of
    rows that mean "inapplicable".
    """
    import tempfile
    fails = []
    try:
        import hook_divergence_trend as T
        import gate_ledger
    except ImportError as exc:
        return ["item24 battery could not import its subject (%s) - a battery that cannot load "
                "is not a battery that passed" % exc]

    ST0 = {"entry_total": 0, "files_total": 0, "wired_dirs": []}
    ST1 = {"entry_total": 16, "files_total": 28, "wired_dirs": ["/one"]}

    # 1. NO POPULATION -> None plus a REASON, and the two causes stay distinguishable.
    f = T.ledger_fields(ST0, {"surfaces": []}, 0, 0)
    if f["entry_stale"] is not None:
        fails.append("an empty population recorded entry_stale=%r, not None. A literal 0 in the "
                     "SERIES makes every fresh CI checkout deposit a row reading 'perfectly "
                     "clean' forever." % (f["entry_stale"],))
    if f["no_count"] != "no-wiring-surface":
        fails.append("the no-surface cause was recorded as %r" % (f["no_count"],))
    f2 = T.ledger_fields(ST0, {"surfaces": ["/a"]}, 0, 0)
    if f2["no_count"] != "surfaces-declared-no-entry-point":
        fails.append("the broken-derivation cause was recorded as %r - the two causes must stay "
                     "distinguishable in the series, not only in the printout" % (f2["no_count"],))
    # WITHHELD must read as withheld, never as 0. The first version wrote files_withheld=0 on an
    # unwired machine: a field reading "nothing was withheld" while meaning "everything was".
    if f["files_stale"] is not None or not f["files_no_count"]:
        fails.append("a withheld hooks/*.py row recorded %r/%r instead of None plus a reason"
                     % (f["files_stale"], f.get("files_no_count")))

    # 2. A REAL population records the real numbers, with both no_count fields cleared.
    f3 = T.ledger_fields(ST1, {"surfaces": ["/a"]}, 1, 2)
    if (f3["entry_stale"], f3["entry_total"], f3["files_stale"]) != (1, 16, 2):
        fails.append("a real population recorded %r" % (f3,))
    if f3["no_count"] is not None or f3["files_no_count"] is not None:
        fails.append("a real population left a no_count reason set: %r" % (f3,))

    # 3. trajectory(): every branch, asserted on CONTENT. A shape-only test would pass against a
    #    function returning one constant sentence - which is exactly what the first version did,
    #    because it read a DIFFERENT ledger from the one under test (item 29).
    saved = gate_ledger.LEDGER
    try:
        def with_rows(rows):
            d = tempfile.mkdtemp(prefix="unbluff-i24-")
            gate_ledger.LEDGER = os.path.join(d, "gate_runs.json")
            with open(gate_ledger.LEDGER, "w", encoding="utf-8") as fh:
                json.dump(rows, fh)
            return T.trajectory(1, {"entry_total": 16})

        P = "hook_provenance"
        U = "2026-08-01T00:00:00+00:00"
        cases = [
            ("no history", [], "no prior run recorded in THIS WORKTREE"),
            ("prior no-count", [{"gate": P, "utc": U, "entry_stale": None, "entry_total": 0,
                                 "no_count": "no-wiring-surface"}], "recorded NO COUNT"),
            ("denominator moved", [{"gate": P, "utc": U, "entry_stale": 6, "entry_total": 11,
                                    "no_count": None}], "DENOMINATOR"),
            ("unchanged", [{"gate": P, "utc": U, "entry_stale": 1, "entry_total": 16,
                            "no_count": None}], "unchanged"),
            ("worse", [{"gate": P, "utc": U, "entry_stale": 0, "entry_total": 16,
                        "no_count": None}], "WORSE by 1"),
            ("better", [{"gate": P, "utc": U, "entry_stale": 4, "entry_total": 16,
                         "no_count": None}], "better by 3"),
        ]
        seen = set()
        for label, rows, needle in cases:
            got = with_rows(rows)
            seen.add(got)
            if needle not in got:
                fails.append("trajectory %s: expected %r in the sentence, got %r"
                             % (label, needle, got))
            # Item 17's load-bearing phrasing, asserted rather than trusted: a local record stated
            # as a global fact is how a correct push-refusal was once written up as spurious.
            if "THIS WORKTREE" not in got:
                fails.append("trajectory %s does not say THIS WORKTREE: %r" % (label, got))
            if "is stale" in got:
                fails.append("trajectory %s says '<tier> is stale', the phrasing item 17 forbids: "
                             "%r" % (label, got))
        # ONE CONSTANT SENTENCE would satisfy the membership tests above if the needles happened to
        # be substrings of it, so assert the branches actually DIVERGE. That is the shape that hid
        # item 29 through a full probe run.
        if len(seen) != len(cases):
            fails.append("trajectory returned %d distinct sentences for %d different ledgers - "
                         "the branches are not diverging, which is what a reader pointed at the "
                         "WRONG LEDGER looks like" % (len(seen), len(cases)))
    finally:
        gate_ledger.LEDGER = saved
    return fails


def _selftest_item15() -> list:
    """[item 15] The COUNT must be derived, and every one of these probes was shown to FAIL.

    Each case below was run against a deliberately broken build before being kept - a
    name-based dispatcher lookup, a raw byte compare, an absent file folded into 'differs',
    and children credited to an unwired dispatcher. A probe never shown to fail is a smoke
    test, and this file's own history is the argument: the population it now derives was
    hand-counted wrong five times in a row.
    """
    import tempfile
    fails = []

    # 1. LINE ENDINGS ARE NOT STALENESS - and a real change still is. Both directions, because
    #    normalising too eagerly would wave through the drift this gate exists for.
    body = b"import os\n\n\ndef main():\n    return 0\n"
    if not _same_program(body, body.replace(b"\n", b"\r\n")):
        fails.append("a CRLF twin of the same program was called different - that is 2 of this "
                     "machine's 28 hooks, and a guard that fires on correct work gets switched off")
    if _same_program(body, body.replace(b"return 0", b"return 1")):
        fails.append("a REAL change survived _same_program - newline normalisation has widened "
                     "into 'ignore differences', which is the drift this whole gate exists for")

    with tempfile.TemporaryDirectory() as td:
        hooks = os.path.join(td, "hooks")
        os.makedirs(hooks)

        def put(d, name, text):
            p = os.path.join(d, name)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            return p

        # 2. A DISPATCHER IS A SHAPE, NOT A NAME. Two dispatcher-shaped modules under different
        #    names must BOTH be found: the plan's count missed post_tooluse_dispatcher entirely
        #    and half of stop_dispatcher's table, which is five live hooks outside the
        #    denominator. A decoy with a HOOKS that is not pairs-of-strings must not count.
        put(hooks, "alpha_dispatch.py", 'HOOKS = (("kid_one", "a"), ("kid_two", "b"))\n')
        put(hooks, "beta_dispatch.py", 'HOOKS = (("kid_three", "c"),)\n')
        put(hooks, "decoy.py", "HOOKS = (1, 2, 3)\n")
        put(hooks, "plain.py", "X = 1\n")
        for n in ("kid_one.py", "kid_two.py", "kid_three.py"):
            put(hooks, n, "def main():\n    return 0\n")
        tables = dispatcher_children(hooks)
        if set(tables) != {"alpha_dispatch.py", "beta_dispatch.py"}:
            fails.append("dispatcher discovery returned %r - it must find EVERY module with a "
                         "HOOKS table of pairs and nothing else. Missing a second dispatcher is "
                         "exactly how three live hooks stayed out of the denominator"
                         % (sorted(tables),))

        # 3. A WIRED dispatcher contributes its children; an UNWIRED one contributes nothing,
        #    because children of a dispatcher nobody calls do not run.
        s_wired = os.path.join(td, "wired.json")
        with open(s_wired, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [
                {"command": 'python "%s"' % os.path.join(hooks, "alpha_dispatch.py")}]}]}}, fh)
        ep = entry_points([s_wired], [], hooks)
        if set(ep) != {"alpha_dispatch.py", "kid_one.py", "kid_two.py"}:
            fails.append("entry_points on a wired dispatcher gave %r; it must credit the "
                         "dispatcher AND its children - the children are what actually run"
                         % (sorted(ep),))
        s_bare = os.path.join(td, "bare.json")
        with open(s_bare, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {"Stop": [{"hooks": [
                {"command": 'python "%s"' % os.path.join(hooks, "plain.py")}]}]}}, fh)
        ep2 = entry_points([s_bare], [], hooks)
        if "kid_one.py" in ep2:
            fails.append("children of an UNWIRED dispatcher were counted as entry points (%r) - "
                         "the denominator would then include hooks that never run" % (sorted(ep2),))

        # 4. staleness: eol-only is reported but NOT stale; a real change IS; and an ABSENT
        #    file is its own bucket - folding it into 'differs' hides that it was never
        #    delivered at all, which is true of two modules on this machine right now.
        live = os.path.join(td, "live")
        os.makedirs(live)
        put(live, "alpha_dispatch.py", 'HOOKS = (("kid_one", "a"), ("kid_two", "b"))\n')
        with open(os.path.join(live, "kid_one.py"), "wb") as fh:
            fh.write(b"def main():\r\n    return 0\r\n")          # CRLF twin
        put(live, "kid_two.py", "def main():\n    return 99\n")   # a REAL change
        # kid_three.py deliberately absent from `live`
        ep3 = {"alpha_dispatch.py": os.path.join(live, "alpha_dispatch.py"),
               "kid_one.py": os.path.join(live, "kid_one.py"),
               "kid_two.py": os.path.join(live, "kid_two.py"),
               "kid_three.py": os.path.join(live, "kid_three.py")}
        st = staleness(ep3, hooks)
        if st["entry_stale"] != ["kid_two.py"]:
            fails.append("staleness called %r stale; only the REAL change should be - a "
                         "line-ending difference is not drift" % (st["entry_stale"],))
        if st["entry_eol"] != ["kid_one.py"]:
            fails.append("the line-ending-only difference was not REPORTED (%r). Counted-and-"
                         "named or it looks like the gate never examined it" % (st["entry_eol"],))
        if st["entry_absent"] != ["kid_three.py"]:
            fails.append("an ABSENT live file landed in %r instead of its own bucket - 'never "
                         "delivered' and 'differs' are not the same fact" % (st,))
        if st["entry_total"] != 4:
            fails.append("entry_total was %r, not the 4 examined - a numerator without its own "
                         "denominator is the defect this item exists to remove" % st["entry_total"])

    # 4b. THE REMEDY SENTENCE MUST NOT FIRE ON A SYNCED TREE. This one is not hypothetical: the
    #     first version printed "only a push/merge will clear the count" unconditionally, and
    #     the merge it recommended was landed, the count went to 0 of 16, and it was STILL
    #     demanding a merge. Both directions, because a guard that never speaks is as useless
    #     as one that never stops.
    synced = sync_phrase("0", "0")
    if "push/merge" in synced or "AHEAD" in synced:
        fails.append("the divergence note still demands a push/merge when the trees are IN "
                     "SYNC (%r) - a guard telling you to fix what you just fixed" % synced)
    if "IN SYNC" not in synced:
        fails.append("a synced tree produced %r, which does not SAY it is synced - silence and "
                     "'in sync' are not the same report" % synced)
    diverged = sync_phrase("15", "0")
    if "push/merge" not in diverged or "15" not in diverged:
        fails.append("a genuinely ahead branch produced %r - it must name the remedy and the "
                     "count, since a pull cannot clear unpushed commits" % diverged)

    # 4c. [item 23] A ZERO POPULATION MUST NOT READ AS A CLEAN MACHINE. This gate's docstring
    #     says a check that examined nothing looks exactly like one that found nothing wrong,
    #     and the count shipped without honouring it - printing a bare "0 of 0 entry points
    #     stale" on a machine with no wiring, which is what a fresh CI checkout produces. Probed
    #     as STATE here (the phrasing lives in main()); the zero must be reachable and visible.
    with tempfile.TemporaryDirectory() as td:
        hooks = os.path.join(td, "hooks")
        os.makedirs(hooks)
        with open(os.path.join(hooks, "solo.py"), "w", encoding="utf-8") as fh:
            fh.write("def main():\n    return 0\n")
        nothing = os.path.join(td, "nowiring.json")
        with open(nothing, "w", encoding="utf-8") as fh:
            json.dump({"hooks": {}}, fh)
        ep0 = entry_points([nothing], [], hooks)
        st0 = staleness(ep0, hooks)
        if ep0:
            fails.append("a settings file declaring no hooks still produced entry points (%r)"
                         % (sorted(ep0),))
        if st0["entry_total"] != 0:
            fails.append("an empty population reported entry_total=%r; the zero must survive to "
                         "main() or the INAPPLICABLE branch can never fire"
                         % st0["entry_total"])
        if st0["wired_dirs"]:
            fails.append("an empty population still reported wired hook dirs (%r), which would "
                         "print a files row derived from nothing" % (st0["wired_dirs"],))

    # 5. THE REGRESSION THIS SESSION FIXED. _same_repo_same_bytes must delegate to
    #    _same_program: a linked worktree checked out with different line endings is our own
    #    file, and calling it FOREIGN blocked a push once already.
    with tempfile.TemporaryDirectory() as gd:
        repo = os.path.join(gd, "r")
        rh = os.path.join(repo, "hooks")
        other = os.path.join(repo, "other")
        os.makedirs(rh)
        os.makedirs(other)
        try:
            ok = subprocess.run(["git", "-C", repo, "init", "-q"],
                                capture_output=True, timeout=30).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
        if ok:
            with open(os.path.join(rh, "x.py"), "wb") as fh:
                fh.write(b"def main():\n    return 0\n")
            with open(os.path.join(other, "x.py"), "wb") as fh:
                fh.write(b"def main():\r\n    return 0\r\n")
            if not _same_repo_same_bytes(os.path.join(other, "x.py"), norm(rh), "x.py"):
                fails.append("a CRLF twin inside the SAME repository was still classified "
                             "FOREIGN - _same_repo_same_bytes is back on a raw byte compare, "
                             "and this gate blocked a v1.4.0 push the last time it did that")
            with open(os.path.join(other, "x.py"), "wb") as fh:
                fh.write(b"def main():\r\n    return 1\r\n")
            if _same_repo_same_bytes(os.path.join(other, "x.py"), norm(rh), "x.py"):
                fails.append("a genuinely DIFFERENT program in the same repository was waved "
                             "through as ours - the false negative is the dangerous direction")
        else:
            print("  [hook-provenance] NOTE: git unavailable; the same-repo CRLF assertion did "
                  "NOT run")
    return fails


def selftest() -> int:
    """Plant a foreign copy and a matching control; the gate must separate them.

    A detector that cannot SEE a planted offender is indistinguishable from a clean machine,
    which is the failure this whole file is about.
    """
    import tempfile
    fails = []

    # The SURFACE LIST must be derived, not passed in. Every other case below hands hook_dirs
    # in explicitly, which would leave _git_hook_dirs() itself unexercised - and git's hook
    # surface is precisely where the 2026-08-05 divergence ran. A gate that stopped reading it
    # would go silent on the only surface that has ever caught anything here.
    own = os.path.join(REPO_ROOT, ".git", "hooks")
    if os.path.isdir(own):
        found = {norm(d) for d in _git_hook_dirs()}
        if norm(own) not in found:
            fails.append("_git_hook_dirs() no longer reports this repo's own .git/hooks (%r); "
                         "git's hook surface is the one the real divergence ran on" % (own,))
    # BEHAVIOURAL: build a repo that actually SETS core.hooksPath and require the function to
    # find it. An earlier version asserted only that the literal "core.hooksPath" still appeared
    # in the function - mutation A3a emptied the scope loop and SURVIVED, because the literal was
    # untouched. core.hooksPath REPLACES .git/hooks wholesale, so a gate that stops reading it
    # inspects the dead surface and calls the machine clean.
    with tempfile.TemporaryDirectory() as gd:
        repo = os.path.join(gd, "r")
        os.makedirs(repo)
        want = os.path.join(gd, "myhooks")
        os.makedirs(want)
        try:
            ok = subprocess.run(["git", "-C", repo, "init", "-q"],
                                capture_output=True, timeout=30).returncode == 0
            if ok:
                subprocess.run(["git", "-C", repo, "config", "--local", "core.hooksPath", want],
                               capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            ok = False
        if ok:
            got = {norm(d) for d in _git_hook_dirs(repos=[repo], cwd=repo)}
            if norm(want) not in got:
                fails.append("_git_hook_dirs() did not report a repo's own core.hooksPath "
                             "(%r not in %r) - that setting REPLACES .git/hooks, so the gate "
                             "would read the dead surface and call the machine clean"
                             % (want, sorted(got)))
        else:
            print("  [hook-provenance] NOTE: git unavailable; the core.hooksPath discovery "
                  "assertion did NOT run")

    with tempfile.TemporaryDirectory() as td:
        fake_hooks = os.path.join(td, "hooks")
        os.makedirs(fake_hooks)
        for n in ("alpha_hook.py", "beta_hook.py"):
            with open(os.path.join(fake_hooks, n), "w", encoding="utf-8") as fh:
                fh.write("# hook\n")
        foreign_dir = os.path.join(td, "elsewhere")
        os.makedirs(foreign_dir)
        with open(os.path.join(foreign_dir, "alpha_hook.py"), "w", encoding="utf-8") as fh:
            fh.write("# stale copy\n")

        def settings_with(*cmds):
            p = os.path.join(td, "s%d.json" % len(os.listdir(td)))
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"hooks": {"Stop": [{"hooks": [{"command": c} for c in cmds]}]}}, fh)
            return p

        # CONTROL: wired from the real hooks dir -> matched, never foreign
        ctl = settings_with('python "%s"' % os.path.join(fake_hooks, "beta_hook.py"))
        r = provenance([ctl], [], fake_hooks)
        if r["foreign"]:
            fails.append("CONTROL flagged as foreign: %r - the gate would fire on a correct "
                         "install, which gets a gate disabled" % (r["foreign"],))
        if len(r["matched"]) != 1:
            fails.append("CONTROL not recognised as ours: %r" % (r["matched"],))

        # OFFENDER: same basename, different directory
        off = settings_with('python "%s"' % os.path.join(foreign_dir, "alpha_hook.py"))
        r = provenance([off], [], fake_hooks)
        if len(r["foreign"]) != 1:
            fails.append("planted FOREIGN copy not detected: %r - the gate matches nothing and "
                         "would report any machine as clean" % (r,))

        # OFFENDER via a git hook shim (the surface that actually bit): shell, not JSON
        gh = os.path.join(td, "githooks")
        os.makedirs(gh)
        with open(os.path.join(gh, "pre-push"), "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\nexec "py" "%s" "$@"\n'
                     % os.path.join(foreign_dir, "alpha_hook.py").replace("\\", "/"))
        r = provenance([], [gh], fake_hooks)
        if len(r["foreign"]) != 1:
            fails.append("foreign copy wired via a GIT HOOK not detected: %r. That is the exact "
                         "surface the 2026-08-05 divergence ran on" % (r,))

        # a path with a SPACE must still parse - the _path_tokens fix must not be lost
        spaced = os.path.join(td, "John Doe")
        os.makedirs(spaced, exist_ok=True)
        with open(os.path.join(spaced, "alpha_hook.py"), "w", encoding="utf-8") as fh:
            fh.write("# stale\n")
        sp = settings_with('python "%s"' % os.path.join(spaced, "alpha_hook.py"))
        r = provenance([sp], [], fake_hooks)
        if len(r["foreign"]) != 1:
            fails.append("a foreign path CONTAINING A SPACE was not detected: %r - every user "
                         "whose home dir has a space would be unchecked" % (r,))

        # an UNPARSEABLE command naming one of ours must be reported, never silently skipped
        up = settings_with("run-alpha_hook.py-somehow --with no path")
        r = provenance([up], [], fake_hooks)
        if not r["unparsed"]:
            fails.append("a command naming one of our hooks with no extractable path was "
                         "silently dropped - non-extraction must not read as non-divergence")

        # NEGATIVE CONTROL 1: our own shim documents itself in a COMMENT. A comment cannot wire
        # anything, and reading it made 22 correctly-installed dispatchers look foreign during
        # the very repair that installed them.
        gh2 = os.path.join(td, "githooks2")
        os.makedirs(gh2)
        with open(os.path.join(gh2, "pre-push"), "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\n# managed by ~/.claude/hooks/alpha_hook.py\nexec "py" "%s"\n'
                     % os.path.join(fake_hooks, "alpha_hook.py").replace("\\", "/"))
        r = provenance([], [gh2], fake_hooks)
        if r["foreign"]:
            fails.append("a path inside a shell COMMENT was read as a wiring: %r - every "
                         "self-documenting shim would fail this gate" % (r["foreign"],))
        if len(r["matched"]) != 1:
            fails.append("the real exec line was lost while stripping comments: %r" % (r,))

        # NEGATIVE CONTROL 2: a bare basename (our dispatcher greps for one) is not a wiring.
        gh3 = os.path.join(td, "githooks3")
        os.makedirs(gh3)
        with open(os.path.join(gh3, "pre-push"), "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\ngrep -q alpha_hook.py "$local_hook" && exit 0\n')
        r = provenance([], [gh3], fake_hooks)
        if r["foreign"]:
            fails.append("a BARE basename was classified as a foreign wiring: %r"
                         % (r["foreign"],))
        if len(r["bare"]) != 1:
            fails.append("a bare basename was silently dropped instead of counted: %r" % (r,))

    fails += _selftest_item15()
    fails += _selftest_item24()

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1
