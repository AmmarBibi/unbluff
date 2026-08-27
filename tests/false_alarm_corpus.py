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
import subprocess
import sys

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


def _stop(td, session, transcript=""):
    return {"session_id": session, "cwd": td, "transcript_path": transcript,
            "stop_hook_active": False}


def _transcript(td, assistant_content):
    """A minimal but REAL transcript - the shape integration scenario D1 already trusts."""
    p = os.path.join(td, "transcript.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user",
                            "message": {"role": "user", "content": "fix the bug"}}) + "\n")
        f.write(json.dumps({"type": "assistant",
                            "message": {"role": "assistant",
                                        "content": assistant_content}}) + "\n")
    return p


def _git_repo_with_failing_gate(td):
    """A repo whose test gate FAILS, with a changed .py so the gate is asked to run.

    Reuses integration scenario E1's trick: the gate is a `.claude/fast-test.cmd` that exits 1
    deterministically, so this control needs NO pytest and cannot go flaky on a machine where
    pytest is absent - which is every CI runner.
    """
    def git(*args):
        subprocess.run(["git", "-C", td, *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
    git("init")
    _write(os.path.join(td, ".claude", "fast-test.cmd"),
           '"%s" -c "raise SystemExit(1)"\n' % sys.executable)
    _write(os.path.join(td, "app.py"), "x = 1\n")
    git("add", "-A")
    git("commit", "-m", "init")
    with open(os.path.join(td, "app.py"), "a", encoding="utf-8") as f:
        f.write("y = 2  # changed source\n")
    return td


def _projects_root(td, memory_index):
    """A projects root holding THIS cwd's memory dir, so memory_hygiene_guard has something
    to read. Pointed at a fixture via UNBLUFF_PROJECTS_ROOT - never the user's real
    ~/.claude/projects, which is the pollution class fixed in timing_claim_guard today."""
    root = os.path.join(td, "_fixture_projects")
    # DERIVED from the hook's own sanitize_cwd, never re-implemented here. A hand-rolled
    # version of this exact rule is what the guard's own docstring records as a live defect:
    # it replaced only ':' '\' and '/', so any path with an underscore or a dot resolved to a
    # directory that does not exist and the hook returned 0 forever, indistinguishable from
    # "this project's memory is clean". A fixture that guesses it would fail the same way -
    # and it DID, on the first run: the control stayed silent and the scorer said so.
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "hooks"))
    from memory_hygiene_guard import sanitize_cwd
    _write(os.path.join(root, sanitize_cwd(td), "memory", "MEMORY.md"), memory_index)
    return root


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

    # [item 22] CONFIRMED false alarms, fixed 2026-08-27. Not hypotheticals: the first fired on
    # this guard's own author twice in one session, and the message MIS-NAMED the gate - it
    # reported `hook_divergence_report`, which appears only in the `for` loop on the line ABOVE
    # the pipe. Two separate defects: a READER on the producer side (the gate's file is an
    # operand, not a command), and a pipeline attributed ACROSS a statement boundary.
    ("gate_file_grepped_not_run", "PreToolUse", False, ("piped_gate_guard",),
     "grep READS a gate's source file; grep's status is the only one in the pipeline, so there "
     "is no gate status to lose. The control that makes this a finding rather than a guess: "
     "swapping the gate filename for a non-gate file was ALREADY quiet, so the NAME was what "
     "triggered it",
     lambda td: {"tool_name": "Bash",
                 "tool_input": {"command": 'grep -n "800" tools/check_file_size.py | head -20'}}),

    ("gate_file_read_by_wc", "PreToolUse", False, ("piped_gate_guard",),
     "same class via wc - the READER SET is what decides, not the operand",
     lambda td: {"tool_name": "Bash",
                 "tool_input": {"command": "wc -l tools/check_file_size.py | head -1"}}),

    ("gate_named_on_a_previous_line", "PreToolUse", False, ("piped_gate_guard",),
     "a pipeline does not cross a statement boundary: the gate name is in a `for` loop on the "
     "LINE ABOVE, and the pipe below it runs grep. Verbatim, this is the command that produced "
     "the mis-attributed message",
     lambda td: {"tool_name": "Bash",
                 "tool_input": {"command":
                                "for f in tools/hook_divergence_report.py; do wc -l < $f; done\n"
                                'grep -n "800" tools/check_file_size.py | head -20'}}),

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

    # ---- the Stop class. Ordinary correct work first. ----
    ("stop_with_a_transcript_that_HAS_proof", "Stop", False, ("show_your_proof",),
     "the assistant cites a tool result, which is what show_your_proof asks for - firing "
     "here would nag on exactly the behaviour it is trying to produce",
     lambda td: _stop(td, "fa-9", _transcript(td, [
         {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest -q"}},
         {"type": "text", "text": "The suite passes - 12 passed, shown above."}]))),

    ("stop_with_a_plan_carrying_DECISION_TAGS", "Stop", False, ("meta_audit_on_stop",),
     "a plan whose items are TAGGED (SCHEDULED/DECIDED) - meta_audit's own rule is that a "
     "tagged line is a record, not hidden work; firing would block every plan-bearing repo",
     lambda td: _stop(td, "fa-10", "") if _write(
         os.path.join(td, "PLAN.md"),
         "# Plan\n\n- SCHEDULED: build the parser\n- DECIDED: use the AST walk\n") else None),

    ("stop_in_a_repo_whose_gate_PASSES", "Stop", False, ("fast_test_on_stop",),
     "a repo with a changed .py and a test gate that SUCCEEDS - the ordinary green turn, and "
     "the shape FASTTEST-BLOCK used to hard-block",
     lambda td: _stop(td, "fa-11", "") if _write(
         os.path.join(_git_repo_with_failing_gate(td), ".claude", "fast-test.cmd"),
         '"%s" -c "raise SystemExit(0)"\n' % sys.executable) else None),

    # ---- the three DISPATCHERS, so the roster has no NO-CORPUS-ENTRY rows ----
    ("dispatcher_stop_on_a_clean_project", "Stop", False, ("stop_dispatcher",),
     "the Stop dispatcher's aggregate verdict on a project with nothing wrong",
     lambda td: _stop(td, "fa-12", "")),

    ("dispatcher_posttooluse_on_an_ordinary_edit", "PostToolUse", False,
     ("post_tooluse_dispatcher",),
     "the PostToolUse dispatcher's aggregate verdict on an ordinary module edit",
     lambda td: _edit(_write(os.path.join(td, "util.py"),
                             "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n"),
                      td, "fa-13")),

    ("close_skills_on_a_file_that_is_NOT_the_close_signal", "PostToolUse", False,
     ("close_skills_guard",),
     "close_skills_guard keys on NEXT_SESSION_PROMPT.md; every other edit must pass, or it "
     "would demand the four close skills on every write in the repo",
     lambda td: _edit(_write(os.path.join(td, "notes.md"), "# Notes\n\nnothing to see\n"),
                      td, "fa-14")),

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

    # ---- Stop-class controls. Without these, the four Stop hooks were UNMEASURED: their
    # silence could not be told apart from never having run. ----
    ("CONTROL_claim_with_no_proof", "Stop", True, ("show_your_proof",),
     "an assistant claiming success with NO tool call behind it - the exact shape the hook "
     "exists for, and integration D1's fixture",
     lambda td: _stop(td, "fa-c4", _transcript(td, [
         {"type": "text", "text": "Done - it works now."}]))),

    ("CONTROL_parked_marker_in_a_plan", "Stop", True, ("meta_audit_on_stop",),
     "a root plan file with a parked marker carrying NO decision tag - work hidden rather "
     "than scheduled",
     lambda td: _stop(td, "fa-c5", "") if _write(
         os.path.join(td, "PLAN.md"),
         "# Plan\n\n- PARKED: investigate cache misses\n- TODO: close the socket\n") else None),

    ("CONTROL_failing_test_gate", "Stop", True, ("fast_test_on_stop",),
     "a repo with a changed .py whose test gate FAILS - deterministic, and needs no pytest, "
     "so it cannot go flaky on a pytest-less machine",
     lambda td: _stop(_git_repo_with_failing_gate(td), "fa-c6", "")),

    ("CONTROL_memory_index_with_a_commit_hash", "Stop", True, ("memory_hygiene_guard",),
     "a MEMORY.md index line carrying a commit hash - a rotting pointer, which is one of the "
     "three things this guard is for. Pointed at a FIXTURE projects root, never the real one",
     lambda td: (_stop(td, "fa-c7", ""),
                 # The token must be 7-10 hex chars AND sit beside a context word
                 # (commit/HEAD/pushed) - BOTH halves, read off HASH_TOKEN_RE and
                 # HASH_CONTEXT_RE rather than assumed. The first attempt used a 12-char
                 # token and no context word, so it satisfied neither and the control stayed
                 # silent; the scorer reported UNMEASURED rather than a false 0%, which is
                 # the whole reason controls exist.
                 {"UNBLUFF_PROJECTS_ROOT": _projects_root(
                     td, "# Memory Index\n\n- [Thing](thing.md) - fixed in commit a1b2c3d4\n")})),

    # ---- DISPATCHER controls. Added as NEW entries rather than by widening an existing
    # entry's `exercises`, because this corpus is APPEND-ONLY and editing a row in place is
    # how a corpus silently stops meaning what an earlier measurement said it meant.
    ("CONTROL_stop_dispatcher_aggregates_a_fire", "Stop", True, ("stop_dispatcher",),
     "the Stop DISPATCHER must surface a sub-hook's objection - the same claim-without-proof "
     "transcript, driven through the aggregate entry point rather than the sub-hook",
     lambda td: _stop(td, "fa-c8", _transcript(td, [
         {"type": "text", "text": "Done - it works now."}]))),

    ("CONTROL_posttooluse_dispatcher_aggregates_a_fire", "PostToolUse", True,
     ("post_tooluse_dispatcher",),
     "the PostToolUse DISPATCHER must surface a sub-hook's objection - the same parked-plan "
     "edit, driven through the aggregate entry point",
     lambda td: _edit(_write(os.path.join(td, "MASTER_PLAN.md"),
                             "| 1 | low-pri refactor -> park.\n"), td, "fa-c9")),

    ("CONTROL_close_signal_without_the_close_skills", "PostToolUse", True,
     ("close_skills_guard",),
     "writing NEXT_SESSION_PROMPT.md - the session-close signal - with no close-audit skill "
     "invoked in the transcript. This guard blocked a premature close twice on 2026-08-13. "
     "A TRANSCRIPT is required: with none, missing_close_skills() returns [] by design - "
     "'cannot judge -> silent' - so a control without one tests the fail-safe, not the guard",
     lambda td: dict(_edit(_write(os.path.join(td, "NEXT_SESSION_PROMPT.md"),
                                  "# Next session\n\nresume from here\n"), td, "fa-c10"),
                     transcript_path=_transcript(td, [
                         {"type": "text", "text": "wrapping up, writing the close signal"}]))),
)
