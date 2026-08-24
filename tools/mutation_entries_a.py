#!/usr/bin/env python3
"""Mutation entries, part 1 of 2 - DATA ONLY, imported by tools/mutation_check.py.

Split out of mutation_check.py on 2026-08-16 because that file hit 1415 lines against an
800-line limit, and file_size_baseline.json's own recorded decision was that the next growth
must be PRECEDED by the split rather than absorbed by another re-record. The two halves are an
arbitrary cut at an entry boundary, not a taxonomy: order is preserved exactly so the sweep
iterates an identical list and the diff is a pure move.

The entry shape is (unit, finding_id, description, [(find, replace), ...], posix_only[, verify]).
See mutation_check.py's module docstring for the semantics of each field.
"""

ENTRIES = [
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
     [("    return _has_collectible_tests(cwd) is not False",
       '    return os.path.isdir(os.path.join(cwd, "tests"))')], False),
    ("fast_test_on_stop", "FTB-1b", "pytest CONFIG files stop counting, so a real pytest "
     "project whose tests live outside tests/ loses its gate entirely",
     [("    for name, marker in _PYTEST_CONFIG_MARKERS:", "    for name, marker in ():")], False),
    ("fast_test_on_stop", "FTB-10", "the config roster loses pytest 9.0's pytest.toml family "
     "and .pytest.ini, so 3 of pytest's 7 canonical config files leave a real project UNGATED",
     [('    ("pytest.ini", None),\n    (".pytest.ini", None),\n    ("pytest.toml", None),\n'
       '    (".pytest.toml", None),', '    ("pytest.ini", None),')], False),
    ("fast_test_on_stop", "FTB-11", "detection needs a `tests/` directory again, so a root-level "
     "test_*.py, `test/` singular, colocated tests and a monorepo package are all UNGATED",
     [("    return _has_collectible_tests(cwd) is not False",
       '    return _has_collectible_tests(os.path.join(cwd, "tests")) is not False')], False),
    ("fast_test_on_stop", "FTB-13", "the config marker goes back to a raw SUBSTRING match, so a "
     "pyproject that merely mentions it in a comment or a string is read as declaring pytest",
     [("                    if line.startswith(marker):", "                    if marker in line:")],
     False),
    ("fast_test_on_stop", "FTB-14", "the file cap counts EVERY file again, so a large tree of "
     "non-Python fixtures hits it and is ACCEPTED as a pytest project on no Python evidence",
     [("                if not fn.endswith(\".py\"):\n                    continue\n",
       "")], False),
    ("fast_test_on_stop", "FTB-15", "the three-state cap collapses to False, so a repo too big "
     "to finish scanning is reported as NOT a pytest project and silently loses its gate",
     [("                    return None\n                if fn.startswith(\"test_\")",
       "                    return False\n                if fn.startswith(\"test_\")")], False),
    ("fast_test_on_stop", "FTB-12", "a root conftest.py stops counting as a pytest test root",
     [('    if os.path.isfile(os.path.join(cwd, "conftest.py")):', "    if False:")], False),
    ("pre_push_gate_selftest", "WT-1", "a broken FIXTURE collapses back into 'the box cannot "
     "make a worktree', so two scenarios go unrun, the reason printed is false, and the suite "
     "still exits 0",
     # The 6th element is the VERIFY TARGET and it is load-bearing: this unit is a selftest
     # MODULE with no --selftest entry point of its own (it is in KNOWN_NO_SELFTEST), so
     # without it the harness ran `pre_push_gate_selftest.py --selftest`, which verifies
     # nothing, and WT-1 came back SURVIVED while the probe was demonstrably working - the
     # mutation was applied and checked against the wrong thing. Every sibling SH-* entry
     # carries it; omitting it is a FIFTH way to make a pin hollow.
     [("    if fixture_err:\n        return False,", "    if False:\n        return False,")],
     False, "pre_push_gate"),
    ("install", "RD-1", "the partial-checkout seed goes back to the hand-typed REQUIRED_HOOKS "
     "alone, so a sub-hook added to a dispatcher roster and never typed into the tuple is "
     "invisible - install prints Done., the selftest prints OK, the hook never runs",
     [("    seed = tuple(sorted(set(REQUIRED_HOOKS) | dispatcher_subhooks(hooks_dir)))",
       "    seed = tuple(sorted(set(REQUIRED_HOOKS)))")], False),
    ("install", "RD-2", "dispatcher_subhooks stops reading the HOOKS rosters, so the derivation "
     "silently becomes a declaration again",
     [('            if not any(isinstance(t, ast.Name) and t.id == "HOOKS" for t in node.targets):',
       '            if True:')], False),
    ("tools/check_readme_fresh", "CI-JOBS-1", "a job-count gate that could not PARSE the "
     "workflow reports the same green as one that looked and found nothing wrong",
     [('    if want <= 0:\n        return 1, ("readme-jobs: FAIL - could not derive',
       '    if False:\n        return 1, ("readme-jobs: FAIL - could not derive')], False),
    ("tools/check_readme_fresh", "CI-JOBS-2", "main() stops consulting the job-count gate, so "
     "the number is hand-maintained again (it said 14 once)",
     [("    rc_jobs, msg_jobs = verdict_jobs(text, expected_jobs())",
       "    rc_jobs, msg_jobs = 0, ''")], False),
    ("selftest_budget", "SB-1", "the budget assertion loses its CONTROL and goes back to raw "
     "wall clock, so a slow or loaded machine false-fails a selftest that is not slow",
     [("    over = normalised > b", "    over = elapsed > b")], False),
    # SB-2 REPOINTED 2026-08-14: adding the I/O half of the control deleted the line this
    # anchored to. Repointed rather than supplemented - a drifted anchor is a pin that has
    # silently stopped pinning, and is indistinguishable from a healthy one until a sweep runs.
    # SEVENTH drift, and the seconds-long anchors gate caught this one too.
    ("selftest_budget", "SB-2", "the load factor loses its cap, so a pathologically slow box "
     "scales the budget without bound and the check silently stops being able to fail",
     [("        return max(1.0, min(_LOAD_FACTOR_CAP, max(cpu, io)))",
       "        return max(1.0, max(cpu, io) * 1e6)")], False),
    ("pre_push_gate", "FTB-GATES", "the push gate stops naming WHY there is no command, so a "
     "pytest project whose pytest is unimportable is told it 'has no test command'",
     [("        _, why_no_gate = fast_test._nogate_reason(root)",
       '        why_no_gate = ""')], False),
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
     [('        if base in ("pytest", "py.test") or _PYTEST_VERSIONED.match(base):',
       "        if True:")], False),
    ("fast_test_on_stop", "FTB-9", "the pytest-command test goes back to a raw substring search, "
     "which MISSES py.test and pytest-3 (FASTTEST-BLOCK survives verbatim) and MATCHES a "
     "directory named pytest (a genuine rc-5 failure is waived)",
     [('        base = tok.replace("\\\\", "/").rsplit("/", 1)[-1].lower()',
       "        base = tok.lower()")], False),
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
     # Anchor re-cut 2026-08-24 [ROOT-GLOB]: the enumerated root entries became `*.py`, so the
     # old anchor stopped matching. The mutation's MEANING is unchanged - narrow the roster back
     # to hooks plus the repo root, leaving tools/, tests/, scripts/ and the shipped skill
     # scripts unwatched. Caught by check_mutation_anchors, not by the 25-minute sweep.
     [('UNIT_GLOBS = ("hooks/*.py", "tools/*.py", "tests/*.py", "scripts/*.py",\n'
       '              "skills/*/scripts/*.py", "*.py")',
       'UNIT_GLOBS = ("hooks/*.py", "*.py")')], False),
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
     # ANCHOR UPDATED 2026-08-12: WT-CAUSE rewrote the asserted "no POSIX shell was found"
     # message this quoted, because it contradicted the shell line printed above it. Fifth
     # anchor drift on this repo; caught by check_mutation_anchors, as all five were.
     # Anchored on the CONDITION alone (verified unique), not on the message beneath it: the
     # previous anchor spanned both and broke the moment a comment was inserted between them.
     # An anchor that quotes prose is an anchor that drifts when the prose is corrected.
     [("\n    if skipped:\n", "\n    if False:\n")],
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
]
