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
    linked              the same, joined into one group (shared borders, rounded
                        outer ends, the recess / shadow round the whole group)
    classic             the style's own buttons, small and square
    dots                coloured dots; the glyph shows on hover
    gargantuan          wide, full-height buttons flush with the edge
    gargantuan-circles  the same size, with a circle on hover
    unpretentious       plain circles (squares with less Button roundness)
    unpretentious-flat  the same, a circle only on hover
    claude              soft squircle hover with a small accent bar
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace

from . import palette as pal
from . import shape

STYLES = {
    "flat": "xl-Cheeselooks Flat",
    "drawn": "xl-Cheeselooks",
    "linked": "xl-Cheeselooks Linked",
    "classic": "Classic",
    "dots": "Dots",
    "gargantuan": "Gargantuan",
    "gargantuan-circles": "Less Gargantuan",
    "unpretentious": "Unpretentious",
    "unpretentious-flat": "Unpretentious Flat",
    "claude": "Claude",
}
OLD_NAMES = {"theme": "flat", "wide": "gargantuan", "circles": "unpretentious",
             "arrows": "unpretentious", "arrows-flat": "unpretentious-flat"}

# Each style's own roundness, as a percentage of fully round (the Button
# roundness slider shows it until you move it). None: the theme's Roundness.
DEFAULT_ROUNDNESS = {
    "flat": None, "drawn": None, "linked": None, "classic": 25, "dots": 100, "gargantuan": 0,
    "gargantuan-circles": 100, "unpretentious": 100, "unpretentious-flat": 100, "claude": 60,
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
GTK3_BUTTON_SPACING = 6   # GtkHeaderBar's spacing between its window buttons
# A GTK 3 header bar's own content (a 34px button with Mint-Y's 6px margins):
# headerbars are never shorter, so Gargantuan buttons are at least this tall
HEADERBAR_CONTENT = 46
# Button spacing: extra space between window buttons, on top of each style's
# own gap, the same in GTK 3 and GTK 4 apps and on Muffin's borders. Each style
# has its own default; Button spacing (0-12px) overrides it, except for the
# styles whose buttons are made to touch.
SPACING_LOCKED = ("linked", "gargantuan")
SPACING_DEFAULT = {"classic": 0, "gargantuan-circles": 0}      # others: 6 (GTK 3's own)
SPACING_RANGE = (0, 12)


def spacing(style: str, t: dict[str, str] | None = None) -> int:
    """Extra space between window buttons: yours (Button spacing), else the style's."""
    if style in SPACING_LOCKED:
        return 0
    chosen = (t or {}).get("wb.button_spacing", "")
    if chosen not in ("", None):
        return int(chosen)
    return SPACING_DEFAULT.get(style, GTK3_BUTTON_SPACING)

# Glyphs. Every set is ours (drawn as SVG at the size each style uses), so
# apps, window borders and the settings app's picker always match, except
# "icons", which takes the icon theme's (GTK draws those itself; window borders
# get copies from the icon theme at Apply, falling back to "regular").
#
#   stroked glyphs: a path on a 16px box, 1.6px round strokes
GLYPHS = {
    "chevron-down": "M4 6.2 8 10.2 12 6.2",
    "chevron-up": "M4 9.8 8 5.8 12 9.8",
    "diamond": "M8 3.6 12.4 8 8 12.4 3.6 8Z",
    "x": "M4.6 4.6 11.4 11.4M11.4 4.6 4.6 11.4",
    "minus": "M3.8 8H12.2",
    "plus": "M8 3.8V12.2M3.8 8H12.2",
}
#   filled glyphs on a 16px box: Mint-Y's window button artwork (GPL-3+,
#   Linux Mint), redrawn here as our own "regular" set
FILLED = {
    "mint-close": "M4.795 3.912l-.883.883.147.146L7.117 8 4.06 11.059l-.147.146.883.883.146-.147L8 8.883"
                  "l3.059 3.058.146.147.883-.883-.147-.146L8.883 8l3.058-3.059.147-.146-.883-.883-.146.147"
                  "L8 7.117 4.941 4.06z",
    "mint-max": "M4 4v8h8V4zm1 1h6v6H5z",
    "mint-min": "M4 10v1h8v-1z",
    "mint-restore": "m3 5v8h8V5Zm1 1h6v6H4ZM5 3v1h7v7h1V3Z",
}
GLYPH_SETS = {
    "regular": {"close": "mint-close", "minimize": "mint-min", "maximize": "mint-max", "unmaximize": "mint-restore"},
    "thin": {"close": "thin-x", "minimize": "thin-min", "maximize": "thin-max", "unmaximize": "thin-restore"},
    "chevrons": {"close": "x", "minimize": "chevron-down", "maximize": "chevron-up", "unmaximize": "diamond"},
    "marks": {"close": "x", "minimize": "minus", "maximize": "plus", "unmaximize": "plus"},
}
GLYPH_SET_NAMES = {"regular": "Regular", "thin": "Thin", "chevrons": "Chevrons", "marks": "Marks",
                   "icons": "Icon Theme"}
# each style's own set (the picker shows it until you choose another)
STYLE_GLYPHS = {"dots": "marks", "gargantuan": "thin", "gargantuan-circles": "thin",
                "unpretentious": "chevrons", "unpretentious-flat": "chevrons"}


def glyph_set(style: str, chosen: str | None) -> str:
    """The glyph set in use: yours, else the style's own."""
    return chosen or STYLE_GLYPHS.get(style, "regular")


def _glyphs(t: dict[str, str], style: str) -> dict[str, str]:
    """function -> glyph name for our own sets; {} for the icon theme's."""
    return GLYPH_SETS.get(glyph_set(style, t.get("wb.button_glyphs") or None), {})


def _thin(name: str, size: int) -> str:
    """Thin glyphs: 1px lines drawn for this size, on whole pixels (crisp)."""
    p = size
    if name == "thin-min":
        a, m = round(p * 0.27) + 0.5, p // 2 + 0.5
        return f"M{a:g} {m:g}H{p - a:g}"
    if name == "thin-max":
        c = round(p * 0.31) + 0.5
        return f"M{c:g} {c:g}H{p - c:g}V{p - c:g}H{c:g}Z"
    if name == "thin-restore":
        c, o = round(p * 0.31) + 0.5, max(1, round(p / 12))
        return (f"M{c:g} {c + o:g}H{p - c - o:g}V{p - c:g}H{c:g}Z"
                f"M{c + o:g} {c + o:g}V{c:g}H{p - c:g}V{p - c - o:g}H{p - c - o:g}")
    c = round(p * 0.29)
    return f"M{c} {c} {p - c} {p - c}M{p - c} {c} {c} {p - c}"


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
        d = min(_even(height * 0.8), h - 4)             # a larger circle in a wide slot
        w = d + round((w - d) * 0.64)                   # the gap between circles 20% smaller, twice
        return Geometry(w, h, d, d, 0, 0, bw, 0, 24, True, True)
    # the click area reaches a few px past the face on every side
    if style == "classic":
        side = _even(max(18, ctl * 0.72))
        return centred(side + 4, side + 8, side, side, 0)     # 4px apart, as Clearlooks
    if style == "dots":
        # 16px: in GTK the face is drawn on the icon node, which is never
        # smaller than the 16px icon inside it (a smaller face put the glyph off centre)
        d = 16
        return centred(d + 8, d + 8, d, d, 0, 12)
    if style in ("unpretentious", "unpretentious-flat"):
        d = _even(ctl)
        return centred(d + max(6, round(d * 0.3)), d + 6, d, d, 0, 16)
    if style == "claude":
        fw, fh = _even(ctl * 1.12), _even(ctl)
        return centred(fw + 6, fh + 6, fw, fh, 0)
    w = round(ctl * 1.12)
    if style == "linked":
        return centred(w, ctl, w, ctl, 0, inner=False)      # joined: no gap
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
    # the accent close face takes the style's suggested-button border (an accent
    # face's rim: on dark styles a darker one, the accent's own shade read as a
    # light edge there), on the title bar's palette
    sug = "wbp.w.suggested."
    close_hover = rect(t[cb + "hover_top"], t[cb + "hover_bottom"], t[sug + "hover_border"],
                       t[cb + "hover_shadow"], t[cb + "hover_g4_shadow"], acc_fg)
    close_pressed = rect(acc_press, acc_press, t[sug + "pressed_border"], glyph=acc_fg)

    f: dict[tuple[str, str], Face] = {}

    def put(kinds, **states):
        for k in kinds:
            for s, face in states.items():
                f[(k, s)] = face

    if style in ("drawn", "linked", "classic"):
        # the style's own buttons (Classic: the same, smaller, in its own size);
        # a style's [title_buttons] colours replace the faces, borders and glyphs
        own = lambda key: t.get(f"tbtn.{key}", "")    # noqa: E731
        border = own("border") or t[bt + "border"]
        hover_border = own("hover_border") or t[bt + "hover_border"]
        # unfocused: flat face, the same layers at the Unfocused depth
        ud = float(t.get("unfocused_depth", "0.7"))
        bd3, bd4 = pal.scale_shadow(t[bt + "shadow"], ud), pal.scale_shadow(t[bt + "g4_shadow"], ud)
        if own("color"):
            rest = rect(own("color_top"), own("color_bottom"), border,
                        t[bt + "shadow"], t[bt + "g4_shadow"], own("color_fg"))
            backdrop = rect(own("color"), own("color"), border, bd3, bd4,
                            glyph=pal.mix(own("color_fg"), own("color"), 0.45))
        else:
            rest = rect(t["wbp.button_top"], t["wbp.button_bottom"], border,
                        t[bt + "shadow"], t[bt + "g4_shadow"], own("glyph") or text)
            backdrop = rect(t["wbp.button"], t["wbp.button"], border, bd3, bd4, glyph=utext)
        hc = own("hover_color")
        hover = rect(own("hover_color_top") if hc else t[bt + "hover_top"],
                     own("hover_color_bottom") if hc else t[bt + "hover_bottom"], hover_border,
                     t[bt + "hover_shadow"], t[bt + "hover_g4_shadow"],
                     own("hover_color_fg") if hc else (own("glyph") or ptext))
        pc = own("pressed_color")
        pressed = rect(pc or t["wbp.pressed"], pc or t["wbp.pressed"],
                       own("hover_border") or own("border") or t[bt + "pressed_border"],
                       t[bt + "pressed_shadow"], t[bt + "pressed_g4_shadow"],
                       own("pressed_color_fg") if pc else (own("glyph") or ptext))
        put(KINDS, rest=rest, hover=hover, pressed=pressed, backdrop=backdrop)
        if style in ("drawn", "linked"):      # Classic's close hovers like the other two
            put(["close"], hover=close_hover, pressed=close_pressed)
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
    elif style in ("unpretentious", "unpretentious-flat"):
        flat = style == "unpretentious-flat"
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
    if style != "dots":         # the dots' hover colours are their own (close stays red)
        _close_hover(f, t)
    return f


def _close_hover(f: dict, t: dict[str, str]) -> None:
    """[title_buttons] close_hover: "hover" gives close the other buttons' hover
    and pressed faces; a colour gives it a face of that colour (in the style's
    own shape: rect, circle, with or without the claude bar)."""
    ch = t.get("tbtn.close_hover", "accent")
    if ch == "accent" or not ch:
        return
    for state in ("hover", "pressed"):
        face = f[("close", state)]
        if ch == "hover":
            f[("close", state)] = f[("minimize", state)]
            continue
        if face.shape == "none":
            continue
        top, bottom = ((t["tbtn.close_hover_top"], t["tbtn.close_hover_bottom"]) if state == "hover"
                       else (t["tbtn.close_pressed"],) * 2)
        f[("close", state)] = replace(face, top=top, bottom=bottom,
                                      border=(pal.darker(bottom, 0.15) if face.border else None),
                                      glyph=t["tbtn.close_hover_fg"],
                                      bar=(face.bar and pal.darker(bottom, 0.25)))


def outer_corner(style: str, layout: str, t: dict[str, str]) -> tuple[str | None, int]:
    """Gargantuan: the close button sits in the window's corner, so its outer
    top corner follows the window's roundness. Returns (side, radius)."""
    if style != "gargantuan":
        return None, 0
    side = "right" if layout.endswith("close") else "left"
    return side, max(0, int(t["wb.r"]) - int(t["wb.border_width"]))


# ------------------------------------------------------------------ SVG (metacity)

def _split_color(c: str) -> tuple[str, float]:
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", c)
    if m:
        r, g, b, a = m.groups()
        return pal.from_rgb(int(r), int(g), int(b)), float(a)
    return c, 1.0


def glyph_svg(name: str, color: str, size: int = 16) -> str:
    """A glyph in one colour, as an SVG the size it's shown. Filled and stroked
    glyphs are drawn on a 16px grid; thin ones are drawn for the size itself."""
    c, a = _split_color(color)
    # written at the size it's shown (the drawing stays on its 16px grid): GTK 3
    # turns an SVG into pixels at its own size before scaling, so a 16px SVG
    # shown at 24 (Gargantuan) was blurred
    if name in FILLED:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 16 16">'
                f'<path d="{FILLED[name]}" fill="{c}" fill-opacity="{a:g}"/></svg>')
    if name.startswith("thin-"):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
                f'viewBox="0 0 {size} {size}"><path d="{_thin(name, size)}" fill="none" stroke="{c}" '
                f'stroke-opacity="{a:g}" stroke-width="1" stroke-linecap="square" stroke-linejoin="miter"/></svg>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 16 16">'
            f'<path d="{GLYPHS[name]}" fill="none" stroke="{c}" stroke-opacity="{a:g}" stroke-width="1.6" '
            'stroke-linecap="round" stroke-linejoin="miter"/></svg>')


