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
        "accent": "#FA8562", "bg": "#F5F5F5", "text": "#303030",
        "size": "normal", "roundness": 15, "gradient": 10,
        "hover_in_ms": 50, "hover_out_ms": 125, "hover_strength": 50,
    },
    "style": {"name": "xl-Cheeselooks", "depth": 50},
    "panel": {
        "separate_colors": False, "accent": None, "bg": None, "text": None,
        "label_weight": "bold",
        "panel_opacity": 70, "menu_opacity": 94,
        "panel_shape": {"follow_global": True, "roundness": 15, "gradient": 10},
        "menu_shape": {"follow_global": True, "roundness": 15, "gradient": 10},
    },
    "window_borders": {
        "separate_colors": False, "title_bar": None, "title_text": None, "border": None,
        "title_bar_height": 44, "border_width": 1, "title_gradient": 30,
        "button_layout": "right", "button_style": "flat",
    },
    "terminal": {"separate_colors": False, "bg": None, "text": None},
    "details": {
        "tooltips": {"custom": False, "bg": None, "text": None},
        "scrollbars": {"custom": False, "mode": "overlay", "roundness": 100},
        "sliders": {"custom": False, "roundness": 100},
        "switches": {"custom": False, "roundness": 100},
        "focus_ring": {"custom": False, "color": None, "width": 2},
    },
    "integration": {"libadwaita_colors": True, "libadwaita_accent": True, "flatpak_access": False},
}

# (path, kind, extra) — kind is one of: color, color?, int, bool, choice
_RULES: list[tuple[tuple[str, ...], str, Any]] = [
    (("global", "accent"), "color", None),
    (("global", "bg"), "color", None),
    (("global", "text"), "color", None),
    (("global", "size"), "choice", tuple(shape.SIZES)),
    (("global", "roundness"), "int", (0, 100)),
    (("global", "gradient"), "int", (0, 100)),
    (("global", "hover_in_ms"), "int", (0, 300)),
    (("global", "hover_out_ms"), "int", (0, 800)),
    (("global", "hover_strength"), "int", (0, 100)),
    (("style", "depth"), "int", (0, 100)),
    (("panel", "separate_colors"), "bool", None),
    (("panel", "accent"), "color?", None),
    (("panel", "bg"), "color?", None),
    (("panel", "text"), "color?", None),
    (("panel", "label_weight"), "choice", ("bold", "regular")),
    (("panel", "panel_opacity"), "int", (30, 100)),
    (("panel", "menu_opacity"), "int", (30, 100)),
    (("panel", "panel_shape", "follow_global"), "bool", None),
    (("panel", "panel_shape", "roundness"), "int", (0, 100)),
    (("panel", "panel_shape", "gradient"), "int", (0, 100)),
    (("panel", "menu_shape", "follow_global"), "bool", None),
    (("panel", "menu_shape", "roundness"), "int", (0, 100)),
    (("panel", "menu_shape", "gradient"), "int", (0, 100)),
    (("window_borders", "separate_colors"), "bool", None),
    (("window_borders", "title_bar"), "color?", None),
    (("window_borders", "title_text"), "color?", None),
    (("window_borders", "border"), "color?", None),
    (("window_borders", "title_bar_height"), "int", (30, 56)),
    (("window_borders", "border_width"), "int", (0, 6)),
    (("window_borders", "title_gradient"), "int", (0, 100)),
    (("window_borders", "button_layout"), "choice", ("left", "right")),
    (("window_borders", "button_style"), "choice", tuple(titlebuttons.STYLES)),
    (("terminal", "separate_colors"), "bool", None),
    (("terminal", "bg"), "color?", None),
    (("terminal", "text"), "color?", None),
    (("details", "tooltips", "custom"), "bool", None),
    (("details", "tooltips", "bg"), "color?", None),
    (("details", "tooltips", "text"), "color?", None),
    (("details", "scrollbars", "custom"), "bool", None),
    (("details", "scrollbars", "mode"), "choice", ("overlay", "classic")),
    (("details", "scrollbars", "roundness"), "int", (0, 100)),
    (("details", "sliders", "custom"), "bool", None),
    (("details", "sliders", "roundness"), "int", (0, 100)),
    (("details", "switches", "custom"), "bool", None),
    (("details", "switches", "roundness"), "int", (0, 100)),
    (("details", "focus_ring", "custom"), "bool", None),
    (("details", "focus_ring", "color"), "color?", None),
    (("details", "focus_ring", "width"), "int", (0, 3)),
    (("integration", "libadwaita_colors"), "bool", None),
    (("integration", "libadwaita_accent"), "bool", None),
    (("integration", "flatpak_access"), "bool", None),
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
        elif kind == "int":
            lo, hi = extra
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
                problems.append(f"{name} must be a number from {lo} to {hi} (got {value!r})")
            else:
                _set(data, path, int(round(value)))
        elif kind == "bool":
            if not isinstance(value, bool):
                problems.append(f"{name} must be true or false (got {value!r})")
        elif kind == "choice":
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
    if isinstance(wb, dict) and wb.get("button_style") in titlebuttons.OLD_NAMES:
        wb["button_style"] = titlebuttons.OLD_NAMES[wb["button_style"]]     # names before v1
    merged["version"] = SETTINGS_VERSION
    problems = validate(merged)
    if problems:
        raise SettingsError(problems)
    return merged


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
    if "depth" in defaults:
        out["style"]["depth"] = defaults["depth"]
    for area in ("panel", "menu"):
        shape = p[f"{area}_shape"]
        r, gr = defaults.get(f"{area}_roundness"), defaults.get(f"{area}_gradient")
        if r is None and gr is None:
            shape.update(follow_global=True, roundness=g["roundness"], gradient=g["gradient"])
        else:
            shape.update(follow_global=False,
                         roundness=g["roundness"] if r is None else r,
                         gradient=g["gradient"] if gr is None else gr)
    for key in ("panel_opacity", "menu_opacity"):
        if key in defaults:
            p[key] = defaults[key]
    if "panel_label_weight" in defaults:
        p["label_weight"] = defaults["panel_label_weight"]
    return from_dict(out)


def apply_preset(settings: dict, preset: dict) -> dict:
    """Presets are partial settings files; merge them over the current settings."""
    preset = {k: v for k, v in preset.items() if k not in ("name", "version")}
    return from_dict(_deep_merge(settings, preset))
