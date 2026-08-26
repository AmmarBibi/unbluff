# Source-coverage audit - 2026-08-26

Run against the **DESIGN**, not the code. Unit under audit: item 5's wiring, the delta
`6aa7e65..1443a59`.

## STEP 1 - name the sources

"Done" for a wired hook is defined against these, not against item 5's own description:

1. **`install.py`'s settings construction** - `HOOK_EVENTS`, `ID_PREFIX`, `_cmd()`,
   `shell_tool_matcher()`, and the literal `PreToolUse` group it builds at line 147. This is the
   authority on what a correctly registered unbluff hook looks like.
2. **`install.py`'s uninstall predicate** - the rule that decides which groups are unbluff's.
3. **`hooks/piped_gate_guard.py`'s header** - `SHELL_TOOLS`, and PGG-PS's account of why the
   matcher must be derived rather than literal.

The guiding question, stated before looking at what was written: **what would `install.py` write
that I did not?**

## STEP 2 - enumerate the source

| # | field `install.py` writes | source value (derived by calling it) |
|---|---|---|
| S1 | `matcher` | `shell_tool_matcher()` -> `'Bash\|PowerShell'` |
| S2 | `hooks[0].type` | `"command"` |
| S3 | `hooks[0].command` | `_cmd("piped_gate_guard.py")` |
| S4 | `hooks[0].timeout` | `10` |
| S5 | `id` | `ID_PREFIX + "piped-gate"` -> **`'unbluff:piped-gate'`** |
| S6 | `description` | the sh/PowerShell explanation string |
| S7 | field SET | exactly `{matcher, hooks, id, description}` |
| S8 | uninstall selects by | `str(g.get("id","")).startswith(ID_PREFIX)` |

## STEP 3 - reconcile

| source item | status |
|---|---|
| S1 matcher | **BUILT** - `'Bash\|PowerShell'`, and confirmed identical to what `shell_tool_matcher()` returns. Worktree and live `SHELL_TOOLS` are also identical, so it will not change under the pull. |
| S2 type, S4 timeout, S6 description, S7 field set | **BUILT** - byte-identical field set `['description','hooks','id','matcher']`, hook keys `['command','timeout','type']` |
| S3 command | **BUILT, deliberately DIFFERENT** - points at the LIVE clone, not the worktree `HOOKS_DIR` `_cmd()` would produce. Intentional and consistent with the other seven wired hooks; running `install.py` from the worktree would repoint all of them, which is a change nobody asked for. Recorded as a justified divergence, not an oversight. |
| **S5 id / S8 uninstall predicate** | **GAP - a real defect. FIXED.** |

## The finding

The `id` was written **`unbluff-piped-gate`** (hyphen). `install.ID_PREFIX` is **`unbluff:`**
(colon), and uninstall selects groups with
`str(g.get("id","")).startswith(ID_PREFIX)`.

`"unbluff-piped-gate".startswith("unbluff:")` is **False**. So:

- `install.py --uninstall` would have left the group in place - an **orphaned PreToolUse hook,
  still firing, invisible to the only tool that manages unbluff's registrations.**
- It works perfectly today, which is precisely why nothing would have surfaced it. The hook fires,
  hook-health resolves it, `duplicate_registration_check` sees exactly one registration. Every
  check says green.

This is the **"registered once, from the wrong root"** class that `stale_root_registrations` was
built for, one level up: not a wrong path, but a right path under an id the management layer cannot
see. A state no check had a name for.

**Fixed** to `unbluff:piped-gate`, and verified against `install.py`'s OWN predicate rather than
against a reading of it: `uninstall WOULD remove it: True`, id equal to `ID_PREFIX + "piped-gate"`,
field set identical. The guard was then re-probed where it ships - `run_selftests | tail` -> rc=2
BLOCKED, `ls | head` -> rc=0 silent - so the correction did not disturb behaviour.
`duplicate_registration_check --selftest` passes; hook-health still reports 31 commands.

## Why the code-only reading would have missed it

Reading `piped_gate_guard.py` tells you nothing about this. Reading the wired settings entry tells
you nothing either - it looks well-formed. The defect only exists *relative to install.py's
convention*, and it is only visible when you enumerate what that file would write and diff it
field by field. **That is the difference between auditing the code and auditing the design.**

## STEP 4/5 - ledger + verify

Every S-item has exactly one status; S3's divergence carries its justification inline in the plan,
not only here. Item 5's row now records the id defect, its cause, and its verification. No
optional-forever language introduced.
