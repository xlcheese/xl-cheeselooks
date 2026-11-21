#!/usr/bin/env python3
"""Torture-test styles: build each one against a light theme, a dark theme and
a colored title bar, check GTK accepts the CSS and the key colors read, and
draw a contact sheet of a sample window in each.

    python3 tools/torture_test.py [STYLE_DIR ...] [--out sheet.png]

With no style folders, every built-in style is tested. Needs Xvfb, ImageMagick's import and convert, and Python with PyGObject (GTK 3).
Prints problems and writes the sheet (default: torture.png).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cheeselooks import install, palette, settings, styles, tokens  # noqa: E402

SETUPS = {
    "theme": {},          # the style's own shipped theme
    "dark": {"global": {"bg": "#2B2B2B", "text": "#E6E6E6", "accent": "#5A9BE0"}},
    "title bar": {"window_borders": {"separate_colors": True, "title_bar": "#3A5A9A",
                                     "title_text": "#FFFFFF", "button_style": "drawn"}},
}
# pairs that must read: (token, token, minimum contrast)
READABLE = [("text", "bg", 4.5), ("text", "base", 4.5), ("accent_fg", "accent", 2.2),
            ("wb.text", "wb.title", 4.5), ("wbp.text", "wbp.button", 3.0),
            ("menu.text", "menu.menu_bg", 4.5), ("panel.text", "panel.panel", 4.5)]

SAMPLE = r'''
import gi, sys
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
w = Gtk.Window(); w.set_default_size(360, 200)
hb = Gtk.HeaderBar(show_close_button=True); hb.set_decoration_layout(":minimize,maximize,close")
st = Gtk.Stack()
for n in ("One", "Two"): st.add_titled(Gtk.Label(label=n), n, n)
sw = Gtk.StackSwitcher(); sw.set_stack(st); hb.set_custom_title(sw)
hb.pack_start(Gtk.Button.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.BUTTON))
w.set_titlebar(hb)
v = Gtk.Box(orientation=1, spacing=8); v.set_border_width(10)
row = Gtk.Box(spacing=6)
row.pack_start(Gtk.Button(label="Button"), False, False, 0)
s = Gtk.Button(label="OK"); s.get_style_context().add_class("suggested-action"); row.pack_start(s, False, False, 0)
l = Gtk.Box(); l.get_style_context().add_class("linked")
for t in ("Left", "Mid", "Right"): l.pack_start(Gtk.Button(label=t), False, False, 0)
row.pack_start(l, False, False, 0)
v.pack_start(row, False, False, 0)
row2 = Gtk.Box(spacing=8)
e = Gtk.Entry(text="Some text"); row2.pack_start(e, True, True, 0)
c = Gtk.CheckButton(label="Check"); c.set_active(True); row2.pack_start(c, False, False, 0)
row2.pack_start(Gtk.Switch(active=True), False, False, 0)
v.pack_start(row2, False, False, 0)
nb = Gtk.Notebook()
for t in ("Tab", "Other"): nb.append_page(Gtk.Label(label=t + " page", margin=10), Gtk.Label(label=t))
v.pack_start(nb, True, True, 0)
w.add(v); w.show_all()
GLib.timeout_add_seconds(3, Gtk.main_quit); Gtk.main()
'''


def merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = merge(base.get(k, {}), v) if isinstance(v, dict) else v
    return out


PARSE = r'''
import gi, sys
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
prov = Gtk.CssProvider()
prov.connect("parsing-error", lambda _p, sec, err: print(
    f"{sec.get_file().get_basename() if sec.get_file() else ''}:{sec.get_start_line() + 1}: {err.message}"))
try:
    prov.load_from_path(sys.argv[1])
except Exception as exc:
    print(exc)
'''


def parse_errors(css: Path, env: dict) -> list[str]:
    """GTK's own parser, run where GTK has a display (no warnings)."""
    r = subprocess.run([sys.executable, "-c", PARSE, str(css)], env=env, capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def own_theme(style_name: str) -> dict:
    """The first built-in theme that uses this style: its colors are the "light" setup."""
    import json
    for f in sorted((ROOT / "data" / "themes").glob("*.json")):
        s = json.loads(f.read_text()).get("settings", {})
        if s.get("style", {}).get("name") == style_name:
            return s
    return {}


def shoot(theme: Path, out: Path, display: int, work: Path, problems: list, label: str) -> None:
    data = work / f"data-{display}"
    (data / "themes").mkdir(parents=True, exist_ok=True)
    link = data / "themes" / "xl-Cheeselooks"
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(theme)
    sample = work / "sample.py"
    sample.write_text(SAMPLE)
    env = {**os.environ, "DISPLAY": f":{display}", "XDG_DATA_HOME": str(data),
           "GTK_THEME": "xl-Cheeselooks", "NO_AT_BRIDGE": "1"}
    x = subprocess.Popen(["Xvfb", f":{display}", "-screen", "0", "380x250x24"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.2)
        problems += [f"{label}: GTK 3 CSS: {e}" for e in parse_errors(theme / "gtk-3.0" / "gtk.css", env)]
        app = subprocess.Popen([sys.executable, str(sample)], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.2)
        subprocess.run(["import", "-window", "root", str(out)], env=env, check=False)
        app.wait(timeout=10)
    finally:
        x.terminate()
        x.wait()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("styles", nargs="*", type=Path)
    ap.add_argument("--out", type=Path, default=Path("torture.png"))
    a = ap.parse_args()
    dirs = a.styles or sorted(p for p in (ROOT / "styles").iterdir() if (p / "style.toml").exists())
    problems, rows = [], []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        display = 70 + os.getpid() % 20
        for d in dirs:
            st = styles.load(d)
            shots = []
            own = own_theme(st.name)
            for label, over in SETUPS.items():
                data = settings.from_dict(merge(merge(settings.DEFAULTS, own), over))
                data["style"]["name"] = st.name
                t = tokens.build(data, st)
                for fg, bg, need in READABLE:
                    if fg in t and bg in t and palette.is_hex(t[fg]) and palette.is_hex(t[bg]):
                        c = palette.contrast(t[fg], t[bg])
                        if c < need:
                            problems.append(f"{st.name} ({label}): {fg} on {bg} is {c:.1f}:1 (wants {need})")
                theme = work / f"{d.name}-{label.replace(' ', '-')}"
                install.build(ROOT / "templates", t, theme)
                shot = work / f"{theme.name}.png"
                shoot(theme, shot, display, work, problems, f"{st.name} ({label})")
                display += 1
                shots.append(str(shot))
            row = work / f"row-{d.name}.png"
            subprocess.run(["convert", *shots, "+append", "-gravity", "West", "-background", "#888888",
                            "-splice", "150x0", "-pointsize", "14", "-annotate", "+8+0", st.name, str(row)],
                           check=False)
            rows.append(str(row))
        subprocess.run(["convert", *rows, "-append", str(a.out)], check=False)
    for p in problems:
        print(p)
    print(f"{len(dirs)} style(s), {len(problems)} problem(s); sheet: {a.out}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
