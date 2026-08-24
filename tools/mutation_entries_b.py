#!/usr/bin/env python3
"""Mutation entries, part 2 of 2 - DATA ONLY, imported by tools/mutation_check.py.

Split out of mutation_check.py on 2026-08-16 because that file hit 1415 lines against an
800-line limit, and file_size_baseline.json's own recorded decision was that the next growth
must be PRECEDED by the split rather than absorbed by another re-record. The two halves are an
arbitrary cut at an entry boundary, not a taxonomy: order is preserved exactly so the sweep
iterates an identical list and the diff is a pure move.

The entry shape is (unit, finding_id, description, [(find, replace), ...], posix_only[, verify]).
See mutation_check.py's module docstring for the semantics of each field.
"""

ENTRIES = [
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
     # ANCHOR UPDATED AGAIN 2026-08-12: ROSTER-DERIVE replaced the seed line this pointed at.
     # That is FOUR known anchor drifts on this repo (IT-1 twice, FTB-5, FTB-1), three of them
     # in one session, and every one was caught by the cheap `check_mutation_anchors` gate
     # rather than by a 25-minute sweep or by review. A pin whose anchor has drifted looks
     # exactly like a healthy one; the drift rate is the argument for keeping that gate fast
     # enough to run on every commit.
     [("    seed = tuple(sorted(set(REQUIRED_HOOKS) | dispatcher_subhooks(hooks_dir)))",
       "    import glob as _glob\n"
       "    seed = tuple(sorted(set(REQUIRED_HOOKS) | {os.path.basename(p)\n"
       "                 for p in _glob.glob(os.path.join(_glob.escape(hooks_dir), '*.py'))}))")],
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
    # [ROOT-GLOB 2026-08-24] OPT-1's sibling, and the SECOND instance of that same class. OPT-1
    # pins the try/except idiom; this pins the lazy one. `import fitz` (extract.py:157) and
    # `from pdfminer.high_level import ...` (:163) sit at the top of their own functions with the
    # caller's reader loop handling failure, so they fell through to find_spec - TRUE on the
    # author's box, FALSE on every runner. install.py then demanded scripts/fitz.py and
    # scripts/pdfminer.py, files that exist nowhere, and sys.exit'd: 15 of 17 CI jobs red, and
    # any USER without both libraries unable to install unbluff at all.
    ("install", "OPT-2", "a LAZY import is treated as REQUIRED again - the fitz/pdfminer defect "
     "that made install.py refuse to run for anyone without PyMuPDF",
     [("        if lazy_optional:", "        if False:")],
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
    # [PGG-PS fallout] The FALSE-ALARM direction, and the one that actually broke something:
    # without the behavioural precondition, any ALL-CAPS tuple of strings reads as a fan-out
    # roster, so a hook holding a VOCABULARY (piped_gate_guard's STATUS_EATERS) was reported as
    # double-registering a module that does not exist. It took integration scenario C2 red.
    ("duplicate_registration_check", "DR-VOCAB", "a module-level tuple of ordinary strings is "
     "read as a dispatcher fan-out roster again, so a hook that imports nothing is reported "
     "as double-registering a phantom module",
     [("    if not _imports_a_named_module(tree):", "    if False:")], False),
    # [MEASURED 2026-08-13] The only stateful hook that ignored UNBLUFF_STATE_DIR. Dropping the
    # env lookup means no harness can isolate it and measuring it writes into the user's real
    # ~/.claude/state - which is how its once-per-session marker silenced a control across
    # scorer runs and nearly produced a false 0%.
    ("timing_claim_guard", "TC-ENV", "the marker directory stops honouring UNBLUFF_STATE_DIR, "
     "so the hook cannot be isolated and measuring it pollutes the user's real state dir",
     [('    return os.environ.get("UNBLUFF_STATE_DIR") or MARKER_DIR', "    return MARKER_DIR")],
     False),
    # [criterion 3] The false-alarm scorer. Both mutations attack the thing that makes its
    # numbers mean anything - not its arithmetic, but its refusal to report a rate it has not
    # earned. Both failure modes below actually occurred while it was being written.
    ("tools/score_false_alarms", "FA-1", "a hook whose CONTROL never fired is given a rate "
     "anyway, so silence from an unreachable hook reads as a perfect score",
     [("    if controls_fired <= 0 or exercised <= 0:", "    if False:")], False),
    # [2026-08-14] The budget control goes back to CPU-only. MEASURED: under a tree-copy load
    # a filesystem round-trip slowed 3.00x while the CPU loop measured 0.90x - not slower at
    # all - so the correction under-shoots exactly when a sweep is running, which is how
    # meta_audit's selftest read 64s against a 2.5x normalisation and took two mutations down
    # with it ("baseline already RED").
    ("selftest_budget", "SB-IO", "the load control stops measuring I/O and goes back to a "
     "CPU-only probe, which is blind to the contention that actually causes the overruns",
     [("        return max(1.0, min(_LOAD_FACTOR_CAP, max(cpu, io)))",
       "        return max(1.0, min(_LOAD_FACTOR_CAP, cpu))")], False),
    # [800-LINE RULE] The ratchet. FS-1 is the direction that matters: a file that is ALREADY
    # over the limit must not be allowed to grow, or the debt rises while the gate stays green.
    ("tools/check_file_size", "FS-1", "an already-over-limit file is allowed to GROW, so the "
     "800-line debt rises while the gate reports OK - the exact monotonic decay that let five "
     "files become seven with every individual addition looking justified",
     [("            if n > was:", "            if False:")], False),
    ("tools/check_file_size", "FS-2", "a NEW file over the limit is accepted, which is how "
     "no_regression.py reached 805 lines while appearing in nobody's list",
     [("        if rel not in baseline:", "        if False:")], False),
    # [SHIP-BAR] Criterion 2's stopping rule. SB-1 is the rule itself; SB-2 is the LOOPHOLE -
    # an exclusion must never rescue a CRITICAL/HIGH, or the stopping rule becomes exactly the
    # unfalsifiable promise the 08-12 rework replaced.
    ("tools/ship_bar_gate", "SHIPBAR-1", "an open CRITICAL or HIGH stops blocking the ship bar, so "
     "v1.0 can be tagged with the defect class criterion 2 exists to forbid",
     [("        if r.get(\"severity\") in BLOCKING and r.get(\"state\") != \"BUILT\":",
       "        if False:")], False),
    ("tools/ship_bar_gate", "SHIPBAR-2", "a CRITICAL marked FINALIZED-EXCLUSION is accepted, "
     "reopening the loophole: any blocking finding can be excused in the state column instead "
     "of re-adjudicated in the report where the change would be visible",
     [('        if r.get("severity") in BLOCKING and st == "FINALIZED-EXCLUSION":',
       "        if False:")], False),
    ("tools/ship_bar_gate", "SHIPBAR-4", "the findings ledger stops having to DECLARE its scope, "
     "so the gate can report PASS over an undeclared subset - its own first version covered 24 "
     "findings while 42 more, ten of them HIGH, sat outside an unstated boundary",
     [('        if not scope.get(key):', "        if False:")], False),
    # [2026-08-16] Anchor repointed. This targeted `elif r.get("severity") not in
    # by_where[where]` - the one-directional membership check that the multiset bijection
    # replaced. The DEFECT it pins is unchanged (a severity silently downgraded by retyping);
    # only the code that decides it moved. Left as a stale anchor it would have been a mutation
    # that cannot be PLACED, which proves nothing and must never read as a pass.
    ("tools/ship_bar_gate", "SHIPBAR-3", "the hand-entered ledger stops being reconciled against "
     "the report's canonical severities, so a severity can be silently downgraded by retyping",
     [("        if in_report == in_findings:\n            continue",
       "        if True:\n            continue")], False),
    # [SHIP-BAR enabler] The gate ledger's retention rule. Reverting it to a GLOBAL cap is the
    # exact shape the original had: the cheapest, most frequent gate evicts the record of the
    # 30-minute sweep, so the tier whose last-run date actually matters is the first to vanish.
    ("tools/gate_ledger", "GL-1", "retention goes back to a GLOBAL cap, so a frequent gate "
     "evicts the record of a rare one and the tier you most need is the first lost",
     [('        counts[gate] = counts.get(gate, 0) + 1',
       '        counts["*"] = counts.get("*", 0) + 1\n        gate = "*"')], False),
    ("tools/score_false_alarms", "FA-5", "the verdict goes back to counting every fire, so a "
     "once-per-session NOTICE - an adjudicated FINALIZED-EXCLUSION - fails criterion 3 and a "
     "ship bar built on this row blocks on a condition already decided",
     [("    return bool(nagging_hooks)", "    return True")], False),
    ("tools/score_false_alarms", "FA-4", "the projects root stops being isolated, so "
     "memory_hygiene_guard resolves against the REAL ~/.claude/projects and every rate this "
     "tool prints depends on whose machine ran it",
     [('    return {"UNBLUFF_STATE_DIR": state,\n'
       '            "UNBLUFF_LEDGER_PATH": ledger,\n'
       '            "UNBLUFF_PROJECTS_ROOT": projects}',
       '    return {"UNBLUFF_STATE_DIR": state,\n'
       '            "UNBLUFF_LEDGER_PATH": ledger}')], False),
    ("tools/score_false_alarms", "FA-3", "the NAG check stops re-running, so a guard that "
     "objects once and then goes silent is reported identically to one that repeats every "
     "turn - the distinction that decides whether a guard gets switched off",
     [("    rc2, _out2, err2, _rows2 = run_entry(script, payload, cwd, state, ledger, "
       "extra_env)\n    return fired(rc2, err2)",
       "    return False")], False),
    ("tools/score_false_alarms", "FA-2", "an ADVISORY fire (a message on stderr with rc 0) is "
     "scored as silence, so every advisory guard reports 0% on inputs it objected to",
     [("    return rc not in (0, None) or bool((err or \"\").strip())",
       "    return rc not in (0, None)")], False),
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
     # ANCHOR UPDATED 2026-08-20: the whole-command substring test became _is_protected(), which
     # asks WHERE the word appears and in WHICH dialect. The old line was flagged as this entry's
     # anchor in a comment beside it, and the comment did not stop the drift - check_mutation_
     # anchors did, in under a second, exactly as designed. Prose is advisory; only a gate is a
     # control.
     [("    if _is_protected(command, dialect):\n        return []",
       "    if False:\n        return []")], False),
    # [DISARM 2026-08-20] The other half, and the one PG2 cannot see: PG2 proves the protector is
    # CONSULTED, not that it protects anything real. A protector accepted ANYWHERE in the command
    # - in a comment, or after the pipeline where it does nothing - silenced a blocking guard.
    ("piped_gate_guard", "PG-DISARM", "a protector counts wherever it appears, so `pipefail` in "
     "a comment or written AFTER the pipeline disarms the guard",
     [('    for word, where in _PROTECTORS.get(dialect, _PROTECTORS["bash"]):\n'
       '        if word in (head if where == "before" else command):',
       '    for word, where in _PROTECTORS.get(dialect, _PROTECTORS["bash"]):\n'
       '        if word in command:')], False),
    ("piped_gate_guard", "PG3", "the LAST pipeline segment is examined too, so a gate NAME "
     "appearing as an argument to the final consumer reads as a discarded gate",
     [("    for i, segment in enumerate(segments[:-1]):",
       "    for i, segment in enumerate(segments):")], False),
    # PG4 REPOINTED 2026-08-13: the PGG-PS fix threads the dialect through this call, which
    # deleted the line the old anchor quoted. Repointed rather than supplemented - a mutation
    # whose anchor has drifted is a pin that has silently stopped pinning, and it is
    # indistinguishable from a healthy one until a full sweep runs. Sixth drift; caught by
    # check_mutation_anchors in seconds, as all six were.
    ("piped_gate_guard", "PG4", "the guard stops blocking and the discarded exit code ships",
     [("    offenders = piped_gates(command, dialect(payload.get(\"tool_name\")))\n"
       "    if not offenders:\n        return 0",
       "    offenders = piped_gates(command, dialect(payload.get(\"tool_name\")))\n"
       "    if True:\n        return 0")], False),
    # [PGG-PS] Both halves of the fix, pinned separately, because they fail independently:
    # the VOCABULARY can be right while the hook is wired to no shell that uses it, and the
    # WIRING can be right while the guard has nothing to say about that shell.
    ("piped_gate_guard", "PG6", "the PowerShell truncators are forgotten, so "
     "`gate | Select-Object -First 1` - the shape that returns -1 with the gate never having "
     "finished - goes invisible again",
     [('PS_TRUNCATING = ("-first", "-index")', "PS_TRUNCATING = ()")], False),
    ("piped_gate_guard", "PG7", "dialect() stops recognising PowerShell, so a PowerShell "
     "command is scored with sh vocabulary and the guard is blind on the platform where "
     "PowerShell is the PRIMARY shell",
     [('    if isinstance(tool_name, str) and tool_name.strip().lower() == "powershell":',
       "    if False:")], False),
    # The FALSE-ALARM direction, which is the one that decides whether the widening survives
    # contact with a user: `sort` and `tee` are status-eaters in sh and status-PRESERVING
    # cmdlet aliases in PowerShell. Dropping the exemption fires on correct PowerShell.
    ("piped_gate_guard", "PG8", "the PowerShell-safe aliases lose their exemption, so "
     "`gate | sort` and `gate | tee` are blocked in a shell where both PRESERVE the exit code",
     [('PS_SAFE_ALIASES = ("sort", "tee")', 'PS_SAFE_ALIASES = ()')], False),
    ("install", "PGG-PS-1", "the PreToolUse matcher goes back to the bare literal 'Bash', so "
     "the piped-gate guard never runs for a PowerShell user at all",
     [('    return "|".join(_load_guard_shell_tools())', '    return "Bash"')], False),
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
    # [MODE-CONTROL 2026-08-16] The defect these two pin is the one this repo committed TWICE
    # and did not pin either time: a gate registered in a mode that cannot catch anything. An
    # independent review reproduced it on a clean clone in ONE TOKEN with the suite still
    # reporting green, because the sweep verifies every mutation via `<unit> --selftest`, which
    # is identical whichever mode the row is registered in. MODE-1 is that exact one-token edit.
    ("./run_selftests", "MODE-1", "an ENFORCING gate is re-registered ('--selftest',), so it "
     "checks its own logic and applies to nothing - the 2026-08-14 defect, one token",
     [('    ("file-size", ("tools", "check_file_size.py"), ()),',
       '    ("file-size", ("tools", "check_file_size.py"), ("--selftest",)),')], False),
    # ...and the detector itself. MODE-1 dies against the LIVE table; MODE-2 dies against the
    # synthetic tree, so deleting either assertion leaves the other exposed. Without this, the
    # control could be disarmed by making its can-fail test answer "no" for everything - which
    # is the shape that made the ORIGINAL probes agree with the original code.
    ("./run_selftests", "MODE-2", "the mode detector's can-fail test always says no, so every "
     "--selftest registration reads as adjudicated and no flip is ever reported",
     [("def _can_fail(fn) -> bool:", "def _can_fail(fn) -> bool:\n    return False")], False),
    # [MODE-3 2026-08-19] The THIRD spelling of the same disarm, and the one MODE-1 and MODE-2
    # could not see. Both of those fixtures use exactly ("--selftest",), so a detector written
    # with `!= ("--selftest",)` and one written with `"--selftest" in extra` agree on every case
    # they exercise. Every gate here dispatches on MEMBERSHIP, so ("--selftest", "") runs the
    # SELFTEST while an equality-based detector reads the row as enforcing and reports no gap -
    # one token, suite green, the gate's real measurement invoked by nothing. Found by an
    # independent review of the enforcing-verify commit, which had reproduced the equality
    # spelling in mutation_check.enforcing_argv - the twin, written while fixing the original.
    ("tools/gate_modes", "MODE-3", "the selftest/measurement predicate goes back to exact tuple "
     "equality, so a ('--selftest', '') registration reads as ENFORCING in both readers while "
     "the target still runs its selftest",
     [("    return SELFTEST_FLAG in tuple(extra or ())",
       "    return tuple(extra or ()) == (SELFTEST_FLAG,)")], False, "./run_selftests"),
    # [ROSTER-GLOB 2026-08-19] The guard that ties the mutation harness's copy roster to the unit
    # roster the freshness gate globs. Without it, widening COPY_TREES armed an assertion whose
    # inputs came from a tree that could never satisfy it, and the failure would have surfaced
    # 25 minutes into a sweep as five unrelated HARNESS ERRORs.
    # [SELF-COMPARE / STALE-TAUTOLOGY 2026-08-20] The two HIGHs task #17 found in the
    # no-regression gate. Both were CHECKS THAT COULD NOT FAIL, and neither was reachable by any
    # existing assertion: the live gate reports the same "1 settled" whether the staleness rule
    # is right or wrong, and the same "predecessor saw N, working tree sees N" whether the A/B is
    # genuine or a self-comparison. MEASURED before the fix: crippling the real detector moved
    # BOTH sides 102 -> 64 and the gate still exited 0. After: the predecessor holds at 102, the
    # working tree drops to 64, and the gate FAILS - which is the whole point of the gate.
    ("tools/no_regression", "NOREG-SELF", "the self-comparison guard reports nothing, so a "
     "predecessor that executes the working tree's own delegate passes as a yardstick",
     [("    shared = set(repo_sibling_modules(prev, repo)) & set(repo_sibling_modules(cur, repo))",
       "    shared = set()")], False),
    ("tools/no_regression", "NOREG-STALE", "waiver staleness goes back to `gained` alone, so a "
     "capability BOTH versions detect is filed SETTLED and can never be pruned",
     [('    if "cur_hits" in res:\n        return set(res["cur_hits"])',
       '    if False:\n        return set(res["cur_hits"])')], False),
    # [SET-AGG 2026-08-20] The task #17 HIGH in cap_types' vocabulary. Restoring the two names to
    # _AGGREGATORS is the exact shipped state, and before this session NOTHING went red on it:
    # no corpus entry and no selftest case exercised a slice wrapped in set()/frozenset(), so a
    # guard built to catch truncation-handed-to-the-caller was silent on one spelling of it.
    ("cap_types", "SET-AGG", "set/frozenset go back to being clause-2 aggregators, so "
     "`return set(rows[:MAX])` is CLEAN to the guard whose whole job is catching that",
     [('_AGGREGATORS = {"any", "all", "sum", "min", "max", "len", "bool",\n'
       '                "next", "int", "float"}',
       '_AGGREGATORS = {"any", "all", "sum", "min", "max", "len", "bool", "set", "frozenset",\n'
       '                "next", "int", "float"}')], False),
    # [NO-NETWORK 2026-08-22] The gate that finally mechanises the README's strongest claim. Two
    # pins because the guard has two ways to become useless: stop DETECTING, or start flagging
    # everything (a guard that fires on correct code is one its owner deletes).
    ("tools/check_no_network", "NONET-BLIND", "the network-module roster empties, so an `import "
     "socket` in a shipped hook passes the gate that exists to forbid it",
     [("        elif isinstance(node, ast.ImportFrom):",
       "        elif False:")], False),
    ("tools/check_no_network", "NONET-FLOOR", "the population floor is dropped, so a scan that "
     "collapsed to nothing reports OK over an empty tree",
     [("    if examined < 20:", "    if False:")], False),
    ("tools/check_mutation_anchors", "ROSTER-1", "the roster-coverage check stops comparing, so "
     "a unit glob no scratch tree can supply is never reported",
     [('        if not any(pattern.startswith(tree.rstrip("/") + "/") for tree in trees):',
       "        if False:")], False),
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
    # [LEDGER 2026-08-16] Review wf_f63b9ccf-816 confirmed four ways gate_ledger could lose the
    # record it exists to keep, and one reason none were caught: the selftest asserted
    # prune/last_run/tiers and never once executed record(), the ONE function every caller uses.
    ("tools/gate_ledger", "GL-REC", "record() hardcodes the gate name again, so every tier "
     "writes under one label and the ledger reports 1 of 6 tiers - the original defect",
     [('        row = {"gate": gate, "utc": _utc(), "result": result}',
       '        row = {"gate": "run_selftests", "utc": _utc(), "result": result}')], False),
    ("tools/gate_ledger", "GL-CORRUPT", "an unparseable ledger reads back as OK, so 'the file "
     "is corrupt' and 'nothing ever ran' become the same answer again",
     [('    except ValueError:\n        return [], "corrupt"',
       '    except ValueError:\n        return [], "ok"')], False),
    ("tools/gate_ledger", "GL-LOCK", "the lock is taken even while another writer holds it, so "
     "two concurrent tiers clobber each other's rows and both report success",
     [("            if age <= stale_s:\n                return None",
       "            if False:\n                return None")], False),
    # [2026-08-17] This pin was DRAFTED with GL-REC/GL-CORRUPT/GL-LOCK and did not survive into
    # the commit - the session's own meta-review caught that the atomic write, the most
    # load-bearing change in the file, had no pin at all. It is the hardest of the four to
    # detect, because truncate-then-write produces a correct file on the happy path; only an
    # INTERRUPTED write tells the two apart, which is why the selftest now fails mid-write.
    ("tools/gate_ledger", "GL-ATOMIC", "the ledger is truncated before the payload is built, "
     "restoring the window where an interrupted write destroys all history unrecoverably",
     [('        payload = json.dumps(prune(history), indent=2)      '
       '# serialise BEFORE touching target\n        tmp = LEDGER + ".tmp"\n'
       '        with open(tmp, "w", encoding="utf-8") as f:\n            f.write(payload)\n'
       '        os.replace(tmp, LEDGER)',
       '        with open(LEDGER, "w", encoding="utf-8") as f:\n'
       '            json.dump(prune(history), f, indent=2)')], False),
    # [RECORD-SITES] finding #40: deleting a tier's recording left every gate, selftest and
    # anchor check green, so the ship bar would read a STALE row rather than no row.
    ("tools/check_file_size", "SITES-1", "the file-size tier records under another gate's name, "
     "so its own last_run() serves the previous PASS forever",
     [('gate_ledger.record("file_size", result, **fields)',
       'gate_ledger.record("not_file_size", "FAIL" if failing else "PASS"')],
     False, "./run_selftests"),
    # [BIJECTION 2026-08-16] reconcile() was one-directional and keyed on a non-unique field, so
    # a confirmed HIGH could be absent from the ledger, a duplicate could stand in for a missing
    # row, and a HIGH could be laundered into a shippable MEDIUM - all with the count matching.
    ("tools/ship_bar_gate", "SHIPBAR-BIJ", "reconcile goes back to walking ledger -> report "
     "only, so a confirmed finding missing from findings.json is never noticed",
     [("        in_report, in_findings = report_ms.get(key, 0), findings_ms.get(key, 0)\n"
       "        if in_report == in_findings:\n            continue",
       "        in_report, in_findings = report_ms.get(key, 0), findings_ms.get(key, 0)\n"
       "        if in_report >= in_findings:\n            continue")], False),
    ("tools/ship_bar_gate", "SHIPBAR-DECL", "the report's own '## Confirmed (N)' heading stops "
     "being enforced, so a silently dropped table row reads as a smaller population",
     [("    if declared is not None and declared != len(report_rows):",
       "    if False and declared != len(report_rows):")], False),
    # [FILE-SIZE 2026-08-16] The three defects review wf_f63b9ccf-816 confirmed in the ratchet's
    # inputs rather than in its rule - which is why the rule's five existing pins were all green.
    ("tools/check_file_size", "FS-TRISTATE", "an unreadable baseline collapses back to an empty "
     "one, so 'I could not look' is reported as seven substantive NEW-offender failures",
     [('    except ValueError:\n        return {}, "unreadable"',
       '    except ValueError:\n        return {}, "absent"')], False),
    ("tools/check_file_size", "FS-REVERSE", "the reverse walk stops naming baseline entries "
     "that no longer qualify, so the recorded count silently overstates the debt",
     [("    out = []\n    for rel in sorted(baseline):", "    out = []\n    for rel in []:")],
     False),
    ("tools/check_file_size", "FS-COUNT", "line_count returns 0 for every file, leaving the "
     "gate green with a healthy-looking denominator and no file ever over the limit",
     [("    with io.open(path, encoding=\"utf-8\", errors=\"replace\") as f:\n"
       "        return sum(1 for _ in f)",
       "    return 0")], False),
    # [BUDGET 2026-08-16] The control had normalised the check out of existence: with the factor
    # capped at 6.0, `normalised > b` needs up to 6x the budget, but the subprocess is KILLED at
    # SELFTEST_TIMEOUT_S. On any box above ~1.43x the budget check could not fire at all.
    ("selftest_budget", "SB-KILL", "the raw ceiling is dropped, so a selftest that runs past "
     "the unconditional kill is normalised under budget and reported as fine",
     [("    over = normalised > b or elapsed > SELFTEST_TIMEOUT_S", "    over = normalised > b")],
     False),
    ("selftest_budget", "SB-IOREF", "the I/O calibration reference is shrunk, which saturates "
     "the load factor at its cap and silently disables the budget check - SB-2's defect reached "
     "from the constant instead of from the cap",
     [("_CALIB_IO_REF_S = 0.0148", "_CALIB_IO_REF_S = 0.0037")], False),

    # ---------------------------------------------------------------------------------------
    # [ENFORCING 2026-08-18] The first entries verified through a gate's REGISTERED invocation
    # rather than its --selftest. Everything above this line reaches only code the selftest
    # calls, which is why the 2026-08-16 meta-review could list six behaviours as fixed-but-
    # UNPINNED for one shared reason: nothing in any `main()` was reachable. Two of the six are
    # FLOORS whose entire purpose is to stop a gate that read NOTHING from printing OK, so they
    # were the exact shape this repo exists to catch, sitting unpinned inside the pinning tool.
    #
    # Read `{"mode": "enforcing"}` as "run it the way it is REGISTERED" - the argv is derived
    # from AUX_GATES, never written here, so an entry cannot assert a mode the repo does not
    # actually wire. See verify_spec() and enforcing_argv() in mutation_check.py.
    ("tools/ship_bar_gate", "SHIPBAR-FLOOR", "the stopping rule passes over an EMPTY population "
     "- both readers return nothing and the gate reports PASS, which is a gate that read "
     "nothing, not a repo with nothing blocking it",
     # THREE edits, and the third is the one that makes this pin mean anything. With only the
     # two readers silenced the mutation is still CAUGHT - but by SHIPBAR-DECL's guard ("the
     # heading declares 24 and 0 rows parsed"), not by the floor. MEASURED 2026-08-19: delete
     # the floor and the gate STILL exits 1, so the entry could not fail and was certifying a
     # guard it never reached. Silencing declared_count removes the absorbing guard, and only
     # then does the floor decide the verdict: rc 1 with it, "ship-bar: PASS" over a ZERO-row
     # population without it. A pin absorbed by a neighbour is decoration wearing a pin's name.
     [("    return rows", "    return []"),
      ("    return scope, rows", "    return scope, []"),
      ("    return int(m.group(1)) if m else None", "    return None")], False,
     {"mode": "enforcing"}),
    ("tools/check_file_size", "FS-FLOOR", "the population collapses to zero and the ratchet "
     "still reports OK - the 'examined almost nothing' floor is what stops it",
     [('            return [r for r in rels if os.path.isfile(os.path.join(root, r))], "git"',
       '            return [], "git"')], False, {"mode": "enforcing"}),
    # The two below are pinned by a MARKER, not by an exit code, and neither could be pinned
    # any other way. FS-GIT-DERIVE changes WHICH derivation ran and nothing else - same files,
    # same verdict, rc 0 either way. FS-CANNOTRUN exits 1 with the guard present AND with it
    # deleted, so an rc-only pin would report CAUGHT for both and prove nothing.
    ("tools/check_file_size", "FS-GIT-DERIVE", "the population stops asking version control and "
     "silently falls back to the walk - the fallback that put thousands of vendored files in "
     "the population whenever a virtualenv was not spelled .venv",
     [("        if out.returncode == 0 and out.stdout.strip():", "        if False:")], False,
     {"mode": "enforcing", "marker": "(source: git)"}),
    ("tools/check_file_size", "FS-CANNOTRUN", "an unreadable baseline stops halting the gate, so "
     "'I could not look' is reported as a per-file verdict over every recorded offender",
     [('BASELINE = os.path.join(REPO, "docs", "audits", "file_size_baseline.json")',
       'BASELINE = os.path.join(REPO, "README.md")')], False,
     {"mode": "enforcing", "marker": ".py file(s) in population"}),
]
