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
    """
    if "/" in name:
        return os.path.normpath(os.path.join(root, *(name + ".py").split("/")))
    return os.path.join(root, "hooks", name + ".py")


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
     [('            registered[tail].append("%s|%s|" % (head, scope))',
       '            entry_ = "%s|%s|" % (head, scope)\n'
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
    ("hook_health_check", "18", "the weekly sweep goes back to a hardcoded roster",
     [('    d = hooks_dir or _HOOKS_DIR\n    return [p for p in sorted(glob.glob(os.path.join('
       'd, "*.py"))) if has_selftest(p)]',
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
    ("capped_report", "B8", "the twin-guard stops seeing a hook that grew its own cap",
     [("    offenders = []\n    for path in sorted(glob.glob(os.path.join(hooks_dir, \"*.py\"))):",
       "    offenders = []\n    for path in []:")], False),
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
]


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
    for find, _replace in edits:
        if find not in live_text:
            return "HARNESS ERROR: mutation anchor not found: %r" % (find[:70],)

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
