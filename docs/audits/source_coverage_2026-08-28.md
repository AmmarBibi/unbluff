# Source-coverage audit - 2026-08-28

**Run against the DESIGN, not the file inventory.** The question asked of every section:
*"what would the AUTHORITY write that I did not?"*

**Authorities**
1. `~/.claude/rules/ecc/common/tooling-discipline.md` - the user's own measured-failure ruleset,
   every section of which exists because prose was tried first and prose is advisory.
2. unbluff's own `README.md` + `docs/PLAN.md`'s **8 standing checks** - the repo's self-declared
   contract, read at every change.

**Subject** - what this session DESIGNED, commits `34f82eb..f10a242`: the gate registry cut, the
BUILT IS NOT LIVE trajectory, the tier-freshness gate, and the coverage work.

---

## Authority 2 - the 8 standing checks

| # | check | this session | verdict |
|---|---|---|---|
| 1 | new instance of the class it fixed? asked MID-session | asked, and it fired: the `files_withheld: 0` field reintroduced the identical-value-different-meaning defect ONE FIELD OVER from the `no_count` split built to prevent it. Caught before commit. | **PASS** |
| 2 | what would make this control UNABLE to fire? | asked of both readers before repointing (both proven fail-closed with their exact messages) and of the new gate. | **PASS** |
| 3 | is the number derived, and derived just now? | 1 stale number found by the consistency pass (`20 rows`, now 21) and labelled an INSTANT. | **PASS, 1 fixed** |
| 4 | is this surface actually LIVE? | **the CHECK ITSELF carried a false premise** - see below | **FINDING, fixed** |
| 5 | never edit while a gate is in flight | held across all four sweeps; tree verified clean before and after each. | **PASS** |
| 6 | a probe not shown to FAIL is not a probe | the sweep proved `TF-UTC` DECORATIVE and I rebuilt it; `TR-ZERO`/`TR-SILENT` shown to bite. | **PASS** |
| 7 | a finding is a hypothesis, and so is a prescribed fix | the plan's own trap map was a prescribed fix and was WRONG in two ways (see below). | **PASS** |
| 8 | **run it where it ships** | everything ran locally. **CI has seen none of it.** | **GAP** |

### Check 4 - the check was asserting the opposite of the truth about its own example

It read: *"`piped_gate_guard`, which is **NOT wired on this machine** and has never fired.
Verified 2026-08-24T21:20:34Z: zero occurrences in `settings.json`"*, and says explicitly that
**the check's whole value is the word NOT**.

Reality on 2026-08-28: item 5 (DONE, same file) WIRED it on 2026-08-25 as `unbluff:piped-gate`;
`settings.json` contains it; and **it fired twice on me during this session**, blocking two
commands that would have eaten a gate's exit status.

So a check read at every change carried a present-tense claim its own plan contradicted three
days earlier. This is the check's own defect class, one level up - and it was invisible to the
completeness and consistency passes because both read the plan as a TO-DO LIST. Only reading it
as an AUTHORITY surfaced it. **Fixed**: the example is dated and marked historical, the check is
unchanged, and it now says to re-derive liveness rather than trust any sentence in the file
including itself.

### Check 8 - the one this session did not satisfy

*"Run it where it ships. Six clean local suite runs missed a CRITICAL that appeared on the first
real `git push`; 41 local gates passed over an `install.py` that refused to install. The local
suite and CI have never once produced the same failure set."*

**5 commits are unpushed. `.github/workflows/selftest.yml` exists and has seen none of them.**
Every verdict in this session - suite 45/45, four sweeps, the new gate - is a LOCAL result.

Sharper still, in the sweep's own words: the 2 not-runnable mutations are *"proven by the OTHER
platform's job, not by this one. **If that job does not exist, they are proven NOWHERE.**"* This
session never confirmed that job runs. Recorded as the session's stated limitation rather than
absorbed - see the next-session prompt, which opens with it.

Not scheduled as a plan row: it is not a defect in the code, it is an unfinished verification
step for THIS branch, and it belongs in the handoff.

---

## Authority 1 - tooling-discipline.md

