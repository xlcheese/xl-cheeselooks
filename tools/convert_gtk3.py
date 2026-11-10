#!/usr/bin/env python3
"""One-time converter: turn the reference Mint-Y-based gtk.css into a template.

This is how templates/gtk-3.0/base.css.tmpl was first produced from
reference/xl_cheese-Mint-Y-Variable/gtk-3.0/gtk.css. It is kept for
transparency. DO NOT re-run it over base.css.tmpl: since November 2026 the
template has hand edits (for example the stack switcher and path bar
border colors), which a re-run would lose. Use `git log -p` on the
template to see them.

Rules (docs/design-spec.md, "Color formats in templates"):
- greys become blends of bg -> text (darker) or bg -> base (lighter),
  keeping how far along they were in the original light theme
- black with opacity becomes the text color with that opacity, except in
  shadows, which stay black
- white text on colored backgrounds becomes accent_fg; white surfaces
  become base; white in shadows becomes base with that opacity
- coral becomes accent, #F18065 becomes select; leftover Mint-Y-Brown
  tints become shades of select
- red, green, orange and blue stay fixed (error, success, warning, links)
- media OSD rules keep their fixed dark colors
- border radii of 2-4px become {{r}}px, 5-8px become {{r2}}px
- image-based checks, radios, switches and pane handles are removed; xl.css redraws them
"""

from __future__ import annotations

import colorsys
import re
import sys
from pathlib import Path

REF_BG = 245      # Mint-Y light window background (#F5F5F5)
REF_TEXT = 48     # Mint-Y light text (#303030)
ACCENT = (250, 133, 98)
SELECT = (241, 128, 101)

COLOR_RE = re.compile(
    r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[\d.]+\s*)?\)"
    r"|\b(?:white|black)\b")
SHADOW_PROPS = ("box-shadow", "text-shadow", "-gtk-icon-shadow")
ON_COLOR_HINTS = (":selected", ":checked", "suggested-action", "destructive-action", "selection",
                  "progressbar", "highlight", "infobar", "rubberband", "level", "block.filled",
                  "needs-attention", "selection-mode", ".error", ".warning", "app-notification",
                  "badge", "coloured", ".sidebar-item.active")

stats: dict[str, int] = {}


def bump(key: str) -> None:
    stats[key] = stats.get(key, 0) + 1


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
    a = float(nums[3]) if len(nums) == 4 else 1.0
    return int(nums[0]), int(nums[1]), int(nums[2]), a


def wrap(expr: str, a: float) -> str:
    simplify = {"mix(bg, text, 1)": "text", "mix(bg, text, 0)": "bg",
                "mix(bg, base, 1)": "base", "mix(bg, base, 0)": "bg"}
    expr = simplify.get(expr, expr)
    if a >= 0.999:
        return "{{" + expr + "}}"
    return "{{alpha(" + expr + f", {round(a, 3):g})" + "}}"


def fmt(t: float) -> str:
    return f"{round(t, 3):g}"


