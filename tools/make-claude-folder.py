#!/usr/bin/env python3
"""Draw the Claude folder style: the "Hot Rod" folder, turned a little left.

    python3 tools/make-claude-folder.py

Claude's design, picked by xl_cheese from its first sketches (21 Nov): a
wide back with a tab, and a front panel that's a wedge, wider at the top than
at the bottom, with a darker band along its foot and a light edge along its
top. Turned gently the other way from xl-Big Baddy (its right edge shows) and
seen from a little *above*, where the binder is seen from below: a different
perspective, not a mirror of it (xl_cheese: "turned slightly opposite the
direction xl-Big Baddy are, but not the same perspective").

True perspective from 3D at 32px and up, Mint-Y's pictures (CC BY-SA 4.0)
on the front's lower right by the same projection (affine over their box);
16, 22, 24px straight on, on whole pixels, Mint-Y's picture at its own size
(tools/smallsize.py). Open (drag-accept): the front tipped forward.

Placeholder colours (cheeselooks/icons.py):
    #c1a0d1 the front (your folder color)     #c1a0d3 the front's edge and foot (darker)
    #c1a0d2 the back and tab (second color)   #c1a0d4 the picture (emblem)
"""
from __future__ import annotations

import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smallsize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icons" / "claude" / "places"
SVG, XLINK = smallsize.SVG, smallsize.XLINK
FRONT, BACK, EDGE, EMBLEM = "#c1a0d1", "#c1a0d2", "#c1a0d3", "#c1a0d4"
SIZES = (16, 22, 24, 32, 48, 64, 96, 128)
SMALL = (16, 22, 24)

# the folder flat, as sketched (u right, v up, a 128 box): the back with its
# tab, and the front: a wedge (108 wide at the top, 100 at the foot)
BACK_PTS = None
T = 5.0                                     # the back sits this far behind the front
YAW, PITCH, CAM = math.radians(-36), math.radians(8), 230.0
PIC = 34.0
PIC_AT = (64.0, 50.0)                       # the picture's centre: the middle of the front (xl_cheese)
FIT = 116.0


def arc(cx, cy, r, a0, a1, n=5):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


BACK_DROP = 6.0          # xl_cheese: the back a little lower (its top and tab), to suit the front


def back_outline():
    """The back: rounded corners (the bottom ones too, hidden behind the
    front's), the tab at the top left (from the sketch), lowered by BACK_DROP."""
    dz = BACK_DROP
    # as wide as the front (10..118 at the top, the fold's ends at the bottom)
    pts = arc(22, 22, 8, -90, -180)                      # bottom left corner
    pts += arc(18, 106 - dz, 8, 180, 90)                 # top left corner, up into the tab
    pts += [(50, 114 - dz)]
    pts += arc(50, 109 - dz, 5, 90, 30)                  # the tab's slope down
    pts += [(58, 104 - dz), (61, 104 - dz)]
    pts += arc(110, 96 - dz, 8, 90, 0)                   # top right corner
    pts += arc(103.5, 22, 8, 0, -90)                     # bottom right corner, tucked in behind the front's
    return pts


def front_outline(lift=0.0):
    """The front: wider at the top (10..118) than its foot (14..114), rounded."""
    pts = []
    pts += arc(16, 80, 6, 180, 90)                     # top left
    pts += arc(112, 80, 6, 90, 0)                      # top right
    pts += arc(106, 22, 8, 0, -90)                     # foot right (the side leans in)
    pts += arc(22, 22, 8, -90, -180)                   # foot left
    return pts


def project(u, v, z):
    x, y, zz = u - 64, v - 64, z + T / 2
    x, zz = x * math.cos(YAW) + zz * math.sin(YAW), -x * math.sin(YAW) + zz * math.cos(YAW)
    y, zz = y * math.cos(PITCH) - zz * math.sin(PITCH), y * math.sin(PITCH) + zz * math.cos(PITCH)
    k = CAM / (CAM - zz)
    return x * k, -y * k


def d(pts3, close=True):
    p = [project(*q) for q in pts3]
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in p) + (" Z" if close else "")


def on(pts, z=0.0, tip=0.0):
    """Points on the front's plane; `tip` tips it forward about its foot (open)."""
    out = []
    for u, v in pts:
        h = v - 14
        out.append((u, 14 + h * math.cos(tip), z + h * math.sin(tip)))
    return out


