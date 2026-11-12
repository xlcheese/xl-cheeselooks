"""Styles: how edges are drawn (docs/design-spec.md, section 6).

A style is a TOML file with named *edges* (border + layers of highlight,
shade, inner shadow, drop shadow, rings) and a *widgets* table that says
which edge each widget uses in each state. Colors are palette token names,
"white"/"black", or #RRGGBB. Alpha values are written for Depth 50; the
Depth slider scales them (Depth 100 doubles them, Depth 0 makes any style flat).
"""

from __future__ import annotations

import copy
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import palette as pal

LAYER_KINDS = ("highlight", "sides", "left", "right", "shade", "inner", "shadow", "ring", "outline")
# Cinnamon (St) allows one box-shadow: keep the first layer present in this order.
ST_PRIORITY = ("highlight", "shadow", "shade", "inner", "ring", "outline")
LAYER_KEYS = {"x", "y", "blur", "spread", "width", "color", "alpha", "alpha_dark", "grow", "inset", "adaptive"}
# Layers drawn on the widget's own surface. Their strength adapts to that surface
# (see _adapt), so one line in a style looks alike on light and dark buttons.
SURFACE_LAYERS = ("highlight", "sides", "left", "right", "shade", "inner")
# The surface each widget sits on at rest (palette names).
WIDGET_FACE = {
    "button": "button", "suggested": "accent", "destructive": "destructive", "linked": "button",
    "toolbar_button": "header", "title_button": "header",
    "close_button": "header", "entry": "base", "combo": "button", "tab": "header",
    "menu_item": "menu_bg", "menubar_item": "header", "panel_button": "pb_rest",
    "check": "base", "switch": "trough",
}
EDGE_KEYS = {"border", *LAYER_KINDS}

WIDGETS = (
    "button", "suggested", "destructive", "linked", "toolbar_button", "title_button", "close_button",
    "entry", "combo", "tab", "menu_item", "menubar_item", "panel_button",
    "check", "switch",
)
STATES = ("rest", "hover", "pressed", "focus")
WIDGET_KEYS = {
    "like", "edge", "hover_edge", "pressed_edge", "focus_edge", "border",
    "hover_color", "tab_kind", "active_marker", "hover_border",
    "color", "selected_color", "selected_border", "padding", "spacing", "hover_fg", "selected_fg",
}
# keys only some widgets use so far (others accept them but ignore them)
WIDGET_ONLY_KEYS = {"color": ("panel_button",), "selected_color": ("panel_button",),
                    "selected_border": ("panel_button",), "padding": ("panel_button",),
                    "spacing": ("panel_button",),
                    "hover_fg": ("menu_item", "menubar_item", "tab"), "selected_fg": ("panel_button",)}
# a text color belongs to its face: a widget that sets its own face doesn't
# inherit the text color of the widget it is "like"
FACE_FG = {"hover_color": "hover_fg", "selected_color": "selected_fg"}
PADDING_RANGE = (0, 24)   # px, left and right
SPACING_RANGE = (0, 12)   # px between window-list buttons
TAB_KINDS = ("boxed", "open", "pills")
# [panel]: the panel's own colors (opacity is a user setting; a style suggests
# it with [defaults] panel_opacity)
PANEL_KEYS = ("color",)
# Settings a style can suggest in [defaults] (applied when the style is picked
# and on a fresh install). Panel and menu values are optional: left out, the
# panel and menus follow Global.
DEFAULT_KEYS: dict[str, Any] = {
    "roundness": (0, 100), "gradient": (0, 100), "depth": (0, 100),
    "panel_roundness": (0, 100), "panel_gradient": (0, 100),
    "menu_roundness": (0, 100), "menu_gradient": (0, 100),
    "panel_opacity": (30, 100), "menu_opacity": (30, 100),
    "panel_label_weight": None,
}
DEFAULT_ADAPT_STRENGTH = 0.6
ACTIVE_MARKERS = ("none", "line", "glow")

