# The PUSH-TIME command, declared explicitly rather than inherited from .claude/fast-test.cmd.
#
# [#45 2026-08-24] The two are deliberately different, and the difference is the whole point.
# Turn-end asks the strictest question available: is ANYTHING wrong, including this machine's
# wiring. A push asks a narrower one: is this CODE sound. `hook-provenance` answers the first
# and not the second - it reports whether the hooks wired on THIS BOX are a current copy of
# unbluff, which during any release is legitimately false, because the branch is ahead of the
# copy that is wired.
#
# MEASURED at 1a0d649: 22 foreign references, AST delta 66 tokens, and the wired file confirmed
# BY HASH to be main:hooks/pre_push_gate.py - 91 insertions behind, i.e. exactly the gate 2 and
# gate 8 fixes. All true, all about the machine, and it BLOCKED the push that would have fixed
# it. A guard that stands between you and the repair is the shape that gets guards switched off,
# and the escape it pushes you toward is `--no-verify`, which turns off ALL of them.
#
# --code-only excludes machine-state gates from the VERDICT only. They still run, still print,
# and are still named with their reason in the output, so this can never read as a clean run.
# A CODE gate that fails still blocks, and run_selftests --selftest asserts exactly that.
python run_selftests.py --code-only
timeout=300
