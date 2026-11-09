"""Build the complete token table that templates are filled from.

Token names are lowercase with dots for areas, for example:

    accent, accent_rgb, select, button_top, button_bottom, r, r2, ctl
    w.button.shadow, w.entry.focus_border          (style edges, Global palette)
    panel.pb_rest_top, panel.r, panel.w.panel_button.st_shadow
    menu.menu_hover, menu.r2, menu.w.menu_item.hover_color
    wb.title_top, wb.height, wb.button_layout
    term.bg, tooltip.bg, scrollbar.r, focus.ring

Every color token also has a <name>_rgb twin ("250, 133, 98") for rgba().
"""

from __future__ import annotations

import colorsys

from . import palette as pal
from . import shape
from . import styles as sty

THEME_NAME = "xl-Cheeselooks"

GRADIENT_COLORS = (
    "button", "button_hover", "accent", "accent_hover", "select", "hover",
    "sidebar_hover", "menu_hover", "fav_hover", "menubar_hover", "panel",
    "pb_rest", "pb_hover", "pb_focus", "pb_attention",
)

# libadwaita's named accents (GNOME 47+)
ADW_ACCENTS = {
    "blue": "#3584E4", "teal": "#2190A4", "green": "#3A944A", "yellow": "#C88800",
    "orange": "#ED5B00", "red": "#E62D42", "pink": "#D56199", "purple": "#9141AC",
    "slate": "#6F8396",
}

LAYOUTS = {"right": ":minimize,maximize,close", "left": "close,minimize,maximize:"}


def nearest_adw_accent(color: str) -> str:
    r, g, b = (v / 255 for v in pal.to_rgb(color))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.18 or l < 0.12 or l > 0.92:
        return "slate"
    best, best_d = "blue", 9.0
    for name, ref in ADW_ACCENTS.items():
        if name == "slate":
            continue
        rr, gg, bb = (v / 255 for v in pal.to_rgb(ref))
        h2, _, _ = colorsys.rgb_to_hls(rr, gg, bb)
        d = min(abs(h - h2), 1 - abs(h - h2))
        if d < best_d:
            best, best_d = name, d
    return best


def _add_colors(tokens: dict[str, str], prefix: str, colors: dict[str, str]) -> None:
    for name, value in colors.items():
        tokens[prefix + name] = value
        tokens[prefix + name + "_rgb"] = pal.rgb_triplet(value)


def _add_gradients(tokens: dict[str, str], prefix: str, palette: dict[str, str], amount: float) -> None:
    for name in GRADIENT_COLORS:
        top, bottom = pal.gradient(palette[name], amount)
        _add_colors(tokens, prefix, {name + "_top": top, name + "_bottom": bottom})


def _add_widgets(tokens: dict[str, str], prefix: str, style: sty.Style,
                 palette: dict[str, str], depth: float) -> None:
    for k, v in sty.widget_tokens(style, palette, depth).items():
        tokens[prefix + k] = v