ICON_NAMES = {"close": "window-close-symbolic", "minimize": "window-minimize-symbolic",
              "maximize": "window-maximize-symbolic", "unmaximize": "window-restore-symbolic"}


def icon_theme_glyph(fn: str, color: str) -> str | None:
    """The icon theme's glyph for a window function as an SVG in one colour, for
    Muffin's window borders (GTK draws icon theme glyphs itself); None if the
    icon theme (or one it inherits) has no SVG for it."""
    from . import reload       # gsettings: which icon theme
    name = ICON_NAMES.get(fn)
    theme = (reload.get("org.cinnamon.desktop.interface", "icon-theme") if reload.available() else None)
    if not name or not theme:
        return None
    from pathlib import Path
    roots = [Path.home() / ".icons", Path.home() / ".local/share/icons", Path("/usr/share/icons")]
    seen, queue = set(), [theme]
    while queue:
        th = queue.pop(0)
        if th in seen:
            continue
        seen.add(th)
        for root in roots:
            d = root / th
            if not d.is_dir():
                continue
            hits = sorted(d.rglob(f"{name}.svg"), key=lambda f: ("scalable" not in str(f), "16" not in str(f)))
            if hits:
                svg = hits[0].read_text(encoding="utf-8", errors="replace")
                c, _a = _split_color(color)
                svg = re.sub(r"fill:\s*#[0-9a-fA-F]{3,6}", f"fill:{c}", svg)
                svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', f'fill="{c}"', svg)
                return re.sub(r"<svg\b", f'<svg fill="{c}"', svg, count=1)
            index = d / "index.theme"
            if index.exists():
                m = re.search(r"^Inherits\s*=\s*(.+)$", index.read_text(errors="replace"), re.M)
                if m:
                    queue += [x.strip() for x in m.group(1).split(",") if x.strip()]
    return None


