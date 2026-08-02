"""Deliberate narrowings, on the record. Not a way to switch the gate off.

WHY A LEDGER AND NOT A FLAG
    Sometimes a capability is removed ON PURPOSE - a shape was wrong to flag, or a whole
    approach is being replaced. A gate with no way to express that blocks correct work, and
    a gate that blocks correct work gets disabled. So the escape hatch has to exist.

    It is a RECORD, not a switch. There is no per-unit disable and no --skip: the only way
    past the gate is to name the exact capability being given up and say why. That keeps
    the cost of a narrowing equal to the cost of writing down a reason, which is the price
    it should have.

THE FIVE STATES, all enforced by tools/no_regression.py:

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

WAIVERS = ()
