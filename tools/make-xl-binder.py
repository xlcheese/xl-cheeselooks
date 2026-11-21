#!/usr/bin/env python3
"""Draw the xl-Big Baddy folder style: an 80s school binder with racing stripes.

    python3 tools/make-xl-binder.py

xl_cheese's design (21 Nov): a zip-flap school binder (Trapper Keeper-like,
not its name or art) standing up, spine at the bottom, flap over the top,
seen from below and to the left so it stands tall and its top leans away.
Wider than tall, one colour (cover and flap), a wedge side (thick at the
spine, thin at the top; the paper and pink pockets inside showing there, the
sides being open), the flap's plastic curving over the top of the side, white
piping on the flap and a white ring on the cover. Racing stripes, a pair from
just above the bottom-left corner to the top-right corner, run under the ring
and the flap and on across the flap under its piping. In the stripe colour
of the cover they vanish (the rings are drawn over them): that's "no stripes".

Drawn in true perspective from 3D at 32px and up (every point projected),
the pictures (Mint-Y's for each name, CC BY-SA 4.0) laid on the cover by the
same projection, as an affine map of their box. At 16, 22 and 24px the
perspective turns to mush: there the binder is drawn straight on, on whole
pixels, keeping the flap, the side and the stripes, with Mint-Y's picture at
its own size. The open folder (drag-accept) has its flap up.

Placeholder colours, swapped at Apply (cheeselooks/icons.py):
    #ff0a01 the binder (your folder color)     #ff0a03 racing stripes (second color)
    #ff0a02 its side (the folder, darker)      #ff0a04 the picture (emblem)
"""
from __future__ import annotations

import importlib.util
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "icons" / "xl-big-baddy" / "places"
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
F, SIDE, STRIPE, EMBLEM = "#ff0a01", "#ff0a02", "#ff0a03", "#ff0a04"
PINK, PAPER, PAPER2, RING = "#E04E8A", "#FFFFFF", "#F4F4F4", "#FFFFFF"

spec = importlib.util.spec_from_file_location("compose", ROOT / "tools" / "compose-missing-places.py")
compose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compose)
MINT_EMBLEM = "#" + compose.icons.STYLES["mint-y"]["source"]["emblem"]

SIZES = (16, 22, 24, 32, 48, 64, 96, 128)
SMALL = (16, 22, 24)

# ------------------------------------------------------------------ the 3D binder
W, H = 96.0, 80.0                      # the cover (u right, v up)
D_BOTTOM, D_TOP = 20.0, 9.0            # the wedge: thick at the spine, thin at the top
FLAP = 24.0                            # the flap's height on the front
YAW, PITCH, CAM = math.radians(38), math.radians(-14), 200.0
STRIPES = ((3.0, 12.0), (20.0, 29.0))  # where each band's edges meet the left edge
SLOPE = (H - 3.0) / W                  # the lower stripe: bottom-left corner to top-right corner
PIC = 34.0                             # the picture's box on the cover, as Mint-Y's on its folder
PIC_AT = (W - 6 - PIC / 2 - 4, 6 + PIC / 2 + 3)
VELCRO, VELCRO_U = "#1E1E1E", (W / 2 - 2.5, W / 2 + 2.5)   # the velcro strips (open binder), centred
FIT = 114.0                            # the binder's width in the 128px icon (Breeze-like margins)


def project(u, v, z):
    x, y, zz = u - W / 2, v - H / 2, z + D_BOTTOM / 2
    x, zz = x * math.cos(YAW) + zz * math.sin(YAW), -x * math.sin(YAW) + zz * math.cos(YAW)
    y, zz = y * math.cos(PITCH) - zz * math.sin(PITCH), y * math.sin(PITCH) + zz * math.cos(PITCH)
    k = CAM / (CAM - zz)
    return x * k, -y * k


def depth(v):
    return D_BOTTOM + (D_TOP - D_BOTTOM) * v / H


