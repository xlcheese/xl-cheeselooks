#!/usr/bin/env python3
"""Make the theme thumbnail master from xl_cheese's comet artwork.

    python3 tools/make_thumbnail.py        (needs Pillow and numpy)

Reads data/thumbnails/comet-source.webp (the comet: the icon's swirl with its
strands streaming left, on a transparent background) and writes
data/thumbnails/comet.png: 120x35, Mint's Themes settings thumbnail size,
filling the width (a little of the upper-left wisps trimmed, the swirl whole).

The artwork was painted for a white background, so its wisp tips fade to near
white and showed as white streaks on dark buttons: near-white parts are made
see-through (their colour without the white); coloured strands stay as painted.

At Apply, cheeselooks/thumbnail.py recolours this master toward the theme's
accent and writes it as the gtk-3.0, cinnamon and metacity-1 thumbnails.
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "thumbnails" / "comet-source.webp"
OUT = ROOT / "data" / "thumbnails" / "comet.png"
W, H = 120, 35
ART = (0, 249, 1449, 803)          # the artwork's box in the source


def main() -> None:
    im = np.asarray(Image.open(SRC).convert("RGBA")).astype(float) / 255
    rgb, a = im[..., :3], im[..., 3:4]
    shown = a * rgb + (1 - a)                       # as it looks on white
    alpha = (1 - shown).max(axis=2, keepdims=True)  # colour to alpha from white
    col = np.where(alpha > 1e-4, 1 - (1 - shown) / np.maximum(alpha, 1e-4), 0)
    white = shown.min(axis=2, keepdims=True)
    k = np.clip((white - 0.62) / 0.28, 0, 1)        # near white: see-through
    out_rgb = rgb * (1 - k) + col * k
    out_a = a * (1 - k) + alpha * k
    art = Image.fromarray((np.dstack([np.clip(out_rgb, 0, 1), np.clip(out_a, 0, 1)]) * 255)
                          .round().astype("uint8"), "RGBA").crop(ART)
    need = round(art.width * H / W)                 # fill the width
    top = art.height - need - 6
    thumb = art.crop((0, top, art.width, top + need)).resize((W, H), Image.LANCZOS)
    thumb.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
