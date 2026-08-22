#!/usr/bin/env python3
"""The README's strongest trust claim, mechanised: no network, no telemetry.

WHY THIS EXISTS. The README carries a `network - none` badge and states "no third-party
dependencies, no network, no telemetry". Until now that was enforced by NOTHING. The promise
inventory recorded it as RM-03 and said so plainly: "a hook that opened a connection would pass
run_selftests.py, every AUX_GATE, the integration test and the mutation sweep". On a public repo
that accepts pull requests, the single most load-bearing claim on the front page was the one
claim with no gate behind it - in a project whose entire thesis is that claims should be proven.

WHAT IT CHECKS. Every tracked `.py` file under the shipped directories, by AST rather than by
grep: an `import` of a networking module, an attribute call into one, or a subprocess invocation
of a networking BINARY. Grep would false-positive on the word "socket" in a docstring - and this
file is full of such words - so the population is parsed, not searched.

THE POPULATION IS DERIVED. `git ls-files` first, walk as a fallback, and the report says WHICH -
a declared roster standing in for a derived one is this repo's most-repeated defect, and a gate
that hardcoded its own file list would be the same defect one directory over.

FAILS CLOSED. A file that cannot be read or parsed is a PROBLEM, not a skip: "I could not look"
must never be recorded as "there is nothing to see", and its count stays in the denominator so
the total cannot shrink silently as files become unreadable.

    python tools/check_no_network.py            # the gate
    python tools/check_no_network.py --selftest # planted positives AND negatives
"""

import ast
import io
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNED_DIRS = ("hooks", "tools", "tests", "skills", "scripts")
ROOT_FILES = ("install.py", "run_selftests.py")

# Stdlib modules that can open a connection. Deliberately broad: the claim is "no network", so
# the bar is "could this reach the outside", not "does this definitely send bytes".
NET_MODULES = frozenset({
    "socket", "ssl", "urllib", "urllib2", "http", "httplib", "requests", "httpx", "aiohttp",
    "ftplib", "smtplib", "poplib", "imaplib", "telnetlib", "xmlrpc", "webbrowser",
    "socketserver", "asyncio", "websocket", "websockets", "paramiko", "boto3", "curl_cffi",
})
# Binaries that reach the network, if one is ever spawned.
NET_BINARIES = frozenset({
    "curl", "wget", "nc", "ncat", "netcat", "ssh", "scp", "sftp", "rsync", "telnet",
    "Invoke-WebRequest", "Invoke-RestMethod",
})

# Adjudicated exceptions: path -> reason. Checked in BOTH directions like NOT_A_GATE, so an
# entry that stops being needed is itself a failure and the list cannot rot into cover.
ALLOWED = {}


def population(root: str = REPO) -> tuple:
    """(relpaths, source) for the .py files this gate judges. DERIVED, and it says HOW."""
    try:
        out = subprocess.run(["git", "ls-files", "--", "*.py"], cwd=root, capture_output=True,
                             text=True, timeout=60)
        if out.returncode == 0 and out.stdout.strip():
            rels = [ln.strip().replace(os.sep, "/") for ln in out.stdout.splitlines() if ln.strip()]
            keep = [r for r in rels
                    if (r.split("/", 1)[0] in SCANNED_DIRS or r in ROOT_FILES)
                    and os.path.isfile(os.path.join(root, *r.split("/")))]
            return keep, "git"
    except (OSError, subprocess.SubprocessError):
        pass
    rels = []
    for d in SCANNED_DIRS:
        for dp, dn, fn in os.walk(os.path.join(root, d)):
            dn[:] = [x for x in dn if x not in ("__pycache__", ".git")]
            for f in fn:
                if f.endswith(".py"):
                    rels.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    rels += [f for f in ROOT_FILES if os.path.isfile(os.path.join(root, f))]
    return sorted(rels), "walk"


def _is_spawn(node: ast.Call) -> bool:
    """True if this Call actually launches a process. See the note in offenders_in()."""
    f = node.func
    name = getattr(f, "attr", "") or getattr(f, "id", "")
    if name in ("run", "Popen", "call", "check_call", "check_output"):
        return getattr(getattr(f, "value", None), "id", "") in ("subprocess", "sp", "")
    return name in ("system", "popen", "execv", "execvp", "spawnv")


