#!/usr/bin/env python3
"""Which files Claude Code actually merges hooks from - DERIVED, never listed.

[P14 B3-P] `duplicate_registration_check.settings_layers()` returned four paths: the user and
project `settings.json` / `settings.local.json`. Hooks contributed by PLUGINS were invisible, so
a hook wired both by a plugin and by `settings.json` reported CLEAN. That is the same
non-extraction-reads-as-non-duplication premise B3 fixed for extensions, one layer up: an
EXTENSION roster became a LAYER roster.

WHY THIS IS NOT A GLOB. The obvious fix - walk `plugins/` and read every `hooks.json` - is
wrong, and measurably so on the author's machine 2026-08-06:

  * 7 plugin `hooks.json` exist, but `settings.json` declares
    `enabledPlugins = {posthog@..., plugin-dev@...}`. Six of the seven belong to DISABLED
    plugins sitting in the marketplace cache. Their hooks never fire. Feeding them in would
    have invented six plugins' worth of wirings and reported them as duplicates against a
    correct config - B3-FP repeating, whose whole lesson is that a guard which false-alarms on
    a correct config gets disabled, which is strictly worse than no guard.
  * `~/.claude/hooks/hooks.json` LOOKS like a large missed layer - 21 commands, settings-shaped,
    `$schema` and all - and is not one. It shares 0 of 30 command strings with `settings.json`,
    and `hook_health_check` independently reports exactly the 30 that `settings.json` declares.
    It is a source template that gets installed INTO settings.json. Reading it would have
    double-counted every hook installed from it.

So the enabled set is read from the AUTHORITY (`enabledPlugins`) and only then resolved against
the filesystem. Neither half alone is correct: the authority does not know where the files are,
and the filesystem does not know which of them fire.

FAIL CLOSED ON THE DENOMINATOR, not on the sample. Every count this module derives is returned
so the caller can print it. An `enabledPlugins` entry that resolves to no file, and a plugin
`hooks.json` that declares nothing, are both REPORTED rather than dropped - a layer that
silently contributes zero is indistinguishable from a layer that was never looked for, which is
the exact failure this module exists to end.
"""
from __future__ import annotations

import json
import os
import sys

# Directories that never contain a plugin's own hook declaration and can be enormous. Pruned by
# name rather than by depth: a depth cap would silently stop finding real plugins the day a
# marketplace nests one level deeper, and this module must not narrow in silence.
_PRUNE = {"node_modules", ".git", "__pycache__", "dist", "build"}

SETTINGS = os.path.expanduser("~/.claude/settings.json")


def enabled_plugin_keys(settings_data) -> tuple:
    """(keys, malformed) - the plugins whose hooks Claude Code actually merges.

    Strict `is True`, deliberately. The asymmetry matters: treating an unrecognised value as
    ENABLED invents wirings and false-alarms on a correct config, which is the failure that gets
    a guard switched off. Treating it as disabled merely misses one - so anything that is not a
    plain boolean is returned in `malformed` and REPORTED, never silently assumed either way.
    """
    if not isinstance(settings_data, dict):
        return [], []
    enabled = settings_data.get("enabledPlugins")
    if not isinstance(enabled, dict):
        return [], []
    keys, malformed = [], []
    for k, v in enabled.items():
        if not isinstance(k, str):
            malformed.append("enabledPlugins key %r is %s, not a string"
                             % (k, type(k).__name__))
            continue
        if v is True:
            keys.append(k)
        elif v is not False:
            malformed.append("enabledPlugins[%r] is %r (%s), not a boolean - treated as "
                             "DISABLED so a guess cannot invent a wiring" % (k, v, type(v).__name__))
    return sorted(keys), malformed


def _hooks_json_files(plugins_root: str) -> list:
    """Every `hooks.json` under the plugins root, pruning the trees that never hold one."""
    found = []
    for dirpath, dirs, files in os.walk(plugins_root):
        dirs[:] = [d for d in dirs if d not in _PRUNE]
        if "hooks.json" in files:
            found.append(os.path.join(dirpath, "hooks.json"))
    return sorted(found)


def _matches(path: str, name: str, marketplace: str) -> bool:
    """Is `path` inside the plugin `name` from `marketplace`?

    Matched on PATH COMPONENTS, not substrings, and not on a known directory layout. The two
    layouts observed on one machine already differ - `plugins/cache/<market>/<name>/<version>/`
    and `plugins/marketplaces/<market>/plugins/<name>/` - so encoding either would be a roster
    that breaks on the third. A component test survives both, and survives a version directory
    appearing or disappearing. Substring matching is what would go wrong: plugin `hookify` would
    otherwise match a path containing `hookify-extras`.
    """
    parts = {p.lower() for p in path.replace("\\", "/").split("/")}
    if name.lower() not in parts:
        return False
    return not marketplace or marketplace.lower() in parts


