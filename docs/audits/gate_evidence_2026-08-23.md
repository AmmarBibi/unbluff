# Gate evidence - v1.4.0, closed rows

The bodies of `docs/PLAN.md`'s closed gate rows, moved here VERBATIM on 2026-08-23 so the plan can hold its two-page rule. Nothing is summarised or dropped; the plan keeps the order and the verdict and links to each section below.

Why this file exists: the plan went 110 -> 254 lines in one session while the GATE COUNT STAYED FROZEN AT 11 and DONE went 0 -> 7. The growth was evidence, not scope - which is a filing problem, not a planning problem, and this is the fix.

## Gate 1 - Merge `main` into `feat/enforcing-verify`.

**DONE 2026-08-23.** Diverged 1 vs 17 at the
   merge. Exactly one conflicting file as predicted; resolved by RE-MEASURING the merged tree
   rather than by picking a side, which independently reproduced the planned union
   (`pre_push_gate_selftest.py` 1131 - main grew it, the branch's 1109 was stale;
   `tools/no_regression.py` out at 719, under the 800 limit). file-size gate rc 0, 5 offenders.
   Suite 38/39 - `hook-provenance` only, and see #39: that is a worktree artifact, rc 0 in the
   main checkout with a byte-identical sha.

## Gate 2 - Fix the execution model

