#!/usr/bin/env python3
"""Cut Mint-Y's places icons out of Mint's source sheet, one small SVG each.

    python3 tools/import-mint-y-places.py MINT_Y_ICONS_CHECKOUT
      (a checkout with src/places and usr/share/icons/Mint-Y/places)

Mint draws all its folder and places icons, at every size, on one sheet
(src/places/src.svg in github.com/linuxmint/mint-y-icons) and renders them
with Inkscape. We cut each icon out once, here, so the Tool can recolour
them as text at Apply (no Inkscape, crisp at every size and on HiDPI):
data/icons/mint-y/places/<size>/<name>.svg, in Mint's source colours
(folder #eeca8f, back #c89e6b, paper #e8e8e8, emblem #575757), which
cheeselooks/icons.py swaps for yours.

Needs Inkscape (for each icon's exact box: `inkscape --query-all`). Mint-Y's
icons are CC BY-SA 4.0 (Sam Hewitt, Alexey Varfolomeev); the copies keep that
licence and credit (data/icons/mint-y/COPYING).
"""
from __future__ import annotations

import copy
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icons" / "mint-y" / "places"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
ICON_ID = re.compile(r"([a-z-]+)_(\d+)$")
REF = re.compile(r"url\(#([^)]+)\)")


def main() -> int:
    src = Path(sys.argv[1]) / "src" / "places" / "src.svg"
    boxes = {}
    out = subprocess.run(["inkscape", "--query-all", str(src)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        name, x, y, w, h = line.split(",")
        boxes[name] = tuple(float(v) for v in (x, y, w, h))
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    tree = ET.parse(src)
    root = tree.getroot()
    parent = {c: p for p in root.iter() for c in p}
    by_id = {e.get("id"): e for e in root.iter() if e.get("id")}

    def referenced(el: ET.Element, seen: set[str]) -> None:
        for e in el.iter():
            for v in list(e.attrib.values()):
                for ref in REF.findall(v):
                    if ref not in seen and ref in by_id:
                        seen.add(ref)
                        referenced(by_id[ref], seen)
            href = e.get(f"{{{XLINK}}}href") or e.get("href")
            if href and href.startswith("#") and href[1:] not in seen and href[1:] in by_id:
                seen.add(href[1:])
                referenced(by_id[href[1:]], seen)

    count = 0
    for ident, el in by_id.items():
        m = ICON_ID.match(ident or "")
        if not m or ident not in boxes:
            continue
        name, size = m.group(1), int(m.group(2))
        x, y, w, h = boxes[ident]
        svg = ET.Element(f"{{{SVG}}}svg", {"width": str(size), "height": str(size),
                                         "viewBox": f"{x:g} {y:g} {w:g} {h:g}", "version": "1.1"})
        refs: set[str] = set()
        referenced(el, refs)
        if refs:
            defs = ET.SubElement(svg, f"{{{SVG}}}defs")
            for r in sorted(refs):
                defs.append(copy.deepcopy(by_id[r]))
        # the layers round the icon, with their positioning, down to the icon
        chain, p = [], parent.get(el)
        while p is not None and p is not root:
            chain.append(p)
            p = parent.get(p)
        holder = svg
        for layer in reversed(chain):
            g = ET.SubElement(holder, f"{{{SVG}}}g")
            if layer.get("transform"):
                g.set("transform", layer.get("transform"))
            holder = g
        holder.append(copy.deepcopy(el))
        for e in svg.iter():                     # Inkscape-only attributes aren't needed
            for k in [k for k in e.attrib if "inkscape" in k or "sodipodi" in k]:
                del e.attrib[k]
        f = OUT / str(size) / f"{name}.svg"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(ET.tostring(svg, encoding="unicode") + "\n", encoding="utf-8")
        count += 1
    print(f"{count} icons written to {OUT}")
    write_aliases(Path(sys.argv[1]))
    return 0


def write_aliases(checkout: Path) -> None:
    """Mint-Y's other names for these icons (nemo, file-manager, folder-open...):
    symlinks in each size's places folder. Mint's colours copy them, so ours do
    too (data/icons/mint-y/aliases.txt: "size alias target" lines)."""
    places = checkout / "usr" / "share" / "icons" / "Mint-Y" / "places"
    names = {f.stem for f in OUT.glob("*/*.svg")}
    lines = []
    for d in sorted(places.iterdir(), key=lambda p: p.name):
        size = d.name
        if not size.isdigit():
            continue
        for f in sorted(d.iterdir()):
            if f.is_symlink():
                target = Path(f.readlink()).stem
                if target in names:
                    lines.append(f"{size} {f.stem} {target}")
    (OUT.parent / "aliases.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} aliases written")


if __name__ == "__main__":
    sys.exit(main())
