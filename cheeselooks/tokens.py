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
import dataclasses

from . import palette as pal
from . import render, shape
from . import styles as sty
from . import gtk4, metacity, titlebuttons, panelmarker, tabs

THEME_NAME = "xl-Cheeselooks"
SCROLL_SLIDER_BORDER = 4   # px, Mint-Y's transparent border around the scrollbar thumb
HOVER_CALIBRATION = 0.8

GRADIENT_COLORS = (
    "button", "button_hover", "accent", "accent_hover", "select", "hover",
    "sidebar_hover", "menu_hover", "fav_hover", "menubar_hover", "panel",
    "pb_rest", "pb_hover", "pb_focus", "pb_attention", "destructive", "pressed",
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
                 palette: dict[str, str], depth: float, amount: float) -> None:
    wt = sty.widget_tokens(style, palette, depth)
    # faces get a gradient pair and a readable text color:
    # w.X.color -> w.X.color_top/_bottom/_fg, w.X.hover_color -> w.X.hover_top/..., etc.
    faces = {".color": "color_", ".hover_color": "hover_", ".selected_color": "selected_",
             ".pressed_color": "pressed_"}
    for k, v in list(wt.items()):
        for suffix, out in faces.items():
            if k.endswith(suffix):
                base = k[: -len(suffix) + 1]
                top, bottom = pal.gradient(v, amount)
                wt[base + out + "top"], wt[base + out + "bottom"] = top, bottom
                if base + out + "fg" in wt:    # the style chose this text color
                    continue
                # on the accent itself, the theme's text-on-accent; otherwise
                # whichever of text / text-on-accent reads better on this face
                wt[base + out + "fg"] = (palette["accent_fg"] if v == palette["accent"] else
                                         max((palette["text"], palette["accent_fg"]),
                                             key=lambda c: pal.contrast(c, v)))
    for k, v in wt.items():
        tokens[prefix + k] = v


def _add_face_gradients(t: dict[str, str], style: sty.Style) -> None:
    """X_grad for every X_top / X_bottom pair: the whole CSS gradient, smooth or
    split (glossy) as the style says. GTK templates use these for faces; the
    title bar and Cinnamon (two-colour gradients only) use the plain pair."""
    for key in [k for k in t if k.endswith("_top")]:
        base = key[: -len("_top")]
        if base + "_bottom" in t and not key.endswith("_rgb"):
            t[base + "_grad"] = pal.gradient_css(t[key], t[base + "_bottom"],
                                                 style.gradient_shape, style.split_step,
                                                 style.glass_return)


def _derive(style: sty.Style, accent: str, bg: str, text: str, hover: float) -> dict[str, str]:
    """The palette, with the style's button color (widgets.button.color) as the
    button face when it sets one. The expression is read against the plain
    palette (so "darker(button, 0.05)" starts from the usual button), then the
    palette is worked out again from that face, so the default button hover
    and gradients follow it."""
    plain = pal.derive(accent, bg, text, hover)
    face = style.widgets.get("button", {}).get("color")
    if not face:
        return plain
    return pal.derive(accent, bg, text, hover, button_face=sty._resolve_color(face, plain))


def _without_button_color(style: sty.Style) -> sty.Style:
    """The style for widget tokens once the button color is in the palette: the
    key is dropped, so widgets that copy button (combo, linked...) don't apply
    the expression a second time."""
    button = style.widgets.get("button")
    if not button or "color" not in button:
        return style
    widgets = {**style.widgets, "button": {k: v for k, v in button.items() if k != "color"}}
    return dataclasses.replace(style, widgets=widgets)


