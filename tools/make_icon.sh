#!/bin/sh
# Render the xl-Cheeselooks icon PNGs from data/icons/xl-cheeselooks.svg:
# the app icon, and the thumbnails Mint's Themes settings shows for each part
# of the theme (scaled to fit 112x80, so drawn at 224x160 for HiDPI).
# Needs: rsvg-convert (librsvg2-bin) and ImageMagick.
set -eu
cd "$(dirname "$0")/.."
python3 tools/make_icon.py
rsvg-convert -w 256 -h 256 data/icons/xl-cheeselooks.svg -o data/icons/xl-cheeselooks-256.png
rsvg-convert -w 150 -h 150 data/icons/xl-cheeselooks.svg -o /tmp/xl-swirl-150.png
for part in gtk-3.0 cinnamon metacity-1; do
  convert -size 224x160 xc:none /tmp/xl-swirl-150.png -gravity center -composite \
    "templates/$part/thumbnail.png"
done
rm -f /tmp/xl-swirl-150.png
echo "Wrote data/icons/xl-cheeselooks-256.png and the theme thumbnails"
