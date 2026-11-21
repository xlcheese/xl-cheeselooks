#!/usr/bin/env python3
"""Copy Breeze's folder icons, marked for the Tool's colours, one SVG each.

    python3 tools/import-breeze-places.py BREEZE_ICONS_CHECKOUT

The same job as tools/import-mint-y-places.py, for KDE's Breeze
(github.com/KDE/breeze-icons, icons/places/<size>/). Breeze draws each folder
small and by hand, a file per size, so there's no sheet to cut: we copy the
ones we use and mark their colours. A Breeze folder is one shape in the
accent (class ColorScheme-Accent), with the back darkened by a black layer
at 33%, thin white and dark lines, and the picture in the text colour at 60%:

    the accent shape                     -> #3daee9 (front: your folder color)
    the black 33% layer (the back)       -> #3dae09, solid (back: your second color)
    the picture (ColorScheme-Text, 60%)  -> #3dae39, solid (emblem)
    the thin lines                       kept (light and dark edges)

Breeze's own colours are drawn at 32, 48, 64 and 96px; its 16 and 22px
folders are one-colour outlines, so the 32px drawing makes 16, 22 and 24px:
snapped to whole pixels, with Mint-Y's picture for each name drawn for that
size (tools/smallsize.py; shrunk, Breeze's 1px outline pictures went under a
pixel, and its edges between pixels). Names Breeze draws elsewhere are taken through its links (folder-music
is its folder-sound, folder-recent its folder-temp); its desktop is a
monitor, so its desktop folder (folder-desktop) is used, as its bookmark
and network folders for user-bookmarks and gtk-network (Mint-Y's names);
where Breeze skips a size, its next size up stands in. Saved-search has no
Breeze drawing: tools/compose-missing-places.py makes it.

Breeze's icons are LGPL 3 or later (Uri Herrera and the KDE contributors);
the licence is in data/icons/breeze/COPYING.
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icons" / "breeze" / "places"
SVG = "http://www.w3.org/2000/svg"
FRONT, BACK, EMBLEM = "#3daee9", "#3dae09", "#3dae39"
# our name: Breeze's (its desktop is a monitor; its desktop *folder* is ours)
NAMES = {"folder": "folder", "folder-documents": "folder-documents", "folder-download": "folder-download",
         "folder-music": "folder-music", "folder-open": "folder-open", "folder-pictures": "folder-pictures",
         "folder-publicshare": "folder-publicshare", "folder-recent": "folder-recent",
         "folder-templates": "folder-templates", "folder-videos": "folder-videos",
         "network-workgroup": "network-workgroup", "user-home": "user-home",
         "user-desktop": "folder-desktop", "user-bookmarks": "folder-bookmark", "gtk-network": "folder-network"}
DRAWN = (32, 48, 64, 96)
SMALL = (16, 22, 24)          # drawn from the 32px folder


def mark(svg_text: str) -> str:
    ET.register_namespace("", SVG)
    root = ET.fromstring(svg_text)
    for defs in [e for e in root if e.tag.endswith("defs")]:
        if not any(not c.tag.endswith("style") for c in defs):
            root.remove(defs)                      # only the colour scheme: not needed now
    for e in root.iter():
        if not e.tag.endswith(("path", "rect", "circle", "ellipse", "polygon", "g")):
            continue
        cls = e.get("class", "")
        # colours as style or as attributes (newer files): read both
        rules = {k: e.get(k) for k in ("fill", "fill-opacity") if e.get(k) is not None}
        rules.update(dict(r.split(":", 1) for r in (e.get("style") or "").replace(" ", "").split(";") if ":" in r))
        try:
            opacity = float(rules.get("fill-opacity", "1"))
        except ValueError:
            opacity = 1.0
        if "ColorScheme-Accent" in cls:
            rules["fill"], rules["fill-opacity"] = FRONT, "1"
        elif "fill" not in rules and abs(opacity - 0.33) < 0.005:
            rules["fill"], rules["fill-opacity"] = BACK, "1"
        elif "ColorScheme-Text" in cls and rules.get("fill") == "currentColor":
            rules["fill"], rules["fill-opacity"] = EMBLEM, "1"
        else:
            continue
        rules.pop("color", None)
        for k in ("fill", "fill-opacity"):
            e.attrib.pop(k, None)
        e.set("style", ";".join(f"{k}:{v}" for k, v in rules.items()))
        if "class" in e.attrib:
            del e.attrib["class"]
    return ET.tostring(root, encoding="unicode") + "\n"


def small_icon(text: str, name: str, size: int, box, front_top) -> str:
    """The 32px drawing on whole pixels at `size`, with Mint-Y's picture (or,
    where Mint-Y has none, Breeze's own)."""
    import smallsize
    ET.register_namespace("", SVG)
    root = ET.fromstring(text)
    sx, sy, tx, ty = smallsize.snap(box, front_top, 32, size)
    cx = tx + (box[0] + box[2]) / 2 * sx
    cy = ty + (front_top + box[3]) / 2 * sy
    pic = smallsize.mint_picture(name, size, cx, cy, EMBLEM)
    out = ET.Element(f"{{{SVG}}}svg", {"width": str(size), "height": str(size), "viewBox": f"0 0 {size} {size}"})
    g = ET.SubElement(out, f"{{{SVG}}}g", {"transform": f"matrix({sx:.6f} 0 0 {sy:.6f} {tx:.6f} {ty:.6f})"})
    for c in list(root):
        if pic is not None and EMBLEM in (c.get("style") or "").lower():
            continue                       # Breeze's picture: Mint-Y's, drawn for this size, instead
        g.append(c)
    if pic is not None:
        out.append(pic)
    return ET.tostring(out, encoding="unicode") + "\n"


def sized(svg_text: str, size: int) -> str:
    return re.sub(r"<svg ", f'<svg width="{size}" height="{size}" ', svg_text, count=1)


def main() -> int:
    places = Path(sys.argv[1]) / "icons" / "places"
    count = 0
    import smallsize
    import xml.etree.ElementTree as ET2
    # the folder in Breeze's 32px drawing: outer box, and the front's top
    box32, front32 = (1.0, 3.0, 31.0, 29.0), 10.0
    for name, theirs in NAMES.items():
        for size in DRAWN:
            # a size Breeze skips (folder-desktop has no 48px): the next one up
            f = next((places / str(d) / f"{theirs}.svg" for d in DRAWN
                      if d >= size and (places / str(d) / f"{theirs}.svg").exists()), None)
            if f is None:
                continue
            text = mark(f.resolve().read_text(encoding="utf-8"))
            if size == 32:
                for small in SMALL:
                    out = OUT / str(small) / f"{name}.svg"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(small_icon(text, name, small, box32, front32), encoding="utf-8")
                    count += 1
            for s in (size,):
                out = OUT / str(s) / f"{name}.svg"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(sized(text, s), encoding="utf-8")
                count += 1
    # Mint-Y's names Breeze doesn't draw, at the small sizes: its folder, Mint-Y's picture
    plain = mark((places / "32" / "folder.svg").resolve().read_text(encoding="utf-8"))
    for name in smallsize.mint_names():
        if name in NAMES or name in ("folder-drag-accept",):
            continue
        for small in SMALL:
            (OUT / str(small) / f"{name}.svg").write_text(small_icon(plain, name, small, box32, front32),
                                                          encoding="utf-8")
            count += 1
    print(f"{count} icons written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
