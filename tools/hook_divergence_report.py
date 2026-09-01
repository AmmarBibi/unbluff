#!/usr/bin/env python3
"""Gate: no hook may be WIRED from a copy that is not this repo's.

WHY THIS IS A GATE AND NOT A REPORT. This file used to diff two named directories and its
docstring ended "Exits 0 always; it is a report, not a gate." It could not fail, nothing ran
it, and its default roots were a hardcoded pair. Meanwhile a stale copy of these hooks ran
every `git push` on the author's machine for weeks - including unbluff's own pushes, gated by
an outdated fail-open copy of unbluff's own gate. `git status` was clean throughout, because
the divergent copy lived outside the repo. A report nobody runs, that cannot fail, and whose
roster is two hardcoded paths, is three fail-opens in one file.

THE QUESTION IT ASKS NOW is provenance, not directory equality: for every hook this machine
has WIRED, does the script it runs live inside this repo? That question stays answerable after
the duplicate directory is deleted, which "diff A against B" does not - with B gone there is
nothing left to compare and the check silently passes forever.

DERIVED, NEVER LISTED. The roster of our hook names comes from `hooks/*.py`. The roster of
wired commands comes from every settings layer Claude Code merges PLUS git's own hook
surfaces - `core.hooksPath` (global and local) and each repo's `.git/hooks`. A two-entry
hardcoded roster was tried in a sibling project and missed a third instance immediately.

BOTH DENOMINATORS ARE PRINTED. A provenance check that examined nothing looks exactly like one
that examined everything and found nothing wrong.

    python tools/hook_divergence_report.py [--selftest] [--json out.json] [--repo DIR]

Exit 1 if any wired hook resolves to a foreign copy of one of our hooks, or if a wired command
could not be parsed at all. Exit 0 only when every wired instance of our hooks is this repo's.
"""
from __future__ import annotations

import argparse
import ast
import glob
import hashlib
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)
_HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

# REUSE, not re-implement. duplicate_registration_check already owns "split a hook command the
# way a shell does" and "which settings files does Claude Code merge". A second copy of either
# is the twin defect this repo exists to catch, and its _path_tokens carries a fix (shlex, so a
# home directory containing a space still parses) that a fresh regex would silently lose.
from duplicate_registration_check import _path_tokens, settings_layers  # noqa: E402

# [#46 item 4] Scrub git's redirect variables at import, before any fixture can run.
# Flagged by tools/check_selftest_isolation.py, which DERIVES this population from the AST
# rather than from a list - and found this file after a hand-built roster of three missed it.
# Reason this file is in the population: its selftest plants foreign copies and writes git config.
# No ImportError fallback here, unlike the hooks/ copies: git_isolation is a SIBLING in
# tools/, so if it is missing this tool is broken anyway and failing loudly at import is the
# honest outcome. The fallback in hooks/ exists only because a partial checkout can have
# hooks/ without tools/.
from git_isolation import scrub_environ as _scrub_environ  # noqa: E402
_scrub_environ()


def norm(p: str) -> str:
    """One canonical spelling, so C:\\a\\b and c:/a/b compare equal on Windows."""
    try:
        p = os.path.realpath(p)
    except OSError:
        pass
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")


def our_hook_names(hooks_dir: str | None = None) -> set:
    """Basenames of THIS repo's hooks. Derived from the filesystem; never a literal list."""
    d = hooks_dir or _HOOKS_DIR
    return {os.path.basename(p) for p in glob.glob(os.path.join(glob.escape(d), "*.py"))}


def _json_commands(path: str) -> list:
    """Every (command, args) pair in a settings file, as one command string each."""
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out

    def walk(node):
        if isinstance(node, dict):
            if "command" in node:
                cmd = node.get("command")
                args = node.get("args")
                parts = [cmd if isinstance(cmd, str) else ""]
                if isinstance(args, list):
                    parts += [a for a in args if isinstance(a, str)]
                elif isinstance(args, str):
                    parts.append(args)
                out.append(" ".join(p for p in parts if p))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return out


