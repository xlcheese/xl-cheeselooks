#!/usr/bin/env python3
"""Make the places icons a folder style doesn't draw, from its own folder and
Mint-Y's picture, so every style covers Mint-Y's set.

    python3 tools/compose-missing-places.py        (after the import-*.py tools)

Mint-Y has 16 places icons (folder, documents, desktop, bookmarks, network,
saved search...). A style missing one would show your previous icon theme's
for it, in other colours. Mint makes each of its icons the same way: one
folder, with a picture on the front. So does this, for each style and size:

  - the style's plain folder (its folder.svg at that size);
  - Mint-Y's picture for that icon (its SVG without the folder), in the
    style's picture colour, so it takes your colours like the rest;
  - placed where the style puts its own pictures: centred on the picture of
    its folder-documents, in a square as big as that picture's longer side.
    At a size where the style draws no pictures (Yaru's 16px folders are
    all plain), its plain folder.

The boxes are found by rendering (GdkPixbuf), not guessed. Mint-Y's pictures
keep their licence (CC BY-SA 4.0), credited in each style's COPYING.
Rerun after an import tool, which overwrites the folders it copies.
"""
from __future__ import annotations

import collections
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cheeselooks import icons  # noqa: E402

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
MINT = icons.source_dir("mint-y")
MINT_SIZES = icons.STYLES["mint-y"]["sizes"]
NAMES = sorted(f.stem for f in (MINT / "48").glob("*.svg"))
SKIP = {"folder", "folder-drag-accept"}        # the folder itself; drag-accept: the open folder stands in
SCALE = 8                                      # render at 8x to find the boxes
MARK = "#ff0000"


def render(svg: str, size: int) -> GdkPixbuf.Pixbuf:
    loader = GdkPixbuf.PixbufLoader()
    loader.set_size(size * SCALE, size * SCALE)
    loader.write(svg.encode())
    loader.close()
    return loader.get_pixbuf()


def box(pb: GdkPixbuf.Pixbuf, test) -> tuple[int, int, int, int] | None:
    """Pixel bounds (x0, y0, x1, y1) of the pixels passing test(r, g, b, a)."""
    px, stride, n = pb.get_pixels(), pb.get_rowstride(), pb.get_n_channels()
    xs, ys = [], []
    for y in range(pb.get_height()):
        row = y * stride
        for x in range(pb.get_width()):
            i = row + x * n
            if test(px[i], px[i + 1], px[i + 2], px[i + 3] if n == 4 else 255):
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None


def viewbox(root: ET.Element, size: int) -> tuple[float, float, float, float]:
    vb = root.get("viewBox")
    return tuple(float(v) for v in vb.replace(",", " ").split()) if vb else (0, 0, size, size)


def to_user(b, vb, size):
    """A pixel box at SCALE to the SVG's own coordinates."""
    k = vb[2] / (size * SCALE)
    return (vb[0] + b[0] * k, vb[1] + b[1] * k, vb[0] + b[2] * k, vb[1] + b[3] * k)


def mint_picture(name: str, size: int) -> tuple[ET.Element, tuple] | None:
    """Mint-Y's icon without its folder, its ids prefixed, and the picture's box."""
    msize = min((s for s in MINT_SIZES if s >= size), default=max(MINT_SIZES))
    f = MINT / str(msize) / f"{name}.svg"
    if not f.exists():
        return None
    text = f.read_text(encoding="utf-8")
    text = re.sub(r'id="([^"]+)"', r'id="m-\1"', text)
    text = re.sub(r'url\(#([^)]+)\)', r'url(#m-\1)', text)
    text = re.sub(r'href="#([^"]+)"', r'href="#m-\1"', text)
    root = ET.fromstring(text)
    removed = False
    for parent in list(root.iter()):
        for c in list(parent):
            href = c.get(f"{{{XLINK}}}href") or c.get("href") or ""
            if c.tag.endswith("use") and href.startswith("#m-folder"):
                parent.remove(c)                   # the folder: the style draws its own
                removed = True
    if not removed:
        return None                                # not a folder with a picture (Mint-Y's desktop)
    vb = viewbox(root, msize)
    alone = ET.tostring(root, encoding="unicode")
    b = box(render(alone, msize), lambda r, g, b, a: a > 40)
    if b is None:
        return None
    return root, to_user(b, vb, msize)


