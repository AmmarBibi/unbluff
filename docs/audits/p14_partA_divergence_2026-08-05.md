# P14 Part A - the installed-hooks divergence: resolved, with the mechanism

Session 2026-08-05. Everything below was regenerated from source or measured; nothing is
carried over as an assertion. Drafted while the baseline mutation suite was in flight and
moved here only after it landed, because editing the repo during a gate run is a defect this
project has already paid for.

## Baseline confirmed FIRST (the brief's precondition)

| gate | result |
|---|---|
| full mutation suite | 84 declared, 82 executed, 2 not-runnable-here, **0 SURVIVED, 0 errors, exit 0** |
| `tools/no_regression.py` | **OK, exit 0**; predecessor `f3ebc8f0` saw 31 of 96, working tree sees 31; coverage 1 of 23 units (4%), 22 named |

`mutation_check` returns `1 if (survivors or errors) else 0`, so exit 0 is a complete proof
that both buckets were empty.

## Summary - the brief was right about the symptom and wrong about the surface

The brief said `~/.claude/hooks` is a stale copy that "ran silently for weeks". True. But it
named two files, and the corrected account changes the fix.

## 1. The roster, DERIVED, with its denominator

| set | count | members |
|---|---|---|
| repo `hooks/*.py` | **19** | - |
| installed `~/.claude/hooks/*.py` | **14** | - |
| in BOTH | **11** | close_skills_guard, fast_test_on_stop, hook_health_check, memory_hygiene_guard, meta_audit_on_stop, plan_defer_guard, pre_push_gate, rate_prompt, show_your_proof, stop_dispatcher, usage_snip_prompt |
| only in repo | **8** | capped_report, duplicate_registration_check, fast_test_on_stop_selftest, numbers_match_on_write, post_tooluse_dispatcher, pre_push_gate_selftest, selftest_budget, transcript_util |
| only installed | **3** | course_method_guard, ecc_script_check, run_local_selftests - genuinely ECC, not ours |

11 + 8 = 19 and 11 + 3 = 14: the partition is complete. **All 11 shared files were DIFFERENT
PROGRAMS** by AST comparison, deltas from 67 to 1437 tokens.

## 2. ROOT CAUSE - two wiring surfaces, two path conventions, nothing reconciling them

