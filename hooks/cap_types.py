"""What KIND of thing is a name - the evidence half of the cap guard.

Clause 1 (collection vs scalar), clause 2 (is the value even reported) and clause 3
(provenance) all reduce to questions about a name or an expression inside ONE function.
They live here, apart from hooks/cap_shapes.py, which asks the other question: what
OPERATION is being applied. Splitting on that seam is what keeps either file under the
800-line rule - cap_shapes arrived at 804 as one module, which is the same live violation
duplicate_registration_check hit at 835 and fixed by MOVING code rather than logging it.

Nothing here decides anything. It reports evidence, and UNKNOWN is a real answer: a guard
that stays quiet on what it cannot classify fails open, which is the premise the C1-NEW
rebuild exists to replace.

Python 3.8 floor: no ast.unparse (3.9+), no match statement.
"""

from __future__ import annotations

import ast

# A bare integer below this is a POSITION or an arity check, not a cap: parts[:1], entry[:2],
# kept[:3], `len(entry) < 4`, `len(entries) < 2` are all structural.
#
# MEASURED, not tuned: the corpus pins 1/2/3/4 as quiet and 10/12 as caps, and the live repo
# adds `len(entries) < 2`. 5 is the largest value consistent with that evidence. The band
# 5..9 is untested in EITHER direction - stated here rather than left for a reader to assume
# the boundary was derived.
POSITIONAL_FLOOR = 5

_MUTATORS = {"append", "extend", "insert", "add", "pop", "remove", "update"}

# Clause 1 evidence. A call whose result is a str/bytes, and one whose result is a sequence.
_SCALAR_CALLS = {"read", "hexdigest", "decode", "encode", "strip", "lstrip", "rstrip",
                 "lower", "upper", "join", "format", "getsize", "str", "repr", "len",
                 # str-returning, found by running this over the live hooks rather than by
                 # imagining the list: re.sub built memory_hygiene_guard's false positive
                 "sub", "subn", "replace", "title", "casefold", "capitalize", "zfill",
                 "ljust", "rjust", "center", "expandtabs", "translate",
                 "basename", "dirname", "abspath", "normpath", "relpath", "normcase"}

# Clause 2. A value consumed by one of these never reaches the user as a list - it becomes a
# bool, a number or a branch. Shortening it hides nothing, because nothing was going to be
# reported. Found by the live sweep: meta_audit_on_stop scans `splitlines()[:5]` inside
# any(), and numbers_match_on_write tests `prefix[-24:]` inside an if.
_AGGREGATORS = {"any", "all", "sum", "min", "max", "len", "bool", "set", "frozenset",
                "next", "int", "float"}
_COLLECTION_CALLS = {"list", "sorted", "set", "dict", "tuple", "split", "splitlines",
                     "readlines", "items", "keys", "values", "glob"}
_COLLECTION_ANNOTATIONS = {"list", "List", "tuple", "Tuple", "set", "Set", "dict", "Dict",
                           "Sequence", "Iterable", "MutableSequence"}

# Clause 3. I/O the function performed ITSELF - a read WINDOW over data the caller never
# had, as opposed to a truncation of data the caller handed in.
_IO_CALLS = {"read", "readlines", "readline", "open", "recv", "getvalue", "iterdir",
             "walk", "glob", "run", "check_output", "communicate"}

# ----------------------------------------------------------------------------------
# small AST helpers
# ----------------------------------------------------------------------------------

def _name_of(node):
    """The bare Name this expression is rooted at, or None. No ast.unparse (3.9+)."""
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _call_name(node):
    """The called function's own name - `a.b.read()` -> 'read', `list(x)` -> 'list'."""
    if not isinstance(node, ast.Call):
        return None
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return None

def _len_arg(node):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "len" and node.args):
        return node.args[0]
    return None


