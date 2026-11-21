"""Let Flatpak apps see the theme (opt-in, undoable).

Flatpak apps run in a sandbox that can't read your home folder, so they can't
find ~/.themes (GTK 3 and GTK 4 themes) or ~/.config/gtk-4.0/gtk.css (the
libadwaita colours). One user-wide override gives every Flatpak app read-only
access to exactly those two places:

    flatpak override --user --filesystem=~/.themes:ro --filesystem=xdg-config/gtk-4.0:ro

Apps learn the theme's name from Cinnamon's settings (XSettings), so nothing
else is needed. Undo removes just those two entries from Flatpak's user-wide
override file, leaving any other overrides alone (`flatpak override --reset`
would wipe them all).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import paths

FILESYSTEMS = ("~/.themes:ro", "xdg-config/gtk-4.0:ro")
COMMAND = ["flatpak", "override", "--user"] + [f"--filesystem={f}" for f in FILESYSTEMS]


def available() -> bool:
    return shutil.which("flatpak") is not None


def overrides_file() -> Path:
    """Flatpak's user-wide override file (written by `flatpak override --user`)."""
    return paths._xdg("XDG_DATA_HOME", paths.HOME / ".local" / "share") / "flatpak" / "overrides" / "global"


def _read_filesystems(text: str) -> list[str]:
    in_context = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_context = stripped == "[Context]"
        elif in_context and stripped.startswith("filesystems="):
            return [f for f in stripped[len("filesystems="):].split(";") if f]
    return []


def granted() -> list[str]:
    """Which of our two entries are in the override file now."""
    f = overrides_file()
    current = _read_filesystems(f.read_text(encoding="utf-8")) if f.exists() else []
    return [fs for fs in FILESYSTEMS if fs in current]


def added_file() -> Path:
    """Which entries enable() added (ones you already had are never removed)."""
    return paths.config_dir() / "flatpak-added"


def enable() -> list[str]:
    """Run the override command; remember which entries it added. Returns them."""
    before = granted()
    result = subprocess.run(COMMAND, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "flatpak override failed")
    new = [fs for fs in FILESYSTEMS if fs not in before]
    if new:
        f = added_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        old = f.read_text(encoding="utf-8").split() if f.exists() else []
        f.write_text("\n".join(dict.fromkeys(old + new)) + "\n", encoding="utf-8")
    return new


def remove_ours(text: str, ours: tuple[str, ...] | list[str] = FILESYSTEMS) -> str:
    """The override file's text without `ours`; everything else kept."""
    out = []
    in_context = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            in_context = stripped == "[Context]"
        elif in_context and stripped.startswith("filesystems="):
            kept = [f for f in stripped[len("filesystems="):].split(";") if f and f not in ours]
            if not kept:
                continue                          # the line held only ours
            line = "filesystems=" + ";".join(kept) + ";\n"
        out.append(line)
    return "".join(out)


def disable() -> bool:
    """Remove the entries enable() added. Returns True if anything changed."""
    record = added_file()
    ours = record.read_text(encoding="utf-8").split() if record.exists() else []
    if record.exists():
        record.unlink()
    f = overrides_file()
    if not ours or not f.exists():
        return False
    text = f.read_text(encoding="utf-8")
    new = remove_ours(text, ours)
    if new == text:
        return False
    f.write_text(new, encoding="utf-8")
    return True
