"""The xl-Cheeselooks settings app (GTK 3).

Themes: the Global tab starts with the list of themes (built-in, yours, and
Custom). Picking one sets every tab to that theme. Changing anything makes it
"Custom", which keeps your latest changes; Save Theme… names Custom as a theme
of your own. Each tab's "Reset to Theme Defaults" puts that tab back to the
theme it started from (and if nothing differs any more, the theme is no longer
Custom).

Preview: every change regenerates the theme into a cache folder and loads its
GTK 3 stylesheet into this app only, so the app's own widgets and a sample
window show the result straight away, with a drawn panel. Nothing reaches the
desktop until Apply; after Apply a bar offers Revert, which puts the previous
desktop theme back and keeps your settings here.

Controls are generated from settings._RULES (the table that validates
settings.json). The on/off switches behind some settings ("own colors",
"customize", "follow Global") are not shown: changing one of those settings
turns its switch on (or Follow Global off) by itself.
"""

from __future__ import annotations

import copy
import json
import shutil
import threading
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import cli, flatpak, palette as pal, panelmarker, paths, render, settings, styles, themes, titlebuttons, tokens  # noqa: E402

APP_TITLE = "xl-Cheeselooks"
PREVIEW_DELAY_MS = 120

TABS = [  # (settings section, tab title)
    ("global", "Global"), ("style", "Style"), ("panel", "Panel & Menu"),
    ("window_borders", "Window Borders"), ("terminal", "Terminal"),
    ("details", "Details"), ("integration", "Integration"), ("share", "Import & Export"),
]
LABELS = {
    "accent": "Accent", "bg": "Background", "text": "Text", "size": "Size",
    "roundness": "Roundness", "gradient": "Gradient", "hover_in_ms": "Hover in (ms)",
    "hover_out_ms": "Hover out (ms)", "hover_strength": "Hover strength", "depth": "Depth",
    "label_weight": "Label weight", "panel_opacity": "Panel opacity", "menu_opacity": "Menu opacity",
    "title_bar": "Title bar", "title_text": "Title text", "border": "Border",
    "title_bar_height": "Title bar height", "border_width": "Border width",
    "title_gradient": "Title bar gradient", "button_layout": "Buttons on the",
    "button_style": "Button style", "button_roundness": "Button roundness",
    "mode": "Mode", "color": "Color", "width": "Width",
    "libadwaita_colors": "Colors for libadwaita apps", "libadwaita_accent": "GNOME accent color",
}
GROUPS = {"panel_shape": "Panel shape", "menu_shape": "Menu shape", "tooltips": "Tooltips",
          "scrollbars": "Scrollbars", "sliders": "Sliders", "switches": "Switches",
          "focus_ring": "Focus ring"}
SECTION_NOTES = {
    "panel": "Colors left on “Follow theme” use the Global colors.",
    "window_borders": "Colors left on “Follow theme” come from the Global colors.",
    "terminal": "Left on “Follow theme”, the terminal uses the theme's content colors.",
}
GATES = {"separate_colors": True, "custom": True, "follow_global": False}  # value set when a sibling changes
HIDDEN = set(GATES) | {"flatpak_access"}
CHOICE_LABELS = {"button_style": titlebuttons.STYLES}   # choices shown by name instead of id


def _get(data: dict, path: tuple[str, ...]) -> Any:
    for k in path:
        data = data[k]
    return data


def _set(data: dict, path: tuple[str, ...], value: Any) -> None:
    for k in path[:-1]:
        data = data[k]
    data[path[-1]] = value


def _hex(rgba: Gdk.RGBA) -> str:
    return "#{:02X}{:02X}{:02X}".format(round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))


def _rgba(hex_color: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hex_color)
    return c


