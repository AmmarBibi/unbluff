# unbluff's tests are custom stdlib selftest runners, NOT pytest - so the fast_test_on_stop
# hook must be told the real command here, else it falls back to `pytest` (which collects
# nothing in this repo and reports a false "no tests ran" failure at stop).
# run_selftests.py runs every hook + skill --selftest; the heavier install/uninstall
# integration test (tests/test_integration.py) is intentionally NOT run on every turn-end.
python run_selftests.py
timeout=120
