"""GTK 4 / libadwaita colours: a marked block in ~/.config/gtk-4.0/gtk.css.

libadwaita apps ignore GTK themes, but every GTK 4 app loads the user's
gtk.css, and libadwaita takes its colours from named colours that file can
redefine. So the generator keeps one block there, between markers, and never
touches anything else in the file. A backup is made the first time.

    libadwaita 1.5 and older   named colours (@define-color accent_bg_color ...)
    libadwaita 1.6 and newer   CSS variables (:root { --accent-bg-color: ... })

Both are written when the installed libadwaita is 1.6 or newer; older GTK 4
doesn't understand the variables and would warn every time an app starts.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from . import palette as pal
from . import render

BEGIN = "/* xl-cheeselooks begin */"
END = "/* xl-cheeselooks end */"
_BLOCK = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
_DEFINE = re.compile(r"^@define-color (\w+) (.+);$", re.M)


def readable_on(color: str, background: str, target: float = 4.5) -> str:
    """`color`, darkened (light background) or lightened (dark) until it reads as text."""
    dark_bg = pal.luminance(background) < 0.18
    out = color
    for step in range(1, 21):
        if pal.contrast(out, background) >= target:
            break
        out = pal.lighter(color, step * 0.05) if dark_bg else pal.darker(color, step * 0.05)
    return out


# libadwaita's own success and warning colours (green_4, yellow_5)
SUCCESS, WARNING = "#2EC27E", "#E5A50A"


def tokens(t: dict[str, str]) -> dict[str, str]:
    dark = pal.luminance(t["bg"]) < 0.18
    return {
        "adw.accent_text": readable_on(t["accent"], t["bg"]),
        "adw.destructive_text": readable_on(t["destructive"], t["bg"]),
        "adw.success_bg": SUCCESS,
        "adw.success_text": readable_on(SUCCESS, t["bg"]),
        "adw.warning_bg": WARNING,
        "adw.warning_text": readable_on(WARNING, t["bg"]),
        # shadows and separators: soft text-coloured on light themes, black on dark
        "adw.shade": "rgba(0, 0, 0, 0.36)" if dark else pal.rgba(t["text"], 0.07),
        "adw.shade_strong": "rgba(0, 0, 0, 0.9)" if dark else pal.rgba(t["text"], 0.12),
        "adw.scrollbar_outline": "rgba(0, 0, 0, 0.5)" if dark else "#FFFFFF",
    }


def libadwaita_version() -> tuple[int, int] | None:
    """Installed libadwaita (from the package manager), or None if unknown."""
    if not shutil.which("dpkg-query"):
        return None
    try:
        out = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "libadwaita-1-0"],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.match(r"(?:\d+:)?(\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else None


ASSETS = "xl-cheeselooks-assets"     # beside gtk.css: the pictures the full styling uses


def full_css(templates_dir: Path, t: dict[str, str]) -> str:
    """Full styling (Integration → "Full styling for libadwaita apps"): our whole
    GTK 4 layer and the libadwaita additions, for apps that ignore the theme
    (Flatpak libadwaita apps bring their own, upstream libadwaita). Its
    pictures are referred to in ASSETS beside gtk.css (copy_assets)."""
    parts = []
    for rel in ("gtk-4.0/xl.css.tmpl", "libadwaita-1.5/adw-extra.part"):
        f = templates_dir / rel
        text = render.expand_includes(f.read_text(encoding="utf-8"), f.parent)
        parts.append(render.render_text(text, t, str(f)))
    # This file outranks an app's own CSS, so a button the app coloured itself
    # (with its own class) gets our face; give it our text colour too, or the
    # app's (white on its purple) stays, unreadable on our face. As unspecific
    # as can be, so our own rules (header bars, accent buttons) still win;
    # "opaque" buttons are libadwaita's way to keep an app's colour, and do.
    safety = f"button:not(.opaque) {{ color: {t['text']}; }}\n"
    css = safety + "\n".join(parts) + _window_button_margins(t)
    return css.replace('url("assets/', f'url("{ASSETS}/').replace("url('assets/", f"url('{ASSETS}/")


# Current libadwaita: header bars are 47px with 6px padding above and 7 below,
# and newer releases stretch the window buttons to fill the 34px between
# (xl_cheese's Flatpak Calculator: 33px buttons for a 26px style).
ADW_HEADER_CONTENT = 34


def _window_button_margins(t: dict[str, str]) -> str:
    """Vertical margins that bring a stretched window button back to its
    style's height; where buttons aren't stretched (Mint's own libadwaita)
    they only fill space that was there anyway."""
    m = re.search(r"windowcontrols > button:not\(\.osd\) \{[^}]*?min-height: (\d+)px", t.get("titlebuttons4.css", ""))
    if not m:
        return ""
    height = int(m.group(1)) + 2                 # and the 1px border above and below
    margin = max(0, (ADW_HEADER_CONTENT - height) // 2)
    if not margin:
        return ""
    return ("\n/* window buttons: their style's height, where libadwaita stretches them */\n"
            f"windowcontrols > button:not(.osd) {{ margin-top: {margin}px; margin-bottom: {margin}px; }}\n")


def asset_names(css: str) -> list[str]:
    return sorted(set(re.findall(re.escape(ASSETS) + r"/([\w.-]+)", css)))


def copy_assets(css: str, theme_dir: Path, gtk_css: Path) -> None:
    """The full styling's pictures, from the built theme, beside gtk.css (a
    Flatpak app sees that folder through the Flatpak apps switch)."""
    dest = gtk_css.parent / ASSETS
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in asset_names(css):
        src = theme_dir / "gtk-4.0" / "assets" / name
        if src.exists():
            shutil.copy2(src, dest / name)


def remove_assets(gtk_css: Path) -> None:
    dest = gtk_css.parent / ASSETS
    if dest.exists():
        shutil.rmtree(dest)


def block(templates_dir: Path, t: dict[str, str], css_variables: bool, full: bool = False) -> str:
    """The marked block: named colours, plus :root variables for libadwaita 1.6+,
    plus (full) our whole GTK 4 layer."""
    part = templates_dir / "libadwaita.css.part"
    text = render.expand_includes(part.read_text(encoding="utf-8"), part.parent)
    css = render.render_text(text, t, str(part))
    if css_variables:
        names = "\n".join(f"  --{n.replace('_', '-')}: {v};" for n, v in _DEFINE.findall(css))
        css += f"/* libadwaita 1.6 and newer */\n:root {{\n{names}\n}}\n"
    if full:
        css += ("\n/* Full styling for libadwaita apps (Integration): the theme's GTK 4 layer.\n"
                "   Note: this file outranks apps' own CSS. */\n" + full_css(templates_dir, t))
    return f"{BEGIN}\n{css.rstrip()}\n{END}\n"


def write(path: Path, new_block: str | None) -> str:
    """Put `new_block` in place of ours (None removes it). Returns what was done."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    had = bool(_BLOCK.search(text))
    if new_block is None:
        if not had:
            return ""
        path.write_text(_BLOCK.sub("", text), encoding="utf-8")
        return f"removed the libadwaita colours from {path}"
    backup = path.with_name(path.name + ".xl-cheeselooks-backup")
    if text and not had and not backup.exists():
        shutil.copy2(path, backup)        # the user's own file, before we first touch it
    if had:
        updated = _BLOCK.sub(lambda _m: new_block, text, count=1)
    else:
        updated = (text.rstrip("\n") + "\n\n" if text.strip() else "") + new_block
    if updated == text:
        return ""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(updated, encoding="utf-8")
    tmp.replace(path)
    return f"{'updated' if had else 'added'} the libadwaita colours in {path}"
