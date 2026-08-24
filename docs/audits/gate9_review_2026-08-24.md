# Gate 9 - independent adversarial review, 2026-08-24

**Scope.** `feat/enforcing-verify` at `580ea57` against `b6cc6cc`. Denominator re-derived
2026-08-24T17:39:50Z and the inherited one was wrong:
`git diff --numstat b6cc6cc...580ea57 -- '*.py'` gives **2,799 Python lines added / 320 deleted
across 47 files**, not the "1,215 lines" gate 9's row had carried unverified for two sessions.

Pinned to the COMMIT, not to `HEAD`, and this session's own consistency audit is why: the first
draft of this line said `b6cc6cc...HEAD` and stamped it `19:39Z`. The time was wrong by two
hours, and by the time anyone read it `HEAD` had moved - the same range against HEAD already
gives **3,593 / 631** (19:47:47Z). A denominator that names a moving ref is a denominator that
will be quietly false, which is standing check 3 firing on the row that re-derives a denominator.

**Shape.** 8 lenses (guard-correctness, disarm, coverage-gap, fail-open, portability,
probe-validity, docs-vs-code, unreviewed-remainder), each finding adversarially refuted per
finding by an independent agent instructed to default to REFUTED when it could not confirm from
the code. 49 agents, 5.9M subagent tokens, 986 tool calls, 32 minutes. **34 findings survived
refutation, 6 were killed.**

**Two results worth stating before the findings.**

1. It independently predicted the CI failures **from the code alone**, while CI was still
   running - the pytest-only probes, the mutation-baseline abort, the job arithmetic.
2. **Three of the defects it found were in the #46 fix written the day before**, by the same
   author, already probed three ways and already documented as sound. That is section 6 of the
   tooling rules holding exactly: the author's probe set and the author's blind spot are the
   same object.

**Tree guard.** `fingerprint()` was byte-identical before and after the fan-out
(`head=580ea572... config=546ac3e97209a524 index=4a382405278bcd32`), so none of the 49
read-only agents wrote to the repository. This is the first run where that claim was measured
rather than asserted.

## Cleared in this session

| id | defect | resolution |
|---|---|---|
| H1 | two probes assert pytest-only outcomes; ~13 of 17 CI jobs red on correct code | `_pytest_importable` pinned in BOTH directions in `fast_test_disclosure`; `pre_push_gate_selftest` 15b made fixture-independent. Also fixed a FALSE PASS: `cmd_before` was None because pytest was absent, not because opt-in was refused |
| H2 | the choke-point scrub reached 1 of 4 fixture-spawning orchestrators, and this evidence file claimed all 4 | `mutation_check`, `test_integration` and `hook_health_check` (which SHIPS TO USERS) scrubbed explicitly; the false claim corrected in `gate0_evidence_2026-08-24.md` s2 |
| H3 | the #46 control's wiring pinned by nothing | partially addressed: `git-isolation` is a registered AUX row and the roster is now runtime-enforced. The AST assertion tying `scrub_environ()` to the first spawn is NOT built - carried as residue |
| H4 | `normpath` vs git's `GetLongPathNameW`: false red on 8.3 / junctioned / subst TEMP | `os.path.realpath`, matching `fast_test_on_stop.py:627-631`'s already-settled answer |
| H5 | README pasted `30/30` against a live 34, in the block headed "Don't take the demos on faith" | corrected to 34/34 and `readme-scenarios` BUILT - the `_SCEN_RE` gate prescribed by `p14_new_code_review.md:301` and never implemented, so the same defect drifted a third time |
| M2 | the check roster was 7 hand-typed names beside 9 failure sites | recorded at runtime, set-compared against `REQUIRED_CHECKS` |
| M7 | fingerprint terms individually deletable - a probe showed **3 of 6 SURVIVING** | `worktrees=` was hashing the branch and HEAD lines and covering for `head=`, `symref=` and `refs=`. Narrowed to paths; **7 of 7 now go red when deleted**, mutation-verified |
| M8 | fixture `config`/`add`/`commit` unchecked, so a gpgsign failure reads as a dead fingerprint | every fixture command rc-checked through one helper |

## Residue - surviving findings NOT fixed, scheduled in `PLAN.md` Phase 2

* **M1 `check_no_network`'s ALLOWED hatch is unusable.** `scan()` (:135) filters allowed hits out
  of `offenders`; `verdict()` (:146) then computes `stale = set(allowed) - {paths in offenders}`
  from that same filtered list, so `stale == set(ALLOWED)` identically. The first legitimate
  exemption makes the gate permanently red while asserting the exemption is no longer needed.
  Dormant (`ALLOWED` is empty) and it fails CLOSED, which is why it does not block. The `:51`
  docstring's "checked in BOTH directions" is enforced by nothing; the selftest pins the broken
  direction only.