def _shape(t: dict[str, str]) -> tuple[str, float, float]:
    """The style's face gradient: (shape, split_step, glass_return)."""
    return (t.get("style.gradient_shape", "smooth"), float(t.get("style.split_step", 0.4)),
            float(t.get("style.glass_return", 0.4)))


def _shadow_layers(shadow: str) -> list[tuple[bool, float, float, float, float, str]]:
    """A CSS box-shadow list as (inset, x, y, blur, spread, colour) layers."""
    parts, depth, cur = [], 0, ""
    for ch in shadow:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    out = []
    for layer in parts:
        if not layer or layer == "none":
            continue
        inset = layer.startswith("inset ")
        m = re.match(r"(?:inset )?(\S+) (\S+)(?: (\S+px|0))?(?: (\S+px|0))? (.+)$", layer)
        if not m:
            continue
        num = [float(v[:-2]) if v and v.endswith("px") else float(v or 0) for v in m.groups()[:4]]
        out.append((inset, *num, m.group(5)))
    return out


def shadowed_face_svg(face: Face, w: int, h: int, shadow: str,
                      shape: tuple[str, float, float] = ("smooth", 0.4, 0.4)) -> tuple[str, int]:
    """The face with its box-shadow layers drawn in (recess, drop shadow, inner
    highlights), for Muffin, which draws a face only as a background image.
    Returns the SVG and the padding round the face it needs for the shadows."""
    layers = _shadow_layers(shadow) if face.shape == "rect" else []
    pad = int(max([abs(x) + abs(y) + b + max(sp, 0) for ins, x, y, b, sp, _c in layers if not ins] or [0]) + 0.999)
    W, H, r = w + 2 * pad, h + 2 * pad, face.radius
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', "<defs>"]
    body, n = [], 0

    def blur_attr(b: float) -> str:
        nonlocal n
        if not b:
            return ""
        n += 1
        parts.append(f'<filter id="b{n}" x="-50%" y="-50%" width="200%" height="200%">'
                     f'<feGaussianBlur stdDeviation="{b / 2:g}"/></filter>')
        return f' filter="url(#b{n})"'

    def rect(x: float, y: float, rw: float, rh: float, rr: float) -> str:
        return (f'x="{x:g}" y="{y:g}" width="{max(rw, 0):g}" height="{max(rh, 0):g}" '
                f'rx="{max(rr, 0):g}"')
    # CSS paints the first shadow on top: draw them last to first
    outer = [l for l in layers if not l[0]][::-1]
    inner = [l for l in layers if l[0]][::-1]
    for _i, x, y, b, sp, c in outer:
        cc, a = _split_color(c)
        body.append(f'<rect {rect(pad + x - sp, pad + y - sp, w + 2 * sp, h + 2 * sp, r + sp)} '
                    f'fill="{cc}" fill-opacity="{a:g}"{blur_attr(b)}/>')
    body.append(f'<svg x="{pad}" y="{pad}" width="{w}" height="{h}">'
                + face_svg(face, w, h, (None, 0), shape).split(">", 1)[1].rsplit("</svg>", 1)[0] + "</svg>")
    if inner:
        bw = 1 if face.border else 0
        parts.append(f'<clipPath id="in"><rect {rect(pad + bw, pad + bw, w - 2 * bw, h - 2 * bw, r - bw)}/></clipPath>')
        for _i, x, y, b, sp, c in inner:
            cc, a = _split_color(c)
            hole = (f"M{pad + bw + x + sp:g} {pad + bw + y + sp:g}h{w - 2 * bw - 2 * sp:g}"
                    f"v{h - 2 * bw - 2 * sp:g}h{-(w - 2 * bw - 2 * sp):g}Z")
            body.append(f'<path clip-path="url(#in)" fill-rule="evenodd" fill="{cc}" fill-opacity="{a:g}"'
                        f'{blur_attr(b)} d="M-50 -50H{W + 50}V{H + 50}H-50Z{hole}"/>')
    parts.append("</defs>")
    return "".join(parts + body) + "</svg>", pad