def picture3d(name: str, size: int, tip: float) -> list:
    found = smallsize.compose.mint_picture(name, size)
    if found is None:
        return monitor3d(tip) if name == "user-desktop" else []
    pic, (x0, y0, x1, y1) = found
    k = PIC / max(x1 - x0, y1 - y0)
    cu, cv = PIC_AT

    def at(x, y):
        return (cu + (x - (x0 + x1) / 2) * k, cv - (y - (y0 + y1) / 2) * k)
    (ax, ay), (bx, by), (cx, cy) = (project(*on([at(x, y)], 0.05, tip)[0]) for x, y in ((x0, y0), (x1, y0), (x0, y1)))
    a, b = (bx - ax) / (x1 - x0), (by - ay) / (x1 - x0)
    c, dd = (cx - ax) / (y1 - y0), (cy - ay) / (y1 - y0)
    e, f = ax - a * x0 - c * y0, ay - b * x0 - dd * y0
    inner = re.sub(smallsize.MINT_EMBLEM, EMBLEM, ET.tostring(pic, encoding="unicode"), flags=re.I)
    g = ET.Element(f"{{{SVG}}}g", {"transform": f"matrix({a:.5f} {b:.5f} {c:.5f} {dd:.5f} {e:.4f} {f:.4f})"})
    for child in list(ET.fromstring(inner)):
        g.append(child)
    return [ET.tostring(g, encoding="unicode")]


def rect_r(x0, y0, x1, y1, r):
    return arc(x0 + r, y1 - r, r, 180, 90, 3) + arc(x1 - r, y1 - r, r, 90, 0, 3) + \
        arc(x1 - r, y0 + r, r, 0, -90, 3) + arc(x0 + r, y0 + r, r, -90, -180, 3)


def monitor3d(tip: float) -> list:
    cu, cv = PIC_AT
    w, h = PIC, PIC * 0.66
    top = cv + h / 2 + 3
    outer = rect_r(cu - w / 2, top - h, cu + w / 2, top, 2.5)
    inner = rect_r(cu - w / 2 + 3, top - h + 3, cu + w / 2 - 3, top - 3, 1)
    stand = [(cu - 3, top - h), (cu + 3, top - h), (cu + 4, top - h - 4), (cu + 9, top - h - 4),
             (cu + 9, top - h - 6.5), (cu - 9, top - h - 6.5), (cu - 9, top - h - 4), (cu - 4, top - h - 4)]
    return [f'<path fill="{EMBLEM}" fill-rule="evenodd" d="{d(on(outer, 0.05, tip))} {d(on(inner[::-1], 0.05, tip))}"/>',
            f'<path fill="{EMBLEM}" d="{d(on(stand, 0.05, tip))}"/>']


def z_back(v: float) -> float:
    """Front and back are one folded piece (xl_cheese's reference picture):
    joined at a fold along the bottom, the gap between them widening upward."""
    return -(1.5 + 20.0 * (v - 14) / 86)


def folder3d(name: str, size: int, opened: bool = False) -> str:
    tip = math.radians(22) if opened else 0.0
    parts = []
    back = back_outline()
    parts.append(f'<path fill="{BACK}" d="{d([(u, v, z_back(v)) for u, v in back])}"/>')
    # the open side (turned this way, the right): the inside of the fold, dark
    top_b = 96 - BACK_DROP
    # (it ends where the front's foot starts to round: lower, slivers showed at the corner)
    side = on([(118, 80)], 0, tip) + on([(114, 24)], 0, tip) + [(111.8, 24, z_back(24)), (118, top_b, z_back(top_b))]
    parts.append(f'<path fill="{EDGE}" d="{d(side)}"/>')
    # the papers inside: their edges in the gap, their tops over the front
    for frac, top, colour in ((0.62, 92 - BACK_DROP, "#E9E9E9"), (0.35, 90 - BACK_DROP + 4 * bool(opened), "#FAFAFA")):
        sheet = [(16, 26), (14, top), (116, top), (110.6, 26)]   # inside the back's edge
        parts.append(f'<path fill="{colour}" d="{d([(u, v, z_back(v) * frac) for u, v in sheet])}"/>')
        edge = [(110.6, 26), (116, top), (117.2, top), (111.4, 26)]
        parts.append(f'<path fill="{colour}" d="{d([(u, v, z_back(v) * frac) for u, v in edge])}"/>')
    front = front_outline()
    # the front: its own thickness on the right, then its face, its foot darker, its top edge light
    edge = on([(118, 80), (114, 22)], 0, tip) + on([(114, 22), (118, 80)], -1.6, tip)
    parts.append(f'<path fill="{EDGE}" d="{d(edge)}"/>')
    parts.append(f'<path fill="{FRONT}" d="{d(on(front, 0, tip))}"/>')
    foot = [(13.86, 24), (114.14, 24)] + arc(106, 22, 8, 0, -90) + arc(22, 22, 8, -90, -180)
    parts.append(f'<path fill="#000" fill-opacity="0.13" d="{d(on(foot, 0.02, tip))}"/>')
    top = arc(16, 80, 6, 180, 90) + arc(112, 80, 6, 90, 0)
    shine = top + [(u, v - 2.2) for u, v in reversed(top)]
    parts.append(f'<path fill="#fff" fill-opacity="0.3" d="{d(on(shine, 0.03, tip))}"/>')
    nums = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+\.\d+) (-?\d+\.\d+)", "".join(parts))]
    parts += picture3d(name, size, tip)
    body = "".join(parts)
    bx0, bx1 = min(p[0] for p in nums), max(p[0] for p in nums)
    by0, by1 = min(p[1] for p in nums), max(p[1] for p in nums)
    s = min(FIT / (bx1 - bx0), 120 / (by1 - by0))
    tx, ty = 64 - s * (bx0 + bx1) / 2, 64 - s * (by0 + by1) / 2
    k = size / 128
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="{XLINK}" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}" version="1.1"><g transform="matrix({s * k:.5f} 0 0 {s * k:.5f} '
            f'{tx * k:.4f} {ty * k:.4f})" stroke-linejoin="round">{body}</g></svg>\n')