`install.py:63` builds its command from `os.path.join(HOOKS_DIR, script)`, repo-relative. The
live `~/.claude/settings.json` accordingly pointed every unbluff hook at
`Downloads\unbluff\hooks\`, with **zero** references to `~/.claude/hooks/*.py`. That surface
was correct and always had been.

The stale copy ran from git's surface instead:

```
git config --global core.hooksPath = C:/Users/ammar/.claude/githooks
  -> githooks/pre-push  ->  "C:/Users/ammar/.claude/hooks/pre_push_gate.py"   <- STALE
```

`install()` and `install_global()` write their shim with
`script=os.path.abspath(__file__)`, so **the shim pins whichever copy ran it**.
`--install-global` was run from `~/.claude/hooks` on 2026-07-28, and every push on this
machine went through that snapshot afterwards.

Two consequences the brief did not have:

- Because `core.hooksPath` is set **globally**, git ignores `.git/hooks` entirely. The
  per-repo `pre-push` shims in ghg-copilot, mishwar and unbluff were **inert**. Reading them
  (as this investigation first did) is actively misleading.
- **unbluff gated its own pushes with a stale, fail-open copy of its own gate.** Every
  "verified" push from this repo since 2026-07-28 was verified by the ancestor.

Blast radius was narrow, though - established by exact AST import scan, after a first grep of
mine got it wrong by filtering every line containing `#`: the installed gate's only local
import is `fast_test_on_stop`. **Exactly 2 of the 14 files were reachable.** The other 12 were
dead weight that LOOKED live, which is why they attracted hand-edits.

## 3. The two named divergences - adjudicated by measurement

### 3a. Source detection: DROP the glob mechanism

Fixture: a throwaway git repo with `README.md`, `src/app.py`, `deploy.sh`, `schema.sql`,
`data/factors/factors.json`, `main.tf`. Each implementation ran in its OWN subprocess with its
own `sys.path` - comparing them in one process silently resolves both `import
fast_test_on_stop` lines to whichever directory hit `sys.path` first, which would make them
look identical for the wrong reason.

| case | repo (NON_SOURCE_EXT deny-list) | installed (SRC_EXT allow-list + globs) |
|---|---|---|
| 1. `.json` newest, nothing declared - the f11eb95 scenario | sees the `.json` | **blind**, reports an older `src/app.py` |
| 2. **CONTROL** `.py` newest | sees it | sees it |
| 3. **FAIRNESS** `.json` newest, `source=data/factors/*.json` declared | - | sees it; the mechanism works when declared |
| 4. **GENERALITY** `.tf` newest, `.json` glob declared | sees `main.tf` | **blind**, reports the older `.json` |

The control passed on both sides, so the harness was live rather than rigged, and case 3 is
recorded because the glob deserves a fair test and passes its own.

**Case 4 is the verdict.** With the `.json` glob declared, the installed copy is still blind
one extension later. The deny-list answers the question for every repo with no declaration;
the glob is a per-repo roster somebody must remember to extend for every source extension they
ever add - the same premise Part B exists to abolish. **`read_source_globs` / `is_source` are
DISCARDED, not ported.**

The repo version is additionally better on three axes the brief did not name: it returns
`(None, reason)` when git FAILS, so an unanswerable question cannot resolve to the same value
as "answered, nothing changed" (the installed copy returns `(0.0, None)` for both); it passes
`-z` so a C-quoted or newline-bearing filename is still seen; and it COUNTS unreadable paths
and refuses to answer instead of silently continuing.

### 3b. Timeout: DISCARD, already fixed here

installed `PUSH_MAX_TIMEOUT_S = 3600` (bare scalar) vs repo
`PUSH_OPTIONS = {"timeout": (5, 7200), "debounce": (0, 86400)}` (per-option ranges, higher
ceiling). Both fix the P13 D5 clamp, but on expiry the installed copy prints "This push is NOT
verified" and `return 0` - it ALLOWS the push (line 152). The repo BLOCKS (`return 1`) with
the typed escape. That is D1-FIND-2, fixed in `4b855ac`, still live in the copy that gated
every push here.

**Nothing in the installed `pre_push_gate.py` was worth porting upstream.**

## 4. THE REPAIR (A5), and how it was verified

Order was load-bearing: re-point, verify, then delete. Deleting first would have left the
global dispatcher exec-ing a missing file and broken pushes in every repo.

1. `--install-global` re-run from the REPO copy: **22 dispatchers** (up from 16 - the P13 D8
   fix restoring seven names that had been silently killed), and it discloses the one it drops.
2. All 3 per-repo shims re-installed from the repo copy.
3. 12 stale files deleted (11 unbluff `.py` + one `.bak`). Backed up first. `state/` and the 3
   ECC scripts preserved. (`state/` held **69 files at the moment of the repair** and is a LIVE
   directory - hooks write markers into it continuously, so it read 70 an hour later. Recorded
   as a timestamped observation, not an invariant, so a later count is not mistaken for drift.)
4. Verified: suite 25/25, and the live gate path exercised directly - `exit 0`, printing
   "verified 257823s ago, no source touched since (docs/images excluded)".

**State ledgers do not collide.** The two variants key state differently - repo
`_state_key()` normalises to `c:/users/...`, the installed copy hashed `cwd.lower()` with
backslashes intact - so they produced different `fasttest-*.json` files. unbluff had **both**
present, proving both variants had been running against this repo with separate ledgers. So
findings 28/34 - the exact bug `_state_key` was written to fix - had reappeared at the
INSTALL boundary rather than inside one program. Post-repair the gate reads only records
written by the repo's own turn-end hook, which is the single source of truth the docstring
promises.

**The `source=` ordering landmine stays defused.** Re-installing ghg-copilot's shim resolved
its gate command to `set "GHG_RERANK=1" && ... -m pytest -q` - the real command, not
`source=...` - confirming the deliberately-below-the-command placement is still correct under
this repo's parser. That file was not touched.

## 5. THE GATE (A3) - provenance, not directory equality

`tools/hook_divergence_report.py` already existed, was listed in `run_selftests.NOT_A_GATE` as
`# reporting`, and its own docstring ended **"Exits 0 always; it is a report, not a gate."**
A report nobody runs, that cannot fail, whose roster was two hardcoded paths, is three
fail-opens in one file - sitting in the tool built to catch this very incident.

It has been rebuilt as a gate that asks **provenance**: for every hook this machine has WIRED,
does the script it runs live inside this repo? That question survives deleting the duplicate
directory; "diff A against B" does not - with B gone there is nothing to compare and the check
passes forever.

- **Roster DERIVED** from `hooks/*.py`; wiring derived from every settings layer Claude Code
  merges PLUS `core.hooksPath` (global and local) and each repo's `.git/hooks`.
- **Both denominators printed**: `19 our hook names / 3 surfaces / 54 commands examined /
  30 ours, 0 foreign, 0 unparsed, 22 bare-name`.
- **Fails closed**: a command naming one of our hooks with no extractable path lands in
  `unparsed` and exits 1. Non-extraction must never read as non-divergence.
- **`--selftest`** with planted offenders on both surfaces AND negative controls.
- Reuses `duplicate_registration_check._path_tokens` / `settings_layers` rather than growing a
  twin - the `shlex` fix (a home directory containing a space) would have been silently lost
  by a fresh regex.
- Wired as AUX gate; suite **24 -> 25**, README transcript updated in the same change.

**HISTORICAL CONTROL - it would have caught the real thing.** Run against the preserved
pre-repair `githooks` directory: **16 of 16 dispatchers FOREIGN**, naming
`C:/Users/ammar/.claude/hooks/pre_push_gate.py`. The plan's own D2 lesson was "preserve the
failing artifact, not only the fix"; this time it was preserved and used.

**Two false positives in my own first draft, caught by running it.** It read `.py` paths out
of shell COMMENTS (so 22 correctly-installed dispatchers looked foreign) and treated the bare
`grep -q pre_push_gate.py` marker token as a wiring. Both are now negative controls.

**Mutation A3a SURVIVED on the first attempt** - my most important test was decorative. The
assertion checked that the literal `"core.hooksPath"` still appeared in `_git_hook_dirs`;
mutation A3a emptied the scope loop and left the literal untouched. Presence is not behaviour.
Replaced with a behavioural test that builds a repo which actually SETS `core.hooksPath` and
requires the function to find it, which needed a `cwd` test seam. All three mutations now
CAUGHT.

An earlier draft of that same assertion grepped its own source file for `"hooksPath"` while
containing that literal - a guard that could never fail, the exact class this repo has already
recorded once. It is now scoped to `_git_hook_dirs`'s own AST so it cannot match itself.

## 6. A6 - the shim comment named a path the shim did not use

Both templates carried `# ... managed by ~/.claude/hooks/pre_push_gate.py` as a hardcoded
literal while the exec line came from `{script}`.

**MEASURED HARM, not theoretical.** During this repair,
`grep -rl '.claude/hooks/pre_push_gate.py' ~/.claude/githooks` returned **22 of 22 AFTER a
correct re-point**, because it matched the comment. The check written to prove the stale path
was gone reported the exact opposite of the truth. A shim's comment is the only thing a human
reads when auditing a git hook.

Fixed by templating the comment from the same `{script}` value. Pinned by
`_selftest_shim_self_reference`, which is **derived** - it discovers shim templates by shape
(`#!/bin/sh` prefix), prints its denominator (`2 shim template(s) checked: GLOBAL_SHIM, SHIM`),
and allows a bare filename token because `GLOBAL_SHIM` greps for one deliberately. Written
first, watched fail on both templates, then fixed. Mutation `pre_push_gate #A6` CAUGHT.

## 7. A4 - the in-flight-thread hook: NOT a twin, but the generic version is DECLINED

Checked against `show_your_proof` first, which fires on a success claim with **zero**
tool_use blocks. The candidate is the complement - tools ran and their output was never
adjudicated - so it is a genuine gap, not a twin.

**DECLINED as specified, for a mechanical reason.** "Referenced" is not decidable by a hook. A
tool result is routinely used without any textual echo - every `Read` that informs an `Edit`.
The mechanical proxy (does later assistant text quote the output?) would fire on ordinary
work, and this repo's standard for `show_your_proof` is explicit: silence is always
acceptable, a false nudge is not. A hook that nags on correct behaviour gets disabled, which
is strictly worse than none - the same argument that keeps D1-LIMIT's two hooks unwired.

**A narrow variant IS worth building and is scheduled** (not built here, per "consider, do not
build on spec"): fire only when the turn ends with an **unadjudicated FAILURE signal** - a
tool result carrying a non-zero exit or a `FAIL`/`SURVIVED`/`BLOCKED` marker - and no
subsequent tool call or assistant text follows it. That is mechanically decidable, carries
information (it can name the command and its marker), and matches the measured failure
exactly: the command returned, the reply pivoted to a mid-turn question, and the output was
never adjudicated. The always-on discipline stays in ECC where it belongs; this would be the
mechanical half.

## 8. D1-LIMIT - a THIRD instance, measured today

`meta_audit_on_stop --selftest` failed its budget at **30.50s against 17.50s**. It is
**unmodified** in this change set (`git status --porcelain` confirms), so an interleaved A/B
against an unmodified CONTROL was run rather than trusting the reading:

| case | runs (s) | median | plan baseline | factor |
|---|---|---|---|---|
| CONTROL `capped_report` | 0.33, 0.58, 0.23 | 0.33 | 0.20 | 1.7x |
| `meta_audit_on_stop` | 12.86, 14.70, 8.79 | **12.86** | 13.30 | **1.0x** |

The code did not get slower; the box was at 97% CPU with foreign work (another Claude session
at 3301s CPU, two `pytest` runs, `ollama`). The suite passed 25/25 on re-run.

**No invariant was weakened.** The budget is right and the INSTRUMENT is load-sensitive. This
is a third instance of D1-LIMIT and a new one: the previously named cases were
`fast_test_on_stop` and `pre_push_gate`, both deliberately unwired for this reason.
`meta_audit_on_stop` is **wired at 0.70 share** and is load-sensitive too, so the flakiness is
already shipped rather than merely anticipated. It strengthens the case that D1-LIMIT needs
CPU time or a calibration probe before any further hook is budgeted on wall clock.

## 9. Why nothing noticed

`git status` here is clean and says nothing about a directory outside the repo. The Claude
Code surface was correct, so every check that read `settings.json` agreed. The git surface is
configured by `git config`, which no gate in this repo read. And the one tool that would have
shown it could not fail by construction. That is four independent reasons for silence, and
only the fourth was a bug in something anyone had thought of as a guard.
