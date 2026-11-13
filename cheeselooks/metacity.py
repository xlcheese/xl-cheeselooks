"""Window borders: the parts of metacity-1/metacity-theme-3.xml that need logic.

Muffin draws traditional title bars from metacity-theme-3.xml. Most of the
file is a template (templates/metacity-1/metacity-theme-3.xml.tmpl); this
module adds what a template can't express, since its drawing language has no
conditionals:

    geometry   corner radius and side widths (button geometry and drawing
               come from cheeselooks/titlebuttons.py)
    borders    0-6 px borders: filled bands on each side plus one arc per
               pixel of width around the rounded top corners (nothing at all
               at width 0)

The title bar, title text and buttons use the same tokens as GTK headerbars,
so both kinds of window match.
"""

from __future__ import annotations

from . import palette as pal


def _band(x: str, y: str, w: str, h: str, color: str) -> str:
    return f'<rectangle color="{color}" x="{x}" y="{y}" width="{w}" height="{h}" filled="true"/>'


def _arcs(radius: int, width: int, color: str) -> list[str]:
    """Concentric 1px arcs around both rounded top corners, one per pixel of border."""
    out = []
    for i in range(min(width, radius)):
        d = 2 * (radius - i)
        out.append(f'<arc color="{color}" x="{i}" y="{i}" width="{d}" height="{d}" '
                   f'start_angle="270" extent_angle="90"/>')
        out.append(f'<arc color="{color}" x="width-1-{i}-{d}" y="{i}" width="{d}" height="{d}" '
                   f'start_angle="0" extent_angle="90"/>')
    return out


def border_ops(color: str, width: int, radius: int, sides: str = "tlrb") -> str:
    """Draw ops for a border `width` px wide on the given sides (t, l, r, b).
    The top corners are rounded by `radius` when both top and side are drawn."""
    if width <= 0:
        return "<!-- no border -->"
    w = str(width)
    rr = radius if ("t" in sides and radius > 0) else 0
    ops = []
    if "t" in sides:
        ops.append(_band(str(rr), "0", f"width-{2 * rr}", w, color))
    if "l" in sides:
        ops.append(_band("0", str(rr), w, f"height-{rr}", color))
    if "r" in sides:
        ops.append(_band(f"width-{w}", str(rr), w, f"height-{rr}", color))
    if "b" in sides:
        ops.append(_band("0", f"height-{w}", "width", w, color))
    if rr:
        ops += _arcs(rr, width, color)
    return "\n\t".join(ops)


def tokens(t: dict[str, str]) -> dict[str, str]:
    """Window-border tokens for the metacity template (needs the wb.*, r and r2 tokens)."""
    bw, radius = int(t["wb.border_width"]), int(t["r2"])
    unfocused_border = pal.mix(t["wb.border"], t["wb.unfocused"], 0.3)
    out = {
        "wb.radius": str(radius),
        "wb.side": str(bw),
        "wb.border_unfocused": unfocused_border,
    }
    for name, color in (("focused", t["wb.border"]), ("unfocused", unfocused_border)):
        out[f"wb.ops.border_{name}"] = border_ops(color, bw, radius)
        out[f"wb.ops.border_left_{name}"] = border_ops(color, bw, 0, "l")      # tiled right
        out[f"wb.ops.border_right_{name}"] = border_ops(color, bw, 0, "r")     # tiled left
    return out
