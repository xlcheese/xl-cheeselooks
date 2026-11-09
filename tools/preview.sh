#!/bin/sh
# Screenshot the showcase windows with a theme, on a virtual display.
# Usage: tools/preview.sh THEME_DIR OUTPUT.png [extra showcase args]
# Needs: Xvfb, ImageMagick (import), python3 with PyGObject.
# Prints GTK's CSS warnings for the theme, if any.
set -eu
theme_dir=$(cd "$1" && pwd); out=$2; shift 2
name=$(basename "$theme_dir")
py=${PYTHON:-python3}
data=$(mktemp -d)
mkdir -p "$data/themes"
ln -s "$theme_dir" "$data/themes/$name"
display=:$((90 + $$ % 9))
Xvfb "$display" -screen 0 1260x600x24 >/dev/null 2>&1 &
xvfb=$!
trap 'kill $xvfb 2>/dev/null; rm -rf "$data"' EXIT
sleep 1
DISPLAY=$display XDG_DATA_HOME=$data GTK_THEME=$name NO_AT_BRIDGE=1 \
  "$py" "$(dirname "$0")/showcase.py" --quit 4 "$@" 2>"$data/log" &
app=$!
sleep 3
DISPLAY=$display import -window root "$out"
wait $app || true
grep -iE "theme|css|warning|error" "$data/log" | grep -v "dbind" | head -40 || true
