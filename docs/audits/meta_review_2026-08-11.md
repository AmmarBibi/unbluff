# Meta-review - 2026-08-11 (close ritual, pass 4 of 4 - the synthesising pass)

Run **LAST**, as the order requires. On 2026-08-11 it was run FIRST and therefore never saw
`MUT-HANG`, a finding the later passes produced. Today it sees everything the three earlier
passes produced, which is the entire argument for the ordering.

All six checks run. **Checks 1 and 5 were the two skipped last time** and are done here in full.

---

## Check 1 - parked-but-unscheduled: 4 marker hits, 0 genuine

All four are prose about already-DONE items (`[DONE 08-11] ... ENTRY-GUARD`, `Pinned OPT-1`) or
the record of the previously-skipped steps. **No item is parked without a home.** Cross-checked
against pass 2, which independently found the one genuinely unhomed item
(`SELFTEST-BUDGET-FTOS`) and scheduled it.

## Check 2 - instance vs mechanism: THE finding of this pass

Applied to this session's four fixes:

| fix | durable? |
|---|---|
| `FASTTEST-BLOCK` detection + containment | **Yes** - 7 mutations pin it, both halves and both call sites |
| `CAP-FP-1` holding exemption | **Yes enough** - liveness-audited, self-reports DEAD when the detector is fixed |
| `meta_audit` budget regression | Instance; the mechanism is `SELFTEST-BUDGET-FLAKE`/`-FTOS`, already scheduled |
| **the `FTB-1`/`FTB-6` decorative-probe class** | **NO - and this is the gap** |

`OPT-1` and `FTB-1`/`FTB-6` are the **same defect shape** - *a probe whose outcome depends on
what happens to be installed* - discovered the same way **both times: a red CI run, after the
push.** Each was fixed per-incident (OPT-1 made its closure optional-aware; FASTTEST-BLOCK made
its probes synthetic). Neither stops the next probe acquiring the same dependency. By this
repo's own rule, both are instance fixes.

**Scheduled: `DEPRIVED-CI`** - run `run_selftests.py` *and* the mutation harness under a
`venv --without-pip` interpreter, as a CI job and a local target. Not speculative: it is exactly
how `FTB-1`/`FTB-6` were confirmed fixed today, locally, instead of a third CI round trip.

The asymmetry it closes matters and is easy to get wrong: **running the SUITE deprived proves
portability; running the MUTATION HARNESS deprived proves the pins still BITE there.** Only the
second catches `FTB-1`, which was green on a deprived box for a reason unrelated to the property
it claimed to test. This session made that exact error and caught it only from CI.

## Check 3 - optimization

**Three files over the 800-line rule, measured: 995 / 1154 / 852.** Two grew this session, and
the third (`fast_test_on_stop_selftest.py`, 852) is newly over and was named in no document
until pass 3. The rule is enforced by nothing. Prescription unchanged and correct: build the
line-count **gate**, then split. Row updated to say its own numbers are a snapshot, not a
control - it had three different pairs in circulation at once.

## Check 4 - missing / wrong: the GATE LEDGER, read not reconstructed

`gate_runs.json`: **200 entries, `{'run_selftests': 200}`**, newest `2026-08-11T20:05:14Z`.

This session ran the **mutation harness five times** (two of them the pytest-less runs that are
the *only* proof `FTB-1`/`FTB-6` now bite), the **integration test**, and **three CI rounds**.
Every one wrote nothing.

**"What proved the FTB pins?" is unanswerable from the durable record.** The evidence lives in
this ledger's prose and in a scratchpad directory that will be deleted. The finding was
previously abstract; it is now concrete, because the gate that validated the session's headline
fix is precisely the one that left no trace. **Priority raised.**

## Check 5 - improvements (skipped last time; run here)

1. **`DEPRIVED-CI`** (above) - highest value; closes a two-incident pattern. **Scheduled.**
2. **Gate-ledger writes from all five tiers** - the enabling change for check 4; without it every
   future session re-argues from prose. **Scheduled** (existing row, priority raised).
3. **`CA-SELFREF` is self-propagating** (pass 1): instance 3 is the ledger's record *of* instance
   2. The flag rate now rises monotonically with how carefully the project records its own
   findings - a direct tax on this repo's central practice. Strengthens an existing row; no new
   row. **Scheduled.**
4. **Not scheduled, offered:** the audit reports are accumulating one file per skill per session
   (four today). That is the accretion shape rule 7.3 warns about. Not acted on - it is a
   judgment call for the user, and inventing a retention policy unasked is the scope creep the
   plan warns against.

## Check 6 - mechanism health

- **`close_skills_guard` FIRED CORRECTLY on its own author** during pass 3, refusing the close
  because `meta-review` had not yet run. The guard works.
- It also demonstrated its known limit in the same moment: it saw one of four skills *missing*,
  but cannot see whether the three invoked ran to **completion**. This pass ran every step; the
  guard would have been equally satisfied otherwise. Row unchanged, evidence strengthened.
- `hook_health_check`: 30 hook commands verified at session start. Suite **33/33** on both a
  pytest-present and a pytest-less interpreter. Integration **30/30**. CI **green, 16 jobs**.
- **Exactly one canonical recommended-order list**: `NEXT_SESSION_PROMPT.md`. Refreshed this
  session; no competing block.

---

## The synthesis - what these four passes say together

**Three of the four problems this session were in the CHECKING INSTRUMENTS, not the product.**
`CAP-FP-1` (a guard flagging correct code), the `meta_audit` budget misattribution (a real
regression that nearly hid inside a known flake), and the decorative-probe class (two mutations
that could not fail). The production fix has been correct and stable since `25a87f2`.

That matches the repo's own recorded 7-of-11 and should now be treated as the base rate rather
than a surprise. Its practical consequence for the remaining plan: **step 4's false-alarm scorer
is itself a checking instrument, and on this base rate it should be budgeted for review as part
of writing it - not after.**

**The one thing today did not do:** every probe of `FASTTEST-BLOCK` was written by the author of
its fix. Twelve shapes passed. That is "12 shapes passed", never "no false alarm remains" - and
this session supplied fresh evidence for why the distinction is load-bearing, since two of those
author-written probes were decorative and CI, not review, is what said so. The independent pass
remains **owed and SCHEDULED**.
