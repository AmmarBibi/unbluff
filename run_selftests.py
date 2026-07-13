#!/usr/bin/env python3
"""Run every self-testable hook's --selftest and exit nonzero if any fail.

Cross-platform (used by CI on Linux/macOS/Windows and locally). rate_prompt.py has no
--selftest (it is a pure instruction-injector), so it is skipped.
"""

import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SELFTESTABLE = {
    "fast_test_on_stop", "show_your_proof", "meta_audit_on_stop",
    "memory_hygiene_guard", "stop_dispatcher", "hook_health_check",
}


def main():
    failed = []
    ran = 0
    for path in sorted(glob.glob(os.path.join(HERE, "hooks", "*.py"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name not in SELFTESTABLE:
            print(f"skip {name} (no selftest)")
            continue
        ran += 1
        rc = subprocess.run([sys.executable, path, "--selftest"],
                            stdin=subprocess.DEVNULL).returncode
        print(f"{name}: {'OK' if rc == 0 else 'FAIL'}")
        if rc != 0:
            failed.append(name)
    if failed:
        print(f"\nFAILED ({len(failed)}/{ran}): {failed}")
        return 1
    print(f"\nall {ran} selftests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
