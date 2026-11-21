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
    # unfocused windows draw button layers at this fraction of their strength
    unfocused_depth = settings["style"].get("unfocused_depth", 70) / 100
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
    # the frame round a notebook's pages (Mint-Y's), which the tabs join
    # dividers, the lines between sections (frames, panes, toolbars, lists,
    # statusbars, tab frames, sidebars, separators): the style's `dividers`,
    # else mixed toward the text (Mint-Y's way: lighter than the background on
    # dark themes; Mint-Y Dark's own are darker)
    t["dividers"] = (sty._resolve_color(style.dividers, theme) if style.dividers
                     else pal.mix(theme["bg"], theme["text"], 0.234))
    t["frame"] = t["dividers"]
    t["separator_divider"] = t["dividers"] if style.dividers else pal.rgba(theme["text"], 0.1)
    _add_gradients(t, "", theme, amount)
    for k, v in shape.shape_tokens(g["size"], g["roundness"]).items():
        t[k] = str(v)
    t["hover_in_ms"] = str(g["hover_in_ms"])
    t["hover_out_ms"] = str(g["hover_out_ms"])
    _add_widgets(t, "", style, theme, depth, amount)
    # joined buttons whose container draws no CSS (Nemo's path bar): each
    # button carries its share of the group's outer layers (recess, shadow)
    for state in ("", "hover_", "pressed_"):
        inset = t[f"w.linked.{state}inset_shadow"]
        both = ", ".join(x for x in (inset, t["w.linked.outer"]) if x and x != "none") or "none"
        for pos in ("first", "middle", "last", "only"):
            # Nemo paints its folder buttons right to left (then its ◀ and ▶
            # scroll buttons, ▶ last of all: it takes the left-to-right end)
            t[f"w.linked.{state}{pos}_shadow"] = titlebuttons._group_shadow(both, pos, rtl_paint=True)
        t[f"w.linked.{state}ltr_last_shadow"] = titlebuttons._group_shadow(both, "last")
        # outer layers only, for Nemo's shared-edge rules (they add their own)
        t[f"w.linked.rtl_outer_{state}middle"] = titlebuttons._group_shadow(t["w.linked.outer"], "middle",
                                                                            rtl_paint=True)
        if state:
            # Nemo's shared edge (its seam) plus the group's piece, as one list
            # (a seam or a piece can be "none", e.g. at Depth 0)
            parts = [t[f"w.linked.{state}seam_shadow"], t[f"w.linked.rtl_outer_{state}middle"]]
            t[f"w.linked.nemo_{state}seam_shadow"] = ", ".join(x for x in parts if x and x != "none") or "none"
        # every other joined group: GTK boxes paint left to right
        _linked_ltr(t, "w.", state)
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
    # menus: Menu roundness for the menu itself, Menu-item roundness for the main
    # menu's items (other menus' items follow Global), Global's gradient
    m_round = g["roundness"] if ms["follow_global"] else ms["roundness"]
    m_item_round = g["roundness"] if ms["follow_global"] else ms.get("item_roundness", ms["roundness"])
    m_grad = g["gradient"]
    ctl = shape.size_value(g["size"])

    if style.panel.get("color"):
        # the style's panel color; its gradient and opacity are added as usual
        pcolors = {**pcolors, "panel": sty._resolve_color(style.panel["color"], pcolors)}
    _add_colors(t, "panel.", pcolors)
    _add_gradients(t, "panel.", pcolors, p_grad / 100)
    _add_widgets(t, "panel.", style, pcolors, depth, p_grad / 100)
    t["panel.r"] = str(shape.radius(p_round, panel_height))
    t["panel.height"] = str(panel_height)
    # light: 300, which needs a font with a Light face (Ubuntu, Noto Sans,
    # Inter...); a font without one shows Regular
    t["panel.label_weight"] = {"bold": "bold", "regular": "normal", "light": "300"}[p["label_weight"]]
    # the focused window's label: one step heavier, so it still stands out
    t["panel.label_weight_focus"] = {"bold": "bold", "regular": "bold", "light": "normal"}[p["label_weight"]]
    t["panel.opacity"] = f"{p['panel_opacity'] / 100:g}"
    t["panel_marker.css"] = panelmarker.css(t)

    # Cinnamon menus use the shell menu colors under the same names, so a
    # style's "menu_hover" means the right thing in GTK and in Cinnamon.
    mcolors = dict(pcolors, menu_bg=pcolors["shell_menu_bg"], menu_hover=pcolors["shell_menu_hover"])
    _add_colors(t, "menu.", mcolors)
    _add_gradients(t, "menu.", mcolors, m_grad / 100)
    _add_widgets(t, "menu.", style, mcolors, depth, m_grad / 100)
    # the main menu's selected category: [panel] menu_category (older styles:
    # menu_item's selected_color), else Mint-Y's grey
    mi = sty.resolved_widgets(style).get("menu_item", {})
    cat_expr = style.panel.get("menu_category") or mi.get("selected_color") or "mix(menu_bg, text, 0.123)"
    cat = sty._resolve_color(cat_expr, mcolors)
    t["menu.category"] = cat
    t["menu.category_top"], t["menu.category_bottom"] = pal.gradient(cat, m_grad / 100)
    t["menu.category_fg"] = (mcolors["accent_fg"] if cat == mcolors["accent"] else
                             max((mcolors["text"], mcolors["accent_fg"]), key=lambda c: pal.contrast(c, cat)))
    # the main menu's hover: [panel] menu_hover / menu_hover_fg, else a step
    # toward the text (the favorites column steps from its own background)
    if style.panel.get("menu_hover"):
        mh = sty._resolve_color(style.panel["menu_hover"], mcolors)
        # on the darker favorites column, the same step from its background
        fav_h = _shift(mh, mcolors["menu_bg"], mcolors["fav_bg"])
    else:
        mh, fav_h = mcolors["menu_hover"], mcolors["fav_hover"]
    if style.panel.get("menu_fav_hover"):
        fav_h = sty._resolve_color(style.panel["menu_fav_hover"], mcolors)
    if style.panel.get("menu_hover_fg"):
        mh_fg = sty._resolve_color(style.panel["menu_hover_fg"], mcolors)
    elif style.panel.get("menu_hover"):
        mh_fg = (mcolors["accent_fg"] if mh == mcolors["accent"] else
                 max((mcolors["text"], mcolors["accent_fg"]), key=lambda c: pal.contrast(c, mh)))
    else:
        mh_fg = mcolors["text"]
    t["menu.main_hover"], t["menu.main_hover_fg"], t["menu.fav_main_hover"] = mh, mh_fg, fav_h
    t["menu.main_hover_top"], t["menu.main_hover_bottom"] = pal.gradient(mh, m_grad / 100)
    # Cinnamon 6.4's sidebar (favorites with names, places, system buttons) has
    # its own background (Mint-Y's), lighter than the menu on dark themes: its
    # hover is the menu's hover moved by as much, or menu_fav_hover
    side_bg = pal.mix(mcolors["menu_bg"], mcolors["text"], 0.123)
    side_h = (fav_h if style.panel.get("menu_fav_hover") else _shift(mh, mcolors["menu_bg"], side_bg))
    t["menu.sidebar_bg"], t["menu.side_hover"] = side_bg, side_h
    t["menu.side_hover_bottom"] = pal.gradient(side_h, m_grad / 100)[1]
    t["menu.side_hover_fg"] = (mh_fg if not style.panel.get("menu_fav_hover") else
                               max((mcolors["text"], mcolors["accent_fg"]), key=lambda c: pal.contrast(c, side_h)))
    # the favorites' hover only shades downward: on their short square buttons a
    # lightened top washed out (xl-Classic Dark), so the top is the hover itself
    t["menu.fav_main_hover_top"] = fav_h
    t["menu.fav_main_hover_bottom"] = pal.gradient(fav_h, m_grad / 100)[1]
    m_r = shape.radius(m_round, ctl)
    t["menu.r"] = str(m_r)
    t["menu.r2"] = str(shape.window_radius(m_r))
    t["menu.item_r"] = str(shape.radius(m_item_round, ctl))         # the main menu's items
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
    t["unfocused_depth"] = f"{unfocused_depth:g}"
    t["wb.button_glyphs"] = wb["button_glyphs"] or ""      # "" = the style's own set
    t["wb.button_spacing"] = "" if wb.get("button_spacing") is None else str(wb["button_spacing"])
    t["wb.button_roundness"] = str(titlebuttons.roundness(wb["button_style"], wb["button_roundness"],
                                                          g["roundness"]))
    # the window's corners: your Window roundness, else Global's (as r2)
    wr = wb.get("window_roundness")
    t["wb.r"] = (str(shape.window_radius(shape.radius(wr, ctl))) if wr is not None else t["r2"])
    # the bottom corners: rounded only where the toolkit can (GTK 4 trims a
    # window's contents to its shape; GTK 3 rounds a window's own background)
    rb = ROUND_BOTTOM_READY and wb.get("round_bottom")
    t["wb.r_bottom"] = t["wb.r"] if rb else "0"
    t["wb.bottom3.css"] = _round_bottom(t["wb.r"], 3) if rb else ""
    t["wb.bottom4.css"] = _round_bottom(t["wb.r"], 4) if rb else ""
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
    # the line under header bars: the style's dividers when it sets them (on
    # the title bar's own colors), else the window border color as before
    t["wb.line"] = (sty._resolve_color(style.dividers, wb_pal) if style.dividers else t["wb.border"])
    for state in ("", "hover_", "pressed_"):
        _linked_ltr(t, "wbp.w.", state)
    # The suggested button on a header bar: its border and edge layers. When the
    # accent is close to the title bar's colour (xl-Classic Dark: a blue bar, a
    # blue accent), the accent's own darker border barely shows on the bar and
    # the button looked washed out beside the others: it takes the title-bar
    # buttons' border and edges then, keeping its accent face.
    near = _near_colour(g["accent"], title)
    src = "wbp.w.button." if near else "wbp.w.suggested."
    for k in ("border", "hover_border", "pressed_border", "shadow", "hover_shadow", "pressed_shadow"):
        t["wbp.sug." + k] = t[src + k]
    # the header bar's top highlight, on the title bar's own colour (Mint-Y's
    # base worked it out from the window background: a pale line on a dark bar)
    key = "highlight_dark" if pal.is_dark(wb_pal) else "highlight"
    hl = style.title_bar.get(key, sty.TITLE_BAR_KEYS[key])
    t["wb.highlight"] = f"inset 0 1px {pal.rgba('#FFFFFF', hl)}" if hl > 0 else "none"
    # windows Cinnamon decorates (Muffin 6): the window border's top and the
    # title bar's sides are drawn inside the title bar as inset lines, over
    # it as the metacity theme drew them, so its height and buttons don't move;
    # the highlight just under the top line
    bw = int(t["wb.border_width"])
    for name, colour in (("focused", t["wb.border"]), ("unfocused", t["wb.border_unfocused"])):
        parts = [f"inset 0 {bw}px {colour}", f"inset {bw}px 0 {colour}", f"inset -{bw}px 0 {colour}"] if bw else []
        if hl > 0:
            parts.append(f"inset 0 {bw + 1}px {pal.rgba('#FFFFFF', hl)}")
        t[f"wb.ssd_title_{name}"] = ", ".join(parts) or "none"
    _title_button_colors(t, style, theme, amount)
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
    if sb["custom"] and sb.get("width") is not None:     # yours, in either mode
        sb_width = sb["width"]
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
    # The default is subtle, like Mint-Y: 1px dashed, text colour at 25%. Each
    # setting changes only itself (a colour keeps the dashes; width 0 = off).
    custom = fr["custom"]
    color = fr["color"] if custom else None
    width = fr["width"] if custom else 1
    ring_style = fr["style"] if custom else "dashed"
    t["focus.ring"] = pal.rgba(color, 1.0) if color else pal.rgba(theme["text"], 0.25)
    # on selected rows (the accent): your colour blended two-thirds into the
    # selection, so a ring that's quiet on buttons isn't a bright outline there
    t["focus.ring_selected"] = (pal.mix(theme["select"], color, 0.35) if color
                                else pal.rgba(theme["accent_fg"], 0.35))
    t["focus.width"] = str(width)
    t["focus.style"] = ring_style if width else "none"

    # --- Integration
    t["adw.accent_name"] = nearest_adw_accent(theme["accent"])
    _add_face_gradients(t, style)      # again, for the panel, menu and title-bar tokens
    _title_gradient(t, style)
    t["lists.css"], t["lists4.css"] = _lists_css(g["roundness"], int(t["r"]), t["frame"])
    # the destructive button's border: the style's own (destructive = { border = ... }),
    # else a step darker than its face, as Mint-Y
    d_border = style.widgets.get("destructive", {}).get("border")
    t["destructive_border"] = (sty._resolve_color(d_border, theme) if d_border
                               else pal.darker(theme["destructive"], 0.14))
    # hover and pressed: the same border, set outright as the suggested
    # button's are (left unset, the plain buttons' hover border showed through)
    t["destructive_hover_border"] = t["destructive_pressed_border"] = t["destructive_border"]
    # Cinnamon's right-click and applet menus follow the same rule: square and
    # edge to edge up to Roundness 30, rounded and inset from the sides above
    if g["roundness"] <= SQUARE_LISTS_AT:
        t["popup_items.css"] = (".popup-menu-item { border-radius: 0; }")
    else:
        t["popup_items.css"] = (".popup-menu-content { padding-left: 6px; padding-right: 6px; }\n"
                                f".popup-menu-item {{ border-radius: {t['r']}px; }}")
    # every shadow at the unfocused strength, for :backdrop rules (bd.<token>)
    for k in [k for k in t if ("shadow" in k or "outer" in k)
              and not k.startswith("bd.")]:
        t["bd." + k] = pal.scale_shadow(t[k], unfocused_depth)
    return t


