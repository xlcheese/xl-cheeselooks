"""Color math and palette derivation.

Every color in the theme is worked out here from three picks: accent,
background and text. The rules match docs/design-spec.md, section 3.
"""

from __future__ import annotations

import re

WHITE = "#FFFFFF"
BLACK = "#000000"
ATTENTION_RED = "#E5534B"
DESTRUCTIVE = "#F04A50"   # Mint-Y's destructive-action red; semantic, so fixed

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def is_hex(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX_RE.match(value.strip()))


def normalize(value: str) -> str:
    """Return a color as uppercase #RRGGBB. Accepts #RGB, RGB, #RRGGBB, RRGGBB."""
    m = _HEX_RE.match(value.strip())
    if not m:
        raise ValueError(f"not a hex color: {value!r}")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.upper()


def to_rgb(color: str) -> tuple[int, int, int]:
    h = normalize(color)[1:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def from_rgb(r: float, g: float, b: float) -> str:
    def clamp(v: float) -> int:
        return max(0, min(255, round(v)))

    return "#{:02X}{:02X}{:02X}".format(clamp(r), clamp(g), clamp(b))


def mix(a: str, b: str, t: float) -> str:
    """Blend from a toward b by t (0 = a, 1 = b)."""
    x, y = to_rgb(a), to_rgb(b)
    return from_rgb(*(x[i] + (y[i] - x[i]) * t for i in range(3)))


def lighter(color: str, t: float) -> str:
    return mix(color, WHITE, t)


def darker(color: str, t: float) -> str:
    return mix(color, BLACK, t)


def luminance(color: str) -> float:
    """WCAG relative luminance."""

    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def rgb_triplet(color: str) -> str:
    """'250, 133, 98' for use inside rgba()."""
    return ", ".join(str(v) for v in to_rgb(color))


def rgba(color: str, alpha: float) -> str:
    alpha = max(0.0, min(1.0, alpha))
    return f"rgba({rgb_triplet(color)}, {round(alpha, 3):g})"


# --------------------------------------------------------------------------
# Gradients (spec section 4)
# --------------------------------------------------------------------------

def gradient(color: str, amount: float) -> tuple[str, str]:
    """One soft top-to-bottom shade, skewed darker so tops don't wash out.

    amount is 0..1 (the Gradient slider / 100).
    """
    return lighter(color, 0.10 * amount), darker(color, 0.20 * amount)


GRADIENT_SHAPES = ("smooth", "split")


def gradient_css(top: str, bottom: str, shape: str = "smooth", step: float = 0.4) -> str:
    """A top-to-bottom face as a CSS gradient.

    smooth  top fading to bottom
    split   a glossy face, as in Clearlooks Gummy / Phenix: the top half fades
            gently, then a crisp step at the middle (two stops at 50%) and the
            bottom half fades on to the bottom colour. `step` (0-1) is how much
            of the top half's fade is saved for that step: 0 = smooth, 1 = a flat
            top half and the whole first half of the fade in one step.
    """
    if shape != "split" or top == bottom:
        return f"linear-gradient(to bottom, {top}, {bottom})"
    upper = mix(top, bottom, 0.5 * (1 - step))   # where the top half ends
    middle = mix(top, bottom, 0.5)               # where the bottom half starts
    return f"linear-gradient(to bottom, {top}, {upper} 50%, {middle} 50%, {bottom})"


def title_gradient(color: str, amount: float) -> tuple[str, str]:
    """Title bar: lighter top, bottom exactly the menubar/toolbar color."""
    return lighter(color, 1.00 * amount), color


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

def derive(accent: str, bg: str, text: str, hover: float = 1.0) -> dict[str, str]:
    """Work out the full palette from the three picks.

    hover scales every hover step together (Hover strength slider / 50):
    1.0 is the default, 0 means hovers don't change color, 2.0 doubles them.
    """
    accent, bg, text = normalize(accent), normalize(bg), normalize(text)
    dark = luminance(bg) < luminance(text)

    def pick(light_value: str, dark_value: str) -> str:
        return dark_value if dark else light_value

    def lift(surface: str, amount: float) -> str:
        """Hover for raised surfaces. Light themes go lighter (as Mint-Y does);
        a surface already at white has no room, so it goes slightly darker.
        Dark themes go toward the text color, which is lighter there."""
        if dark:
            return mix(surface, text, amount * hover)
        if luminance(surface) > 0.97:
            return mix(surface, text, 0.05 * hover)
        return mix(surface, WHITE, min(1.0, amount * hover))

    if luminance(accent) > 0.55:
        accent_fg = darker(bg, 0.2) if dark else mix(text, BLACK, 0.3)
    else:
        accent_fg = WHITE

    select = accent
    if accent_fg == WHITE:
        for _ in range(8):
            if contrast(select, WHITE) >= 2.6:
                break
            select = darker(select, 0.04)

    header = mix(bg, text, 0.066)   # Mint-Y's toolbar shade: #E8E8E8 on the default colors
    # light buttons rest a little below white so hover has room to go lighter
    button = pick(mix(bg, WHITE, 0.30), mix(bg, text, 0.08))
    border_strong = pick(mix(bg, text, 0.30), mix(bg, text, 0.26))
    base = pick(mix(bg, WHITE, 0.75), darker(bg, 0.18))
    menu_bg = base                                             # GTK menus: content color, as Mint-Y
    shell_menu_bg = pick(mix(bg, text, 0.03), mix(bg, text, 0.04))  # Cinnamon menus and popups
    fav_bg = pick(mix(bg, text, 0.075), mix(bg, text, 0.09))

    return {
        "accent": accent,
        "bg": bg,
        "text": text,
        "accent_fg": accent_fg,
        "select": select,
        "accent_hover": lighter(accent, 0.12),
        "accent_press": darker(accent, 0.14),
        "base": base,
        "button": button,
        "button_hover": pick(lift(button, 0.80), lift(button, 0.06)),
        "header": header,
        "menubar_hover": mix(header, text, 0.09 * hover),
        # hover for buttons that aren't drawn at rest (toolbar, title buttons) and
        # unselected tabs: lighter than the toolbar, but not as bright as a full button hover
        "flat_hover": pick(lift(header, 0.50), lift(header, 0.08)),
        "sidebar": pick(mix(bg, text, 0.035), mix(bg, text, 0.03)),
        "sidebar_hover": pick(mix(bg, text, 0.035 + 0.105 * hover), mix(bg, text, 0.03 + 0.10 * hover)),
        "hover": pick(mix(bg, text, 0.07 * hover), mix(bg, text, 0.08 * hover)),
        "pressed": pick(mix(bg, text, 0.13), mix(bg, text, 0.15)),
        "border": pick(mix(bg, text, 0.20), mix(bg, text, 0.16)),
        "border_strong": border_strong,
        # hovered borders: darker on light themes, lighter on dark (both toward text)
        "border_hover": mix(border_strong, text, 0.15 * hover),
        "trough": pick(mix(bg, text, 0.12), mix(bg, text, 0.14)),
        # scrollbar thumb at rest and hovered (Mint-Y's; dragging uses the accent)
        "scroll_slider": mix(bg, text, 0.421),
        "scroll_hover": mix(bg, text, 0.31),
        "text_dim": mix(text, bg, 0.38),
        "menu_bg": menu_bg,
        "menu_hover": mix(menu_bg, text, 0.10 * hover),
        "shell_menu_bg": shell_menu_bg,
        "shell_menu_hover": mix(shell_menu_bg, text, 0.10 * hover),
        "fav_bg": fav_bg,
        "fav_hover": mix(fav_bg, text, 0.10 * hover),
        "panel": pick(mix(bg, WHITE, 0.25), mix(bg, text, 0.03)),
        "pb_rest": pick(mix(bg, text, 0.15), mix(bg, text, 0.13)),
        "pb_hover": pick(lift(bg, 0.50), mix(bg, text, 0.13 + 0.09 * hover)),
        "pb_edge": pick(mix(bg, text, 0.35), darker(bg, 0.45)),
        "pb_focus": accent,
        "pb_progress": darker(accent, 0.25),
        "pb_attention": pick(mix(bg, ATTENTION_RED, 0.36), mix(bg, ATTENTION_RED, 0.50)),
        "pb_attention_edge": mix(bg, "#B8322B", 0.6),
        "knob": pick(WHITE, mix(bg, text, 0.75)),
        "destructive": DESTRUCTIVE,
        "destructive_fg": WHITE,
        "white": WHITE,
        "black": BLACK,
    }


def is_dark(palette: dict[str, str]) -> bool:
    return luminance(palette["bg"]) < luminance(palette["text"])


def terminal_colors(theme: dict[str, str], bg: str | None, text: str | None) -> dict[str, str]:
    """Terminal follows the theme (content area + text) unless colors are given."""
    t_bg = normalize(bg) if bg else theme["base"]
    t_text = normalize(text) if text else theme["text"]
    dark = luminance(t_bg) < luminance(t_text)
    accent = theme["accent"]
    return {
        "bg": t_bg,
        "text": t_text,
        "cursor": accent,
        "prompt": lighter(accent, 0.10) if dark else darker(accent, 0.25),
    }


def readability_warnings(palette: dict[str, str], label: str = "Theme") -> list[str]:
    """Plain-language warnings; never blocking."""
    notes = []
    c = contrast(palette["text"], palette["bg"])
    if c < 4.5:
        notes.append(f"{label} text is hard to read on its background "
                     f"(contrast {c:.1f}:1, aim for 4.5 or more).")
    if contrast(palette["accent"], palette["bg"]) < 1.5:
        notes.append(f"{label} accent nearly disappears against the background.")
    if contrast(palette["accent_fg"], palette["select"]) < 2.5:
        notes.append(f"{label} text on selected items is faint.")
    return notes