def build(settings: dict, style: sty.Style, panel_height: int = shape.DEFAULT_PANEL_HEIGHT,
          overlay_scrollbars: bool | None = None) -> dict[str, str]:
    """overlay_scrollbars: Mint's own switch, used when Details doesn't choose a mode."""
    g = settings["global"]
    depth = settings["style"]["depth"]
    amount = g["gradient"] / 100
    # Calibrated so the slider's center (50) is xl_cheese's chosen look, which was
    # 40 on the original scale: h = value / 50 x 0.8.
    hover = g["hover_strength"] / 50 * HOVER_CALIBRATION
    render.LIFT_SCALE = g["hover_strength"] / 50     # style lift() hovers follow the slider too
    theme = _derive(style, g["accent"], g["bg"], g["text"], hover)
    # the button color is in the palette now; widget tokens use the style without it
    face_style, style = style, _without_button_color(style)
    t: dict[str, str] = {}

    # --- meta
    t["theme_name"] = THEME_NAME
    t["style_name"] = style.name
    t["is_dark"] = "true" if pal.is_dark(theme) else "false"

    # --- Global palette, gradients, shape, timing, style edges
    _add_colors(t, "", theme)
    # hovered list rows (activatable rows on a list): a text tint that follows
    # Hover strength (Mint-Y's is a fixed 3%)
    t["row_hover"] = pal.rgba(theme["text"], 0.075 * hover)
    _add_gradients(t, "", theme, amount)
    for k, v in shape.shape_tokens(g["size"], g["roundness"]).items():
        t[k] = str(v)
    t["hover_in_ms"] = str(g["hover_in_ms"])
    t["hover_out_ms"] = str(g["hover_out_ms"])
    _add_widgets(t, "", style, theme, depth, amount)
    t["style.extra_css"] = style.extra_css
    _add_face_gradients(t, style)
    t["tabs.css"] = tabs.css(t)
    t["tabs4.css"] = tabs.css(t, gtk4=True)
    t["tabs_adw.css"] = tabs.adw_css(t)
    t.update(gtk4.tokens(t))

    # --- Panel & Menu: shared colors, separate shapes
    p = settings["panel"]
    if p["separate_colors"]:
        pcolors = _derive(face_style, p["accent"] or g["accent"], p["bg"] or g["bg"], p["text"] or g["text"], hover)
    else:
        pcolors = theme
    ps, ms = p["panel_shape"], p["menu_shape"]
    p_round, p_grad = (g["roundness"], g["gradient"]) if ps["follow_global"] else (ps["roundness"], ps["gradient"])
    m_round, m_grad = (g["roundness"], g["gradient"]) if ms["follow_global"] else (ms["roundness"], ms["gradient"])
    ctl = shape.SIZES[g["size"]][0]

    if style.panel.get("color"):
        # the style's panel color; its gradient and opacity are added as usual
        pcolors = {**pcolors, "panel": sty._resolve_color(style.panel["color"], pcolors)}
    _add_colors(t, "panel.", pcolors)
    _add_gradients(t, "panel.", pcolors, p_grad / 100)
    _add_widgets(t, "panel.", style, pcolors, depth, p_grad / 100)
    t["panel.r"] = str(shape.radius(p_round, panel_height))
    t["panel.height"] = str(panel_height)
    t["panel.label_weight"] = "bold" if p["label_weight"] == "bold" else "normal"
    t["panel.opacity"] = f"{p['panel_opacity'] / 100:g}"
    t["panel_marker.css"] = panelmarker.css(t)

    # Cinnamon menus use the shell menu colors under the same names, so a
    # style's "menu_hover" means the right thing in GTK and in Cinnamon.
    mcolors = dict(pcolors, menu_bg=pcolors["shell_menu_bg"], menu_hover=pcolors["shell_menu_hover"])
    _add_colors(t, "menu.", mcolors)
    _add_gradients(t, "menu.", mcolors, m_grad / 100)
    _add_widgets(t, "menu.", style, mcolors, depth, m_grad / 100)
    m_r = shape.radius(m_round, ctl)
    t["menu.r"] = str(m_r)
    t["menu.r2"] = str(shape.window_radius(m_r))
    t["menu.opacity"] = f"{p['menu_opacity'] / 100:g}"
    # notification popups: the style's kind of accent, your opacity
    t["notification.opacity"] = f"{p['notification_opacity'] / 100:g}"
    n = style.notification
    n_color = sty._resolve_color(n["color"], mcolors) if n.get("color") else mcolors["accent"]
    t["notification.css"] = {
        "line": f"border: 0 solid {n_color}; border-top: 4px solid {n_color};",
        "flat": "border: none;",
        "bordered": f"border: 1px solid {n_color};",
    }[n.get("kind", "line")]

    # --- Window borders
    wb = settings["window_borders"]
    sep = wb["separate_colors"]
    title = (wb["title_bar"] if sep and wb["title_bar"] else theme["header"])
    title_text = (wb["title_text"] if sep and wb["title_text"] else theme["text"])
    border = (wb["border"] if sep and wb["border"] else theme["border_strong"])
    top, bottom = pal.title_gradient(title, wb["title_gradient"] / 100)
    unfocused = title  # unfocused: same color, gradient removed, so it matches menubar/toolbar
    _add_colors(t, "wb.", {
        "title": title, "title_top": top, "title_bottom": bottom, "text": title_text,
        "border": border, "unfocused": unfocused,
        "unfocused_text": pal.mix(title_text, unfocused, 0.4),
    })
    height = wb["title_bar_height"]
    btn_h = min(ctl, height - 10)
    t["wb.height"] = str(height)
    t["wb.height_inner"] = str(height - 1)  # GTK min-height excludes the 1px bottom border
    t["wb.border_width"] = str(wb["border_width"])
    t["wb.button_h"] = str(btn_h)
    t["wb.button_w"] = str(round(btn_h * 1.12))
    t["wb.button_layout"] = LAYOUTS[wb["button_layout"]]
    t["wb.button_style"] = wb["button_style"]
    t["wb.button_roundness"] = str(titlebuttons.roundness(wb["button_style"], wb["button_roundness"],
                                                          g["roundness"]))
    t.update(metacity.tokens(t))
    # Title buttons and headerbar buttons sit on the title bar. With the title
    # bar's own colours, their faces come from a palette built on those (wbp.*),
    # so a hover face isn't light on a dark title bar; otherwise wbp = the theme.
    if sep and (title != theme["header"] or title_text != theme["text"]):
        wb_pal = _derive(face_style, g["accent"], title, title_text, hover)
    else:
        wb_pal = theme
    _add_colors(t, "wbp.", wb_pal)
    _add_gradients(t, "wbp.", wb_pal, amount)
    _add_widgets(t, "wbp.", style, wb_pal, depth, amount)
    # the style's face shape, for title buttons drawn outside the CSS (SVG faces)
    t["style.gradient_shape"] = style.gradient_shape
    t["style.split_step"] = str(style.split_step)
    t["style.glass_return"] = str(style.glass_return)
    t.update(titlebuttons.tokens(t))

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
    if sb["custom"]:
        mode = sb["mode"]
    else:
        mode = "classic" if overlay_scrollbars is False else "overlay"
    sb_width = 6 if mode == "overlay" else 10
    t["scrollbar.mode"] = mode
    t["scrollbar.width"] = str(sb_width)
    sb_round = sb["roundness"] if sb["custom"] else 100
    # The thumb sits inside a 4px clear border (Mint-Y's spacing) and the radius
    # applies to that outer edge, so add the border for the thumb to get it.
    t["scrollbar.r"] = str(shape.radius(sb_round, sb_width) + SCROLL_SLIDER_BORDER)
    # the thin overlay line (4px wide, 1px border) when not hovered
    t["scrollbar.indicator_r"] = str(shape.radius(sb_round, 4) + 1)
    sl = d["sliders"]["roundness"] if d["sliders"]["custom"] else 100
    t["slider.handle_r"] = str(shape.radius(sl, 16))
    t["slider.track_r"] = str(shape.radius(sl, 4))
    sw = d["switches"]["roundness"] if d["switches"]["custom"] else 100
    t["switch.r"] = str(shape.radius(sw, 22))
    t["switch.knob_r"] = str(shape.radius(sw, 18))
    fr = d["focus_ring"]
    if fr["custom"]:
        # your own ring: solid, in your color (or the accent), at your width (0 = off)
        t["focus.ring"] = pal.rgba(fr["color"] or theme["accent"], 1.0)
        t["focus.width"] = str(fr["width"])
        t["focus.style"] = "solid" if fr["width"] else "none"
    else:
        # default: subtle, like Mint-Y: 1px dashed, text color at 25%
        t["focus.ring"] = pal.rgba(theme["text"], 0.25)
        t["focus.width"] = "1"
        t["focus.style"] = "dashed"

    # --- Integration
    t["adw.accent_name"] = nearest_adw_accent(theme["accent"])
    _add_face_gradients(t, style)      # again, for the panel, menu and title-bar tokens
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
