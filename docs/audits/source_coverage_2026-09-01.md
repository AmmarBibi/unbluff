# Source-coverage audit - 2026-09-01

**Run against the DESIGN of this session's decision-layer re-cut**, asking of every authority
section: *"what would the AUTHORITY write that I did not?"*

**Authorities**
1. `~/.claude/rules/ecc/common/tooling-discipline.md`
2. unbluff's own `docs/PLAN.md` - the 8 standing checks

**Subject:** the new `## Status and order` section; the restated bar that now RETIRES work rather
than sequencing it; item 20's added marker; item 34's corrected denominator; item 36; and the
DELETION of `check_tier_freshness.py` (`2c72620`) assessed as a design decision.

---

## THE FINDING: the authority would not have written this section as PROSE

`tooling-discipline` 7.3 is the whole file's generalisation: *"every section here exists because
prose was tried first and prose is advisory"*, and its rule is to route each instruction by
whether it must be REMEMBERED or ENFORCED - *"whenever you write down a warning, ask whether it
can be a check instead."*

**The new Status and order section is REMEMBER.** It is a hand-maintained list of 37 row numbers,
a closed/open split, and a tiered order. And the evidence against it is not theoretical:

- it claimed **36 rows / 18 open** and was stale **within the hour**, when the completeness pass
  added item 36;
- it carried **"1 of 45"** for the corpus denominator - copied from a row that had itself gone
  stale three days earlier - and the consistency pass caught it;
- the very defect it was written to prevent (item 20's status disagreeing with the session
  prompts for six days) is the same class it just committed twice against itself.

**So the honest verdict on my own work: I fixed the instance and built a new instance of the same
class in the same edit.** Standing check 1 asks exactly this - *"did this fix create a new
instance of the class it fixed?"* - and the answer is yes.

**What the authority would have written instead:** a check that PARSES the plan and asserts the
Status section's counts against the parse, failing when they disagree. It is ~15 lines, it is the
same parse already used three times in this session, and it converts the section from a claim into
a derived fact.

**Mitigation actually applied, and it is deliberately the smaller one:** the section now embeds
the one-line command that re-derives the numbers, and says *"re-derive it, do not read it."* That
is still REMEMBER. **Recorded here rather than built**, because the owner's standing instruction
this session was to prefer deleting over building and to stop when things work, and because a
plan-parsing gate is a gate on a document, not on the product. **This is a judgment call and it is
flagged as one, not hidden.** If the Status section goes stale a third time, build the check.

---

## Authority 2 - the 8 standing checks

| # | check | this session | verdict |
|---|---|---|---|
| 1 | new instance of the class it fixed? | **YES - see above.** The section fixing stale status went stale twice within the hour. Caught by the close passes, before the session ended. | **FINDING, recorded** |
| 2 | what would make this control UNABLE to fire? | Asked of item 36's subject: `MACHINE_STATE` has no floor, verified at `run_selftests.py:327`, no assertion on its size anywhere. | **PASS - and it produced item 36** |
| 3 | is the number derived, and derived just now? | Every count in the new section re-derived by parse; the parse itself was WRONG first (took the last `^N. **` match; the Retired section reuses numbers) and was corrected before use. | **PASS, after a self-correction** |
| 4 | is this surface actually LIVE? | Item 36 is scheduled precisely because `.claude/pre-push.cmd` runs `--code-only` - the liveness question is what made it Tier 1 position 0. | **PASS** |
| 5 | never edit while a gate is in flight | No gate was in flight this session. | N/A |
| 6 | a probe not shown to FAIL is not a probe | The order-completeness check was run BEFORE and AFTER adding item 36, and the second run is what proved it still total. | **PASS** |
| 7 | a finding is a hypothesis, and so is a prescribed fix | The reviewers' `MACHINE_STATE` claim was VERIFIED at the source line before being scheduled, not taken on their word. | **PASS** |
| 8 | **run it where it ships** | **SATISFIED, unlike last session.** CI ran on `2c72620` (17/17) and on `a33921d` (17/17), both including `mutation harness (do the tests bite?)` and `mutation harness (windows-only mutations)` - confirmed job-by-job, not inferred from the run conclusion. | **PASS** |