# ------------------------------------------------------------------ small, straight on
SMALL_GEO = {   # size: back x0, x1, top; tab end; front x0, x1 (top), top, bottom; foot inset
    16: (1, 15, 2, 6, 1, 15, 5, 15, 1),
    22: (2, 20, 4, 9, 1, 21, 7, 20, 1),
    24: (2, 22, 4, 10, 1, 23, 8, 22, 1),
}


def folder_small(name: str, size: int, opened: bool = False) -> str:
    bx0, bx1, bt, tab, fx0, fx1, ft, fb, inset = SMALL_GEO[size]
    parts = []
    # the back with its tab
    parts.append(f'<path fill="{BACK}" d="M{bx0} {bt + 1} q0 -1 1 -1 H{tab} l2 2 H{bx1 - 1} q1 0 1 1 V{fb - 2} H{bx0} Z"/>')
    if opened:
        parts.append(f'<rect x="{bx0 + 1}" y="{bt + 3}" width="{bx1 - bx0 - 2}" height="{fb - bt - 5}" fill="#F5F5F5"/>')
        ft += 2
    # the front: a wedge, its foot a whole pixel in at each side; its edge, foot and top
    parts.append(f'<path fill="{FRONT}" d="M{fx0} {ft + 1} q0 -1 1 -1 H{fx1 - 1} q1 0 1 1 '
                 f'L{fx1 - inset} {fb - 1} q0 1 -1 1 H{fx0 + inset + 1} q-1 0 -1 -1 Z"/>')
    parts.append(f'<path fill="#000" fill-opacity="0.13" d="M{fx0 + inset} {fb - 2} H{fx1 - inset} V{fb - 1} '
                 f'q0 1 -1 1 H{fx0 + inset + 1} q-1 0 -1 -1 Z"/>')
    parts.append(f'<rect x="{fx0 + 1}" y="{ft}" width="{fx1 - fx0 - 2}" height="1" fill="#fff" fill-opacity="0.3"/>')
    cx = (fx0 + fx1) / 2 - 0.5
    cy = (ft + fb) / 2 + 0.5
    pic = smallsize.mint_picture(name, size, cx, cy, EMBLEM)
    extra = ""
    if pic is not None:
        extra = ET.tostring(pic, encoding="unicode")
    elif name == "user-desktop":
        mw, mh = (7, 5) if size == 16 else (9, 6)
        mx, my = round(cx - mw / 2), round(cy - mh / 2 - 0.5)
        extra = (f'<path fill="{EMBLEM}" fill-rule="evenodd" d="M{mx} {my} h{mw} v{mh} h{-mw} Z '
                 f'M{mx + 1} {my + 1} v{mh - 2} h{mw - 2} v{-(mh - 2)} Z"/>'
                 f'<rect fill="{EMBLEM}" x="{mx + mw // 2 - 1}" y="{my + mh}" width="{3 if mw > 7 else 2}" height="1"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="{XLINK}" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}" version="1.1">{"".join(parts)}{extra}</svg>\n')


def main() -> int:
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    count = 0
    for size in SIZES:
        for name in smallsize.mint_names():
            opened = name == "folder-drag-accept"
            svg = (folder_small if size in SMALL else folder3d)(name, size, opened)
            f = OUT / str(size) / f"{name}.svg"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(svg, encoding="utf-8")
            count += 1
    print(f"{count} icons written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
