"""False-alarm corpus: ordinary CORRECT work, plus the controls that prove the harness looked.

CRITERION 3. "Each hook's FALSE-ALARM rate on ordinary correct code is MEASURED and recorded."
A guard that fires on correct work gets switched off, which is strictly worse than no guard.

WHY A SECOND CORPUS. tests/cap_spelling_corpus.py grades ONE detector by calling
`slicing_offenders(hooks_dir)`. Every guard criterion 3 actually cares about instead reads a
Claude Code EVENT PAYLOAD on stdin - a prompt, a Bash command, an edited file, a transcript -
and none of them exposes that function. "The corpus machinery already exists" was FALSE.

CONTRACT
  ENTRY = (name, event, must_fire, exercises, rationale, build)
    name       short id, unique
    event      "PreToolUse" | "PostToolUse" | "Stop" - decides which entry point runs
    must_fire  False -> ORDINARY CORRECT WORK. A hook that fires here has false-alarmed.
               True  -> a CONTROL. It MUST fire, or the harness is not reaching the hook and
                        every quiet result in the same event class is meaningless.
    exercises  the sub-hooks this entry actually puts in a position to object. Declared so the
               scorer can refuse to report 0% for a hook that was merely INERT.
    rationale  why this is ordinary/correct, in one line - a corpus entry nobody can adjudicate
               is a number nobody can trust
    build      build(td) -> payload dict. Plants whatever files it needs under `td`.

THE TRAP THIS CORPUS IS BUILT AROUND. Several hooks are OPT-IN: numbers_match_on_write exits 0
immediately unless the project has a `.claude/number-sources.txt`. A "correct" entry with no
such config makes the hook exit 0 without looking at anything, and a scorer that counted that
would report a beautiful 0% false-alarm rate for a hook that never ran. So the negatives here
are planted in projects where the hook IS active, and `exercises` records that claim so the
scorer can hold it to account against the controls.

APPEND-ONLY. Removing an entry, or flipping a must_fire, silently narrows every guard graded
against it. Add; do not edit or delete.
"""

import json
import os

# --------------------------------------------------------------------------------------
# helpers - plant a realistic little project, so "ordinary" means ordinary
# --------------------------------------------------------------------------------------


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _numbers_project(td, report_body):
    """A project where numbers_match_on_write is ACTIVE (it is opt-in via this config).

    Same shape as integration scenario H2, deliberately: reusing a probe the repo already
    trusts beats inventing a second one that has never been adjudicated.
    """
    _write(os.path.join(td, "results", "sweep.csv"),
           "metric,value\novershoot,94.7651\nsettle,8.6542\n")
    _write(os.path.join(td, ".claude", "number-sources.txt"),
           "sources = results\nreports = *REPORT*.md\n")
    return _write(os.path.join(td, "REPORT.md"), report_body)


def _edit(path, td, session):
    return {"session_id": session, "cwd": td, "tool_name": "Write",
            "tool_input": {"file_path": path}}


# --------------------------------------------------------------------------------------
# ORDINARY CORRECT WORK - a hook that fires on any of these has FALSE-ALARMED
# --------------------------------------------------------------------------------------

