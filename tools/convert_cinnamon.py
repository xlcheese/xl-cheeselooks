#!/usr/bin/env python3
"""One-time converter: Linux Mint's Mint-Y cinnamon.css -> template.

Source: linuxmint/mint-themes, src/Mint-Y/cinnamon/cinnamon.css (light,
green accent). Produces templates/cinnamon/base.css.tmpl. Kept for
transparency; like the GTK base, the template may be edited by hand after
the first run, so do not re-run it over a template that has hand edits.

All Cinnamon colors use the Panel & Menu palette (the "menu." tokens),
which follows Global unless separate panel colors are switched on.

Rules:
- greys (Mint-Y's are slightly blue) become blends around the shell menu
  color: darker ones toward the text color, lighter ones toward the
  content color, keeping how far along they were
- black with opacity becomes the text color with that opacity, except in
  shadows, which stay black
- white text on colored backgrounds becomes accent_fg
- Mint's green (#35a854, #298141) becomes the accent / pressed accent
- red, orange and blue stay fixed (warnings, errors, drag-and-drop hints)
- radii of 2-4px become {{menu.r}}px, 5-8px become {{menu.r2}}px
- asset paths: light-assets/ (colored) are replaced by generated images in
  assets/; common-assets/ are copied unchanged
"""

from __future__ import annotations

import colorsys
import re
import sys
from pathlib import Path

REF_MENU = 235    # Mint-Y Cinnamon menu background #ebebed
REF_TEXT = 48     # #303030
GREENS = {(53, 168, 84): "menu.accent", (41, 129, 65): "menu.accent_press"}
SHADOW_PROPS = ("box-shadow", "text-shadow", "-gtk-icon-shadow")
ON_COLOR_HINTS = ("selected", ":checked", "highlight", "-active", ":focus", "badge", "attention", "progress",
                  "suggested", "destructive", "today", "osd")
COLOR_RE = re.compile(
    r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)"
    r"|\b(?:white|black)\b")
stats: dict[str, int] = {}


def bump(k: str) -> None:
    stats[k] = stats.get(k, 0) + 1


def parse(lit: str) -> tuple[int, int, int, float]:
    lit = lit.strip().lower()
    if lit == "white":
        return 255, 255, 255, 1.0
    if lit == "black":
        return 0, 0, 0, 1.0
    if lit.startswith("#"):
        h = lit[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0
    nums = [x.strip() for x in lit[lit.index("(") + 1:-1].split(",")]
    return int(nums[0]), int(nums[1]), int(nums[2]), float(nums[3]) if len(nums) == 4 else 1.0


def fmt(t: float) -> str:
    return f"{round(t, 3):g}"


def wrap(expr: str, a: float) -> str:
    simplify = {"mix(menu.menu_bg, menu.text, 1)": "menu.text", "mix(menu.menu_bg, menu.text, 0)": "menu.menu_bg",
                "mix(menu.menu_bg, menu.base, 1)": "menu.base", "mix(menu.menu_bg, menu.base, 0)": "menu.menu_bg"}
    expr = simplify.get(expr, expr)
    return "{{" + expr + "}}" if a >= 0.999 else "{{alpha(" + expr + f", {fmt(a)})" + "}}"


def convert(lit: str, prop: str, selector: str) -> str:
    sel = selector.lower()
    r, g, b, a = parse(lit)
    if a <= 0.001:
        bump("transparent")
        return "transparent"
    if (r, g, b) in GREENS:
        bump("green -> accent")
        return wrap(GREENS[(r, g, b)], a)
    shadow = prop in SHADOW_PROPS
    _, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    # Mint-Y's greys lean blue; pale, low-saturation blue-greys count as greys too
    grey = max(r, g, b) - min(r, g, b) <= 12 or (sat < 0.4 and light > 0.75)
    if grey:
        v = round((r + g + b) / 3)
        if shadow and v <= 60:
            bump("shadow black kept")
            return lit
        if shadow and v >= 240:
            bump("shadow white -> base")
            return wrap("menu.base", a)
        if v <= 30 and a < 0.999:
            bump("black alpha -> text")
            return wrap("menu.text", a)
        if v >= 254:
            if prop in ("color", "-st-icon-color") or prop.endswith("-color") and "background" not in prop \
                    and "border" not in prop and any(h in sel for h in ON_COLOR_HINTS):
                bump("white -> accent_fg")
                return wrap("menu.accent_fg", a)
            bump("white -> base")
            return wrap("menu.base", a)
        if v >= REF_MENU:
            bump("light grey -> mix(menu_bg, base)")
            return wrap(f"mix(menu.menu_bg, menu.base, {fmt((v - REF_MENU) / (255 - REF_MENU))})", a)
        if v >= REF_TEXT:
            bump("grey -> mix(menu_bg, text)")
            return wrap(f"mix(menu.menu_bg, menu.text, {fmt((REF_MENU - v) / (REF_MENU - REF_TEXT))})", a)
        bump("dark grey -> darker(text)")
        return wrap(f"darker(menu.text, {fmt((REF_TEXT - v) / REF_TEXT)})", a)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    if 0.25 <= h <= 0.45 and s > 0.3:   # other greens: shades of the accent
        bump("other green -> accent shade")
        return wrap("menu.accent" if l >= 0.4 else "menu.accent_press", a)
    bump("semantic kept")
    return lit


def radius_value(value: str) -> str:
    def sub(m: re.Match) -> str:
        n = float(m.group(1))
        if 2 <= n <= 4:
            bump("radius -> r")
            return "{{menu.r}}px"
        if 5 <= n <= 8:
            bump("radius -> r2")
            return "{{menu.r2}}px"
        return m.group(0)
    return re.sub(r"(\d+(?:\.\d+)?)px", sub, value)


DECL_RE = re.compile(r"([-\w]+)(\s*:\s*)([^;{}]*)")


def convert_body(body: str, selector: str) -> str:
    def decl(m: re.Match) -> str:
        prop, sep, value = m.group(1).lower(), m.group(2), m.group(3)
        if prop.endswith("radius") and "url(" not in value:
            value = radius_value(value)
        if "url(" in value:
            value = value.replace('url("light-assets/checkbox/', 'url("assets/').replace(
                'url("light-assets/switch/', 'url("assets/').replace('url("light-assets/', 'url("assets/')
            bump("asset path")
        value = COLOR_RE.sub(lambda c: convert(c.group(0), prop, selector), value)
        return m.group(1) + sep + value
    return DECL_RE.sub(decl, body)


def convert_css(css: str) -> str:
    out, pos, stack, sel_start, i = [], 0, [], 0, 0
    while i < len(css):
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end < 0 else end + 2
            continue
        ch = css[i]
        if ch == "{":
            stack.append(css[sel_start:i].strip())
            out.append(css[pos:i + 1])
            pos = sel_start = i + 1
        elif ch == "}":
            selector = stack.pop() if stack else ""
            out.append(convert_body(css[pos:i], selector))
            out.append("}")
            pos = sel_start = i + 1
        i += 1
    out.append(css[pos:])
    return "".join(out)


def main() -> int:
    src, dest = Path(sys.argv[1]), Path(sys.argv[2])
    header = ("/* xl-Cheeselooks: Cinnamon base layer.\n"
              " * Derived from Linux Mint's Mint-Y Cinnamon theme (GPL-3.0),\n"
              " * converted by tools/convert_cinnamon.py. Colors and radii are template tokens\n"
              " * from the Panel & Menu palette. The xl layer (xl.css.part) follows below. */\n\n")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(header + convert_css(src.read_text(encoding="utf-8")), encoding="utf-8")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"{v:5}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