def rounded(x0, y0, x1, y1, r, corners="tl tr br bl", n=6):
    pts = []
    for name, cx, cy, a0 in (("tl", x0 + r, y1 - r, 180), ("tr", x1 - r, y1 - r, 90),
                             ("br", x1 - r, y0 + r, 0), ("bl", x0 + r, y0 + r, 270)):
        if name in corners:
            pts += [(cx + r * math.cos(math.radians(a0 - 90 * i / n)),
                     cy + r * math.sin(math.radians(a0 - 90 * i / n))) for i in range(n + 1)]
        else:
            pts.append({"tl": (x0, y1), "tr": (x1, y1), "br": (x1, y0), "bl": (x0, y0)}[name])
    return pts


def d(pts3, close=True):
    p = [project(*q) for q in pts3]
    return "M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in p) + (" Z" if close else "")


def front(pts, z=0.0):
    return [(u, v, z) for u, v in pts]


def top_curve(inset, n=10):
    r = D_TOP / 2 + 1
    return [(-(D_TOP - inset) * math.cos(math.radians(90 * i / n)),
             H - r + (r - inset) * math.sin(math.radians(90 * i / n))) for i in range(n + 1)]


def clip(poly, u0, v0, u1, v1):
    def cut(pts, inside, cross):
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            if inside(p):
                if not inside(q):
                    out.append(cross(q, p))
                out.append(p)
            elif inside(q):
                out.append(cross(q, p))
        return out
    at_u = lambda u: lambda a, b: (u, a[1] + (b[1] - a[1]) * (u - a[0]) / (b[0] - a[0]))  # noqa: E731
    at_v = lambda v: lambda a, b: (a[0] + (b[0] - a[0]) * (v - a[1]) / (b[1] - a[1]), v)  # noqa: E731
    for inside, cross in ((lambda p: p[0] >= u0, at_u(u0)), (lambda p: p[0] <= u1, at_u(u1)),
                          (lambda p: p[1] >= v0, at_v(v0)), (lambda p: p[1] <= v1, at_v(v1))):
        poly = cut(poly, inside, cross)
        if not poly:
            break
    return poly


def stripes(v_from, v_to, z):
    out = []
    for a0, a1 in STRIPES:
        far = 3 * W
        band = clip([(0, a0), (far, a0 + SLOPE * far), (far, a1 + SLOPE * far), (0, a1)], 0, v_from, W, v_to)
        if len(band) > 2:
            out.append(f'<path fill="{STRIPE}" d="{d(front(band, z))}"/>')
    return out


def picture(name: str, size: int, opened: bool) -> list:
    """Mint-Y's picture for `name`, laid on the cover's lower right."""
    found = compose.mint_picture(name, size)
    if found is None:
        return []
    pic, (x0, y0, x1, y1) = found
    k = PIC / max(x1 - x0, y1 - y0)
    cu, cv = PIC_AT

    def to_cover(x, y):
        return (cu + (x - (x0 + x1) / 2) * k, cv - (y - (y0 + y1) / 2) * k)
    # the projection is nearly affine over a box this small: three corners fix it
    (ax, ay), (bx, by), (cx, cy) = (project(*to_cover(x, y), 0.05) for x, y in ((x0, y0), (x1, y0), (x0, y1)))
    a, b = (bx - ax) / (x1 - x0), (by - ay) / (x1 - x0)
    c, dd = (cx - ax) / (y1 - y0), (cy - ay) / (y1 - y0)
    e, f = ax - a * x0 - c * y0, ay - b * x0 - dd * y0
    inner = re.sub(MINT_EMBLEM, EMBLEM, ET.tostring(pic, encoding="unicode"), flags=re.I)
    g = ET.Element(f"{{{SVG}}}g", {"transform": f"matrix({a:.5f} {b:.5f} {c:.5f} {dd:.5f} {e:.4f} {f:.4f})"})
    for child in list(ET.fromstring(inner)):
        g.append(child)
    return [ET.tostring(g, encoding="unicode")]


