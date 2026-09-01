#!/usr/bin/env python3
"""BUILT IS NOT LIVE, as a SERIES rather than a single instant. [item 24, 2026-08-28]

WHY THIS EXISTS. Item 15 replaced a hand-maintained prose count - hand-counted five times and
wrong five times - with a count DERIVED by `hook_divergence_report`. That was the right fix and
it had an honest cost: the prose was WRONG but LONGITUDINAL, and the number that replaced it is
RIGHT but INSTANTANEOUS. This gate's subject is a trajectory - every session that fixes something
makes the live machine MORE stale - so today's "1 of 16" only means something against what it was
yesterday. After the prose was deleted that comparison could not be made from the artifacts at
all, and the fix had removed the thing the number was for.

WHY IT IS ITS OWN MODULE. `hook_divergence_report.py` hit the 800-line ratchet twice while this
was being added, and its comments were trimmed twice to fit. Trimming a third time is how a
ratchet becomes cover - `file_size_baseline.json` calls re-recording "THE LOOPHOLE IN THIS
DESIGN", and the same reasoning applies to shaving prose until the number passes. This is a
separable concern (the LEDGER view of the gate, not the provenance walk itself), so it is
separated. `tools` is in COPY_TREES, so it reaches every mutation scratch tree.

WHAT STAYED BEHIND, DELIBERATELY. The `gate_ledger.record("hook_provenance", ...)` CALL is still
in `hook_divergence_report.py`. `run_selftests.unrecorded_tiers()` resolves `RECORDING_TIERS` by
walking the declared file's AST for that call, so moving the call here would have meant pointing
the tier row at a helper module and describing the wrong file as the tier. The bulk moved; the
one line that makes the tier row true did not.

A ZERO IS NOT A COUNT, and in a SERIES that matters more than in a printout. `main()` already
refuses to print "0 of 0 entry points stale" on an unwired machine, because that is
typographically identical to a fully synced one (item 23). Recording a literal 0 into a trend is
worse than printing it once: every fresh CI checkout would deposit a row reading "perfectly
clean" forever, and the series would be built out of rows that mean "inapplicable". So a run with
no count records None plus the REASON, carrying the same two-cause split main() prints.

EVERY PHRASING SAYS "THIS WORKTREE". The ledger is gitignored and therefore per-worktree local
state, by recorded design (item 21) - the two worktrees on this box disagree by ten days on
another tier and BOTH are correct. Item 17's requirement applies verbatim: a local record stated
as a global fact is how a correct push-refusal once got written up as spurious.
"""

REPO_GATE = "hook_provenance"


def ledger_fields(st: dict, r: dict, n_entry: int, n_files: int) -> dict:
    """The structured extras for one recorded run. Absent counts are None PLUS a reason."""
    if st["entry_total"] == 0:
        fields = {"entry_stale": None, "entry_total": 0,
                  "no_count": ("no-wiring-surface" if not r["surfaces"]
                               else "surfaces-declared-no-entry-point")}
    else:
        fields = {"entry_stale": n_entry, "entry_total": st["entry_total"], "no_count": None}
    # The hooks/*.py row is WITHHELD unless exactly one hook dir is wired, because "the live copy"
    # is otherwise ambiguous. Withheld must read as withheld in the series too, not as 0. Recorded
    # as a REASON rather than a count, for the reason the first version got wrong: it wrote
    # `files_withheld=len(wired_dirs)`, which serialised as `files_withheld: 0` on an unwired
    # machine - a field reading "nothing was withheld" while meaning "everything was". That is the
    # identical-value-different-meaning shape the no_count split exists to prevent, one field over.
    if len(st["wired_dirs"]) == 1:
        fields.update(files_stale=n_files, files_total=st["files_total"], files_no_count=None)
    else:
        fields.update(files_stale=None, files_total=None,
                      files_no_count=("no-wired-hook-dir" if not st["wired_dirs"]
                                      else "%d-wired-hook-dirs-live-copy-ambiguous"
                                           % len(st["wired_dirs"])))
    return fields


def trajectory(n_entry: int, st: dict) -> str:
    """One sentence comparing this run's count to the previous one RECORDED IN THIS WORKTREE.

    Never a bare number, and never silently omits itself: no history is a STATEMENT, because an
    empty string would read exactly like "nothing changed".
    """
    try:
        import gate_ledger
        # The path is passed EXPLICITLY, and that is not decoration. gate_ledger's readers -
        # read(), last_run(), tiers() - all declare `path: str = LEDGER`, so the default binds at
        # DEF time, while record() resolves the module global at CALL time. Anything that
        # reassigns gate_ledger.LEDGER therefore WRITES one file and READS another. gate_ledger's
        # own selftest already works around this by passing the path to tiers(); doing the same
        # here keeps this reader agreeing with the writer. Found 2026-08-28 by a probe that
        # returned the SAME sentence for all seven branches - see plan item 29.
        prev = gate_ledger.last_run(REPO_GATE, gate_ledger.LEDGER)
    except Exception:                              # bookkeeping must never fail the gate
        return ("trajectory: UNAVAILABLE - this worktree's gate ledger could not be read, so no "
                "comparison was made. That is not the same as no change.")
    if not prev:
        return ("trajectory: no prior run recorded in THIS WORKTREE, so there is nothing to "
                "compare against yet. The next run will have one.")
    when = prev.get("utc", "an unrecorded time")
    if prev.get("no_count") is not None:
        return ("trajectory: the previous run in THIS WORKTREE (%s) recorded NO COUNT (%s), so a "
                "comparison would be against a number that was never taken." % (when, prev["no_count"]))
    was, total = prev.get("entry_stale"), prev.get("entry_total")
    if was is None or total is None:
        return "trajectory: the previous run in THIS WORKTREE (%s) recorded no usable count." % when
    # The DENOMINATOR moving is its own fact. A numerator compared across two different
    # populations is the exact defect item 15 was built for, where five corrections each fixed the
    # numerator and left the denominator scoped to whatever the author had in mind.
    if total != st["entry_total"]:
        return ("trajectory: %d of %d now, %d of %d in THIS WORKTREE at %s - the DENOMINATOR "
                "moved, so the two numerators are not comparable."
                % (n_entry, st["entry_total"], was, total, when))
    direction = ("unchanged" if n_entry == was
                 else "WORSE by %d" % (n_entry - was) if n_entry > was
                 else "better by %d" % (was - n_entry))
    return ("trajectory: %d of %d now vs %d of %d in THIS WORKTREE at %s - %s."
            % (n_entry, st["entry_total"], was, total, when, direction))
