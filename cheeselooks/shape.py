"""Size, roundness and timing rules (docs/design-spec.md, section 4)."""

from __future__ import annotations

# Size: the control height, 24-38px in 2px steps (even heights keep 16px icons
# on whole pixels); row padding and title-button glyph size follow it. The old
# Compact / Normal / Large are 26, 30 and 36.
SIZE_RANGE = (24, 38)
SIZE_DEFAULT = 30
OLD_SIZES = {"compact": 26, "normal": 30, "large": 36}
# kept for reference: the three sizes before the slider
SIZES: dict[str, tuple[int, int, int]] = {
    "compact": (26, 3, 12),
    "normal": (30, 4, 14),
    "large": (36, 6, 16),
}


def size_value(size) -> int:
    """A Size setting as a control height: an old name, or a number snapped to
    an even height within the range."""
    if isinstance(size, str):
        return OLD_SIZES.get(size, SIZE_DEFAULT)
    lo, hi = SIZE_RANGE
    return max(lo, min(hi, int(round(size / 2)) * 2))


def size_params(size) -> tuple[int, int, int]:
    """(control height, row padding, title-button glyph size) for a Size."""
    ctl = size_value(size)
    pad = max(2, round(4 + (ctl - 30) / 3))            # 26 -> 3, 30 -> 4, 36 -> 6
    glyph = max(12, min(16, 2 * round((14 + (ctl - 30) / 3) / 2)))
    return ctl, pad, glyph

WINDOW_RADIUS_MAX = 14
SWITCH_RADIUS_FULL = 12
CHECK_RADIUS_MAX = 5
DEFAULT_PANEL_HEIGHT = 40


def radius(pct: float, height: float) -> int:
    """Roundness as a percentage of fully round for something `height` tall."""
    pct = max(0.0, min(100.0, pct))
    return round(pct / 100 * height / 2)


def window_radius(control_radius: int) -> int:
    return min(WINDOW_RADIUS_MAX, round(control_radius * 1.4))


def shape_tokens(size: str, roundness: float) -> dict[str, int]:
    ctl, pad, glyph = size_params(size)
    r = radius(roundness, ctl)
    delta = ctl - SIZE_DEFAULT         # Normal (30) keeps Mint-Y's original sizes
    return {
        "button_min_h": 22 + delta,
        "entry_min_h": 20 + delta,
        "menu_pad": pad + 1,
        "row_min_h": 30 + delta,
        "ctl": ctl,
        "pad": pad,
        "glyph": glyph,
        "r": r,
        "r2": window_radius(r),
        "r_check": min(r, CHECK_RADIUS_MAX),
        "r_switch": radius(roundness, SWITCH_RADIUS_FULL * 2),
    }
