"""Text editors in the theme's colours (Integration → "Text editors"; on by
default, undoable).

Xed, gedit, Meld and other GTK text editors colour their text area with a
GtkSourceView colour scheme, not the GTK theme. A scheme made for light
themes (Xed's Classic) on a dark theme gave white line numbers on a fixed
light gutter and dark-blue comments on dark. So at each Apply we write an
"xl-Cheeselooks" scheme from the theme: the editor background and text, the
gutter and line numbers, the current line, selection and cursor, matching
brackets and search results in the accent, and syntax colours worked out to
read on the editor background (light or dark), keyed to the accent's hue.

It goes into every GtkSourceView version's user folder (3, 4 for Xed and
Meld, 5, and gedit's own), so any editor can pick it. Xed, gedit and Meld are
switched to it (their previous scheme is remembered); switching off puts
their schemes back and removes the files. Flatpak editors can't see these
folders.
"""

from __future__ import annotations

import colorsys
import json
from pathlib import Path
from xml.sax.saxutils import quoteattr

from . import palette as pal
from . import paths, reload

SCHEME_ID = "xl-cheeselooks"
SCHEME_NAME = "xl-Cheeselooks"
STYLE_DIRS = ("gtksourceview-3.0", "gtksourceview-4", "gtksourceview-5", "libgedit-gtksourceview-300")
# (schema, key): the editors we switch to the scheme, if installed
EDITORS = (("org.x.editor.preferences.editor", "scheme", "Xed"),
           ("org.gnome.gedit.preferences.editor", "scheme", "gedit"),
           ("org.gnome.meld", "style-scheme", "Meld"))


def scheme_files() -> list[Path]:
    data = paths._xdg("XDG_DATA_HOME", paths.HOME / ".local" / "share")
    return [data / d / "styles" / f"{SCHEME_ID}.xml" for d in STYLE_DIRS]


def state_file() -> Path:
    return paths.config_dir() / "editor-colors.json"


# ---------------------------------------------------------------- colours

def _readable(color: str, bg: str, need: float = 4.5) -> str:
    """The colour, moved in lightness (hue and saturation kept) until it reads on bg."""
    if pal.contrast(color, bg) >= need:
        return color
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in pal.to_rgb(color)))
    toward = 0.0 if pal.luminance(bg) > 0.4 else 1.0
    for step in range(1, 41):
        nl = l + (toward - l) * step / 40
        r, g, b = colorsys.hls_to_rgb(h, nl, s)
        c = pal.from_rgb(r * 255, g * 255, b * 255)
        if pal.contrast(c, bg) >= need:
            return c
    return "#000000" if toward == 0.0 else "#FFFFFF"


def _hue(base: str, turn: float, sat: float, light: float) -> str:
    h = colorsys.rgb_to_hls(*(v / 255 for v in pal.to_rgb(base)))[0]
    r, g, b = colorsys.hls_to_rgb((h + turn) % 1, light, sat)
    return pal.from_rgb(r * 255, g * 255, b * 255)


def colours(t: dict[str, str]) -> dict[str, str]:
    bg, text, accent = t["base"], t["text"], t["accent"]
    dark = pal.luminance(bg) < 0.25
    light = 0.70 if dark else 0.38         # syntax colours: light on dark, deep on light
    sat = 0.55 if dark else 0.65
    c = {"bg": bg, "text": text, "accent": accent, "accent_fg": t["accent_fg"]}
    c["gutter"] = pal.mix(bg, t["bg"], 0.6)
    c["line_numbers"] = _readable(pal.mix(text, bg, 0.5), c["gutter"], 3.0)
    c["current_line"] = pal.mix(bg, text, 0.06 if dark else 0.04)
    c["current_number"] = text
    c["select"] = pal.mix(bg, accent, 0.35 if dark else 0.28)
    c["select_fg"] = text
    c["bracket"] = pal.mix(bg, accent, 0.45)
    c["search"] = pal.mix(bg, accent, 0.30) if dark else pal.mix(bg, "#F5C211", 0.45)
    c["right_margin"] = pal.mix(bg, text, 0.12)
    c["spaces"] = pal.mix(bg, text, 0.25)
    # syntax: the statements in the accent; the others round the colour wheel from it
    c["statement"] = _readable(accent, bg)
    c["type"] = _readable(_hue(accent, 0.45, sat, light), bg)
    c["constant"] = _readable(_hue(accent, 0.80, sat, light), bg)
    c["string"] = _readable(_hue(accent, 0.30, sat, light), bg)
    c["identifier"] = _readable(_hue(accent, 0.55, sat * 0.9, light), bg)
    c["preprocessor"] = _readable(_hue(accent, 0.12, sat, light), bg)
    c["special"] = _readable(_hue(accent, 0.90, sat, light), bg)
    c["comment"] = _readable(pal.mix(text, bg, 0.45), bg, 3.0)
    c["error_bg"] = pal.mix(bg, "#E01B24", 0.35)
    c["warning_bg"] = pal.mix(bg, "#F5C211", 0.30)
    c["added"] = _readable(_hue("#33D17A", 0, sat, light), bg)
    c["removed"] = _readable(_hue("#E01B24", 0, sat, light), bg)
    return c


