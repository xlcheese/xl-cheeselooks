"""Colors from a picture (the wallpaper, or any image): its main colors, most
vivid first, and the one that makes the best accent.

The picture is shrunk to about 64px, its pixels grouped by hue (24 steps
round the wheel) and lightness (dark, middle, light), and each group's
average color scored by how much of the picture it covers and how vivid it
is. Grey groups (little saturation) only count when the picture has nothing
else. Uses GdkPixbuf (part of every Mint desktop).
"""

from __future__ import annotations

import colorsys
import math
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import palette as pal

SAMPLE = 64            # the picture is read at about this size
HUES = 24              # hue groups round the wheel
GREY = 0.12            # below this saturation a pixel counts as grey


def colors(path: Path, count: int = 6) -> list[str]:
    """The picture's main colors as #RRGGBB, most vivid (and most present) first."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), SAMPLE, SAMPLE, True)
    n = pix.get_n_channels()
    data, stride = pix.get_pixels(), pix.get_rowstride()
    groups: dict[tuple, list[float]] = {}
    for y in range(pix.get_height()):
        for x in range(pix.get_width()):
            i = y * stride + x * n
            if n == 4 and data[i + 3] < 128:
                continue
            r, g, b = data[i] / 255, data[i + 1] / 255, data[i + 2] / 255
            h, l, s = colorsys.rgb_to_hls(r, g, b)
            key = ("grey", min(2, int(l * 3))) if s < GREY else (int(h * HUES) % HUES, min(2, int(l * 3)))
            acc = groups.setdefault(key, [0.0, 0.0, 0.0, 0.0])
            acc[0] += r; acc[1] += g; acc[2] += b; acc[3] += 1
    found = []
    for key, (r, g, b, c) in groups.items():
        r, g, b = r / c, g / c, b / c
        _h, l, s = colorsys.rgb_to_hls(r, g, b)
        vivid = s * (1 - abs(l - 0.5) * 1.4)             # saturated, and not near black or white
        found.append((math.sqrt(c) * (0.15 + vivid), key[0] == "grey",
                      pal.from_rgb(r * 255, g * 255, b * 255)))
    found.sort(key=lambda f: (f[1], -f[0]))              # colors before greys, best first
    out: list[str] = []
    for _score, _grey, c in found:
        if all(_distance(c, o) > 0.12 for o in out):     # no near-duplicates
            out.append(c)
        if len(out) == count:
            break
    return out


def _distance(a: str, b: str) -> float:
    ra, ga, ba = (v / 255 for v in pal.to_rgb(a))
    rb, gb, bb = (v / 255 for v in pal.to_rgb(b))
    return math.sqrt((ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2)


def accent(found: list[str]) -> str | None:
    """The best accent among a picture's colors: the most vivid, brought into a
    usable lightness (an accent too pale or too dark doesn't read as one)."""
    best = None
    for c in found:
        h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in pal.to_rgb(c)))
        if s >= GREY:
            best = (h, l, s)
            break
    if best is None:
        return None
    h, l, s = best
    l = min(0.62, max(0.42, l))                          # usable as an accent face
    s = max(0.45, s)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return pal.from_rgb(r * 255, g * 255, b * 255)


def wallpaper() -> Path | None:
    """The current Cinnamon wallpaper, if it's a file that exists."""
    from . import reload
    if not reload.available():
        return None
    uri = reload.get("org.cinnamon.desktop.background", "picture-uri") or ""
    uri = uri.strip("'\"")
    path = Path(unquote(urlparse(uri).path)) if uri.startswith("file://") else Path(uri) if uri else None
    return path if path and path.is_file() else None
