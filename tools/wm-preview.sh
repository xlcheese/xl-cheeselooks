#!/bin/bash
# Screenshot the window borders (metacity-1/) of a generated theme.
# Usage: tools/wm-preview.sh THEME_DIR OUTPUT_PREFIX
#   writes OUTPUT_PREFIX-rest.png and OUTPUT_PREFIX-hover.png (pointer over the
#   focused window's maximize button; set HOVER="x y" to move it) and prints
#   Metacity's warnings about the theme.
# Needs: Xvfb, xdotool, ImageMagick (import), dbus-run-session, metacity
# (GNOME's window manager reads the same theme format as Cinnamon's Muffin),
# and python3 with PyGObject.
set -u
here=$(cd "$(dirname "$0")" && pwd)
theme=$(cd "$1" && pwd); out=$2
py=${PYTHON:-python3}
work=$(mktemp -d)
trap 'rm -rf -- "${work:?}"' EXIT
mkdir -p "$work/themes" "$work/cfg"
ln -s "$theme" "$work/themes/xl-Cheeselooks"
cat > "$work/windows.py" <<'EOF'
import gi, sys
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
for title, x in (("Focused window", 20), ("Other window", 400)):
    w = Gtk.Window(title=title); w.set_default_size(340, 150); w.move(x, 30)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    bar = Gtk.MenuBar()
    for label in ("File", "Edit", "View"):
        bar.append(Gtk.MenuItem(label=label))
    box.pack_start(bar, False, False, 0)
    box.pack_start(Gtk.Label(label="content"), True, True, 0)
    w.add(box); w.show_all()
GLib.timeout_add_seconds(int(sys.argv[1]), Gtk.main_quit)
Gtk.main()
EOF
export DISPLAY=:$((80 + $$ % 9)) XDG_DATA_HOME=$work XDG_CONFIG_HOME=$work/cfg \
       GTK_THEME=xl-Cheeselooks NO_AT_BRIDGE=1
Xvfb "$DISPLAY" -screen 0 780x240x24 >/dev/null 2>&1 & xvfb=$!
sleep 1
timeout 40 dbus-run-session -- bash -c "
gsettings set org.gnome.metacity.theme type metacity
gsettings set org.gnome.metacity.theme name xl-Cheeselooks
gsettings set org.gnome.desktop.wm.preferences button-layout ':minimize,maximize,close'
metacity --replace >'$work/wm.log' 2>&1 &
sleep 2
'$py' '$work/windows.py' 9 2>/dev/null &
sleep 3
xdotool search --name 'Focused window' windowactivate 2>/dev/null; sleep 1
import -window root '$out-rest.png'
xdotool mousemove ${HOVER:-300 51}; sleep 1
import -window root '$out-hover.png'
sleep 1
pkill -f '$work/windows.py'; pkill -f 'metacity --replace'
" >/dev/null 2>&1
kill "$xvfb" 2>/dev/null
grep -i "metacity-warning" "$work/wm.log" | grep -v "Buggy client" || true
