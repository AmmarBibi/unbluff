# unbluff's tests are custom stdlib selftest runners, NOT pytest - so the fast_test_on_stop
# hook must be told the real command here, else it falls back to `pytest` (which collects
# nothing in this repo and reports a false "no tests ran" failure at stop).
# run_selftests.py runs every hook + skill --selftest; the heavier install/uninstall
# integration test (tests/test_integration.py) is intentionally NOT run on every turn-end.
# [2026-08-14] 120 -> 300. MEASURED: the suite is 109.1s against the old 120s ceiling - 91% of
# it - so the pre-push gate began BLOCKING correct pushes. That is a guard firing on correct
# work, which is how a guard gets switched off (the `--no-verify` the message itself suggests).
# The suite grew legitimately: 33 gates on 08-13, 37 on 08-14.
# This is a RESOURCE bound, not a correctness one, so raising it does not weaken any check -
# but the growth was INVISIBLE until it blocked a push, so run_selftests now records its
# DURATION in the gate ledger. Watch that number rather than rediscovering this at the ceiling.
python run_selftests.py
timeout=300
