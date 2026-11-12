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


# "claude" tabs (designed by Claude): quiet until needed. Unselected tabs are
# just text, with a soft highlight on hover; the selected tab is a card in the
# page colour, joined to the page, with a short accent bar centred on its outer
# edge instead of a full-width line. Softer corners (the window radius).
_BAR = {"top": "ellipse 16px 3px at 50% 0", "bottom": "ellipse 16px 3px at 50% 100%",
        "left": "ellipse 3px 16px at 0 50%", "right": "ellipse 3px 16px at 100% 50%"}


def claude_bar(pos: str, accent: str) -> str:
    """The claude tab's short accent bar on the outer edge (a clipped ellipse)."""
    return f"radial-gradient({_BAR[pos]}, {accent} 60%, transparent 100%)"


# the edge of a tab that faces the page, per tab position
PAGE_SIDE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}


def split_shadows(value: str) -> list[str]:
    """Split a box-shadow list on its top-level commas (not those inside rgba())."""
    parts, depth, cur = [], 0, ""
    for ch in value:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _edge_of(shadow: str) -> str | None:
    """Which edge an inset shadow layer lies along (from its offsets), if any."""
    bits = shadow.split()
    if not bits or bits[0] != "inset":
        return None
    try:
        x, y = (float(b.rstrip("px") or 0) for b in bits[1:3])
    except ValueError:
        return None
    if y > 0 and x == 0:
        return "top"
    if y < 0 and x == 0:
        return "bottom"
    if x > 0 and y == 0:
        return "left"
    if x < 0 and y == 0:
        return "right"
    return None


def without_side(value: str, side: str) -> str:
    """The shadow list minus the inset layers along `side` (the page-facing edge)."""
    if value == "none":
        return value
    kept = [p for p in split_shadows(value) if _edge_of(p) != side]
    return ", ".join(kept) if kept else "none"


def css(t: dict[str, str], gtk4: bool = False) -> str:
    """Notebook tab CSS. gtk4=True uses the GTK 4 shadows (blur doubled)."""
    def k(name: str) -> str:
        # w.button.inset_shadow -> w.button.g4_inset_shadow for GTK 4
        if not gtk4:
            return name
        head, _, last = name.rpartition(".")
        state = next((p for p in ("hover_", "pressed_", "focus_") if last.startswith(p)), "")
        return f"{head}.{state}g4_{last[len(state):]}"

    kind = t.get("w.tab.tab_kind", "boxed")
    marker = t.get("w.tab.active_marker", "none")
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
                f"  box-shadow: {t[k('w.button.inset_shadow')]};")
    else:  # open and pills: nothing drawn until hover
        rest = (f"  color: {t['text_dim']};\n  border-color: transparent;\n"
                f"  background-color: transparent;\n  background-image: none;\n  box-shadow: none;")
    hover_edge = "transparent" if kind == "claude" else t["w.tab.hover_border"]
    hover = (f"  color: {t['w.tab.hover_fg']};\n  border-color: {hover_edge};\n"
             f"  background-color: {t['w.tab.hover_color']};\n"
             f"  background-image: {t['w.tab.hover_grad']};\n"
             f"  box-shadow: {t[k('w.tab.hover_inset_shadow')]};")

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
            radii = _RADII[pos].format(r=t["r2"] if kind == "claude" else r)
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
    if kind != "pills":
        # boxed and open tabs are joined to the page: no highlight or shade on
        # the edge that faces it (e.g. no bottom shade on top tabs)
        rest_sh = t[k("w.button.inset_shadow")] if kind == "boxed" else "none"
        hover_sh = t[k("w.tab.hover_inset_shadow")]
        for pos in POSITIONS:
            side = PAGE_SIDE[pos]
            also = ",\nnotebook > header > tabs > tab" if pos == "top" else ""
            out.append(f"{sel(pos, ':not(:checked)')}{also + ':not(:checked)' if also else ''} {{\n"
                       f"  box-shadow: {without_side(rest_sh, side)}; }}")
            out.append(f"{sel(pos, ':hover:not(:checked)')}{also + ':hover:not(:checked)' if also else ''} {{\n"
                       f"  box-shadow: {without_side(hover_sh, side)}; }}")

    # selected tab
    accent = t["accent"]
    for pos in POSITIONS:
        m = _marker(marker, pos, accent)
        if kind == "pills":
            body = (f"  color: {t['text']};\n  border-color: {t['w.button.border']};\n"
                    f"  background-color: {t['button']};\n"
                    f"  background-image: {t['button_grad']};\n"
                    f"  box-shadow: {_join(t[k('w.button.shadow')], m)};")
        else:
            bar = claude_bar(pos, accent) if kind == "claude" else "none"
            body = (f"  color: {t['text']};\n  border-color: {t['w.button.border']};\n"
                    f"  background-color: {t['base']};\n  background-image: {bar};\n"
                    f"  box-shadow: {_join(m)};")
        selectors = sel(pos, ":checked") + (",\nnotebook > header > tabs > tab:checked" if pos == "top" else "")
        out.append(f"{selectors} {{\n{body} }}")
    return "\n".join(out) + "\n"