ENTRIES = (
    # ---- PostToolUse: an edited file. defer / numbers / timing all see this event. ----
    ("plain_python_module", "PostToolUse", False,
     ("plan_defer_guard", "numbers_match_on_write", "timing_claim_guard"),
     "an ordinary module: no plan language, no cited numbers, no duration claims",
     lambda td: _edit(_write(os.path.join(td, "app.py"),
                             "def add(a, b):\n    return a + b\n"), td, "fa-1")),

    ("readme_prose", "PostToolUse", False,
     ("plan_defer_guard", "numbers_match_on_write", "timing_claim_guard"),
     "ordinary documentation prose with a heading and a list",
     lambda td: _edit(_write(os.path.join(td, "README.md"),
                             "# Widget\n\nA small tool.\n\n- fast\n- tested\n"), td, "fa-2")),

    ("plan_without_defer_language", "PostToolUse", False,
     ("plan_defer_guard",),
     "a real plan file with scheduled work and NO optional-forever language - the shape "
     "plan_defer_guard must stay quiet on, or every plan edit is blocked",
     lambda td: _edit(_write(os.path.join(td, "MASTER_PLAN.md"),
                             "# Plan\n\n| 1 | build the parser | SCHEDULED |\n"
                             "| 2 | wire the CLI | SCHEDULED |\n"), td, "fa-3")),

    ("report_numbers_that_MATCH_their_source", "PostToolUse", False,
     ("numbers_match_on_write",),
     "numbers_match is ACTIVE here (the project has number-sources.txt) and every cited "
     "figure is present in results/sweep.csv - quiet because CORRECT, not because inert",
     lambda td: _edit(_numbers_project(
         td, "# Report\n\novershoot 94.7651 and settle 8.6542\n"), td, "fa-4")),

    ("duration_with_a_control", "PostToolUse", False,
     ("timing_claim_guard",),
     "a timing claim that DOES carry a control marker - timing_claim_guard's own rule is "
     "that a controlled claim is fine",
     lambda td: _edit(_write(os.path.join(td, "NOTES.md"),
                             "# Notes\n\nThe sweep took 30 minutes, measured against an idle "
                             "control run of the same suite.\n"), td, "fa-5")),

    ("config_json", "PostToolUse", False,
     ("plan_defer_guard", "numbers_match_on_write", "timing_claim_guard"),
     "an ordinary JSON config full of numbers that are settings, not cited evidence",
     lambda td: _edit(_write(os.path.join(td, "config.json"),
                             json.dumps({"port": 8080, "retries": 3, "timeout": 30},
                                        indent=2)), td, "fa-6")),

    ("changelog_entry", "PostToolUse", False,
     ("plan_defer_guard", "numbers_match_on_write", "timing_claim_guard"),
     "a CHANGELOG entry with a version number and a date",
     lambda td: _edit(_write(os.path.join(td, "CHANGELOG.md"),
                             "# Changelog\n\n## [1.2.0] - 2026-01-05\n\n- added the parser\n"),
                      td, "fa-7")),

    ("test_file", "PostToolUse", False,
     ("plan_defer_guard", "numbers_match_on_write", "timing_claim_guard"),
     "an ordinary test module",
     lambda td: _edit(_write(os.path.join(td, "test_app.py"),
                             "from app import add\n\n\ndef test_add():\n"
                             "    assert add(1, 2) == 3\n"), td, "fa-8")),

    # ---- PreToolUse: a shell command. piped_gate_guard sees this event. ----
    ("ordinary_pipe_no_gate", "PreToolUse", False, ("piped_gate_guard",),
     "the single most common shell shape there is; blocking it would end the guard",
     lambda td: {"tool_name": "Bash", "tool_input": {"command": "ls -la | head -20"}}),

    ("gate_not_piped", "PreToolUse", False, ("piped_gate_guard",),
     "a gate run correctly - its status is the command's status",
     lambda td: {"tool_name": "Bash",
                 "tool_input": {"command": "python run_selftests.py"}}),

    ("gate_status_captured", "PreToolUse", False, ("piped_gate_guard",),
     "a gate whose status is explicitly captured, which is the fix the guard asks for",
     lambda td: {"tool_name": "Bash",
                 "tool_input": {"command": 'python run_selftests.py; echo "EXIT=$?"'}}),

    ("powershell_safe_consumer", "PreToolUse", False, ("piped_gate_guard",),
     "MEASURED 2026-08-13: Select-Object -Last PRESERVES $LASTEXITCODE, so blocking it is a "
     "false alarm - this is the entry that would have caught the prescribed PGG-PS fix",
     lambda td: {"tool_name": "PowerShell",
                 "tool_input": {"command":
                                "python run_selftests.py | Select-Object -Last 5"}}),

    ("powershell_select_string", "PreToolUse", False, ("piped_gate_guard",),
     "MEASURED: Select-String is a cmdlet, not grep, and preserves the gate's exit code",
     lambda td: {"tool_name": "PowerShell",
                 "tool_input": {"command": "python run_selftests.py | Select-String OK"}}),

    ("git_status", "PreToolUse", False, ("piped_gate_guard",),
     "an everyday command with no gate and no pipe at all",
     lambda td: {"tool_name": "Bash", "tool_input": {"command": "git status --porcelain"}}),

    # ---- Stop: end of a turn in a clean project. ----
    ("stop_in_a_clean_project", "Stop", False, ("show_your_proof", "meta_audit_on_stop", "memory_hygiene_guard", "fast_test_on_stop"),
     "a turn ending in a project with nothing wrong - the dispatcher must be silent",
     lambda td: {"session_id": "fa-stop-1", "cwd": td, "transcript_path": ""}),

    # ==================================================================================
    # CONTROLS. Each MUST fire. A quiet control means the harness never reached the hook,
    # and every 0% in the same event class is then an artefact, not a measurement.
    # ==================================================================================

    ("CONTROL_plan_with_park_language", "PostToolUse", True, ("plan_defer_guard",),
     "optional-forever language in a plan - plan_defer_guard's whole purpose",
     lambda td: _edit(_write(os.path.join(td, "MASTER_PLAN.md"),
                             "| 1 | low-pri refactor -> park.\n"), td, "fa-c1")),

    ("CONTROL_report_number_with_no_source", "PostToolUse", True, ("numbers_match_on_write",),
     "a cited figure that appears in no source file - numbers_match's whole purpose",
     lambda td: _edit(_numbers_project(
         td, "# Report\n\novershoot 12.3456 and settle 99.9999\n"), td, "fa-c2")),

    ("CONTROL_uncontrolled_duration", "PostToolUse", True, ("timing_claim_guard",),
     "a duration stated with a measurement verb and NO control - timing_claim_guard's whole "
     "purpose, and the pair to duration_with_a_control above",
     lambda td: _edit(_write(os.path.join(td, "NOTES.md"),
                             "# Notes\n\nThe run took 47 seconds.\n"), td, "fa-c3")),

    ("CONTROL_piped_gate_posix", "PreToolUse", True, ("piped_gate_guard",),
     "the exact shape the guard was built for: a gate piped into tail",
     lambda td: {"tool_name": "Bash",
                 "tool_input": {"command": "python run_selftests.py 2>&1 | tail -2"}}),

    ("CONTROL_piped_gate_powershell", "PreToolUse", True, ("piped_gate_guard",),
     "MEASURED: Select-Object -First truncates the pipeline and tears the gate down",
     lambda td: {"tool_name": "PowerShell",
                 "tool_input": {"command":
                                "python run_selftests.py | Select-Object -First 1"}}),
)