* **M3 the `--code-only` disarm probe re-implements the routing instead of exercising it.**
  `run_selftests.py:725` builds a hardcoded `(("hook-provenance",1),("some-code-gate",1))` and
  re-types the predicate; the real one at :486 is `rc != 0 and code_only and label in
  MACHINE_STATE`, and `selftest()` never calls `main()`. Detection envelope is exactly
  "hook-provenance left MACHINE_STATE" - a strictness increase - so the silent edit that survives
  is adding a CODE gate TO `MACHINE_STATE`. Both `run_selftests.py:206` and
  `.claude/pre-push.cmd:18` assert "the selftest proves it".
* **M5 `no_regression` materialises predecessor source through a locale-decoded pipe.** `_git`
  (:217) uses `text=True` with no `encoding=`; cp1252 on this box, re-written as UTF-8 at :165.
  Already live-wrong on three units that contain non-ASCII. One such character in a REGISTERED
  unit makes `predecessor()` return the byte-identical HEAD blob, so `lost` is empty by
  construction and `no-regression: OK` is vacuous over a real regression. Fixed twice before
  per-site (`pre_push_gate.py:76-81`, `hook_divergence_report.py:240`) and never at the class.
* **M6 an excluded MACHINE-STATE failure still counts in `ran` and records `PASS, failed=[]`.**
  `record_gate_run` takes no `excluded` argument, so the durable row - the one meta-review CHECK 4
  is instructed to READ rather than reconstruct - says clean. Mitigated only by the unconditional
  block printed three lines above the contradicting verdict.
* **M9 `UNBLUFF_LEDGER_OFF` suppresses every ledger write silently.** The other two suppression
  paths announce themselves (a NOTE, a `_discontinuity` marker); this one is a bare `return`,
  while `unrecorded_tiers` - being textual - still prints "6 tier(s) still recording". This is
  #44's own fix one degree short.
* **M10 `piped_gate_guard` is disarmed by the word `pipefail` anywhere before the first pipe.**
  Verified by executing the branch code: `# remember set -o pipefail` on a preceding line, or
  `--log pipefail.log`, silently allows a DENY. Still a strict improvement on the prior
  `any(p in command)` spelling, and the looseness has a real false-alarm rationale
  (`bash -o pipefail -c '...'`), so this is a narrowing job.
* **M11 `CHANGELOG.md:75`** claims `mutation_check.py` "split 1415 -> 377 lines"; it was 645 at
  the commit that wrote the line. A `4cb9d81` qualification recording those sizes as an INSTANT
  was stripped when the line was re-cut. Belongs with #42.
* **L1** `check_repo_integrity` re-baselines onto the `FINGERPRINT-UNAVAILABLE` sentinel, then
  compares a constant to itself. Needs `.git` destroyed or its config syntactically corrupt to
  reach, and a loud FAIL has printed by then. Treat the sentinel as terminal.
* **L2** `fingerprint()`'s docstring says "a total snapshot"; nothing observes the WORKING TREE,
  so `git checkout -- .` is invisible. Unreachable from the #46 mechanism (`GIT_WORK_TREE` is
  scrubbed), and the accurate enumeration is four lines below. Delete the word or add `status=`.
* **L3** `fast_test_disclosure` writes its marker before printing the disclosure, so an
  unwritable `STATE_DIR` or a zero-byte marker suppresses the #25 notice permanently. Print
  first, then record.

## Coverage gap - what this review did NOT examine

Assembled from the eight lenses' own denominators. Anything here is **unreviewed, not clean.**

* **Never executed.** No lens ran `run_selftests.py`, any `*_selftest.py`, `mutation_check.py` or
  `test_integration.py` - the read-only constraint. No finding above is backed by an observed
  suite run; H1's and H4's consequences were inferred from code plus the repo's own MEASURED
  workflow comments. CI then confirmed H1 independently.
* **`tools/no_regression.py`'s ~400-line rewrite on this branch** is the largest unreviewed
  surface remaining. One lens read only its selftest apparatus and `predecessor()`/`_git()`.
* **~120 mutation entry BODIES** in `mutation_entries_a.py` / `_b.py` were grepped for anchors and
  never read. `noregress_selftest.py`'s 309 new lines were read structurally for git calls only;
  its assertions A-G are unadjudicated.
* **`docs/audits/gate_evidence_2026-08-23.md` was never opened by any lens** - and it is the file
  every gate 1-8 DONE row links to as its proof. A DONE row could be unsupported inside a file
  nobody in this review read. That is the single highest-value target for the next pass, on
  7.1's rule: point the expensive tools where nobody has looked.
* **Unverified numbers noticed but not filed:** `SECURITY.md:77`, `CHANGELOG.md:64` and
  `PLAN.md:59` all say "59 files, 0 reaches" against a live 60 - all three dated 2026-08-23,
  which is the stated mitigation, but it drifted again within a day of #42 correcting it from 58.
  And `git_isolation.py:79`'s "43 git invocations in 15 files" is unstated as to method; a crude
  grep gives 63 across 17.
