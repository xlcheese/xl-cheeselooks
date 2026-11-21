"""User settings: defaults, loading, validation and presets.

Stored as JSON in ~/.config/xl-cheeselooks/settings.json. A value of None
means "follow Global" (docs/design-spec.md, section 2).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from . import palette, shape, titlebuttons

SETTINGS_VERSION = 1

DEFAULTS: dict[str, Any] = {
    "version": SETTINGS_VERSION,
    "theme": "xl-Cheeselooks",     # the theme these settings came from, or "Custom"
    "global": {
        "accent": "#FF8467", "bg": "#F5F5F5", "text": "#303030",
        "size": shape.SIZE_DEFAULT, "roundness": 15, "gradient": 10,
        "hover_in_ms": 50, "hover_out_ms": 125, "hover_strength": 50,
    },
    "style": {"name": "xl-Cheeselooks", "depth": 50,
              "unfocused_depth": 70},   # % of the button layers kept in unfocused windows
    "panel": {
        "separate_colors": False, "accent": None, "bg": None, "text": None,
        "label_weight": "bold",
        "panel_opacity": 70, "menu_opacity": 94, "notification_opacity": 94,
        "panel_height": None,   # None: leave Cinnamon's panel height as it is
        "panel_shape": {"follow_global": True, "roundness": 15, "gradient": 10},
        # menus follow Global's gradient; item_roundness: Cinnamon's main menu's items
        "menu_shape": {"follow_global": True, "roundness": 15, "item_roundness": 15},
    },
    "window_borders": {
        "separate_colors": False, "title_bar": None, "title_text": None, "border": None,
        "title_bar_height": 44, "border_width": 1, "title_gradient": 30,
        "window_roundness": None,   # None: follows Global roundness
        "round_bottom": False,      # round the bottom corners too (GTK 4; GTK 3 header bar windows)
        "button_layout": "right", "button_style": "flat",
        "button_roundness": None,   # None: the button style's own roundness
        "button_spacing": None,     # None: the button style's own spacing (px)
        "button_glyphs": None,      # None: the button style's own glyph set
    },
    "terminal": {"separate_colors": False, "bg": None, "text": None},
    "details": {
        "tooltips": {"custom": False, "bg": None, "text": None},
        "scrollbars": {"custom": False, "mode": "overlay", "roundness": 100,
                       "width": None},   # None: 6 overlay (expanded), 10 classic
        "sliders": {"custom": False, "roundness": 100},
        "switches": {"custom": False, "roundness": 100},
        "focus_ring": {"custom": False, "color": None, "width": 1, "style": "dashed"},
    },
    # Icons tab: folders in your colors (icons.py). Off by default: a first look
    # at the Tool shouldn't change icons people chose in Mint's settings
    "icons": {"enabled": False, "style": "mint-y", "folder_color": None, "second_color": None},
    "integration": {"libadwaita_colors": True, "libadwaita_accent": True,
                    "libadwaita_full": False,  # our whole GTK 4 layer for apps that ignore the theme (gtk4.py)
                    "flatpak_access": True,  # Flatpak apps can read the theme (flatpak.py); on, as the others
                    "qt_colors": True,       # Qt apps (VLC...) in the theme's colours (qt.py);
                    "editor_colors": True,   # Xed, gedit, Meld: a colour scheme from the theme (editor.py);
                    "watch_theme": True},    # take those out of apps when another theme is picked (watch.py)
                                             # on: most people wouldn't know to look for it
}

# (path, kind, extra) — kind is one of: color, color?, int, bool, choice
_RULES: list[tuple[tuple[str, ...], str, Any]] = [
    (("global", "accent"), "color", None),
    (("global", "bg"), "color", None),
    (("global", "text"), "color", None),
    (("global", "size"), "int", shape.SIZE_RANGE),
    (("global", "roundness"), "int", (0, 100)),
    (("global", "gradient"), "int", (0, 100)),
    (("global", "hover_in_ms"), "int", (0, 200)),
    (("global", "hover_out_ms"), "int", (0, 400)),
    (("global", "hover_strength"), "int", (0, 100)),
    (("style", "depth"), "int", (0, 100)),
    (("style", "unfocused_depth"), "int", (0, 100)),
    (("panel", "separate_colors"), "bool", None),
    (("panel", "accent"), "color?", None),
    (("panel", "bg"), "color?", None),
    (("panel", "text"), "color?", None),
    (("panel", "label_weight"), "choice", ("bold", "regular", "light")),
    (("panel", "panel_opacity"), "int", (30, 100)),
    (("panel", "menu_opacity"), "int", (30, 100)),
    (("panel", "notification_opacity"), "int", (30, 100)),
    (("panel", "panel_height"), "int?", (20, 60)),
    (("panel", "panel_shape", "follow_global"), "bool", None),
    (("panel", "panel_shape", "roundness"), "int", (0, 100)),
    (("panel", "panel_shape", "gradient"), "int", (0, 100)),
    (("panel", "menu_shape", "follow_global"), "bool", None),
    (("panel", "menu_shape", "roundness"), "int", (0, 100)),
    (("panel", "menu_shape", "item_roundness"), "int", (0, 100)),
    (("window_borders", "separate_colors"), "bool", None),
    (("window_borders", "title_bar"), "color?", None),
    (("window_borders", "title_text"), "color?", None),
    (("window_borders", "border"), "color?", None),
    (("window_borders", "title_bar_height"), "int", (30, 56)),
    (("window_borders", "border_width"), "int", (0, 6)),
    (("window_borders", "window_roundness"), "int?", (0, 100)),
    (("window_borders", "round_bottom"), "bool", None),
    (("window_borders", "title_gradient"), "int", (0, 100)),
    (("window_borders", "button_layout"), "choice", ("left", "right")),
    (("window_borders", "button_glyphs"), "choice?", tuple(titlebuttons.GLYPH_SET_NAMES)),
    (("window_borders", "button_style"), "choice", tuple(titlebuttons.STYLES)),
    (("window_borders", "button_roundness"), "int?", (0, 100)),
    (("window_borders", "button_spacing"), "int?", titlebuttons.SPACING_RANGE),
    (("terminal", "separate_colors"), "bool", None),
    (("terminal", "bg"), "color?", None),
    (("terminal", "text"), "color?", None),
    (("details", "tooltips", "custom"), "bool", None),
    (("details", "tooltips", "bg"), "color?", None),
    (("details", "tooltips", "text"), "color?", None),
    (("details", "scrollbars", "custom"), "bool", None),
    (("details", "scrollbars", "mode"), "choice", ("overlay", "classic")),
    (("details", "scrollbars", "roundness"), "int", (0, 100)),
    (("details", "scrollbars", "width"), "int?", (6, 16)),
    (("icons", "enabled"), "bool", None),
    (("icons", "style"), "choice", ("xl-big-baddy", "xl-rad", "claude", "mint-y", "yaru", "breeze")),
    (("icons", "folder_color"), "color?", None),
    (("icons", "second_color"), "color?", None),
    (("details", "sliders", "custom"), "bool", None),
    (("details", "sliders", "roundness"), "int", (0, 100)),
    (("details", "switches", "custom"), "bool", None),
    (("details", "switches", "roundness"), "int", (0, 100)),
    (("details", "focus_ring", "custom"), "bool", None),
    (("details", "focus_ring", "color"), "color?", None),
    (("details", "focus_ring", "style"), "choice", ("dashed", "dotted", "solid")),
    (("details", "focus_ring", "width"), "int", (0, 3)),
    (("integration", "libadwaita_colors"), "bool", None),
    (("integration", "libadwaita_accent"), "bool", None),
    (("integration", "libadwaita_full"), "bool", None),
    (("integration", "flatpak_access"), "bool", None),
    (("integration", "qt_colors"), "bool", None),
    (("integration", "editor_colors"), "bool", None),
    (("integration", "watch_theme"), "bool", None),
]


class SettingsError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _get(data: dict, path: tuple[str, ...]) -> Any:
    for key in path:
        data = data[key]
    return data


def _set(data: dict, path: tuple[str, ...], value: Any) -> None:
    for key in path[:-1]:
        data = data[key]
    data[path[-1]] = value


def validate(data: dict) -> list[str]:
    """Return a list of problems; empty means valid. Also normalizes colors in place."""
    problems = []
    for path, kind, extra in _RULES:
        name = ".".join(path)
        try:
            value = _get(data, path)
        except (KeyError, TypeError):
            problems.append(f"{name} is missing")
            continue
        if kind in ("color", "color?"):
            if value is None and kind == "color?":
                continue
            if not palette.is_hex(value):
                problems.append(f"{name} must be a hex color like #FA8562 (got {value!r})")
            else:
                _set(data, path, palette.normalize(value))
        elif kind in ("int", "int?"):
            if value is None and kind == "int?":
                continue
            lo, hi = extra
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
                problems.append(f"{name} must be a number from {lo} to {hi} (got {value!r})")
            else:
                _set(data, path, int(round(value)))
        elif kind == "bool":
            if not isinstance(value, bool):
                problems.append(f"{name} must be true or false (got {value!r})")
        elif kind in ("choice", "choice?"):
            if value is None and kind == "choice?":
                continue
            if value not in extra:
                problems.append(f"{name} must be one of {', '.join(extra)} (got {value!r})")
    if not isinstance(data.get("theme"), str):
        problems.append("theme must be text")
    if not isinstance(data.get("style", {}).get("name"), str):
        problems.append("style.name must be text")
    return problems


def from_dict(data: dict) -> dict:
    """Merge user data over defaults and validate. Raises SettingsError."""
    merged = _deep_merge(DEFAULTS, data or {})
    wb = merged.get("window_borders")
    g = merged.get("global")
    if isinstance(g, dict) and isinstance(g.get("size"), str) and g["size"] in shape.OLD_SIZES:
        g["size"] = shape.OLD_SIZES[g["size"]]           # Compact / Normal / Large before the slider
    if isinstance(g, dict) and isinstance(g.get("size"), (int, float)) and not isinstance(g["size"], bool):
        g["size"] = shape.size_value(g["size"])           # even heights only
    if isinstance(g, dict):          # hover ranges narrowed (0-300 / 0-800 before)
        for key, hi in (("hover_in_ms", 200), ("hover_out_ms", 400)):
            if isinstance(g.get(key), (int, float)) and not isinstance(g.get(key), bool):
                g[key] = max(0, min(hi, g[key]))
    if isinstance(wb, dict) and wb.get("button_style") in titlebuttons.OLD_NAMES:
        wb["button_style"] = titlebuttons.OLD_NAMES[wb["button_style"]]     # names before v1
    if isinstance(wb, dict) and wb.get("button_glyphs") == "theme":
        wb["button_glyphs"] = "regular"                                      # renamed
    merged["version"] = SETTINGS_VERSION
    problems = validate(merged)
    if problems:
        raise SettingsError(problems)
    return merged


# Sections that belong to your desktop, not to a look: picking a theme (or
# resetting to one) keeps yours. A theme file's own copy, if any, is ignored.
# (Paths: a whole section, or one setting in it.)
PER_USER = (("integration",), ("icons", "enabled"), ("icons", "style"))


def keep_per_user(new: dict, current: dict) -> dict:
    """`new` (a theme's settings) with `current`'s per-user sections and settings."""
    out = copy.deepcopy(new)
    for path in PER_USER:
        src, dst = current, out
        for k in path[:-1]:
            src, dst = src.get(k, {}), dst.setdefault(k, {})
        if path[-1] in src:
            dst[path[-1]] = copy.deepcopy(src[path[-1]])
    return out


def load(path: Path) -> dict:
    if not path.exists():
        return copy.deepcopy(DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SettingsError([f"{path} is not valid JSON: {exc}"]) from exc
    return from_dict(data)


def save(settings: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def apply_style_defaults(settings: dict, defaults: dict) -> dict:
    """Use a style's suggested [defaults] as the starting point (when the style is
    picked, on a fresh install, or on "reset to style defaults")."""
    out = copy.deepcopy(settings)
    g, p = out["global"], out["panel"]
    for key in ("roundness", "gradient"):
        if key in defaults:
            g[key] = defaults[key]
    for key in ("depth", "unfocused_depth"):
        if key in defaults:
            out["style"][key] = defaults[key]
    ps = p["panel_shape"]
    r, gr = defaults.get("panel_roundness"), defaults.get("panel_gradient")
    if r is None and gr is None:
        ps.update(follow_global=True, roundness=g["roundness"], gradient=g["gradient"])
    else:
        ps.update(follow_global=False, roundness=g["roundness"] if r is None else r,
                  gradient=g["gradient"] if gr is None else gr)
    ms = p["menu_shape"]          # menus follow Global's gradient (menu_gradient is ignored)
    r, ir = defaults.get("menu_roundness"), defaults.get("menu_item_roundness")
    if r is None and ir is None:
        ms.update(follow_global=True, roundness=g["roundness"], item_roundness=g["roundness"])
    else:
        ms.update(follow_global=False, roundness=g["roundness"] if r is None else r,
                  item_roundness=(r if r is not None else g["roundness"]) if ir is None else ir)
    for key in ("panel_opacity", "menu_opacity", "notification_opacity"):
        if key in defaults:
            p[key] = defaults[key]
    if "panel_label_weight" in defaults:
        p["label_weight"] = defaults["panel_label_weight"]
    return from_dict(out)


def apply_preset(settings: dict, preset: dict) -> dict:
    """Presets are partial settings files; merge them over the current settings."""
    preset = {k: v for k, v in preset.items() if k not in ("name", "version")}
    return from_dict(_deep_merge(settings, preset))