| section | demand | this session | verdict |
|---|---|---|---|
| 1 | scan the roster before hand-rolling | four audit skills invoked at close; `search-first` not needed (no vendored upstream touched) | PASS |
| 2 | file a task BEFORE answering an interruption | 4 tasks filed; findings survived | PASS |
| 3 | a tool that WRITES to the repo | sweeps ran in scratch trees; tree verified clean around each; **but see 7.1** | PASS |
| 4 | a green result that cannot fail is not evidence | `$?` captured explicitly every time - and it MATTERED: three task notifications reported "exit code 0" for sweeps whose real rc was 1 and 0 | **PASS, and it paid** |
| 5 | gates, snapshots, scope | new gate registered EXPLICITLY in `AUX_GATES` rather than relying on name-pattern detection | PASS |
| 6 | never let the author write the only probe | **NOT SATISFIED** - see below | **GAP -> item 33** |
| 7.1 | point expensive tools where NOBODY has looked | **NOT SATISFIED** - see below | **GAP, stated** |
| 7.2 | content goes in a FILE, never through a shell | every commit message written with Write, `git commit -F`, and read BACK byte-identical (4 for 4) | PASS |
| 7.3 | REMEMBER vs ENFORCE | the session's main theme; scratchpad probes were MOVED into the shipped battery for exactly this reason | PASS |

### Section 6 - the author wrote the only probe, and it showed

Section 6 requires an INDEPENDENT pass before calling a unit sound, and names the categories:
*"guard and gate logic, governance/routing/calculation, ... anything where the author also wrote
the only test."* All three modules shipped this session are in those categories, and all three
are named by `review-freshness` as never adversarially reviewed.

The section's argument is structural, not about care - *"the author's probe set and the author's
blind spot are the same object"* - and this session produced two textbook demonstrations inside
its own new code: the `TF-UTC` assertion passed while being decorative, and `head()` shipped a
fail-open its own selftest could not see. In both cases my reasoning had concluded the code was
correct; the sweep disagreed.

**Scheduled as item 33.** Items 7, 17 and 24 are currently DONE on the strength of gates written
by the same author who wrote the code.

### Section 7.1 - all four sweeps were pointed at what I had just written

Section 7.1 is measured, with a table: a 5.88M-token fan-out over a doc written 40 minutes
earlier yielded 24 findings; a 1.51M-token fan-out over eight days of unexamined plan state
yielded 123 findings and 9 CRITICALs. *"The cheaper run was worth several times more."* Its rule:
**ask "when did anyone last look here?"** If the answer is "an hour ago", spend less.

This session ran **four full mutation sweeps, roughly three hours**, every one of them over code
written in the same session. Two of the four earned it outright (MODE-1, TF-UTC), so the spend
was not wasted - but by 7.1's own measure it is the EXPENSIVE half of the trade, and nothing this
session pointed at unexamined state.

**What the authority would have written that I did not:** a pass over the parts of this repo
nobody has looked at in weeks. `review-freshness` names them for free every run - 44 UNREVIEWED
units and 18 STALE ones, some last reviewed 2026-07-31. That is the "nobody has ever looked here"
surface, and it is enumerated already.

Stated rather than scheduled as a new row: item 33 covers this session's three modules, and the
broader backlog is what `review-freshness` exists to keep asking. The finding for the handoff is
the ALLOCATION rule - next session, spend on the unexamined surface before spending on freshly
written code.

---

## Authority 2b - the README as contract

`readme-fresh`, `readme-jobs`, `readme-pieces` and `readme-scenarios` all pass, and the 44 -> 45
selftest change was caught by the gate rather than by me. No README claim was found that this
session's design fails to uphold.

One confirm-don't-assume item: the README pastes a transcript including the gate roster. It now
lists `tier-freshness` and `21 row(s) examined, 7 adjudicated`. Those are derived numbers checked
by `readme-fresh` for the count, but the ROSTER LINE itself is hand-pasted prose - a gate added
without touching that line would leave it silently short. Not a new row: it is the same class as
item 15 and is bounded by the four readme gates already in place.

---

## Ledger

| authority requirement | status |
|---|---|
| standing checks 1, 2, 3, 5, 6, 7 | SATISFIED |
| standing check 4 (surface actually live) | **FINDING FOUND IN THE CHECK ITSELF - FIXED** |
| standing check 8 (run it where it ships) | **NOT SATISFIED - stated, carried to handoff** |
| tooling-discipline 1, 2, 3, 4, 5, 7.2, 7.3 | SATISFIED |
| tooling-discipline 6 (independent probe) | **NOT SATISFIED - SCHEDULED as item 33** |
| tooling-discipline 7.1 (aim at unexamined state) | **NOT SATISFIED - stated, allocation rule for next session** |

## Verdict

Reading the plan as an AUTHORITY rather than as a to-do list found a defect that both other
passes missed: **standing check 4 was asserting the opposite of the truth about its own example,
and had been for three days.** Two design-level omissions are recorded honestly rather than
absorbed - no CI verification of any of this session's five commits, and no independent review of
three gate-layer modules whose author is also their only prober. Both qualify the confidence of
the three DONE items this session shipped, and both are in the handoff.
