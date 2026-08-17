#!/usr/bin/env python3
"""The gate ledger: which gates actually RAN, and when. Shared by every tier.

WHY THIS EXISTS AS A MODULE. A gate that did not run leaves no trace in the code or the docs,
so "were the gates green?" is unanswerable after the fact - you can only re-run and hope
nothing changed in between. Reviewers then reconstruct it from memory, which is how eight
eval batteries once went unexecuted while every review reported healthy.

WHY IT WAS NOT ENOUGH. The writer lived inside `run_selftests.py` as a private function with
the gate name HARDCODED, so exactly one of five tiers could record anything. Measured
2026-08-13: 200 entries, `{'run_selftests': 200}`, while that same day ran the mutation
harness five times, the integration suite four times, the anchors gate four times and a new
criterion-3 scorer - none of which left a trace. The 1-of-5 finding had been recorded as
abstract record-keeping for days; it is the ENABLER for the ship bar's verify-before-pushing
half, which cannot exist until more than one tier is recorded.

THE CAP IS PER GATE, AND THAT IS THE LOAD-BEARING PART. The original kept `history[-200:]`
GLOBALLY. Extending that to five tiers would not have worked: `run_selftests` runs many times
an hour and the 30-minute mutation sweep runs once or twice a day, so a global cap lets the
CHEAPEST gate evict the record of the most EXPENSIVE one - and the expensive, rarely-run gate
is precisely the one whose last-run date you need. Per-gate retention makes the rare tier's
record survive exactly as long as the frequent one's.

DURABILITY, ADDED 2026-08-16 AFTER AN ADVERSARIAL REVIEW (wf_f63b9ccf-816) CONFIRMED FOUR
SEPARATE WAYS THIS FILE COULD LOSE THE RECORD IT EXISTS TO KEEP. `record()` was an unlocked,
non-atomic read-modify-write behind a blanket `except Exception: pass`, and it TRUNCATED the
target before serialising:
  - two tiers writing at once lost each other's rows wholesale, and this repo's own notes
    document that concurrent tiers happen on this machine;
  - any failure between truncate and write destroyed the entire history, unrecoverably - the
    file is GITIGNORED, so there is no restore, and a bad retention bound already cost 140
    rows once;
  - a corrupt file read back as `[]`, making "unreadable" and "nothing ever ran" the same
    answer - the identical-error-and-success-value defect this repo hunts elsewhere.
The fix is the boring one: serialise FIRST, write to a sibling temp file, `os.replace()` onto
the target (atomic on NTFS and POSIX), all inside an `O_EXCL` lock with a stale-lock timeout.
A corrupt ledger is QUARANTINED and announced rather than silently overwritten.
"""

import datetime
import errno
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(REPO, "docs", "audits", "gate_runs.json")

# Per GATE, not overall. See the module docstring - a global cap silently deletes the tier you
# most need, and does it faster the more tiers you add.
#
# 200 rather than a smaller bound, and the reason is a mistake made here on 2026-08-13: the
# first version used 60, and the very first run PERMANENTLY DISCARDED 140 of this file's 200
# historical `run_selftests` rows. The file is GITIGNORED (.gitignore:23), so there was no
# restore. Matching the previous global bound per-gate means a migration can only ever ADD
# history, never remove it.
KEEP_PER_GATE = 200

# A lock older than this is assumed to belong to a process that died. Long enough that the
# ~30-minute mutation sweep cannot trip it (the sweep holds the lock only for the final write,
# not for its runtime), short enough that a crash does not wedge the ledger until someone
# notices. MEASURED, not guessed: the longest observed record() call is milliseconds.
STALE_LOCK_S = 30

# WHAT THIS LEDGER IS NOT. It is gitignored, so it never reaches CI, does not survive a clone,
# and no reviewer can read it. It records what THIS MACHINE ran. A ship-bar gate built on it
# therefore enforces LOCAL discipline - "the sweep has been run since the last source change
# on this box" - which is exactly what verify-before-pushing needs, and is NOT a shared or
# auditable record. Anything claiming the latter needs a different artifact.


