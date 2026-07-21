#!/usr/bin/env python3
"""Regenerate the unbluff README demo assets (local, deterministic).

These are accurate reconstructions, NOT screencasts: the hook nudge text and output are the
real thing. Writes 3 GIFs + 5 PNG "terminal cards" into ../docs/.

Dev-only tool - needs Pillow (`pip install -r requirements-dev.txt`). The hooks themselves
have zero dependencies. Run from anywhere: `python scripts/make_demos.py`.
"""

import os
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # scripts/ -> repo root
DOCS = os.path.join(REPO, "docs")


def _find_font():
    """A monospace TTF from common locations across Windows / Linux / macOS."""
    for path in (
        r"C:\Windows\Fonts\consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/Library/Fonts/Consolas.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
    ):
        if os.path.exists(path):
            return path
    raise SystemExit("make_demos: no monospace TTF found; add one to _find_font().")


FONT_PATH = _find_font()
FONT_BOLD = FONT_PATH
FS = 19
LINE_H = 28
PAD = 18
TITLE_H = 36

BG = (13, 17, 23)
TITLEBAR = (28, 33, 40)
DEFAULT = (201, 209, 217)
GREEN = (126, 231, 135)
AMBER = (240, 180, 41)
BLUE = (121, 192, 255)
OKGREEN = (86, 211, 100)
RED = (248, 81, 73)
DIM = (139, 148, 158)
CURSOR = (201, 209, 217)

font = ImageFont.truetype(FONT_PATH, FS)
font_b = ImageFont.truetype(FONT_BOLD, FS)
CHAR_W = font.getlength("M")

# timing (ms)
TYPE_MS = 30
COMMIT_HOLD_MS = 130
INSTANT_MS = 320
BLANK_MS = 80
END_MS = 2200
CHUNK = 3


def _canvas(width, n_lines):
    return width, TITLE_H + n_lines * LINE_H + 2 * PAD


