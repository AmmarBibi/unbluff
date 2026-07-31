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

Mutations marked posix_only are skipped on Windows (os.chmod exec bits are a no-op there), so
they are the ones only CI can prove.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (hook, finding, description, [(find, replace), ...], posix_only)
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
     [("    if isinstance(content, list):\n        for block in content:",
       "    if isinstance(content, list):\n        for block in content[:1]:")], False,
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
    ("fast_test_on_stop", "D10", "kill_tree loses the saved pgid / job (grandchild survives)",
     [("        _kill_tree(proc, pgid, job)  # release the pipe; never leave what we spawned "
       "running",
       "        _kill_tree(proc)")], False),
    ("fast_test_on_stop", "D10b", "the Windows job object is never created",
     [("    job = _win_job_kill_on_close()", "    job = None")], False),
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
]


def run(hook: str, finding: str, desc: str, edits, posix_only: bool, verify: str = "") -> str:
    """Mutate `hook`, then run `verify`'s selftest (default: the mutated hook's own).

    They differ when the defect lives in one file and the test that catches it lives in
    another - which is exactly the shape of a TWIN defect, so the harness has to express it.
    """
    # Validate the ANCHOR even when the mutation will be skipped. The early return used to
    # precede this, so a #30 anchor that had drifted was never checked on the authoring
    # machine and the harness still printed "all mutations caught".
    live = os.path.join(REPO, "hooks", hook + ".py")
    try:
        with open(live, encoding="utf-8") as f:
            live_text = f.read()
    except OSError as e:
        return "HARNESS ERROR: cannot read %s (%s)" % (hook, e)
    for find, _replace in edits:
        if find not in live_text:
            return "HARNESS ERROR: mutation anchor not found: %r" % (find[:70],)

    if posix_only and os.name == "nt":
        return "SKIPPED (posix only - this machine cannot run it; CI must)"
    scratch = tempfile.mkdtemp(prefix="unbluff-mut-")
    try:
        shutil.copytree(os.path.join(REPO, "hooks"), os.path.join(scratch, "hooks"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        target = os.path.join(scratch, "hooks", hook + ".py")
        text = open(target, encoding="utf-8").read()
        for find, replace in edits:
            if find not in text:
                return "HARNESS ERROR: mutation anchor not found: %r" % (find[:70],)
            text = text.replace(find, replace, 1)
        with open(target, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        if verify:
            target = os.path.join(scratch, "hooks", verify + ".py")
        try:
            p = subprocess.run([sys.executable, target, "--selftest"], capture_output=True,
                               text=True, timeout=400, stdin=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace")
            rc = p.returncode
        except subprocess.TimeoutExpired:
            return "CAUGHT (the mutated hook hung - the bound is real)"
        if rc == 0:
            return "SURVIVED - the test for finding %s is DECORATIVE" % finding
        return "CAUGHT (rc=%s)" % rc
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default="", help="only mutations for this hook")
    args = ap.parse_args()
    survivors = []
    errors = []
    skipped = []
    for entry in MUTATIONS:
        hook, finding, desc, edits, posix_only = entry[:5]
        verify = entry[5] if len(entry) > 5 else ""
        if args.only and args.only not in (hook, verify):
            continue
        verdict = run(hook, finding, desc, edits, posix_only, verify)
        print("[%-28s #%-8s] %-58s -> %s" % (hook, finding, desc[:58], verdict))
        if verdict.startswith("SURVIVED"):
            survivors.append((hook, finding))
        elif verdict.startswith("HARNESS ERROR"):
            errors.append((hook, finding, verdict))
        elif verdict.startswith("SKIPPED"):
            skipped.append((hook, finding))
    print()
    # ALWAYS print the denominator. "all mutations caught" was printed unqualified while a
    # posix-only mutation had never executed on this machine - so deleting the os.chmod it
    # guards left the harness certifying every fix as pinned. This file's output is the
    # evidence base for the whole fix round; it must not overstate what it ran.
    executed = len(MUTATIONS) - len(skipped)
    print("%d of %d mutations executed, %d skipped" % (executed, len(MUTATIONS), len(skipped)))
    if errors:
        print("HARNESS ERRORS (%d) - a mutation could not be applied, so nothing was proven:"
              % len(errors))
        for h, f, v in errors:
            print("  %s #%s: %s" % (h, f, v))
    if survivors:
        print("MUTATIONS SURVIVED (%d): %s" % (len(survivors), survivors))
        print("Each one names a fix whose regression test does not actually bite.")
    if skipped:
        print("SKIPPED (%d): %s" % (len(skipped), skipped))
        print("  A skip is NOT a pass - these fixes are unproven on this machine.")
        if os.environ.get("CI"):
            print("  CI must not skip: failing.")
            return 1
    if not survivors and not errors:
        if skipped:
            print("every EXECUTED mutation was caught; %d remain unproven here" % len(skipped))
        else:
            print("all mutations caught - every fix is pinned by a test that fails without it")
    return 1 if (survivors or errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