# Global Roundness at or below this: menu items and sidebar rows are square and
# full width (sidebars with divider lines, as Mint-Y); above it, rounded, with a
# little space at the sides so a rounded hover doesn't touch the menu's edges.
SQUARE_LISTS_AT = 30


# Round bottom corners is on the back burner (docs/design-spec.md, roadmap):
# the switch is hidden in the settings app and a saved "on" is ignored, so
# nobody is left with it stuck on. True brings both back.
ROUND_BOTTOM_READY = False

# Pieces that paint their own background into a window's bottom corners, by
# toolkit: (selector, corners). A sidebar is rounded with the scroller, viewport
# and list inside it (each paints); a tree view isn't (it draws every row with
# its own style, so its rows would round too: Nemo's sidebar).
_SIDEBAR_PARTS = ("{s}", "{s} scrolledwindow", "{s} viewport", "{s} list")
_SIDEBARS = {
    "left": (".sidebar:dir(ltr)", ".sidebar.left", "placessidebar:dir(ltr)", ".navigation-sidebar:dir(ltr)"),
    "right": (".sidebar:dir(rtl)", ".sidebar.right", "placessidebar:dir(rtl)", ".navigation-sidebar:dir(rtl)"),
}
_BOTTOM_PIECES = {
    3: ("actionbar",                        # GtkActionBar (Drawing, dialogs)
        "evview"),                          # Xreader's page view
    4: ("actionbar > revealer > box",),
}
_SQUARE_STATES = {3: ("maximized", "tiled", "fullscreen"),
                  4: ("maximized", "fullscreen", "tiled", "tiled-left", "tiled-right", "tiled-bottom")}