def offenders_in(source: str, rel: str = "<memory>") -> list:
    """Network reachs in one file's SOURCE. Pure, so the selftest can plant known answers.

    AST, not grep: this very file names every networking module in a frozenset and would flag
    itself under any textual rule - which is the shape of guard that gets deleted for crying wolf.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return ["%s: does not parse (%s) - a file this gate cannot read is REPORTED, never "
                "silently skipped" % (rel, exc.msg)]
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in NET_MODULES:
                    hits.append("%s:%d imports %s" % (rel, node.lineno, a.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in NET_MODULES:
                hits.append("%s:%d imports from %s" % (rel, node.lineno, node.module))
        elif isinstance(node, ast.Call) and _is_spawn(node):
            # ONLY inside an actual spawn. The first version inspected string constants in ANY
            # Call, and immediately flagged THIS FILE: `NET_BINARIES = frozenset({...})` is a
            # Call node, so every binary name in the vocabulary read as an invocation of it. A
            # guard whose own definition trips it is the "fires on correct work" shape its
            # docstring warns about - caught by the gate on its first run against a tracked tree,
            # which is the only reason it did not ship that way.
            for arg in ast.walk(node):
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    first = arg.value.strip().split(" ")[0].split("/")[-1].split("\\")[-1]
                    if first in NET_BINARIES:
                        hits.append("%s:%d spawns %r" % (rel, node.lineno, first))
    return sorted(set(hits))


def scan(root: str = REPO) -> tuple:
    """(offenders, examined, unreadable, source)."""
    rels, src = population(root)
    offenders, unreadable = [], []
    for rel in rels:
        path = os.path.join(root, *rel.split("/"))
        try:
            text = io.open(path, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            unreadable.append("%s: unreadable (%s)" % (rel, exc))
            continue
        offenders.extend(h for h in offenders_in(text, rel) if rel not in ALLOWED)
    return offenders, len(rels), unreadable, src


def verdict(offenders, examined, unreadable, src, allowed=None) -> tuple:
    """(rc, message). PURE, so the selftest can exercise every branch - the lesson of
    check_mutation_anchors, whose decision was once inline and therefore untested."""
    allowed = ALLOWED if allowed is None else allowed
    if examined < 20:
        return 1, ("no-network: CANNOT RUN - only %d file(s) in the population (source: %s). A "
                   "gate that examined almost nothing must not report OK." % (examined, src))
    stale = sorted(set(allowed) - {o.split(":")[0] for o in offenders})
    if unreadable:
        return 1, ("no-network: FAIL - %d file(s) could not be read, so the claim is unproven:"
                   "\n  " + "\n  ".join(unreadable)) % len(unreadable)
    if offenders:
        return 1, ("no-network: FAIL - %d network reach(es) in %d file(s) examined (source: %s). "
                   "The README claims none:\n  %s"
                   % (len(offenders), examined, src, "\n  ".join(offenders)))
    if stale:
        return 1, ("no-network: FAIL - %d adjudicated exception(s) no longer needed: %s. An "
                   "exemption list that outlives its reason rots into cover."
                   % (len(stale), ", ".join(stale)))
    return 0, ("no-network: OK - %d file(s) examined (source: %s), 0 network reach(es), "
               "%d adjudicated exception(s)" % (examined, src, len(allowed)))


def main() -> int:
    offenders, examined, unreadable, src = scan()
    rc, msg = verdict(offenders, examined, unreadable, src)
    print(msg)
    return rc


def selftest() -> int:
    """PLANTED fixtures, both directions. A selftest that only scanned the live repo would pass
    on a clean tree no matter what the detector did - which is how every mutation of such a
    guard survives."""
    fails = []
    must_flag = {
        "import socket": "import socket\n",
        "from urllib import": "from urllib import request\n",
        "dotted import": "import http.client\n",
        "curl via subprocess": "import subprocess\nsubprocess.run(['curl', 'http://x'])\n",
        "wget in a string": "import subprocess\nsubprocess.run('wget http://x', shell=True)\n",
    }
    for label, src in must_flag.items():
        if not offenders_in(src, "f.py"):
            fails.append("MISSED a network reach (%s) - the guard is blind to it" % label)
    must_not = {
        "the word socket in a docstring": '"""talks about socket and urllib"""\nx = 1\n',
        "a local name": "def urllib():\n    return 1\n",
        "ordinary subprocess": "import subprocess\nsubprocess.run(['git', 'status'])\n",
        "unrelated import": "import json, os\n",
        # the regression this gate caught in ITSELF on its first tracked run: a vocabulary of
        # binary names is a frozenset() Call, not an invocation of any of them.
        "a frozenset of binary names": 'NAMES = frozenset({"curl", "wget", "ssh"})\n',
        "a list of binary names": 'NAMES = ["curl", "nc"]\n',
    }
    for label, src in must_not.items():
        hit = offenders_in(src, "f.py")
        if hit:
            fails.append("FALSE ALARM on %s: %r - a guard that fires on correct code gets "
                         "deleted" % (label, hit))
    if not offenders_in("def f(:\n", "bad.py"):
        fails.append("an unparseable file was silently skipped - it must be REPORTED")

    if verdict([], 5, [], "git")[0] != 1:
        fails.append("a population of 5 was accepted - the floor is what stops a collapsed scan "
                     "reporting OK")
    if verdict([], 50, ["x: unreadable"], "git")[0] != 1:
        fails.append("an unreadable file did not fail the gate - 'I could not look' is not "
                     "'there is nothing to see'")
    if verdict(["a.py:1 imports socket"], 50, [], "git")[0] != 1:
        fails.append("a real offender did not fail the gate")
    if verdict([], 50, [], "git")[0] != 0:
        fails.append("a clean scan did not pass - the gate would be permanently red")
    if verdict([], 50, [], "git", allowed={"gone.py": "reason"})[0] != 1:
        fails.append("a stale adjudication was accepted; an exemption list must be checked in "
                     "BOTH directions or it rots into cover")

    offenders, examined, unreadable, src = scan()
    print("-- no-network selftest: %d planted fixture(s), live scan %d file(s) (source: %s)"
          % (len(must_flag) + len(must_not), examined, src))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