def _git_hook_dirs(repos: list | None = None, cwd: str | None = None) -> list:
    """Directories git will actually run hooks from.

    core.hooksPath REPLACES .git/hooks wholesale, so both surfaces must be read: the global
    setting decides which one is live today, and the other becomes live the moment it is unset.
    A check that looked at only one would have called this machine clean while every push ran a
    foreign copy.
    """
    dirs = []
    # `cwd` is a test seam, not decoration: without it the local scope could only ever be read
    # from the process's own directory, so a selftest could not create a repo that SETS
    # core.hooksPath and prove the function finds it. The first version of that assertion checked
    # only that the string "core.hooksPath" still appeared in this function - and a mutation that
    # emptied the scope loop SURVIVED it, because the literal was still there. Presence is not
    # behaviour.
    base = ["git"] + (["-C", cwd] if cwd else [])
    for scope in ("--global", "--local"):
        try:
            r = subprocess.run(base + ["config", scope, "core.hooksPath"],
                               capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            continue
        p = (r.stdout or "").strip()
        if r.returncode == 0 and p:
            dirs.append(os.path.expanduser(p))
    for root in (repos or [REPO_ROOT]):
        dirs.append(os.path.join(root, ".git", "hooks"))
    return [d for d in dirs if os.path.isdir(d)]


def _strip_shell_comments(body: str) -> str:
    """Drop whole-line shell comments before extracting paths.

    Our own shim templates document themselves with `# ... managed by <path>`, so reading
    comments made every correctly-installed dispatcher look like a foreign wiring. A comment
    cannot wire anything; only executable lines can. (Trailing `#` on a code line is left alone
    - stripping it would need a shell parser, and a false NEGATIVE there is the dangerous
    direction, so the conservative choice is to keep the line.)
    """
    return "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))


def _shell_commands(hook_dir: str) -> list:
    """Text of every hook script in a git hooks dir (they are shell, not JSON)."""
    out = []
    try:
        names = sorted(os.listdir(hook_dir))
    except OSError:
        return out
    for n in names:
        p = os.path.join(hook_dir, n)
        if not os.path.isfile(p) or n.endswith(".sample"):
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                out.append(_strip_shell_comments(fh.read()))
        except OSError:
            continue
    return out


def wired_sources(settings_paths=None, hook_dirs=None) -> list:
    """[(surface, command_string)] across every wiring surface, DERIVED from disk."""
    src = []
    for p in (settings_paths if settings_paths is not None else settings_layers()):
        if os.path.exists(p):
            for c in _json_commands(p):
                src.append((p, c))
    for d in (hook_dirs if hook_dirs is not None else _git_hook_dirs()):
        for body in _shell_commands(d):
            src.append((d, body))
    return src


def provenance(settings_paths=None, hook_dirs=None, hooks_dir=None) -> dict:
    """Classify every wired reference to one of OUR hook names as ours or foreign.

    A command naming none of our hooks is not our business and is counted, not judged - the
    machine is full of other people's hooks and flagging them would make this gate noise.
    """
    ours = our_hook_names(hooks_dir)
    repo_hooks = norm(hooks_dir or _HOOKS_DIR)
    sources = wired_sources(settings_paths, hook_dirs)

    result = {"examined": len(sources), "our_hook_names": len(ours),
              "matched": [], "foreign": [], "unparsed": [], "bare": [], "surfaces": []}
    seen_surfaces = set()
    for surface, cmd in sources:
        if surface not in seen_surfaces:
            seen_surfaces.add(surface)
            result["surfaces"].append(surface)
        toks = _path_tokens(cmd)
        if not toks:
            # A command that names one of our hooks but yields no parseable path is the
            # dangerous case: non-extraction is indistinguishable from non-duplication, which
            # is exactly how a sibling guard failed open. Report it rather than skip it.
            if any(n in cmd for n in ours):
                result["unparsed"].append({"surface": surface, "command": cmd[:200]})
            continue
        for t in toks:
            base = os.path.basename(t.replace("\\", "/"))
            if base not in ours:
                continue
            entry = {"surface": surface, "script": t, "name": base}
            if "/" not in t and "\\" not in t:
                # A bare basename is not a wiring path - nothing on this machine puts hooks on
                # PATH. Our OWN dispatcher contains `grep -q pre_push_gate.py "$local_hook"` as a
                # marker test, and reading that as a wiring made 22 correct dispatchers look
                # foreign. COUNTED and printed, never silently dropped: if a real wiring ever
                # arrives in this shape, the bare bucket is where it will show up.
                result["bare"].append(entry)
                continue
            if os.path.dirname(norm(t)) == repo_hooks:
                result["matched"].append(entry)
            elif _same_repo_same_bytes(t, repo_hooks, base):
                # [#39] A LINKED WORKTREE IS NOT A FOREIGN COPY. Path equality alone called it
                # one: settings.json wires the main checkout, so running from a worktree flagged
                # all 29 references with `AST delta 0` and IDENTICAL shas, and the gate fired on
                # correct work - hard enough to BLOCK the v1.4.0 push, which is how a guard ends
                # up switched off. Two conditions, both required: git says the same repository
                # (same common dir, so a genuinely separate clone still fails), AND the bytes
                # match (so a STALE worktree - the drift this gate exists for - still fails).
                entry["note"] = "same repository via a linked worktree, byte-identical"
                result["matched"].append(entry)
            else:
                result["foreign"].append(entry)
    return result


def _git_common_dir(path: str):
    """The repository a path belongs to, or None. Linked worktrees share this with their main
    checkout, which is exactly the fact a path comparison cannot see."""
    d = path if os.path.isdir(path) else os.path.dirname(path)
    if not os.path.isdir(d):
        return None
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--git-common-dir"],
                           capture_output=True, timeout=15, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    # Decoded explicitly: subprocess text=True is cp1252 here and mangles non-ASCII paths.
    out = r.stdout.decode("utf-8", "surrogateescape").strip()
    if not out:
        return None
    return norm(out if os.path.isabs(out) else os.path.join(d, out))


def _same_program(a: bytes, b: bytes) -> bool:
    r"""Byte equality, blind to line endings ONLY.

    A CRLF checkout and an LF checkout of the same commit differ by hundreds of bytes and are
    the same program. MEASURED 2026-08-26 on this machine: `cap_shapes.py` and
    `capped_report.py` differed from the wired copy by 756 and 171 bytes while git reported the
    two commits IDENTICAL for both files. A raw byte compare called 10 of 28 `hooks/*.py` stale
    when 8 were - a guard firing on correct work, which is the shape this repo says gets guards
    switched off, and the CRLF case is named explicitly in `tooling-discipline`.

    Deliberately narrow: only \r\n -> \n. Whitespace, comments and docstrings are NOT
    normalised, because a copy differing in any of those IS a different file and noticing that
    is the entire point of this gate.
    """
    return a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def _read(path: str):
    """File bytes, or None. None means COULD NOT LOOK and never means no difference."""
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _same_repo_same_bytes(wired: str, repo_hooks: str, base: str) -> bool:
    """True only if `wired` is our OWN file reached through another worktree of this repository.

    Fails closed: an unreadable side, a git failure, or any difference that is not purely a line
    ending -> False, i.e. the reference stays FOREIGN. The dangerous direction is a false
    negative - a genuinely stale copy waved through - so every uncertainty resolves toward
    flagging.
    """
    mine = os.path.join(repo_hooks, base)
    if not (os.path.isfile(wired) and os.path.isfile(mine)):
        return False
    ours = _git_common_dir(repo_hooks)
    theirs = _git_common_dir(wired)
    if not ours or not theirs or ours != theirs:
        return False
    a, b = _read(wired), _read(mine)
    if a is None or b is None:
        return False
    return _same_program(a, b)


# ------------------------------------------------------------------ [item 15] the COUNT

def dispatcher_children(hooks_dir: str = None) -> dict:
    """{dispatcher basename: [child module names]}, READ FROM THE AST of `hooks/*.py`.

    DERIVED, NEVER LISTED - and this population has already been counted wrong twice. The plan
    carried 11 entry points: settings.json's 8, `stop_dispatcher`'s table counted as **2**, and
    the pre-push shim. The truth measured 2026-08-26 is **16**. `stop_dispatcher.HOOKS` has
    FOUR children, not two - `show_your_proof` and `memory_hygiene_guard` were never counted -
    and `post_tooluse_dispatcher` has a table of its own (`plan_defer_guard`,
    `numbers_match_on_write`, `timing_claim_guard`) that no count has ever included at all.
    Five hooks that run on every matching event sat outside the denominator.

    A dispatcher is recognised by SHAPE, not by name: a module-level `HOOKS` bound to a
    tuple/list of pairs whose first element is a string. Naming the two known dispatchers here
    is what would let a third be missed, which is exactly how the last two were.
    """
    d = hooks_dir or _HOOKS_DIR
    tables = {}
    for p in sorted(glob.glob(os.path.join(glob.escape(d), "*.py"))):
        src = _read(p)
        if src is None:
            continue
        try:
            tree = ast.parse(src.decode("utf-8", "replace"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if "HOOKS" not in [t.id for t in node.targets if isinstance(t, ast.Name)]:
                continue
            if not isinstance(node.value, (ast.Tuple, ast.List)):
                continue
            kids = []
            for elt in node.value.elts:
                if isinstance(elt, (ast.Tuple, ast.List)) and elt.elts:
                    first = elt.elts[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        kids.append(first.value)
            if kids:
                tables[os.path.basename(p)] = kids
    return tables


def entry_points(settings_paths=None, hook_dirs=None, hooks_dir=None) -> dict:
    """{basename: the path the machine actually RUNS} for every hook that executes here.

    Three reaching mechanisms, all derived: a wiring surface names the script (settings.json or
    a git hook shim), or a WIRED dispatcher imports it by name. A dispatcher that is not itself
    wired contributes nothing - its children do not run - so the population tracks reality
    rather than the repo's ambitions.
    """
    ours = our_hook_names(hooks_dir)
    found = {}
    for _surface, cmd in wired_sources(settings_paths, hook_dirs):
        for t in _path_tokens(cmd):
            base = os.path.basename(t.replace("\\", "/"))
            if base in ours and ("/" in t or "\\" in t):
                found.setdefault(base, t)
    for disp, kids in sorted(dispatcher_children(hooks_dir).items()):
        wired = found.get(disp)
        if not wired:
            continue
        near = os.path.dirname(wired)
        for k in kids:
            base = k + ".py"
            if base in ours:
                found.setdefault(base, os.path.join(near, base))
    return found


def _classify(wired: str, mine: str) -> str:
    """'same' | 'eol' | 'differs' | 'absent' | 'unreadable'.

    'unreadable' is its own answer on purpose: could-not-look must never be recorded as
    found-no-difference, which is this suite's most-repeated finding about its own instruments.
    """
    if not os.path.isfile(wired):
        return "absent"
    a, b = _read(wired), _read(mine)
    if a is None or b is None:
        return "unreadable"
    if a == b:
        return "same"
    return "eol" if _same_program(a, b) else "differs"


def staleness(entry: dict, hooks_dir: str = None) -> dict:
    """How much of what RUNS is not what is BUILT - both numerators, both denominators.

    ABSENT counts as stale and is labelled: a module living in no live copy at all is the most
    stale a file can be, and lumping it in with "differs" hides that it was never delivered.
    Line-ending-only differences are counted and PRINTED but never called stale - see
    `_same_program`.
    """
    d = hooks_dir or _HOOKS_DIR
    res = {"entry_total": len(entry), "entry_stale": [], "entry_absent": [], "entry_eol": [],
           "entry_unreadable": [], "files_total": 0, "files_stale": [], "files_absent": [],
           "files_eol": [], "files_unreadable": [], "wired_dirs": []}
    for base in sorted(entry):
        kind = _classify(entry[base], os.path.join(d, base))
        if kind == "differs":
            res["entry_stale"].append(base)
        elif kind == "absent":
            res["entry_absent"].append(base)
        elif kind == "eol":
            res["entry_eol"].append(base)
        elif kind == "unreadable":
            res["entry_unreadable"].append(base)

    res["wired_dirs"] = sorted({norm(os.path.dirname(p)) for p in entry.values() if p})
    names = sorted(our_hook_names(hooks_dir))
    res["files_total"] = len(names)
    # One wired hooks dir is the normal case. With two or more, "the live copy" is ambiguous and
    # a single P/Q would be a made-up number - so the row is withheld and SAID to be withheld.
    if len(res["wired_dirs"]) == 1:
        wd = res["wired_dirs"][0]
        for base in names:
            kind = _classify(os.path.join(wd, base), os.path.join(d, base))
            if kind == "differs":
                res["files_stale"].append(base)
            elif kind == "absent":
                res["files_absent"].append(base)
            elif kind == "eol":
                res["files_eol"].append(base)
            elif kind == "unreadable":
                res["files_unreadable"].append(base)
    return res


def _git_out(cwd: str, *args):
    try:
        r = subprocess.run(["git", "-C", cwd] + list(args), capture_output=True, timeout=15,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", "surrogateescape").strip() or None


def sync_phrase(ahead: str, behind: str) -> str:
    """SAY THE REMEDY ONLY WHEN THERE IS SOMETHING TO REMEDY.

    The first version printed "only a push/merge will clear the count" unconditionally, so the
    moment the merge landed and the answer became 0 of 16 it was still demanding a merge - a
    guard telling you to fix what you have just fixed, which is the shape this repo says gets
    guards switched off. Found by running it where it ships, immediately after the merge it had
    itself recommended. Split out as a pure function so both directions can be probed without a
    git fixture.
    """
    if ahead == "0" and behind == "0":
        return "same repository, IN SYNC with the live worktree - nothing to reconcile."
    return ("SAME repository, different commits: this branch is %s commit(s) AHEAD of\n      "
            "the live one and %s behind. A `git pull` over there cannot clear a count\n      "
            "caused by unpushed commits - only a push/merge, or rewiring, will." % (ahead, behind))


def wired_divergence_note(wired_dirs: list, repo_root: str = REPO_ROOT) -> list:
    """WHY the live copies differ - the sentence whose absence caused a wrong prediction.

    "Run the pull and the count becomes 0" was written into the plan and acted on, and it was
    FALSE. The wired copies are the MAIN worktree of THIS SAME repository, tracking `main`,
    while the work happens on a branch ahead of it. A pull moves that clone to `origin/main`;
    it cannot deliver commits that were never pushed. The number alone could not say this, and
    a number that invites a wrong remedy is worse than no number - so the relationship is
    derived and printed beside it.
    """
    notes = []
    mine_common = _git_common_dir(repo_root)
    for wd in wired_dirs:
        top = _git_out(wd, "rev-parse", "--show-toplevel") or os.path.dirname(wd)
        if norm(top) == norm(repo_root):
            continue
        wb, wc = _git_out(top, "rev-parse", "--abbrev-ref", "HEAD"), _git_out(top, "rev-parse",
                                                                             "--short", "HEAD")
        mb, mc = (_git_out(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
                  _git_out(repo_root, "rev-parse", "--short", "HEAD"))
        if not (wb and wc and mb and mc):
            notes.append("live copies are in %s; git could not be asked how it relates to this "
                         "repo, so the CAUSE of any difference above is UNKNOWN" % top)
            continue
        line = "live copies run from %s @ %s (%s); this repo is %s @ %s" % (top, wc, wb, mb, mc)
        their_common = _git_common_dir(wd)
        if mine_common and their_common and mine_common == their_common:
            cnt = _git_out(repo_root, "rev-list", "--left-right", "--count",
                           "%s...%s" % (wc, mc))
            behind, ahead = ((cnt or "").split() + ["?", "?"])[:2]
            line += "\n      " + sync_phrase(ahead, behind)
        else:
            line += "\n      a SEPARATE repository, not a worktree of this one."
        notes.append(line)
    return notes


# --------------------------------------------------------------------------- diffing a find

def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:]
    return tree


def ast_delta(a: str, b: str):
    """(token_delta, identical) between two modules, or None if either cannot be parsed."""
    from collections import Counter

    def toks(path):
        try:
            with open(path, encoding="utf-8") as fh:
                tree = _strip_docstrings(ast.parse(fh.read()))
        except (OSError, SyntaxError):
            return None
        c: Counter = Counter()
        for n in ast.walk(tree):
            if isinstance(n, ast.Name):
                c["name:" + n.id] += 1
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                c["def:" + n.name] += 1
            elif isinstance(n, ast.Attribute):
                c["attr:" + n.attr] += 1
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                c["str:" + n.value[:60]] += 1
        return c, ast.dump(tree)

    ta, tb = toks(a), toks(b)
    if ta is None or tb is None:
        return None
    return sum((ta[0] - tb[0]).values()) + sum((tb[0] - ta[0]).values()), ta[1] == tb[1]


def sha(path: str):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError:
        return None


# The selftest battery lives in tools/hook_divergence_selftest.py - see that file's header for
# why, and for the two conditions the cut had to satisfy. Imported lazily inside main() so a
# normal gate run never pays for tempfile/git fixtures it will not use, and so a missing sibling
# is a loud failure ON THE SELFTEST PATH rather than an import error that takes the GATE down.
def selftest() -> int:
    try:
        from hook_divergence_selftest import selftest as _run
    except ImportError as exc:
        print("SELFTEST FAILED: tools/hook_divergence_selftest.py could not be imported (%s). "
              "The battery is not optional - a selftest that cannot load is not a selftest that "
              "passed." % exc)
        return 1
    return _run()



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--repo", help="treat this dir's hooks/ as canonical (default: this repo)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    hooks_dir = os.path.join(args.repo, "hooks") if args.repo else None
    r = provenance(hooks_dir=hooks_dir)

    print("=" * 74)
    print("HOOK PROVENANCE - is every WIRED hook this repo's copy?")
    print("=" * 74)
    # BOTH denominators, always. "0 foreign" means nothing without them.
    print("  our hook names (derived from hooks/*.py): %d" % r["our_hook_names"])
    print("  wiring surfaces read: %d" % len(r["surfaces"]))
    for s in r["surfaces"]:
        print("      %s" % s)
    print("  hook commands examined: %d" % r["examined"])
    print("  references to OUR hooks: %d ours, %d foreign, %d unparsed, %d bare-name"
          % (len(r["matched"]), len(r["foreign"]), len(r["unparsed"]), len(r["bare"])))

    # [item 15] BUILT IS NOT LIVE, DERIVED. This number was hand-counted five times and was
    # wrong five times - 2 of 6, 4 of 6, 5 of 6, 5 of 10, 6 of 11 - and each correction fixed
    # the NUMERATOR while the denominator stayed scoped to whatever the author had in mind.
    # It is printed here because this gate already walks every wiring surface; the count was
    # the one thing it computed and threw away. The plain-prose copies of it are deleted from
    # docs/PLAN.md: a number restated in a second place drifts in one of them, and it did, four
    # sessions running.
    ep = entry_points(hooks_dir=hooks_dir)
    st = staleness(ep, hooks_dir)
    n_entry = len(st["entry_stale"]) + len(st["entry_absent"])
    n_files = len(st["files_stale"]) + len(st["files_absent"])
    if len(st["wired_dirs"]) == 1:
        files_row = "%d of %d hooks/*.py" % (n_files, st["files_total"])
    else:
        files_row = ("hooks/*.py row WITHHELD - %d wired hook dirs, so 'the live copy' is "
                     "ambiguous" % len(st["wired_dirs"]))
    # [item 23] A ZERO POPULATION IS NOT A CLEAN MACHINE, and this gate's own docstring says so:
    # "a provenance check that examined nothing looks exactly like one that examined everything
    # and found nothing wrong". main() has honoured that for the VERDICT since the rebuild, with
    # a two-cause split. The count shipped without it and printed a bare "0 of 0 entry points
    # stale" on a machine with no wiring - typographically identical to a fully synced one, and
    # what every fresh CI checkout would print forever. Same two causes, same split, said here.
    if st["entry_total"] == 0:
        why = ("no wiring surface on this machine declares any hook, so there is nothing to be "
               "stale - INAPPLICABLE, not clean" if not r["surfaces"] else
               "%d wiring surface(s) were read and NOT ONE resolved to an entry point. That is "
               "a broken derivation wearing a clean result, not a synced machine" % len(r["surfaces"]))
        print("  BUILT IS NOT LIVE: NO COUNT - %s" % why)
    else:
        print("  BUILT IS NOT LIVE: %d of %d entry points stale, %s"
              % (n_entry, st["entry_total"], files_row))
    # [item 24] THE TRAJECTORY, DERIVED - the half that makes recording worth doing. Read BEFORE
    # this run records, or the "previous" row is this one. See hook_divergence_trend.py.
    try:
        import hook_divergence_trend
        print("      %s" % hook_divergence_trend.trajectory(n_entry, st))
    except Exception as _e:                        # a missing trend view must SAY so, not vanish
        print("      trajectory: UNAVAILABLE (%s) - no comparison was made, which is NOT the "
              "same as no change." % type(_e).__name__)
    for label, key in (("stale", "entry_stale"), ("ABSENT live", "entry_absent"),
                       ("UNREADABLE", "entry_unreadable")):
        if st[key]:
            print("      entry points %s: %s" % (label, ", ".join(st[key])))
    if st["files_stale"]:
        print("      files differing: %s" % ", ".join(st["files_stale"]))
    if st["files_absent"]:
        print("      files ABSENT live: %s" % ", ".join(st["files_absent"]))
    # Counted and named, never silently dropped: a line-ending-only difference is NOT staleness,
    # and saying so is what stops the next reader "fixing" it.
    eol = sorted(set(st["entry_eol"]) | set(st["files_eol"]))
    if eol:
        print("      %d line-ending-only difference(s), NOT counted as stale: %s"
              % (len(eol), ", ".join(eol)))
    if st["files_unreadable"]:
        print("      %d file(s) COULD NOT BE READ - not counted either way: %s"
              % (len(st["files_unreadable"]), ", ".join(st["files_unreadable"])))
    for note in wired_divergence_note(st["wired_dirs"]):
        print("      %s" % note)
    # [item 23, second half] --json is an advertised output, and a consumer of it could not see
    # the number this gate exists to publish. Merged into the same payload rather than a second
    # file, so there is one artifact to read.
    r["staleness"] = st

    # [item 24 2026-08-28] The count now has a HISTORY, derived like the count is. Field shaping
    # and the trend sentence live in hook_divergence_trend.py - this file hit the 800-line ratchet
    # twice while they were being written, and trimming a third time is how a ratchet becomes
    # cover. THE record CALL STAYS HERE ON PURPOSE: unrecorded_tiers() resolves RECORDING_TIERS by
    # walking THIS file's AST for it, so moving the call would point the tier row at a helper and
    # describe the wrong file as the tier.
    #
    # The plan asserted "hook-provenance already calls into that path". IT DID NOT - this file had
    # no gate_ledger call and was in no RECORDING_TIERS row, so nothing here was ever recorded
    # under its own name. Checked before designing around it, per that row's confirm-don't-assume.
    def _record(result: str) -> None:
        try:
            import gate_ledger
            import hook_divergence_trend
            gate_ledger.record("hook_provenance", result,
                               **hook_divergence_trend.ledger_fields(st, r, n_entry, n_files))
        except Exception:                          # never let bookkeeping fail a gate
            pass

    # [MODE-CONTROL follow-up] A zero denominator has TWO causes and they are not the same fact.
    # No surface at all = this machine has no wiring, so the gate is inapplicable (a fresh CI
    # checkout). Surfaces that exist but declare no hook command = something we READ produced
    # nothing, which is a broken parse wearing a clean result. The old code printed one NOTE for
    # both and returned 0 either way, so the second - the only one that is a defect - was
    # indistinguishable from the first.
    if r["examined"] == 0 and not r["surfaces"]:
        print("\n  NOTE: no wiring surface on this machine declared any hook. This gate is "
              "INAPPLICABLE here;\n        it is the --selftest that shows it can still see an "
              "offender.")
    elif r["examined"] == 0:
        print("\nFAIL: %d wiring surface(s) were read and NOT ONE hook command was examined. A "
              "denominator of\nzero from surfaces that exist is a broken parse, not a clean "
              "machine - the surfaces were:\n   %s"
              % (len(r["surfaces"]), "\n   ".join(r["surfaces"])))
        _record("FAIL")
        return 1

    for f in r["foreign"]:
        print("\nFOREIGN COPY WIRED: %s" % f["name"])
        print("   wired from : %s" % f["surface"])
        print("   runs       : %s" % f["script"])
        print("   this repo  : %s" % os.path.join(_HOOKS_DIR, f["name"]))
        mine = os.path.join(_HOOKS_DIR, f["name"])
        d = ast_delta(f["script"], mine)
        if d is None:
            print("   AST delta  : (one side could not be parsed - compare by hand)")
        else:
            delta, identical = d
            print("   AST delta  : %d token(s), %s" % (delta, "same program" if identical
                                                       else "DIFFERENT PROGRAMS"))
        print("   sha        : foreign=%s  repo=%s" % (sha(f["script"]), sha(mine)))

    for u in r["unparsed"]:
        print("\nUNPARSEABLE COMMAND naming one of our hooks (provenance UNKNOWN, not clean):")
        print("   %s\n   %s" % (u["surface"], u["command"]))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2)
        print("\nJSON written to %s" % args.json)

    bad = len(r["foreign"]) + len(r["unparsed"])
    if bad:
        print("\nFAIL: %d wired reference(s) are not this repo's copy. A copy outside the repo "
              "does not\nshow up in `git status`, so it can drift for weeks unnoticed - that is "
              "how an outdated\nfail-open gate came to run every push on this machine." % bad)
        _record("FAIL")
        return 1
    print("\nOK: every wired reference to our hooks resolves to this repo.")
    # EVERY exit after the count records. A recorder wired to only the happy path builds a series
    # made of successes, which is the one shape that cannot show a trajectory getting worse - and
    # this gate's subject is precisely a number that grows as the branch pulls ahead.
    _record("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
