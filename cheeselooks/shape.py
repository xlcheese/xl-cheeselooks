"""Size, roundness and timing rules (docs/design-spec.md, section 4)."""

from __future__ import annotations

# control height, row padding, title-button glyph size
SIZES: dict[str, tuple[int, int, int]] = {
    "compact": (26, 3, 12),
    "normal": (30, 4, 14),
    "large": (36, 6, 16),
}

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
    ctl, pad, glyph = SIZES[size]
    r = radius(roundness, ctl)
    return {
        "ctl": ctl,
        "pad": pad,
        "glyph": glyph,
        "r": r,
        "r2": window_radius(r),
        "r_check": min(r, CHECK_RADIUS_MAX),
        "r_switch": radius(roundness, SWITCH_RADIUS_FULL * 2),
    }
