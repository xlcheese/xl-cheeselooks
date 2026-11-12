"""Tell Cinnamon, GTK apps and the window manager to pick up the new theme.

Rewriting files isn't enough: each part only reloads when its theme setting
changes. So for each setting that already points at our theme, switch it
away for a moment and back. That gives one short flicker.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time

# (schema, key, theme to switch to briefly, folder that must exist in the theme)
THEME_KEYS = (
    ("org.cinnamon.theme", "name", "Mint-Y", "cinnamon"),
    ("org.cinnamon.desktop.interface", "gtk-theme", "Mint-Y", "gtk-3.0"),
    ("org.cinnamon.desktop.wm.preferences", "theme", "Mint-Y", "metacity-1"),
)
LAYOUT_KEY = ("org.cinnamon.desktop.wm.preferences", "button-layout")
PANEL_HEIGHT_KEY = ("org.cinnamon", "panels-height")
# Mint's Themes settings: "Use overlay scroll bars"
OVERLAY_KEY = ("org.cinnamon.desktop.interface", "gtk-overlay-scrollbars")


def available() -> bool:
    return shutil.which("gsettings") is not None


def _run(*args: str) -> str | None:
    try:
        result = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def get(schema: str, key: str) -> str | None:
    value = _run("get", schema, key)
    if value is None:
        return None
    return value.strip("'\"")


def set_value(schema: str, key: str, value: str) -> bool:
    return _run("set", schema, key, value) is not None


def panel_height(default: int) -> int:
    """First panel's height from Cinnamon's Panel settings, e.g. ['1:40']."""
    if not available():
        return default
    raw = _run("get", *PANEL_HEIGHT_KEY)
    if raw:
        m = re.search(r"\d+:(\d+)", raw)
        if m:
            return int(m.group(1))
    return default


def overlay_scrollbars() -> bool | None:
    """Whether GTK apps use overlay (floating) scrollbars; None when unknown."""
    if not available():
        return None
    value = get(*OVERLAY_KEY)
    return None if value is None else value == "true"


def set_overlay_scrollbars(enabled: bool) -> str | None:
    """Match Mint's overlay-scrollbar switch to the Details choice. Returns a log line."""
    if not available() or overlay_scrollbars() in (None, enabled):
        return None
    set_value(*OVERLAY_KEY, "true" if enabled else "false")
    return f"overlay scroll bars turned {'on' if enabled else 'off'} (Details > Scrollbars)"


ADW_ACCENT_KEY = ("org.gnome.desktop.interface", "accent-color")


def set_adw_accent(name: str) -> str | None:
    """GNOME's named accent (GNOME 47+), for libadwaita apps that ignore custom CSS.
    Skipped quietly where the key doesn't exist (Mint 22 has GNOME 46 schemas)."""
    if not available():
        return None
    current = get(*ADW_ACCENT_KEY)
    if current is None or current == name:
        return None
    set_value(*ADW_ACCENT_KEY, name)
    return f"GNOME accent colour set to {name} (nearest to your accent)"


def apply(theme_name: str, button_layout: str | None = None, activate: bool = False,
          pause: float = 0.3, theme_dir=None) -> list[str]:
    """Reload (and optionally switch to) the theme. Returns what was done, for the log."""
    if not available():
        return ["gsettings not found: skipped reloading (not running on Cinnamon?)"]
    log = []
    if button_layout is not None and get(*LAYOUT_KEY) != button_layout:
        if set_value(*LAYOUT_KEY, button_layout):
            log.append(f"button layout set to {button_layout}")
    refresh_wm = False
    for schema, key, fallback, part in THEME_KEYS:
        if theme_dir is not None and not (theme_dir / part).is_dir():
            log.append(f"{schema} {key}: this version of the theme has no {part}/ yet, left alone")
            continue
        current = get(schema, key)
        if current is None:
            log.append(f"{schema} {key}: not available, skipped")
            continue
        if current == theme_name:
            set_value(schema, key, fallback)
            time.sleep(pause)
            set_value(schema, key, theme_name)
            log.append(f"reloaded {schema} {key}")
            if key == "gtk-theme":
                refresh_wm = True
        elif activate:
            set_value(schema, key, theme_name)
            log.append(f"switched {schema} {key} to {theme_name}")
        else:
            log.append(f"{schema} {key} is '{current}', not {theme_name}: left alone "
                       f"(use --activate to switch)")
    # Window border themes (ours or Mint-Y's) read their colors from the GTK
    # theme, but only when they load. Nudge the current one so it picks up the
    # new colors, unless it was already reloaded above.
    wm_schema, wm_key = "org.cinnamon.desktop.wm.preferences", "theme"
    current_wm = get(wm_schema, wm_key)
    if refresh_wm and current_wm and current_wm != theme_name:
        other = "Mint-X" if current_wm != "Mint-X" else "Mint-Y"
        set_value(wm_schema, wm_key, other)
        time.sleep(pause)
        set_value(wm_schema, wm_key, current_wm)
        log.append(f"refreshed window borders ({current_wm}) so title bars pick up the new colors")
    return log