def read(path: str = LEDGER) -> tuple:
    """(history, status) where status is 'ok' | 'absent' | 'unreadable' | 'corrupt'.

    THREE outcomes, not two. The previous `_load` mapped every failure to `[]`, so a truncated
    or half-written ledger was indistinguishable from a machine that had never run a gate -
    and `tiers()` printed `{}` for both. An error value identical to a legitimate success value
    is the defect class this repo exists to catch, so the states are separated here and every
    caller gets to decide what to do about them.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return [], "absent"
    except OSError:
        return [], "unreadable"
    except ValueError:
        return [], "corrupt"
    if not isinstance(data, list):
        return [], "corrupt"
    return data, "ok"


def _load(path):
    """History only. Kept because `last_run`/`tiers` want the list and not the status."""
    return read(path)[0]


def prune(history, keep=KEEP_PER_GATE):
    """Keep the last `keep` runs OF EACH GATE, preserving overall order.

    Pure, so the retention rule can be asserted without writing a file - the previous version
    was an inline slice inside a try/except that no test could reach.
    """
    counts = {}
    keep_idx = set()
    for i in range(len(history) - 1, -1, -1):
        gate = (history[i] or {}).get("gate", "?")
        counts[gate] = counts.get(gate, 0) + 1
        if counts[gate] <= keep:
            keep_idx.add(i)
    return [row for i, row in enumerate(history) if i in keep_idx]


def _acquire(lock_path: str, stale_s: float = STALE_LOCK_S):
    """An O_EXCL lock file, stealing one that is provably stale. None if it could not be taken.

    Without this, two tiers finishing at once each read the same history, each appended one row,
    and the second write erased the first tier's row. Both gates reported success.
    """
    for _attempt in range(2):
        try:
            return os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except OSError as e:
            if e.errno != errno.EEXIST:
                return None
            try:
                age = time.time() - os.path.getmtime(lock_path)
            except OSError:
                age = 0.0
            if age <= stale_s:
                return None
            # The holder is gone (SIGKILL cannot run a cleanup handler, which is exactly why
            # the timeout - and not a finally block - is the real guarantee here).
            try:
                os.unlink(lock_path)
            except OSError:
                return None
    return None


def _release(fd, lock_path):
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(lock_path)
    except OSError:
        pass


def quarantine(path: str) -> str:
    """Rename a corrupt ledger aside and return the new name. Never delete evidence."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dead = "%s.corrupt-%s" % (path, stamp)
    os.replace(path, dead)
    return dead


def record(gate: str, result: str, **fields) -> None:
    """Append one gate run. BEST-EFFORT: an unwritable ledger must never fail the gate.

    The swallow at the bottom is deliberate and stays - a bookkeeping failure turning a green
    suite red would be a worse trade. What changed is that it now guards a write that cannot
    lose history even if it is interrupted: the payload is serialised BEFORE the target is
    touched, written to a sibling temp file, and moved into place with os.replace(), which is
    atomic on both NTFS and POSIX. There is no longer a window in which the ledger exists as a
    truncated file.
    """
    lock_path = LEDGER + ".lock"
    fd = None
    try:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        fd = _acquire(lock_path)
        if fd is None:
            # Another tier is mid-write. Dropping ONE row is strictly better than corrupting
            # the file or clobbering that tier's row, and it is announced rather than silent.
            print("[gate-ledger] NOTE: %s not recorded - the ledger lock is held. The run "
                  "itself is unaffected; only its ledger row was skipped." % gate)
            return
        history, status = read(LEDGER)
        notes = {}
        if status == "corrupt":
            dead = quarantine(LEDGER)
            print("[gate-ledger] WARNING: the ledger was unparseable and has been moved to %s. "
                  "History before this point is NOT lost, it is in that file - but it is no "
                  "longer readable by last_run()/tiers(), so treat the record as discontinuous."
                  % os.path.basename(dead))
            # A marker row, so the discontinuity is visible in tiers() instead of looking like
            # a machine that had simply never run anything.
            history = [{"gate": "_discontinuity", "utc": _utc(), "result": "CORRUPT",
                        "quarantined_to": os.path.basename(dead)}]
        elif status == "unreadable":
            notes["ledger_was_unreadable"] = True
        row = {"gate": gate, "utc": _utc(), "result": result}
        row.update(fields)
        row.update(notes)
        history.append(row)
        payload = json.dumps(prune(history), indent=2)      # serialise BEFORE touching target
        tmp = LEDGER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, LEDGER)
    except Exception:                              # noqa: BLE001 - never fail the caller
        pass
    finally:
        if fd is not None:
            _release(fd, lock_path)


def _utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def last_run(gate: str, path: str = LEDGER):
    """The most recent recorded run of `gate`, or None. The reader a ship-bar gate needs."""
    rows = [r for r in _load(path) if (r or {}).get("gate") == gate]
    return rows[-1] if rows else None


def tiers(path: str = LEDGER) -> dict:
    """{gate: count} - the coverage question, answerable without reconstructing it."""
    out = {}
    for r in _load(path):
        g = (r or {}).get("gate", "?")
        out[g] = out.get(g, 0) + 1
    return out


