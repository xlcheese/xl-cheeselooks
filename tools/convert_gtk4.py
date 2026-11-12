#!/usr/bin/env python3
"""One-time converter: turn Linux Mint's Mint-Y GTK 4 gtk.css into a template.

    python3 tools/convert_gtk4.py MINT-Y/gtk-4.0/gtk.css templates/gtk-4.0/base.css.tmpl

Uses the GTK 3 converter's rules (tools/convert_gtk3.py) with Mint-Y GTK 4's
reference colours: background #F8F8F9, text #303030, accent Mint green
#35A854. Differences from GTK 3:
- the accent's lighter and darker greens become lighter()/darker() of the
  accent, so hover and pressed shades follow your accent
- Mint-Y's greys are slightly blue (#C8C8CE, #ADADB5); they count as greys
- image-based checks, radios and switches are removed (Mint-Y's are green);
  templates/gtk-4.0/xl.css.tmpl redraws them

Like the GTK 3 template, base.css.tmpl may get hand edits later; check
`git log -p` before re-running this over it.
"""

from __future__ import annotations

import colorsys
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_gtk3 as g3  # noqa: E402

g3.REF_BG = 248                 # #F8F8F9
g3.REF_TEXT = 48                # #303030
g3.ACCENT = (53, 168, 84)       # #35A854
g3.SELECT = (-1, -1, -1)        # Mint-Y GTK 4 has no separate selection colour
GREY_TOLERANCE = 9              # max - min channel spread still counted as grey
_ACCENT_HLS = colorsys.rgb_to_hls(*(c / 255 for c in g3.ACCENT))
_base_convert = g3.convert


def convert(lit: str, prop: str, selector: str) -> str:
    r, g, b, a = g3.parse(lit)
    if a > 0.001 and "osd" not in selector.lower():
        spread = max(r, g, b) - min(r, g, b)
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        ah, al, _ = _ACCENT_HLS
        hue_gap = min(abs(h - ah), 1 - abs(h - ah)) * 360
        if (r, g, b) != g3.ACCENT and s > 0.25 and hue_gap <= 10:
            # shades of the Mint green accent -> shades of your accent
            if l >= al:
                g3.bump("accent shade -> lighter(accent)")
                return g3.wrap(f"lighter(accent, {g3.fmt((l - al) / (1 - al))})", a)
            g3.bump("accent shade -> darker(accent)")
            return g3.wrap(f"darker(accent, {g3.fmt((al - l) / al)})", a)
        if 6 < spread <= GREY_TOLERANCE:
            # bluish Mint-Y grey: treat as the plain grey of the same brightness
            v = round((r + g + b) / 3)
            return _base_convert(f"rgba({v}, {v}, {v}, {a})", prop, selector)
    return _base_convert(lit, prop, selector)


g3.convert = convert


def main() -> int:
    src, dest = Path(sys.argv[1]), Path(sys.argv[2])
    result = g3.convert_css(src.read_text(encoding="utf-8"))
    header = ("/* xl-Cheeselooks: GTK 4 base layer.\n"
              " * Derived from Linux Mint's Mint-Y GTK 4 theme (GPL-3.0+), converted by\n"
              " * tools/convert_gtk4.py. Colours and radii are template tokens.\n"
              " * The hand-written layer in xl.css.tmpl is applied on top. */\n\n")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(header + result, encoding="utf-8")
    for k, v in sorted(g3.stats.items(), key=lambda kv: -kv[1]):
        print(f"{v:5}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