def scheme_xml(t: dict[str, str]) -> str:
    c = colours(t)
    rows = [
        ("text", dict(foreground=c["text"], background=c["bg"])),
        ("selection", dict(foreground=c["select_fg"], background=c["select"])),
        ("selection-unfocused", dict(foreground=c["select_fg"], background=pal.mix(c["bg"], c["text"], 0.12))),
        ("cursor", dict(foreground=c["text"])),
        ("secondary-cursor", dict(foreground=c["comment"])),
        ("current-line", dict(background=c["current_line"])),
        ("line-numbers", dict(foreground=c["line_numbers"], background=c["gutter"])),
        ("current-line-number", dict(foreground=c["current_number"], background=c["current_line"])),
        ("bracket-match", dict(foreground=c["text"], background=c["bracket"], bold="true")),
        ("bracket-mismatch", dict(foreground=c["text"], background=c["error_bg"], bold="true")),
        ("search-match", dict(foreground=c["text"], background=c["search"])),
        ("right-margin", dict(foreground=c["right_margin"], background=c["right_margin"])),
        ("draw-spaces", dict(foreground=c["spaces"])),
        ("background-pattern", dict(background=c["current_line"])),
        ("def:comment", dict(foreground=c["comment"], italic="true")),
        ("def:shebang", dict(foreground=c["comment"], bold="true")),
        ("def:doc-comment-element", dict(italic="true")),
        ("def:constant", dict(foreground=c["constant"])),
        ("def:string", dict(foreground=c["string"])),
        ("def:special-char", dict(foreground=c["special"])),
        ("def:special-constant", dict(foreground=c["constant"], bold="true")),
        ("def:identifier", dict(foreground=c["identifier"])),
        ("def:statement", dict(foreground=c["statement"], bold="true")),
        ("def:type", dict(foreground=c["type"], bold="true")),
        ("def:preprocessor", dict(foreground=c["preprocessor"])),
        ("def:emphasis", dict(italic="true")),
        ("def:strong-emphasis", dict(bold="true")),
        ("def:inline-code", dict(foreground=c["identifier"])),
        ("def:insertion", dict(underline="single")),
        ("def:deletion", dict(strikethrough="true")),
        ("def:link-text", dict(foreground=c["statement"])),
        ("def:link-symbol", dict(foreground=c["statement"], bold="true")),
        ("def:link-destination", dict(italic="true", underline="single")),
        ("def:heading", dict(foreground=c["statement"], bold="true")),
        ("def:thematic-break", dict(foreground=c["statement"], bold="true")),
        ("def:preformatted-section", dict(foreground=c["identifier"])),
        ("def:list-marker", dict(foreground=c["statement"], bold="true")),
        ("def:net-address", dict(foreground=c["statement"], italic="true", underline="single")),
        ("def:error", dict(background=c["error_bg"], bold="true")),
        ("def:warning", dict(background=c["warning_bg"])),
        ("def:note", dict(background=c["warning_bg"], bold="true")),
        ("def:underlined", dict(italic="true", underline="single")),
        ("diff:added-line", dict(foreground=c["added"])),
        ("diff:removed-line", dict(foreground=c["removed"])),
        ("diff:changed-line", dict(foreground=c["preprocessor"])),
        ("diff:diff-file", dict(foreground=c["type"], bold="true")),
        ("diff:location", dict(foreground=c["statement"], bold="true")),
        ("diff:special-case", dict(foreground=c["constant"])),
        ("xml:tags", dict(foreground=c["type"])),
        ("xml:attribute-name", dict(foreground=c["identifier"])),
        ("xml:namespace", dict(bold="true")),
        ("sh:variable", dict(foreground=c["constant"])),
        ("sh:variable-definition", dict(foreground=c["type"])),
    ]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             "<!-- Written by xl-Cheeselooks from your theme at each Apply (Integration: Text editors). -->",
             f'<style-scheme id="{SCHEME_ID}" name="{SCHEME_NAME}" version="1.0">',
             "  <author>xl-Cheeselooks</author>",
             "  <description>Your xl-Cheeselooks theme's colors, made by the xl-Cheeselooks tool.</description>"]
    for name, attrs in rows:
        a = " ".join(f"{k}={quoteattr(v)}" for k, v in attrs.items())
        lines.append(f'  <style name="{name}" {a}/>')
    lines.append("</style-scheme>")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- state

def _load_state() -> dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    f = state_file()
    if not state:
        if f.exists():
            f.unlink()
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- on / off

def enable(t: dict[str, str]) -> list[str]:
    """Write the scheme (ours: simply rewritten each Apply) and switch the
    installed editors to it, remembering their previous scheme the first time."""
    xml = scheme_xml(t)
    for f in scheme_files():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(xml, encoding="utf-8")
    state = _load_state()
    state["written"] = True
    previous = state.setdefault("previous", {})
    switched = []
    if reload.available():
        for schema, key, name in EDITORS:
            current = reload.get(schema, key)
            if current is None:                # not installed
                continue
            current = current.strip("'\"")
            if schema not in previous and current != SCHEME_ID:
                previous[schema] = current
            if current != SCHEME_ID and reload.set_value(schema, key, SCHEME_ID):
                switched.append(name)
    _save_state(state)
    log = ["Text editors: xl-Cheeselooks color scheme written"]
    if switched:
        log.append(f"Text editors: {', '.join(switched)} switched to it")
    return log


def disable() -> list[str]:
    """Put each editor's previous scheme back and remove ours."""
    state = _load_state()
    if not state:
        return []
    if reload.available():
        for schema, key, _name in EDITORS:
            before = state.get("previous", {}).get(schema)
            if before and (reload.get(schema, key) or "").strip("'\"") == SCHEME_ID:
                reload.set_value(schema, key, before)
    for f in scheme_files():
        if f.exists():
            f.unlink()
    _save_state({})
    return ["Text editors: xl-Cheeselooks color scheme removed, your previous schemes back"]


def active() -> bool:
    return bool(_load_state())


NOTE = ("Xed, gedit and Meld use your colors in their text area (switched for you; off puts "
        "back your previous scheme). Other GTK editors: pick “xl-Cheeselooks” in their color "
        "settings.")
