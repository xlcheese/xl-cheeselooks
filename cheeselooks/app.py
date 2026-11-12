"""The xl-Cheeselooks settings app (GTK 3).

Every control edits the settings in memory. The window itself is the preview:
after each change the theme is generated into a cache folder and its GTK 3
stylesheet is loaded into this app only, so the buttons, tabs, sliders and
pickers you are using show the result straight away, with a drawn panel and a
title bar for the parts GTK can't show. Nothing reaches the desktop until
Apply (the same as `cheeselooks apply`); Revert drops the changes made since.

Most controls are generated from settings._RULES, the table that also
validates settings.json, so every setting has a control with the right type
and range.
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

from . import cli, flatpak, palette as pal, paths, render, settings, styles, tokens  # noqa: E402

APP_TITLE = "xl-Cheeselooks"
PREVIEW_DELAY_MS = 120

TABS = [  # (settings section, tab title)
    ("global", "Global"), ("style", "Style"), ("panel", "Panel & Menu"),
    ("window_borders", "Window Borders"), ("terminal", "Terminal"),
    ("details", "Details"), ("integration", "Integration"),
]
PRESET_SECTIONS = {"global": "global", "panel": "panel", "terminal": "terminal"}

LABELS = {
    "accent": "Accent", "bg": "Background", "text": "Text", "size": "Size",
    "roundness": "Roundness", "gradient": "Gradient", "hover_in_ms": "Hover in (ms)",
    "hover_out_ms": "Hover out (ms)", "hover_strength": "Hover strength", "depth": "Depth",
    "separate_colors": "Own colours", "label_weight": "Label weight",
    "panel_opacity": "Panel opacity", "menu_opacity": "Menu opacity",
    "follow_global": "Follow Global", "title_bar": "Title bar", "title_text": "Title text",
    "border": "Border", "title_bar_height": "Title bar height", "border_width": "Border width",
    "title_gradient": "Title bar gradient", "button_layout": "Button layout",
    "button_style": "Button style", "custom": "Customise", "mode": "Mode", "color": "Colour",
    "width": "Width", "libadwaita_colors": "Colours for libadwaita apps",
    "libadwaita_accent": "GNOME accent colour", "flatpak_access": "Flatpak apps",
}
GROUPS = {"panel_shape": "Panel shape", "menu_shape": "Menu shape", "tooltips": "Tooltips",
          "scrollbars": "Scrollbars", "sliders": "Sliders", "switches": "Switches",
          "focus_ring": "Focus ring"}
GATES = ("separate_colors", "custom", "follow_global")   # bools that switch their siblings


def _hex(rgba: Gdk.RGBA) -> str:
    return "#{:02X}{:02X}{:02X}".format(round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255))


def _rgba(hex_color: str) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(hex_color)
    return c


def _get(data: dict, path: tuple[str, ...]) -> Any:
    for k in path:
        data = data[k]
    return data


def _set(data: dict, path: tuple[str, ...], value: Any) -> None:
    for k in path[:-1]:
        data = data[k]
    data[path[-1]] = value


class SettingsWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title=APP_TITLE)
        self.set_default_size(1180, 720)
        self.saved = settings.load(paths.settings_file())
        self.data = copy.deepcopy(self.saved)
        self.controls: dict[tuple[str, ...], tuple[Gtk.Widget, str]] = {}
        self.syncing = False
        self.pending = 0
        self.preview_dir = paths.HOME / ".cache" / "xl-cheeselooks" / "preview"
        self.theme_css = Gtk.CssProvider()
        self.extra_css = Gtk.CssProvider()
        screen = Gdk.Screen.get_default()
        Gtk.StyleContext.add_provider_for_screen(screen, self.theme_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Gtk.StyleContext.add_provider_for_screen(screen, self.extra_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

        header = Gtk.HeaderBar(show_close_button=True, title=APP_TITLE)
        header.set_subtitle("Preview — nothing changes on the desktop until Apply")
        self.apply_btn = Gtk.Button(label="Apply")
        self.apply_btn.get_style_context().add_class("suggested-action")
        self.apply_btn.connect("clicked", self.on_apply)
        self.revert_btn = Gtk.Button(label="Revert")
        self.revert_btn.set_tooltip_text("Drop the changes made since the last Apply")
        self.revert_btn.connect("clicked", self.on_revert)
        header.pack_end(self.apply_btn)
        header.pack_end(self.revert_btn)
        self.set_titlebar(header)
        self.header = header

        # the tabs as a sidebar list (seven don't fit across the top), as
        # Cinnamon's own settings windows do
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        for section, title in TABS:
            self.stack.add_titled(self._tab(section), section, title)
        sidebar = Gtk.StackSidebar(stack=self.stack)
        sidebar.set_size_request(150, -1)
        self.status = Gtk.Label(xalign=0, selectable=True, wrap=True)
        self.status.get_style_context().add_class("dim-label")
        pages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        pages.pack_start(self.stack, True, True, 0)
        pages.pack_start(self.status, False, False, 6)
        left = Gtk.Box()
        left.pack_start(sidebar, False, False, 0)
        left.pack_start(pages, True, True, 0)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.pack1(left, resize=True, shrink=False)
        paned.pack2(self._preview(), resize=False, shrink=False)
        paned.set_position(600)
        self.add(paned)
        self.sync_controls()
        self.update_preview()
        self.update_buttons()
        self.show_all()

    # ------------------------------------------------------------------ tabs
    def _tab(self, section: str) -> Gtk.Widget:
        grid = Gtk.Grid(column_spacing=12, row_spacing=8, margin=12)
        row = 0
        if section in PRESET_SECTIONS:
            row = self._preset_row(grid, row, PRESET_SECTIONS[section])
        if section == "style":
            row = self._style_rows(grid, row)
        group = None
        for path, kind, extra in settings._RULES:
            if path[0] != section:
                continue
            if len(path) == 3 and path[1] != group:
                group = path[1]
                head = Gtk.Label(xalign=0, margin_top=8)
                head.set_markup(f"<b>{GLib.markup_escape_text(GROUPS.get(group, group))}</b>")
                grid.attach(head, 0, row, 2, 1)
                row += 1
            label = Gtk.Label(label=LABELS.get(path[-1], path[-1].replace("_", " ").capitalize()), xalign=0)
            widget = self._control(path, kind, extra)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
            row += 1
        if section == "integration":
            row = self._flatpak_row(grid, row)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroller.add(grid)
        return scroller

    def _control(self, path: tuple[str, ...], kind: str, extra: Any) -> Gtk.Widget:
        if kind in ("color", "color?"):
            box = Gtk.Box(spacing=6)
            button = Gtk.ColorButton(use_alpha=False)
            button.connect("color-set", lambda b: self.changed(path, _hex(b.get_rgba())))
            box.pack_start(button, False, False, 0)
            if kind == "color?":
                reset = Gtk.Button(label="Follow theme")
                reset.get_style_context().add_class("flat")
                reset.connect("clicked", lambda _b: self.changed(path, None))
                box.pack_start(reset, False, False, 0)
            self.controls[path] = (button, kind)
            return box
        if kind == "int":
            lo, hi = extra
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
            scale.set_digits(0)
            scale.set_hexpand(True)
            scale.set_size_request(240, -1)
            scale.connect("value-changed", lambda s: self.changed(path, int(round(s.get_value()))))
            self.controls[path] = (scale, kind)
            return scale
        if kind == "bool":
            switch = Gtk.Switch(halign=Gtk.Align.START)
            switch.connect("notify::active", lambda s, _p: self.changed(path, s.get_active()))
            self.controls[path] = (switch, kind)
            return switch
        combo = Gtk.ComboBoxText()
        for choice in extra:
            combo.append(choice, choice.replace("_", " ").capitalize())
        combo.connect("changed", lambda c: c.get_active_id() and self.changed(path, c.get_active_id()))
        self.controls[path] = (combo, kind)
        return combo

    def _preset_row(self, grid: Gtk.Grid, row: int, section: str) -> int:
        combo = Gtk.ComboBoxText()
        combo.append("", "Choose a preset…")
        for f in cli.preset_files():
            data = json.loads(f.read_text(encoding="utf-8"))
            if section in data:
                combo.append(str(f), data.get("name", f.stem))
        combo.set_active_id("")

        def picked(c: Gtk.ComboBoxText) -> None:
            if c.get_active_id():
                preset = json.loads(Path(c.get_active_id()).read_text(encoding="utf-8"))
                self.data = settings.apply_preset(self.data, preset)
                self.after_change()
                c.set_active_id("")
        combo.connect("changed", picked)
        grid.attach(Gtk.Label(label="Preset", xalign=0), 0, row, 1, 1)
        grid.attach(combo, 1, row, 1, 1)
        return row + 1

    def _style_rows(self, grid: Gtk.Grid, row: int) -> int:
        self.style_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.style_list.get_style_context().add_class("frame")
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
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=8)
                name = Gtk.Label(xalign=0)
                name.set_markup(f"<b>{GLib.markup_escape_text(st.name)}</b>")
                desc = Gtk.Label(label=st.description or "", xalign=0, wrap=True)
                desc.get_style_context().add_class("dim-label")
                box.pack_start(name, False, False, 0)
                box.pack_start(desc, False, False, 0)
                r = Gtk.ListBoxRow()
                r.add(box)
                r.style_name = st.name
                self.style_list.add(r)
        self.style_list.connect("row-selected", self.on_style_selected)
        grid.attach(self.style_list, 0, row, 2, 1)
        reset = Gtk.Button(label="Reset to style defaults")
        reset.set_tooltip_text("Roundness, gradient, depth and the panel and menu shape from the style")
        reset.connect("clicked", lambda _b: self.reset_style_defaults())
        grid.attach(reset, 0, row + 1, 2, 1)
        return row + 2

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
        note = Gtk.Label(label="Flatpak apps get your colours (libadwaita keeps its own shapes there).",
                         xalign=0, wrap=True)
        note.get_style_context().add_class("dim-label")
        grid.attach(Gtk.Label(label="Flatpak", xalign=0), 0, row, 1, 1)
        grid.attach(box, 1, row, 1, 1)
        grid.attach(note, 1, row + 1, 1, 1)
        return row + 2

    # --------------------------------------------------------------- preview
    def _preview(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=10)
        outer.set_size_request(440, -1)

        # a window: title bar, menubar, content
        frame = Gtk.Frame()
        win = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hb = Gtk.HeaderBar(show_close_button=True, title="Preview")
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
        toggle = Gtk.ToggleButton(label="Toggled", active=True)
        buttons.pack_start(toggle, False, False, 0)
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

        entry = Gtk.Entry(text="Some text")
        body.pack_start(entry, False, False, 0)
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_value(60)
        scale.set_draw_value(False)
        body.pack_start(scale, False, False, 0)

        notebook = Gtk.Notebook()
        for name in ("General", "Colours", "Advanced"):
            lb = Gtk.ListBox()
            for i, text in enumerate(("First row", "Selected row", "Third row")):
                lb.add(Gtk.Label(label=text, xalign=0, margin=6))
            lb.select_row(lb.get_row_at_index(1))
            notebook.append_page(lb, Gtk.Label(label=name))
        body.pack_start(notebook, False, False, 0)

        term = Gtk.Label(label="wes@daddy:~$ ls\nDesktop  Documents  Music", xalign=0, margin=6)
        term.get_style_context().add_class("xl-prev-terminal")
        body.pack_start(term, False, False, 0)
        win.pack_start(body, False, False, 0)
        frame.add(win)
        outer.pack_start(frame, False, False, 0)

        # a panel strip (drawn: Cinnamon's panel can't be shown in a GTK window)
        panel = Gtk.Box(spacing=2)
        panel.get_style_context().add_class("xl-prev-panel")
        for i, name in enumerate(("Terminal", "Files", "Browser")):
            b = Gtk.ToggleButton(label=name)
            b.get_style_context().add_class("xl-prev-pb")
            if i == 1:
                b.get_style_context().add_class("focused")
            panel.pack_start(b, False, False, 0)
        clock = Gtk.Label(label="12:00", margin_end=8)
        panel.pack_end(clock, False, False, 0)
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
  background-image: linear-gradient(to bottom, {t[pb + 'selected_top']}, {t[pb + 'selected_bottom']}); }}
button.xl-prev-pb.focused label {{ color: {t[pb + 'selected_fg']}; font-weight: bold; }}
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
        try:
            self.theme_css.load_from_path(str(self.preview_dir / "gtk-3.0" / "gtk.css"))
            self.extra_css.load_from_data(self._extra_css(t).encode())
        except GLib.Error as exc:
            self.status.set_text(f"Preview CSS problem: {exc.message}")
        return False

    # ---------------------------------------------------------------- state
    def changed(self, path: tuple[str, ...], value: Any) -> None:
        if self.syncing:
            return
        _set(self.data, path, value)
        self.after_change()

    def after_change(self) -> None:
        try:
            self.data = settings.from_dict(self.data)
        except settings.SettingsError as exc:
            self.status.set_text("; ".join(exc.problems))
            return
        self.sync_controls()
        self.update_buttons()
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = GLib.timeout_add(PREVIEW_DELAY_MS, self.update_preview)

    def sync_controls(self) -> None:
        """Show self.data in every control (without triggering changes)."""
        self.syncing = True
        try:
            theme = pal.derive(self.data["global"]["accent"], self.data["global"]["bg"], self.data["global"]["text"])
            for path, (widget, kind) in self.controls.items():
                value = _get(self.data, path)
                if kind in ("color", "color?"):
                    widget.set_rgba(_rgba(value or self._effective_color(path, theme)))
                elif kind == "int":
                    widget.set_value(value)
                elif kind == "bool":
                    widget.set_active(value)
                else:
                    widget.set_active_id(value)
                gate = self._gate(path)
                if gate is not None:
                    widget.get_parent().set_sensitive(gate) if kind in ("color", "color?") else widget.set_sensitive(gate)
            if hasattr(self, "style_list"):
                for r in self.style_list.get_children():
                    if r.style_name == self.data["style"]["name"]:
                        self.style_list.select_row(r)
        finally:
            self.syncing = False

    def _gate(self, path: tuple[str, ...]) -> bool | None:
        """Whether a control is in use: siblings of separate_colors / custom are
        live when it's on; siblings of follow_global when it's off."""
        parent = _get(self.data, path[:-1])
        for g in GATES:
            if g in parent and path[-1] != g:
                return (not parent[g]) if g == "follow_global" else bool(parent[g])
        return None

    def _effective_color(self, path: tuple[str, ...], theme: dict[str, str]) -> str:
        name = path[-1]
        if name in ("bg", "title_bar"):
            return theme["header"] if name == "title_bar" else theme["bg"]
        if name in ("text", "title_text"):
            return theme["text"]
        if name == "border":
            return theme["border_strong"]
        return theme["accent"]

    def update_buttons(self) -> None:
        dirty = self.data != self.saved
        self.apply_btn.set_sensitive(dirty)
        self.revert_btn.set_sensitive(dirty)

    # -------------------------------------------------------------- actions
    def on_style_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if self.syncing or row is None or row.style_name == self.data["style"]["name"]:
            return
        self.data["style"]["name"] = row.style_name
        self.reset_style_defaults()

    def reset_style_defaults(self) -> None:
        try:
            style = cli._load_style(self.data["style"]["name"], None)
        except styles.StyleError as exc:
            self.status.set_text("; ".join(exc.problems))
            return
        self.data = settings.apply_style_defaults(self.data, style.defaults)
        self.after_change()

    def on_revert(self, _button: Gtk.Button) -> None:
        self.data = copy.deepcopy(self.saved)
        self.after_change()
        self.status.set_text("Reverted to the last applied settings.")

    def on_apply(self, _button: Gtk.Button) -> None:
        self.apply_btn.set_sensitive(False)
        self.status.set_text("Applying… the desktop flickers once while it reloads.")
        data = copy.deepcopy(self.data)

        def work() -> None:
            try:
                style = cli._load_style(data["style"]["name"], None)
                # Apply means "use this theme": also switch to it if it isn't active yet
                log = cli.apply_to_desktop(data, style, activate=True)
                GLib.idle_add(self.applied, data, "\n".join(log[:4]))
            except Exception as exc:  # report anything to the user
                GLib.idle_add(self.applied, None, f"Apply failed: {exc}")
        threading.Thread(target=work, daemon=True).start()

    def applied(self, data: dict | None, message: str) -> bool:
        if data is not None:
            self.saved = data
        self.status.set_text(message)
        self.update_buttons()
        return False

    def on_flatpak_allow(self, _button: Gtk.Button) -> None:
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text="Let Flatpak apps see the theme?")
        dialog.format_secondary_text(
            "This gives every Flatpak app read-only access to your themes folder and your "
            "GTK 4 colours. It runs:\n\n" + " ".join(flatpak.COMMAND) + "\n\nYou can undo it here.")
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