def _walk_skipping_functions(node):
    """Every descendant, but not into a nested def - that is its own scope."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        cur = stack.pop()
        yield cur
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stack.extend(ast.iter_child_nodes(cur))


def _contains_exit(node):
    """Break/Return/Continue anywhere under `node`. Recursive on purpose:
    break_nested_in_with buries the break inside a `with` inside the if-body."""
    for sub in _walk_skipping_functions(node):
        if isinstance(sub, (ast.Break, ast.Return, ast.Continue)):
            return True
    return False


def _import_aliases(tree):
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name] = a.name.split(".")[0]
    return aliases


def _negative_constant(node):
    return isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)


def _small_int(node):
    """A bare integer literal below the positional floor."""
    return (isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool) and node.value < POSITIONAL_FLOOR)

# ----------------------------------------------------------------------------------
# clause 1 - is this name a COLLECTION, a SCALAR, or unknown?
# ----------------------------------------------------------------------------------

class Facts(object):
    """Intra-function evidence about every local name. Built once per scope."""

    def __init__(self, scope):
        self.bindings = {}          # name -> [value node, ...]
        self.mutated = set()        # .append/.pop/... called on it -> definitely a collection
        self.annotations = {}       # name -> annotation node
        self.str_concat = set()     # used in `+` with a str literal -> definitely a scalar
        self.appends_in_loop = set()
        self.appends_outside_loop = set()
        self._collect(scope)

    def _collect(self, scope):
        for arg in _all_args(scope):
            if arg.annotation is not None:
                self.annotations[arg.arg] = arg.annotation
        loop_depth = _loop_depths(scope)
        for node in _walk_skipping_functions(scope):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.bindings.setdefault(t.id, []).append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                self.annotations[node.target.id] = node.annotation
                if node.value is not None:
                    self.bindings.setdefault(node.target.id, []).append(node.value)
            elif isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
                self.bindings.setdefault(node.target.id, []).append(node.value)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in _MUTATORS:
                    name = _name_of(node.func.value)
                    if name:
                        self.mutated.add(name)
                        if loop_depth.get(id(node), 0) > 0:
                            self.appends_in_loop.add(name)
                        else:
                            self.appends_outside_loop.add(name)
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                for a, b in ((node.left, node.right), (node.right, node.left)):
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        nm = _name_of(b)
                        if nm:
                            self.str_concat.add(nm)

    def kind(self, name):
        """'collection' | 'scalar' | 'unknown'. UNKNOWN flags: a guard that stays quiet on
        what it cannot type would fail open, which is the premise this rebuild replaces."""
        if name is None:
            return "unknown"
        if name in self.mutated:
            return "collection"          # .append()/.pop() do not exist on str
        if name in self.str_concat:
            return "scalar"
        ann = self.annotations.get(name)
        if ann is not None:
            root = _name_of(ann) or (ann.id if isinstance(ann, ast.Name) else None)
            if root in _COLLECTION_ANNOTATIONS:
                return "collection"
            if root in ("str", "bytes", "int", "float"):
                return "scalar"
        for value in self.bindings.get(name, ()):
            call = _call_name(value)
            if call in _COLLECTION_CALLS:
                return "collection"
            if call in _SCALAR_CALLS:
                return "scalar"
            if isinstance(value, (ast.List, ast.ListComp, ast.SetComp, ast.DictComp,
                                  ast.Dict, ast.Set)):
                return "collection"
            if isinstance(value, ast.Constant) and isinstance(value.value, (str, bytes)):
                return "scalar"
            if isinstance(value, ast.JoinedStr):
                return "scalar"
        return "unknown"

    def io_derived(self, name, depth=0, seen=None):
        """Clause 3: does this name's binding chain reach I/O this function performed?

        Follows EVERY Name in the binding expression, not just its syntactic root. The root
        of `data.decode('utf-8').splitlines()` is a Call, so a root-only walk stopped dead
        one link short of `data = handle.read()` - which is the live show_your_proof site and
        the corpus's read-window entry, both missed for the same reason.
        """
        if name is None or depth > 6:
            return False
        seen = set() if seen is None else seen
        if name in seen:
            return False
        seen.add(name)
        for value in self.bindings.get(name, ()):
            for sub in ast.walk(value):
                if _call_name(sub) in _IO_CALLS:
                    return True
            for sub in ast.walk(value):
                if (isinstance(sub, ast.Name) and sub.id != name
                        and self.io_derived(sub.id, depth + 1, seen)):
                    return True
        return False


def expr_kind(node, facts):
    """Clause 1 applied to the SLICED EXPRESSION, not only to its root name.

    `hashlib.sha1(b).hexdigest()[:12]` has no root Name at all, and `line.strip()[:N]` has a
    root name whose own binding says nothing. Reading the expression directly is what makes
    those two scalar instead of unknown - and unknown FLAGS, by design.
    """
    if isinstance(node, ast.Call):
        call = _call_name(node)
        if call in _SCALAR_CALLS:
            return "scalar"
        if call in _COLLECTION_CALLS:
            return "collection"
        return "unknown"
    if isinstance(node, ast.Constant):
        return "scalar" if isinstance(node.value, (str, bytes)) else "unknown"
    if isinstance(node, ast.JoinedStr):
        return "scalar"
    if isinstance(node, ast.BinOp):
        for side in (node.left, node.right):
            if isinstance(side, ast.Constant) and isinstance(side.value, (str, bytes)):
                return "scalar"
        return "unknown"
    if isinstance(node, ast.IfExp):
        for branch in (node.body, node.orelse):
            if expr_kind(branch, facts) == "scalar":
                return "scalar"
        return "unknown"
    if isinstance(node, (ast.ListComp, ast.List, ast.Set, ast.Dict)):
        return "collection"
    return facts.kind(_name_of(node))


def _message_context_nodes(scope):
    """ids of every Subscript sitting inside a formatted MESSAGE.

    `"... %r" % (err[:120],)` and `f"...{err[:120]!r}"` truncate a string for display; they
    are not caps on a reported collection. This is the single largest false-positive family
    in the live hooks - selftest failure messages - and it is decidable structurally, so it
    does not need a roster.
    """
    marked = set()

    def mark(node):
        for sub in ast.walk(node):
            marked.add(id(sub))

    def stringy(node):
        """Recursive on purpose. `msg + " || got: " + out[:200]` nests the literal one level
        down, so requiring a bare Constant operand missed the largest family in the live
        hooks - selftest failure messages built by chained concatenation."""
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (str, bytes))
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
            return stringy(node.left) or stringy(node.right)
        if isinstance(node, ast.IfExp):
            return stringy(node.body) or stringy(node.orelse)
        return isinstance(node, ast.Call) and _call_name(node) in ("format", "join")

    for node in _walk_skipping_functions(scope):
        if isinstance(node, ast.JoinedStr):
            mark(node)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
            for a, b in ((node.left, node.right), (node.right, node.left)):
                if stringy(a):
                    mark(b)
        elif isinstance(node, ast.Call) and _call_name(node) in ("format", "join"):
            mark(node)
    return marked


def _aggregated_nodes(scope):
    """Clause 2 - ids of every node whose value is consumed into a bool/number/branch.

    A DISPLAY cap on something that never leaves the function as a list hides nothing. This
    is deliberately NOT applied to collection caps: `break`ing out of a scan destroys the
    real total for the CALLER too, whether or not this function reports it.
    """
    marked = set()

    def mark(node):
        for sub in ast.walk(node):
            marked.add(id(sub))

    for node in _walk_skipping_functions(scope):
        if isinstance(node, ast.Call) and _call_name(node) in _AGGREGATORS:
            for a in node.args:
                mark(a)
        elif isinstance(node, ast.Compare):
            mark(node)
        elif isinstance(node, (ast.If, ast.While)):
            mark(node.test)
    return marked


def _all_args(scope):
    a = getattr(scope, "args", None)
    if a is None:
        return []
    out = list(a.args) + list(a.kwonlyargs) + list(getattr(a, "posonlyargs", []))
    if a.vararg:
        out.append(a.vararg)
    if a.kwarg:
        out.append(a.kwarg)
    return out


def _loop_depths(scope):
    """{id(node): depth} so an append inside a loop is distinguishable from one outside."""
    depths = {}

    def walk(node, depth):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            d = depth + 1 if isinstance(child, (ast.For, ast.AsyncFor, ast.While)) else depth
            depths[id(child)] = d
            walk(child, d)

    walk(scope, 0)
    return depths

def _references(node, names):
    return any(isinstance(s, ast.Name) and s.id in names for s in ast.walk(node))

def _contains_exit(node):
    """Break/Return/Continue anywhere under `node`. Recursive on purpose:
    break_nested_in_with buries the break inside a `with` inside the if-body."""
    for sub in _walk_skipping_functions(node):
        if isinstance(sub, (ast.Break, ast.Return, ast.Continue)):
            return True
    return False


def _import_aliases(tree):
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name] = a.name.split(".")[0]
    return aliases


# ----------------------------------------------------------------------------------
# selftest - each vocabulary decision asserted on a parsed snippet
# ----------------------------------------------------------------------------------

def _scope_of(source, fname=None):
    """(function node, Facts) for the named def, or the module body when fname is None."""
    tree = ast.parse(source)
    if fname is None:
        return tree, Facts(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fname:
            return node, Facts(node)
    raise AssertionError("no def %s in the fixture" % fname)


_KIND_CASES = (
    # (source, name, expected kind, why this case exists)
    ("def f(xs):\n    out = []\n    out.append(1)\n    return out\n", "out", "collection",
     ".append() does not exist on str, so it PROVES a collection"),
    ("def f(fh):\n    text = fh.read()\n    return text\n", "text", "scalar",
     "a read() result is str/bytes"),
    ("def f(path):\n    s = path.replace('a', 'b')\n    return s\n", "s", "scalar",
     "re/str substitution returns str - memory_hygiene_guard's live false positive"),
    ("def f(line):\n    parts = line.split(':')\n    return parts\n", "parts", "collection",
     "split() returns a list"),
    ("def f(problems: list):\n    return problems\n", "problems", "collection",
     "an annotation is evidence"),
    ("def f(msg):\n    return 'x: ' + msg\n", "msg", "scalar",
     "concatenation with a str literal proves the other operand is a str"),
    ("def f(xs):\n    return xs\n", "xs", "unknown",
     "UNKNOWN is a real answer and it FLAGS - staying quiet on the unclassifiable is the "
     "fail-open premise this rebuild replaces"),
)


def selftest() -> int:
    fails = []

    for source, name, want, why in _KIND_CASES:
        _node, facts = _scope_of(source, "f")
        got = facts.kind(name)
        if got != want:
            fails.append("kind(%r) is %r, expected %r - %s" % (name, got, want, why))

    # expr_kind reads the EXPRESSION, which is the only way to classify something with no
    # root Name at all
    node, facts = _scope_of("import hashlib\ndef f(b):\n"
                            "    return hashlib.sha256(b).hexdigest()[:12]\n", "f")
    sub = [n for n in ast.walk(node) if isinstance(n, ast.Subscript)][0]
    if expr_kind(sub.value, facts) != "scalar":
        fails.append("expr_kind did not read .hexdigest() as a scalar - a root-name-only "
                     "check returns unknown here, and unknown flags")

    # clause 3: the chain must survive an intermediate call, which is where a root-only walk
    # stopped one link short of `data = handle.read()`
    _node, facts = _scope_of("def f(path):\n    with open(path, 'rb') as h:\n"
                            "        data = h.read()\n"
                            "    lines = data.decode('utf-8').splitlines()\n"
                            "    return lines\n", "f")
    if not facts.io_derived("lines"):
        fails.append("io_derived lost the chain lines <- data <- h.read()")
    if facts.io_derived("path"):
        fails.append("io_derived claimed a bare parameter came from I/O")

    # a cycle must terminate rather than recurse forever
    _node, facts = _scope_of("def f(a):\n    b = a\n    a = b\n    return a\n", "f")
    facts.io_derived("a")

    # clause 2 and the message rule, both directions
    node, _f = _scope_of("def f(fails, msg):\n    fails.append('bad: %r' % (msg[:120],))\n",
                         "f")
    subs = [n for n in ast.walk(node) if isinstance(n, ast.Subscript)]
    if not subs or id(subs[0]) not in _message_context_nodes(node):
        fails.append("a slice inside a %-formatted message was not recognised - this is the "
                     "largest false-positive family in the live hooks")
    node, _f = _scope_of("def f(xs):\n    return xs[:12]\n", "f")
    subs = [n for n in ast.walk(node) if isinstance(n, ast.Subscript)]
    if id(subs[0]) in _message_context_nodes(node):
        fails.append("a plain returned slice was mistaken for a message - the rule would "
                     "silence real caps")
    node, _f = _scope_of("def f(text):\n    return any(x for x in text.splitlines()[:5])\n",
                         "f")
    subs = [n for n in ast.walk(node) if isinstance(n, ast.Subscript)]
    if id(subs[0]) not in _aggregated_nodes(node):
        fails.append("a slice consumed by any() was not seen as aggregated - clause 2 is off")
    node, _f = _scope_of("def f(xs):\n    return xs[:12]\n", "f")
    subs = [n for n in ast.walk(node) if isinstance(n, ast.Subscript)]
    if id(subs[0]) in _aggregated_nodes(node):
        fails.append("a plain returned slice was mistaken for an aggregate")

    # the positional floor is a MEASURED boundary; pin both sides of it
    tree = ast.parse("a = [1, 2, 3, 4, 5, 12]")
    consts = [n for n in ast.walk(tree) if isinstance(n, ast.Constant)]
    below = [c.value for c in consts if _small_int(c)]
    above = [c.value for c in consts if not _small_int(c)]
    if below != [1, 2, 3, 4] or above != [5, 12]:
        fails.append("the positional floor moved: below=%r above=%r. The corpus pins 1-4 as "
                     "positions and 10/12 as caps; changing this silently reclassifies every "
                     "bare-integer bound in the repo" % (below, above))

    print("-- cap-types: %d kind case(s), floor %d (band 5..9 untested by construction)"
          % (len(_KIND_CASES), POSITIONAL_FLOOR))
    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