# a header bar's suggested button takes the title-bar buttons' border and
# edges when the accent is near the title bar's colour: the same hue (within
# NEAR_HUE degrees, both coloured) and not far in lightness (contrast below
# NEAR_CONTRAST), or nearly the same colour whatever the hue
NEAR_HUE, NEAR_CONTRAST = 20, 2.0


def _near_colour(a: str, b: str) -> bool:
    import colorsys
    c = pal.contrast(a, b)
    if c < 1.15:
        return True
    ha, _la, sa = colorsys.rgb_to_hls(*(v / 255 for v in pal.to_rgb(a)))
    hb, _lb, sb = colorsys.rgb_to_hls(*(v / 255 for v in pal.to_rgb(b)))
    dh = abs(((ha - hb + 0.5) % 1) - 0.5) * 360
    return sa > 0.15 and sb > 0.15 and dh < NEAR_HUE and c < NEAR_CONTRAST


def _shift(color: str, frm: str, to: str) -> str:
    """color moved by as much as `to` differs from `frm`, channel by channel:
    the same step from a different background."""
    c, a, b = pal.to_rgb(color), pal.to_rgb(frm), pal.to_rgb(to)
    return pal.from_rgb(*(min(255, max(0, c[i] + b[i] - a[i])) for i in range(3)))