def monitor3d(z: float) -> list:
    """Our Desktop picture (Mint-Y's desktop isn't a folder with a picture): a
    monitor, solid as Mint-Y's pictures, on the cover's lower right."""
    cu, cv = PIC_AT
    w, h = PIC * 1.0, PIC * 0.66
    top = cv + h / 2 + 3
    outer = rounded(cu - w / 2, top - h, cu + w / 2, top, 2.5)
    inner = rounded(cu - w / 2 + 3, top - h + 3, cu + w / 2 - 3, top - 3, 1)
    stand = [(cu - 3, top - h), (cu + 3, top - h), (cu + 4, top - h - 4), (cu + 9, top - h - 4),
             (cu + 9, top - h - 6.5), (cu - 9, top - h - 6.5), (cu - 9, top - h - 4), (cu - 4, top - h - 4)]
    return [f'<path fill="{EMBLEM}" fill-rule="evenodd" d="{d(front(outer, z))} {d(front(inner[::-1], z))}"/>',
            f'<path fill="{EMBLEM}" d="{d(front(stand, z))}"/>']


COVER = "stripes"            # "stripes": xl-Big Baddy; "checker": the 80s binder (xl_cheese's mockup)
CHECK = 6.0                  # a checker square, on the cover
WAVE_LOW, WAVE_HIGH, WAVE_AMP, WAVE_LEN = 9.0, 31.0, 2.4, 34.0


def wave(v0: float, phase: float, n: int = 48) -> list:
    return [(W * i / n, v0 + WAVE_AMP * math.sin(2 * math.pi * (W * i / n) / WAVE_LEN + phase)) for i in range(n + 1)]


def checker_band(uid: str, z: float = 0.02) -> list:
    """xl_cheese's 80s cover: a checkerboard band across the cover between two
    wavy lines in the second color. The checks are projected squares, clipped
    to the band (an SVG clip path in the same coordinates)."""
    low, high = wave(WAVE_LOW, 0.4), wave(WAVE_HIGH, 2.2)
    band = low + high[::-1]
    out = [f'<clipPath id="band{uid}"><path d="{d(front(band, z))}"/></clipPath>',
           f'<g clip-path="url(#band{uid})"><path fill="#FFFFFF" d="{d(front(band, z))}"/>']
    cells = []
    for i in range(int(W / CHECK) + 1):
        for j in range(int((WAVE_HIGH + WAVE_AMP + 2) / CHECK) + 2):
            if (i + j) % 2:
                u0, v0 = i * CHECK, j * CHECK
                cells.append(d(front([(u0, v0), (u0 + CHECK, v0), (u0 + CHECK, v0 + CHECK), (u0, v0 + CHECK)], z)))
    out.append(f'<path fill="#1A1A1A" d="{" ".join(cells)}"/></g>')
    for line in (low, high):
        out.append(f'<path fill="none" stroke="{STRIPE}" stroke-width="3.4" d="{d(front(line, z + 0.01), close=False)}"/>')
    return out


