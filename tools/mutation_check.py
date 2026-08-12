#!/usr/bin/env python3
"""Mutation harness: revert each fix on a scratch copy and require the suite to go RED.

A test that stays green when you delete the code it covers is decorative. Three tests written
on 2026-07-29 asserted things the implementation could not violate, and the v1.3.0 release was
declared closeable twice while 34 defects sat in it - both because "the suite passes" was read
as "the suite asks the right questions". This turns that into a mechanical check.

Each mutation names the plan finding it reverts. A mutation whose suite stays GREEN is a
FAILURE of this harness: it means the regression test for that finding does not bite.

    python tools/mutation_check.py                 # every mutation
    python tools/mutation_check.py pre_push_gate   # only mutations for one hook

Mutations marked posix_only=True are skipped on Windows (os.chmod exec bits are a no-op
there), so they are the ones only CI can prove. posix_only="nt" is the mirror: windows-only
code that does not exist on POSIX, which must SKIP on Linux rather than report SURVIVED.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Source trees copied into each scratch tree. `hooks/` ALONE meant a fix in tools/ or in a
# top-level entry point could not be mutation-tested at all - the harness that certifies every
# other fix as pinned had a blind spot covering its own directory, and the review-freshness
# gate meant to notice such things omitted tools/ for the same reason (P13 A1). Both halves of
# the evidence base were unwatched at once.
COPY_TREES = ("hooks", "tools", "tests", "skills")
COPY_FILES = ("install.py", "run_selftests.py")


def unit_path(root: str, name: str) -> str:
    """Resolve a mutation target to a path under `root`.

    A bare name is a hook (`hooks/<name>.py`) - the original and still commonest form. A name
    containing "/" is repo-relative (`tools/check_review_freshness`), which is what lets this
    harness reach the gate tooling.

    A bare name that is NOT a hook falls back to the repo ROOT. Without that fallback the two
    files in `COPY_FILES` - `install.py` and `run_selftests.py` - had no addressable form at
    all: a bare name went to `hooks/`, and a repo-relative name needs a "/" they do not have.
    The harness copied them into every scratch tree and could not mutate either, so the single
    most user-facing file in the repo - the one a user actually runs - was uncoverable BY
    CONSTRUCTION while the summary line printed a clean total. That is the INSTALL-TAUTOLOGY
    shape again: a roster not derived from what the code does.

    `hooks/` is probed FIRST so every pre-existing entry resolves exactly as before - this is
    strictly additive, and a name present in both places keeps its old meaning rather than
    silently changing target.
    """
    if "/" in name:
        return os.path.normpath(os.path.join(root, *(name + ".py").split("/")))
    hooked = os.path.join(root, "hooks", name + ".py")
    if os.path.isfile(hooked):
        return hooked
    rooted = os.path.join(root, name + ".py")
    if os.path.isfile(rooted):
        return rooted
    return hooked  # absent either way: report against the conventional location


def missing_anchors(live_text: str, edits) -> list:
    """The `find` strings in `edits` that no longer appear in `live_text`.

    ONE implementation, shared by `run()` below and by `tools/check_mutation_anchors.py`. A
    second copy of this rule in the standalone gate would be the twin defect this repo hunts:
    that gate exists to say something about what this harness actually does, and a gate whose
    rule has quietly diverged from the harness reports on a program nobody runs.
    """
    return [find for find, _replace in edits if find not in live_text]


# (unit, finding, description, [(find, replace), ...], posix_only[, verify_unit])
# `unit` is a hook name, or a repo-relative path like "tools/check_review_freshness".
MUTATIONS = [
    ("pre_push_gate", "1", "git output decoded with the locale codec again (non-ASCII paths)",
     [('_GIT_TEXT = {"encoding": "utf-8", "errors": "surrogateescape"}', "_GIT_TEXT = {}")], False),
    ("pre_push_gate", "1b", "_repo_root stops checking the decoded root exists",
     [("    if root and not os.path.isdir(root):\n        return None\n", "")], False),
    ("pre_push_gate", "3/11", "newest_source_mtime ignores git's exit code again",
     [('    if r.returncode != 0:\n        return None, "<git ls-files failed>"',
       '    if False:\n        return None, "<git ls-files failed>"')], False),
    ("pre_push_gate", "2/12", "source detection back to the SRC_EXT allowlist",
     [("if os.path.splitext(rel)[1].lower() in NON_SOURCE_EXT:",
       "if os.path.splitext(rel)[1].lower() not in fast_test.SRC_EXT:")], False),
    ("pre_push_gate", "4", "ls-files back to C-quoting (no -z)",
     [('"--exclude-standard", "-z"]', '"--exclude-standard"]'),
      ('(r.stdout or "").split("\\0")', '(r.stdout or "").splitlines()')], False),
    ("pre_push_gate", "9a", "last_pass trusts a non-dict state file again",
     [("    if not isinstance(st, dict):\n        return 0.0\n", "")], False),
    ("pre_push_gate", "9b", "last_pass stops guarding the float coercion",
     [('    try:\n        return float(st.get("ts") or 0.0)\n    except (TypeError, ValueError):\n        return 0.0',
       '    return float(st.get("ts") or 0.0)')], False),
    # [P14 A6] The shim's "managed by" comment is the only thing a human reads when auditing an
    # installed git hook. Hardcoding it made a grep for the STALE path match a correctly-installed
    # shim - 22 of 22 during the 2026-08-05 repair - so the check written to prove the stale copy
    # was gone reported the opposite of the truth.
    ("pre_push_gate", "A6", "a shim template hardcodes a path it does not exec again",
     [("# Universal pre-push gate - managed by {script}",
       "# Universal pre-push gate - managed by ~/.claude/hooks/pre_push_gate.py")], False),
    # [P14 A3] The provenance gate. A3a is the FAIL-OPEN direction and the one that matters:
    # git's hook surface is where the stale copy actually ran, so a gate that stops reading it
    # reports a clean machine while every push runs a foreign copy. A3b and A3c are the
    # fail-LOUD direction - a gate that fires on a correct install gets disabled by its owner,
    # which is strictly worse than no gate.
    ("tools/hook_divergence_report", "A3a", "the provenance gate stops reading core.hooksPath",
     [('for scope in ("--global", "--local"):', 'for scope in ():')], False),
    ("tools/hook_divergence_report", "A3b", "shell COMMENTS read as wirings again (false alarms)",
     [("if not ln.lstrip().startswith(\"#\")", "if True")], False),
    ("tools/hook_divergence_report", "A3c", "a bare basename is classified as a foreign copy again",
     [('if "/" not in t and "\\\\" not in t:', "if False:")], False),
    # The bounded runner and the shared state key live in fast_test_on_stop - BOTH gates use
    # them, so that is where the mutation must be applied. pre_push_gate's selftest is what
    # catches it, which is the point: the twin is covered, not just the instance.
    ("fast_test_on_stop", "10", "run_tests back to subprocess.run (unbounded pipe)",
     [("    t = threading.Thread(target=reader)\n    t.daemon = True   # can never keep this "
       "process alive, whatever the pipe does\n    t.start()\n",
       "    t = threading.Thread(target=reader)\n    t.daemon = True\n    t.start()\n"
       "    try:\n        _r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,\n"
       "                            text=True, timeout=timeout_s, encoding='utf-8',\n"
       "                            errors='replace')\n        return _r.returncode, "
       "(_r.stdout or '') + (_r.stderr or '')\n    except subprocess.TimeoutExpired:\n"
       "        return None, ''\n")], False),
    ("fast_test_on_stop", "28/34", "state key back to cwd.lower() (the two gates diverge)",
     [("    try:\n        p = os.path.realpath(cwd)\n    except OSError:\n        p = cwd\n"
       '    return os.path.normcase(os.path.abspath(p)).replace("\\\\", "/")',
       "    return cwd.lower()")], False),
    ("pre_push_gate", "5", "dispatcher back to --git-dir (breaks linked worktrees)",
     [("git rev-parse --git-common-dir", "git rev-parse --git-dir")], False),
    ("pre_push_gate", "6", "install() assumes <root>/.git/hooks again",
     [('    dest = os.path.join(hooks_dir, "pre-push")',
       '    dest = os.path.join(root, ".git", "hooks", "pre-push")')], False),
    ("pre_push_gate", "27", "CLIENT_HOOKS floor loses the seven missing names",
     [('                "pre-merge-commit", "reference-transaction", "fsmonitor-watchman",\n'
       '                "p4-changelist", "p4-prepare-changelist", "p4-post-changelist", '
       '"p4-pre-submit")', "                )")], False),
    ("pre_push_gate", "8", "the 'tests passed' message is dropped",
     [('    sys.stderr.write(f"[pre-push] tests passed in {time.time() - started:.0f}s - '
       'allowing push.\\n")', "    pass")], False),
    ("pre_push_gate", "7", "the dispatcher's pre-push branch never matches",
     [('if [ "$hook" = "pre-push" ]; then', 'if [ "$hook" = "never-matches-anything" ]; then')],
     False),
    ("pre_push_gate", "30", "install() stops chmod-ing the per-repo hook",
     [("    os.chmod(dest, 0o755)\n    cmd, _ = resolve_command(root)",
       "    cmd, _ = resolve_command(root)")], True),
    # These three classes now live in transcript_util (both hooks import it), so the mutation
    # applies THERE and is verified through close_skills_guard - the consumer whose suite must
    # go red. That split is the point: a shared rule needs a test in a hook that uses it.
    ("transcript_util", "13", "genuine-user detection back to content[0] only",
     # [P14 M-M12] The anchor carries the `type == "text"` line because the two-line version
     # matched BOTH first_text() and has_tool_result() - MEASURED: 2 occurrences. Since
     # .replace(..., 1) edits the first hit, re-ordering those two functions would silently
     # have re-pointed this entry at a fix it was never written for, while it went on
     # reporting CAUGHT. This harness validates anchors by PRESENCE, not uniqueness; the
     # general fix (fail on any anchor matching != 1) is scheduled as M-M12 in cluster 2.
     [('    if isinstance(content, list):\n        for block in content:\n'
       '            if isinstance(block, dict) and block.get("type") == "text":',
       '    if isinstance(content, list):\n        for block in content[:1]:\n'
       '            if isinstance(block, dict) and block.get("type") == "text":')], False,
     "close_skills_guard"),
    ("transcript_util", "17", "harness-injected entries counted as the user again",
     [('    return bool(entry.get("isMeta") or entry.get("sourceToolUseID"))',
       "    return False")], False, "close_skills_guard"),
    ("close_skills_guard", "33", "one non-dict JSONL entry disables the guard again",
     [("                if isinstance(obj, dict):\n                    yield obj",
       "                yield obj")], False),
    ("close_skills_guard", "14/15/16", "main() stops writing the message",
     [("        if code == 2 and message:\n            sys.stderr.write(message)", "        pass")],
     False),
    ("duplicate_registration_check", "20/23", "registrations collapse into a set of roots again",
     # ANCHOR UPDATED 2026-08-05 (P14 B3). The entry encoding grew event/matcher/invocation
     # fields, so the old anchor stopped matching and this mutation became UNRUNNABLE - it
     # reported HARNESS ERROR rather than silently passing, which is the only reason it was
     # noticed. A fix that disarms another finding's test while the suite stays green is the
     # failure P13 hit three times; here the FULL re-run caught it and the filtered run did not.
     [('            registered[tail].append("%s|%s||%s|%s|%s" % (head, scope, event, matcher, full))',
       '            entry_ = "%s|%s||%s|%s|%s" % (head, scope, event, matcher, full)\n'
       "            if entry_ not in registered[tail]:\n"
       "                registered[tail].append(entry_)")], False),
    ("duplicate_registration_check", "21/22", "paths scraped by regex again (spaces break it)",
     [('        toks = shlex.split(text, posix=False)   # posix=False: Windows backslashes '
       "survive",
       '        toks = __import__("re").findall('
       "r'[^\"\\s]*[/\\\\\\\\][A-Za-z0-9_.-]+\\.py', text)")], False),
    ("duplicate_registration_check", "25", "an unknown digest votes SAME FILE again",
     [("        if any(v is None for v in values):", "        if False:")], False),
    ("duplicate_registration_check", "24/26", "only ~/.claude/settings.json is audited again",
     [("    for layer in settings_layers(settings_path, cwd):",
       "    for layer in [settings_path or SETTINGS]:")], False),
    # --- second-review defects (D5/D6/D7) ---
    ("fast_test_on_stop", "D5", "repo probe back to isdir(.git) (dead in every worktree)",
     [('    if not is_git_worktree(cwd):\n        return 0',
       '    if not os.path.isdir(os.path.join(cwd, ".git")):\n        return 0')], False),
    ("fast_test_on_stop", "D5b", "is_git_worktree back to a filesystem probe",
     [('    try:\n        r = subprocess.run(["git", "-C", cwd, "rev-parse", '
       '"--is-inside-work-tree"],',
       '    if True:\n        return os.path.isdir(os.path.join(cwd, ".git"))\n'
       '    try:\n        r = subprocess.run(["git", "-C", cwd, "rev-parse", '
       '"--is-inside-work-tree"],')], False),
    # The review's own mutation: a SPELLING VARIANT that the structural regex cannot match, so
    # only the behavioural check catches it. Before M6 this printed SELFTEST OK - the twin
    # guard grepped for a literal that appeared inside its own assertion.
    ("meta_audit_on_stop", "M6", "repo probe swapped for a variant the regex cannot see",
     [("    if not cwd or not fast_test.is_git_worktree(cwd):",
       '    if not cwd or not os.path.isdir(os.path.join(cwd, ".gitx")):')], False),
    ("meta_audit_on_stop", "D5-twin", "meta_audit keeps its own .git probe again",
     [("    if not cwd or not fast_test.is_git_worktree(cwd):",
       '    if not cwd or not os.path.exists(os.path.join(cwd, ".git")):')], False),
    ("fast_test_on_stop", "D6", "a bad optional line discards the command again",
     [("            except ValueError:\n                sys.stderr.write(",
       "            except ValueError:\n                return None, DEFAULT_TIMEOUT_S, "
       "DEFAULT_DEBOUNCE_S\n            if False:\n                sys.stderr.write(")], False),
    ("fast_test_on_stop", "D6b", "the malformed-option warning goes silent",
     [('                sys.stderr.write(\n                    f"[fast-test] {name} line {num}: '
       'ignoring malformed {key}="',
       '                _ = (\n                    f"[fast-test] {name} line {num}: '
       'ignoring malformed {key}="')], False),
    ("pre_push_gate", "D7", "install() ignores core.hooksPath again",
     [("    hooks_dir, via_hooks_path = _hooks_dir_for(target)",
       "    hooks_dir, via_hooks_path = (os.path.join(_common_git_dir(target) or '', 'hooks'), "
       "False)")], False),
    ("transcript_util", "D8", "origin shortcut jumps ahead of the synthetic filter again",
     [('    if is_synthetic(content):\n        return False\n    origin = entry.get("origin")',
       '    origin = entry.get("origin")\n'
       '    if isinstance(origin, dict) and origin.get("kind"):\n'
       '        return origin.get("kind") == "human"\n'
       "    if is_synthetic(content):\n        return False")], False, "close_skills_guard"),
    ("duplicate_registration_check", "D9", "selftest reads the invoking cwd's real config again",
     [('            out_ = "\\n".join(audit(p, cwd=cwd or hermetic))',
       '            out_ = "\\n".join(audit(p, cwd=cwd))')], False),
    # WINDOWS-ONLY in effect, and it took a CI round to see why. Dropping the saved pgid is a
    # genuine no-op on POSIX: start_new_session makes pgid == proc.pid, and _kill_tree already
    # falls back to proc.pid, so it kills the same process group either way. SURVIVED on ubuntu
    # was a true statement about the MUTATION, not about the test - the honest fix is to say
    # what platform it actually exercises, not to keep re-timing the fixture (P13 F). The
    # POSIX half of the same cleanup is covered by D10c below.
    ("fast_test_on_stop", "D10", "kill_tree loses the saved pgid / job (grandchild survives)",
     [("        _kill_tree(proc, pgid, job)  # release the pipe; never leave what we spawned "
       "running",
       "        _kill_tree(proc)")], "nt"),
    # WINDOWS-ONLY by construction: _win_job_kill_on_close() already returns None on POSIX, so
    # this edit is a literal no-op there and "SURVIVED" would be a statement about the platform,
    # not about the test. CI reported it as a decorative test for exactly that reason (P13 F).
    ("fast_test_on_stop", "D10c", "the POSIX kill stops being group-wide (only the direct "
     "child dies, the grandchild lives)",
     [("                os.killpg(target, signal.SIGKILL)",
       "                os.kill(target, signal.SIGKILL)")], True),
    ("fast_test_on_stop", "D10b", "the Windows job object is never created",
     [("    job = _win_job_kill_on_close()", "    job = None")], "nt"),
    # --- FASTTEST-BLOCK: a repo that is not a pytest project must never be BLOCKED ---
    # MEASURED before the fix: 7 of 10 repo shapes hard-blocked a turn end (rc 2) with nothing
    # wrong, and the same detect() blocked their pushes. Two halves - detection and exit-code
    # containment - each pinned on BOTH sides, plus both call sites, because the helper being
    # correct proves nothing about whether either gate consults it.
    ("fast_test_on_stop", "FTB-1", "a bare tests/ dir is proof of a pytest project again "
     "(the original defect: Cargo's tests/ dir blocked every Rust turn end)",
     [("    return _has_collectible_tests(tests_dir) is not False", "    return True")], False),
    ("fast_test_on_stop", "FTB-1b", "pytest CONFIG files stop counting, so a real pytest "
     "project whose tests live outside tests/ loses its gate entirely",
     [("    for name, marker in _PYTEST_CONFIG_MARKERS:", "    for name, marker in ():")], False),
    ("fast_test_on_stop", "FTB-2", "detect() stops asking whether pytest is importable, so a "
     "box without pytest gets rc 1 - indistinguishable from a real failure",
     [("    if looks_like_pytest_project(cwd) and _pytest_importable():",
       "    if looks_like_pytest_project(cwd):")], False),
    ("fast_test_on_stop", "FTB-3", "rc 4 / rc 5 are treated as verdicts again",
     [("    return _PYTEST_INCONCLUSIVE.get(rc)", "    return None")], False),
    ("fast_test_on_stop", "FTB-4", "main() stops CONSULTING inconclusive_reason (the wiring, "
     "not the helper - check 7's lesson in this same file)",
     [("        reason = inconclusive_reason(cmd, rc)", "        reason = None")], False),
    ("fast_test_on_stop", "FTB-5", "the pytest-command test matches anything, so pytest's exit "
     "table is applied to npm/go/cargo and a GENUINE failure there is waived",
     [("    return re.search(", "    return True or re.search(")], False),
    ("pre_push_gate", "FTB-6", "the PUSH gate stops consulting inconclusive_reason, so a run "
     "that collected nothing blocks the push as 'tests are failing'",
     [("        reason = fast_test.inconclusive_reason(cmd, rc)", "        reason = None")], False),
    # --- FTB-RC4 / FTB-MASK: found by the independent pass (wf_a6b49ecf-667), NOT by the
    # author who wrote both the fix and its probes. The first is a false NEGATIVE the fix
    # INTRODUCED - the more dangerous direction than the false alarm it was removing.
    ("fast_test_on_stop", "FTB-7", "rc 4 goes back into the waiver, so a BROKEN conftest.py - "
     "the user's own code, zero tests run - is silently waved through by both gates",
     [('_PYTEST_INCONCLUSIVE = {\n    5: "pytest collected no tests, so nothing was verified",\n}',
       '_PYTEST_INCONCLUSIVE = {\n    5: "pytest collected no tests, so nothing was verified",\n'
       '    4: "pytest could not start (usage or collection error), so nothing was verified",\n}')],
     False),
    ("fast_test_on_stop", "FTB-8", "the no-gate marker drops the REASON from its key again, so "
     "the first notice permanently masks every later, different one",
     [("    np = _nogate_state_path(cwd, kind)", "    np = _nogate_state_path(cwd)")], False),
    ("hook_health_check", "D11", "the weekly sweep loses its aggregate budget",
     [("        if time.monotonic() >= deadline:", "        if False:")], False),
    ("hook_health_check", "D11b", "sweep progress is no longer persisted per hook",
     [("        _persist()\n\n    n = len(done)", "\n    n = len(done)")], False),
    # --- item 45: the eight previously-unreviewed hooks ---
    ("numbers_match_on_write", "H1", "ref-prefix regex loses its left word boundary",
     [('    r"(?<![A-Za-z])"\n    r"(?:figure|fig|table', '    r"(?:figure|fig|table')], False),
    ("numbers_match_on_write", "H2", "a report is indexed as its own evidence again",
     [("            if os.path.normcase(os.path.abspath(fpath)) in skip:\n"
       "                continue\n", "")], False),
    ("numbers_match_on_write", "H3", "trailing # comments leak into config values again",
     [("        val = val.split(\"#\", 1)[0]\n", "")], False),
    ("memory_hygiene_guard", "H4", "sanitize_cwd back to replacing only : \\ /",
     [('    sanitized = re.sub(r"[^a-zA-Z0-9]", "-", cwd)\n'
       "    return sanitized if len(sanitized) <= PROJECT_DIR_MAX else "
       "sanitized[:PROJECT_DIR_MAX]",
       '    return cwd.replace(":", "-").replace("\\\\", "-").replace("/", "-")')], False),
    ("memory_hygiene_guard", "H5", "main() stops returning 2 when rot is found",
     [("    sys.stderr.write(\"\\n\".join(out) + \"\\n\")\n    return 2",
       "    sys.stderr.write(\"\\n\".join(out) + \"\\n\")\n    return 0")], False),
    ("show_your_proof", "H6", "harness injections accepted as real prompts again",
     [("    return transcript_util.is_genuine_user(entry)",
       "    if entry.get(\"type\") != \"user\":\n        return False\n"
       "    content = get_content(entry)\n"
       "    if isinstance(content, str):\n        return True\n"
       "    if isinstance(content, list):\n"
       "        return any(isinstance(b, dict) and b.get('type') == 'text' for b in content)\n"
       "    return False")], False),
    ("transcript_util", "H6b", "the shared classifier stops rejecting synthetic text",
     [("    if is_synthetic(content):\n        return False\n", "")], False),
    # --- item 45 MEDIUMs ---
    ("numbers_match_on_write", "M1", "an empty source index passes silently again",
     [('        dead = [e for e in cfg["sources"]', '        return 0, ""\n        dead = [e for e in cfg["sources"]')],
     False),
    ("numbers_match_on_write", "M2", "the display cap is reported as the total again",
     [("            if len(findings) >= MAX_FINDINGS_TRACKED:\n                break",
       "            if len(findings) >= MAX_BULLETS:\n                break")], False),
    ("numbers_match_on_write", "M3", "line numbers back to count() per match (quadratic)",
     [("        out.append((bisect.bisect_right(newlines, start - 1) + 1, raw, value, "
       "is_percent))",
       '        out.append((text.count("\\n", 0, start) + 1, raw, value, is_percent))')], False),
    ("memory_hygiene_guard", "M4", "quarantine latch opens on prose again",
     [("        stripped = line.lstrip()\n        if stripped.startswith(\"#\"):",
       "        if QUARANTINE_RE.search(line):\n            in_quarantine = True\n"
       "            continue\n        stripped = line.lstrip()\n"
       "        if stripped.startswith(\"## \"):")], False),
    ("plan_defer_guard", "M5", "marker keyed by session only again (2nd plan file skipped)",
     [('    marker = marker_path(state_dir, payload.get("session_id") or "nosession", path)',
       '    marker = marker_path(state_dir, payload.get("session_id") or "nosession")')], False),
    # [DOCX-1 2026-08-08] The first mutations to reach a SHIPPED SKILL script. install.py
    # copytree()s skills/ onto the user's machine and close_skills_guard BLOCKS the close until
    # consistency-audit is invoked, so this file is squarely in the shipped path - it was simply
    # outside the ship gate's entry-point derivation. Verified through the skill's own gate.
    ("skills/consistency-audit/scripts/extract", "DOCX1a",
     "the docx reader prefers python-docx again, so Word TEXT BOXES go unread and the audit "
     "certifies a deliverable clean for a number it never looked at - installing the "
     "recommended optional dependency makes it read LESS",
     [("        return _docx_to_text_stdlib(path)",
       '        raise ExtractError("forced fallback")')], False,
     "skills/consistency-audit/scripts/audit"),
    ("skills/consistency-audit/scripts/extract", "DOCX1b",
     "runs are collected per-paragraph with .iter() again, so a nested text-box paragraph is "
     "counted TWICE and every number the audit reports on such a document is inflated",
     [('    own: Dict[int, List[str]] = {}\n'
       '    for run in root.iter(_WORD_NS + "t"):\n'
       '        para = _nearest_para(run)\n'
       '        if para is not None:\n'
       '            own.setdefault(id(para), []).append(run.text or "")',
       '    own: Dict[int, List[str]] = {}\n'
       '    for para in root.iter(_WORD_NS + "p"):\n'
       '        own[id(para)] = [n.text or "" for n in para.iter(_WORD_NS + "t")]')], False,
     "skills/consistency-audit/scripts/audit"),
    # [SKIP-1 2026-08-08] CONFIRMED by the ship-gate adversarial review. HIGH-1's own recorded
    # fix could not work: an age stamp recomputed on every write measures nothing.
    ("hook_health_check", "SKIP1", "the slice age stamp is refreshed to today on every sweep, so "
     "it can never age out - one permanently-skipping hook then freezes every other hook's "
     "recorded pass forever behind an '[hook-health] OK' line",
     [("    started_on = slice_started or datetime.date.today().isoformat()",
       "    started_on = datetime.date.today().isoformat()")], False),
    # [GLOB-1 2026-08-08] CONFIRMED by the ship-gate adversarial review, then reproduced: a
    # matched bracket pair in the INSTALL PATH ('unbluff-main[1]' is what Windows names a
    # re-downloaded zip) made glob match nothing, so the sweep "verified" 0 of 22 hooks, printed
    # OK, and wrote a marker suppressing itself for a further week. Both halves pinned, because
    # either one alone restores a blind sweep. Fixed repo-wide - 13 sites - not just here: the
    # repo already had this class fixed in check_review_freshness ALONE, which is why it was
    # still live everywhere else.
    ("hook_health_check", "GLOB1a", "selftestable_hooks stops escaping the directory, so a "
     "bracket in the install path silently reduces the weekly sweep to zero hooks",
     [('sorted(glob.glob(os.path.join(glob.escape(d), "*.py"))) if has_selftest(p)]',
       'sorted(glob.glob(os.path.join(d, "*.py"))) if has_selftest(p)]')], False),
    ("hook_health_check", "GLOB1b", "all_hook_files stops escaping the directory, so the "
     "DENOMINATOR silently goes to zero and every coverage ratio reads as complete",
     [('sorted(glob.glob(os.path.join(glob.escape(hooks_dir or _HOOKS_DIR), "*.py")))',
       'sorted(glob.glob(os.path.join(hooks_dir or _HOOKS_DIR, "*.py")))')], False),
    ("hook_health_check", "18", "the weekly sweep goes back to a hardcoded roster",
     [('    d = hooks_dir or _HOOKS_DIR\n    return [p for p in sorted(glob.glob(os.path.join('
       'glob.escape(d), "*.py"))) if has_selftest(p)]',
       "    d = hooks_dir or _HOOKS_DIR\n"
       "    return [os.path.join(d, n) for n in _LOCAL_HOOKS_FLOOR]")], False),
    # The twin lands in a DIFFERENT file from the test that catches it - which is precisely
    # what a twin defect is - so this one mutates usage_snip_prompt and verifies with
    # hook_health_check. Written as a real second definition, since the guard is anchored.
    ("usage_snip_prompt", "19", "a second selftest detector is reintroduced in another file",
     [("def main() -> int:",
       "def has_selftest(path):\n    return False\n\n\ndef main() -> int:")], False,
     "hook_health_check"),
    ("hook_health_check", "32", "a skipped selftest is counted as a pass again",
     [("    if not problems and not n_skipped:", "    if not problems:")], False),
    # ---- P13: the never-adjudicated findings. These are the FIRST mutations this harness has
    # ever been able to apply outside hooks/ - the gate tooling was unreachable until the
    # copy-tree widening above, which is the same blind spot as A1 itself.
    ("tools/check_review_freshness", "A1", "units() back to the hooks-only roster (tools/ and "
     "tests/ unwatched)",
     [('UNIT_GLOBS = ("hooks/*.py", "tools/*.py", "tests/*.py", "scripts/*.py",\n'
       '              "skills/*/scripts/*.py", "install.py", "run_selftests.py")',
       'UNIT_GLOBS = ("hooks/*.py", "install.py", "run_selftests.py")')], False),
    ("tools/check_review_freshness", "A1b", "_tracked() returns an empty set instead of None "
     "when git cannot answer",
     [("    if r.returncode != 0:\n        return None\n    return {x.replace",
       "    if r.returncode != 0:\n        return set()\n    return {x.replace")], False),
    # P13 E: D3/D4 were already FIXED, but the adjudication found NO test that bites. "Fixed"
    # and "pinned" are different claims and only one of them was true. Both anchors target the
    # returncode branch - git RUNS fine against a path that does not exist and simply exits
    # non-zero, which is the ordinary shape of "git could not answer".
    ("tools/check_review_freshness", "E1", "[D3] dirty_units returns an empty set when git "
     "cannot answer",
     [("    if r.returncode != 0:\n        return None\n    out = set()",
       "    if r.returncode != 0:\n        return set()\n    out = set()")], False),
    ("tools/check_review_freshness", "E2", "[D4] last_change reports a date when git could not "
     "answer",
     [('    if r.returncode != 0:\n        return None\n    return (r.stdout or "").strip() or None',
       '    if r.returncode != 0:\n        return ""\n    return (r.stdout or "").strip() or None')],
     False),
    # ---- P13 D: the remaining never-adjudicated findings.
    ("plan_defer_guard", "D1", "plan-file matching back to a `*plan*.md` SUBSTRING glob "
     "(explanation.md becomes a plan)",
     [("    return any(tok in _PLAN_TOKENS for tok in re.split(r\"[^a-z0-9]+\", base[:-3]) if tok)",
       '    import fnmatch\n    return fnmatch.fnmatch(base, "*plan*.md")')], False),
    ("meta_audit_on_stop", "D1b", "meta_audit grows its own plan-file glob again",
     [("            if plan_defer_guard.is_plan_file(n) and os.path.isfile(os.path.join(cwd, n))]",
       '            if "plan" in n.lower() and n.lower().endswith(".md")\n'
       "            and os.path.isfile(os.path.join(cwd, n))]")], False, "plan_defer_guard"),
    ("plan_defer_guard", "D2", "the exemption branch stops being load-bearing",
     [("    if _EXEMPT_RE.search(line):\n        return False", "    if False:\n        return False")],
     False),
    # [P14 B2] The twin guard, rebuilt fail-closed. B2a/B2b are the two axes the predecessor
    # was blind on - it enumerated 4 identifiers over 1 non-recursive directory and missed 6 of
    # 6 novel twins while catching 5 of 5 controls. B2c pins the unreadable-file reporting: a
    # file the guard could not parse must never be counted as clean.
    ("transcript_util", "B2a", "twin guard back to a non-recursive hooks/ scan",
     [("    for dirpath, dirnames, filenames in os.walk(root):",
       "    for dirpath, dirnames, filenames in [(here, [], os.listdir(here))]:")], False),
    ("transcript_util", "B2b", "twin guard back to enumerated NAMES only (behaviour ignored)",
     [("            if marks or tags:", "            if False:")], False),
    ("transcript_util", "B2c", "an unparseable file is silently skipped again",
     [("                unreadable_paths.append(rel)", "                pass")], False),
    ("transcript_util", "D4", "an image-only prompt is not a turn boundary again",
     [("    return first_text(content) is not None or has_user_media(content)",
       "    return first_text(content) is not None")], False),
    ("fast_test_on_stop", "P13-D5", "the push gate shares the turn-end 600s ceiling again",
     [('PUSH_OPTIONS = {"timeout": (5, 7200), "debounce": (0, 86400)}',
       'PUSH_OPTIONS = {"timeout": (5, 600), "debounce": (0, 86400)}')], False),
    ("fast_test_on_stop", "P13-D6", "the Stop gate keys shared state on the SESSION dir again",
     [("    cwd = project_root(cwd)\n", "")], False),
    ("pre_push_gate", "D8", "--install-global stops disclosing the hook names it drops",
     [("    return tuple(sorted(all_client_hook_candidates() & HIGH_FREQUENCY_HOOKS))",
       "    return ()")], False),
    # ---- STEP2 SH: the three sh-delegation paths. Until 2026-08-09 each caught OSError,
    # printed "SELFTEST SKIP: sh unavailable" and CONTINUED, so on any box without `sh` on PATH
    # three of this gate's own tests verified nothing while the suite exited 0 and
    # run_selftests reported 32/32. All four mutations below are cross-platform on purpose: a
    # guard whose failure branch is only reachable on a shell-less machine is a guard no runner
    # can prove, which is the shape of defect this repo exists to catch.
    ("pre_push_gate_selftest", "SH-1", "the shell resolver goes back to finding nothing",
     [("    tried = []\n\n    def _works(path):",
       "    tried = []\n    return None, tried\n\n    def _works(path):")],
     False, "pre_push_gate"),
    ("pre_push_gate_selftest", "SH-2", "a skipped delegation site stops being a failure",
     [('    if skipped:\n        fails.append("no POSIX shell was found',
       '    if False:\n        fails.append("no POSIX shell was found')],
     False, "pre_push_gate"),
    ("pre_push_gate_selftest", "SH-3", "a delegation site that was never REACHED stops failing",
     [('    if missing:\n        fails.append("sh-delegation site(s) never REACHED',
       '    if False:\n        fails.append("sh-delegation site(s) never REACHED')],
     False, "pre_push_gate"),
    ("pre_push_gate_selftest", "SH-4", "the candidate walk collapses to the one-level "
     "derivation that misses the mingw64 layout",
     [("    for _ in range(4):  # bounded: no git layout nests its shell deeper than this",
       "    for _ in range(1):  # bounded: no git layout nests its shell deeper than this")],
     False, "pre_push_gate"),
    # ---- SH-5..SH-7 pin the three defects an INDEPENDENT adversarial review found in SH-1..SH-4
    # (run wf_feb7202e-8fe, 24 findings produced / 24 adjudicated / 14 confirmed). Every one of
    # them was a property the original guards ASSERTED but did not PIN, so each mutation below
    # would have survived on every platform before the fix - which is what the review measured.
    ("pre_push_gate_selftest", "SH-5", "the raw usr/bin shell is preferred over the "
     "environment-setting bin/sh again (MEASURED: raw = no coreutils on PATH)",
     [('        for rel in (("bin", "sh"), ("usr", "bin", "sh"),\n'
       '                    ("bin", "sh.exe"), ("usr", "bin", "sh.exe")):',
       '        for rel in (("usr", "bin", "sh"), ("bin", "sh"),\n'
       '                    ("usr", "bin", "sh.exe"), ("bin", "sh.exe")):')],
     False, "pre_push_gate"),
    ("pre_push_gate_selftest", "SH-6", "the extension-less shell candidates are dropped "
     "(they were asserted by NOTHING before the review)",
     [('        for rel in (("bin", "sh"), ("usr", "bin", "sh"),\n'
       '                    ("bin", "sh.exe"), ("usr", "bin", "sh.exe")):',
       '        for rel in (("bin", "sh.exe"), ("usr", "bin", "sh.exe")):')],
     False, "pre_push_gate"),
    ("pre_push_gate_selftest", "SH-8", "UNAVAILABLE collapses back into 'skipped', turning an "
     "environment incapability into a selftest FAILURE (the false alarm step 2 introduced)",
     [("    skipped = sorted(n for n, ok in sites if ok is False)\n"
       "    unavailable = sorted(n for n, ok in sites if ok is None)",
       "    skipped = sorted(n for n, ok in sites if not ok)\n"
       "    unavailable = []")],
     False, "pre_push_gate"),
    ("pre_push_gate_selftest", "SH-7", "the delegation numerator goes back to subtraction, "
     "which under-reports and can print a negative count",
     [("    ran = {n for n, ok in sites if ok is True} & required",
       "    ran = range(len(required) - len([1 for _n, o in sites if o is False]) - "
       "len(required - {n for n, _ in sites}))")],
     False, "pre_push_gate"),
    # ---- INT-MUT: the integration suite's FIRST mutation coverage. 30 scenarios had zero, so
    # a scenario that silently stopped asserting - exactly what A2 did until it drifted - would
    # keep printing "30/30 scenarios passed", which is this repo's own definition of the absence
    # of evidence. That gap mattered more after step 2, not less: criterion 4 is now claimed
    # BUILT on three platforms on the strength of this suite, and running an unverified suite on
    # three runners multiplies it rather than verifying it.
    #
    # The plan recorded INT-MUT as BLOCKED ("mutation_check verifies through a unit's
    # --selftest, so either test_integration.py grows one (it is a script, not a unit) or the
    # harness learns to verify through a command"). That premise is REFUTED by measurement:
    # test_integration.py ignores argv entirely and exits 0 on pass / 1 on fail, so
    # `python tests/test_integration.py --selftest` already satisfies the verify contract
    # unchanged. Measured 2026-08-09: rc=0. No harness change was needed.
    #
    # DENOMINATOR: 2 of 30 scenario-groups are pinned here, not 30. This closes INT-MUT's
    # "zero mutations" state and proves the mechanism; full per-scenario coverage stays
    # SCHEDULED in the ledger.
    ("install", "INT-1", "install_skill stops copying bundled scripts (SKILL.md only again)",
     [('        shutil.copytree(src, dest, dirs_exist_ok=True,\n'
       '                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))',
       '        os.makedirs(dest, exist_ok=True)\n'
       '        shutil.copy2(os.path.join(src, "SKILL.md"), os.path.join(dest, "SKILL.md"))')],
     False, "tests/test_integration"),
    ("install", "INT-2", "install_skill ships only the first skill (the v1.1.1 drift)",
     # ANCHOR UPDATED 2026-08-11: install_skill gained dest_root/src_root params so the
     # SKILLDIR-DESTROY cases could be driven without a fake HOME. Second anchor drift caused
     # by this session's own refactors; both times the harness said HARNESS ERROR rather than
     # passing quietly, which is the only reason either was noticed.
     [("    src_root = src_root or SKILLS_DIR\n    for name in SKILL_NAMES:",
       "    src_root = src_root or SKILLS_DIR\n    for name in SKILL_NAMES[:1]:")],
     False, "tests/test_integration"),
    # ---- INSTALL-TAUTOLOGY (CRITICAL, criterion 2). The partial-checkout guard globbed
    # hooks/*.py into its required set and then asserted those files exist - the same statement
    # twice, so the globbed half could never report a single missing name. Real coverage was the
    # hardcoded floor alone: 16 of 25, leaving 9 unguarded and 5 of those imported by production
    # hooks. Both mutations verify through install.py's OWN new --selftest, which is reachable
    # only because unit_path gained the repo-root fallback earlier this session.
    ("install", "IT-1", "the partial-checkout guard goes back to globbing the directory it "
     "validates (a tautology: 9 of 25 hook files unguarded)",
     # ANCHOR UPDATED 2026-08-09: the walk moved into _import_closure when the skill roster
     # became a second caller, so the old anchor stopped matching. The harness reported
     # HARNESS ERROR rather than passing quietly, which is the only reason it was noticed -
     # the same way P14 B3 was caught.
     [("    required = _import_closure(hooks_dir, REQUIRED_HOOKS)",
       "    import glob as _glob\n"
       "    required = set(REQUIRED_HOOKS)\n"
       "    required.update(os.path.basename(p)\n"
       "                    for p in _glob.glob(os.path.join(_glob.escape(hooks_dir), '*.py')))")],
     False, "install"),
    ("install", "IT-2", "_resolves_outside stops removing the hook dirs from sys.path, so a "
     "PRESENT intermediate reads as external and its transitive deps drop out",
     [("    blocked = {os.path.normcase(os.path.abspath(src_dir)),\n"
       "               os.path.normcase(os.path.abspath(HOOKS_DIR))}",
       "    blocked = set()")],
     False, "install"),
    # ---- ENTRY-GUARD, the sibling INSTALL-TAUTOLOGY had to be fixed with (ledger K3).
    # ---- SKILLDIR-DESTROY: unbluff destroying the USER's own data, both directions.
    ("install", "SD-1", "install merges into a skill directory it did not create again, "
     "overwriting the user's same-named skill",
     [("        if os.path.isdir(dest) and _read_skill_manifest(dest) is None:",
       "        if False:")],
     False, "install"),
    ("install", "SD-2", "uninstall goes back to rmtree of the WHOLE directory, deleting a "
     "skill that predates unbluff",
     [("        files = _read_skill_manifest(dest)\n"
       "        if files is None:",
       "        shutil.rmtree(dest, ignore_errors=True)\n"
       "        files = _read_skill_manifest(dest)\n"
       "        if files is None:")],
     False, "install"),
    ("install", "OPT-1", "an import guarded by try/except ImportError is treated as REQUIRED "
     "again - the defect that turned all 16 CI jobs red on c488ab3",
     [('    import ast\n'
       '    names = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}',
       '    import ast\n'
       '    return False\n'
       '    names = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}')],
     False, "install"),
    ("install", "EG-1", "a missing SKILL.md stops being reported, so install ships "
     "close_skills_guard demanding a skill the user never received",
     [('        if not os.path.exists(md):\n'
       '            missing.append(os.path.join(name, "SKILL.md"))\n'
       '            continue',
       '        if not os.path.exists(md):\n'
       '            continue')],
     False, "install"),
    ("install", "EG-2", "the skill-script roster goes back to globbing the directory it "
     "validates - INSTALL-TAUTOLOGY reproduced one directory over",
     [('        seeds = sorted(set(re.findall(r"scripts/([A-Za-z0-9_]+\\.py)", text)))',
       '        seeds = sorted(os.path.basename(p) for p in __import__("glob").glob(\n'
       '            os.path.join(skills_dir, name, "scripts", "*.py")))')],
     False, "install"),
    # ---- P13 C: the malformed-input cluster. A checker that crashes or goes quiet on bad
    # input is indistinguishable from one reporting a clean bill of health.
    ("stop_dispatcher", "C1", "a crashed hook is recorded as a clean rc=0 again",
     [("                results[key] = CRASH_RC", "                results[key] = 0")], False),
    ("post_tooluse_dispatcher", "C1b", "the TWIN dispatcher records a crash as clean again",
     [("                results[key] = CRASH_RC", "                results[key] = 0")], False),
    ("rate_prompt", "C2", "a non-string prompt reaches .strip() again",
     [("    prompt = _as_text(prompt).strip()", '    prompt = (prompt or "").strip()')], False),
    ("hook_health_check", "C4", "_iter_hook_commands stops type-guarding the containers",
     [("    hooks_cfg = cfg.get(\"hooks\") if isinstance(cfg, dict) else None\n"
       "    if not isinstance(hooks_cfg, dict):\n        return\n    for groups in "
       "hooks_cfg.values():\n        if not isinstance(groups, list):\n            continue",
       "    for groups in (cfg.get(\"hooks\") or {}).values():\n        if False:\n"
       "            continue")], False),
    ("hook_health_check", "C5", "a non-string command reaches .strip() again",
     [('                raw_command = h.get("command", "")\n'
       "                if raw_command is not None and not isinstance(raw_command, str):",
       '                raw_command = h.get("command", "")\n'
       "                if False:")], False),
    # [P14 B3] The four axes the guard was blind on, plus the false-alarm axis its fix opened.
    ("duplicate_registration_check", "B3a", "extraction back to the hardcoded '.py' only",
     [("        if t.lower().endswith(SCRIPT_EXTS):", "        if t.lower().endswith('.py'):")],
     False),
    ("duplicate_registration_check", "B3b", "`python -m pkg.mod` yields no script again",
     [('        elif prev == "-m" and t and not t.startswith("-"):', "        elif False:")],
     False),
    ("duplicate_registration_check", "B3c", "dispatcher detection back to a FILENAME substring",
     [('        if not base.lower().endswith(".py"):', '        if "dispatcher" not in base:')],
     False),
    ("duplicate_registration_check", "B3d", "the fan-out list must be literally named HOOKS again",
     [("        if not any(isinstance(t, ast.Name) and t.id.isupper() for t in targets):",
       '        if not any(isinstance(t, ast.Name) and t.id == "HOOKS" for t in targets):')],
     False),
    ("duplicate_registration_check", "B3e",
     "counting back to bare basenames, so distinct events read as duplicates (false alarms)",
     [("        fires, why = _fires(entries)", "        fires, why = True, 'merged'")], False),
    ("duplicate_registration_check", "C6", "a non-string command silences the whole audit again",
     [("                if cmd is not None and not isinstance(cmd, str):",
       "                if False:")], False),
    ("numbers_match_on_write", "C8", "an unparsed `sources` key opts the project out silently",
     [('    if not cfg["sources"]:\n        # [P13 C8]', '    if not cfg["sources"]:\n'
       '        return 0, ""\n    if False:\n        # [P13 C8]')], False),
    ("tools/check_review_freshness", "G2", "a reviewed unit with OPEN findings counts as "
     "fresh again (the gate asks recency, never outcome)",
     [("        elif _open_count(entry) > 0:", "        elif False:")], False),
    ("tools/check_readme_fresh", "G1", "an ABSENT selftest-count claim reads as a pass",
     [("    if not claims:\n        # An ABSENT claim is not a passing one.",
       "    if False:\n        # An ABSENT claim is not a passing one.")], False),
    ("./run_selftests", "A3", "a missing auxiliary-gate file is silently skipped again",
     [("    return [label for label, parts, _extra in gates\n"
       "            if not os.path.exists(os.path.join(root, *parts))]",
       "    return []")], False),
    ("meta_audit_on_stop", "B1", "count_unpushed maps 'no upstream' back to 0 (a never-pushed "
     "branch looks identical to a clean tree)",
     [('    if ahead is None:\n        remotes = _git(cwd, "remote")\n'
       '        if remotes is None or not remotes.strip():\n            return 0\n'
       '        ahead = _git(cwd, "rev-list", "--count", "HEAD", "--not", "--remotes")\n'
       '        if ahead is None:\n            return 0\n',
       "    if ahead is None:\n        return 0\n")], False),
    ("meta_audit_on_stop", "B2", "the marker stem mis-groups its suffix again (PARKED? matches "
     "PARKE, misses PARK)",
     [('_MARKER_STEMS = (("PARK", "ED"),', '_MARKER_STEMS = (("PARKE", "D"),')], False),
    ("meta_audit_on_stop", "B3", "a decision tag is matched anywhere in the line again",
     [("    return bool(_ALLOW_CAPS_RE.search(line) or _ALLOW_BRACKET_RE.search(line))",
       "    return bool(re.search(_TAG_ALT, line, re.IGNORECASE))")], False),
    # [W-MA1 2026-08-06] The bracket branch, which the P13 B3 pass left with no fixture and no
    # mutation at all. TWO entries because the fix has two independent constraints and the
    # SECOND is the one the reviewer's own prescribed fix got wrong.
    ("meta_audit_on_stop", "WMA1a", "the bracket branch goes back to matching an allow-word "
     "ANYWHERE inside any parenthesis, so '(closed-loop)' in a user's own plan reads as a "
     "decision tag and the hiding line is suppressed AND subtracted from the total",
     [('_ALLOW_BRACKET_RE = re.compile(rf"[(\\[]\\s*(?:{_TAG_ALT})(?:[\\s:,;][^)\\]]{{0,40}})?'
       '\\s*[)\\]]",\n                               re.IGNORECASE)',
       '_ALLOW_BRACKET_RE = re.compile(rf"[(\\[][^)\\]]*(?:{_TAG_ALT})[^)\\]]*[)\\]]", '
       're.IGNORECASE)')], False),
    ("meta_audit_on_stop", "WMA1b", "the tag is anchored to the head of the bracket but is no "
     "longer required to END there - the fix the review PRESCRIBED, which still reads "
     "'(closed-loop)' as a tag and scored 7 of 12 on the measured case matrix",
     [('_ALLOW_BRACKET_RE = re.compile(rf"[(\\[]\\s*(?:{_TAG_ALT})(?:[\\s:,;][^)\\]]{{0,40}})?'
       '\\s*[)\\]]",\n                               re.IGNORECASE)',
       '_ALLOW_BRACKET_RE = re.compile(rf"[(\\[]\\s*(?:{_TAG_ALT})[^)\\]]{{0,32}}[)\\]]", '
       're.IGNORECASE)')], False),
    # [SUP-1 2026-08-08] CONFIRMED by the adversarial review of the ship-gate classification:
    # P13 B4 fixed the word appearing MID-line and left it OPENING one. The anchor and its
    # replacement were sliced out of the file and out of git rather than retyped - a heredoc
    # turned this exact string's \b into a BACKSPACE on the first attempt.
    ("meta_audit_on_stop", "SUP1", "the superseded declaration goes back to a `*`-quantified "
     "prefix class, so any of the first five lines merely OPENING with the word freezes the "
     "whole plan file and run() returns (0, '') at every turn end",
     [('_SUPERSEDED_DECL_RE = re.compile(\n    r"^\\s*(?:#+\\s*\\**\\s*|\\*\\*\\s*|(?:status|state)\\s*[:\\-]\\s*\\**\\s*)superseded\\b"\n    r"|(?-i:^\\s*\\**\\s*SUPERSEDED\\b)", re.IGNORECASE)',
       '_SUPERSEDED_DECL_RE = re.compile(\n    r"^\\s*(?:[#>*\\-\\s]*)(?:status\\s*[:\\-]\\s*)?\\**\\s*superseded\\b", re.IGNORECASE)')], False),
    ("meta_audit_on_stop", "B4", "_is_superseded back to a substring match anywhere in the head",
     [("    return any(_SUPERSEDED_DECL_RE.match(line) for line in text.splitlines()[:5])",
       '    return "superseded" in "\\n".join(text.splitlines()[:5]).lower()')], False),
    ("meta_audit_on_stop", "B5", "the unpushed bullet goes back to LAST, where the cap eats it",
     [("    return head + plan_findings, total + len(head)",
       "    return plan_findings + head, total + len(head)")], False),
    # The shared cap helper: three hooks now depend on it, so a mutation here must be caught by
    # the hook whose message would start lying, not only by capped_report's own selftest.
    ("capped_report", "B6", "keep() reports the SURVIVOR count as the total again",
     [("    all_items = list(items)\n    return all_items[:limit], len(all_items)",
       "    all_items = list(items)\n    return all_items[:limit], len(all_items[:limit])")],
     False, "memory_hygiene_guard"),
    ("capped_report", "B7", "render() truncates with no notice again",
     [('    hidden = real_total - len(shown)\n    if hidden > 0:',
       "    hidden = real_total - len(shown)\n    if False:")], False, "plan_defer_guard"),
    # [P14 B1, C1-NEW] The detector moved to cap_shapes/cap_types when it stopped classifying
    # the BOUND and started classifying the OPERATION. #B8 is re-anchored rather than dropped
    # - the capability it pins (the sweep can still SEE a file) is unchanged. B9..B18 pin one
    # rule each: every suppression rule needs its own mutation, or a later edit can delete the
    # rule and the corpus score will not move, because the corpus has no entry for a live
    # false positive that no longer exists.
    ("cap_shapes", "B8", "the twin-guard stops seeing a hook that grew its own cap",
     [("    offenders = []\n    for path in sorted(glob.glob(os.path.join(glob.escape(hooks_dir)"
       ", \"*.py\"))):",
       "    offenders = []\n    for path in []:")], False),
    ("cap_shapes", "B9", "an unparseable file is silently skipped again (fail-open)",
     [('        except SyntaxError as exc:\n            offenders.append("%s: does not parse '
       '(%s) - a file this guard cannot read is "\n                             "REPORTED, '
       'never silently skipped" % (module, exc.msg))\n            continue',
       "        except SyntaxError:\n            continue")], False),
    ("cap_shapes", "B10", "clause 1 stays quiet on anything it cannot classify",
     [('                if kind == "scalar":', '                if kind != "collection":')],
     False),
    ("cap_shapes", "B11", "a dead exemption stops being a finding",
     [("    lines = list(offenders) + list(dead_exemptions)",
       "    lines = list(offenders)")], False),
    ("cap_shapes", "B12", "module-level caps go blind again (the predecessor-derived loss)",
     [('    out = [("<module>", tree)]', "    out = []")], False),
    ("cap_shapes", "B13", "clause 2 swallows every display cap, not just the aggregated ones",
     [('            if (clause2 and site.kind == "display" and site.expr is not None',
       '            if (clause2 and site.kind == "display" and site.expr is None')], False),
    ("cap_shapes", "B14", "clause 3 stops recognising a read window this function performed",
     [("            if clause3 and facts.io_derived(site.target):\n                continue",
       "            if False:\n                continue")], False),
    ("cap_shapes", "B15", "a pad-to-minimum loop reads as a cap again",
     [("return bool(appends) and all(all(isinstance(a, ast.Constant) for a in c.args)\n"
       "                                 for c in appends)",
       "return False")], False),
    # p14_new_code_review.md reserved a mutation for this against the OLD (module, constant)
    # key and it was never built: a two-line widening of the exemption membership test blinded
    # the guard while capped_report --selftest, the whole suite and all three capped_report
    # mutations stayed green, "because nothing anywhere pins the (module, constant) pair".
    # The source names it B9; that id is taken here by an unrelated cap_shapes mutation, so it
    # is B19. The key is now a TRIPLE and this widens it to the module alone.
    ("cap_shapes", "B19", "the exemption key widens to the module, so every cap in an "
     "exempted file inherits the exemption (the reserved-but-never-built B9)",
     [("            if use_roster and key in ALL_EXEMPTIONS:",
       "            if use_roster and any(k[0] == key[0] for k in ALL_EXEMPTIONS):")], False),
    ("cap_shapes", "B16", "an index bounds check inside a loop reads as a cap again",
     [("        if any(_references(o, loop_vars) for o in others):\n            continue",
       "        if False:\n            continue")], False),
    # The piped-gate guard. Each of these reintroduces one half of the design: seeing nothing,
    # or seeing too much. The second is the dangerous one - this hook BLOCKS, and a guard that
    # blocks correct work is disabled within a week (B3-FP).
    ("piped_gate_guard", "PG1", "the gate token is matched as a SUBSTRING again, so a quoted "
     "argument naming a gate blocks a correct grep",
     [('    if tok.endswith(".py"):', "    if True:")], False),
    ("piped_gate_guard", "PG2", "pipefail / PIPESTATUS no longer protect the exit status, so "
     "a command that already captures it is blocked anyway",
     [("    if any(p in command for p in PROTECTED):\n        return []",
       "    if False:\n        return []")], False),
    ("piped_gate_guard", "PG3", "the LAST pipeline segment is examined too, so a gate NAME "
     "appearing as an argument to the final consumer reads as a discarded gate",
     [("    for i, segment in enumerate(segments[:-1]):",
       "    for i, segment in enumerate(segments):")], False),
    ("piped_gate_guard", "PG4", "the guard stops blocking and the discarded exit code ships",
     [("    offenders = piped_gates(command)\n    if not offenders:\n        return 0",
       "    offenders = piped_gates(command)\n    if True:\n        return 0")], False),
    ("piped_gate_guard", "PG5", "the lexer stops treating punctuation as tokens, so a pipe "
     "written without surrounding spaces - the common shape - goes invisible",
     [("        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)",
       "        lexer = shlex.shlex(command, posix=True, punctuation_chars=False)")], False),
    # [MR-c] The timing-claim guard. TC1 is the FALSE-ALARM direction and the one that decides
    # whether this hook survives contact with its owner: the first design fired on ~65 of 82
    # duration mentions and would have been switched off in a week.
    ("timing_claim_guard", "TC1", "the measurement-verb requirement is dropped, so every "
     "declared cap and timeout is reported as an uncontrolled claim",
     [("        if not (MEASUREMENT_VERBS.search(line) or AGAINST_A_BUDGET.search(line)):",
       "        if False:")], False),
    ("timing_claim_guard", "TC2", "a CONTROLLED claim is reported anyway, so writing the "
     "median and the control earns a nag instead of silence",
     [("        if CONTROL_MARKERS.search(line):", "        if False:")], False),
    ("timing_claim_guard", "TC3", "the decision goes permanently silent (MR-a's one-token disarm)",
     [('    if not found:\n        return False, ""', '    if True:\n        return False, ""')],
     False),
    ("timing_claim_guard", "TC4", "the once-per-session marker stops being honoured, so the "
     "hook nags on every doc edit",
     [("    if os.path.exists(marker):\n        return 0", "    if False:\n        return 0")],
     False),
    ("cap_types", "B17", "the positional floor swallows real caps",
     [("POSITIONAL_FLOOR = 5", "POSITIONAL_FLOOR = 50")], False),
    # C1-NEW acceptance criterion 2, which this build REINTRODUCED and the corpus could not
    # see: every existing entry renamed a callee by IMPORT, so the score never moved.
    ("cap_types", "B18", "a callee renamed by ASSIGNMENT stops resolving again "
     "(acceptance criterion 2, a real defect in the reverted detector)",
     [("    for _ in range(3):", "    for _ in range(0):")], False),
    ("./run_selftests", "A3b", "an undeclared tools/ file no longer forces a decision",
     [("    return (sorted(present - gate_basenames - set(not_a_gate)),\n"
       "            sorted(set(not_a_gate) - present))",
       "    return ([], sorted(set(not_a_gate) - present))")], False),
    # [P14 D2] The no-regression gate is itself a gate, and finding M-M4 records that 4 of 6
    # aux gates were re-run by NO mutation - a check nothing mutation-tests is decorative by
    # default. These two pin the halves that carry the whole design.
    ("tools/no_regression", "D2a", "the predecessor stops walking PAST identical blobs, so "
     "a unit whose only commit matches the working tree compares a file to itself and passes",
     [("            if _norm(blob) != current:\n                return blob, sha, None",
       "            return blob, sha, None")], False),
    ("tools/no_regression", "D2b", "a predecessor that detects nothing is treated as a clean "
     "tree instead of an unusable yardstick, so a broken probe reads as no regression",
     [('        if prev_score == 0:\n            raise Broken(',
       '        if False:\n            raise Broken(')], False),
    # [CI-SHALLOW 2026-08-06] Two halves of one fix, pinned separately because either half
    # alone restores the failure. This gate was RED on 11 of 11 CI jobs across two commits
    # while the identical tree was green locally: a --depth 1 checkout cannot reach the
    # differing blob, and "I could not look" was being reported as "there is nothing to look
    # at". Both must turn no_regression's test F red.
    ("tools/no_regression", "CS1", "predecessor() stops naming a truncated checkout, so a "
     "shallow clone's unreachable blob is reported as a definite absence again",
     [("    truncated = history_truncated(repo)\n    if truncated:",
       "    truncated = history_truncated(repo)\n    if False:")], False),
    ("tools/no_regression", "CS2", "classify_waivers stops routing an undeterminable waiver to "
     "the UNKNOWN state, so a shallow checkout BLOCKS on a waiver it never examined",
     [('        if res is not None and unanswerable and res.get("skipped") == unanswerable:',
       "        if False:")], False),
    # [HB-1 2026-08-06] The shell-builtin false positive, both directions. Found by running
    # tests/test_integration.py ON WINDOWS - the integration CI job is ubuntu-only, where
    # /bin/echo is a real file, so this shipped green. P13 F's shape, already fixed for the
    # mutation jobs with a Windows mirror and never applied to the integration job.
    #
    # NOTE on what is NOT pinned here: the A2 twin-roster fix lives in tests/test_integration.py,
    # which has no --selftest, so `verify` cannot reach it - the harness verifies units through
    # their selftest. The whole 30-scenario integration suite is therefore mutation-covered by
    # NOTHING: no mutation anywhere proves any of its scenarios can fail. Rowed for v1.4, not
    # papered over with a mutation that would report CAUGHT without running it.
    # The fixture DERIVES its builtin from the box rather than naming one per platform: the
    # first version said "`echo` on Windows" and came back SURVIVED on windows-latest, whose
    # PATH carries Git for Windows' echo.EXE. Description kept in step with that.
    ("hook_health_check", "HB1a", "a shell builtin invisible to shutil.which() on THIS box is "
     "reported as a missing executable again, so a correct config reads as broken on the one "
     "line the user sees at every SessionStart",
     [("                elif shutil.which(exe) is None and not is_shell_builtin(exe):",
       "                elif shutil.which(exe) is None:")], False),
    ("hook_health_check", "HB1b", "the builtin exemption widens to EVERY name, so a genuinely "
     "missing executable stops being reported - the trade the fix must not make",
     [('    if os.name == "nt":\n        # cmd.exe is case-insensitive',
       "    if True:\n        return True\n    if os.name == \"nt\":\n"
       "        # cmd.exe is case-insensitive")], False),
    # [P14 meta-review] The two defects the 2026-08-06 meta-review PROBED out of this session's
    # own work. Both were invisible to reading and to every existing test.
    ("tools/check_mutation_anchors", "MRa", "the anchor gate's own DECISION is disarmed - a "
     "drifted anchor no longer fails it. Before the verdict() split this was silent: selftest "
     "OK and both M1 mutations still CAUGHT, i.e. finding #16 inside the guard built to stop it",
     [("    if problems:\n        head =", "    if False:\n        head =")], False),
    ("hook_layers", "MRb", "one enabled plugin present in BOTH the cache and marketplace trees "
     "merges every copy again, so the same hook is counted once per copy and a correct config "
     "is reported as a duplicate - the false-alarm mode this module exists to avoid",
     [("        if hits[0] not in layers:\n            layers.append(hits[0])",
       "        for _h in hits:\n            if _h not in layers:\n                "
       "layers.append(_h)")], False),
    ("tools/score_corpus", "B1p", "the corpus scorer goes back to a hardcoded absolute repo "
     "path, which is correct on exactly one machine and red in CI on the other two platforms",
     [("REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))",
       "REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))")],
     False),
    # [P14 B1] The scorer that grades the ship-blocker. It double-counted every negative control
    # and printed a denominator 23% too large; nothing noticed because measurement tools were
    # exempt from the gates. Reintroducing the double-count must go RED.
    ("tools/score_corpus", "B1s", "the corpus scorer counts every negative control twice again, "
     "so it reports 154 entries for a 125-entry corpus and doubles every false-positive count",
     [("        if e[0] in seen:", "        if False:")], False),
    ("tools/score_corpus", "B1c", "the scorer stops noticing that its own corpus asks the same "
     "question twice with opposite answers, so it prints a denominator no guard can reach",
     [("        if len({mf for _n, mf in members}) > 1:", "        if False:")], False),
    # [P14 B3-P] The LAYER roster. Each of these reintroduces one half of the fix: seeing
    # nothing, or seeing too much. The second is the dangerous one - B3-FP proved that a guard
    # which false-alarms on a correct config gets switched off, which is worse than none.
    ("hook_layers", "B3Pa", "every plugin on disk counts as enabled again, so six DISABLED "
     "plugins' hooks are reported as live wirings on a correct config",
     [("        if v is True:", "        if True:")], False),
    ("hook_layers", "B3Pb", "plugin matching goes back to a SUBSTRING, so plugin 'alpha' "
     "claims 'alpha-extras' and merges a layer belonging to another plugin",
     [("    if name.lower() not in parts:", "    if name.lower() not in path.lower():")], False),
    # TWIN: the defect is in hook_layers (where settings_layers moved when the plugin work
    # pushed duplicate_registration_check over the 800-line rule), but the test that catches it
    # is the end-to-end case in duplicate_registration_check's selftest - so the 6th element
    # names the verifying unit. The anchor-drift gate caught this move in 0.087s, one commit
    # after being built, which is the case M1 was written for.
    ("hook_layers", "B3Pc", "settings_layers stops appending plugin layers, so a hook wired by "
     "both a plugin and settings.json reports CLEAN again",
     [("    out.extend(_plugin_layer_files(user))", "    out.extend([])")], False,
     "duplicate_registration_check"),
    # [P14 M1] The anchor-drift sweep. The detector lives HERE, the planted-fixture selftest
    # that pins it lives in the gate, so these are TWIN mutations - hence the 6th element.
    #
    # Both anchors are written SPLIT ("missing_" "anchors"). These are the first mutations whose
    # target file is THIS one, so an anchor written contiguously would occur twice in it - once
    # as the code and once as this very table entry - and `replace(find, replace, 1)` would edit
    # the TABLE rather than the code, mutating nothing and reporting SURVIVED. Splitting keeps
    # the contiguous literal unique to the code. If this is ever got wrong,
    # `check_mutation_anchors` prints a multi-match note for the entry.
    ("tools/mutation_check", "M1a", "anchor_audit stops reporting a drifted anchor, so the cheap "
     "gate goes green while a mutation is silently unrunnable",
     [("        for find in missing_" "anchors(text, edits):", "        for find in []:")],
     False, "tools/check_mutation_anchors"),
    ("tools/mutation_check", "M1b", "an unreadable unit is recorded as empty rather than "
     "unreadable, so a mutation naming a deleted file is reported as a drifted anchor and the "
     "reader is sent to fix an anchor that is fine",
     [('                cache[path] = (None' ', e)', '                cache[path] = ("", e)')],
     False, "tools/check_mutation_anchors"),
]


def anchor_audit(root: str = REPO, mutations=None) -> tuple:
    """(problems, anchors, units, multi) for every mutation anchor against CURRENT sources.

    [P14 M1] `run()` validates one entry's anchors on the way past. This asks the same question
    of the whole table in one cheap sweep, so a disarmed mutation surfaces in under a second
    instead of on the next ~25-minute full run - the gap that let the B3 entry-encoding change
    silently make `#20/23` unrunnable while every FILTERED run reported clean.

    Pure and root-parameterised so the gate's selftest can PLANT a drifted anchor. A selftest
    that could only audit the live repo would pass on a clean tree no matter what this function
    did, which is how every mutation of such a guard survives.

    Fails CLOSED. A unit that cannot be read is a PROBLEM, not a skip, and its anchors stay in
    the denominator - otherwise the total shrinks silently as units go missing and the sweep
    reads healthier the more of it has evaporated.

    `multi` is an OBSERVATION, not a failure: an anchor matching more than once means
    `str.replace(find, replace, 1)` mutates the FIRST site, which may not be the intended one.
    That is finding M-M12 in cluster 2; it is reported here so that row arrives already
    measured, and enforcing it here would be doing M-M12's work under M1's name.
    """
    if mutations is None:
        mutations = MUTATIONS
    problems, anchors, multi = [], 0, []
    units, cache = {}, {}
    for entry in mutations:
        unit, finding, edits = entry[0], entry[1], entry[3]
        path = unit_path(root, unit)
        units[path] = True
        anchors += len(edits)
        if path not in cache:
            try:
                with open(path, encoding="utf-8") as f:
                    cache[path] = (f.read(), None)
            except OSError as e:
                cache[path] = (None, e)
        text, err = cache[path]
        if text is None:
            problems.append("%s #%s: cannot read %s (%s) - a mutation naming a file that is "
                            "not there is as unrunnable as one whose anchor drifted"
                            % (unit, finding, os.path.relpath(path, root), err))
            continue
        for find in missing_anchors(text, edits):
            problems.append("%s #%s: anchor no longer matches %s: %r"
                            % (unit, finding, os.path.relpath(path, root), find[:70]))
        for find, _replace in edits:
            n = text.count(find)
            if n > 1:
                multi.append("%s #%s matches %dx" % (unit, finding, n))
    return problems, anchors, sorted(units), multi


def run(hook: str, finding: str, desc: str, edits, posix_only: bool, verify: str = "") -> str:
    """Mutate `hook`, then run `verify`'s selftest (default: the mutated hook's own).

    They differ when the defect lives in one file and the test that catches it lives in
    another - which is exactly the shape of a TWIN defect, so the harness has to express it.
    """
    # Validate the ANCHOR even when the mutation will be skipped. The early return used to
    # precede this, so a #30 anchor that had drifted was never checked on the authoring
    # machine and the harness still printed "all mutations caught".
    live = unit_path(REPO, hook)
    try:
        with open(live, encoding="utf-8") as f:
            live_text = f.read()
    except OSError as e:
        return "HARNESS ERROR: cannot read %s (%s)" % (hook, e)
    gone = missing_anchors(live_text, edits)
    if gone:
        return "HARNESS ERROR: mutation anchor not found: %r" % (gone[0][:70],)

    # `posix_only` is True for posix-only, or the string "nt" for windows-only. A mutation that
    # can only be MEANINGFUL on one platform must SKIP on the other, never report SURVIVED: a
    # no-op edit staying green says nothing about the test, and reading it as a decorative test
    # sent us hunting a defect that was not there (P13 F). A skip is reported and is not a pass.
    if posix_only is True and os.name == "nt":
        return "SKIPPED (posix only - this machine cannot run it; CI must)"
    if posix_only == "nt" and os.name != "nt":
        return "SKIPPED (windows only - the code it mutates does not exist on this platform)"
    scratch = tempfile.mkdtemp(prefix="unbluff-mut-")
    try:
        _ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for tree in COPY_TREES:
            src = os.path.join(REPO, tree)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(scratch, tree), ignore=_ignore)
        for name in COPY_FILES:
            src = os.path.join(REPO, name)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(scratch, name))
        verify_target = unit_path(scratch, verify or hook)

        # [HIGH-6] BASELINE FIRST, on the UNMUTATED copy. If the verifying selftest is already
        # red in a scratch tree - e.g. meta_audit's asserted something about the REAL
        # environment that a non-git tempdir cannot satisfy - then EVERY mutation "fails" for
        # a reason unrelated to the mutation and the harness certifies them all as CAUGHT.
        # Two mutations (M6, D5-twin) were certified exactly that way.
        try:
            base = subprocess.run([sys.executable, verify_target, "--selftest"],
                                  capture_output=True, text=True, timeout=400,
                                  stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
            if base.returncode not in (0, 77):
                return ("HARNESS ERROR: baseline already RED before mutating (%s --selftest "
                        "rc=%s) - this mutation would prove nothing"
                        % (os.path.basename(verify_target), base.returncode))
        except subprocess.TimeoutExpired:
            return "HARNESS ERROR: baseline selftest timed out before mutating"
        except (OSError, subprocess.SubprocessError) as e:
            return "HARNESS ERROR: baseline selftest could not run (%s)" % e

        target = unit_path(scratch, hook)
        text = open(target, encoding="utf-8").read()
        for find, replace in edits:
            if find not in text:
                return "HARNESS ERROR: mutation anchor not found: %r" % (find[:70],)
            text = text.replace(find, replace, 1)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        target = verify_target
        try:
            p = subprocess.run([sys.executable, target, "--selftest"], capture_output=True,
                               text=True, timeout=400, stdin=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace")
            rc = p.returncode
        except subprocess.TimeoutExpired:
            return "CAUGHT (the mutated hook hung - the bound is real)"
        if rc == 0:
            return "SURVIVED - the test for finding %s is DECORATIVE" % finding
        if rc == 77:
            # SKIP_RC. The verifying selftest could not RUN (no git/sh), so it asserted
            # nothing - counting a non-zero rc as "caught" certified 13 pre_push_gate
            # mutations as pinned on any machine without git.
            return "UNPROVEN (the verifying selftest could not run - rc 77)"
        return "CAUGHT (rc=%s)" % rc
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def duplicate_ids() -> list:
    """(unit, finding) pairs that appear more than once.

    Two entries sharing an id make the report ambiguous and the CLI filter unable to name one
    of them - and it happened by accident the moment a second round of findings reused the
    D-series letters (P13). Cheap to check, impossible to notice by eye in an 80-entry table.
    """
    seen, dupes = set(), []
    for entry in MUTATIONS:
        key = (entry[0], entry[1])
        if key in seen:
            dupes.append(key)
        seen.add(key)
    return dupes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default="", help="only mutations for this hook")
    args = ap.parse_args()
    dupes = duplicate_ids()
    if dupes:
        print("HARNESS ERROR: duplicate mutation ids %r - the report cannot name them apart"
              % (dupes,))
        return 1
    survivors = []
    errors = []
    skipped = []
    other_platform = []
    unproven = []
    filtered = 0
    for entry in MUTATIONS:
        hook, finding, desc, edits, posix_only = entry[:5]
        verify = entry[5] if len(entry) > 5 else ""
        # Match the bare name too: the unit may be written "./run_selftests" or
        # "tools/mutation_check", and a filter that only compared the full string made those
        # entries unreachable from the CLI - i.e. silently unrunnable, which is this file's
        # own failure mode.
        _names = {hook, verify, hook.rsplit("/", 1)[-1], verify.rsplit("/", 1)[-1]}
        if args.only and args.only not in _names:
            # [HIGH-5] COUNT the filtered-out entries. They were recorded in no bucket while
            # the denominator stayed len(MUTATIONS), so `mutation_check.py pre_push_gate`
            # printed "51 of 51 mutations executed, 0 skipped / all mutations caught" after
            # running two. The one line the whole evidence base rests on was arithmetic
            # nonsense under the filter the docstring itself advertises.
            filtered += 1
            continue
        verdict = run(hook, finding, desc, edits, posix_only, verify)
        print("[%-28s #%-8s] %-58s -> %s" % (hook, finding, desc[:58], verdict))
        if verdict.startswith("SURVIVED"):
            survivors.append((hook, finding))
        elif verdict.startswith("HARNESS ERROR"):
            errors.append((hook, finding, verdict))
        elif verdict.startswith("SKIPPED"):
            # A skip is still not a pass, but a mutation marked for the OTHER platform can
            # never run here, so failing CI on it would just make the build permanently red.
            # It has to run on the other platform's job instead - which is why one now exists.
            (other_platform if "only" in verdict else skipped).append((hook, finding))
        elif verdict.startswith("UNPROVEN"):
            unproven.append((hook, finding))
    print()
    # ALWAYS print the denominator. "all mutations caught" was printed unqualified while a
    # posix-only mutation had never executed on this machine - so deleting the os.chmod it
    # guards left the harness certifying every fix as pinned. This file's output is the
    # evidence base for the whole fix round; it must not overstate what it ran.
    considered = len(MUTATIONS) - filtered
    executed = considered - len(skipped) - len(other_platform) - len(unproven)
    scope = " (filter %r: %d of %d entries considered)" % (args.only, considered,
                                                           len(MUTATIONS)) if args.only else ""
    print("%d of %d mutations executed, %d skipped, %d not-runnable-here, %d unproven%s"
          % (executed, considered, len(skipped), len(other_platform), len(unproven), scope))
    if unproven:
        print("UNPROVEN (%d): %s" % (len(unproven), unproven))
        print("  The verifying selftest could not RUN, so it asserted nothing.")
    if errors:
        print("HARNESS ERRORS (%d) - a mutation could not be applied, so nothing was proven:"
              % len(errors))
        for h, f, v in errors:
            print("  %s #%s: %s" % (h, f, v))
    if survivors:
        print("MUTATIONS SURVIVED (%d): %s" % (len(survivors), survivors))
        print("Each one names a fix whose regression test does not actually bite.")
    if other_platform:
        # Named, never silent: the denominator has to show these were not executed here.
        print("NOT RUNNABLE ON THIS PLATFORM (%d): %s" % (len(other_platform), other_platform))
        print("  These are proven by the OTHER platform's job, not by this one. If that job "
              "does not exist, they are proven NOWHERE.")
    if skipped:
        print("SKIPPED (%d): %s" % (len(skipped), skipped))
        print("  A skip is NOT a pass - these fixes are unproven on this machine.")
        if os.environ.get("CI"):
            print("  CI must not skip: failing.")
            return 1
    if unproven and os.environ.get("CI"):
        return 1
    if not survivors and not errors:
        if args.only:
            print("filtered run - this proves nothing about the %d entries not considered"
                  % filtered)
        elif skipped or unproven or other_platform:
            print("every EXECUTED mutation was caught; %d remain unproven here"
                  % (len(skipped) + len(unproven) + len(other_platform)))
        else:
            print("all mutations caught - every fix is pinned by a test that fails without it")
    return 1 if (survivors or errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