# Fallbacks used for anything a style leaves out.
BUILTIN_EDGES: dict[str, dict[str, Any]] = {
    "flat": {"border": "none"},
    "raised": {
        "border": "border_strong",
        "highlight": {"y": 1, "color": "white", "alpha": 0.60, "alpha_dark": 0.07},
        "shade": {"y": -1, "color": "black", "alpha": 0.07, "alpha_dark": 0.20},
        "shadow": {"y": 1, "blur": 2, "color": "black", "alpha": 0.10, "alpha_dark": 0.30},
    },
    "raised_hover": {
        "border": "border_hover",
        "highlight": {"y": 1, "color": "white", "alpha": 0.60, "alpha_dark": 0.07},
        "shade": {"y": -1, "color": "black", "alpha": 0.07, "alpha_dark": 0.20},
        "shadow": {"y": 1, "blur": 2, "color": "black", "alpha": 0.10, "alpha_dark": 0.30},
    },
    "sunken": {
        "border": "border_strong",
        "inner": {"y": 1, "blur": 2, "color": "black", "alpha": 0.10, "alpha_dark": 0.30},
    },
    "focus": {
        "border": "accent",
        "ring": {"width": 1, "color": "accent", "alpha": 1.0},
        "inner": {"y": 1, "blur": 2, "color": "black", "alpha": 0.10, "alpha_dark": 0.30},
    },
}

BUILTIN_WIDGETS: dict[str, dict[str, Any]] = {
    "button": {"edge": "raised", "hover_edge": "raised_hover", "pressed_edge": "sunken",
               "focus_edge": "raised", "hover_color": "button_hover"},
    "suggested": {"like": "button", "hover_color": "accent_hover"},
    "destructive": {"like": "button", "hover_color": "destructive"},
    # joined button groups (path bars, stack switchers, spin buttons); inner
    # layers only, never a drop shadow, so neighbours don't overlap
    "linked": {"like": "button"},
    "toolbar_button": {"edge": "flat", "hover_edge": "raised_hover", "pressed_edge": "sunken",
                       "focus_edge": "flat", "hover_color": "flat_hover"},
    "title_button": {"like": "toolbar_button"},
    "close_button": {"like": "title_button", "hover_color": "accent"},
    "entry": {"edge": "sunken", "hover_edge": "sunken", "pressed_edge": "sunken", "focus_edge": "focus"},
    "combo": {"like": "button"},
    # tabs take their look from the buttons (see tabs.py); a style only picks the shape
    "tab": {"like": "toolbar_button", "tab_kind": "boxed", "active_marker": "none"},
    "menu_item": {"edge": "flat", "hover_edge": "flat", "pressed_edge": "flat", "focus_edge": "flat",
                  "hover_color": "menu_hover"},
    "menubar_item": {"like": "menu_item", "hover_color": "menubar_hover"},
    # panel window-list buttons, launchers and applets; "selected" is the
    # focused window's button
    "panel_button": {"edge": "raised", "hover_edge": "raised", "pressed_edge": "sunken",
                     "focus_edge": "raised", "color": "pb_rest", "hover_color": "pb_hover",
                     "selected_color": "pb_focus", "selected_border": "accent_press",
                     "active_marker": "none", "padding": 4, "spacing": 2},
    "check": {"edge": "sunken", "hover_edge": "sunken", "pressed_edge": "sunken", "focus_edge": "focus"},
    "switch": {"like": "check"},
}


class StyleError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class Style:
    name: str
    path: Path | None
    author: str = ""
    description: str = ""
    defaults: dict[str, Any] = field(default_factory=dict)
    adapt_strength: float = DEFAULT_ADAPT_STRENGTH
    edges: dict[str, dict[str, Any]] = field(default_factory=dict)
    widgets: dict[str, dict[str, Any]] = field(default_factory=dict)
    panel: dict[str, Any] = field(default_factory=dict)
    extra_css: str = ""
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Loading and checking
# --------------------------------------------------------------------------

def _is_color_ref(value: Any, palette_names: set[str]) -> bool:
    """A palette color name, #RRGGBB, 'none', or an expression such as
    "darker(border_strong, 0.1)" or "mix(border_strong, text, 0.2)"."""
    if not isinstance(value, str):
        return False
    if value in palette_names or pal.is_hex(value) or value in ("none", "transparent"):
        return True
    if "(" in value:
        from . import render
        try:
            result = render.evaluate(value, pal.derive("#FA8562", "#F5F5F5", "#303030"))
        except Exception:
            return False
        return pal.is_hex(result)
    return False


