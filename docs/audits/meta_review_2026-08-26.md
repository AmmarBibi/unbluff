# Meta-review - 2026-08-26

**Scope:** `6aa7e65..HEAD` plus today's edits. Run to its own procedure; CHECK 1's grep set
(`PARK|DEFER|TODO|OPTIONAL|candidate|later`) differs from the completeness sweep's.

## CHECK 1 - parked but unscheduled

**Seven hits, zero findings.** All are descriptive prose about the words themselves - item 18
literally discusses `[TODO]` as a token the placeholder detector should keep matching, and item 13
uses "candidate shape" to describe a proposed hook. Nothing is a parked item. The
`plan-defer-guard` hook remains the tripwire between runs.

## CHECK 2 - instance-only fixes (the durability check)

| fix today | instance or mechanism? |
|---|---|
| "zero problems" -> "zero MACHINE-SANITY problems" | instance; a prose-ambiguity fix has no sensible mechanism - **judgment call, left as one** |
| `12 of 26` -> `14 of 28` in three places | **instance, AGAIN - item 15 already exists and is now demonstrated twice, not predicted** |
| `id` `unbluff-piped-gate` -> `unbluff:piped-gate` | **INSTANCE ONLY -> new item 19** |

### The id defect is the finding, and its durability half is item 19

Fixing one id fixes one id. `install.ID_PREFIX` is `unbluff:`, uninstall selects on
`startswith(ID_PREFIX)`, and a group under any other id **works perfectly and is unmanageable** -
it fires, hook-health resolves its script, `duplicate_registration_check` sees one registration,
and `--uninstall` silently leaves it. **Every existing check says green.** That is why it survived
being written by hand, and why it would survive being written by hand again.

Grep confirms nothing asserts it: `ID_PREFIX` lives in `install.py` alone; `show_your_proof.py`'s
apparent hits are `SESSION_ID_PREFIX_LEN`. Item 19 puts the assertion where the walk already
exists, and requires reading `ID_PREFIX` from `install.py` rather than restating the literal whose
exact spelling caused the defect.

### And item 15 is now evidence rather than argument

`12 of 26` was restated in three places without a pin and all three were wrong within one day -
the **second consecutive session** in which item 2's body drifted from the table it copies
("all four" -> "five ... 12 of 26" -> "6 of 11 ... 14 of 28"). Part of the movement was
self-inflicted: **wiring item 5 turned `piped_gate_guard` into an entry point while it was stale**,
taking the population 10 -> 11 and the count 5 -> 6. The plan's line *every session that fixes
something makes the live machine MORE stale* is not rhetoric; this is the mechanism and item 5 is
the instance.

## CHECK 3 - optimization

`file-size`: **64** files, limit 800, **5 recorded offenders, all AT baseline, 0 new, 0 grown**.
Both modules added on 2026-08-25 remain well under (351 / 262). `run_selftests.py` is still 803
with zero headroom, which is why item 8 cannot land before item 7 - measured, not assumed.

## CHECK 4 - READ the gate ledger, do not reconstruct

Read from `docs/audits/gate_runs.json` (229 rows):

| tier | latest | result |
|---|---|---|
| `run_selftests` | 2026-08-26T19:33:29Z | FAIL - `['hook-provenance']` only |
| `file_size` | 2026-08-26T19:33:06Z | PASS |
| `ship_bar` | 2026-08-26T19:33:07Z | PASS |
| **`integration`** | **2026-08-25T03:07:54Z -> RE-RUN 19:43:42Z** | **PASS 34/34** |
| `mutation_sweep_filtered` | 2026-08-24T21:23:01Z | PASS |
| **`mutation_sweep`** | **2026-08-20T17:28:15Z** | **FAIL - SIX DAYS** |
| `false_alarm_scorer` | 2026-08-20T13:46:26Z | PASS (age by design) |

**`integration` was stale by six minutes of commit ordering, and I nearly adjudicated it clean.**
The first reading was "no code changed since it ran, so it is not materially stale". The git log
said otherwise: `6aa7e65` landed at 03:14:16Z, **six minutes after** the 03:07:54Z run, and it
touched `hooks/wired_clone_sanity_selftest.py` - a file in `REQUIRED_HOOKS` and therefore in
integration's scope. Re-run: **34/34, rc=0**. Nothing was wrong, again - and again that was
unverified until it was run. **Second consecutive session that this tier was stale**, which is the
argument for item 17 and the reason it is not low-priority bookkeeping.

`mutation_sweep` is now six days stale, still the tier that would prove items 7 and 9, still
blocked behind item 2's pull. Stated again rather than allowed to fade.

## CHECK 5 - improvements worth considering

1. **The pull now blocks eight items**: 7, 8, 9, 15, the clean sweep, `mutation_sweep`, item 5's
   M10 fix, and item 15's best timing. It is one command.
2. **Item 17 has a trap that must be built in from the start**: `mutation_sweep` is permanently
   stale by design (CI cannot write the local ledger), so it must be exempted with a written
   reason or the new tier-age gate is red forever and gets switched off.
3. **Two of this session's three findings came from comparing against a DESIGN document rather
   than reading code** (the id/`ID_PREFIX` diff, the five-class `fingerprint()` enumeration). That
   is worth making the default for any unit that has a convention to conform to.

## CHECK 6 - mechanism health, and exactly ONE canonical order

**PASS.** `docs/NEXT_SESSION_PROMPT.md` still declares itself a pointer. Open items are **0-18,
verified contiguous by parsing the headings** (no repeat of the skipped-13 defect from the previous
close); standing checks 1-8 are the only other numbered sequence. Item 19 added by this pass.

Hooks: `[hook-health] 8 problem(s) across 31 hook commands, 1 wired clone(s) config-checked` - the
8 are all stale-root registrations, i.e. item 2's condition, and zero are machine-sanity.
`duplicate_registration_check --selftest` passes. The wired guard was re-probed after the id change
and still fires both directions.

## End-of-turn finalize

`docs/PLAN.md` carries one list, 0-19: 0-1, 3-6, 10 DONE with dates and commits; 2 PARTIAL and
blocking eight things; 7, 8, 9 blocked in a stated chain; 11-19 open. Every item raised in this
close was added to that list as it was raised, never in a side block.

## Deviation, stated as a deviation

`close_skills_guard` enforces RECENCY. The four skills were invoked, and the remediation they
produced - the `docs/PLAN.md` edits, the `settings.json` id correction - was written **after** the
invocations, so the guard's window is open. That is the intended audit->fix order rather than an
evasion, and every one of those edits is described in the artifact that prompted it. Stated here
because the rule is that a deviation gets named, including when naming it makes the report look
worse.
