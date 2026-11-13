"""Title button styles: the minimize, maximize and close buttons.

One description per style drives all three places title buttons are drawn,
so they match: Muffin's window borders (metacity-1, SVG faces and glyphs),
GTK 3 header bars and GTK 4 / libadwaita window controls (CSS).

A style says, for each kind of button (button, minimize, maximize, close) and
each state (rest, hover, pressed, backdrop = unfocused window), what face to
draw behind the glyph and in what colour the glyph is. Faces are "none", a
"rect" (rounded rectangle, filling the button) or a "circle" (centred).

    flat                glyph only; the style's title button on hover
                        (xl-Cheeselooks-flat, the original look)
    drawn               the style's normal button at rest (xl-Cheeselooks)
    classic             small square buttons in the title bar's colour
    dots                coloured dots; the glyph shows on hover
    gargantuan          wide, full-height buttons flush with the edge
    gargantuan-circles  the same size, with a circle on hover
    arrows              circles with chevron glyphs
    arrows-flat         chevrons, a circle only on hover
    claude              soft squircle hover with a small accent bar
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import palette as pal
from . import shape

STYLES = {
    "flat": "xl-Cheeselooks Flat",
    "drawn": "xl-Cheeselooks",
    "classic": "Classic",
    "dots": "Dots",
    "gargantuan": "Gargantuan",
    "gargantuan-circles": "Less Gargantuan",
    "arrows": "Arrows",
    "arrows-flat": "Arrows Flat",
    "claude": "Claude",
}
OLD_NAMES = {"theme": "flat", "wide": "gargantuan", "circles": "arrows"}

# Each style's own roundness, as a percentage of fully round (the Button
# roundness slider shows it until you move it). None: the theme's Roundness.
DEFAULT_ROUNDNESS = {
    "flat": None, "drawn": None, "classic": 25, "dots": 100, "gargantuan": 0,
    "gargantuan-circles": 100, "arrows": 100, "arrows-flat": 100, "claude": 60,
}


def roundness(style: str, chosen: int | None, theme_roundness: int) -> int:
    """The button roundness in use: yours, else the style's, else the theme's."""
    if chosen is not None:
        return chosen
    own = DEFAULT_ROUNDNESS.get(style)
    return theme_roundness if own is None else own


KINDS = ("button", "minimize", "maximize", "close")
STATES = ("rest", "hover", "pressed", "backdrop")
EDGE_PAD = 6          # px from the frame edge to the first/last button (headerbar padding)
GTK3_HEADER_PAD = 7   # Mint-Y's headerbar side padding (GTK 3)
GTK4_HEADER_PAD = 6   # and GTK 4 / libadwaita

# Our own glyphs (16px box, drawn as 1.6px strokes), for styles that don't
# use the theme's: arrows use chevrons, dots use small marks.
GLYPHS = {
    "chevron-down": "M4 6.2 8 10.2 12 6.2",
    "chevron-up": "M4 9.8 8 5.8 12 9.8",
    "diamond": "M8 3.6 12.4 8 8 12.4 3.6 8Z",
    "x": "M4.6 4.6 11.4 11.4M11.4 4.6 4.6 11.4",
    "minus": "M3.8 8H12.2",
    "plus": "M8 3.8V12.2M3.8 8H12.2",
    # gargantuan: thin 1px lines on a 24px box (Windows-like), crisp at 100% scale
    "thin-x": ("M7 7 17 17M17 7 7 17", 24, 1),
    "thin-min": ("M6.5 12.5H17.5", 24, 1),
    "thin-max": ("M7.5 7.5H16.5V16.5H7.5Z", 24, 1),
    "thin-restore": ("M7.5 9.5H14.5V16.5H7.5ZM9.5 9.5V7.5H16.5V14.5H14.5", 24, 1),
}
# glyph per window function, for styles with their own glyphs
CUSTOM_GLYPHS = {
    "arrows": {"close": "x", "minimize": "chevron-down", "maximize": "chevron-up", "unmaximize": "diamond"},
    "dots": {"close": "x", "minimize": "minus", "maximize": "plus", "unmaximize": "plus"},
}
CUSTOM_GLYPHS["arrows-flat"] = CUSTOM_GLYPHS["arrows"]
CUSTOM_GLYPHS["gargantuan"] = {"close": "thin-x", "minimize": "thin-min", "maximize": "thin-max",
                               "unmaximize": "thin-restore"}
CUSTOM_GLYPHS["gargantuan-circles"] = CUSTOM_GLYPHS["gargantuan"]

DOTS = {"close": ("#EF6A5F", "#E2554B"), "minimize": ("#F2C04F", "#E6AE33"),
        "maximize": ("#6BC46A", "#55B054")}


@dataclass(frozen=True)
class Face:
    shape: str = "none"            # none, rect, circle
    top: str = "transparent"
    bottom: str = "transparent"
    border: str | None = None      # a colour, or rgba(...) in CSS (the SVG gets its opacity)
    radius: int = 0
    corner: str | None = None      # gargantuan close: only this outer top corner rounded
    shadow3: str = "none"
    shadow4: str = "none"
    glyph: str | None = None       # glyph colour; None hides it
    bar: str | None = None         # claude: small accent bar under the glyph
    size: int = 0                  # circle diameter / rect side when smaller than the button


@dataclass(frozen=True)
class Geometry:
    w: int                         # button size: the area you can click
    h: int
    fw: int                        # the face drawn inside it (equal to w, h for flat / drawn / gargantuan)
    fh: int
    gap: int                       # between buttons (outside the click area)
    edge: int                      # frame edge to the outer button (metacity, without the border)
    pad_top: int                   # metacity: title bar top to the button
    pad_bottom: int
    glyph: int = 0                 # glyph size for our own glyphs (0 = the theme's natural size)
    full_height: bool = False      # gargantuan: buttons fill the title bar
    inner: bool = False            # the face is smaller than the button (drawn on the icon node in GTK)


def _even(n: float) -> int:
    """Nearest even number: an even face centres a 12/16/24px glyph on whole pixels."""
    return int(round(n / 2) * 2)


def geometry(style: str, t: dict[str, str]) -> Geometry:
    height, ctl = int(t["wb.height"]), int(t["wb.button_h"])
    bw = int(t["wb.border_width"])

    def centred(w: int, h: int, fw: int, fh: int, gap: int, glyph: int = 0, inner: bool = True) -> Geometry:
        h = min(h, height - bw - 2)
        top = (height - h) // 2
        return Geometry(w, h, fw, fh, gap, EDGE_PAD, top, height - h - top, glyph, False, inner)

    if style in ("gargantuan", "gargantuan-circles"):
        h = height - bw
        w = round(height * 1.16)
        if style == "gargantuan":
            return Geometry(w, h, w, h, 0, 0, bw, 0, 24, True)
        d = min(_even(height * 0.8), h - 4)             # a larger circle in the same wide slot
        return Geometry(w, h, d, d, 0, 0, bw, 0, 24, True, True)
    # the click area reaches a few px past the face on every side
    if style == "classic":
        side = _even(max(18, ctl * 0.72))
        return centred(side + 6, side + 8, side, side, 0)
    if style == "dots":
        # 16px: in GTK the face is drawn on the icon node, which is never
        # smaller than the 16px icon inside it (a smaller face put the glyph off centre)
        d = 16
        return centred(d + 8, d + 8, d, d, 0, 12)
    if style in ("arrows", "arrows-flat"):
        d = _even(ctl)
        return centred(d + max(6, round(d * 0.3)), d + 6, d, d, 0, 16)
    if style == "claude":
        fw, fh = _even(ctl * 1.12), _even(ctl)
        return centred(fw + 6, fh + 6, fw, fh, 0)
    w = round(ctl * 1.12)
    return centred(w, ctl, w, ctl, 2, inner=False)


def _kind(fn: str) -> str:
    return {"close": "close", "minimize": "minimize", "maximize": "maximize",
            "unmaximize": "maximize"}.get(fn, "button")


def faces(style: str, t: dict[str, str]) -> dict[tuple[str, str], Face]:
    """(kind, state) -> Face for every kind and state."""
    g = geometry(style, t)
    title, unf = t["wb.title"], t["wb.unfocused"]
    text, utext = t["wb.text"], t["wb.unfocused_text"]
    ptext = t["wbp.text"]
    tb, cb, bt = "wbp.w.title_button.", "wbp.w.close_button.", "wbp.w.button."
    acc_fg, acc_press = t["accent_fg"], t["accent_press"]
    pct = int(t["wb.button_roundness"])
    r = shape.radius(pct, min(g.fw, g.fh))

    def rect(top, bottom, border=None, s3="none", s4="none", glyph=None, **kw):
        return Face("rect", top, bottom, border, kw.pop("radius", r), shadow3=s3, shadow4=s4, glyph=glyph, **kw)

    def circle(color, glyph, border=None, size=None):
        d = size or min(g.fw, g.fh)
        return Face("circle", color, color, border, shape.radius(pct, d), glyph=glyph, size=d)

    none = lambda glyph: Face(glyph=glyph)  # noqa: E731
    style_hover = rect(t[tb + "hover_top"], t[tb + "hover_bottom"], t[tb + "hover_border"],
                       t[tb + "hover_shadow"], t[tb + "hover_g4_shadow"], ptext)
    style_pressed = rect(t["wbp.pressed"], t["wbp.pressed"], t[tb + "pressed_border"],
                         t[tb + "pressed_shadow"], t[tb + "pressed_g4_shadow"], ptext)
    close_hover = rect(t[cb + "hover_top"], t[cb + "hover_bottom"], acc_press,
                       t[cb + "hover_shadow"], t[cb + "hover_g4_shadow"], acc_fg)
    close_pressed = rect(acc_press, acc_press, acc_press, glyph=acc_fg)

    f: dict[tuple[str, str], Face] = {}

    def put(kinds, **states):
        for k in kinds:
            for s, face in states.items():
                f[(k, s)] = face

    if style == "drawn":
        rest = rect(t["wbp.button_top"], t["wbp.button_bottom"], t[bt + "border"],
                    t[bt + "shadow"], t[bt + "g4_shadow"], text)
        hover = rect(t[bt + "hover_top"], t[bt + "hover_bottom"], t[bt + "hover_border"],
                     t[bt + "hover_shadow"], t[bt + "hover_g4_shadow"], ptext)
        pressed = rect(t["wbp.pressed"], t["wbp.pressed"], t[bt + "pressed_border"],
                       t[bt + "pressed_shadow"], t[bt + "pressed_g4_shadow"], ptext)
        backdrop = rect(t["wbp.button"], t["wbp.button"], t[bt + "border"], glyph=utext)
        put(KINDS, rest=rest, hover=hover, pressed=pressed, backdrop=backdrop)
        put(["close"], hover=close_hover, pressed=close_pressed)
    elif style == "classic":
        # Clearlooks: small squares in the title bar's own colour, a lighter
        # outline toward the title text and a soft highlight along the top
        cr = r
        edge = pal.mix(title, text, 0.38)
        hi = "inset 0 1px 0 rgba(255, 255, 255, 0.22)"
        rest = rect(pal.lighter(title, 0.22), title, edge, hi, hi, text, radius=cr)
        hover = rect(pal.lighter(title, 0.42), pal.lighter(title, 0.14), pal.mix(title, text, 0.5),
                     hi, hi, text, radius=cr)
        pressed = rect(pal.darker(title, 0.10), pal.darker(title, 0.03), pal.mix(title, text, 0.5),
                       "inset 0 1px 2px rgba(0, 0, 0, 0.15)", "inset 0 1px 2px rgba(0, 0, 0, 0.15)",
                       text, radius=cr)
        backdrop = rect(unf, unf, pal.mix(unf, utext, 0.3), glyph=utext, radius=cr)
        put(KINDS, rest=rest, hover=hover, pressed=pressed, backdrop=backdrop)
    elif style == "dots":
        grey = pal.mix(title, text, 0.25)
        ring = "rgba(0, 0, 0, 0.14)"
        for k in KINDS:
            top, bottom = DOTS.get(k, (grey, grey))
            dot = pal.mix(top, bottom, 0.5)
            mark = pal.darker(dot, 0.6)
            f[(k, "rest")] = circle(dot, None, ring)
            f[(k, "hover")] = circle(dot, mark, ring)
            f[(k, "pressed")] = circle(pal.darker(dot, 0.15), mark, ring)
            f[(k, "backdrop")] = circle(pal.mix(unf, utext, 0.22), None, "rgba(0, 0, 0, 0.10)")
    elif style in ("gargantuan", "gargantuan-circles"):
        hover_c = pal.mix(t[tb + "hover_top"], t[tb + "hover_bottom"], 0.5)
        if style == "gargantuan":
            hover = rect(hover_c, hover_c, glyph=ptext)
            pressed = rect(t["wbp.pressed"], t["wbp.pressed"], glyph=ptext)
            ch = rect(t[cb + "hover_top"], t[cb + "hover_bottom"], glyph=acc_fg)
            cp = rect(acc_press, acc_press, glyph=acc_fg)
        else:
            d = g.fw
            hover_c = pal.mix(title, text, 0.12)       # a white circle barely shows on a light bar
            hover = circle(hover_c, ptext, size=d)
            pressed = circle(t["wbp.pressed"], ptext, size=d)
            ch = circle(pal.mix(t[cb + "hover_top"], t[cb + "hover_bottom"], 0.5), acc_fg, size=d)
            cp = circle(acc_press, acc_fg, size=d)
        put(KINDS, rest=none(text), hover=hover, pressed=pressed, backdrop=none(utext))
        put(["close"], hover=ch, pressed=cp)
    elif style in ("arrows", "arrows-flat"):
        flat = style == "arrows-flat"
        rest = none(text) if flat else circle(pal.mix(title, text, 0.10), text)
        backdrop = none(utext) if flat else circle(pal.mix(unf, utext, 0.08), utext)
        put(KINDS, rest=rest, hover=circle(pal.mix(title, text, 0.18), text),
            pressed=circle(pal.mix(title, text, 0.27), text), backdrop=backdrop)
        put(["close"], hover=circle(t["accent"], acc_fg), pressed=circle(acc_press, acc_fg))
    elif style == "claude":
        # quiet at rest; a soft squircle with a short accent bar on hover,
        # echoing the claude tabs; close fills with the accent
        sq = r
        soft = pal.mix(t[tb + "hover_top"], t[tb + "hover_bottom"], 0.5)
        put(KINDS, rest=none(pal.mix(text, title, 0.22)),
            hover=rect(soft, soft, glyph=ptext, radius=sq, bar=t["accent"]),
            pressed=rect(t["wbp.pressed"], t["wbp.pressed"], glyph=ptext, radius=sq, bar=acc_press),
            backdrop=none(utext))
        put(["close"], hover=rect(t["accent"], t["accent"], glyph=acc_fg, radius=sq),
            pressed=rect(acc_press, acc_press, glyph=acc_fg, radius=sq))
    else:  # flat
        put(KINDS, rest=none(text), hover=style_hover, pressed=style_pressed, backdrop=none(utext))
        put(["close"], hover=close_hover, pressed=close_pressed)
    return f


def outer_corner(style: str, layout: str, t: dict[str, str]) -> tuple[str | None, int]:
    """Gargantuan: the close button sits in the window's corner, so its outer
    top corner follows the window's roundness. Returns (side, radius)."""
    if style != "gargantuan":
        return None, 0
    side = "right" if layout.endswith("close") else "left"
    return side, max(0, int(t["r2"]) - int(t["wb.border_width"]))