def convert(lit: str, prop: str, selector: str) -> str:
    sel = selector.lower()
    r, g, b, a = parse(lit)
    if a <= 0.001:
        bump("transparent")
        return "transparent"
    if (r, g, b) == ACCENT:
        bump("accent")
        return wrap("accent", a)
    if (r, g, b) == SELECT:
        bump("select")
        return wrap("select", a)
    if "osd" in sel:
        bump("osd kept")
        return lit
    is_shadow = prop in SHADOW_PROPS
    grey = max(r, g, b) - min(r, g, b) <= 6


    if grey:
        v = round((r + g + b) / 3)
        if is_shadow:
            if v <= 60:
                bump("shadow black kept")
                return lit
            if v >= 240:
                bump("shadow white -> base")
                return wrap("base", a)
        if v <= 40 and a < 0.999:
            bump("black alpha -> text")
            return wrap("text", a)
        if v == 255 or v >= 254:
            if prop == "color" or prop.endswith("-color") and prop not in ("background-color", "border-color") \
                    or any(h in sel for h in ON_COLOR_HINTS) and prop in ("color", "caret-color", "-gtk-icon-palette"):
                bump("white -> accent_fg")
                return wrap("accent_fg", a)
            bump("white -> base")
            return wrap("base", a)
        if v >= REF_BG:
            bump("light grey -> mix(bg, base)")
            return wrap(f"mix(bg, base, {fmt((v - REF_BG) / (255 - REF_BG))})", a)
        if v >= REF_TEXT:
            bump("grey -> mix(bg, text)")
            return wrap(f"mix(bg, text, {fmt((REF_BG - v) / (REF_BG - REF_TEXT))})", a)
        bump("dark grey -> darker(text)")
        return wrap(f"darker(text, {fmt((REF_TEXT - v) / REF_TEXT)})", a)

    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hue = h * 360
    if 10 <= hue <= 45 and s < 0.45:
        # leftover Mint-Y-Brown accent tints -> shades of the selection color
        _, sl, _ = colorsys.rgb_to_hls(*(c / 255 for c in SELECT))
        if l >= sl:
            bump("brown -> lighter(select)")
            return wrap(f"lighter(select, {fmt((l - sl) / (1 - sl))})", a)
        bump("brown -> darker(select)")
        return wrap(f"darker(select, {fmt((sl - l) / sl)})", a)
    bump("semantic kept")
    return lit


def radius_value(value: str) -> str:
    def sub(m: re.Match) -> str:
        n = float(m.group(1))
        if 2 <= n <= 4:
            bump("radius -> r")
            return "{{r}}px"
        if 5 <= n <= 8:
            bump("radius -> r2")
            return "{{r2}}px"
        return m.group(0)

    return re.sub(r"(\d+(?:\.\d+)?)px", sub, value)


DECL_RE = re.compile(r"([-\w]+)(\s*:\s*)([^;{}]*)")


ASSET_DECL_RE = re.compile(r'[-\w]+\s*:[^;{}]*url\("assets/[^;{}]*;?[ \t]*\n?')


def convert_body(body: str, selector: str) -> str:
    # image-based checks, radios, switches and pane handles are redrawn in CSS by xl.css
    body, removed = ASSET_DECL_RE.subn("", body)
    for _ in range(removed):
        bump("asset declaration removed")
    def decl(m: re.Match) -> str:
        prop, sep, value = m.group(1).lower(), m.group(2), m.group(3)
        if prop == "border-radius" or prop.endswith("-radius"):
            value = radius_value(value)
        value = COLOR_RE.sub(lambda c: convert(c.group(0), prop, selector), value)
        return m.group(1) + sep + value

    return DECL_RE.sub(decl, body)


def convert_css(css: str) -> str:
    out = []
    pos = 0
    depth = 0
    stack: list[str] = []
    selector_start = 0
    i = 0
    while i < len(css):
        ch = css[i]
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            i = len(css) if end < 0 else end + 2
            continue
        if ch == "{":
            selector = css[selector_start:i]
            stack.append(selector.strip())
            out.append(css[pos:i + 1])
            pos = i + 1
            depth += 1
            selector_start = i + 1
        elif ch == "}":
            body = css[pos:i]
            selector = stack.pop() if stack else ""
            out.append(convert_body(body, selector) if not selector.startswith("@") else body)
            out.append("}")
            pos = i + 1
            depth -= 1
            selector_start = i + 1
        elif ch == ";" and depth == 0:
            # top-level statement such as @define-color name #hex;
            stmt = css[pos:i]
            out.append(COLOR_RE.sub(lambda c: convert(c.group(0), "color", stmt), stmt) + ";")
            pos = i + 1
            selector_start = i + 1
        i += 1
    out.append(css[pos:])
    return "".join(out)


def main() -> int:
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    css = src.read_text(encoding="utf-8")
    result = convert_css(css)
    header = ("/* xl-Cheeselooks: GTK 3 base layer.\n"
              " * Derived from Linux Mint's Mint-Y (GPL-3.0) via xl_cheese-Mint-Y-Variable,\n"
              " * converted by tools/convert_gtk3.py. Colors and radii are template tokens.\n"
              " * The hand-written layer in xl.css.tmpl is applied on top. */\n\n")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(header + result, encoding="utf-8")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"{v:5}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
