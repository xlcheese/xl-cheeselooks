"""Color math and palette derivation.

Every color in the theme is worked out here from three picks: accent,
background and text. The rules match docs/design-spec.md, section 3.
"""

from __future__ import annotations

import re

WHITE = "#FFFFFF"
BLACK = "#000000"
ATTENTION_RED = "#E5534B"

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


def title_gradient(color: str, amount: float) -> tuple[str, str]:
    """Title bar: lighter top, bottom exactly the menubar/toolbar color."""
    return lighter(color, 0.20 * amount), color


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

def derive(accent: str, bg: str, text: str) -> dict[str, str]:
    """Work out the full palette from the three picks."""
    accent, bg, text = normalize(accent), normalize(bg), normalize(text)
    dark = luminance(bg) < luminance(text)

    def pick(light_value: str, dark_value: str) -> str:
        return dark_value if dark else light_value

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

    header = pick(mix(bg, text, 0.05), mix(bg, text, 0.06))
    button = pick(mix(bg, WHITE, 0.60), mix(bg, text, 0.08))
    menu_bg = pick(mix(bg, text, 0.03), mix(bg, text, 0.04))
    fav_bg = pick(mix(bg, text, 0.075), mix(bg, text, 0.09))

    return {
        "accent": accent,
        "bg": bg,
        "text": text,
        "accent_fg": accent_fg,
        "select": select,
        "accent_hover": lighter(accent, 0.12),
        "accent_press": darker(accent, 0.14),
        "base": pick(mix(bg, WHITE, 0.75), darker(bg, 0.18)),
        "button": button,
        "button_hover": pick(lighter(button, 0.50), mix(button, text, 0.06)),
        "header": header,
        "menubar_hover": mix(header, text, 0.12),
        "sidebar": pick(mix(bg, text, 0.035), mix(bg, text, 0.03)),
        "sidebar_hover": pick(mix(bg, text, 0.14), mix(bg, text, 0.13)),
        "hover": pick(mix(bg, text, 0.07), mix(bg, text, 0.08)),
        "pressed": pick(mix(bg, text, 0.13), mix(bg, text, 0.15)),
        "border": pick(mix(bg, text, 0.20), mix(bg, text, 0.16)),
        "border_strong": pick(mix(bg, text, 0.30), mix(bg, text, 0.26)),
        "trough": pick(mix(bg, text, 0.12), mix(bg, text, 0.14)),
        "text_dim": mix(text, bg, 0.38),
        "menu_bg": menu_bg,
        "menu_hover": mix(menu_bg, text, 0.10),
        "fav_bg": fav_bg,
        "fav_hover": mix(fav_bg, text, 0.10),
        "panel": pick(mix(bg, WHITE, 0.25), mix(bg, text, 0.03)),
        "pb_rest": pick(mix(bg, text, 0.15), mix(bg, text, 0.13)),
        "pb_hover": pick(lighter(bg, 0.50), mix(bg, text, 0.22)),
        "pb_edge": pick(mix(bg, text, 0.35), darker(bg, 0.45)),
        "pb_focus": accent,
        "pb_progress": darker(accent, 0.25),
        "pb_attention": pick(mix(bg, ATTENTION_RED, 0.36), mix(bg, ATTENTION_RED, 0.50)),
        "pb_attention_edge": mix(bg, "#B8322B", 0.6),
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
