"""Deliberate narrowings, on the record. Not a way to switch the gate off.

WHY A LEDGER AND NOT A FLAG
    Sometimes a capability is removed ON PURPOSE - a shape was wrong to flag, or a whole
    approach is being replaced. A gate with no way to express that blocks correct work, and
    a gate that blocks correct work gets disabled. So the escape hatch has to exist.

    It is a RECORD, not a switch. There is no per-unit disable and no --skip: the only way
    past the gate is to name the exact capability being given up and say why. That keeps
    the cost of a narrowing equal to the cost of writing down a reason, which is the price
    it should have.

THE SIX STATES, all enforced by tools/no_regression.py:

    ACTIVE   the capability is lost against the predecessor RIGHT NOW and a reason is on
             file -> non-blocking, but printed on its own line every run.
    SETTLED  the narrowing landed in an earlier commit, so NEITHER side detects it any
             more -> the record stays as the standing reason. Non-blocking.
    STALE    the capability is detected again -> the waiver is dead weight and is BLOCKING,
             because a ledger nobody prunes is how an exemption roster rots into
             pre-authorisation. This repo already found 2 of 3 BOUND_EXEMPTIONS entries
             inert and silently widening a blind spot.
    GHOST    names a unit or capability id that does not exist -> BLOCKING. Same reasoning
             as a registry ghost: a waiver pointing at nothing is a waiver nobody can audit.
    UNUSED   the unit has no predecessor at all, so nothing can be lost -> BLOCKING, since
             the waiver claims to excuse something that cannot happen.
    UNKNOWN  the CHECKOUT cannot see the past - a --depth or partial clone - so the waiver's
             state is undeterminable here -> NON-BLOCKING, and printed on its own
             UNDETERMINED line every run. Added 2026-08-06 after a shallow `actions/checkout`
             made 11 of 11 CI jobs red on a commit that was green locally: the differing blob
             existed and was simply never fetched, and "I could not look" was being reported
             as "there is nothing to look at". It must not be silent either - a gate that
             quietly passes on a truncated checkout is a gate that cannot fail, which is why
             CI now fetches full history rather than relying on this state.

ENTRY SHAPE
    {"unit": <repo-relative path>,
     "capability": <entry name from that unit's corpus>,
     "narrowed_on": "YYYY-MM-DD",
     "reason": <why this capability SHOULD no longer be detected>}

    The reason must argue that detecting it was WRONG. "It is noisy" is not a reason - a
    guard that is boundedly noisy and fails closed is the design this repo settled on after
    a probe treated 6 false positives as disqualifying and bought an unbounded problem.
"""

from __future__ import annotations

WAIVERS = (
    {"unit": "hooks/capped_report.py",
     "capability": "scalar_slice_without_a_roster_entry",
     "narrowed_on": "2026-08-06",
     "reason":
         "Detecting it was WRONG, and the corpus proves it mechanically rather than by "
         "argument. `scalar_slice_without_a_roster_entry` and `neg_scalar_slice_rostered` "
         "are BYTE-IDENTICAL: same rel_path 'hooks/f.py', same source "
         "(`text = fh.read(); return text[:MAX_FILE_BYTES]`), opposite must_flag. "
         "score_corpus plants one entry per fresh temp dir, so a deterministic guard is "
         "asked the same question twice and required to answer differently. It cannot. "
         "The predecessor took the flag-both side and paid for it with the single false "
         "positive in its record; C1-NEW takes the stay-quiet side, because clause 1 "
         "correctly reads `fh.read()` as a str and truncating a string is not the defect "
         "this guard exists to catch. Trading 1 unreachable positive for 0 false positives "
         "is the better half of an unsatisfiable pair, not a narrowing of the guard. "
         "MEASURED 2026-08-06, and stamped rather than written in the present tense because "
         "the corpus is append-only and these figures move every time it grows: predecessor "
         "38 of 105 with FALSE-POS 1; C1-NEW 102 of 105 with FALSE-POS 0, which is the "
         "arithmetic ceiling given three such pairs. The live figures are whatever "
         "tools/score_corpus.py prints, and it prints the ceiling alongside them. "
         "This waiver goes STALE and BLOCKING the moment the corpus stops contradicting "
         "itself, which is the correct trigger to revisit it."},
)