def _rounded_rect(x0: float, y0: float, x1: float, y1: float, radii: tuple[float, float, float, float]) -> str:
    """An SVG path for a rectangle with its own radius per corner (tl, tr, br, bl)."""
    tl, tr, br, bl = radii
    return (f"M{x0 + tl:g} {y0:g}H{x1 - tr:g}" + (f"A{tr:g} {tr:g} 0 0 1 {x1:g} {y0 + tr:g}" if tr else "")
            + f"V{y1 - br:g}" + (f"A{br:g} {br:g} 0 0 1 {x1 - br:g} {y1:g}" if br else "")
            + f"H{x0 + bl:g}" + (f"A{bl:g} {bl:g} 0 0 1 {x0:g} {y1 - bl:g}" if bl else "")
            + f"V{y0 + tl:g}" + (f"A{tl:g} {tl:g} 0 0 1 {x0 + tl:g} {y0:g}" if tl else "") + "Z")


def face_svg(face: Face, w: int, h: int, corner: tuple[str | None, int] = (None, 0),
             shape: tuple[str, float, float] = ("smooth", 0.4, 0.4), joined: str | None = None) -> str:
    """The face as an SVG the size of the button (metacity centres it), with the
    style's gradient shape (smooth, split or glass), as the GTK buttons have."""
    stops = "".join(f'<stop offset="{o:g}" stop-color="{c}"/>'
                    for o, c in pal.gradient_stops(face.top, face.bottom, *shape))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
             f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">{stops}</linearGradient></defs>']
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
    elif face.shape == "rect" and joined:
        # Linked: rounded only at the group's outer ends; every button draws its
        # left edge and only the last its right one, so neighbours share one line
        inset = 0.5 if face.border else 0
        r = face.radius
        radii = {"first": (r, 0, 0, r), "last": (0, r, r, 0), "middle": (0, 0, 0, 0), "only": (r, r, r, r)}[joined]
        open_right = joined in ("first", "middle")
        x1 = w + 1 if open_right else w - inset          # past the edge: no right border line
        parts.append(f'<path d="{_rounded_rect(inset, inset, x1, h - inset, radii)}" fill="url(#g)"{stroke}/>')
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


def _layout_order(layout: str) -> list[str]:
    """The window buttons in screen order, e.g. ':minimize,maximize,close'."""
    return [b for side in layout.split(":") for b in side.split(",") if b in ("minimize", "maximize", "close")]


def _joined(order: list[str], fn: str) -> str:
    """first / middle / last / only: a function's place in a Linked group."""
    fn = "maximize" if fn == "unmaximize" else fn
    if fn not in order:
        return "only"
    if len(order) == 1:
        return "only"
    i = order.index(fn)
    return "first" if i == 0 else "last" if i == len(order) - 1 else "middle"