# ------------------------------------------------------------------ SVG (metacity)

def _split_color(c: str) -> tuple[str, float]:
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", c)
    if m:
        r, g, b, a = m.groups()
        return pal.from_rgb(int(r), int(g), int(b)), float(a)
    return c, 1.0


def glyph_svg(name: str, color: str) -> str:
    c, a = _split_color(color)
    path, box, width = GLYPHS[name] if isinstance(GLYPHS[name], tuple) else (GLYPHS[name], 16, 1.6)
    cap = "square" if box == 24 else "round"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{box}" height="{box}" viewBox="0 0 {box} {box}">'
            f'<path d="{path}" fill="none" stroke="{c}" stroke-opacity="{a:g}" stroke-width="{width:g}" '
            f'stroke-linecap="{cap}" stroke-linejoin="miter"/></svg>')


def face_svg(face: Face, w: int, h: int, corner: tuple[str | None, int] = (None, 0)) -> str:
    """The face as an SVG the size of the button (metacity centres it)."""
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
             '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{face.top}"/><stop offset="1" stop-color="{face.bottom}"/>'
             '</linearGradient></defs>']
    stroke = ""
    if face.border:
        c, a = _split_color(face.border)
        stroke = f' stroke="{c}" stroke-opacity="{a:g}"'
    if face.shape == "circle":
        d = face.size or min(w, h)
        inset = 0.5 if face.border else 0
        if face.radius * 2 >= d:
            parts.append(f'<circle cx="{w / 2:g}" cy="{h / 2:g}" r="{d / 2 - inset:g}" fill="url(#g)"{stroke}/>')
        else:     # Button roundness below 100: a rounded square
            x0, y0 = (w - d) / 2 + inset, (h - d) / 2 + inset
            parts.append(f'<rect x="{x0:g}" y="{y0:g}" width="{d - 2 * inset:g}" height="{d - 2 * inset:g}" '
                         f'rx="{max(0, face.radius - inset):g}" fill="url(#g)"{stroke}/>')
    elif face.shape == "rect":
        side, cr = corner
        inset = 0.5 if face.border else 0
        x0, y0, x1, y1 = inset, inset, w - inset, h - inset
        if side and cr and not face.radius:
            if side == "right":
                path = f"M{x0} {y0}H{x1 - cr}A{cr} {cr} 0 0 1 {x1} {y0 + cr}V{y1}H{x0}Z"
            else:
                path = f"M{x0 + cr} {y0}H{x1}V{y1}H{x0}V{y0 + cr}A{cr} {cr} 0 0 1 {x0 + cr} {y0}Z"
            parts.append(f'<path d="{path}" fill="url(#g)"{stroke}/>')
        else:
            parts.append(f'<rect x="{x0:g}" y="{y0:g}" width="{x1 - x0:g}" height="{y1 - y0:g}" '
                         f'rx="{face.radius}" fill="url(#g)"{stroke}/>')
    if face.bar:
        bw_, bh = 10, 2
        parts.append(f'<rect x="{(w - bw_) / 2:g}" y="{h - 5:g}" width="{bw_}" height="{bh}" rx="1" '
                     f'fill="{face.bar}"/>')
    parts.append("</svg>")
    return "".join(parts)


