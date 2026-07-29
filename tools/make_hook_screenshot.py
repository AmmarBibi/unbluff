#!/usr/bin/env python3
"""Render real hook output to a terminal-style PNG for the README.

The other hook images in docs/ were hand-captured, which means they cannot be refreshed
when a message changes and nothing detects that they have gone stale. This renders from
text you supply (normally captured from an actual hook run), so a doc image is a build
artifact rather than a screenshot someone has to remember to retake.

    python tools/make_hook_screenshot.py --out docs/foo.png --text-file out.txt
    some_hook.py | python tools/make_hook_screenshot.py --out docs/foo.png

Requires Pillow. Exits 1 with a clear message if it is unavailable.
"""
from __future__ import annotations

import argparse
import os
import sys

BG = (13, 17, 23)          # GitHub dark canvas
FG = (201, 209, 217)
DIM = (110, 118, 129)
ACCENT = (63, 185, 80)     # green: OK / success
WARN = (210, 153, 34)      # amber: a finding
PAD = 18
LINE_H = 22
FONT_SIZE = 15
CHAR_W_FALLBACK = 8

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\CascadiaMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


def _load_font():
    from PIL import ImageFont
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, FONT_SIZE)
            except OSError:
                continue
    return ImageFont.load_default()


def colour_for(line: str):
    stripped = line.strip()
    if stripped.startswith("$"):
        return DIM
    low = stripped.lower()
    if " ok" in low or low.endswith("ok") or "passed" in low or "resolved" in low:
        return ACCENT
    if any(w in low for w in ("problem", "registered", "no test gate", "warning", "fail")):
        return WARN
    return FG


def render(text: str, out_path: str) -> int:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow is required: pip install Pillow", file=sys.stderr)
        return 1
    font = _load_font()
    lines = text.rstrip("\n").split("\n") or [""]
    try:
        char_w = font.getbbox("M")[2] - font.getbbox("M")[0]
    except Exception:
        char_w = CHAR_W_FALLBACK
    width = PAD * 2 + max(char_w * max(len(l) for l in lines), 320)
    height = PAD * 2 + LINE_H * len(lines)
    img = Image.new("RGB", (int(width), int(height)), BG)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((PAD, PAD + i * LINE_H), line, font=font, fill=colour_for(line))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    img.save(out_path)
    print(f"wrote {out_path} ({img.width}x{img.height})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--text-file", help="read the text from a file instead of stdin")
    args = ap.parse_args()
    text = (open(args.text_file, encoding="utf-8").read() if args.text_file
            else sys.stdin.read())
    if not text.strip():
        print("no text supplied", file=sys.stderr)
        return 1
    return render(text, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