def _render(width, height, committed, active=None):
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, width, TITLE_H], fill=TITLEBAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 16 + i * 20
        d.ellipse([cx, TITLE_H // 2 - 6, cx + 12, TITLE_H // 2 + 6], fill=c)
    label = "unbluff - Claude Code"
    d.text((width / 2 - font.getlength(label) / 2, TITLE_H / 2 - FS / 2), label, font=font, fill=DIM)
    y = TITLE_H + PAD
    for text, color in committed:
        d.text((PAD, y), text, font=font, fill=color)
        y += LINE_H
    if active is not None:
        text, color = active
        d.text((PAD, y), text, font=font, fill=color)
        cx = PAD + font.getlength(text)
        d.rectangle([cx + 1, y + 2, cx + 1 + CHAR_W * 0.6, y + FS + 2], fill=CURSOR)
    return img


def build(script, out_name):
    # count display lines to size the canvas; measure width
    n_lines = sum(1 for s in script if s[0] != "hold")
    max_chars = max((len(s[1]) for s in script if s[0] not in ("hold", "blank")), default=40)
    width = int(max_chars * CHAR_W + 2 * PAD + CHAR_W * 2)
    width, height = _canvas(width, n_lines)

    frames, durs = [], []
    committed = []

    def emit(img, ms):
        frames.append(img)
        durs.append(ms)

    color_map = {"u": GREEN, "a": DEFAULT, "nudge": AMBER, "cmd": BLUE,
                 "out": GREEN, "ok": OKGREEN, "box": BLUE, "dim": DIM, "blank": DEFAULT,
                 "red": RED}

    for step in script:
        kind = step[0]
        if kind == "hold":
            emit(_render(width, height, committed), step[1])
            continue
        if kind == "blank":
            committed.append(("", DEFAULT))
            emit(_render(width, height, committed), BLANK_MS)
            continue
        text = step[1]
        color = color_map[kind]
        typed = kind in ("u", "a", "nudge", "cmd")
        if typed:
            i = 1
            while i <= len(text):
                emit(_render(width, height, committed, active=(text[:i], color)), TYPE_MS)
                i += CHUNK
            emit(_render(width, height, committed, active=(text, color)), COMMIT_HOLD_MS)
            committed.append((text, color))
        else:
            committed.append((text, color))
            emit(_render(width, height, committed), INSTANT_MS)

    # hold the final frame, then loop
    emit(_render(width, height, committed), END_MS)

    # shared palette from the fullest (last) frame -> small, flicker-free GIF
    master = frames[-1].convert("P", palette=Image.ADAPTIVE, colors=64)
    pframes = [f.quantize(palette=master, dither=Image.NONE) for f in frames]
    os.makedirs(DOCS, exist_ok=True)
    out = os.path.join(DOCS, out_name)
    pframes[0].save(out, save_all=True, append_images=pframes[1:], duration=durs,
                    loop=0, optimize=True, disposal=2)
    kb = os.path.getsize(out) / 1024
    print(f"{out_name}: {width}x{height}, {len(frames)} frames, {kb:.0f} KB")


DEMO = [
    ("u", "> the add() in calc.py returns a-b; fix it and confirm"),
    ("blank",),
    ("a", "Fixed calc.py - it works now."),
    ("blank",),
    ("nudge", "[show-your-proof] The last reply claims success ('it works') but"),
    ("nudge", "this turn ran no tools. Show verification (run the test/build/"),
    ("nudge", "command) or soften the claim to what was actually verified."),
    ("blank",),
    ("a", "You're right - let me actually run it."),
    ("cmd", "$ pytest -q"),
    ("out", "1 passed in 0.03s"),
    ("ok", "Confirmed - the test passes."),
    ("hold", 400),
]

RATE = [
    ("u", "You:  fix teh login thing thats broken"),
    ("blank",),
    ("nudge", "5/10 - clear intent but vague: which login, what is broken?"),
    ("blank",),
    ("box", "+-----------------------------------------------------------+"),
    ("box", "| Fix the login bug: valid creds get a 401 on first submit  |"),
    ("box", "| but succeed on retry. Likely a token race in src/auth/.   |"),
    ("box", "| Reproduce, fix, and add a regression test.                |"),
    ("box", "+-----------------------------------------------------------+"),
    ("blank",),
    ("dim", "[proceeds on the sharpened prompt - no extra model call]"),
    ("hold", 400),
]

def still(lines, out_name):
    """Render a single static 'terminal card' PNG from [(text, color), ...]."""
    n = len(lines)
    max_chars = max((len(t) for t, _ in lines), default=40)
    width = int(max_chars * CHAR_W + 2 * PAD + CHAR_W)
    height = TITLE_H + n * LINE_H + 2 * PAD
    img = _render(width, height, lines)
    os.makedirs(DOCS, exist_ok=True)
    out = os.path.join(DOCS, out_name)
    img.save(out, optimize=True)
    print(f"{out_name}: {width}x{height}, {os.path.getsize(out) / 1024:.0f} KB (png)")


FASTTEST = [
    ("u", "> speed up the parser in tokenizer.py"),
    ("blank",),
    ("a", "Refactored tokenizer.py - should be faster now."),
    ("blank",),
    ("nudge", "[fast-test] FAILING at stop - fix before finishing (cmd: pytest -x -q):"),
    ("red", "  FAILED tests/test_tokenizer.py::test_roundtrip"),
    ("blank",),
    ("a", "Good catch - the refactor broke roundtripping. Fixing."),
    ("cmd", "$ pytest -x -q"),
    ("out", "5 passed in 0.11s"),
    ("hold", 400),
]

META_AUDIT = [
    ("[meta-audit] parked/unpushed state at stop:", AMBER),
    ("- PLAN.md:42: TODO: wire the retry backoff", DEFAULT),
    ("- 2 commit(s) unpushed (push only on user say-so - surface, not push)", DEFAULT),
    ("Schedule each named item into the plan order, or tag the line with its decision (SCHEDULED/DECIDED/BACKLOG/...).", DIM),
]

MEMORY_HYGIENE = [
    ("[memory-hygiene] memory rot for this project:", AMBER),
    ("  - MEMORY.md:7: commit hash in index: fixed in abc1234 on main", DEFAULT),
    ("  - notes.md:12: NEXT ORDER: wire the API -> ship", DEFAULT),
    ("Move evolving state to the project plan/docs; memory keeps pointers + durable facts only.", DIM),
]

HOOK_HEALTH = [
    ("[hook-health] OK - 3 hook commands verified, weekly selftests 6/6 OK", OKGREEN),
]

STOP_DISPATCHER = [
    ("$ tail -2 ~/.claude/hooks/state/fire_ledger.jsonl", BLUE),
    ('{"ts":"2026-07-13T16:58:04","cwd":"~/proj","results":{"proof":2,"audit":0,"memory":0,"test":0},"fired":["proof"]}', DIM),
    ('{"ts":"2026-07-13T17:12:39","cwd":"~/proj","results":{"proof":0,"audit":2,"memory":0,"test":2},"fired":["audit","test"]}', DIM),
    ("", DEFAULT),
    ("One process per turn-end runs all four Stop hooks; the ledger shows what fired.", DEFAULT),
]

META_REVIEW = [
    ("[meta-review] hardening pass - example report (6 checks, findings + action):", AMBER),
    ("  1 Parked work    2 items scheduled into the plan order", DEFAULT),
    ("  2 Durability     1 instance-fix -> added a regression test", DEFAULT),
    ("  3 Optimization   calc.py at 812 lines -> split scheduled", DEFAULT),
    ("  4 Missing/wrong  an eval not run -> queued", DEFAULT),
    ("  5 Improvements   3 logged for you to pick", DEFAULT),
    ("  6 Mechanism      hooks green; one coherent recommended-order list", DEFAULT),
]

PLAN_DEFER = [
    ("u", "> update the plan - park the low-priority refactor for now"),
    ("blank",),
    ("a", "Updated MASTER_PLAN.md -> added: | 9.2 | low-pri refactor -> park."),
    ("blank",),
    ("nudge", "[plan-defer-guard] optional-forever language in MASTER_PLAN.md:"),
    ("red", "  L92: | 9.2 | low-pri refactor -> park."),
    ("blank",),
    ("a", "Right - that reads decided but means never. Reclassifying: | 9.2 | low-pri refactor (SCHEDULED, low)."),
    ("hold", 400),
]

SOURCE_COVERAGE = [
    ("[source-coverage] plan reconciled against its source docs:", AMBER),
    ("  BUILT        128 items   (module + test named)", DEFAULT),
    ("  SCHEDULED     14 items   (real plan rows)", DEFAULT),
    ("  EXCLUSION      3 items   (justified, in the ledger)", DEFAULT),
    ("  GAP          ~40 items   NOT in the plan - e.g. a whole refining-method family", AMBER),
    ("A grep can't find what the plan never names; scheduled each gap, refreshed the ledger.", DIM),
]

NUMBERS_MATCH = [
    ("u", "> write up the results in REPORT.md from results/*.csv"),
    ("blank",),
    ("a", "Wrote REPORT.md - overshoot 94.8%, settling 8.65 s, peak stress 512.4 MPa."),
    ("blank",),
    ("nudge", "[numbers-match] 1 cited number(s) in REPORT.md have no match in the"),
    ("nudge", "source data (results):"),
    ("red", "  REPORT.md:12: 512.4 MPa   (peak stress 512.4 MPa is the worst case)"),
    ("nudge", "Verify against the source-of-truth data or correct the prose."),
    ("blank",),
    ("a", "Right - 512.4 is in no sweep row; the CSV peak is 487.6 MPa. Fixing."),
    ("hold", 400),
]

CONSISTENCY_AUDIT = [
    ("[consistency-audit] deliverable vs source data - candidate drift:", AMBER),
    ("  [A] number, no source match   3   e.g. 512.4 MPa (nearest 487.6)", AMBER),
    ("  [B] figure never referenced   1   Figure 7 embedded, never cited", DEFAULT),
    ("  [C] dangling cross-reference  1   'Figure 4' has no such caption", DEFAULT),
    ("  [D] claim to verify           2   'lowest overshoot' vs the sweep", DEFAULT),
    ("  [E] unfilled placeholder      2   [TABLE], [TODO] left in the prose", AMBER),
    ("  [F] table promised, none rendered  'Table 3' cited but no table", DEFAULT),
    ("The hook flags a number with no source; the skill judges drift vs derived vs definitional.", DIM),
]

if __name__ == "__main__":
    build(DEMO, "demo.gif")
    build(PLAN_DEFER, "plan-defer-guard.gif")
    build(RATE, "rate-prompt.gif")
    build(FASTTEST, "fast-test.gif")
    build(NUMBERS_MATCH, "numbers-match.gif")
    still(META_AUDIT, "meta-audit.png")
    still(SOURCE_COVERAGE, "source-coverage.png")
    still(MEMORY_HYGIENE, "memory-hygiene.png")
    still(HOOK_HEALTH, "hook-health.png")
    still(STOP_DISPATCHER, "stop-dispatcher.png")
    still(META_REVIEW, "meta-review.png")
    still(CONSISTENCY_AUDIT, "consistency-audit.png")
    print("done")
