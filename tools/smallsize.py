"""Shared by the import tools: sharp small sizes from a bigger drawing.

A folder drawn for one size and shrunk lands between pixels (soft edges) and
its pictures go thinner than a pixel. So at 16, 22 and 24px:

  snap()          a scale and offset, a little different across and down (a
                  few percent at most), that put the folder's outer edges, and
                  as near as can be its front's top, on whole pixels
  mint_picture()  Mint-Y's picture for the icon, drawn for that size, moved by
                  whole pixels to the centre of the front, in the style's
                  picture colour

First written for Adwaita (tools/import-adwaita-places.py, 20 Nov), shared
since Breeze needed the same (21 Nov).
"""
from __future__ import annotations

import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"

_spec = importlib.util.spec_from_file_location("compose", ROOT / "tools" / "compose-missing-places.py")
compose = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compose)
MINT_EMBLEM = "#" + compose.icons.STYLES["mint-y"]["source"]["emblem"]


def snap(box: tuple[float, float, float, float], front_top: float, drawn: int, size: int):
    """(sx, sy, tx, ty) mapping a drawing made for `drawn` px onto `size` px so
    the folder's box (left, top, right, bottom) lands on whole pixels."""
    left0, top0, right0, bottom0 = box
    k = size / drawn
    best = None
    for left in (round(left0 * k) + d for d in (-1, 0, 1)):
        for right in (round(right0 * k) + d for d in (-1, 0, 1)):
            for top in (round(top0 * k) + d for d in (-1, 0, 1)):
                for bottom in (round(bottom0 * k) + d for d in (-1, 0, 1)):
                    if not (0 <= left < right <= size and 0 <= top < bottom <= size):
                        continue
                    sx, sy = (right - left) / (right0 - left0), (bottom - top) / (bottom0 - top0)
                    front = top + (front_top - top0) * sy
                    cost = abs(sx / k - 1) + abs(sy / k - 1) + abs(sx - sy) / k + 0.05 * abs(front - round(front))
                    if best is None or cost < best[0]:
                        best = (cost, sx, sy, left - left0 * sx, top - top0 * sy)
    return best[1:]


def mint_picture(name: str, size: int, cx: float, cy: float, emblem: str) -> ET.Element | None:
    """Mint-Y's picture for `name` at `size`, centred near (cx, cy) by whole
    pixels, coloured `emblem`; None when Mint-Y has none for it."""
    found = compose.mint_picture(name, size)
    if found is None:
        return None
    pic, (x0, y0, x1, y1) = found
    vb = compose.viewbox(pic, size)
    dx = round(cx - ((x0 + x1) / 2 - vb[0]))
    dy = round(cy - ((y0 + y1) / 2 - vb[1]))
    inner = re.sub(MINT_EMBLEM, emblem, ET.tostring(pic, encoding="unicode"), flags=re.I)
    nested = ET.Element(f"{{{SVG}}}svg", {"x": str(dx), "y": str(dy), "width": str(size), "height": str(size),
                                        "viewBox": " ".join(f"{v:g}" for v in vb), "overflow": "visible"})
    for child in list(ET.fromstring(inner)):
        nested.append(child)
    return nested


def mint_names() -> list[str]:
    return sorted(f.stem for f in compose.MINT.glob("48/*.svg"))