---

## Authority 1 - tooling-discipline

| section | this session | verdict |
|---|---|---|
| 1 scan the roster | four audit skills invoked; `adversarial-review` used for item 33 last session | PASS |
| 2 file work where an interruption cannot erase it | the plan now carries its own order - that IS the fix for this at plan scale | PASS |
| 3 a tool that writes to the repo | none run this session | N/A |
| 4 a green result that cannot fail is not evidence | `$?` captured explicitly on every run; CI verdict read per-job rather than from the rollup | PASS |
| 5 register a gate explicitly | item 36's fix is specified as an explicit assertion plus a mutation, not name-pattern detection | PASS |
| 6 never let the author write the only probe | the re-cut is my own work checked by my own skills. For a DOCUMENT this is proportionate; the code it describes was independently reviewed last session. | PASS, scoped |
| **7.1 point expensive tools where NOBODY has looked** | **PASS, and it is the session's best allocation.** The audits were pointed at the plan's DECISION LAYER - which had never had an order section at all, i.e. nobody had ever looked. It returned item 36, three stale claims and a six-day status disagreement. Contrast last session, which spent ~3 hours of sweeps on code written that day. | **PASS** |
| 7.2 content in a FILE, never through a shell | every commit message via Write + `git commit -F`, read back byte-identical | PASS |
| **7.3 REMEMBER vs ENFORCE** | **NOT SATISFIED - the Status section is prose.** See the finding above. | **FINDING, recorded** |

---

## The DELETION assessed as a design decision - would either authority object?

**No, and both support it.**

- `tooling-discipline` 4: *"a green result that cannot fail is not evidence."* The deleted gate was
  registered `("--selftest",)`, so its measurement and blocking modes never ran. It produced a
  green that could not fail, in a file whose 29 confirmed findings included a `--release` that
  returned 0 whenever git could not answer.
- `tooling-discipline` 7.3's whole thrust is that an unenforced mechanism is advisory. A gate
  nobody invokes is the limiting case.
- Standing check 4 (*is this surface actually LIVE?*) is the decisive one: it was not.
- The owner's restated bar - *"would I notice if this were never built?"* - answers itself.

**The one thing an authority WOULD have insisted on, and it was done:** the evidence outlived the
code. Item 17 keeps the three findings that generalise (a blocking gate failing OPEN from data
where no mutation can reach it; VERIFIED meaning "ran recently" regardless of pass/fail; a dead
parameter passing a selftest that exercised it) as the acceptance criteria if it is ever rebuilt.
Deleting the code without keeping those would have been the objectionable version.

---

## Ledger

| authority requirement | status |
|---|---|
| standing checks 2, 3, 4, 6, 7, 8 | SATISFIED |
| standing check 1 (new instance of the fixed class) | **FINDING - the Status section, recorded, caught in-session** |
| standing check 5 | N/A |
| tooling-discipline 1, 2, 4, 5, 6, 7.1, 7.2 | SATISFIED |
| **tooling-discipline 7.3 (REMEMBER vs ENFORCE)** | **NOT SATISFIED - judgment call, flagged not hidden** |
| the deletion as a design decision | SUPPORTED by both authorities |

## Verdict

One real finding, and it is against this session's own work: **the section written to stop the
plan's status going stale is itself hand-maintained, and went stale twice within an hour.** The
authority's answer is a 15-line parse-and-assert check; what shipped instead is the derive command
embedded in the prose. That is a deliberate, stated deviation under the owner's stop-when-it-works
instruction - not an oversight - and the trigger for revisiting it is written down: **if it goes
stale a third time, build the check.**