def _same(a: dict, b: dict) -> bool:
    """Equal settings, ignoring which theme they're labelled with."""
    strip = lambda d: {k: v for k, v in d.items() if k not in ("theme", "based_on", "version")}  # noqa: E731
    return strip(a) == strip(b)


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title=APP_TITLE)
        self.set_default_size(1180, 740)
        self.applied = settings.load(paths.settings_file())
        self.data = copy.deepcopy(self.applied)
        if self.data["theme"] == themes.CUSTOM:
            self.base = themes.based_on() or settings.DEFAULTS["theme"]
        else:
            self.base = self.data["theme"]
        self.base_cache: dict[str, dict] = {}
        self.controls: dict[tuple[str, ...], tuple[Any, str]] = {}
        self.syncing = False
        self.pending = 0
        self.preview_dir = paths.HOME / ".cache" / "xl-cheeselooks" / "preview"
        self.theme_css = Gtk.CssProvider()
        self.extra_css = Gtk.CssProvider()
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(screen, self.theme_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Gtk.StyleContext.add_provider_for_screen(screen, self.extra_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

        header = Gtk.HeaderBar(show_close_button=True, title=APP_TITLE)
        header.set_subtitle("Preview: nothing changes on the desktop until Apply")
        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.get_style_context().add_class("suggested-action")
        self.apply_btn.connect("clicked", self.on_apply)
        header.pack_start(self.apply_btn)          # opposite the window buttons, at the outer edge
        # shown after Apply: puts the previous desktop theme back
        self.revert_btn = Gtk.Button(label="Revert")
        self.revert_btn.get_style_context().add_class("xl-drawn")    # a drawn button, not flat
        self.revert_btn.set_tooltip_text("Put the previous theme back on the desktop (your settings here stay)")
        self.revert_btn.connect("clicked", self.on_revert)
        self.revert_btn.set_no_show_all(True)
        header.pack_start(self.revert_btn)
        self.set_titlebar(header)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for section, title in TABS:
            self.stack.add_titled(self._tab(section), section, title)
        sidebar = Gtk.StackSidebar(stack=self.stack)
        sidebar.set_size_request(160, -1)
        self.status = Gtk.Label(xalign=0, selectable=True, wrap=True, margin_start=12, margin_bottom=6)
        self.status.get_style_context().add_class("dim-label")
        pages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pages.pack_start(self.stack, True, True, 0)
        pages.pack_start(self.status, False, False, 0)
        left = Gtk.Box()
        left.pack_start(sidebar, False, False, 0)
        left.pack_start(pages, True, True, 0)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.pack1(left, resize=True, shrink=False)
        paned.pack2(self._preview(), resize=False, shrink=False)
        paned.set_position(660)
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main.pack_start(paned, True, True, 0)
        self.add(main)
        self.fill_theme_list()
        self.sync_controls()
        self.update_preview()
        self.update_buttons()
        self.show_all()

    # ------------------------------------------------------------------ tabs
    def _page(self, grid: Gtk.Grid) -> Gtk.Widget:
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add(grid)
        return scroller

    def _tab(self, section: str) -> Gtk.Widget:
        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=14)
        row = 0
        if section == "share":
            return self._page(self._share_tab(grid))
        if section == "global":
            row = self._theme_rows(grid, row)
        if section == "style":
            row = self._style_rows(grid, row)
        if section == "terminal":
            row = self._terminal_picks(grid, row)
        if section in SECTION_NOTES:
            note = Gtk.Label(label=SECTION_NOTES[section], xalign=0, wrap=True)
            note.get_style_context().add_class("dim-label")
            grid.attach(note, 0, row, 2, 1)
            row += 1
        group = None
        for path, kind, extra in settings._RULES:
            if path[0] != section or path[-1] in HIDDEN:
                continue
            if len(path) == 3 and path[1] != group:
                group = path[1]
                head = Gtk.Label(xalign=0, margin_top=8)
                head.set_markup(f"<b>{GLib.markup_escape_text(GROUPS.get(group, group))}</b>")
                grid.attach(head, 0, row, 2, 1)
                row += 1
            label = Gtk.Label(label=LABELS.get(path[-1], path[-1].replace("_", " ").capitalize()), xalign=0)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(self._control(path, kind, extra), 1, row, 1, 1)
            row += 1
        if section == "integration":
            row = self._flatpak_row(grid, row)
        reset = Gtk.Button(label="Reset to Theme Defaults", halign=Gtk.Align.START, margin_top=14)
        reset.set_tooltip_text("Put this tab back to the theme's values (other tabs stay as they are)")
        reset.connect("clicked", lambda _b, s=section: self.reset_section(s))
        grid.attach(reset, 0, row, 2, 1)
        return self._page(grid)

    def _control(self, path: tuple[str, ...], kind: str, extra: Any) -> Gtk.Widget:
        if kind in ("color", "color?"):
            box = Gtk.Box(spacing=10)
            button = Gtk.ColorButton(use_alpha=False, show_editor=True)   # straight to the editor
            button.connect("color-set", lambda b: self.changed(path, _hex(b.get_rgba())))
            value = Gtk.Label(xalign=0, selectable=True)
            box.pack_start(button, False, False, 0)
            box.pack_start(value, False, False, 0)
            self.controls[path] = ((button, value), kind)
            return box
        if kind in ("int", "int?"):    # int?: None shows the default (button roundness: the style's)
            lo, hi = extra
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_size_request(260, -1)
            scale.connect("value-changed", lambda s: self.changed(path, int(round(s.get_value()))))
            self.controls[path] = (scale, kind)
            return scale
        if kind == "bool":
            switch = Gtk.Switch(halign=Gtk.Align.START)
            switch.connect("notify::active", lambda s, _p: self.changed(path, s.get_active()))
            self.controls[path] = (switch, kind)
            return switch
        if len(extra) <= 3:
            # a few choices: inline buttons, one pressed
            box = Gtk.Box(halign=Gtk.Align.START)
            box.get_style_context().add_class("linked")
            buttons = {}
            for choice in extra:
                b = Gtk.ToggleButton(label=choice.replace("_", " ").capitalize())
                b.connect("toggled", lambda btn, c=choice: btn.get_active() and self.changed(path, c))
                box.pack_start(b, False, False, 0)
                buttons[choice] = b
            self.controls[path] = (buttons, "inline")
            return box
        combo = Gtk.ComboBoxText()
        names = CHOICE_LABELS.get(path[-1], {})
        for choice in extra:
            combo.append(choice, names.get(choice, choice.replace("_", " ").capitalize()))
        combo.connect("changed", lambda c: c.get_active_id() and self.changed(path, c.get_active_id()))
        self.controls[path] = (combo, kind)
        return combo

    def _theme_rows(self, grid: Gtk.Grid, row: int) -> int:
        head = Gtk.Label(xalign=0)
        head.set_markup("<b>Theme</b>")
        grid.attach(head, 0, row, 2, 1)
        self.theme_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.theme_list.connect("row-selected", self.on_theme_selected)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, min_content_height=150,
                                      max_content_height=260, propagate_natural_height=True)
        scroller.get_style_context().add_class("frame")
        scroller.add(self.theme_list)
        grid.attach(scroller, 0, row + 1, 2, 1)
        buttons = Gtk.Box(spacing=6)
        self.save_btn = Gtk.Button(label="Save Theme…")
        self.save_btn.set_tooltip_text("Keep your Custom settings as a theme with its own name")
        self.save_btn.connect("clicked", self.on_save_theme)
        self.delete_btn = Gtk.Button(label="Delete Theme")
        self.delete_btn.connect("clicked", self.on_delete_theme)
        buttons.pack_start(self.save_btn, False, False, 0)
        buttons.pack_start(self.delete_btn, False, False, 0)
        grid.attach(buttons, 0, row + 2, 2, 1)
        sep = Gtk.Separator(margin_top=6, margin_bottom=6)
        grid.attach(sep, 0, row + 3, 2, 1)
        return row + 4

    def _row(self, title: str, subtitle: str = "", tag: str = "") -> Gtk.ListBoxRow:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=8)
        top = Gtk.Box(spacing=8)
        name = Gtk.Label(xalign=0)
        name.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        top.pack_start(name, False, False, 0)
        if tag:
            t = Gtk.Label(label=tag)
            t.get_style_context().add_class("dim-label")
            top.pack_start(t, False, False, 0)
        box.pack_start(top, False, False, 0)
        if subtitle:
            sub = Gtk.Label(label=subtitle, xalign=0, wrap=True)
            sub.get_style_context().add_class("dim-label")
            box.pack_start(sub, False, False, 0)
        r = Gtk.ListBoxRow()
        r.add(box)
        return r

    def fill_theme_list(self) -> None:
        self.syncing = True
        for r in self.theme_list.get_children():
            self.theme_list.remove(r)
        for name, _f, builtin in themes.list_themes():
            r = self._row(name, tag="" if builtin else "Your theme")
            r.theme_name, r.builtin = name, builtin
            self.theme_list.add(r)
        r = self._row(themes.CUSTOM, "Your latest changes")
        r.theme_name, r.builtin = themes.CUSTOM, False
        self.theme_list.add(r)
        self.theme_list.show_all()
        self.syncing = False

    def _style_rows(self, grid: Gtk.Grid, row: int) -> int:
        self.style_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        builtin_dir = (paths.data_dir() / "styles").resolve()
        seen = set()
        for base in paths.style_dirs():
            if not base.is_dir():
                continue
            for d in sorted(base.iterdir()):
                try:
                    st = styles.load(d)
                except (styles.StyleError, OSError):
                    continue
                if st.name in seen:
                    continue
                seen.add(st.name)
                yours = builtin_dir not in d.resolve().parents and d.resolve().parent != builtin_dir
                r = self._row(st.name, st.description or "", "Your style" if yours else "")
                r.style_name = st.name
                self.style_list.add(r)
        self.style_list.connect("row-selected", self.on_style_selected)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, min_content_height=150,
                                      max_content_height=320, propagate_natural_height=True)
        scroller.get_style_context().add_class("frame")
        scroller.add(self.style_list)
        grid.attach(scroller, 0, row, 2, 1)
        return row + 1

    def _terminal_picks(self, grid: Gtk.Grid, row: int) -> int:
        combo = Gtk.ComboBoxText()
        combo.append("default", "Theme default")
        for f in sorted((paths.builtin_presets_dir() / "terminal").glob("*.json")):
            combo.append(str(f), json.loads(f.read_text(encoding="utf-8")).get("name", f.stem))
        self.term_combo = combo

        def picked(c: Gtk.ComboBoxText) -> None:
            if self.syncing or not c.get_active_id():
                return
            if c.get_active_id() == "default":
                self.reset_section("terminal")
            else:
                preset = json.loads(Path(c.get_active_id()).read_text(encoding="utf-8"))
                for key in ("bg", "text"):
                    _set(self.data, ("terminal", key), preset["terminal"][key])
                self.data["terminal"]["separate_colors"] = True
                self.after_change()
        combo.connect("changed", picked)
        grid.attach(Gtk.Label(label="Colors", xalign=0), 0, row, 1, 1)
        grid.attach(combo, 1, row, 1, 1)
        return row + 1

    def _flatpak_row(self, grid: Gtk.Grid, row: int) -> int:
        box = Gtk.Box(spacing=6)
        allow = Gtk.Button(label="Let Flatpak apps see the theme…")
        undo = Gtk.Button(label="Undo")
        allow.connect("clicked", self.on_flatpak_allow)
        undo.connect("clicked", self.on_flatpak_undo)
        box.pack_start(allow, False, False, 0)
        box.pack_start(undo, False, False, 0)
        if not flatpak.available():
            allow.set_sensitive(False)
            undo.set_sensitive(False)
            allow.set_tooltip_text("Flatpak isn't installed")
        note = Gtk.Label(label="Flatpak apps get your colors (libadwaita keeps its own shapes there).",
                         xalign=0, wrap=True)
        note.get_style_context().add_class("dim-label")
        grid.attach(Gtk.Label(label="Flatpak", xalign=0), 0, row, 1, 1)
        grid.attach(box, 1, row, 1, 1)
        grid.attach(note, 1, row + 1, 1, 1)
        return row + 2

    def _share_tab(self, grid: Gtk.Grid) -> Gtk.Grid:
        text = Gtk.Label(xalign=0, wrap=True, max_width_chars=60)
        text.set_text("Share a theme as one file (.xltheme). It holds every setting, the theme's name, "
                      "the version of xl-Cheeselooks it was made with, and your style when the theme "
                      "uses one of your own, so the person importing it gets exactly your look.")
        grid.attach(text, 0, 0, 2, 1)
        export = Gtk.Button(label="Export the current theme…", halign=Gtk.Align.START)
        export.connect("clicked", self.on_export)
        imp = Gtk.Button(label="Import a theme…", halign=Gtk.Align.START)
        imp.connect("clicked", self.on_import)
        grid.attach(export, 0, 1, 2, 1)
        grid.attach(imp, 0, 2, 2, 1)
        return grid

    # --------------------------------------------------------------- preview
    def _preview(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=10)
        outer.set_size_request(460, -1)
        frame = Gtk.Frame()
        frame.get_style_context().add_class("xl-prev-window")
        win = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hb = Gtk.HeaderBar(show_close_button=True, title="Preview")
        self.prev_hb = hb
        hb.get_style_context().add_class("titlebar")
        win.pack_start(hb, False, False, 0)
        menubar = Gtk.MenuBar()
        for name in ("File", "Edit", "View"):
            item = Gtk.MenuItem(label=name)
            sub = Gtk.Menu()
            for entry in ("Open", "Save", "Quit"):
                sub.append(Gtk.MenuItem(label=entry))
            item.set_submenu(sub)
            menubar.append(item)
        win.pack_start(menubar, False, False, 0)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=10)
        buttons = Gtk.Box(spacing=6)
        for label, cls in (("Button", None), ("Suggested", "suggested-action"), ("Delete", "destructive-action")):
            b = Gtk.Button(label=label)
            if cls:
                b.get_style_context().add_class(cls)
            buttons.pack_start(b, False, False, 0)
        buttons.pack_start(Gtk.ToggleButton(label="Toggled", active=True), False, False, 0)
        body.pack_start(buttons, False, False, 0)
        linked = Gtk.Box()
        linked.get_style_context().add_class("linked")
        for i, label in enumerate(("Left", "Center", "Right")):
            linked.pack_start(Gtk.ToggleButton(label=label, active=(i == 1)), False, False, 0)
        row = Gtk.Box(spacing=10)
        row.pack_start(linked, False, False, 0)
        row.pack_start(Gtk.Switch(active=True, valign=Gtk.Align.CENTER), False, False, 0)
        row.pack_start(Gtk.CheckButton(label="Check", active=True), False, False, 0)
        row.pack_start(Gtk.RadioButton(label="Radio"), False, False, 0)
        body.pack_start(row, False, False, 0)
        body.pack_start(Gtk.Entry(text="Some text"), False, False, 0)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_value(60)
        scale.set_draw_value(False)
        body.pack_start(scale, False, False, 0)
        notebook = Gtk.Notebook()
        for name in ("General", "Colors", "Advanced"):
            lb = Gtk.ListBox()
            for text in ("First row", "Selected row", "Third row"):
                lb.add(Gtk.Label(label=text, xalign=0, margin=6))
            lb.select_row(lb.get_row_at_index(1))
            notebook.append_page(lb, Gtk.Label(label=name))
        body.pack_start(notebook, False, False, 0)
        term = Gtk.Label(label="user@mint:~$ ls\nDesktop  Documents  Music", xalign=0, margin=6)
        term.get_style_context().add_class("xl-prev-terminal")
        body.pack_start(term, False, False, 0)
        win.pack_start(body, False, False, 0)
        frame.add(win)
        outer.pack_start(frame, False, False, 0)
        panel = Gtk.Box(spacing=2)
        panel.get_style_context().add_class("xl-prev-panel")
        for i, name in enumerate(("Terminal", "Files", "Browser")):
            b = Gtk.ToggleButton(label=name)
            b.get_style_context().add_class("xl-prev-pb")
            if i == 1:
                b.get_style_context().add_class("focused")
            panel.pack_start(b, False, False, 0)
        panel.pack_end(Gtk.Label(label="12:00", margin_end=8), False, False, 0)
        caption = Gtk.Label(label="Panel (drawn preview)", xalign=0)
        caption.get_style_context().add_class("dim-label")
        outer.pack_start(caption, False, False, 0)
        outer.pack_start(panel, False, False, 0)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add(outer)
        return scroller

    def _extra_css(self, t: dict[str, str]) -> str:
        """The drawn panel and the terminal sample, from the same tokens."""
        pb = "panel.w.panel_button."
        kind = t.get(pb + "active_marker", "none")
        marker = "none"
        if kind != "none":     # the focused window's marker, as the real panel draws it
            color = t["panel.accent_press"] if t[pb + "selected_color"] == t["panel.accent"] else t["panel.accent"]
            marker = panelmarker.shadow(kind, color, 28)
        return f"""
.xl-prev-panel {{ background-color: rgba({t['panel.panel_rgb']}, {t['panel.opacity']});
  background-image: linear-gradient(to bottom, rgba({t['panel.panel_top_rgb']}, {t['panel.opacity']}),
  rgba({t['panel.panel_bottom_rgb']}, {t['panel.opacity']}));
  border-top: 1px solid {t['panel.border']}; padding: 3px 4px; color: {t['panel.text']}; }}
.xl-prev-panel label {{ color: {t['panel.text']}; font-weight: {t['panel.label_weight']}; }}
button.xl-prev-pb {{ min-height: 26px; padding: 0 {t[pb + 'padding']}px; margin-right: {t[pb + 'spacing']}px;
  border: 1px solid {t[pb + 'border']}; border-radius: {t['panel.r']}px;
  background-color: {t[pb + 'color']};
  background-image: linear-gradient(to bottom, {t[pb + 'color_top']}, {t[pb + 'color_bottom']});
  box-shadow: none; }}
button.xl-prev-pb:hover {{ border-color: {t[pb + 'hover_border']}; background-color: {t[pb + 'hover_color']};
  background-image: linear-gradient(to bottom, {t[pb + 'hover_top']}, {t[pb + 'hover_bottom']}); }}
button.xl-prev-pb.focused {{ border-color: {t[pb + 'selected_border']}; background-color: {t[pb + 'selected_color']};
  background-image: linear-gradient(to bottom, {t[pb + 'selected_top']}, {t[pb + 'selected_bottom']});
  box-shadow: {marker}; }}
button.xl-prev-pb.focused label {{ color: {t[pb + 'selected_fg']}; font-weight: bold; }}
headerbar button.xl-drawn {{ border-color: {t['wbp.w.button.border']}; background-color: {t['wbp.button']};
  background-image: {t['wbp.button_grad']}; box-shadow: {t['wbp.w.button.shadow']}; }}
headerbar button.xl-drawn:hover {{ border-color: {t['wbp.w.button.hover_border']};
  background-color: {t['wbp.w.button.hover_color']}; background-image: {t['wbp.w.button.hover_grad']};
  box-shadow: {t['wbp.w.button.hover_shadow']}; }}
headerbar button.xl-drawn:active {{ border-color: {t['wbp.w.button.pressed_border']};
  background-color: {t['wbp.pressed']}; background-image: image({t['wbp.pressed']});
  box-shadow: {t['wbp.w.button.pressed_shadow']}; }}
frame.xl-prev-window > border {{ border: {t['wb.border_width']}px solid {t['wb.border']};
  border-radius: {t['r2']}px {t['r2']}px 0 0; }}
.xl-prev-terminal {{ font-family: monospace; color: {t['term.text']}; background-color: {t['term.bg']}; padding: 6px; }}
"""

    def update_preview(self) -> bool:
        self.pending = 0
        try:
            style = cli._load_style(self.data["style"]["name"], None)
            t = tokens.build(self.data, style)
        except (styles.StyleError, settings.SettingsError, KeyError) as exc:
            self.status.set_text(f"Can't preview: {exc}")
            return False
        if self.preview_dir.exists():
            shutil.rmtree(self.preview_dir)
        render.render_tree(paths.templates_dir(), self.preview_dir, t)
        # the preview's title bar shows all three buttons, on your side
        left = self.data["window_borders"]["button_layout"] == "left"
        self.prev_hb.set_decoration_layout("close,minimize,maximize:" if left else ":minimize,maximize,close")
        try:
            self.theme_css.load_from_path(str(self.preview_dir / "gtk-3.0" / "gtk.css"))
            self.extra_css.load_from_data(self._extra_css(t).encode())
        except GLib.Error as exc:
            self.status.set_text(f"Preview CSS problem: {exc.message}")
        if self.data["theme"] == themes.CUSTOM:
            themes.save_custom(self.data, self.base)
        return False

    # ---------------------------------------------------------------- state
    def base_settings(self) -> dict:
        if self.base not in self.base_cache:
            try:
                self.base_cache[self.base] = themes.load(self.base)
            except themes.ThemeError:
                self.base_cache[self.base] = themes.load(settings.DEFAULTS["theme"])
        return self.base_cache[self.base]

    def changed(self, path: tuple[str, ...], value: Any) -> None:
        if self.syncing:
            return
        _set(self.data, path, value)
        if path == ("window_borders", "button_style"):
            # a new style starts at its own roundness
            self.data["window_borders"]["button_roundness"] = None
        parent = _get(self.data, path[:-1])
        for gate, on in GATES.items():       # changing a setting turns its hidden switch on
            if gate in parent and path[-1] != gate:
                parent[gate] = on
        self.after_change()

    def after_change(self) -> None:
        try:
            self.data = settings.from_dict(self.data)
        except settings.SettingsError as exc:
            self.status.set_text("; ".join(exc.problems))
            return
        # unchanged from the theme it started from: still that theme; else Custom
        self.data["theme"] = self.base if _same(self.data, self.base_settings()) else themes.CUSTOM
        self.sync_controls()
        self.update_buttons()
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = GLib.timeout_add(PREVIEW_DELAY_MS, self.update_preview)

    def sync_controls(self) -> None:
        """Show self.data in every control (without triggering changes)."""
        self.syncing = True
        try:
            g = self.data["global"]
            theme = pal.derive(g["accent"], g["bg"], g["text"])
            for path, (widget, kind) in self.controls.items():
                value = _get(self.data, path)
                if kind in ("color", "color?"):
                    button, label = widget
                    shown = value or self._effective_color(path, theme)
                    button.set_rgba(_rgba(shown))
                    if value is None and kind == "color?":
                        label.set_text("Follow theme")
                    else:
                        r, gg, b = pal.to_rgb(shown)
                        label.set_text(f"{shown}   rgb({r}, {gg}, {b})")
                elif kind == "int":
                    widget.set_value(value)
                elif kind == "int?":   # button roundness: None shows the style's own
                    wb = self.data["window_borders"]
                    widget.set_value(titlebuttons.roundness(wb["button_style"], value,
                                                            self.data["global"]["roundness"]))
                elif kind == "bool":
                    widget.set_active(value)
                elif kind == "inline":
                    for choice, b in widget.items():
                        b.set_active(choice == value)
                else:
                    widget.set_active_id(value)
            for r in self.theme_list.get_children():
                if r.theme_name == self.data["theme"]:
                    self.theme_list.select_row(r)
            for r in self.style_list.get_children():
                if r.style_name == self.data["style"]["name"]:
                    self.style_list.select_row(r)
            if not self.data["terminal"]["separate_colors"]:
                self.term_combo.set_active_id("default")
        finally:
            self.syncing = False

    def _effective_color(self, path: tuple[str, ...], theme: dict[str, str]) -> str:
        name = path[-1]
        if name == "title_bar":
            return theme["header"]
        if name == "bg":
            return theme["base"] if path[0] == "terminal" else theme["bg"]
        if name in ("text", "title_text"):
            return theme["text"]
        if name == "border":
            return theme["border_strong"]
        if path[:2] == ("details", "tooltips"):
            return theme["menu_bg"] if name == "bg" else theme["text"]
        return theme["accent"]

    def update_buttons(self) -> None:
        self.apply_btn.set_sensitive(not _same(self.data, self.applied) or self.data["theme"] != self.applied["theme"])
        self.save_btn.set_sensitive(self.data["theme"] == themes.CUSTOM)
        row = self.theme_list.get_selected_row()
        self.delete_btn.set_sensitive(bool(row) and not row.builtin and row.theme_name != themes.CUSTOM)

    # -------------------------------------------------------------- actions
    def on_theme_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if self.syncing or row is None or row.theme_name == self.data["theme"]:
            self.update_buttons()
            return
        try:
            data = themes.load(row.theme_name)
        except themes.ThemeError as exc:
            self.status.set_text(str(exc))
            self.sync_controls()
            return
        if row.theme_name == themes.CUSTOM:
            self.base = themes.based_on() or self.base
        else:
            self.base = row.theme_name
            self.base_cache.pop(self.base, None)
        self.data = data
        self.status.set_text(f"Theme: {row.theme_name}")
        self.after_change()

    def on_style_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if self.syncing or row is None or row.style_name == self.data["style"]["name"]:
            return
        self.changed(("style", "name"), row.style_name)

    def reset_section(self, section: str) -> None:
        if section in ("share",):
            return
        self.data[section] = copy.deepcopy(self.base_settings()[section])
        self.status.set_text(f"{dict(TABS)[section]} reset to {self.base}.")
        self.after_change()

    def on_save_theme(self, _button: Gtk.Button) -> None:
        dialog = Gtk.Dialog(title="Save Theme", transient_for=self, modal=True)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        area.set_spacing(8)
        area.set_border_width(12)
        area.add(Gtk.Label(label="Name your theme. It uses the style "
                                 f"“{self.data['style']['name']}” and all your current settings.",
                           xalign=0, wrap=True, max_width_chars=50))
        entry = Gtk.Entry(activates_default=True, placeholder_text="My theme")
        area.add(entry)
        dialog.show_all()
        while dialog.run() == Gtk.ResponseType.OK:
            name = entry.get_text().strip()
            try:
                themes.save(name, self.data)
            except themes.ThemeError as exc:
                if "already have" in str(exc) and self._confirm(f"Replace your theme “{name}”?"):
                    themes.save(name, self.data, overwrite=True)
                else:
                    self.status.set_text(str(exc))
                    continue
            self.base = name
            self.base_cache.pop(name, None)
            self.data["theme"] = name
            self.fill_theme_list()
            self.after_change()
            self.status.set_text(f"Saved the theme “{name}”.")
            break
        dialog.destroy()

    def on_delete_theme(self, _button: Gtk.Button) -> None:
        row = self.theme_list.get_selected_row()
        if not row or row.builtin or row.theme_name == themes.CUSTOM:
            return
        if self._confirm(f"Delete your theme “{row.theme_name}”? Its style stays installed."):
            themes.delete(row.theme_name)
            if self.data["theme"] == row.theme_name:
                self.data["theme"] = themes.CUSTOM
            self.fill_theme_list()
            self.sync_controls()
            self.update_buttons()

    def _confirm(self, question: str) -> bool:
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.OK_CANCEL, text=question)
        answer = d.run()
        d.destroy()
        return answer == Gtk.ResponseType.OK

    def on_export(self, _button: Gtk.Button) -> None:
        name = self.data["theme"] if self.data["theme"] != themes.CUSTOM else "My theme"
        chooser = Gtk.FileChooserNative(title="Export theme", transient_for=self,
                                        action=Gtk.FileChooserAction.SAVE)
        chooser.set_current_name(f"{themes.slug(name)}{themes.EXTENSION}")
        chooser.set_do_overwrite_confirmation(True)
        if chooser.run() == Gtk.ResponseType.ACCEPT:
            dest = Path(chooser.get_filename())
            label = name if name != "My theme" else dest.stem.replace("-", " ").title()
            try:
                out = themes.export(label, self.data, dest)
                self.status.set_text(f"Exported “{label}” to {out}")
            except (themes.ThemeError, styles.StyleError, OSError) as exc:
                self.status.set_text(f"Export failed: {exc}")
        chooser.destroy()

    def on_import(self, _button: Gtk.Button) -> None:
        chooser = Gtk.FileChooserNative(title="Import theme", transient_for=self,
                                        action=Gtk.FileChooserAction.OPEN)
        f = Gtk.FileFilter()
        f.set_name("xl-Cheeselooks themes")
        f.add_pattern(f"*{themes.EXTENSION}")
        chooser.add_filter(f)
        if chooser.run() == Gtk.ResponseType.ACCEPT:
            try:
                name, notes = themes.import_file(Path(chooser.get_filename()))
                self.fill_theme_list()
                for r in self.theme_list.get_children():
                    if r.theme_name == name:
                        self.theme_list.select_row(r)       # loads it into the preview
                self.status.set_text(f"Imported “{name}”." + ("\n" + "\n".join(notes) if notes else ""))
            except (themes.ThemeError, OSError, ValueError) as exc:
                self.status.set_text(f"Import failed: {exc}")
        chooser.destroy()

    def on_apply(self, _button: Gtk.Button) -> None:
        self.apply_btn.set_sensitive(False)
        self.status.set_text("Applying… the desktop flickers once while it reloads.")
        data = copy.deepcopy(self.data)

        def work() -> None:
            try:
                style = cli._load_style(data["style"]["name"], None)
                # Apply means "use this theme": also switch to it if it isn't active yet
                log = cli.apply_to_desktop(data, style, activate=True)
                GLib.idle_add(self.applied_ok, data, log)
            except Exception as exc:  # report anything to the user
                GLib.idle_add(self.applied_failed, f"Apply failed: {exc}")
        threading.Thread(target=work, daemon=True).start()

    def applied_ok(self, data: dict, log: list[str]) -> bool:
        self.applied = data
        self.status.set_text(f"“{data['theme']}” is on the desktop. Revert puts the previous theme back.")
        self.revert_btn.set_sensitive(True)
        self.revert_btn.show()
        self.update_buttons()
        return False

    def applied_failed(self, message: str) -> bool:
        self.status.set_text(message)
        self.update_buttons()
        return False

    def on_revert(self, _button: Gtk.Button) -> None:
        self.revert_btn.set_sensitive(False)
        self.status.set_text("Reverting… the desktop flickers once while it reloads.")

        def work() -> None:
            try:
                restored, log = cli.revert_desktop()
                GLib.idle_add(self.reverted, restored, log)
            except Exception as exc:
                GLib.idle_add(self.applied_failed, f"Revert failed: {exc}")
        threading.Thread(target=work, daemon=True).start()

    def reverted(self, restored: dict | None, log: list[str]) -> bool:
        if restored:
            self.applied = restored
        self.revert_btn.hide()
        self.status.set_text("The previous theme is back on the desktop. Your settings here are unchanged.")
        self.update_buttons()
        return False

    def on_flatpak_allow(self, _button: Gtk.Button) -> None:
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text="Let Flatpak apps see the theme?")
        dialog.format_secondary_text(
            "This gives every Flatpak app read-only access to your themes folder and your "
            "GTK 4 colors. It runs:\n\n" + " ".join(flatpak.COMMAND) + "\n\nYou can undo it here.")
        answer = dialog.run()
        dialog.destroy()
        if answer == Gtk.ResponseType.OK:
            try:
                flatpak.enable()
                cli._set_flatpak_setting(True)
                self.status.set_text("Flatpak apps can see the theme. Restart any open Flatpak apps.")
            except RuntimeError as exc:
                self.status.set_text(f"Flatpak: {exc}")

    def on_flatpak_undo(self, _button: Gtk.Button) -> None:
        changed = flatpak.disable()
        cli._set_flatpak_setting(False)
        self.status.set_text("Removed xl-Cheeselooks' Flatpak access." if changed
                             else "Flatpak apps had no access from xl-Cheeselooks.")


class SettingsApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.xlcheese.Cheeselooks")

    def do_activate(self) -> None:
        win = self.props.active_window or SettingsWindow(self)
        win.present()


def main() -> int:
    return SettingsApp().run([])
