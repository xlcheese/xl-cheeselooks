"""Notebook tab CSS, generated from the style's tab settings.

Each tab shape needs different rules, and templates have no conditionals,
so the tab section of the GTK layer is written here.

    tab_kind       boxed  tabs joined to the page; unselected ones drawn in the
                          toolbar color (xl-Cheeselooks)
                   open   like boxed, but unselected tabs have no box until
                          hovered (Mint-Y)
                   pills  rounded tabs floating in a trough; the selected one
                          is a raised button
    active_marker  none   nothing extra on the selected tab
                   line   a slim accent line on the outer edge
                   glow   the line plus an accent gradient fading inward
                          (Clearlooks)

Tabs take their look from the buttons: unselected tabs use the toolbar
button's hover color and hover border, and the button's inner layers
(highlight, sides, shade). Boxed and open tabs never get a drop shadow,
since they are joined to the page below.
"""

from __future__ import annotations

from . import palette as pal

POSITIONS = ("top", "bottom", "left", "right")
# marker offset on the outer edge, as "x y"
_EDGE = {"top": ("0", "{n}px"), "bottom": ("0", "-{n}px"), "left": ("{n}px", "0"), "right": ("-{n}px", "0")}
# corner radii: rounded on the outer side only
_RADII = {"top": "{r}px {r}px 0 0", "bottom": "0 0 {r}px {r}px", "left": "{r}px 0 0 {r}px", "right": "0 {r}px {r}px 0"}
MARKER_ALIASES = {"accent_top": "line", "accent_bottom": "line"}


def _marker(kind: str, pos: str, accent: str) -> str:
    if kind == "none":
        return ""
    width = 2 if kind == "line" else 1          # glow: a 1px edge line, the fade does the rest
    x, y = (v.format(n=width) for v in _EDGE[pos])
    line = f"inset {x} {y} 0 {accent}"
    if kind == "line":
        return line
    # glow: the line, plus a soft accent fade kept on the same edge
    gx, gy = (v.format(n=width + 8) for v in _EDGE[pos])
    return f"{line}, inset {gx} {gy} 8px -8px {pal.rgba(accent, 0.35)}"


def _join(*shadows: str) -> str:
    parts = [s for s in shadows if s and s != "none"]
    return ", ".join(parts) if parts else "none"


def css(t: dict[str, str]) -> str:
    kind = t.get("w.tab.tab_kind", "boxed")
    marker = MARKER_ALIASES.get(t.get("w.tab.active_marker", "none"), t.get("w.tab.active_marker", "none"))
    r = t["r"]
    out = [f"/* tabs: {kind}, selected marker: {marker} */"]

    def sel(pos: str, state: str = "") -> str:
        return f"notebook > header.{pos} > tabs > tab{state}"

    def all_pos(state: str = "") -> str:
        return ",\n".join([f"notebook > header > tabs > tab{state}"] + [sel(p, state) for p in POSITIONS])

    # unselected tab at rest
    if kind == "boxed":
        rest = (f"  color: {t['text_dim']};\n  border-color: {t['w.button.border']};\n"
                f"  background-color: {t['header']};\n  background-image: none;\n"
                f"  box-shadow: {t['w.button.inset_shadow']};")
    else:  # open and pills: nothing drawn until hover
        rest = (f"  color: {t['text_dim']};\n  border-color: transparent;\n"
                f"  background-color: transparent;\n  background-image: none;\n  box-shadow: none;")
    hover = (f"  color: {t['w.tab.hover_fg']};\n  border-color: {t['w.tab.hover_border']};\n"
             f"  background-color: {t['w.tab.hover_color']};\n"
             f"  background-image: linear-gradient(to bottom, {t['w.tab.hover_top']}, {t['w.tab.hover_bottom']});\n"
             f"  box-shadow: {t['w.tab.hover_inset_shadow']};")

    if kind == "pills":
        # the whole tab strip is the trough, edge to edge, in the toolbar/menubar color
        out.append(f"notebook > header, {', '.join(f'notebook > header.{p}' for p in POSITIONS)} {{\n"
                   f"  padding: 3px;\n  background-color: {t['header']};\n  background-image: none;\n"
                   f"  box-shadow: none; }}")
        out.append("notebook > header > tabs {\n  margin: 0;\n  padding: 0;\n"
                   "  border-radius: 0;\n  background-color: transparent; }")
        out.append(f"{all_pos()} {{\n  margin: 0 1px;\n  border: 1px solid transparent;\n  border-radius: {r}px; }}")
    else:
        for pos in POSITIONS:
            radii = _RADII[pos].format(r=r)
            out.append(f"{sel(pos)}{', ' + 'notebook > header > tabs > tab' if pos == 'top' else ''} {{\n"
                       f"  border-radius: {radii}; }}")

    out.append(f"{all_pos(':not(:checked)')} {{\n{rest} }}")
    if kind == "boxed":
        # unselected boxed tabs keep the edge that faces the page; only the
        # selected tab opens into it
        inner = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}
        for pos in POSITIONS:
            side = inner[pos]
            out.append(f"{sel(pos, ':not(:checked)')}"
                       f"{',' + chr(10) + 'notebook > header > tabs > tab:not(:checked)' if pos == 'top' else ''} {{\n"
                       f"  border-{side}-style: solid;\n  border-{side}-width: 1px;\n"
                       f"  border-{side}-color: {t['w.button.border']}; }}")
    out.append(f"{all_pos(':hover:not(:checked)')} {{\n{hover} }}")

    # selected tab
    accent = t["accent"]
    for pos in POSITIONS:
        m = _marker(marker, pos, accent)
        if kind == "pills":
            body = (f"  color: {t['text']};\n  border-color: {t['w.button.border']};\n"
                    f"  background-color: {t['button']};\n"
                    f"  background-image: linear-gradient(to bottom, {t['button_top']}, {t['button_bottom']});\n"
                    f"  box-shadow: {_join(t['w.button.shadow'], m)};")
        else:
            body = (f"  color: {t['text']};\n  border-color: {t['w.button.border']};\n"
                    f"  background-color: {t['base']};\n  background-image: none;\n"
                    f"  box-shadow: {_join(m)};")
        selectors = sel(pos, ":checked") + (",\nnotebook > header > tabs > tab:checked" if pos == "top" else "")
        out.append(f"{selectors} {{\n{body} }}")
    return "\n".join(out) + "\n"
