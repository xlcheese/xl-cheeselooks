#!/usr/bin/env python3
"""Draw the xl-Cheeselooks icon: a static swirly rainbow (one SVG master).

    python3 tools/make_icon.py

Writes data/icons/xl-cheeselooks.svg. The PNGs (app icon, and the theme
thumbnails that Mint's Themes settings shows for every part of the theme) are
rendered from it with ImageMagick by tools/make_icon.sh. Static on purpose: the
brand, not a preview of the current colours (docs/design-spec.md).

The swirl is an Archimedean spiral drawn as many short overlapping strokes
with round caps: the hue runs once around the colour wheel from the centre
out, and the stroke thickens outward, so it reads as one smooth ribbon.
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path

SIZE = 256
TURNS = 2.15            # how many times the ribbon wraps
STEPS = 420             # strokes along the ribbon (more = smoother)
R_START, R_END = 10.0, 108.0
W_START, W_END = 7.0, 30.0


def hex_color(h: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h % 1.0, 0.56, 0.86)
    return f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"


def main() -> None:
    c = SIZE / 2
    total = TURNS * 2 * math.pi
    pts = []
    for i in range(STEPS + 1):
        t = i / STEPS
        a = t * total - math.pi / 2           # start pointing up
        r = R_START + (R_END - R_START) * t
        pts.append((c + r * math.cos(a), c + r * math.sin(a), t))
    strokes = []
    for (x1, y1, t), (x2, y2, _) in zip(pts, pts[1:]):
        w = W_START + (W_END - W_START) * t
        strokes.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                       f'stroke="{hex_color(t * 0.92)}" stroke-width="{w:.2f}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}" '
           f'viewBox="0 0 {SIZE} {SIZE}">\n'
           f'<title>xl-Cheeselooks</title>\n'
           f'<g fill="none" stroke-linecap="round">\n' + "\n".join(strokes) + "\n</g>\n</svg>\n")
    out = Path(__file__).resolve().parent.parent / "data" / "icons" / "xl-cheeselooks.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
