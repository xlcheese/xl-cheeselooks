"""The focused window's marker on panel window-list buttons.

    active_marker  none   nothing extra (the selected_color face only)
                   line   a 3px accent line along the bottom of the button
                   glow   an accent glow rising from the bottom edge and
                          fading out by the middle of the button (Clearlooks)

The same names as the tab markers (tabs.py). Cinnamon allows one shadow per
widget and its gradients always span the whole button, so each marker is a
single inset shadow (it replaces the button's highlight). The glow is that
shadow blurred: strongest along the bottom edge, gone by the middle. Kept off
the sides with the same negative-spread trick as the style layers.
Templates have no conditionals, so the rules are written here.
"""

from __future__ import annotations

from . import palette as pal

LINE_WIDTH = 3
GLOW_ALPHA = 0.6   # at the bottom edge


def shadow(kind: str, color: str, height: int) -> str:
    if kind == "line":
        return f"inset 0 -{LINE_WIDTH}px 0 0 {color}"
    # glow: blur b = half the button, so the fade reaches the middle. The
    # shadow's hole is grown by b on every side (keeps it off the sides and
    # top) and lifted so its lower edge sits b/2 above the bottom: full
    # strength at the bottom edge, nothing left at height b.
    b = max(4, round(height / 2))
    lift = b + b // 2
    return f"inset 0 -{lift}px {b}px -{b}px {pal.rgba(color, GLOW_ALPHA)}"


def css(t: dict[str, str]) -> str:
    kind = t.get("panel.w.panel_button.active_marker", "none")
    head = f"/* focused window marker: {kind} */"
    if kind == "none":
        return head
    face = t["panel.w.panel_button.selected_color"]
    accent = t["panel.accent"]
    # on an accent face, a darker accent so the marker still shows
    color = t["panel.accent_press"] if face == accent else accent
    sel = ",\n".join(f".{box}:focus, .{box}:focus:hover"
                     for box in ("grouped-window-list-item-box", "window-list-item-box"))
    return f"{head}\n{sel} {{\n  box-shadow: {shadow(kind, color, int(t['panel.height']))}; }}"
