#!/usr/bin/env python3
"""Cut Yaru's folder icons out of Ubuntu's source sheet, one small SVG each.

    python3 tools/import-yaru-places.py YARU_CHECKOUT

The same job as tools/import-mint-y-places.py, for a sheet laid out
differently: Yaru (github.com/ubuntu/yaru, icons/src/fullcolor/accented-full/
places/folders.svg) draws each icon in a group whose "Baseplate" layer holds
a box per size (16, 24, 32, 48 and 256px) and a text naming the icon, and its
build renders each box's area. We keep the icon's group, cropped to each box,
without the drawings that lie outside it, into data/icons/yaru/places/<size>/
<name>.svg. cheeselooks/icons.py then recolours them like Mint-Y's.

Yaru colours a folder with placeholders its build swaps for each accent:
#00ff03 for the folder, #008502 for darker accent details. Its front and back
are the same colour; we mark them apart, so the Tool can colour them
separately (front: your folder color, back: your second color):

    #00ff03 in "Folder (Front Section)" and the pictogram   -> #00ff03 (front)
    #00ff03 in "Folder (Back Section)"                      -> #00ff13 (back)
    #008502 in the folder's "Darken Overlays"               -> #008512 (back, darker)
    #008502 elsewhere (the pictogram)                       -> #008502 (emblem)

Needs Inkscape (each box's and element's position: `inkscape --query-all`).
Yaru's icons are CC BY-SA 4.0 (Canonical and the Yaru contributors); credited
in data/icons/yaru/COPYING.
"""
from __future__ import annotations

import copy
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icons" / "yaru" / "places"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
INK = "{http://www.inkscape.org/namespaces/inkscape}label"
REF = re.compile(r"url\(#([^)]+)\)")
FRONT, BACK, BACK_DARK, EMBLEM = "#00ff03", "#00ff13", "#008512", "#008502"


def main() -> int:
    sheet = Path(sys.argv[1]) / "icons" / "src" / "fullcolor" / "accented-full" / "places" / "folders.svg"
    boxes = {}
    out = subprocess.run(["inkscape", "--query-all", str(sheet)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        ident, x, y, w, h = line.split(",")
        boxes[ident] = tuple(float(v) for v in (x, y, w, h))
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    root = ET.parse(sheet).getroot()
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

    def mark(el: ET.Element, label_path: list[str]) -> None:
        """Front, back and emblem told apart by the layer they're in."""
        lab = el.get(INK) or ""
        path = label_path + [lab]
        for k, v in list(el.attrib.items()):
            low = v.lower()
            if "#00ff03" in low and "Folder (Back Section)" in path:
                el.set(k, re.sub("#00ff03", BACK, v, flags=re.I))
            elif "#008502" in low and "Darken Overlays" in path and "Shape" in path:
                el.set(k, re.sub("#008502", BACK_DARK, v, flags=re.I))
        for c in el:
            mark(c, path)

    def outside(ident: str | None, area: tuple[float, float, float, float]) -> bool:
        if not ident or ident not in boxes:
            return False
        x, y, w, h = boxes[ident]
        ax, ay, aw, ah = area
        return x > ax + aw or y > ay + ah or x + w < ax or y + h < ay

    def prune(el: ET.Element, area) -> None:
        for c in list(el):
            if outside(c.get("id"), area):
                el.remove(c)
            else:
                prune(c, area)

    count = 0
    for base in root.iter():
        if base.get(INK) != "Baseplate":
            continue
        group = parent[base]
        name = next(("".join(t.itertext()).strip() for t in base.iter() if t.get(INK) == "icon-name"), None)
        if not name:
            continue
        for rect in [r for r in base if r.tag.endswith("rect")]:
            area = boxes[rect.get("id")]
            size = int(round(area[2]))
            icon = copy.deepcopy(group)
            for b in [c for c in icon if c.get(INK) == "Baseplate"]:
                icon.remove(b)
            prune(icon, area)
            mark(icon, [])
            x, y, w, h = area
            svg = ET.Element(f"{{{SVG}}}svg", {"width": str(size), "height": str(size),
                                             "viewBox": f"{x:g} {y:g} {w:g} {h:g}", "version": "1.1"})
            refs: set[str] = set()
            referenced(icon, refs)
            if refs:
                defs = ET.SubElement(svg, f"{{{SVG}}}defs")
                for r in sorted(refs):
                    d = copy.deepcopy(by_id[r])
                    mark(d, [])
                    defs.append(d)
            chain, p = [], parent.get(group)
            while p is not None and p is not root:
                chain.append(p)
                p = parent.get(p)
            holder = svg
            for layer in reversed(chain):
                g = ET.SubElement(holder, f"{{{SVG}}}g")
                if layer.get("transform"):
                    g.set("transform", layer.get("transform"))
                holder = g
            holder.append(icon)
            for e in svg.iter():
                for k in [k for k in e.attrib if "inkscape" in k or "sodipodi" in k]:
                    del e.attrib[k]
            f = OUT / str(size) / f"{name}.svg"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(ET.tostring(svg, encoding="unicode") + "\n", encoding="utf-8")
            count += 1
    print(f"{count} icons written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