def binder3d(name: str, size: int, opened: bool = False) -> str:
    parts = []
    if opened:   # the flap, up behind: its underside, plain and darker (no piping there), rising from the back's top
        flap = [(u, H - 2 + v, -D_TOP + v * 0.35) for u, v in rounded(0, 0, W, FLAP, 6, "tl tr")]
        parts.append(f'<path fill="{SIDE}" d="{d(flap)}"/>')
        # its velcro strip, near the free edge (xl_cheese: the flap closed with velcro)
        strip = [(u, H - 2 + v, -D_TOP + v * 0.35 + 0.05)
                 for u, v in rounded(VELCRO_U[0], FLAP - 12, VELCRO_U[1], FLAP - 3, 0.8)]
        parts.append(f'<path fill="{VELCRO}" d="{d(strip)}"/>')
    # the open side: dark, with the paper and pink pockets inside, narrowing up
    prof = [(-D_BOTTOM, 0.0)] + [(-depth(v), v) for v in (H * 0.5, H - D_TOP / 2 - 1)] + top_curve(0) + [(0.0, 0.0)]
    parts.append(f'<path fill="{SIDE}" d="{d([(0, v, z) for z, v in prof])}"/>')
    for f0, f1, colour in ((0.12, 0.26, PINK), (0.26, 0.42, PAPER2), (0.42, 0.52, PINK), (0.52, 0.86, PAPER)):
        pts = [(0, v, -depth(v) * (1 - f0)) for v in (4, H - 12)] + [(0, v, -depth(v) * (1 - f1)) for v in (H - 12, 4)]
        parts.append(f'<path fill="{colour}" d="{d(pts)}"/>')
    if opened:   # flap up: the papers' tops show over the cover
        for z0, z1, top, colour in ((-7.5, -4.5, 5, PAPER2), (-5.0, -1.2, 3, PAPER)):
            pts = [(1, H - 4, z1), (1, H + top, z1), (W - 3, H + top, z1), (W - 3, H - 4, z1)]
            parts.append(f'<path fill="{colour}" d="{d(pts)}"/>')
            parts.append(f'<path fill="{colour}" d="{d([(1, H - 4, z0), (1, H + top, z0), (1, H + top, z1), (1, H - 4, z1)])}"/>')
    else:        # the flap's plastic, over the top of the side
        wrap = [(0, v, z) for z, v in top_curve(0)] + [(0, v, z) for z, v in reversed(top_curve(2.2))]
        parts.append(f'<path fill="{F}" d="{d(wrap)}"/>')
    parts.append(f'<path fill="#E6E6E6" d="{d([(0, 0, -D_BOTTOM), (0, 5, -D_BOTTOM + 0.5), (0, 5, -0.5), (0, 0, 0)])}"/>')
    # the cover, its stripes, its ring, its picture
    parts.append(f'<path fill="{F}" d="{d(front(rounded(0, 0, W, H, 4, "tr br")))}"/>')
    if COVER == "checker":
        parts += checker_band(name)
    else:
        parts += stripes(0, H if opened else H - FLAP + 3, 0.02)
        ring_top = H - FLAP - 6          # the same ring, open or closed (xl_cheese)
        parts.append(f'<path fill="none" stroke="{RING}" stroke-width="1.8" d="{d(front(rounded(6, 6, W - 6, ring_top, 6)))}"/>')
    if opened:   # the cover's velcro, where the flap presses down when closed
        parts.append(f'<path fill="{VELCRO}" d="{d(front(rounded(VELCRO_U[0], H - 18, VELCRO_U[1], H - 9, 0.8), 0.06))}"/>')
    parts += monitor3d(0.05) if name == "user-desktop" else picture(name, size, opened)
    if not opened:
        flap = rounded(0, H - FLAP, W, H, 6, "br bl")
        parts.append(f'<path fill="#000" fill-opacity="0.16" d="{d(front([(u, v - 1.8) for u, v in flap], 0.1))}"/>')
        parts.append(f'<path fill="{F}" d="{d(front(flap, 0.2))}"/>')
        if COVER != "checker":
            parts += stripes(H - FLAP, H - 0.3, 0.25)
        piping = [(W - 4, H - 1)] + [q for q in rounded(4, H - FLAP + 4, W - 4, H + 4, 5, "br bl") if q[1] < H - 1] + [(4, H - 1)]
        parts.append(f'<path fill="none" stroke="{RING}" stroke-width="1.5" d="{d(front(piping, 0.3), close=False)}"/>')
        parts.append(f'<path fill="#fff" fill-opacity="0.2" d="{d(front([(0, H - 2), (W, H - 2), (W, H), (0, H)], 0.3))}"/>')
    body = "".join(parts)
    # fit: the closed binder's box, so open and closed sit alike
    x0, x1, y0, y1 = _closed_box()
    s = FIT / (x1 - x0)
    if opened:   # the flap and papers rise above: fit the whole, a little smaller
        nums = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+\.\d+) (-?\d+\.\d+)", body)]
        x0, x1 = min(p[0] for p in nums), max(p[0] for p in nums)
        y0, y1 = min(p[1] for p in nums), max(p[1] for p in nums)
        s = min(s, 122 / (y1 - y0), 122 / (x1 - x0))
    tx, ty = 64 - s * (x0 + x1) / 2, 64 - s * (y0 + y1) / 2
    k = size / 128
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="{XLINK}" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}" version="1.1"><g transform="matrix({s * k:.5f} 0 0 {s * k:.5f} '
            f'{tx * k:.4f} {ty * k:.4f})" stroke-linejoin="round" stroke-linecap="round">{body}</g></svg>\n')


_BOX = None


