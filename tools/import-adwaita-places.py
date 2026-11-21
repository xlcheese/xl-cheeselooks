#!/usr/bin/env python3
"""Make the Adwaita folder style from GNOME's folder drawings, sharp at small sizes.

Retired (21 Nov, xl_cheese: too like Mint-Y and Yaru); kept to bring it back:
put its entry back in cheeselooks/icons.py STYLES and settings, then run this.

    python3 tools/import-adwaita-places.py ADWAITA_ICON_THEME_CHECKOUT
      then: python3 tools/compose-missing-places.py

GNOME draws each folder once (Adwaita/scalable/places/<name>.svg, 128px in
github.com/GNOME/adwaita-icon-theme) and lets it be shrunk. Shrunk to 24px,
its edges fall between pixels and its outline pictures go thinner than a
pixel: soft (GNOME's own apps use one-colour symbolic icons at that size).
So, per size:

  64, 96, 128px   GNOME's drawing as it is (its edges land on whole pixels)
  32, 48px        the drawing stretched a little (under 3%) so the folder's
                  outer edges land on whole pixels; GNOME's own pictures
  16, 22, 24px    the same, with Mint-Y's picture for that icon at its own
                  size (drawn for it, on whole pixels) instead of GNOME's,
                  moved by whole pixels onto the front

Every Adwaita folder is the same four layers, marked for the Tool's colours:

    #438de6  the back and tab (the first shape)       -> #438d0e (your second color)
    #a4caee  the front                                 -> #a4ca0e (your folder color)
    #62a0ea  the front's lower edge (a gradient)       -> #62a00e (the front, darker)
    #afd4ff, #c0d5ea  the edge's shine at its ends     -> #afd40f (the front, lighter)
    #438de6  the picture (any shape after the front)   -> #438d1e (emblem)

GNOME's folders: CC BY-SA 3.0 (the GNOME Project), credited with Mint-Y's
pictures in data/icons/adwaita/COPYING. Its desktop, remote, projects,
network and trash icons aren't folders of this kind and aren't used;
compose-missing-places.py makes the rest of Mint-Y's set.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icons" / "adwaita" / "places"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
NAMES = ("folder", "user-home", "folder-documents", "folder-download", "folder-music",
         "folder-pictures", "folder-publicshare", "folder-templates", "folder-videos",
         "folder-drag-accept", "user-bookmarks", "user-desktop")
WHOLE = (64, 96, 128)                     # 128 / size is whole: as drawn
SNAPPED = (32, 48)                        # snapped, GNOME's pictures
SMALL = (16, 22, 24)                      # snapped, Mint-Y's pictures
# the folder in GNOME's 128px drawing: the back's left, top, right; the front's top and bottom
LEFT, TOP, RIGHT, FRONT_TOP, BOTTOM = 12.0, 12.0, 116.0, 32.0, 118.03

spec = importlib.util.spec_from_file_location("compose", ROOT / "tools" / "compose-missing-places.py")
compose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compose)


def mark(text: str) -> str:
    """GNOME's colours to the Tool's placeholders (see the table above)."""
    text = re.sub("#afd4ff|#c0d5ea", "#afd40f", text, flags=re.I)
    text = re.sub("#62a0ea", "#62a00e", text, flags=re.I)
    text = re.sub("#a4caee", "#a4ca0e", text, flags=re.I)
    first = True

    def back_or_picture(_m):
        nonlocal first
        out = "#438d0e" if first else "#438d1e"
        first = False
        return out
    return re.sub("#438de6", back_or_picture, text, flags=re.I)


def snap(size: int) -> tuple[float, float, float, float]:
    """Scale and offset (sx, sy, tx, ty) putting the folder's outer edges on
    whole pixels, as close as can be to GNOME's own size."""
    k = size / 128
    best = None
    for left in (round(LEFT * k) + d for d in (-1, 0, 1)):
        for right in (round(RIGHT * k) + d for d in (-1, 0, 1)):
            for top in (round(TOP * k) + d for d in (-1, 0, 1)):
                for bottom in (round(BOTTOM * k) + d for d in (-1, 0, 1)):
                    if not (0 <= left < right <= size and 0 <= top < bottom <= size):
                        continue
                    sx, sy = (right - left) / (RIGHT - LEFT), (bottom - top) / (BOTTOM - TOP)
                    # stay near GNOME's size and shape, and keep the front's top crisp too
                    front = top + (FRONT_TOP - TOP) * sy
                    cost = abs(sx / k - 1) + abs(sy / k - 1) + abs(sx - sy) / k + 0.02 * abs(front - round(front))
                    if best is None or cost < best[0]:
                        best = (cost, sx, sy, left - LEFT * sx, top - TOP * sy)
    return best[1:]