def plugin_layers(home: str, settings_data) -> tuple:
    """(layers, report) for the ENABLED plugins under `home`.

    `home` is the `.claude` directory, parameterised so the selftest can plant a whole fake one -
    a check that could only run against the real machine would pass on any machine where nothing
    happens to be wired, which is how a layer guard silently becomes decorative.
    """
    keys, malformed = enabled_plugin_keys(settings_data)
    plugins_root = os.path.join(home, "plugins")
    on_disk = _hooks_json_files(plugins_root)

    layers, unresolved, silent, ambiguous = [], [], [], []
    for key in keys:
        name, _sep, marketplace = key.partition("@")
        hits = [p for p in on_disk if _matches(p, name, marketplace)]
        if not hits:
            # An enabled plugin with no hooks.json is NORMAL (most plugins ship none). It is
            # reported at the debug level only - see `report` - never as a problem, or the guard
            # cries wolf on every plugin that simply has no hooks.
            unresolved.append(key)
            continue
        if len(hits) > 1:
            # [P14 meta-review 2026-08-06] ONE plugin, SEVERAL copies on disk - it exists in both
            # the cache and the marketplace tree. Merging all of them counts the same hook once
            # per copy and reports a correct config as a DUPLICATE: the precise false-alarm mode
            # this module was written to avoid, reproduced inside it. Found by probing rather
            # than by reading; no fixture covered it.
            #
            # Claude Code loads ONE of them, and which one is not knowable from here, so take a
            # deterministic single copy and REPORT the ambiguity rather than guessing silently.
            # Reporting is what keeps this from being the fail-open it replaces.
            ambiguous.append("%s resolves to %d copies on disk; using %s"
                             % (key, len(hits), os.path.relpath(hits[0], home)))
        if hits[0] not in layers:
            layers.append(hits[0])

    # A file that parses but declares nothing is REPORTED. Silent zero-contribution is exactly
    # how a layer that was added stops being a layer without anyone noticing.
    for p in layers:
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as e:
            silent.append("%s: unreadable (%s)" % (p, e))
            continue
        if not isinstance(data, dict) or not (data.get("hooks") or {}):
            silent.append("%s: declares no 'hooks' object" % (p,))

    report = {
        "enabled": keys,
        "malformed": malformed,
        "on_disk": on_disk,
        "layers": layers,
        "no_hooks_file": unresolved,
        "declares_nothing": silent,
        "ambiguous": ambiguous,
    }
    return layers, report


def report_line(report: dict) -> str:
    """The DENOMINATOR, in one line. Never 'plugins OK' - always the counts it rests on."""
    return ("  [plugin-layers] %d enabled plugin(s), %d hooks.json on disk, %d merged as a layer"
            % (len(report["enabled"]), len(report["on_disk"]), len(report["layers"])))


