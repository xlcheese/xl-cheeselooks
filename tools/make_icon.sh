#!/bin/sh
# Render the xl-Cheeselooks icon PNGs from data/icons/xl-cheeselooks.svg:
# the app icon.
# Needs: rsvg-convert (librsvg2-bin) and ImageMagick.
set -eu
cd "$(dirname "$0")/.."
python3 tools/make_icon.py
rsvg-convert -w 256 -h 256 data/icons/xl-cheeselooks.svg -o data/icons/xl-cheeselooks-256.png
echo "Wrote data/icons/xl-cheeselooks-256.png"
# (the theme thumbnails come from tools/make_thumbnail.py: the comet)