def build(settings: dict, style: sty.Style, panel_height: int = shape.DEFAULT_PANEL_HEIGHT) -> dict[str, str]:
    g = settings["global"]
    depth = settings["style"]["depth"]
    amount = g["gradient"] / 100
    theme = pal.derive(g["accent"], g["bg"], g["text"])
    t: dict[str, str] = {}

    # --- meta
    t["theme_name"] = THEME_NAME
    t["style_name"] = style.name
    t["is_dark"] = "true" if pal.is_dark(theme) else "false"

    # --- Global palette, gradients, shape, timing, style edges
    _add_colors(t, "", theme)
    _add_gradients(t, "", theme, amount)
    for k, v in shape.shape_tokens(g["size"], g["roundness"]).items():
        t[k] = str(v)
    t["hover_in_ms"] = str(g["hover_in_ms"])
    t["hover_out_ms"] = str(g["hover_out_ms"])
    _add_widgets(t, "", style, theme, depth)
    t["style.extra_css"] = style.extra_css

    # --- Panel & Menu: shared colors, separate shapes
    p = settings["panel"]
    if p["separate_colors"]:
        pcolors = pal.derive(p["accent"] or g["accent"], p["bg"] or g["bg"], p["text"] or g["text"])
    else:
        pcolors = theme
    ps, ms = p["panel_shape"], p["menu_shape"]
    p_round, p_grad = (g["roundness"], g["gradient"]) if ps["follow_global"] else (ps["roundness"], ps["gradient"])
    m_round, m_grad = (g["roundness"], g["gradient"]) if ms["follow_global"] else (ms["roundness"], ms["gradient"])
    ctl = shape.SIZES[g["size"]][0]

    _add_colors(t, "panel.", pcolors)
    _add_gradients(t, "panel.", pcolors, p_grad / 100)
    _add_widgets(t, "panel.", style, pcolors, depth)
    t["panel.r"] = str(shape.radius(p_round, panel_height))
    t["panel.height"] = str(panel_height)
    t["panel.label_weight"] = "bold" if p["label_weight"] == "bold" else "normal"
    t["panel.opacity"] = f"{p['panel_opacity'] / 100:g}"

    _add_colors(t, "menu.", pcolors)
    _add_gradients(t, "menu.", pcolors, m_grad / 100)
    _add_widgets(t, "menu.", style, pcolors, depth)
    m_r = shape.radius(m_round, ctl)
    t["menu.r"] = str(m_r)
    t["menu.r2"] = str(shape.window_radius(m_r))
    t["menu.opacity"] = f"{p['menu_opacity'] / 100:g}"

    # --- Window borders
    wb = settings["window_borders"]
    sep = wb["separate_colors"]
    title = (wb["title_bar"] if sep and wb["title_bar"] else theme["header"])
    title_text = (wb["title_text"] if sep and wb["title_text"] else theme["text"])
    border = (wb["border"] if sep and wb["border"] else theme["border"])
    top, bottom = pal.title_gradient(title, amount)
    unfocused = pal.mix(title, theme["bg"], 0.5) if sep else theme["bg"]
    _add_colors(t, "wb.", {
        "title": title, "title_top": top, "title_bottom": bottom, "text": title_text,
        "border": border, "unfocused": unfocused,
        "unfocused_text": pal.mix(title_text, unfocused, 0.4),
    })
    height = wb["title_bar_height"]
    btn_h = min(ctl, height - 10)
    t["wb.height"] = str(height)
    t["wb.border_width"] = str(wb["border_width"])
    t["wb.button_h"] = str(btn_h)
    t["wb.button_w"] = str(round(btn_h * 1.12))
    t["wb.button_layout"] = LAYOUTS[wb["button_layout"]]
    t["wb.button_style"] = wb["button_style"]

    # --- Terminal
    term = settings["terminal"]
    tc = pal.terminal_colors(theme, term["bg"] if term["separate_colors"] else None,
                             term["text"] if term["separate_colors"] else None)
    _add_colors(t, "term.", tc)

    # --- Details
    d = settings["details"]
    tip = d["tooltips"]
    _add_colors(t, "tooltip.", {
        "bg": tip["bg"] if tip["custom"] and tip["bg"] else theme["menu_bg"],
        "text": tip["text"] if tip["custom"] and tip["text"] else theme["text"],
    })
    sb = d["scrollbars"]
    mode = sb["mode"] if sb["custom"] else "overlay"
    sb_width = 6 if mode == "overlay" else 10
    t["scrollbar.mode"] = mode
    t["scrollbar.width"] = str(sb_width)
    t["scrollbar.r"] = str(shape.radius(sb["roundness"] if sb["custom"] else 100, sb_width))
    sl = d["sliders"]["roundness"] if d["sliders"]["custom"] else 100
    t["slider.handle_r"] = str(shape.radius(sl, 16))
    t["slider.track_r"] = str(shape.radius(sl, 4))
    sw = d["switches"]["roundness"] if d["switches"]["custom"] else 100
    t["switch.r"] = str(shape.radius(sw, 24))
    t["switch.knob_r"] = str(shape.radius(sw, 18))
    fr = d["focus_ring"]
    if fr["custom"] and fr["color"]:
        ring_color, ring_alpha, ring_width = fr["color"], 1.0, fr["width"]
    else:
        ring_color, ring_alpha, ring_width = theme["accent"], 0.5, fr["width"] if fr["custom"] else 2
    t["focus.ring"] = pal.rgba(ring_color, ring_alpha)
    t["focus.width"] = str(ring_width)

    # --- Integration
    t["adw.accent_name"] = nearest_adw_accent(theme["accent"])
    return t


def warnings(settings: dict) -> list[str]:
    """Readability warnings for every area that has its own colors."""
    g = settings["global"]
    theme = pal.derive(g["accent"], g["bg"], g["text"])
    notes = pal.readability_warnings(theme, "Theme")
    p = settings["panel"]
    if p["separate_colors"]:
        pc = pal.derive(p["accent"] or g["accent"], p["bg"] or g["bg"], p["text"] or g["text"])
        notes += pal.readability_warnings(pc, "Panel")
    if p["menu_opacity"] < 80:
        notes.append("Menus are quite see-through; window text behind them may make menu text harder to read.")
    wb = settings["window_borders"]
    if wb["separate_colors"] and wb["title_bar"] and wb["title_text"]:
        if pal.contrast(wb["title_bar"], wb["title_text"]) < 4.5:
            notes.append("Title text is hard to read on the title bar.")
    term = settings["terminal"]
    if term["separate_colors"] and term["bg"] and term["text"]:
        if pal.contrast(term["bg"], term["text"]) < 4.5:
            notes.append("Terminal text is hard to read on the terminal background.")
    return notes
