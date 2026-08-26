# Consistency audit - 2026-08-26

**Scope: the unaudited delta.** The four artifacts dated `2026-08-25b` cover `ff251e2..6aa7e65`.
Commit `1443a59` (item 5's wiring) landed after them and was unaudited - 16 lines of prose in
`docs/PLAN.md` item 5. Tolerance: default rel 1%. Sources indexed: `docs/audits/gate_runs.json`,
the live `hook_health_check` output, the captured suite output.

## STEP 1 - mechanical pass

| class | raw | after adjudication |
|---|---|---|
| [A] number with no source match | 11 | **1 real** (below); 10 are DEFINITIONAL - nine are fragments of the timestamp `2026-08-25T01:15:51Z` (`08`, `25`, `15`, `51`) and two are the `-5` in `tail -5` / `head -5`, which are command literals |
| [B] [C] [D] [E] [F] | 0 | 0 |

The one real [A] hit is `31` ("hook-health went 30 -> 31 commands"), which the script matched
against 30 - the OLD value in the same sentence. **CONFIRMED** against the live run:
`[hook-health] 8 problem(s) across 31 hook commands`.

## STEP 2/3 - the reasoning pass, and four DRIFT findings

Every substantive claim in item 5's row was re-verified against the live system, not re-read:

| claim | verdict |
|---|---|
| registered as `unbluff-piped-gate`, PreToolUse, matcher `Bash\|PowerShell`, timeout 10 | **CONFIRMED** - read back out of the real `settings.json` |
| the matcher is what `install.py` DERIVES | **CONFIRMED** - `install.shell_tool_matcher()` returns exactly `'Bash\|PowerShell'`, and worktree and live `SHELL_TOOLS` are identical, so the hand-written entry matches what install would write |
| backed up to `settings.json.bak-2026-08-25-item5` | CONFIRMED - 40,034 bytes on disk |
| `run_selftests \| tail` -> rc=2; `ls \| head` -> rc=0 | CONFIRMED last session, both directions, against the wired copy |
| "with zero problems" | **DRIFT-1** |
| "one of the 12 stale files" | **DRIFT-2** |

### DRIFT-1 (fixed) - a scoped truth written as a plain one

The row read *"still reports `1 wired clone(s) config-checked` with zero problems."* Live output:
**8 problems across 31 hook commands, of which 0 are machine-sanity.** True under the scoped
reading, false under the plain one - and the plain reading is the one a reader takes. Fixed to say
"zero MACHINE-SANITY problems", naming the 8 and attributing them to item 2's condition (stale-root
registrations from running out of the worktree), which is not item 5's.

### DRIFT-2 (fixed) - and it is the whole BUILT IS NOT LIVE problem arriving one session early

The row said `piped_gate_guard.py` "is one of the **12** stale files". Re-derived at `1443a59`,
**2026-08-26T19:35:02Z**:

| population | at `ff251e2` (as the plan's table says) | at `1443a59` (now) |
|---|---|---|
| `hooks/*.py` | 12 of 26 | **14 of 28** |
| entry points that RUN | 5 of 10 | **6 of 11** |

Two causes, and the second is the finding:
1. `wired_clone_sanity.py` and its selftest exist in **no live copy at all** - so both the numerator
   and the denominator grew by 2.
2. **Wiring item 5 turned `piped_gate_guard` into an entry point, and it is stale.** The
   entry-point population went 10 -> 11 and the stale count 5 -> 6. *The act of closing item 5
   made BUILT IS NOT LIVE worse by one entry point.*

The plan's table is correctly PINNED to `ff251e2`, so it is not false - but two other places
restated the figure without a pin (item 2's body, item 5's caveat) and both were wrong within a
day. **That is the second consecutive session in which item 2's body drifted from the table it
copies** ("all four stale hooks" -> "five ... 12 of 26" -> "6 of 11 ... 14 of 28").

Fixed in all three places, each now carrying its instant and commit, plus an explicit note that
the table is a pinned measurement and the current figure differs. **This is item 15's argument,
demonstrated rather than predicted:** a number restated in prose in three places will drift in at
least one of them, every single session. Item 15 removes the restatement by deriving it in
`hook-provenance`.

## Cross-section consistency

`6 of 11` and `14 of 28` now appear in three places (the BUILT IS NOT LIVE section, item 2's body,
item 5's caveat) and agree in all three, each with the same instant `2026-08-26T19:35:02Z` and the
same commit `1443a59`. The superseded `12 of 26` survives only inside the explicitly-pinned
`ff251e2` table and in the history paragraph that exists to record the drift.

## Interpretation check

The narrative reading matches the numbers: item 5's row now says the wiring made the staleness
worse, which is what the derived figures show. Before this pass it said the opposite by omission -
it presented the stale copy as a caveat on item 5's usefulness rather than as an increase in item
2's cost.
