# Source-coverage audit - 2026-08-27

Run **against the DESIGN**, not only the code, and phrased throughout as *"what would the
authority write that I did not?"*. This is the pass that reads the source of truth rather than
re-reading the plan, so it can find what the plan never mentions.

## 1. The authorities named

For a repo with no external specification, the authorities are the design notes that already
encode decisions - and the session's best findings last close came from diffing against exactly
these rather than from reading code.

| authority | what it governs |
|---|---|
| `tools/hook_divergence_report.py` module docstring | DERIVED-NEVER-LISTED; BOTH DENOMINATORS PRINTED; fail-closed |
| `.claude/pre-push.cmd` `[#45 2026-08-24]` | machine-state vs code gates at push time |
| `run_selftests.MACHINE_STATE` | a machine-state gate needs a written adjudication |
| `tools/gate_ledger.py` header | gate outcomes must be observable OVER TIME, not per-run |
| `docs/audits/file_size_baseline.json` notes | split-before-regrow; "AN INSTANT, NOT A CURRENT FACT" |
| `tooling-discipline.md` sections 3-7 | repo-writing tools, green-that-cannot-fail, REMEMBER vs ENFORCE |

## 2-3. Enumerate and reconcile

### CONFIRMED COVERED

| authority requirement | status | evidence |
|---|---|---|
| roster DERIVED, never listed | **BUILT** | `dispatcher_children()` recognises a dispatcher by SHAPE; finding the plan's 11 should be 16 came directly from obeying this |
| both denominators printed | **BUILT, for the provenance verdict** | `N ours / foreign / unparsed / bare` unchanged |
| fail-closed on uncertainty | **BUILT** | `_classify` returns `unreadable` as its own answer; counted and printed, never folded into "no difference" |
| machine-state gate adjudicated | **BUILT** | `hook-provenance` already in `MACHINE_STATE`; the count is machine-state and lives on that gate |
| split before re-record | **BUILT** | 803 -> 655 and 925 -> 667+321, both splits rather than a fifth re-record |
| repo-writing tool must be crash-safe | **BUILT, by avoidance** | the mutation battery copies into `tools/` and never opens the real file for writing - nothing to restore, no sentinel to leak |
| ambiguity must be SAID, not guessed | **BUILT** | >1 wired hooks dir withholds the files row and prints that it withheld it |

### GAPS - what the authority would have written and I did not

**GAP A (HIGH, and it is in code shipped today).** The file's own docstring: *"A provenance
check that examined nothing looks exactly like one that examined everything and found nothing
wrong."* `main()` obeys this for the verdict, with a two-cause NOTE distinguishing "no wiring
surface at all" from "surfaces read, zero commands parsed".

**The new count obeys neither.** Measured with an empty settings file: `entry_points()` returns
`{}` and the gate prints `BUILT IS NOT LIVE: 0 of 0 entry points stale`. That is
indistinguishable from a fully synced machine, and it is what every fresh CI checkout will
print. **I re-created, inside the same file, the precise fail-open that file was rebuilt to
eliminate** - while quoting its convention approvingly in the item-15 write-up.

Scheduled as **item 23**. Not deferred silently: applied as soon as the in-flight
`mutation_sweep` lands, because editing source mid-sweep is `tooling-discipline` section 3.

**GAP B (MEDIUM).** The tool advertises `--json out.json`. The payload contains
`matched/foreign/unparsed/bare/examined/our_hook_names/surfaces` and **none** of the item-15
counts, so a consumer of the JSON cannot see the number the item exists to publish. Same item 23.

**GAP C (MEDIUM) - the one the plan's own words demand and nobody scheduled.** `PLAN.md` says
of this number: *"The trajectory is the real point... every session that fixes something makes
the live machine MORE stale."* `gate_ledger.py`'s header exists because a per-run verdict is not
an observable trend.

**Item 15 deleted the prose that carried the trajectory and replaced it with a point-in-time
print.** The count is now correct and *has no history*. The authority would record it per run in
the ledger the way every tier's result is recorded; today's `0 of 16` is only meaningful against
yesterday's `6 of 11`, and that comparison is now impossible from the artifacts.

This is a genuine coverage gap created BY the fix: prose that was wrong but longitudinal was
replaced with a number that is right but instantaneous. Scheduled as **item 24**.

### FINALIZED EXCLUSIONS

- **CRLF normalisation limited to `\r\n` -> `\n`.** An authority might argue for normalising
  trailing whitespace too. Excluded deliberately and stated in the docstring: whitespace,
  comments and docstrings differing IS a different file, and noticing that is the gate's job.
- **`sync_phrase()` not recorded in the ledger.** Presentation, not a verdict.

## 4. Ledger

| source item | status |
|---|---|
| derived roster / by shape | BUILT |
| both denominators (verdict) | BUILT |
| both denominators (the COUNT) | **GAP A -> item 23** |
| `--json` completeness | **GAP B -> item 23** |
| trajectory observable over time | **GAP C -> item 24** |
| fail-closed on unreadable | BUILT |
| split-before-regrow | BUILT |
| crash-safe repo writes | BUILT (by avoidance) |
| line-ending normalisation scope | FINALIZED EXCLUSION |

## 5. Verify

Three gaps, none of which a grep of the plan could have found, because the plan never mentioned
any of them. All three came from reading a design note and asking what it would require. **Two
of the three are defects in code written today**, which is the argument for running this pass
against the design at the close of the session that wrote the code rather than a session later.
