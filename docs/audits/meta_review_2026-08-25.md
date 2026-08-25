# Meta-review - 2026-08-25

**Scope:** this session, `1e12792..d39559d`, 10 commits. Run to its own procedure; CHECK 1's grep
set differs from the completeness sweep's - only `park` overlaps.

## CHECK 1 - did a fix create a new instance of the class it fixed?

**Yes, and it is the sharpest finding of the session.**

Item 4 exists because *"`scrub_environ()` at the top of `main()` is guarded by nothing - move it
into an uncalled helper and all 41 gates stay green."* I built `check_selftest_isolation` to close
exactly that, **and then shipped four new controls guarded by nothing**: `strip_comments`, the
`PG-QUOTED` limit, and the scrub call sites, none registered as mutation entries.

Same class, same session, one item apart. Filed as **item 9**. Standing check 1 has now fired on my
own work in three consecutive sessions, which is an argument for running it earlier rather than at
the close.

A second, smaller instance: the M10 fix introduced `strip_comments`, whose over-stripping would
itself fire on correct work. Caught before shipping by an explicit over-strip control, and the
residual is adjudicated as `PG-QUOTED` rather than left implicit.

## CHECK 2 - instance-only fixes

| fix | instance or mechanism? |
|---|---|
| item 3's 8 scrubs | instance edits, but item 4's gate is the durable mechanism - **OK** |
| M10 | instance + 5 pinned cases; **not** mutation-pinned -> item 9 |
| item 6 print-before-record | instance + matched control; not mutation-pinned -> item 9 |
| **item 2's config repair** | **INSTANCE ONLY -> new item 10** |

The config repair is the notable one. `git_isolation.fingerprint()` catches a fixture mutating a
repo *during a sweep* - the upstream cause - but **nothing ever asks whether this machine's wired
clone is currently sane.** `hook_health_check` runs at SessionStart and does not look at git config
at all (zero grep hits for `core.bare` or `hooksPath`). So the exact state that sat unnoticed - a
non-bare repo marked bare, `core.hooksPath` aimed at a deleted temp directory silently disabling
every git hook, a `t@t` identity - would sit unnoticed again. **Item 10**, and it is the only new
item NOT blocked behind the pull.

## CHECK 3 - optimization

5 recorded offenders, all AT baseline: `pre_push_gate_selftest` 1213, `fast_test_on_stop_selftest`
1026, `duplicate_registration_check` 858, `fast_test_on_stop` 851, `run_selftests` 803. The
orchestrator crossing the line is item 7; the finding there is not the 3-line overage but that it
had **six** lines of headroom, so the next gate registration hits the same wall.

## CHECK 4 - READ the gate ledger, do not reconstruct

| gate | latest | result |
|---|---|---|
| `file_size` | 2026-08-25T01:40:47Z | PASS |
| `run_selftests` | 2026-08-25T01:41:15Z | FAIL (`hook-provenance` only) |
| `ship_bar` | 2026-08-25T01:19:31Z | PASS |
| `integration` | 2026-08-24T18:42:34Z | PASS |
| `mutation_sweep_filtered` | 2026-08-24T21:23:01Z | PASS |
| **`mutation_sweep`** | **2026-08-20T17:28:15Z** | **FAIL** |
| `false_alarm_scorer` | 2026-08-20T13:46:26Z | PASS |

**`mutation_sweep` has not run for five days**, and it is the tier that would prove items 9's
entries and item 7's split. Blocked behind item 2's pull. `false_alarm_scorer`'s MEASUREMENT is
also five days old - that one is by design (its measurement carries a known adjudicated false
alarm, so the selftest is the gate), stated here so its age does not read as neglect.

## CHECK 6 - exactly ONE canonical order

**PASS.** 11 numbered items in `docs/PLAN.md`'s Open section; `docs/NEXT_SESSION_PROMPT.md` is a
pointer whose first line says so. The competing-order failure found at the previous close has not
recurred.

## CHECK 5 - improvements worth considering

1. **Run CHECK 1 mid-session, not only at the close.** It has caught a same-class regression three
   sessions running; each time the fix was already committed.
2. **`hook_health_check` is the natural home for machine-sanity checks** (item 10) - it already
   runs at SessionStart and already owns "is the wiring healthy".
3. **The heredoc backslash trap has now cost four incidents in two days**, one of which put a
   literal TAB into the plan. It is prose in a rules file; per REMEMBER-vs-ENFORCE it wants a hook.

## End-of-turn finalize

The single recommended-order list in `docs/PLAN.md` is current: items 0-6 marked DONE or PARTIAL
with dates and commits, items 7-10 open with their blocking order stated in each row. All work
built this session was added to that list before or as it was built, never in a side block.
