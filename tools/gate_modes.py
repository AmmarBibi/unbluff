#!/usr/bin/env python3
"""ONE definition of "is this registration the gate's SELFTEST or its enforcing measurement?".

DATA + one predicate. No gate, no dispatch, nothing to run - it exists so that two callers cannot
answer the same question differently.

WHY IT EXISTS. `AUX_GATES`' third element is the argv a gate is invoked with. Two places reason
about it: `run_selftests.enforcing_mode_gaps()`, which demands an adjudication for a gate wired to
its own selftest, and `mutation_check.enforcing_argv()`, which picks the invocation a mutation is
verified through. Both were written as `extra != ("--selftest",)` - exact tuple equality - while
every gate in this repo actually dispatches on MEMBERSHIP:

    raise SystemExit(selftest() if "--selftest" in sys.argv else main())

The gap between those two spellings is a one-token disarm, and an independent adversarial review
found it (2026-08-19). Register a gate `("--selftest", "")` and: `enforcing_mode_gaps` skips the
row, because the tuple is not exactly `("--selftest",)`, so no unadjudicated gap is reported and
the suite stays green; `enforcing_argv` classifies the row as ENFORCING and hands it to the
mutation harness as "the argv it is registered with"; and the target, dispatching on membership,
runs its SELFTEST - the exact thing enforcing mode exists to escape. The gate's real measurement
is then invoked by nothing, which is the defect this whole cluster of controls was built for,
reintroduced by the controls themselves.

Two implementations of one rule is the defect (`missing_anchors` carries the same argument for
the same reason). So the rule lives here, once, and both callers import it.
"""
from __future__ import annotations

SELFTEST_FLAG = "--selftest"


def is_selftest_argv(extra) -> bool:
    """True if invoking a gate with `extra` runs its SELFTEST rather than its measurement.

    MEMBERSHIP, not equality, because that is what the targets themselves do. `()` is enforcing;
    `("--selftest",)` is the selftest; `("--selftest", "-v")` is ALSO the selftest, and reading it
    as enforcing is the disarm described in the module docstring.
    """
    return SELFTEST_FLAG in tuple(extra or ())