def build(text: str, size: int, picture: bool) -> str:
    root = ET.fromstring(text)
    defs = [c for c in root if c.tag.endswith(("linearGradient", "radialGradient", "defs"))]
    shapes = [c for c in root if c not in defs]
    if not picture:
        shapes = shapes[:3]                       # back, edge, front: no picture
    out = ET.Element(f"{{{SVG}}}svg", {"width": str(size), "height": str(size),
                                     "viewBox": f"0 0 {size} {size}", "version": "1.1"})
    for d in defs:
        out.append(d)
    if size in WHOLE:
        g = ET.SubElement(out, f"{{{SVG}}}g", {"transform": f"scale({size / 128:g})"})
    else:
        sx, sy, tx, ty = snap(size)
        g = ET.SubElement(out, f"{{{SVG}}}g", {"transform": f"matrix({sx:.6f} 0 0 {sy:.6f} {tx:.6f} {ty:.6f})"})
    for s in shapes:
        g.append(s)
    return ET.tostring(out, encoding="unicode") + "\n"


def mint_picture(svg_text: str, name: str, size: int) -> str:
    """Mint-Y's picture for `name` at `size`, at its own scale, moved by whole
    pixels so it's centred on the front."""
    found = compose.mint_picture(name, size)
    if found is None:
        return svg_text
    pic, (x0, y0, x1, y1) = found
    mvb = compose.viewbox(pic, size)
    sx, sy, tx, ty = snap(size)
    front_top, bottom = ty + FRONT_TOP * sy, ty + BOTTOM * sy
    cx, cy = tx + (LEFT + RIGHT) / 2 * sx, (front_top + bottom) / 2
    dx = round(cx - ((x0 + x1) / 2 - mvb[0]))
    dy = round(cy - ((y0 + y1) / 2 - mvb[1]))
    inner = ET.tostring(pic, encoding="unicode")
    inner = re.sub(icons_emblem_mint(), "#438d1e", inner, flags=re.I)
    inner_root = ET.fromstring(inner)
    nested = ET.Element(f"{{{SVG}}}svg", {"x": str(dx), "y": str(dy), "width": str(size), "height": str(size),
                                        "viewBox": " ".join(f"{v:g}" for v in mvb), "overflow": "visible"})
    for c in list(inner_root):
        nested.append(c)
    root = ET.fromstring(svg_text)
    root.append(nested)
    return ET.tostring(root, encoding="unicode") + "\n"


def icons_emblem_mint() -> str:
    return "#" + compose.icons.STYLES["mint-y"]["source"]["emblem"]


def main() -> int:
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    places = Path(sys.argv[1]) / "Adwaita" / "scalable" / "places"
    count = 0
    for name in NAMES:
        text = mark((places / f"{name}.svg").read_text(encoding="utf-8"))
        for size in WHOLE + SNAPPED + SMALL:
            svg = build(text, size, picture=size not in SMALL)
            if size in SMALL:
                svg = mint_picture(svg, name, size)
            f = OUT / str(size) / f"{name}.svg"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(svg, encoding="utf-8")
            count += 1
    # the small sizes of the names GNOME doesn't draw: its plain folder with Mint-Y's picture
    mint = sorted(f.stem for f in compose.MINT.glob("48/*.svg"))
    plain = mark((places / "folder.svg").read_text(encoding="utf-8"))
    for name in mint:
        if name in NAMES or name in compose.SKIP:
            continue
        for size in SMALL:
            f = OUT / str(size) / f"{name}.svg"
            f.write_text(mint_picture(build(plain, size, picture=False), name, size), encoding="utf-8")
            count += 1
    print(f"{count} icons written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
