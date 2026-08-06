#!/usr/bin/env python3
"""End-to-end integration test for unbluff: install -> fire each hook as Claude Code would -> uninstall.

Uses a throwaway HOME and temp projects. Fires the EXACT command strings install.py writes into
settings.json, piping realistic Claude Code hook JSON on stdin, and checks behaviour + exit codes.
Stdlib-only; needs `git` on PATH. Runs in CI.
"""
import json, os, subprocess, sys, tempfile, shutil

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tests/ -> repo root
PYEXE = sys.executable
results = []


def _install_skill_names():
    """The skills install.py actually ships - read from install.py, never re-listed here.

    A second copy of this list is a twin waiting to drift: the point of asserting it is that
    the installer and the test cannot disagree.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ub_install",
                                                  os.path.join(REPO, "install.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.SKILL_NAMES)


def _install_group_ids():
    """The hook-group ids install.py actually wires - read from install.py, never re-listed.

    A2 asserted a hardcoded `== 4` while `_install_skill_names` above already documented why
    that is wrong ("a second copy of this list is a twin waiting to drift"). It drifted the day
    `piped_gate_guard` made it five, and main went red. A COUNT is also weaker than it looks:
    it cannot tell a missing group from an unexpected extra one, so this returns the ids and
    A2 compares sets.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ub_install_groups",
                                                  os.path.join(REPO, "install.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {g["id"] for g in mod.desired_groups().values()}


def _close_guard_required_skills():
    """The skills close_skills_guard demands, read from the hook itself."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_ub_guard", os.path.join(REPO, "hooks", "close_skills_guard.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.REQUIRED_SKILLS)


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail and not ok else ""))


def child_env(home):
    e = dict(os.environ)
    e["USERPROFILE"] = home
    e["HOME"] = home
    e["HOMEDRIVE"], e["HOMEPATH"] = os.path.splitdrive(home)
    return e


def run(cmd, env, stdin="", cwd=None):
    """Run a hook command. `cwd` matters: duplicate_registration_check merges the PROJECT
    layer (<cwd>/.claude/settings*.json), so a scenario launched from the repo root silently
    audits unbluff's own config alongside the fixture - C2 could fail, or pass, for reasons
    unrelated to the code under test (D9)."""
    p = subprocess.run(cmd, shell=True, input=stdin, capture_output=True, text=True, env=env,
                       cwd=cwd)
    return p.returncode, p.stdout or "", p.stderr or ""


def git(cwd, *args):
    subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def main():
    home = tempfile.mkdtemp(prefix="unbluff-home-")
    env = child_env(home)
    os.makedirs(os.path.join(home, ".claude"))
    # seed a pre-existing unrelated hook + env to prove we preserve them
    seed = {"hooks": {"Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo other"}],
                                "id": "someone-else:keep"}]}, "env": {"FOO": "bar"}}
    settings_path = os.path.join(home, ".claude", "settings.json")
    json.dump(seed, open(settings_path, "w"))

    try:
        # --- A. INSTALL ---
        rc, out, err = run(f'"{PYEXE}" "{os.path.join(REPO, "install.py")}"', env)
        s = json.load(open(settings_path))
        ids = [g.get("id") for gs in s["hooks"].values() for g in gs]
        record("A1 install exit 0", rc == 0, f"rc={rc} err={err[:200]}")
        want = _install_group_ids()
        got = {i for i in ids if str(i).startswith("unbluff:")}
        record(f"A2 every unbluff group install.py declares is wired ({len(want)}, derived)",
               got == want,
               f"missing={sorted(want - got)} unexpected={sorted(got - want)} all={sorted(ids)}")
        record("A3 preexisting hook preserved", "someone-else:keep" in ids)
        record("A4 env preserved", s.get("env", {}).get("FOO") == "bar")
        # [finding 31] DERIVED from install.SKILL_NAMES, never a hand-written list. Three of
        # the four were asserted by name, so completeness-audit - the skill added in v1.3.0
        # precisely because close_skills_guard REQUIRES all four - was the one whose install
        # nothing checked. A hook demanding a skill the installer silently failed to ship
        # would have blocked every close with an unsatisfiable message, all gates green.
        skill_names = _install_skill_names()
        record("A5 installer ships >= 4 skills (derived, not listed)",
               len(skill_names) >= 4, str(skill_names))
        for _i, _name in enumerate(skill_names):
            record(f"A5.{_i + 1} skill installed: {_name}",
                   os.path.isfile(os.path.join(home, ".claude", "skills", _name, "SKILL.md")))
        record("A7 consistency-audit skill installed with bundled scripts",
               os.path.isfile(os.path.join(home, ".claude", "skills", "consistency-audit",
                                           "scripts", "audit.py")))
        # every skill close_skills_guard names must actually be among them
        _required = _close_guard_required_skills()
        record("A8 every skill close_skills_guard requires is installed",
               all(os.path.isfile(os.path.join(home, ".claude", "skills", r, "SKILL.md"))
                   for r in _required), f"requires={_required} ships={skill_names}")

        ups = s["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
        ss = s["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        stop = next(g["hooks"][0]["command"] for g in s["hooks"]["Stop"]
                    if str(g.get("id", "")).startswith("unbluff:"))
        ptu = next(g["hooks"][0]["command"] for g in s["hooks"]["PostToolUse"]
                   if str(g.get("id", "")).startswith("unbluff:"))

        # --- B. rate_prompt (UserPromptSubmit) ---
        rc, out, err = run(ups, env, json.dumps({"prompt": "fix the login bug and confirm"}))
        record("B1 rate_prompt fires on substantive prompt",
               rc == 0 and "one-line rating (X/10)" in out, f"rc={rc} out={out[:80]!r}")
        rc, out, err = run(ups, env, json.dumps({"prompt": "ok"}))
        record("B2 rate_prompt silent on trivial reply", rc == 0 and out.strip() == "", f"out={out!r}")

        # --- C. hook_health_check (SessionStart) ---
        rc, out, err = run(ss, env, "{}")
        record("C1 hook_health reports OK", rc == 0 and "[hook-health] OK" in out,
               f"rc={rc} out={out[:120]!r}")

        # --- C2/C3. duplicate_registration_check (SessionStart, 2nd command in the group) ---
        # A clean install must be silent. A hook wired from a SECOND directory must be reported on
        # STDOUT (stderr is not reliably surfaced at SessionStart) with exit 0 - advisory, never blocks.
        dup = s["hooks"]["SessionStart"][0]["hooks"][1]["command"]
        # Launch from a directory with NO .claude, so the project layer contributes nothing
        # and the assertion is about the fixture alone (D9).
        nocfg = tempfile.mkdtemp(prefix="unbluff-nocfg-")
        rc, out, err = run(dup, env, "{}", cwd=nocfg)
        record("C2 duplicate-check silent on a clean install",
               rc == 0 and out.strip() == "", f"rc={rc} out={out[:150]!r}")

        second_root = tempfile.mkdtemp(prefix="unbluff-dup-")
        spath = os.path.join(home, ".claude", "settings.json")
        try:
            shutil.copy2(os.path.join(REPO, "hooks", "rate_prompt.py"),
                         os.path.join(second_root, "rate_prompt.py"))
            with open(spath, encoding="utf-8") as f:
                s2 = json.load(f)
            s2["hooks"]["UserPromptSubmit"].append({"hooks": [
                {"type": "command",
                 "command": f'"{PYEXE}" "{os.path.join(second_root, "rate_prompt.py")}"'}]})
            with open(spath, "w", encoding="utf-8") as f:
                json.dump(s2, f, indent=2)
            rc, out, err = run(dup, env, "{}", cwd=nocfg)
            record("C3 duplicate-check reports a second registration on stdout",
                   rc == 0 and "rate_prompt.py" in out and "registered 2 times" in out,
                   f"rc={rc} out={out[:200]!r}")
        finally:
            with open(spath, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2)  # restore before the uninstall scenarios
            shutil.rmtree(second_root, ignore_errors=True)

        # --- D. show-your-proof via the Stop dispatcher (end to end) ---
        proj = tempfile.mkdtemp(prefix="unbluff-proj-")  # plain dir: only show_your_proof should fire
        tpath = os.path.join(proj, "transcript.jsonl")
        with open(tpath, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "user", "message": {"role": "user", "content": "fix the bug"}}) + "\n")
            f.write(json.dumps({"type": "assistant", "message": {"role": "assistant",
                    "content": [{"type": "text", "text": "Done - it works now."}]}}) + "\n")
        payload = json.dumps({"session_id": "itest-proof", "cwd": proj,
                              "transcript_path": tpath, "stop_hook_active": False})
        rc, out, err = run(stop, env, payload)
        record("D1 show-your-proof fires (rc 2 + nudge)",
               rc == 2 and "[show-your-proof]" in err, f"rc={rc} err={err[:120]!r}")
        ledger = os.path.join(home, ".claude", "hooks", "state", "fire_ledger.jsonl")
        fired = json.loads(open(ledger).readlines()[-1]).get("fired") if os.path.exists(ledger) else None
        record("D2 fire-ledger records 'proof'", fired == ["proof"], f"fired={fired}")
        rc2, _, _ = run(stop, env, payload)  # same session -> once-per-session guard
        record("D3 once-per-session (second fire quiet)", rc2 == 0, f"rc={rc2}")

        # --- E. fast-test-on-stop via the dispatcher (end to end) ---
        repo2 = tempfile.mkdtemp(prefix="unbluff-git-")
        git(repo2, "init")
        os.makedirs(os.path.join(repo2, ".claude"))
        with open(os.path.join(repo2, ".claude", "fast-test.cmd"), "w") as f:
            f.write(f'"{PYEXE}" -c "raise SystemExit(1)"\n')  # deterministic failing test, no pytest needed
        with open(os.path.join(repo2, "app.py"), "w") as f:
            f.write("x = 1\n")
        git(repo2, "add", "-A"); git(repo2, "commit", "-m", "init")
        with open(os.path.join(repo2, "app.py"), "a") as f:
            f.write("y = 2  # changed source\n")  # porcelain now shows a changed .py
        rc, out, err = run(stop, env, json.dumps({"session_id": "itest-test", "cwd": repo2,
                                                  "stop_hook_active": False}))
        record("E1 fast-test fires on failing tests (rc 2)",
               rc == 2 and "[fast-test] FAILING" in err, f"rc={rc} err={err[:120]!r}")
        rc2, _, _ = run(stop, env, json.dumps({"session_id": "itest-test2", "cwd": repo2,
                                               "stop_hook_active": False}))
        record("E2 fast-test debounced on immediate re-run", rc2 == 0, f"rc={rc2}")

        # --- F. quiet path: nothing wrong -> dispatcher exits 0 ---
        clean = tempfile.mkdtemp(prefix="unbluff-clean-")
        rc, out, err = run(stop, env, json.dumps({"session_id": "itest-clean", "cwd": clean,
                                                  "stop_hook_active": False}))
        record("F1 dispatcher quiet when nothing is wrong", rc == 0, f"rc={rc} err={err[:120]!r}")

        # --- H. plan_defer_guard (PostToolUse) fires on optional-forever plan language ---
        planf = os.path.join(tempfile.mkdtemp(prefix="unbluff-plan-"), "MASTER_PLAN.md")
        with open(planf, "w", encoding="utf-8") as f:
            f.write("| 1 | low-pri refactor -> park.\n")
        rc, out, err = run(ptu, env, json.dumps({"session_id": "itest-defer",
                           "tool_input": {"file_path": planf}}))
        record("H1 plan-defer-guard fires on '-> park' plan edit (rc 2 + nudge)",
               rc == 2 and "[plan-defer-guard]" in err, f"rc={rc} err={err[:120]!r}")

        # --- H2. numbers-match (PostToolUse) fires on a report number with no source ---
        nmproj = tempfile.mkdtemp(prefix="unbluff-nm-")
        os.makedirs(os.path.join(nmproj, ".claude"))
        os.makedirs(os.path.join(nmproj, "results"))
        with open(os.path.join(nmproj, "results", "sweep.csv"), "w", encoding="utf-8") as f:
            f.write("metric,value\novershoot,94.7651\nsettle,8.6542\n")
        with open(os.path.join(nmproj, ".claude", "number-sources.txt"), "w", encoding="utf-8") as f:
            f.write("sources = results\nreports = *REPORT*.md\n")
        nmreport = os.path.join(nmproj, "REPORT.md")
        with open(nmreport, "w", encoding="utf-8") as f:
            f.write("Overshoot was 94.8% (matches) but peak stress 512.4 MPa is the worst case.\n")
        rc, out, err = run(ptu, env, json.dumps({"session_id": "itest-numbers", "cwd": nmproj,
                           "tool_input": {"file_path": nmreport}}))
        record("H2 numbers-match fires on unmatched number (rc 2 + nudge)",
               rc == 2 and "[numbers-match]" in err and "512.4" in err, f"rc={rc} err={err[:160]!r}")

        # --- H3. hook/skill SOURCE_EXTS parity (guard the intentional duplication) ---
        import importlib.util as _ilu
        def _load(mod_path, mod_name):
            spec = _ilu.spec_from_file_location(mod_name, mod_path)
            mod = _ilu.module_from_spec(spec)
            sys.modules[mod_name] = mod  # so @dataclass in the module can resolve its module
            spec.loader.exec_module(mod)
            return mod
        hook_exts = skill_exts = None
        try:
            _hm = _load(os.path.join(REPO, "hooks", "numbers_match_on_write.py"), "nm_hook_parity")
            _sm = _load(os.path.join(REPO, "skills", "consistency-audit", "scripts", "sources.py"), "ca_sources_parity")
            hook_exts, skill_exts = set(_hm.SOURCE_EXTS), set(_sm.SOURCE_EXTS)
        except Exception as e:
            record("H3 hook/skill SOURCE_EXTS parity", False, f"load error: {e}")
        else:
            record("H3 hook/skill SOURCE_EXTS parity", hook_exts == skill_exts,
                   f"hook-only={sorted(hook_exts - skill_exts)} skill-only={sorted(skill_exts - hook_exts)}")

        # --- G. UNINSTALL ---
        rc, out, err = run(f'"{PYEXE}" "{os.path.join(REPO, "install.py")}" --uninstall', env)
        s2 = json.load(open(settings_path))
        ids2 = [g.get("id") for gs in s2.get("hooks", {}).values() for g in gs]
        record("G1 uninstall exit 0", rc == 0, f"rc={rc}")
        record("G2 all unbluff entries removed",
               not any(str(i).startswith("unbluff:") for i in ids2), str(ids2))
        record("G3 preexisting hook still there", "someone-else:keep" in ids2)
        record("G4 env still there", s2.get("env", {}).get("FOO") == "bar")
        # [finding 31] every installed skill must come back OUT, not just the first one.
        _left = [n for n in _install_skill_names()
                 if os.path.exists(os.path.join(home, ".claude", "skills", n))]
        record("G5 every installed skill removed", not _left, f"left behind: {_left}")

        for d in (proj, repo2, clean, nmproj):
            shutil.rmtree(d, ignore_errors=True)
    finally:
        shutil.rmtree(home, ignore_errors=True)

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n==== {passed}/{len(results)} scenarios passed ====")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
