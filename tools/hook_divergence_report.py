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
_HOOKS_DIR = os.path.join(REPO_ROOT, "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

# REUSE, not re-implement. duplicate_registration_check already owns "split a hook command the
# way a shell does" and "which settings files does Claude Code merge". A second copy of either
# is the twin defect this repo exists to catch, and its _path_tokens carries a fix (shlex, so a
# home directory containing a space still parses) that a fresh regex would silently lose.
from duplicate_registration_check import _path_tokens, settings_layers  # noqa: E402


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
            else:
                result["foreign"].append(entry)
    return result


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


def selftest() -> int:
    """Plant a foreign copy and a matching control; the gate must separate them.

    A detector that cannot SEE a planted offender is indistinguishable from a clean machine,
    which is the failure this whole file is about.
    """
    import tempfile
    fails = []

    # The SURFACE LIST must be derived, not passed in. Every other case below hands hook_dirs
    # in explicitly, which would leave _git_hook_dirs() itself unexercised - and git's hook
    # surface is precisely where the 2026-08-05 divergence ran. A gate that stopped reading it
    # would go silent on the only surface that has ever caught anything here.
    own = os.path.join(REPO_ROOT, ".git", "hooks")
    if os.path.isdir(own):
        found = {norm(d) for d in _git_hook_dirs()}
        if norm(own) not in found:
            fails.append("_git_hook_dirs() no longer reports this repo's own .git/hooks (%r); "
                         "git's hook surface is the one the real divergence ran on" % (own,))
    # BEHAVIOURAL: build a repo that actually SETS core.hooksPath and require the function to
    # find it. An earlier version asserted only that the literal "core.hooksPath" still appeared
    # in the function - mutation A3a emptied the scope loop and SURVIVED, because the literal was
    # untouched. core.hooksPath REPLACES .git/hooks wholesale, so a gate that stops reading it
    # inspects the dead surface and calls the machine clean.
    with tempfile.TemporaryDirectory() as gd:
        repo = os.path.join(gd, "r")
        os.makedirs(repo)
        want = os.path.join(gd, "myhooks")
        os.makedirs(want)
        try:
            ok = subprocess.run(["git", "-C", repo, "init", "-q"],
                                capture_output=True, timeout=30).returncode == 0
            if ok:
                subprocess.run(["git", "-C", repo, "config", "--local", "core.hooksPath", want],
                               capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            ok = False
        if ok:
            got = {norm(d) for d in _git_hook_dirs(repos=[repo], cwd=repo)}
            if norm(want) not in got:
                fails.append("_git_hook_dirs() did not report a repo's own core.hooksPath "
                             "(%r not in %r) - that setting REPLACES .git/hooks, so the gate "
                             "would read the dead surface and call the machine clean"
                             % (want, sorted(got)))
        else:
            print("  [hook-provenance] NOTE: git unavailable; the core.hooksPath discovery "
                  "assertion did NOT run")

    with tempfile.TemporaryDirectory() as td:
        fake_hooks = os.path.join(td, "hooks")
        os.makedirs(fake_hooks)
        for n in ("alpha_hook.py", "beta_hook.py"):
            with open(os.path.join(fake_hooks, n), "w", encoding="utf-8") as fh:
                fh.write("# hook\n")
        foreign_dir = os.path.join(td, "elsewhere")
        os.makedirs(foreign_dir)
        with open(os.path.join(foreign_dir, "alpha_hook.py"), "w", encoding="utf-8") as fh:
            fh.write("# stale copy\n")

        def settings_with(*cmds):
            p = os.path.join(td, "s%d.json" % len(os.listdir(td)))
            with open(p, "w", encoding="utf-8") as fh:
                json.dump({"hooks": {"Stop": [{"hooks": [{"command": c} for c in cmds]}]}}, fh)
            return p

        # CONTROL: wired from the real hooks dir -> matched, never foreign
        ctl = settings_with('python "%s"' % os.path.join(fake_hooks, "beta_hook.py"))
        r = provenance([ctl], [], fake_hooks)
        if r["foreign"]:
            fails.append("CONTROL flagged as foreign: %r - the gate would fire on a correct "
                         "install, which gets a gate disabled" % (r["foreign"],))
        if len(r["matched"]) != 1:
            fails.append("CONTROL not recognised as ours: %r" % (r["matched"],))

        # OFFENDER: same basename, different directory
        off = settings_with('python "%s"' % os.path.join(foreign_dir, "alpha_hook.py"))
        r = provenance([off], [], fake_hooks)
        if len(r["foreign"]) != 1:
            fails.append("planted FOREIGN copy not detected: %r - the gate matches nothing and "
                         "would report any machine as clean" % (r,))

        # OFFENDER via a git hook shim (the surface that actually bit): shell, not JSON
        gh = os.path.join(td, "githooks")
        os.makedirs(gh)
        with open(os.path.join(gh, "pre-push"), "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\nexec "py" "%s" "$@"\n'
                     % os.path.join(foreign_dir, "alpha_hook.py").replace("\\", "/"))
        r = provenance([], [gh], fake_hooks)
        if len(r["foreign"]) != 1:
            fails.append("foreign copy wired via a GIT HOOK not detected: %r. That is the exact "
                         "surface the 2026-08-05 divergence ran on" % (r,))

        # a path with a SPACE must still parse - the _path_tokens fix must not be lost
        spaced = os.path.join(td, "John Doe")
        os.makedirs(spaced, exist_ok=True)
        with open(os.path.join(spaced, "alpha_hook.py"), "w", encoding="utf-8") as fh:
            fh.write("# stale\n")
        sp = settings_with('python "%s"' % os.path.join(spaced, "alpha_hook.py"))
        r = provenance([sp], [], fake_hooks)
        if len(r["foreign"]) != 1:
            fails.append("a foreign path CONTAINING A SPACE was not detected: %r - every user "
                         "whose home dir has a space would be unchecked" % (r,))

        # an UNPARSEABLE command naming one of ours must be reported, never silently skipped
        up = settings_with("run-alpha_hook.py-somehow --with no path")
        r = provenance([up], [], fake_hooks)
        if not r["unparsed"]:
            fails.append("a command naming one of our hooks with no extractable path was "
                         "silently dropped - non-extraction must not read as non-divergence")

        # NEGATIVE CONTROL 1: our own shim documents itself in a COMMENT. A comment cannot wire
        # anything, and reading it made 22 correctly-installed dispatchers look foreign during
        # the very repair that installed them.
        gh2 = os.path.join(td, "githooks2")
        os.makedirs(gh2)
        with open(os.path.join(gh2, "pre-push"), "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\n# managed by ~/.claude/hooks/alpha_hook.py\nexec "py" "%s"\n'
                     % os.path.join(fake_hooks, "alpha_hook.py").replace("\\", "/"))
        r = provenance([], [gh2], fake_hooks)
        if r["foreign"]:
            fails.append("a path inside a shell COMMENT was read as a wiring: %r - every "
                         "self-documenting shim would fail this gate" % (r["foreign"],))
        if len(r["matched"]) != 1:
            fails.append("the real exec line was lost while stripping comments: %r" % (r,))

        # NEGATIVE CONTROL 2: a bare basename (our dispatcher greps for one) is not a wiring.
        gh3 = os.path.join(td, "githooks3")
        os.makedirs(gh3)
        with open(os.path.join(gh3, "pre-push"), "w", encoding="utf-8") as fh:
            fh.write('#!/bin/sh\ngrep -q alpha_hook.py "$local_hook" && exit 0\n')
        r = provenance([], [gh3], fake_hooks)
        if r["foreign"]:
            fails.append("a BARE basename was classified as a foreign wiring: %r"
                         % (r["foreign"],))
        if len(r["bare"]) != 1:
            fails.append("a bare basename was silently dropped instead of counted: %r" % (r,))

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


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

    if r["examined"] == 0:
        print("\n  NOTE: no wiring surface on this machine declared any hook. This gate proved "
              "nothing here;\n        it is the --selftest that shows it can still see an "
              "offender.")

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
        return 1
    print("\nOK: every wired reference to our hooks resolves to this repo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
