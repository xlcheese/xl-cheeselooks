#!/usr/bin/env python3
"""Draw the xl-Cheeselooks icon: a silky swirl (one SVG master).

    python3 tools/make_icon.py

Writes data/icons/xl-cheeselooks.svg. The PNGs (app icon, and the theme
thumbnails that Mint's Themes settings shows) are rendered from it by
tools/make_icon.sh. Static on purpose: the brand, not a preview of the
current colours (docs/design-spec.md).

About 520 fine strands over a soft blurred wash, winding into an eye at the
lower right with a broad wave further out. Each strand's colour comes from a
loop of hues by its angle round the eye (orange, peach, coral, crimson,
violet, blue, teal, green, lime...), so colours blend instead of banding; one
in five is darkened, and a few thin white strands give it sheen. Seeded, so
the same SVG comes out every time.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

seed = 1
random.seed(seed)
CX, CY, R = 172, 176, 330
# colour by the strand's angle round the eye: a loop of hues (orange/peach,
# blue, violet, magenta, crimson, teal) blended smoothly
STOPS = [(0.00, "#FF8A3D"), (0.10, "#FFC08A"), (0.19, "#F05A3A"), (0.27, "#B5174F"), (0.36, "#7B1FA2"),
         (0.46, "#3F51D8"), (0.54, "#1E88E5"), (0.61, "#26A6C4"), (0.68, "#2FBF8F"), (0.74, "#7CCB5A"),
         (0.81, "#8E6CF0"), (0.90, "#C2306A"), (1.00, "#FF8A3D")]
def h2(c): return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))
def colour(f, dark=0.0, light=0.0):
    f += 0.35
    f %= 1
    for (a, ca), (b, cb) in zip(STOPS, STOPS[1:]):
        if a <= f <= b:
            t = (f - a) / (b - a); x, y = h2(ca), h2(cb)
            rgb = [x[i] + (y[i] - x[i]) * t for i in range(3)]
            rgb = [v * (1 - dark) + 255 * light * (1 - dark) - v * light * (1 - dark) * 0 for v in rgb]
            rgb = [min(255, v + (255 - v) * light) for v in rgb]
            return "#%02X%02X%02X" % tuple(int(v) for v in rgb)
def curve(phi, amp, k, r0=2.0, steps=90):
    pts = []
    for i in range(steps + 1):
        r = r0 * (R / r0) ** (i / steps)
        tw = 1.3 * math.log(R / r) + amp * math.sin(k * math.log(r + 1) + 0.4) * min(1, r / 55)
        pts.append((CX + r * math.cos(phi + tw), CY + r * math.sin(phi + tw)))
    return pts
def path(pts): return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
o = ['<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">',
     '<defs><clipPath id="c"><rect x="8" y="8" width="240" height="240" rx="52"/></clipPath>',
     '<filter id="base" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7"/></filter>',
     '<filter id="soft"><feGaussianBlur stdDeviation="0.5"/></filter>',
     f'<radialGradient id="eye" gradientUnits="userSpaceOnUse" cx="{CX}" cy="{CY}" r="46">'
     '<stop offset="0" stop-color="#14000A" stop-opacity="0.95"/><stop offset="0.4" stop-color="#3A0018" stop-opacity="0.5"/>'
     '<stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient></defs>',
     '<g clip-path="url(#c)"><rect width="256" height="256" fill="#1A0A20"/>']
# soft base: wide blurred strokes
o.append('<g filter="url(#base)">')
for i in range(48):
    phi = i / 48 * 2 * math.pi
    o.append(f'<path d="{path(curve(phi, 1.0, 2.4))}" fill="none" stroke="{colour(i / 48)}" stroke-width="22"/>')
o.append('</g><g filter="url(#soft)" stroke-linecap="round" fill="none">')
# strands: many thin ones, each a little off the others in phase and wave
for i in range(520):
    f = random.random()
    phi = f * 2 * math.pi
    amp = 1.0 + random.gauss(0, 0.06)
    dark = random.random() < 0.22
    col = colour(f + random.gauss(0, 0.012), light=0 if dark else random.uniform(0, 0.25))
    if dark:
        col = "#%02X%02X%02X" % tuple(int(v * 0.45) for v in h2(col))
    w = random.uniform(0.6, 3.2)
    o.append(f'<path d="{path(curve(phi, amp, 2.4 + random.gauss(0, 0.05)))}" stroke="{col}" '
             f'stroke-width="{w:.1f}" opacity="{random.uniform(0.45, 0.95):.2f}"/>')
# a few bright sheen strands
for i in range(40):
    f = random.random()
    o.append(f'<path d="{path(curve(f * 2 * math.pi, 1.0 + random.gauss(0, 0.05), 2.4))}" stroke="#FFFFFF" '
             f'stroke-width="{random.uniform(0.4, 1.2):.1f}" opacity="{random.uniform(0.25, 0.6):.2f}"/>')
o += ['</g><rect width="256" height="256" fill="url(#eye)"/></g></svg>']


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "icons" / "xl-cheeselooks.svg"
    out.write_text("".join(o), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