def check(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for raw style data."""
    errors: list[str] = []
    warnings: list[str] = []
    names = set(pal.derive("#FA8562", "#F0F0F0", "#303030"))

    if not isinstance(data.get("name"), str) or not data["name"].strip():
        errors.append("'name' is required and must be text")
    for key in data:
        if key not in ("name", "author", "description", "defaults", "edges", "widgets", "panel",
                       "adapt_strength"):
            warnings.append(f"unknown top-level key '{key}' is ignored")

    a = data.get("adapt_strength", DEFAULT_ADAPT_STRENGTH)
    if isinstance(a, bool) or not isinstance(a, (int, float)) or not 0 <= a <= 1:
        errors.append("adapt_strength must be a number from 0 (no adapting) to 1 (full)")

    panel = data.get("panel", {})
    if not isinstance(panel, dict):
        errors.append("'panel' must be a table")
    else:
        for k, v in panel.items():
            if k not in PANEL_KEYS:
                warnings.append(f"panel.{k} is not a known panel setting and is ignored "
                                f"(known: {', '.join(PANEL_KEYS)})")
            elif not _is_color_ref(v, names):
                errors.append(f"panel.{k} must be a palette color name or #RRGGBB (got {v!r})")

    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        errors.append("'defaults' must be a table")
    else:
        for k, v in defaults.items():
            if k not in DEFAULT_KEYS:
                warnings.append(f"defaults.{k} is not a known setting and is ignored "
                                f"(known: {', '.join(DEFAULT_KEYS)})")
            elif k == "panel_label_weight":
                if v not in ("bold", "regular"):
                    errors.append("defaults.panel_label_weight must be \"bold\" or \"regular\"")
            else:
                lo, hi = DEFAULT_KEYS[k]
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
                    errors.append(f"defaults.{k} must be a number from {lo} to {hi}")

    edges = data.get("edges", {})
    if not isinstance(edges, dict):
        errors.append("'edges' must be a table")
        edges = {}
    for ename, edge in edges.items():
        if not isinstance(edge, dict):
            errors.append(f"edges.{ename} must be a table")
            continue
        for k, v in edge.items():
            where = f"edges.{ename}.{k}"
            if k not in EDGE_KEYS:
                warnings.append(f"{where} is not a known edge part and is ignored")
            elif k == "border":
                if not _is_color_ref(v, names):
                    errors.append(f"{where} must be a palette color name, 'none', #RRGGBB, or an expression "
                                  f"like \"darker(border_strong, 0.1)\" (got {v!r})")
            else:
                if not isinstance(v, dict):
                    errors.append(f"{where} must be a table like {{ y = 1, color = \"white\", alpha = 0.5 }}")
                    continue
                for lk, lv in v.items():
                    if k in ("sides", "left", "right") and lk == "y":
                        warnings.append(f"{where}.y has no effect on {k}; its width is x "
                                        f"(default 1px)")
                    if lk not in LAYER_KEYS:
                        warnings.append(f"{where}.{lk} is not a known layer setting and is ignored")
                    elif lk == "color":
                        if not _is_color_ref(lv, names):
                            errors.append(f"{where}.color must be a palette color name or #RRGGBB (got {lv!r})")
                    elif lk in ("grow", "inset", "adaptive"):
                        if not isinstance(lv, bool):
                            errors.append(f"{where}.{lk} must be true or false")
                    elif lk in ("alpha", "alpha_dark"):
                        if isinstance(lv, bool) or not isinstance(lv, (int, float)) or not 0 <= lv <= 1:
                            errors.append(f"{where}.{lk} must be a number from 0 to 1")
                    elif isinstance(lv, bool) or not isinstance(lv, (int, float)):
                        errors.append(f"{where}.{lk} must be a number")
                if "color" not in v:
                    errors.append(f"{where} needs a color")

    all_edges = set(BUILTIN_EDGES) | set(edges)
    widgets = data.get("widgets", {})
    if not isinstance(widgets, dict):
        errors.append("'widgets' must be a table")
        widgets = {}
    for wname, w in widgets.items():
        where = f"widgets.{wname}"
        if wname not in WIDGETS:
            warnings.append(f"{where} is not a known widget and is ignored "
                            f"(known: {', '.join(WIDGETS)})")
            continue
        if not isinstance(w, dict):
            errors.append(f"{where} must be a table")
            continue
        for k, v in w.items():
            if k not in WIDGET_KEYS:
                warnings.append(f"{where}.{k} is not a known widget setting and is ignored")
            elif k == "like":
                if v not in WIDGETS:
                    errors.append(f"{where}.like must name another widget (got {v!r})")
            elif k.endswith("edge"):
                if v not in all_edges:
                    errors.append(f"{where}.{k} refers to an edge that doesn't exist: {v!r}")
            elif k in ("border", "hover_color", "color", "selected_color", "selected_border",
                       "hover_fg", "selected_fg"):
                if k in WIDGET_ONLY_KEYS and wname not in WIDGET_ONLY_KEYS[k]:
                    warnings.append(f"{where}.{k} is only used by "
                                    f"{', '.join(WIDGET_ONLY_KEYS[k])} so far and is ignored")
                if not _is_color_ref(v, names):
                    errors.append(f"{where}.{k} must be a palette color name or #RRGGBB (got {v!r})")
            elif k in ("padding", "spacing"):
                if wname not in WIDGET_ONLY_KEYS[k]:
                    warnings.append(f"{where}.{k} is only used by panel_button so far and is ignored")
                lo, hi = PADDING_RANGE if k == "padding" else SPACING_RANGE
                if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
                    errors.append(f"{where}.{k} must be a whole number of pixels from {lo} to {hi} (got {v!r})")
            elif k == "tab_kind" and v not in TAB_KINDS:
                errors.append(f"{where}.tab_kind must be one of {', '.join(TAB_KINDS)}")
            elif k == "active_marker" and v not in ACTIVE_MARKERS:
                errors.append(f"{where}.active_marker must be one of {', '.join(ACTIVE_MARKERS)}")
            elif k == "hover_border":
                warnings.append(f"{where}.hover_border is no longer used (tabs follow "
                                f"toolbar_button) and can be removed")

    # 'like' cycles
    merged_like = {w: dict(BUILTIN_WIDGETS.get(w, {})) for w in WIDGETS}
    for wname, w in widgets.items():
        if wname in merged_like and isinstance(w, dict):
            merged_like[wname].update(w)
    for start in WIDGETS:
        seen, cur = [], start
        while "like" in merged_like.get(cur, {}):
            if cur in seen:
                errors.append(f"widgets.{start}: 'like' goes round in a circle ({' → '.join(seen + [cur])})")
                break
            seen.append(cur)
            cur = merged_like[cur]["like"]
    return errors, warnings


def load(path: Path) -> Style:
    """Load a style folder (containing style.toml) or a style.toml file."""
    path = Path(path)
    toml_path = path / "style.toml" if path.is_dir() else path
    try:
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StyleError([f"{toml_path} not found"]) from exc
    except tomllib.TOMLDecodeError as exc:
        raise StyleError([f"{toml_path}: {exc}"]) from exc
    errors, warnings = check(data)
    if errors:
        raise StyleError(errors)
    extra = toml_path.parent / "extra.css"
    return Style(
        name=data["name"].strip(),
        path=toml_path,
        author=data.get("author", ""),
        description=data.get("description", ""),
        defaults={k: (v if isinstance(v, str) else int(v))
                  for k, v in data.get("defaults", {}).items() if k in DEFAULT_KEYS},
        adapt_strength=float(data.get("adapt_strength", DEFAULT_ADAPT_STRENGTH)),
        edges=copy.deepcopy(data.get("edges", {})),
        widgets=copy.deepcopy(data.get("widgets", {})),
        panel=copy.deepcopy(data.get("panel", {})),
        extra_css=extra.read_text(encoding="utf-8") if extra.exists() else "",
        warnings=warnings,
    )


def find(name: str, search_dirs: list[Path]) -> Style:
    """Find a style by its name (folder name or the 'name' inside style.toml)."""
    for base in search_dirs:
        if not base.is_dir():
            continue
        direct = base / name
        if (direct / "style.toml").exists():
            return load(direct)
        for sub in sorted(base.iterdir()):
            toml_path = sub / "style.toml"
            if toml_path.exists():
                try:
                    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
                except tomllib.TOMLDecodeError:
                    continue
                if data.get("name") == name:
                    return load(sub)
    raise StyleError([f"style '{name}' not found in: {', '.join(str(d) for d in search_dirs)}"])


# --------------------------------------------------------------------------
# Turning edges into CSS
# --------------------------------------------------------------------------

def _resolve_color(ref: str, palette: dict[str, str]) -> str:
    if ref in palette:
        return palette[ref]
    if pal.is_hex(ref):
        return pal.normalize(ref)
    if "(" in ref:
        from . import render
        return pal.normalize(render.evaluate(ref, palette))
    raise KeyError(ref)


def _lightness(color: str) -> float:
    """Perceived lightness, 0 (black) to 100 (white): CIE L*."""
    y = pal.luminance(color)
    return 116 * y ** (1 / 3) - 16 if y > 0.008856 else 903.3 * y


def _adapt(layer_color: str, surface: str | None, reference: str | None,
           strength: float = DEFAULT_ADAPT_STRENGTH) -> float:
    """How much to scale a surface layer so it looks as strong on `surface`
    as the style author saw it on `reference` (the normal button). A white
    line on coral is a far bigger jump than on a near-white button, so it is
    toned down there. Only ever reduces. strength (the style's
    adapt_strength) softens it: 1 = fully equal, 0 = no adapting."""
    if not surface or not reference:
        return 1.0
    want = abs(_lightness(layer_color) - _lightness(reference))
    have = abs(_lightness(layer_color) - _lightness(surface))
    if have <= want or have < 1:
        return 1.0
    return max(0.15, (want / have) ** strength)


def _layer_css(kind: str, layer: dict[str, Any], palette: dict[str, str], depth: float, dark: bool,
               surface: str | None = None, strength: float = DEFAULT_ADAPT_STRENGTH) -> str | None:
    scale = depth / 50.0
    alpha = layer.get("alpha_dark", layer.get("alpha", 1.0)) if dark else layer.get("alpha", 1.0)
    base_color = _resolve_color(layer["color"], palette)
    if kind in SURFACE_LAYERS and layer.get("adaptive", True):
        alpha *= _adapt(base_color, surface, palette.get("button"), strength)
    alpha = min(1.0, alpha * scale)
    if alpha <= 0.001:
        return None
    color = pal.rgba(base_color, alpha)
    grow = scale if layer.get("grow") else 1.0

    def px(v: float) -> str:
        v = round(v, 1)
        return "0" if v == 0 else f"{v:g}px"

    if kind in ("sides", "left", "right"):
        # a line inside the left and/or right edge: x = width in px (default 1),
        # blur = fade inward over that many px (0 = crisp line)
        w = abs(layer.get("x", 1))
        blur = layer.get("blur", 0)
        if blur:
            # Keep the fade on its own edge: a blurred inset shadow would also
            # glow along the top and bottom. Shrink it by the blur (negative
            # spread) and push it out by the same amount.
            tail = f" {px(blur)} {px(-blur)}"
            w += blur
        else:
            tail = " 0"
        left = f"inset {px(w)} 0{tail} {color}"
        right = f"inset -{px(w)} 0{tail} {color}"
        return {"sides": f"{left}, {right}", "left": left, "right": right}[kind]
    if kind in ("ring", "outline"):
        width = layer.get("width", 1)
        inset = layer.get("inset", kind == "ring")
        return f"{'inset ' if inset else ''}0 0 0 {px(width)} {color}"
    x = layer.get("x", 0)
    y = layer.get("y", 0) * grow
    blur = layer.get("blur", 0) * grow
    spread = layer.get("spread", 0)
    inset = kind in ("highlight", "shade", "inner")
    if kind in ("highlight", "shade") and blur and "spread" not in layer and y:
        # Same trick as for the side layers: keep a top or bottom fade off the
        # left and right edges.
        spread = -blur
        y += blur if y > 0 else -blur
    parts = [px(x), px(y), px(blur)]
    if spread:
        parts.append(px(spread))
    return f"{'inset ' if inset else ''}{' '.join(parts)} {color}"


def edge_css(edge: dict[str, Any], palette: dict[str, str], depth: float,
             border_override: str | None = None, surface: str | None = None,
             strength: float = DEFAULT_ADAPT_STRENGTH) -> dict[str, str]:
    """Return {'border', 'shadow' (GTK, all layers), 'st_shadow' (Cinnamon, one layer)}."""
    dark = pal.is_dark(palette)
    border_ref = border_override or edge.get("border", "none")
    if border_ref in ("none", "transparent"):
        border = "transparent"
    else:
        border = _resolve_color(border_ref, palette)
    layers = {k: _layer_css(k, edge[k], palette, depth, dark, surface, strength) for k in LAYER_KINDS if k in edge}
    gtk = [layers[k] for k in LAYER_KINDS if layers.get(k)]
    inset = [layers[k] for k in LAYER_KINDS if layers.get(k) and layers[k].startswith("inset")]
    st = next((layers[k] for k in ST_PRIORITY if layers.get(k)), None)
    return {
        "border": border,
        "shadow": ", ".join(gtk) if gtk else "none",
        "inset_shadow": ", ".join(inset) if inset else "none",
        "st_shadow": st or "none",
    }


def resolved_widgets(style: Style) -> dict[str, dict[str, Any]]:
    """Each widget's settings with 'like' and built-in fallbacks applied."""
    raw = {w: {**BUILTIN_WIDGETS.get(w, {}), **style.widgets.get(w, {})} for w in WIDGETS}
    out: dict[str, dict[str, Any]] = {}

    def resolve(name: str) -> dict[str, Any]:
        if name in out:
            return out[name]
        spec = dict(raw[name])
        base_name = spec.pop("like", None)
        result = dict(resolve(base_name)) if base_name else {}
        for face, fg in FACE_FG.items():
            if face in spec and fg not in spec:
                result.pop(fg, None)
        result.update(spec)
        out[name] = result
        return result

    for w in WIDGETS:
        resolve(w)
    return out


def widget_tokens(style: Style, palette: dict[str, str], depth: float) -> dict[str, str]:
    """Tokens like w.button.shadow, w.button.hover_st_shadow, w.tab.active_marker."""
    edges = {**copy.deepcopy(BUILTIN_EDGES), **style.edges}
    tokens: dict[str, str] = {}
    for wname, spec in resolved_widgets(style).items():
        border_override = spec.get("border")
        face = (_resolve_color(spec["color"], palette) if spec.get("color")
                else palette.get(WIDGET_FACE.get(wname, "button")))
        hover_face = _resolve_color(spec["hover_color"], palette) if spec.get("hover_color") else face
        surfaces = {"rest": face, "hover": hover_face, "pressed": palette.get("pressed"), "focus": face}
        for state in STATES:
            key = "edge" if state == "rest" else f"{state}_edge"
            ename = spec.get(key, spec.get("edge", "flat"))
            css = edge_css(edges[ename], palette, depth,
                           border_override if ename != "flat" else None, surfaces[state],
                           style.adapt_strength)
            prefix = f"w.{wname}." + ("" if state == "rest" else f"{state}_")
            tokens[prefix + "border"] = css["border"]
            tokens[prefix + "shadow"] = css["shadow"]
            tokens[prefix + "inset_shadow"] = css["inset_shadow"]
            # the inner shadows plus a 1px line just outside the right edge, for
            # joined buttons that must draw the edge they share with the next one
            seam = f"1px 0 0 0 {css['border']}"
            tokens[prefix + "seam_shadow"] = (seam if css["inset_shadow"] == "none"
                                              else f"{seam}, {css['inset_shadow']}")
            tokens[prefix + "st_shadow"] = css["st_shadow"]
        hover_color = spec.get("hover_color")
        if hover_color:
            tokens[f"w.{wname}.hover_color"] = _resolve_color(hover_color, palette)
        for k in ("color", "selected_color", "selected_border", "hover_fg", "selected_fg"):
            if spec.get(k):
                tokens[f"w.{wname}.{k}"] = _resolve_color(spec[k], palette)
        for k in ("padding", "spacing"):
            if k in spec:
                tokens[f"w.{wname}.{k}"] = str(spec[k])
        for k in ("tab_kind", "active_marker"):
            if k in spec:
                tokens[f"w.{wname}.{k}"] = spec[k]
    return tokens