def adw_css(t: dict[str, str]) -> str:
    """libadwaita's tab bar (AdwTabBar: tabbar > tabbox > tabboxchild > tab), in the
    style's tab look. Boxed and open tabs sit on the page like notebook tabs;
    pills float in the strip. GTK 4 shadows (blur doubled, solid colours)."""
    kind = t.get("w.tab.tab_kind", "boxed")
    marker = _marker(t.get("w.tab.active_marker", "none"), "top", t["accent"])
    r = t["r"]
    border = t["w.button.border"]
    hover = (f"  color: {t['w.tab.hover_fg']};\n  background-color: {t['w.tab.hover_color']};\n"
             f"  background-image: {t['w.tab.hover_grad']};\n"
             f"  box-shadow: inset 0 0 0 1px {t['w.tab.hover_border']}; }}")
    out = [f"/* libadwaita tab bar: {kind}, selected marker: "
           f"{t.get('w.tab.active_marker', 'none')} (cheeselooks/tabs.py) */",
           f"tabbar .box {{\n  background-color: {t['header']};\n  background-image: none;\n"
           f"  box-shadow: inset 0 -1px {border}; }}",
           "tabbar tab, tabbar tab:selected, tabbar tab:hover, tabbar tab:active {\n"
           "  background-image: none;\n  box-shadow: none;\n  transition-property: color, background-color; }"]
    if kind == "pills":
        out += [f"tabbar tabbox > tabboxchild {{ border-radius: {r}px; }}",
                f"tabbar tab {{ border-radius: {r}px; color: {t['text_dim']}; background-color: transparent; }}",
                f"tabbar tab:hover:not(:selected) {{\n{hover}",
                f"tabbar tab:selected, tabbar tab:selected:hover {{\n  color: {t['text']};\n"
                f"  background-color: {t['button']};\n"
                f"  background-image: {t['button_grad']};\n"
                f"  box-shadow: {_join(f'inset 0 0 0 1px {border}', t['w.button.g4_inset_shadow'], marker)}; }}"]
    else:
        # sit on the page: no gap below the tabs, square bottom corners
        rest_bg = t["header"] if kind == "boxed" else "transparent"
        bar = claude_bar("top", t["accent"]) if kind == "claude" else "none"
        rr = t["r2"] if kind == "claude" else r
        rest_edge = f"inset 0 0 0 1px {border}" if kind == "boxed" else "none"
        out += ["tabbar .box { padding-bottom: 0; box-shadow: none; }   /* tabs sit right on the page */",
                "tabbar tabbox { padding-bottom: 0; }",
                f"tabbar tabbox > tabboxchild {{ border-radius: {rr}px {rr}px 0 0; }}",
                f"tabbar tab {{\n  border-radius: {rr}px {rr}px 0 0;\n  color: {t['text_dim']};\n"
                f"  background-color: {rest_bg};\n  box-shadow: {rest_edge}; }}",
                f"tabbar tab:hover:not(:selected) {{\n{hover}",
                f"tabbar tab:selected, tabbar tab:selected:hover {{\n  color: {t['text']};\n"
                f"  background-color: {t['base']};\n  background-image: {bar};\n"
                f"  box-shadow: {_join(f'inset 1px 0 {border}', f'inset -1px 0 {border}', f'inset 0 1px {border}', marker)}; }}"]
    return "\n".join(out) + "\n"