def metacity(style: str, t: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """(tokens, files): draw ops for every function x state, and the SVG files they use."""
    g = geometry(style, t)
    fc = faces(style, t)
    shape = _shape(t)
    corner = outer_corner(style, t["wb.button_layout"], t)
    glyphs = _glyphs(t, style)
    icons = glyph_set(style, t.get("wb.button_glyphs") or None) == "icons"
    files: dict[str, str] = {}
    tok: dict[str, str] = {}

    order = _layout_order(t["wb.button_layout"])

    def face_op(face: Face, corner_=(None, 0), fn: str = "") -> str:
        if face.shape == "none":
            return ""
        joined = _joined(order, fn) if style == "linked" else None
        name = _name("face", face.shape, face.top, face.bottom, face.border and _split_color(face.border)[0],
                     str(face.radius), face.bar, corner_[0], str(corner_[1]), str(face.size),
                     *(str(v) for v in shape), joined)
        files[name] = face_svg(face, g.fw, g.fh, corner_, shape, joined)
        return f'\t<image filename="{name}" {CENTER}/>\n'

    def glyph_op(fn: str, color: str | None) -> str:
        if color is None:
            return ""
        s = g.glyph or 16
        if fn in glyphs:
            c, _a = _split_color(color)
            name = _name(glyphs[fn], c, str(s))
            files[name] = glyph_svg(glyphs[fn], color, s)
            return (f'\t<image filename="{name}" x="(width-{s})/2" y="(height-{s})/2" '
                    f'width="{s}" height="{s}"/>\n')
        if icons:        # the icon theme's glyph, copied in the right colour
            svg = icon_theme_glyph(fn, color)
            if svg is None and fn in GLYPH_SETS["regular"]:
                svg = glyph_svg(GLYPH_SETS["regular"][fn], color, s)    # none there: ours
            if svg is not None:
                c, _a = _split_color(color)
                name = _name("icon", fn, c, str(s))
                files[name] = svg
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
            tok[f"wb.ops.{fn}_{op_state}"] = (face_op(face, c, fn) + glyph_op(fn, face.glyph)) or "\t"
            if fn == "close" and corner[0]:
                # maximized and tiled windows have square corners
                tok[f"wb.ops.{fn}_{op_state}_square"] = (face_op(face, (None, 0), fn) + glyph_op(fn, face.glyph)) or "\t"
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


def _inset_only(shadow: str) -> str:
    """The inset layers of a box-shadow list (outer ones go round a Linked group)."""
    parts, depth, cur = [], 0, ""
    for ch in shadow:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    inset = [x for x in parts if x.startswith("inset")]
    return ", ".join(inset) if inset else "none"


def _lean(pos: str, rtl_paint: bool = False) -> tuple[int, int]:
    """Which way a joined button's shadow piece reaches at its left and right
    joins, in blurs: +1 toward a right neighbour painted after it, -1 toward a
    left neighbour painted after it, 0 at the group's ends."""
    if rtl_paint:
        return {"first": (0, -1), "middle": (-1, -1), "last": (-1, 0), "only": (0, 0)}[pos]
    return {"first": (0, 1), "middle": (1, 1), "last": (1, 0), "only": (0, 0)}[pos]


def _group_shadow(shadow: str, pos: str, rtl_paint: bool = False,
                  lean: tuple[int, int] | None = None) -> str:
    """A Linked button's share of the group's outer layers (pos: first, middle,
    last, only), kept with its inner ones. The recess becomes strips: the dark
    one along the top of every button (and the left of the first), the light
    one along the bottom (and the right of the last). A drop shadow is shifted
    so the pieces meet under the group (see below)."""
    parts, depth, cur = [], 0, ""
    for ch in shadow:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    out = []

    def num(v: str) -> float:
        return float(v[:-2]) if v.endswith("px") else float(v)

    def px(v: float) -> str:
        return "0" if v == 0 else f"{v:g}px"
    for layer in parts:
        if not layer or layer == "none":
            continue
        if layer.startswith("inset") or pos == "only":
            out.append(layer)
            continue
        m = re.match(r"(\S+) (\S+) (\S+)(?: (\S+px|0))? (.+)$", layer)
        if not m:
            out.append(layer)
            continue
        x, y, blur = num(m.group(1)), num(m.group(2)), num(m.group(3))
        spread = num(m.group(4)) if m.group(4) else 0.0
        color = m.group(5)
        if blur == 0 and spread == 0 and x == y and x != 0:         # a recess side
            if x > 0:                                               # light: bottom, right end
                out.append(f"0 {px(x)} 0 {color}")
                if pos == "last":
                    out.append(f"{px(x)} 0 0 {color}")
            else:                                                   # dark: top, left end
                out.append(f"0 {px(y)} 0 {color}")
                if pos == "first":
                    out.append(f"{px(x)} 0 0 {color}")
        else:                                                       # a drop shadow
            # Buttons are painted left to right, so each piece is shifted right
            # by its blur: it never reaches back onto the button before it
            # (the next button's face covers what falls under it), and the
            # pieces of neighbours meet edge to edge, adding up to one shadow
            # under the whole group. The last stops at the group's right end
            # (shrunk by half the blur, moved to keep its bottom edge in place);
            # the first starts at the left end (growing it to reach past the
            # end put shadow above the group).
            # The piece spans [left + jl*blur, right + jr*blur]: at a join it
            # reaches into the neighbour painted later (which covers it) and
            # stops a blur short of one painted earlier (so its soft edge
            # ends at that button). Growing at a group end would push shadow
            # above the group, so an end next to a reaching join leans too.
            jl, jr = lean or _lean(pos, rtl_paint)
            if (jl, jr) == (0, 1):
                jl = 1
            elif (jl, jr) == (-1, 0):
                jr = -1
            b = blur
            dx, ds = (jl + jr) * b / 2, (jr - jl) * b / 2
            # keep the bottom edge in place (or the top, if the piece grows)
            dy = -ds if ds <= 0 else ds
            out.append(f"{px(x + dx)} {px(y + dy)} {px(blur)} {px(spread + ds)} {color}")
    return ", ".join(out) if out else "none"


def _linked_css(t: dict[str, str], g: Geometry, fc: dict, gtk4: bool, bases: list[str],
                pseudos: dict, classes: dict, h: int) -> list[str]:
    """Linked: corners only at the group's two ends, one shared border between
    neighbours (each button draws its left edge, the last its right one too),
    the hovered button's colour on the edge it shares, and the recess / drop
    shadow round the whole group on the box that holds the buttons."""
    out = []
    r = fc[("button", "rest")].radius
    every = [p for ps in pseudos.values() for p in ps]

    def rule(suffix: str, decl: str) -> str:
        sels = [f"{b}{cls}{p}{suffix}" for b in bases for cls in classes.values() for p in every]
        return ",\n".join(dict.fromkeys(sels)) + f" {{ {decl} }}"
    first = [":first-child"] if gtk4 else [":first-child"]
    out.append(rule("", "border-radius: 0;"))
    for f in first:
        out.append(rule(f, f"border-radius: {r}px 0 0 {r}px;"))
    if not gtk4:
        # GTK 3 puts a (hidden) separator before the first window button
        sels = [f"{b.split(' ')[0]} separator + button.titlebutton{cls}{p}"
                for b in bases for cls in classes.values() for p in every]
        out.append(",\n".join(dict.fromkeys(sels)) + f" {{ border-radius: {r}px 0 0 {r}px; }}")
    out.append(rule(":last-child", f"border-radius: 0 {r}px {r}px 0;"))
    out.append(rule(":first-child:last-child", f"border-radius: {r}px;"))
    out.append(rule(":not(:last-child)", "border-right-width: 0;"))
    # the shared edge takes the hovered / pressed button's border colour
    nxt = "button" if gtk4 else "button.titlebutton"
    for kind, cls in classes.items():
        for state, pseudo_list in (("hover", pseudos["hover"]), ("pressed", pseudos["pressed"])):
            face = fc[(kind, state)]
            if face.shape == "none" or not face.border:
                continue
            sels = [f"{b}{cls}{p} + {nxt}" + ("" if not gtk4 else ":not(.osd)") for b in bases for p in pseudo_list]
            out.append(",\n".join(sels) + f" {{ border-left-color: {face.border}; }}")
    # the group's outer layers (recess, drop shadow), split between the buttons
    # by position: a box round them only fits a header bar of exactly the
    # title bar's height (taller header bars left a gap under the buttons)
    pos_sel = {"first": [":first-child"], "last": [":last-child"], "only": [":first-child:last-child"]}
    for pos, suffixes in pos_sel.items():
        for kind, cls in classes.items():
            for state in STATES:
                face = fc[(kind, state)]
                if face.shape != "rect":
                    continue
                shadow = _group_shadow(face.shadow4 if gtk4 else face.shadow3, pos)
                sels = [f"{b}{cls}{p}{sfx}" for b in bases for p in pseudos[state] for sfx in suffixes]
                if pos == "first" and not gtk4:      # GTK 3's hidden separator comes first
                    sels += [f"{b.split(' ')[0]} separator + button.titlebutton{cls}{p}"
                             for b in bases for p in pseudos[state]]
                out.append(",\n".join(sels) + f" {{ box-shadow: {shadow}; }}")
    return out


MUFFIN = ".ssd headerbar.default-decoration"     # Cinnamon's window borders (Muffin 6)


def _muffin_css(style: str, t: dict[str, str], g: Geometry, fc: dict, glyphs: dict[str, str],
                files: dict[str, str], shape: tuple, pseudos: dict, classes: dict,
                side: str | None, cr: int) -> list[str]:
    """Window borders. Cinnamon's Muffin (Mint 22) draws them from this GTK 3 CSS,
    not from metacity-1: a header bar under window.ssd > decoration, one button
    node it restyles per function (no siblings, so no :first-child), and only
    that button's background and frame: never the image node inside. It lays the
    buttons out itself, with a fixed 6px between them plus their margins, and
    draws the icon theme's glyph in the button's colour on top (ours are a
    background layer, the icon hidden by a clear colour).

    So here: the title bar's height and side padding, every button's size and
    spacing, and for styles whose face is on the image node in apps, the face
    drawn on the button instead (as an SVG). tools/muffin-preview.py draws it."""
    out = [f"/* window borders (Muffin) */"]
    full = g.full_height
    h = int(t["wb.height_inner"]) if full else g.h
    border_px = 0 if (g.inner or style == "gargantuan") else 1
    order = _layout_order(t["wb.button_layout"])
    left_side = t["wb.button_layout"].startswith(("close", "minimize", "maximize")) and \
        len(t["wb.button_layout"].split(":")[0].split(",")) >= len(order) / 2
    # a 6px gap is built in: take it back with a margin on the side away from
    # the window's edge (on the edge side it would move the outer button)
    pull = g.gap + spacing(style, t) - GTK3_BUTTON_SPACING
    margin = f"0 {pull}px 0 0" if left_side else f"0 0 0 {pull}px"
    edge = 0 if full else g.edge
    out.append(f"{MUFFIN} {{\n  min-height: {t['wb.height_inner']}px;\n  padding: 0 {edge}px;\n  border-width: 0; }}")
    # the title's height counts only through its margins: pulled in, so the
    # title bar keeps your height with a large title font (the text stays centred)
    out.append(f"{MUFFIN} label.title {{ margin-top: -12px; margin-bottom: -12px; }}")
    btn = f"{MUFFIN} button.titlebutton"
    every = [f"{btn}{p}" for ps in pseudos.values() for p in ps]
    out.append(",\n".join(every) + f" {{\n  min-width: {g.w - 2 * border_px}px;\n  min-height: {h - 2 * border_px}px;\n"
               f"  padding: 0;\n  margin: {margin};"
               + ("\n  border-width: 1px;" if style == "linked" else "") + " }")
    out.append(f"{btn} image {{\n  min-width: 0;\n  min-height: 0;\n  margin: 0;\n  padding: 0;\n  border: none; }}")

    if style == "linked":
        # one face per function, by its place in the group (as on the metacity
        # borders): corners at the ends, one shared line between neighbours
        r = fc[("button", "rest")].radius
        painted = {"close": 0, "maximize": 1, "minimize": 2}     # Muffin's paint order

        def lean(fn: str) -> tuple[int, int]:
            if fn not in order:
                return (0, 0)
            i = order.index(fn)
            jl = 0 if i == 0 else (1 if painted[order[i - 1]] < painted[fn] else -1)
            jr = 0 if i == len(order) - 1 else (1 if painted[order[i + 1]] > painted[fn] else -1)
            return jl, jr
        for fn in ("minimize", "maximize", "close"):
            pos = _joined(order, fn)
            radius = {"first": f"{r}px 0 0 {r}px", "last": f"0 {r}px {r}px 0",
                      "middle": "0", "only": f"{r}px"}[pos]
            kind = fn
            for state in STATES:
                face = fc[(kind, state)]
                sels = ",\n".join(f"{btn}.{fn}{p}" for p in pseudos[state])
                decl = [f"border-radius: {radius};"]
                decl.append(f"border-right-width: {0 if pos in ('first', 'middle') else 1}px;")
                if face.shape == "rect":
                    decl.append(f"box-shadow: {_group_shadow(face.shadow3, pos, lean=lean(fn))};")
                out.append(sels + " { " + " ".join(decl) + " }")
    if not g.inner:
        if full and glyphs:
            # Gargantuan: the app rules place the glyph for a header bar's height
            # (at least 46px); Muffin's buttons are the title bar's, so re-centre
            gs = g.glyph or 16
            pos = [f"{(g.w - 2 * border_px - gs) // 2}px {(h - 2 * border_px - gs) // 2}px"]
            if any(f.bar for f in fc.values()):
                pos.append(f"{(g.w - 10) // 2}px {h // 2 + 6}px")
            if any(f.shape != "none" and f.top != f.bottom for f in fc.values()):
                pos.append("0 0")
            sels = [f"{btn}{cls}{p}" for cls in classes.values() for ps in pseudos.values() for p in ps]
            sels += [f".maximized {btn}.maximize{p}" for ps in pseudos.values() for p in ps]
            out.append(",\n".join(sels) + f" {{ background-position: {', '.join(pos)}; }}")
        return out            # the face is on the button already (the app rules apply)

    # the face on the button, as an SVG centred in it, under the glyph
    gs = g.glyph or 16
    def layers(face: Face, glyph_name: str | None) -> list[str]:
        imgs, sizes, pos = [], [], []
        if glyph_name and face.glyph:
            c, _a = _split_color(face.glyph)
            name = _name(glyph_name, c, str(gs))
            files[name] = glyph_svg(glyph_name, face.glyph, gs)
            imgs.append(f'url("assets/{name}")')
            sizes.append(f"{gs}px {gs}px")
            pos.append(f"{(g.w - gs) // 2}px {(h - gs) // 2}px")
        if face.shape != "none":
            svg, pad = shadowed_face_svg(face, g.fw, g.fh, face.shadow3, shape)
            name = _name("mface", face.shape, face.top, face.bottom,
                         face.border and _split_color(face.border)[0], str(face.radius), str(g.fw),
                         str(g.fh), *(str(v) for v in shape),
                         hashlib.sha1(face.shadow3.encode()).hexdigest()[:8])
            files[name] = svg
            imgs.append(f'url("assets/{name}")')
            sizes.append(f"{g.fw + 2 * pad}px {g.fh + 2 * pad}px")
            pos.append(f"{(g.w - g.fw) // 2 - pad}px {(h - g.fh) // 2 - pad}px")
        if not imgs:
            return ["background-image: none;"]
        return [f"background-image: {', '.join(imgs)};", f"background-size: {', '.join(sizes)};",
                f"background-position: {', '.join(pos)};", "background-repeat: no-repeat;"]

    for kind, cls in classes.items():
        fn = {"close": "close", "minimize": "minimize", "maximize": "maximize"}.get(kind)
        for state in STATES:
            face = fc[(kind, state)]
            sels = ",\n".join(f"{btn}{cls}{p}" for p in pseudos[state])
            decl = ["border: none;", "border-radius: 0;", "box-shadow: none;", "background-color: transparent;"]
            decl += layers(face, glyphs.get(fn) if glyphs and fn else None)
            decl.append(f"color: {'transparent' if glyphs else (face.glyph or 'transparent')};")
            out.append(sels + " {\n  " + "\n  ".join(decl) + " }")
            if fn == "maximize" and glyphs and glyphs.get("unmaximize", "maximize") != glyphs["maximize"]:
                sels = ",\n".join(f".maximized {btn}.maximize{p}" for p in pseudos[state])
                out.append(sels + " {\n  " + "\n  ".join(layers(face, glyphs["unmaximize"])) + " }")
    return out


def css(style: str, t: dict[str, str], gtk4: bool = False) -> tuple[str, dict[str, str]]:
    """(css, asset files) for title buttons in GTK 3 header bars or GTK 4 window controls."""
    g = geometry(style, t)
    fc = faces(style, t)
    shape = _shape(t)
    glyphs = _glyphs(t, style)
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
        out.append(f"windowcontrols {{ border-spacing: {spacing(style, t)}px; }}")
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
        # filling the title bar: but GTK centres window buttons in a header bar,
        # which its other buttons hold at 46px at least (a strip showed above)
        # (its buttons grow with Size: 34px plus Mint-Y's 6px margins at Size 30)
        h = max(int(t["wb.height_inner"]), HEADERBAR_CONTENT + int(t["ctl"]) - 30)
        margin = "0"
    else:
        h, margin = g.h, f"0 {g.gap // 2}px"
    # Gargantuan faces have no border: none at all, so they reach the window's
    # edge (a transparent 1px border left a strip of title bar round the face,
    # since backgrounds are drawn inside the border)
    borderless = g.full_height and style == "gargantuan"
    border_px = 0 if (g.inner or borderless) else 1
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
    else:
        # The face is on the button: the icon node draws nothing but the glyph.
        # Reset everything a face-on-the-icon style sets there, so none of it
        # shows through from another title button style loaded underneath (the
        # settings app previews over the applied theme).
        out.append(f"{sel('', child)} {{\n  min-width: 0;\n  min-height: 0;\n  margin: 0;\n  padding: 0;\n"
                   f"  border: none;\n  border-radius: 0;\n  box-shadow: none;\n"
                   f"  background-color: transparent;\n  background-image: none;\n"
                   f"  color: {'transparent' if glyphs else 'inherit'};\n"
                   # no fade of its own: the glyph follows the button's colour as
                   # it fades (with its own transition it lagged behind the face)
                   f"  transition: none; }}")

    if not glyphs and g.glyph and g.glyph != 16:
        # the icon theme's glyphs, at this style's glyph size
        rule = f"-gtk-icon-size: {g.glyph}px;" if gtk4 else f"-gtk-icon-transform: scale({g.glyph / 16:g});"
        out.append(f"{sel('', child)} {{ {rule} }}")

    # glyph offsets in whole pixels (a glyph on a half pixel is blurry)
    if g.inner:
        box_w, box_h = g.fw - 2, g.fh - 2
    else:
        box_w, box_h = g.w - 2 * border_px, h - 2 * border_px
    # faces too small to hold the 16px icon inside a 1px border draw their
    # outline as an inset ring instead (dots)
    ring = g.inner and min(g.fw, g.fh) - 2 < 16
    if ring:
        box_w, box_h = g.fw, g.fh
    gs = g.glyph or 16
    glyph_pos = f"{(box_w - gs) // 2}px {(box_h - gs) // 2}px"

    # Every state has the same layer slots (glyph, claude bar, gradient face),
    # each with the same size and position; a slot with nothing to show holds a
    # clear image. Otherwise a layer appearing on hover is animated from the
    # default size and position: the dots' glyphs slid in from the top left.
    glyph_slot = bool(glyphs)
    grad_slot = any(f.shape != "none" and f.top != f.bottom for f in fc.values())
    clear = "image(transparent)"

    def bg_layers(face: Face, glyph_name: str | None) -> tuple[list[str], list[str], list[str]]:
        layers, sizes, positions = [], [], []
        if glyph_slot:
            if glyph_name and face.glyph:
                c, _a = _split_color(face.glyph)
                name = _name(glyph_name, c, str(gs))
                files[name] = glyph_svg(glyph_name, face.glyph, gs)
                layers.append(f'url("{assets}{name}")')
            else:
                layers.append(clear)
            sizes.append(f"{gs}px {gs}px")
            positions.append(glyph_pos)
        if has_bar:
            bar = face.bar or _clear(t["accent"])
            layers.append(f"linear-gradient(to right, {bar}, {bar})")
            sizes.append("10px 2px")
            positions.append(f"{(box_w - 10) // 2}px {box_h // 2 + 6}px")    # just under the glyph
        if grad_slot:
            if face.shape != "none" and face.top != face.bottom:
                layers.append(pal.gradient_css(face.top, face.bottom, *shape))   # split / glass as the style says
            else:
                layers.append(clear)
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
            if style == "linked":
                shadow = _group_shadow(shadow, "middle")
            decl = [f"border-radius: {radius};", f"border: 1px solid {border};", f"box-shadow: {shadow};",
                    f"background-color: {bg};"] + bg_decl(*layers)
            if style == "linked":
                decl = decl[1:]                    # corners: see the position rules below
            if borderless:
                decl[1] = "border: none;"
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
            # the face fades, the glyph colour switches at once: a fading text
            # colour lagged well behind the face (a dark x on the coral close)
            decl.append("transition-property: " + ("background-color, border-color;" if gtk4
                        else "background-color, background-image, border-color;"))
            out.append(selectors + " {\n  " + "\n  ".join(decl) + " }")
    if style == "linked":
        out += _linked_css(t, g, fc, gtk4, bases, pseudos, classes, h)
    if not gtk4:
        # GTK 3's header bar adds 6px between window buttons (a box property,
        # not CSS): the next button's margin turns that into Button spacing
        out.append(",\n".join(f"{b} + button.titlebutton" for b in bases)
                   + f" {{ margin-left: {g.gap // 2 + spacing(style, t) - GTK3_BUTTON_SPACING}px; }}")
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
    if not gtk4:
        out += _muffin_css(style, t, g, fc, glyphs, files, shape, pseudos, classes, side, cr)
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
