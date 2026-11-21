"""The theme's thumbnail (what Mint's Themes settings shows): the comet,
recoloured toward the theme's accent.

data/thumbnails/comet.png is the master (120x35, made by
tools/make_thumbnail.py from xl_cheese's artwork). At Apply each pixel's hue
is pulled most of the way to the accent's (KEEP of its distance kept, so the
comet keeps a little variety); lightness, saturation and transparency as
painted. So each xl-Cheeselooks theme in Mint's list shows its own colours.

Uses GdkPixbuf (part of every Mint desktop). Without it the master is used as
it is, rainbow and all.
"""

from __future__ import annotations

import colorsys
from pathlib import Path

from . import palette as pal
from . import paths

MASTER = Path("data") / "thumbnails" / "comet.png"
PARTS = ("gtk-3.0", "cinnamon", "metacity-1")      # the theme's parts Mint shows a thumbnail for
KEEP = 0.12          # how much of each colour's distance from the accent it keeps (0: all the accent)


def recolour_pixel(r: int, g: int, b: int, accent_hue: float) -> tuple[int, int, int]:
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    # each hue pulled most of the way to the accent's: colours near the accent
    # barely move, far ones keep a hint of themselves (the comet's variety)
    d = ((h - accent_hue + 0.5) % 1) - 0.5
    rr, gg, bb = colorsys.hls_to_rgb((accent_hue + d * KEEP) % 1, l, s)
    return round(rr * 255), round(gg * 255), round(bb * 255)


def render(accent: str, master: Path | None = None) -> bytes | None:
    """The thumbnail as PNG bytes, in the accent's colours; None without GdkPixbuf."""
    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf, GLib
    except (ImportError, ValueError):
        return None
    master = master or paths.data_dir() / MASTER
    pix = GdkPixbuf.Pixbuf.new_from_file(str(master))
    if not pix.get_has_alpha():
        pix = pix.add_alpha(False, 0, 0, 0)
    w, h, stride = pix.get_width(), pix.get_height(), pix.get_rowstride()
    data = bytearray(pix.get_pixels())
    hue = colorsys.rgb_to_hls(*(c / 255 for c in pal.to_rgb(accent)))[0]
    for y in range(h):
        row = y * stride
        for x in range(w):
            i = row + x * 4
            if data[i + 3]:
                data[i:i + 3] = bytes(recolour_pixel(data[i], data[i + 1], data[i + 2], hue))
    out = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(data)), GdkPixbuf.Colorspace.RGB,
                                          True, 8, w, h, stride)
    ok, buf = out.save_to_bufferv("png", [], [])
    return bytes(buf) if ok else None


def write(theme_dir: Path, accent: str) -> list[Path]:
    """Write the thumbnail into each part of a generated theme. The templates'
    own thumbnail (the rainbow master) stays where recolouring can't run."""
    png = render(accent)
    if png is None:
        return []
    written = []
    for part in PARTS:
        if (theme_dir / part).is_dir():
            target = theme_dir / part / "thumbnail.png"
            target.write_bytes(png)
            written.append(target)
    return written