def selftest() -> int:
    import tempfile
    fails = []

    # The retention rule, asserted directly. A frequent gate must NOT evict a rare one.
    hist = ([{"gate": "run_selftests", "utc": "t%d" % i} for i in range(500)]
            + [{"gate": "mutation_harness", "utc": "rare"}])
    kept = prune(hist, keep=60)
    rare = [r for r in kept if r["gate"] == "mutation_harness"]
    frequent = [r for r in kept if r["gate"] == "run_selftests"]
    if not rare:
        fails.append("a 500-run frequent gate EVICTED the only run of a rare one - which is "
                     "exactly what the global cap did, and why this is per-gate")
    if len(frequent) != 60:
        fails.append("per-gate retention kept %d of a 500-run gate, expected 60"
                     % len(frequent))
    # order must survive, or "the last run" stops meaning the last run
    if kept != sorted(kept, key=lambda r: hist.index(r)):
        fails.append("prune() reordered history; last_run() would return the wrong row")

    # last_run must read back what record() writes, keyed by gate
    with tempfile.TemporaryDirectory(prefix="unbluff-gl-") as td:
        p = os.path.join(td, "g.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump([{"gate": "a", "utc": "1", "result": "PASS"},
                       {"gate": "b", "utc": "2", "result": "FAIL"},
                       {"gate": "a", "utc": "3", "result": "PASS"}], f)
        if (last_run("a", p) or {}).get("utc") != "3":
            fails.append("last_run returned the wrong row for a repeated gate")
        if last_run("zzz", p) is not None:
            fails.append("last_run invented a row for a gate that never ran")
        if tiers(p) != {"a": 2, "b": 1}:
            fails.append("tiers() miscounted: %r" % (tiers(p),))

    # [2026-08-16] record() ITSELF - the one function every caller uses, and until now the only
    # one no assertion executed. prune/last_run/tiers were all pinned; the writer was not, so
    # reverting it to its documented pre-fix bug (the hardcoded gate name that recorded 1 tier
    # of 5) was invisible to the registered gate. Found by review wf_f63b9ccf-816.
    global LEDGER
    saved = LEDGER
    try:
        with tempfile.TemporaryDirectory(prefix="unbluff-gl-rec-") as td:
            LEDGER = os.path.join(td, "docs", "audits", "gate_runs.json")
            record("alpha", "PASS", ran=1)
            record("beta", "FAIL", ran=2)
            record("alpha", "PASS", ran=3)
            got = tiers(LEDGER)
            if got != {"alpha": 2, "beta": 1}:
                fails.append("record() did not write the CALLER's gate name - got %r, expected "
                             "{'alpha': 2, 'beta': 1}. The pre-fix bug hardcoded one name and "
                             "recorded 1 tier of 5" % (got,))
            row = last_run("beta", LEDGER) or {}
            if row.get("result") != "FAIL" or row.get("ran") != 2:
                fails.append("record() dropped the result or the **fields: %r" % (row,))

            # atomicity: a corrupt ledger must be QUARANTINED and announced, never silently
            # overwritten, and the discontinuity must be visible afterwards
            with open(LEDGER, "w", encoding="utf-8") as f:
                f.write("{ this is not json")
            if read(LEDGER)[1] != "corrupt":
                fails.append("a truncated ledger did not read as 'corrupt' - 'unreadable' and "
                             "'nothing ever ran' would give the same answer again")
            record("gamma", "PASS")
            after = tiers(LEDGER)
            if "_discontinuity" not in after:
                fails.append("a corrupt ledger was overwritten without leaving a discontinuity "
                             "marker, so the gap is invisible: %r" % (after,))
            if not [n for n in os.listdir(os.path.dirname(LEDGER)) if ".corrupt-" in n]:
                fails.append("the corrupt ledger was destroyed rather than quarantined")

            # The lock must exclude a second writer. Assert it with a lock file that is CLOSED
            # but FRESH, not one held open: on Windows os.unlink refuses a file with an open
            # handle, so a held-open lock is defended by the OS rather than by this code, and
            # the assertion passed no matter what _acquire did. Measured, not reasoned - the
            # GL-LOCK mutation SURVIVED against the held-open version and dies against this one.
            lock = LEDGER + ".lock"
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            try:
                before = len(_load(LEDGER))
                record("delta", "PASS")
                if len(_load(LEDGER)) != before:
                    fails.append("record() stole a FRESH lock, so two concurrent tiers can "
                                 "still clobber each other's rows and both report success")
            finally:
                if os.path.exists(lock):
                    os.unlink(lock)
            # ...and a STALE lock must be stolen, or one crash wedges the ledger forever
            held2 = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(held2)
            os.utime(lock, (time.time() - STALE_LOCK_S - 60,) * 2)
            before = len(_load(LEDGER))
            record("epsilon", "PASS")
            if len(_load(LEDGER)) != before + 1:
                fails.append("a STALE lock was not stolen, so a killed process wedges the "
                             "ledger permanently")
    finally:
        LEDGER = saved

    print("-- gate-ledger: keep %d per gate; tiers recorded live: %r"
          % (KEEP_PER_GATE, tiers()))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else print(json.dumps(tiers(), indent=2)) or 0)