def _round_bottom(r: str, gtk: int) -> str:
    """Neither GTK 3 nor a plain GTK 4 window trims its contents to its
    rounded corners, so the pieces that paint their own background into a
    bottom corner would square it again: they round that corner too. Emitted
    only with Round bottom corners on, so the switch off leaves every other
    radius alone."""
    corners = {side: [p.format(s=s) for s in sels for p in _SIDEBAR_PARTS] for side, sels in _SIDEBARS.items()}
    for piece in _BOTTOM_PIECES[gtk]:
        corners["left"].append(piece)
        corners["right"].append(piece)
    out = []
    for side, sels in corners.items():
        out.append(",\n".join(f"window.csd {x}" for x in sels) + f" {{\n  border-bottom-{side}-radius: {r}px; }}")
    every = dict.fromkeys(corners["left"] + corners["right"])
    sq = ",\n".join(f"window.csd.{m} {x}" for m in _SQUARE_STATES[gtk] for x in every)
    out.append(f"{sq} {{\n  border-bottom-left-radius: 0; border-bottom-right-radius: 0; }}")
    return "\n".join(out)


def _lists_css(roundness: float, r: int, line: str) -> tuple[str, str]:
    """GTK 3 and GTK 4 rules for menu items (not Cinnamon's) and sidebar rows:
    stack sidebars, and the places sidebar of file dialogs (GTK 3's
    placessidebar, GTK 4's navigation-sidebar). Square and edge to edge up to
    Roundness 30; rounded, with a little room at each end, above."""
    places3 = ("filechooser placessidebar.sidebar list row.sidebar-row,\n"
               ".nautilus-window placessidebar.sidebar list row.sidebar-row,\n"
               "placessidebar.sidebar list row.sidebar-row, placessidebar row")
    places4 = "placessidebar .navigation-sidebar > row, .navigation-sidebar > row"
    if roundness <= SQUARE_LISTS_AT:
        g3 = ("menu menuitem, .menu menuitem { margin: 0; border-radius: 0; }\n"
              "stacksidebar.sidebar row, stacksidebar.sidebar row:hover, stacksidebar.sidebar row:selected,\n"
              "stacksidebar row, stacksidebar row:hover, stacksidebar row:selected {\n"
              "  margin: 0; border-radius: 0; box-shadow: inset 0 -1px " + line + "; }\n"
              + places3 + " { margin: 0; border-radius: 0; }")
        g4 = ("popover.menu > contents { padding-left: 0; padding-right: 0; }\n"
              "popover.menu modelbutton { margin: 0; border-radius: 0; }\n"
              "stacksidebar.sidebar row, stacksidebar.sidebar row:hover, stacksidebar.sidebar row:selected,\n"
              "stacksidebar row, stacksidebar row:hover, stacksidebar row:selected {\n"
              "  margin: 0; border-radius: 0; box-shadow: inset 0 -1px " + line + "; }\n"
              + places4 + " { margin: 0; border-radius: 0; }")
    else:
        # rounded rows float in the list: no dividers (said outright, so the
        # square version's lines don't show through from another theme underneath)
        rows = ("stacksidebar.sidebar row, stacksidebar.sidebar row:hover, stacksidebar.sidebar row:selected,\n"
                "stacksidebar row, stacksidebar row:hover, stacksidebar row:selected {\n"
                f"  margin: 2px 6px; border-radius: {r}px; box-shadow: none; }}")
        g3 = (f"menu menuitem, .menu menuitem {{ margin: 0 2px; border-radius: {r}px; }}\n" + rows + "\n"
              + places3 + f" {{ margin: 1px 6px; border-radius: {r}px; }}")
        g4 = (f"popover.menu > contents {{ padding-left: 8px; padding-right: 8px; }}\n"
              f"popover.menu modelbutton {{ margin: 0 2px; border-radius: {r}px; }}\n" + rows + "\n"
              + places4 + f" {{ margin: 1px 6px; border-radius: {r}px; }}")
    note = "/* Menu items and sidebar rows: square below Roundness " + str(SQUARE_LISTS_AT + 1) + " (tokens._lists_css) */\n"
    return note + g3 + "\n", note + g4 + "\n"