def _name(*parts: str) -> str:
    return "tb-" + "-".join(p.lstrip("#").lower() for p in parts if p) + ".svg"


METACITY_ICONS = {"close": "close", "maximize": "max", "unmaximize": "restore", "minimize": "min",
                  "menu": "menu", "shade": "shade", "unshade": "unshade", "stick": "stick", "unstick": "unstick"}
CENTER = 'x="(width-object_width)/2" y="(height-object_height)/2" width="object_width" height="object_height"'


def metacity(style: str, t: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """(tokens, files): draw ops for every function x state, and the SVG files they use."""
    g = geometry(style, t)
    fc = faces(style, t)
    corner = outer_corner(style, t["wb.button_layout"], t)
    glyphs = CUSTOM_GLYPHS.get(style, {})
    files: dict[str, str] = {}
    tok: dict[str, str] = {}

    def face_op(face: Face, corner_=(None, 0)) -> str:
        if face.shape == "none":
            return ""
        name = _name("face", face.shape, face.top, face.bottom, face.border and _split_color(face.border)[0],
                     str(face.radius), face.bar, corner_[0], str(corner_[1]), str(face.size))
        files[name] = face_svg(face, g.fw, g.fh, corner_)
        return f'\t<image filename="{name}" {CENTER}/>\n'

    def glyph_op(fn: str, color: str | None) -> str:
        if color is None:
            return ""
        if fn in glyphs:
            c, _a = _split_color(color)
            name = _name(glyphs[fn], c)
            files[name] = glyph_svg(glyphs[fn], color)
            s = g.glyph or 16
            return (f'\t<image filename="{name}" x="(width-{s})/2" y="(height-{s})/2" '
                    f'width="{s}" height="{s}"/>\n')
        if g.glyph:      # the theme's glyph, scaled (gargantuan)
            s = g.glyph
            return (f'\t<image filename="{METACITY_ICONS[fn]}-icon.svg" colorize="{color}" '
                    f'x="(width-{s})/2" y="(height-{s})/2" width="{s}" height="{s}"/>\n')
        return f'\t<image filename="{METACITY_ICONS[fn]}-icon.svg" colorize="{color}" {CENTER}/>\n'

    for fn in METACITY_ICONS:
        k = _kind(fn)
        for state, op_state in (("rest", "focused"), ("hover", "prelight"), ("pressed", "pressed"),
                                ("backdrop", "unfocused")):
            face = fc[(k, state)]
            c = corner if fn == "close" else (None, 0)
            tok[f"wb.ops.{fn}_{op_state}"] = (face_op(face, c) + glyph_op(fn, face.glyph)) or "\t"
            if fn == "close" and corner[0]:
                # maximized and tiled windows have square corners
                tok[f"wb.ops.{fn}_{op_state}_square"] = (face_op(face) + glyph_op(fn, face.glyph)) or "\t"
            elif fn == "close":
                tok[f"wb.ops.{fn}_{op_state}_square"] = tok[f"wb.ops.{fn}_{op_state}"]
    return tok, files


# ------------------------------------------------------------------ CSS (GTK 3 and 4)

def _clear(color: str) -> str:
    """A colour at alpha 0. Fading to or from it keeps its hue: plain
    "transparent" is black at alpha 0, which shows as a dark edge mid-fade."""
    if color.startswith("rgba"):
        return re.sub(r",\s*[\d.]+\)$", ", 0)", color)
    if not pal.is_hex(color):
        return "transparent"
    return pal.rgba(color, 0)


def _edge_rule(gtk4: bool, margin: str) -> str:
    """Margin on the outermost button (next to the window edge), either layout."""
    if gtk4:
        return (f"headerbar windowcontrols.end > button:last-child:not(.osd) {{ margin-right: {margin}; }}\n"
                f"headerbar windowcontrols.start > button:first-child:not(.osd) {{ margin-left: {margin}; }}")
    return (f"headerbar box.right > button.titlebutton:last-child,\n"
            f".titlebar box.right > button.titlebutton:last-child {{ margin-right: {margin}; }}\n"
            f"headerbar box.left > button.titlebutton:first-child,\n"
            f".titlebar box.left > button.titlebutton:first-child {{ margin-left: {margin}; }}")


def css(style: str, t: dict[str, str], gtk4: bool = False) -> tuple[str, dict[str, str]]:
    """(css, asset files) for title buttons in GTK 3 header bars or GTK 4 window controls."""
    g = geometry(style, t)
    fc = faces(style, t)
    glyphs = CUSTOM_GLYPHS.get(style, {})
    side, cr = outer_corner(style, t["wb.button_layout"], t)
    files: dict[str, str] = {}
    pad = GTK4_HEADER_PAD if gtk4 else GTK3_HEADER_PAD

    if gtk4:
        bases = ["windowcontrols > button:not(.osd)"]
        img = "windowcontrols > button > image"
    else:
        bases = ["headerbar button.titlebutton", ".titlebar button.titlebutton"]
        img = "headerbar button.titlebutton image, .titlebar button.titlebutton image"

    def sel(cls: str, pseudo: str) -> str:
        return ", ".join(f"{b}{cls}{pseudo}" for b in bases)

    out = [f"/* Title buttons: {STYLES[style]} (cheeselooks/titlebuttons.py) */"]
    if gtk4:
        out.append("windowcontrols { border-spacing: 0; }")
    pseudos = {"rest": [""], "backdrop": [":backdrop"], "hover": [":hover", ":hover:backdrop"],
               "pressed": [":active", ":active:backdrop", ":checked"]}
    classes = {"button": "", "minimize": ".minimize", "maximize": ".maximize", "close": ".close"}
    child = " > image" if gtk4 else " image"
    assets = "assets/"
    has_bar = any(f.bar for f in fc.values())
    circles = any(f.shape == "circle" for f in fc.values())

    # The button: the click area. Inner styles draw nothing on it; their face is
    # drawn on the icon node inside, so the area can be larger than the face.
    if g.full_height:
        h = int(t["wb.height_inner"])
        margin = "0"
    else:
        h, margin = g.h, f"0 {g.gap // 2}px"
    border_px = 0 if g.inner else 1
    out.append(f"{sel('', '')} {{\n  min-width: {g.w - 2 * border_px}px;\n  min-height: {h - 2 * border_px}px;\n"
               f"  padding: 0;\n  margin: {margin};\n  -gtk-icon-shadow: none; }}")
    if g.full_height:
        out.append(_edge_rule(gtk4, f"-{pad}px"))
    if g.inner:
        every = ",\n".join(sel(c, p) for c in classes.values() for ps in pseudos.values() for p in ps)
        out.append(every + " {\n  border: none;\n  background-color: transparent;\n  background-image: none;\n"
                   "  box-shadow: none; }")
        # the face fades on its own node
        if gtk4:
            fade = ("transition-property: color, background-color, border-color, box-shadow;\n"
                    f"  transition-duration: {t['hover_out_ms']}ms;")
        else:
            fade = f"transition: all {t['hover_out_ms']}ms ease-out;"
        out.append(f"{sel('', child)} {{\n  {fade} }}")
        out.append(f"{sel('', ':hover' + child)} {{ transition-duration: {t['hover_in_ms']}ms; }}")
        out.append(f"{sel('', ':active' + child)} {{ transition-duration: 0; }}")
    elif glyphs:
        out.append(f"{sel('', child)} {{ color: transparent; }}")

    # glyph offsets in whole pixels (a glyph on a half pixel is blurry)
    if g.inner:
        box_w, box_h = g.fw - 2, g.fh - 2
    else:
        box_w, box_h = g.w - 2, h - 2
    # faces too small to hold the 16px icon inside a 1px border draw their
    # outline as an inset ring instead (dots)
    ring = g.inner and min(g.fw, g.fh) - 2 < 16
    if ring:
        box_w, box_h = g.fw, g.fh
    gs = g.glyph or 16
    glyph_pos = f"{(box_w - gs) // 2}px {(box_h - gs) // 2}px"

    def bg_layers(face: Face, glyph_name: str | None) -> tuple[list[str], list[str], list[str]]:
        layers, sizes, positions = [], [], []
        if glyph_name and face.glyph:
            c, _a = _split_color(face.glyph)
            name = _name(glyph_name, c)
            files[name] = glyph_svg(glyph_name, face.glyph)
            layers.append(f'url("{assets}{name}")')
            sizes.append(f"{gs}px {gs}px")
            positions.append(glyph_pos)
        if has_bar:
            bar = face.bar or _clear(t["accent"])
            layers.append(f"linear-gradient(to right, {bar}, {bar})")
            sizes.append("10px 2px")
            positions.append(f"{(box_w - 10) // 2}px {box_h // 2 + 6}px")    # just under the glyph
        if face.shape != "none" and face.top != face.bottom:
            layers.append(f"linear-gradient(to bottom, {face.top}, {face.bottom})")
            sizes.append("100% 100%")
            positions.append("0 0")
        return layers, sizes, positions

    def bg_decl(layers, sizes, positions) -> list[str]:
        out_ = [f"background-image: {', '.join(layers) if layers else 'none'};"]
        if layers:   # always set: Mint-Y sizes title button backgrounds at 80px
            out_ += [f"background-size: {', '.join(sizes)};",
                     f"background-position: {', '.join(positions)};", "background-repeat: no-repeat;"]
        return out_

    for kind, cls in classes.items():
        hv = fc[(kind, "hover")]
        hv_color = pal.mix(hv.top, hv.bottom, 0.5) if hv.shape != "none" else t["wb.title"]
        for state in STATES:
            face = fc[(kind, state)]
            target = child if g.inner else ""
            selectors = ",\n".join(sel(cls, p + target) for p in pseudos[state])
            drawn = face.shape != "none"
            if kind == "close" and side and cr and face.shape == "rect":
                rr = face.radius
                radius = (f"{rr}px {max(cr, rr)}px {rr}px {rr}px" if side == "right"
                          else f"{max(cr, rr)}px {rr}px {rr}px {rr}px")
            else:
                radius = f"{(face if drawn else hv).radius}px"
            border = face.border if (drawn and face.border) else _clear(hv.border or hv_color)
            bg = (pal.mix(face.top, face.bottom, 0.5) if face.shape == "circle" else face.bottom) if drawn \
                else _clear(hv_color)
            fn = {"close": "close", "minimize": "minimize", "maximize": "maximize"}.get(kind)
            layers = bg_layers(face, glyphs.get(fn) if glyphs and fn else None)
            shadow = (face.shadow4 if gtk4 else face.shadow3) if (drawn and face.shape == "rect") else "none"
            decl = [f"border-radius: {radius};", f"border: 1px solid {border};", f"box-shadow: {shadow};",
                    f"background-color: {bg};"] + bg_decl(*layers)
            if ring:
                decl[1] = "border: none;"
                inner_ring = f"inset 0 0 0 1px {border}"
                decl[2] = f"box-shadow: {inner_ring if shadow == 'none' else inner_ring + ', ' + shadow};"
            if g.inner:
                # the icon node fills the button unless held in by margins
                mx, my = (g.w - g.fw) // 2, (h - g.fh) // 2
                b2 = 0 if ring else 2
                decl = [f"min-width: {g.fw - b2}px;", f"min-height: {g.fh - b2}px;", "padding: 0;",
                        f"margin: {my}px {g.w - g.fw - mx}px {h - g.fh - my}px {mx}px;",
                        "-gtk-icon-shadow: none;"] + decl
            # our own glyphs replace the icon, which stays but is hidden
            decl.append(f"color: {'transparent' if glyphs else (face.glyph or 'transparent')};")
            out.append(selectors + " {\n  " + "\n  ".join(decl) + " }")
    if glyphs and "unmaximize" in glyphs and glyphs["unmaximize"] != glyphs["maximize"]:
        # a maximized window's maximize button restores: its own glyph
        win = "window.maximized" if gtk4 else ".maximized"
        target = child if g.inner else ""
        for state in STATES:
            face = fc[("maximize", state)]
            if not face.glyph:
                continue
            selectors = ",\n".join(f"{win} {b}.maximize{p}{target}" for b in bases for p in pseudos[state])
            out.append(selectors + " {\n  " + "\n  ".join(bg_decl(*bg_layers(face, glyphs["unmaximize"]))) + " }")
    if side and cr:
        # maximized and tiled windows have square corners
        win = "window" if gtk4 else ""
        sq = ", ".join(f"{win}.{s} {b}.close" for s in ("maximized", "tiled", "fullscreen") for b in bases)
        out.append(f"{sq} {{ border-radius: 0; }}")
    return "\n".join(out) + "\n", files


def tokens(t: dict[str, str]) -> dict[str, str]:
    """Title button tokens: metacity geometry and draw ops, the GTK 3 and GTK 4
    CSS, and the SVG files they use (as "file:<path>" tokens)."""
    style = t["wb.button_style"]
    g = geometry(style, t)
    out = {
        "wb.tb_w": str(g.w), "wb.tb_h": str(g.h),
        "wb.button_pad_top": str(g.pad_top), "wb.button_pad_bottom": str(g.pad_bottom),
        "wb.button_gap": str(g.gap // 2),
        "wb.edge": str(g.edge + int(t["wb.border_width"])),
    }
    ops, mfiles = metacity(style, t)
    out.update(ops)
    for name, svg in mfiles.items():
        out[f"file:metacity-1/{name}"] = svg
    c3, f3 = css(style, t)
    c4, f4 = css(style, t, gtk4=True)
    out["titlebuttons.css"] = c3
    out["titlebuttons4.css"] = c4
    for name, svg in f3.items():
        out[f"file:gtk-3.0/assets/{name}"] = svg
    for name, svg in f4.items():
        out[f"file:gtk-4.0/assets/{name}"] = svg
        out[f"file:libadwaita-1.5/assets/{name}"] = svg
    return out


__all__ = ["STYLES", "OLD_NAMES", "Face", "Geometry", "geometry", "faces", "metacity", "css", "tokens"]
