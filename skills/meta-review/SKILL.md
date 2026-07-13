---
name: meta-review
description: A repeatable meta-hardening pass for any project. Claude (the reasoner) audits for parked-but-unscheduled work, instance-only fixes lacking a durable mechanism, code/structure/perf optimization gaps, things missing or wrong, and improvements that would lead to a better outcome - then schedules or fixes each. Use at milestones, before a release/cutover, or whenever the user asks "am I missing anything / is this optimized / did we only patch the instance". This is the REASONING half that hooks cannot do; hooks only surface state.
metadata:
  suite: unbluff
tools: Read, Grep, Glob, Bash, Edit
---

# Meta-Review

The deliberate pass that catches what incremental work misses. **Claude is the reasoner; a hook can
only surface markers - it cannot decide what is missing or fix it.** Run this; do not delegate the
judgment to a script.

## When to run
- At a milestone, before a release/cutover, or when the user asks "am I missing anything?", "is this
  optimized?", "did we only fix the instance?", or "is anything wrong?".
- After a stretch of incremental fixes (each fix tends to spawn an unscheduled follow-up).

## The six checks (do each, then act)

1. **Parked-but-unscheduled.** Grep the canonical plan for `PARK|DEFER|TODO|OPTIONAL|candidate|later`.
   For each: is it in the recommended order with a rationale, or explicitly justified-parked? If
   neither, schedule it now (priority + one-line why). Standing rule: defer -> schedule in the SAME edit.
   (The `meta_audit_on_stop` hook in this suite surfaces the mechanical version of this at turn-end.)

2. **Instance-only fixes (the durability check).** For each notable fix in recent history (git log,
   plan, notes), ask: *did we fix the instance, or install a mechanism so it cannot recur?* A fix that
   relies on "Claude will remember" is instance-only. Durable forms: an encoded standing rule, a
   test/regression, a self-checking harness, a small mechanical hook, or a structural change. Convert
   the real ones; not everything needs a mechanism (judgment calls stay judgment calls).

3. **Optimization (code/structure/perf).** Files over the project's size rule (e.g. 800 lines) ->
   schedule a behaviour-preserving split (tests as the safety net). Look for duplication, per-request
   work that should be cached, N+1 / unbounded queries, and dead code. Report a number where you can
   (coverage %, file sizes), not a vibe.

4. **Missing / wrong.** At the product level (a capability that silently refuses, a claimed feature that
   does not work) and the process level (an eval not run, a gate skipped). Prefer a fresh held-out probe
   over re-reading code you wrote.

5. **Improvements for a better outcome.** Not bugs - the "this would be materially better" ideas:
   sharper UX, a stronger default, a missing guardrail, a reusable abstraction. List them; let the user
   pick. Spin out-of-scope ones into their own task so they are not lost.

6. **Mechanism health.** Are the project's standing mechanisms actually working - hooks not silently
   erroring (the `hook_health_check` hook covers this), the test runner green, notes/plan lean, and
   **exactly ONE canonical recommended-order list** (no competing "sequence" + "infra" block that has
   drifted apart - if two orderings exist, merge them now)? A broken safety net is worse than none.

**End-of-turn finalize (always last):** after acting, REFRESH the single recommended-order list so DONE
items are marked and the next items are in priority - the closing artifact is always a current, coherent
order. New work must already be IN that list (added before it was built), never in a side block. This is
the durable guard against the order silently drifting from reality.

## Output
A short report: per check, findings + the action taken (scheduled / fixed / justified-parked). Then
build the low-risk high-value items in the project's recommended order; schedule the rest with priority.

## Design note (why this is a skill, not a hook)
Hooks run shell commands on events - deterministic, always-on, zero reasoning. They are right for
mechanical surfacing (format, test-on-stop, egress guard, "N parked markers found", "a hook errored").
They CANNOT weigh trade-offs or decide what is missing. Keep hooks few and mechanical (they add per-call
overhead - a busy setup can fire a dozen-plus hook commands per call); put the judgment here, in a skill
the user or Claude invokes on purpose. The mechanical hooks in this suite (`meta_audit_on_stop`,
`memory_hygiene_guard`, `fast_test_on_stop`, `show_your_proof`, `hook_health_check`) surface the state;
this skill is the reasoning that acts on it.
