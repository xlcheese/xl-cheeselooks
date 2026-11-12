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


def block(templates_dir: Path, t: dict[str, str], css_variables: bool) -> str:
    """The marked block: named colours, plus :root variables for libadwaita 1.6+."""
    part = templates_dir / "libadwaita.css.part"
    text = render.expand_includes(part.read_text(encoding="utf-8"), part.parent)
    css = render.render_text(text, t, str(part))
    if css_variables:
        names = "\n".join(f"  --{n.replace('_', '-')}: {v};" for n, v in _DEFINE.findall(css))
        css += f"/* libadwaita 1.6 and newer */\n:root {{\n{names}\n}}\n"
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