def target(style: str, size: int) -> tuple[float, float, float, float] | None:
    """The style's picture square: its folder-documents picture, made square."""
    f = icons.source_dir(style) / str(size) / "folder-documents.svg"
    if not f.exists():
        return None
    c = {"folder": "#0000f0", "backfolder": "#00f000", "backdark": "#00a000", "paper": "#f0f0f0",
         "frontedge": "#0000a0", "frontshine": "#8080f0",
         "emblem": MARK}
    svg = icons.recolour(f.read_text(encoding="utf-8"), c, style)
    # the picture may be see-through over the folder (Yaru: red over blue shows
    # purple-red); its colour is also on other details at 256px (a line along
    # the bottom), so only the picture's own main shade counts
    pb = render(svg, size)
    reds = collections.Counter()
    box(pb, lambda r, g, b, a: a > 200 and r > 120 and g < 60 and r > b + 60 and not reds.update([(r, g, b)]))
    if not reds:
        return None
    main = reds.most_common(1)[0][0]
    b = box(pb, lambda r, g, b, a: a > 200 and sum((u - v) ** 2 for u, v in zip((r, g, b), main)) < 12 ** 2)
    if b is None:
        return None
    vb = viewbox(ET.fromstring(svg), size)
    x0, y0, x1, y1 = to_user(b, vb, size)
    side = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2 - vb[0], (y0 + y1) / 2 - vb[1]     # from the icon's corner: each
    return cx - side / 2, cy - side / 2, side, side           # Yaru icon has its own place on the sheet


def compose(style: str, name: str, size: int) -> str | None:
    folder = icons.source_dir(style) / str(size) / "folder.svg"
    if not folder.exists():
        return None
    pic, where = mint_picture(name, size), target(style, size)
    if where is None:                      # the style has no pictures at this size (Yaru's 16px):
        return folder.read_text(encoding="utf-8")         # its plain folder, as its own
    if pic is None:
        return None
    root, (px0, py0, px1, py1) = pic
    emblem = icons.STYLES[style]["source"]["emblem"]
    mint_emblem = icons.STYLES["mint-y"]["source"]["emblem"]
    inner = ET.tostring(root, encoding="unicode")
    inner = re.sub(mint_emblem, emblem, inner, flags=re.I)        # takes your picture colour
    inner_root = ET.fromstring(inner)
    out = ET.fromstring(folder.read_text(encoding="utf-8"))
    fx, fy = viewbox(out, size)[:2]
    x, y, w, h = where
    x, y = x + fx, y + fy
    nested = ET.Element(f"{{{SVG}}}svg", {
        "x": f"{x:.3f}", "y": f"{y:.3f}", "width": f"{w:.3f}", "height": f"{h:.3f}",
        "viewBox": f"{px0:.3f} {py0:.3f} {px1 - px0:.3f} {py1 - py0:.3f}",
        "preserveAspectRatio": "xMidYMid meet", "overflow": "visible"})
    for c in list(inner_root):
        nested.append(c)
    out.append(nested)
    return ET.tostring(out, encoding="unicode") + "\n"


def main() -> int:
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    made = []
    for style, spec in icons.STYLES.items():
        if style == "mint-y":
            continue
        for size in spec["sizes"]:
            d = icons.source_dir(style) / str(size)
            for name in NAMES:
                if name in SKIP or (d / f"{name}.svg").exists():
                    continue
                svg = compose(style, name, size)
                if svg:
                    (d / f"{name}.svg").write_text(svg, encoding="utf-8")
                    made.append(f"{style} {size} {name}")
    print(f"{len(made)} icons made")
    for m in made:
        print("  " + m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