(#25). **DONE 2026-08-23.** All three parts shipped; suite 39/40
   (`hook-provenance` only, see #39).
   - turn end: auto-detect KEPT, `hooks/fast_test_disclosure.py` added. **The plan said "naming
     the exact command" and that was wrong** - the exact commands are `npm test --silent` and
     `"<py>" -m pytest -x -q`, and neither names the untrusted part. It discloses the
     `scripts.test` BODY and the `conftest.py` files pytest imports. Keyed on the disclosed
     CONTENT, not the project, so a repo that changes what runs is disclosed again.
   - `--install-global` pre-push: auto-detect OFF unless `repo_opted_in()` - DERIVED from the
     presence of a shim naming `pre_push_gate.py`, so `--install` IS the consent record and there
     is no new state to drift. Declines loudly and ALLOWS the push.
   - `SECURITY.md` shipped.
   - Two defects found by probing rather than by review, both recorded because they generalise:
     (a) the disclosure import was first written inside `try/except ImportError`, which
     `install.py`'s `_import_closure` treats as OPTIONAL and drops from the install roster -
     MEASURED 26 unguarded vs 25 guarded, i.e. it would have been dead in silence on every
     installed machine; (b) a mutation SURVIVED because opt-in was tested only by presence, so a
     husky/lefthook `pre-push` counted as consent - scenario 15c now covers it. 4/4 killed after.

## Gate 3 - Prove the README subset

(#6, #28). **DONE 2026-08-23, and RE-CUT.** The "~30 README rows"
   framing is retired: it was unexecutable (nothing anywhere enumerated the ~30, nor the "three
   front-page sentences" - grep across this file and all of `docs/audits` found only the
   assertion that they exist) and it silently dropped the 91 `SKILL.md` claims, which are shipped
   surface. Population DERIVED from the inventory's own section headings and it reconciles:
   README 152 / 70 proven / 82 unproven + SKILL.md 91 / 15 / 76 = the recorded 243 / 85 / 158,
   and SKILL.md's unproven 76 is exactly A1's "~76 rows".
   **The re-cut: unproven is not false, and only FALSE is a release blocker.** The gate is the
   set of claims the repo's own tests CONTRADICT. Derived, and all fixed here:
   - "enables all eighteen pieces" - the README's own What's-inside list held 17 and the code
     ships 20. Three numbers, no two agreeing. `piped_gate_guard` and `timing_claim_guard` FIRE
     on a user's machine while being undocumented.
   - "It reuses `fast_test_on_stop`'s command detection" for the push gate - made false by
     gate 2 four hours earlier. Standing check 1 caught a defect introduced by the fix for the
     same class, which is the whole reason that check exists.
   - the pasted transcript: 39 vs 40, `gate modes: 16` vs 17, and `no-network: OK` missing since
     a80937c.
   **MECHANISM, not the third instance** (#40 closed with it): `check_readme_fresh` now derives
   the piece COUNT and the piece ROSTER from `install.py` + `skills/` and fails on either. It
   was shown failing on the real README first, naming all three missing pieces.
   **`findings.json` needs no rewrite, and that is the point of the re-cut.** Its
   `exclusion_basis` names criterion 1 as the only route back for 42 findings (10 HIGH). The
   rewrite was only ever needed because the old plan DELETED criterion 1. Criterion 1 survives as
   a post-release issue carrying the full 243/152/91 denominator, so the route stays open.

## Gate 4 - Mechanise the network claim

(#32a). **DONE 2026-08-22 (a80937c).** The README's strongest
   trust badge - "no network, no telemetry" - was enforced by nothing: a hook that opened a
   socket would have passed every gate. `tools/check_no_network.py` scans by AST (not grep - the
   file names every networking module and would flag itself), population DERIVED, fails closed,
   registered ENFORCING. 59 files / 0 reaches (re-derived 2026-08-23; it read 58 until this
   session added `hooks/fast_test_disclosure.py`, and the stale 58 sat in two documents until the
   close audit caught it - a population count in prose is a mutable count, so it carries a date);
   pinned NONET-BLIND + NONET-FLOOR. It flagged
   ITSELF on its first tracked run - `frozenset({...})` is a Call - which is the fires-on-correct-
   work shape; fixed by restricting to real spawns, with two negative controls so it cannot
   silently revert. NOTE #32's other items (demo GIFs, upgrade path, CONTRIBUTING, 103 absolute
   home paths in docs) are NOT done and stay in Phase 2.

## Gate 5 - Fix the shipped skill that audits documents it never read

(#16). **DONE 2026-08-23.** The
   PyMuPDF branch `return`ed unconditionally while the other two readers checked `.strip()`, so a
   scan yielded `"\n\n\n"` and the audit reported CLEAN. Twin of DOCX-1 in the same file, and it
   survived that fix - both have the shape where INSTALLING the better library makes the audit
   read LESS. Second half, not in the original row: falling through raised "No PDF text extractor
   available", which for a scan is false and sends the user to install what they already have.
   The two cases are now distinguished (missing reader vs no text layer -> OCR). Pinned as PDF-1
   through injected readers so the verdict does not depend on which pdf library the box has;
   3/3 mutations killed, including one asserting the chain still falls through an empty reader
   to a later one that can read the file - refusing early would trade silent-CLEAN for
   silent-refuse. SKILL.md states the refusal.

## Gate 6 - Fix `check_file_size`'s live C1

(#31). **DONE 2026-08-22 (1d90cff)** - every exit now routes
   through one `_record` helper; verified BY INDUCTION (an unparseable baseline writes
   `CANNOT_RUN`), not by reading the diff.

## Gate 7 - Make the release notes publishable

(#29). **PARTIAL - local half done 2026-08-23, publish
   step NOT done and it is the user's call, see below.** (Marker worded to survive a scan: the
   earlier "LOCAL HALF DONE" read as DONE to anything grepping for the word.) The row's diagnosis was WRONG and it mattered: `[Unreleased]` was
   called "19 KB of internal workflow ids and agent telemetry", but measured it held 19,241
   chars with **1** `wf_` id, **0** hex SHAs, **0** absolute paths, **0** scratchpad or temp
   refs. It was not telemetry - it was well-formed prose at maintainer depth, ~1,200 chars per
   bullet against `[1.3.1]`'s 4,072 chars for a whole release. "Strip the telemetry" is a
   20-minute delete; "compress maintainer prose to reader depth" is an editorial pass. Budgeting
   the first for the second is how this row sat undone.
   Done: the 19 KB moved VERBATIM to `docs/audits/changelog_v1_4_0_engineering_log.md` (it is the
   best record of why each change exists; deleting it would cost more than the notes gain), and
   a reader-facing `[1.4.0]` written at 5,285 chars against the 4,072 target.
   **NOT DONE, and deliberately not:** publishing the retroactive v1.3.1 GitHub Release. That is
   a public action and needs an explicit go-ahead. The notes for it already exist and are clean
   (`[1.3.1] - 2026-08-08`, 4,072 chars, 0 workflow ids), so it is one command when authorised.

## Gate 8 - Fix install/uninstall

(#30). **DONE 2026-08-23, and fixed at the CLASS rather than the
   instance.** The row framed this as an uninstall gap, but the harm is broader than uninstall:
   both shims embed an ABSOLUTE path to the clone, so moving, renaming or deleting it - not only
   uninstalling - made the shim run a missing script, return nonzero, and BLOCK EVERY `git push`
   ON THE MACHINE under `--install-global`, in repos with nothing to do with unbluff. The
   README's "keep the clone somewhere permanent" was the only thing standing between a user and
   that, which is prose where a control was needed.
   Both shims now fail **loud but open**: a missing gate prints `NOTHING WAS VERIFIED` on every
   push and allows it. Not silent - a quiet allow is indistinguishable from a clean run, the
   thing this project exists to prevent. `--install-global --remove` now also deletes the
   dispatchers it wrote (leaving them is how a stale path returns), and the README documents
   that `install.py --uninstall` does NOT undo it, because `install.py` never set it.
   Pinned as J1/J2 in `tests/test_integration.py`, executed with a real `sh` rather than by
   reading the template; 3/3 mutations killed and the reverted shim reproduces the reported
   harm exactly (rc=2, push blocked). Test placed there rather than in
   `pre_push_gate_selftest.py` because that file is a recorded size offender - see #41.