def _linked_ltr(t: dict[str, str], prefix: str, state: str) -> None:
    """A joined group's share per button (GTK boxes paint left to right), from
    the window's palette ("w.") or the title bar's ("wbp.w.", header bars)."""
    inset = t[f"{prefix}linked.{state}inset_shadow"]
    both = ", ".join(x for x in (inset, t[f"{prefix}linked.outer"]) if x and x != "none") or "none"
    for pos in ("first", "middle", "last", "only"):
        t[f"{prefix}linked.ltr_{state}{pos}_shadow"] = titlebuttons._group_shadow(both, pos)


def _title_button_colors(t: dict[str, str], style: sty.Style, theme: dict[str, str], amount: float) -> None:
    """[title_buttons]: the window buttons' own colours (tbtn.*; "" = unset), read
    against the theme's palette. Each face gets a gradient pair and a glyph
    colour that reads on it (your glyph, else the better of the title text and
    the theme's text)."""
    tb = style.title_buttons

    def ev(key: str) -> str:
        v = tb.get(key)
        if not v:
            return ""
        return theme[v] if v in theme else (v if pal.is_hex(v) else render.evaluate(v, theme))
    glyph = ev("glyph")
    candidates = (t["wb.text"], theme["text"], theme["accent_fg"])
    base = ev("color")
    # with only a face colour, hover and pressed follow it (as the palette's own
    # button hover and pressed face follow the button)
    defaults = {"hover_color": render.evaluate(f"lift({base}, 0.06)", theme) if base else "",
                "pressed_color": pal.darker(base, 0.12) if base else ""}
    for key in ("color", "hover_color", "pressed_color"):
        c = ev(key) or defaults.get(key, "")
        t[f"tbtn.{key}"] = c
        if c:
            top, bottom = pal.gradient(c, amount) if key != "pressed_color" else (c, c)
            t[f"tbtn.{key}_top"], t[f"tbtn.{key}_bottom"] = top, bottom
            t[f"tbtn.{key}_fg"] = glyph or max(candidates, key=lambda x: pal.contrast(x, c))
    t["tbtn.border"] = ev("border")
    t["tbtn.hover_border"] = ev("hover_border") or t["tbtn.border"]
    t["tbtn.glyph"] = glyph
    ch = tb.get("close_hover", "accent")
    t["tbtn.close_hover"] = ch if ch in ("accent", "hover") else ev("close_hover")
    if t["tbtn.close_hover"] not in ("accent", "hover"):
        c = t["tbtn.close_hover"]
        t["tbtn.close_hover_top"], t["tbtn.close_hover_bottom"] = pal.gradient(c, amount)
        t["tbtn.close_hover_fg"] = max(candidates, key=lambda x: pal.contrast(x, c))
        t["tbtn.close_pressed"] = pal.darker(c, 0.12)


def _title_gradient(t: dict[str, str], style: sty.Style) -> None:
    """The focused title bar's gradient in the style's [title_bar] shape (smooth
    by default), as CSS for header bars and draw ops for Muffin's title bars."""
    tb = style.title_bar
    shape = (tb.get("gradient_shape", "smooth"), float(tb.get("split_step", 0.4)),
             float(tb.get("glass_return", 0.4)))
    top, bottom = t["wb.title_top"], t["wb.title_bottom"]
    t["wb.title_grad"] = pal.gradient_css(top, bottom, *shape)
    stops = pal.gradient_stops(top, bottom, *shape)

    def grad(y: str, h: str, a: str, b: str) -> str:
        return (f'<gradient type="vertical" x="0" y="{y}" width="width" height="{h}">'
                f'<color value="{a}"/><color value="{b}"/></gradient>')
    if len(stops) == 4:
        # metacity gradients have evenly spaced colours, so a step is two gradients
        t["wb.ops.titlebar_focused"] = (grad("0", "height/2", stops[0][1], stops[1][1]) + "\n\t"
                                        + grad("height/2", "height-height/2", stops[2][1], stops[3][1]))
    else:
        t["wb.ops.titlebar_focused"] = grad("0", "height", top, bottom)


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