def _closed_box():
    global _BOX
    if _BOX is None:
        pts = [project(0, v, z) for z, v in [(-D_BOTTOM, 0.0), (-D_TOP, H - D_TOP / 2 - 1)] + top_curve(0)]
        pts += [project(u, v, 0) for u, v in ((0, 0), (W, 0), (W, H), (0, H))]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        _BOX = (min(xs), max(xs), min(ys), max(ys))
    return _BOX


# ------------------------------------------------------------------ small sizes, straight on
SMALL_GEO = {   # size: side width, cover x0, x1, y0 (top), y1 (bottom), flap height, stripe width
    16: (1, 2, 15, 2, 14, 4, 1),
    22: (2, 3, 21, 3, 19, 5, 2),
    24: (2, 3, 23, 3, 21, 6, 2),
}


def binder_small(name: str, size: int, opened: bool = False) -> str:
    sw, x0, x1, y0, y1, fh, st = SMALL_GEO[size]
    parts = []
    # the side: a strip at the left, paper inside, the white spine end at the bottom
    parts.append(f'<rect x="{x0 - sw - 1}" y="{y0 + 1}" width="{sw + 1}" height="{y1 - y0 - 1}" fill="{SIDE}"/>')
    if sw > 1:
        parts.append(f'<rect x="{x0 - sw}" y="{y0 + fh}" width="1" height="{y1 - y0 - fh - 2}" fill="{PAPER}"/>')
    parts.append(f'<rect x="{x0 - sw - 1}" y="{y1 - 1}" width="{sw + 1}" height="1" fill="#E6E6E6"/>')
    r = 1.5 if size > 16 else 1
    parts.append(f'<path fill="{F}" d="M{x0} {y0} H{x1 - r} Q{x1} {y0} {x1} {y0 + r} V{y1 - r} Q{x1} {y1} {x1 - r} {y1} H{x0} Z"/>')
    # stripes, bottom left to top right, on whole-pixel steps (the 80s binder: its checker band)
    slope = (y1 - y0 - 1) / (x1 - x0)
    cell = 1 if size == 16 else 2
    band_bottom = y1 - 2                          # the lower line; the checks above it; the upper line
    band_top = band_bottom - cell - 1
    if COVER == "checker":
        parts.append(f'<rect x="{x0}" y="{band_top + 1}" width="{x1 - x0}" height="{cell}" fill="#FFFFFF"/>')
        for i, x in enumerate(range(x0, x1, cell)):
            if i % 2:
                parts.append(f'<rect x="{x}" y="{band_top + 1}" width="{min(cell, x1 - x)}" height="{cell}" fill="#1A1A1A"/>')
        for y in (band_top, band_bottom):
            parts.append(f'<rect x="{x0}" y="{y}" width="{x1 - x0}" height="1" fill="{STRIPE}"/>')
    for off in (1, 1 + st * 2 + (1 if size > 16 else 0)) if COVER != "checker" else ():
        y_left = y1 - off
        parts.append(f'<path fill="{STRIPE}" d="M{x0} {y_left} L{x1} {y_left - slope * (x1 - x0)} '
                     f'L{x1} {y_left - slope * (x1 - x0) - st * 1.25} L{x0} {y_left - st * 1.25} Z"/>')
    if opened:
        parts.append(f'<rect x="{x0 + 1}" y="{y0 - 2}" width="{x1 - x0 - 3}" height="3" fill="{PAPER}"/>')
        parts.append(f'<rect x="{x0}" y="{y0 - 3}" width="{x1 - x0}" height="1" fill="{SIDE}"/>')
    else:
        # the flap: the binder's colour over the stripes, its edge a shade and a white piping line
        parts.append(f'<path fill="#000" fill-opacity="0.18" d="M{x0} {y0 + fh} H{x1} V{y0 + fh + 1} H{x0} Z"/>')
        parts.append(f'<path fill="{F}" d="M{x0} {y0} H{x1 - r} Q{x1} {y0} {x1} {y0 + r} V{y0 + fh} H{x0} Z"/>')
        slope2 = slope
        for off in (1, 1 + st * 2 + (1 if size > 16 else 0)) if COVER != "checker" else ():   # stripes, across the flap
            y_left = y1 - off
            ys = [y_left - slope2 * (x - x0) for x in (x0, x1)]
            parts.append(f'<path fill="{STRIPE}" clip-path="url(#flap)" d="M{x0} {ys[0]} L{x1} {ys[1]} '
                         f'L{x1} {ys[1] - st * 1.25} L{x0} {ys[0] - st * 1.25} Z"/>')
        parts.append(f'<rect x="{x0 + 1}" y="{y0 + fh - 2}" width="{x1 - x0 - 2}" height="1" fill="{RING}" fill-opacity="0.9"/>')
    # Mint-Y's picture at its own size, on whole pixels at the cover's lower right
    # (the 80s binder: Mint-Y's 16px picture, centred above the band)
    pic_size = 16 if COVER == "checker" else size
    found = compose.mint_picture(name, pic_size)
    pic = ""
    if found is not None:
        root, (px0, py0, px1, py1) = found
        mvb = compose.viewbox(root, pic_size)
        if COVER == "checker":
            cx, cy = (x0 + x1) / 2, (y0 + fh + band_top) / 2 + 0.5
        else:
            cx = (x1 + x0 + (x1 - x0) * 0.35) / 2
            cy = (y0 + fh + y1) / 2 + 0.5
        dx = round(cx - ((px0 + px1) / 2 - mvb[0]))
        dy = round(cy - ((py0 + py1) / 2 - mvb[1]))
        inner = re.sub(MINT_EMBLEM, EMBLEM, ET.tostring(root, encoding="unicode"), flags=re.I)
        nested = ET.Element(f"{{{SVG}}}svg", {"x": str(dx), "y": str(dy), "width": str(pic_size),
                                            "height": str(pic_size),
                                            "viewBox": " ".join(f"{v:g}" for v in mvb), "overflow": "visible"})
        for child in list(ET.fromstring(inner)):
            nested.append(child)
        pic = ET.tostring(nested, encoding="unicode")
    if name == "user-desktop":      # our monitor, on whole pixels
        mw, mh = (7, 5) if size == 16 else (9, 6)
        if COVER == "checker":
            mw, mh = 7, 5
            mx, my = round((x0 + x1) / 2 - mw / 2), round((y0 + fh + band_top) / 2 - mh / 2 - 0.5)
        else:
            mx = round((x1 + x0 + (x1 - x0) * 0.35) / 2 - mw / 2)
            my = round((y0 + fh + y1) / 2 - mh / 2 - 0.5)
        pic = (f'<path fill="{EMBLEM}" fill-rule="evenodd" d="M{mx} {my} h{mw} v{mh} h{-mw} Z '
               f'M{mx + 1} {my + 1} v{mh - 2} h{mw - 2} v{-(mh - 2)} Z"/>'
               f'<rect fill="{EMBLEM}" x="{mx + mw // 2 - 1}" y="{my + mh}" width="{3 if mw > 7 else 2}" height="1"/>')
    defs = f'<defs><clipPath id="flap"><rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{fh}"/></clipPath></defs>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="{XLINK}" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}" version="1.1">{defs}{"".join(parts)}{pic}</svg>\n')


STYLES_MADE = {   # folder style: its cover, where it's written, its picture's box and centre
    "xl-big-baddy": ("stripes", 34.0, (W - 6 - 34.0 / 2 - 4, 6 + 34.0 / 2 + 3)),
    "xl-rad": ("checker", 21.0, (W / 2, (WAVE_HIGH + WAVE_AMP + H - FLAP) / 2 + 0.5)),
}


def main() -> int:
    global COVER, OUT, PIC, PIC_AT
    for style, (COVER, PIC, PIC_AT) in STYLES_MADE.items():
        OUT = ROOT / "data" / "icons" / style / "places"
        make()
    return 0


def make() -> None:
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", XLINK)
    names = sorted(f.stem for f in compose.MINT.glob("48/*.svg"))
    count = 0
    for size in SIZES:
        for name in names:
            opened = name == "folder-drag-accept"
            svg = (binder_small if size in SMALL else binder3d)(name, size, opened)
            f = OUT / str(size) / f"{name}.svg"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(svg, encoding="utf-8")
            count += 1
    print(f"{count} icons written to {OUT}")


if __name__ == "__main__":
    sys.exit(main())