def _plugin_layer_files(user_settings: str) -> list:
    """hooks.json of every ENABLED plugin, resolved beside `user_settings`.

    Unreadable or absent settings yields NOTHING rather than raising: this is one layer source
    among several, and a machine with no plugins at all is the common case. It cannot fail open
    in the dangerous direction, because contributing no plugin layers is exactly the behaviour
    this replaced - the change can only add visibility, never remove it.
    """
    try:
        with open(user_settings, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    layers, _report = plugin_layers(os.path.dirname(os.path.abspath(user_settings)), data)
    return layers


def settings_layers(settings_path=None, cwd=None) -> list:
    """Every file Claude Code merges hooks from, most-global first.

    Lives here rather than in `duplicate_registration_check` because "which files are layers" is
    this module's whole subject, and because that file crossed the 800-line rule the moment
    plugins were added to it - the first live violation in the repo (835). Moved rather than
    logged: N3's complaint is precisely that the rule re-breaks silently.

    Reading only ~/.claude/settings.json hid the commonest real double-wiring: the same hook in
    the user file AND in the project's .claude/settings.json. Both fire on every event, and the
    check printed nothing.
    """
    base = cwd or os.getcwd()
    user = settings_path or SETTINGS
    out = [user]
    if not settings_path:
        out.append(os.path.join(os.path.expanduser("~"), ".claude", "settings.local.json"))
    out.append(os.path.join(base, ".claude", "settings.json"))
    out.append(os.path.join(base, ".claude", "settings.local.json"))
    # [P14 B3-P] ...and every ENABLED plugin, which is a layer Claude Code merges and this
    # function did not read at all. The `.claude` home is taken as the user settings file's own
    # directory rather than expanduser("~"), so a test plants a settings.json with
    # `enabledPlugins` beside a plugins/ tree and exercises THIS code path instead of a mock.
    out.extend(_plugin_layer_files(user))
    seen, uniq = set(), []
    for p in out:
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def selftest() -> int:
    """PLANTED fixtures. The negative controls are the load-bearing ones here: this module exists
    because the obvious implementation reports DISABLED plugins as live wirings."""
    import tempfile
    fails = []

    def plant(root, rel, payload):
        p = os.path.join(root, *rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return p

    wired = {"hooks": {"Stop": [{"matcher": "*", "hooks": [{"command": "x.py"}]}]}}

    with tempfile.TemporaryDirectory() as home:
        # one ENABLED plugin, in the cache layout WITH a version directory
        on = plant(home, ("plugins", "cache", "mkt", "alpha", "1.2.3", "hooks", "hooks.json"), wired)
        # one DISABLED plugin, in the OTHER layout - the false-alarm case that motivated this
        off = plant(home, ("plugins", "marketplaces", "mkt", "plugins", "beta", "hooks",
                           "hooks.json"), wired)
        # ONE enabled plugin present in BOTH layouts: must merge ONCE, and say so.
        plant(home, ("plugins", "marketplaces", "mkt", "plugins", "alpha", "hooks",
                     "hooks.json"), wired)
        # an enabled plugin whose file declares nothing (reference/doc schema)
        ref = plant(home, ("plugins", "cache", "mkt", "gamma", "hooks", "hooks.json"),
                    {"description": "reference only", "events": [{"event": "Stop"}]})
        settings = {"enabledPlugins": {"alpha@mkt": True, "beta@mkt": False, "gamma@mkt": True,
                                       "delta@mkt": "yes"}}

        layers, rep = plugin_layers(home, settings)

        if on not in layers:
            fails.append("an ENABLED plugin's hooks.json was not merged as a layer - the whole "
                         "point: %r" % (layers,))
        if off in layers:
            fails.append("a DISABLED plugin's hooks.json was merged. Its hooks never fire, so "
                         "every one of them would be reported as a duplicate against a correct "
                         "config - B3-FP, which is how a guard gets switched off")
        if len(rep["on_disk"]) != 4:
            fails.append("the on-disk denominator is %d, expected 4 - a guard that cannot say "
                         "how many it looked at cannot be audited" % (len(rep["on_disk"]),))
        if ref not in layers or not rep["declares_nothing"]:
            fails.append("an enabled plugin whose file declares no hooks was not REPORTED; a "
                         "layer that silently contributes zero looks identical to one nobody "
                         "looked for: %r" % (rep["declares_nothing"],))
        # ONE plugin, TWO copies on disk: exactly one layer, and the ambiguity REPORTED. Merging
        # both counts the same hook twice and reports a correct config as a duplicate - the
        # false-alarm mode this whole module exists to avoid, reproduced inside it.
        alpha_layers = [p for p in layers if "alpha" in p.replace("\\", "/").split("/")]
        if len(alpha_layers) != 1:
            fails.append("an enabled plugin present in BOTH the cache and marketplace layouts "
                         "merged %d layers, expected 1. Each extra copy re-counts the same hook "
                         "and reports a correct config as a DUPLICATE" % (len(alpha_layers),))
        if not rep["ambiguous"]:
            fails.append("a plugin resolving to several on-disk copies was resolved SILENTLY. "
                         "Which copy Claude Code loads is not knowable here, so picking one "
                         "without saying so is the fail-open this module replaced")
        if not rep["malformed"]:
            fails.append("a non-boolean enabledPlugins value was accepted silently; guessing "
                         "either way is how a wiring gets invented or lost")
        if "delta@mkt" in rep["enabled"]:
            fails.append("a non-boolean enabledPlugins value was treated as ENABLED, which "
                         "invents wirings on a correct config")

    # A plugins root that does not exist at all must yield nothing and must not raise: most
    # machines have no plugins, and a crash here would take the whole duplicate audit down.
    with tempfile.TemporaryDirectory() as empty:
        layers, rep = plugin_layers(empty, {"enabledPlugins": {"a@b": True}})
        if layers:
            fails.append("invented %d layer(s) from an empty home" % (len(layers),))
        if rep["no_hooks_file"] != ["a@b"]:
            fails.append("an enabled plugin with no hooks.json was not accounted for: %r"
                         % (rep["no_hooks_file"],))

    # Component matching, not substring: `alpha` must not match `alpha-extras`.
    if _matches("/h/plugins/cache/mkt/alpha-extras/hooks/hooks.json", "alpha", "mkt"):
        fails.append("_matches() matched a SUBSTRING, so plugin 'alpha' would claim "
                     "'alpha-extras' and merge a layer that belongs to another plugin")

    for f in fails:
        print("SELFTEST FAIL:", f)
    print("SELFTEST OK" if not fails else "SELFTEST FAILED")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else 0)
