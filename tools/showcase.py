#!/usr/bin/env python3
"""Preview windows for checking the GTK 3 theme.

Shows a Nemo-like window (menubar, toolbar, path bar, sidebar, icon view,
status bar) and a headerbar window with common widgets. Run it with the
theme you want to see:

    GTK_THEME=xl-Cheeselooks python3 tools/showcase.py

Options:
    --menu      also open the View menu with an item highlighted
    --quit N    close after N seconds (for screenshots)
"""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402


def icon_button(name: str, tooltip: str = "", toggle: bool = False, active: bool = False) -> Gtk.Button:
    btn = Gtk.ToggleButton() if toggle else Gtk.Button()
    btn.set_image(Gtk.Image.new_from_icon_name(name, Gtk.IconSize.BUTTON))
    btn.set_relief(Gtk.ReliefStyle.NONE)
    if toggle:
        btn.set_active(active)
    if tooltip:
        btn.set_tooltip_text(tooltip)
    return btn


def files_window() -> tuple[Gtk.Window, Gtk.MenuItem]:
    win = Gtk.Window(title="Home")
    win.set_default_size(760, 540)
    win.move(10, 10)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    win.add(box)

    # menubar
    menubar = Gtk.MenuBar()
    view_item = None
    for label in ("File", "Edit", "View", "Go", "Bookmarks", "Help"):
        item = Gtk.MenuItem(label=label)
        menu = Gtk.Menu()
        if label == "View":
            view_item = item
            for entry in ("Reload", "Show Hidden Files", None, "Icons", "List", "Compact", None,
                          "Zoom In", "Zoom Out"):
                if entry is None:
                    menu.append(Gtk.SeparatorMenuItem())
                elif entry == "Show Hidden Files":
                    menu.append(Gtk.CheckMenuItem(label=entry, active=True))
                else:
                    menu.append(Gtk.MenuItem(label=entry))
        else:
            menu.append(Gtk.MenuItem(label="Example"))
        menu.show_all()
        item.set_submenu(menu)
        menubar.append(item)
    box.pack_start(menubar, False, False, 0)

    # toolbar (Nemo uses a primary-toolbar)
    toolbar = Gtk.Box(spacing=6)
    toolbar.get_style_context().add_class("primary-toolbar")
    toolbar.get_style_context().add_class("toolbar")
    toolbar.set_border_width(6)
    for name in ("go-previous-symbolic", "go-next-symbolic", "go-up-symbolic"):
        toolbar.pack_start(icon_button(name), False, False, 0)
    path = Gtk.Box()
    path.get_style_context().add_class("linked")
    for i, (label, icon) in enumerate((("wes", "user-home-symbolic"), ("Downloads", "folder-download-symbolic"))):
        b = Gtk.ToggleButton(label=label, active=(i == 0))
        b.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
        b.set_always_show_image(True)
        path.pack_start(b, False, False, 0)
    toolbar.pack_start(path, False, False, 6)
    for name, active in (("view-list-symbolic", False), ("view-grid-symbolic", True), ("edit-find-symbolic", False)):
        toolbar.pack_end(icon_button(name, toggle=True, active=active), False, False, 0)
    box.pack_start(toolbar, False, False, 0)

    paned = Gtk.Paned()
    sidebar = Gtk.PlacesSidebar()
    sidebar.set_size_request(190, -1)
    paned.pack1(sidebar, False, False)

    store = Gtk.ListStore(str, str)
    for name in ("anaconda3", "Desktop", "Documents", "Downloads", "Dropbox", "logs", "Music",
                 "Pictures", "Public", "Templates", "Videos", "VirtualBox VMs"):
        store.append([name, "folder"])
    icons = Gtk.IconView(model=store)
    icons.set_text_column(0)
    icons.set_pixbuf_column(-1)
    cell = Gtk.CellRendererPixbuf(icon_name="folder", stock_size=Gtk.IconSize.DIALOG)
    icons.pack_start(cell, False)
    icons.reorder(cell, 0)
    icons.set_item_width(90)
    icons.select_path(Gtk.TreePath.new_from_string("3"))
    scroll = Gtk.ScrolledWindow()
    scroll.add(icons)
    paned.pack2(scroll, True, False)
    box.pack_start(paned, True, True, 0)

    status = Gtk.Box(spacing=8)
    status.set_border_width(4)
    status.pack_start(Gtk.Label(label='"Downloads" selected (containing 875 items), Free space: 108.8 GB'),
                      True, True, 0)
    zoom = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
    zoom.set_value(60)
    zoom.set_draw_value(False)
    zoom.set_size_request(110, -1)
    status.pack_end(zoom, False, False, 0)
    box.pack_end(status, False, False, 0)
    box.pack_end(Gtk.Separator(), False, False, 0)
    return win, view_item


def widgets_window() -> Gtk.Window:
    win = Gtk.Window()
    win.set_default_size(450, 560)
    win.move(790, 10)
    hb = Gtk.HeaderBar(title="Appearance", show_close_button=True)
    hb.set_decoration_layout("menu:minimize,maximize,close")
    hb.pack_start(icon_button("go-previous-symbolic"))
    win.set_titlebar(hb)

    nb = Gtk.Notebook()
    grid = Gtk.Grid(row_spacing=12, column_spacing=12)
    grid.set_border_width(14)
    row = 0

    def add(label: str, widget: Gtk.Widget) -> None:
        nonlocal row
        lbl = Gtk.Label(label=label, xalign=0)
        grid.attach(lbl, 0, row, 1, 1)
        widget.set_halign(Gtk.Align.END)
        grid.attach(widget, 1, row, 1, 1)
        row += 1

    sw_on, sw_off = Gtk.Switch(active=True), Gtk.Switch(active=False)
    add("Show desktop icons", sw_on)
    add("Snap windows to edges", sw_off)

    checks = Gtk.Box(spacing=14)
    checks.pack_start(Gtk.CheckButton(label="Animations", active=True), False, False, 0)
    checks.pack_start(Gtk.CheckButton(label="Tooltips"), False, False, 0)
    mixed = Gtk.CheckButton(label="Mixed")
    mixed.set_inconsistent(True)
    checks.pack_start(mixed, False, False, 0)
    grid.attach(checks, 0, row, 2, 1)
    row += 1

    radios = Gtk.Box(spacing=14)
    r1 = Gtk.RadioButton(label="Light")
    radios.pack_start(r1, False, False, 0)
    radios.pack_start(Gtk.RadioButton(label="Dark", group=r1), False, False, 0)
    radios.pack_start(Gtk.RadioButton(label="Auto", group=r1), False, False, 0)
    grid.attach(radios, 0, row, 2, 1)
    row += 1

    entry = Gtk.Entry(text="xl-Cheeselooks")
    entry.set_hexpand(True)
    grid.attach(entry, 0, row, 2, 1)
    row += 1
    search = Gtk.SearchEntry(placeholder_text="Search…")
    grid.attach(search, 0, row, 1, 1)
    combo = Gtk.ComboBoxText()
    for item in ("Coral", "Coral Night", "Sea Glass"):
        combo.append_text(item)
    combo.set_active(0)
    grid.attach(combo, 1, row, 1, 1)
    row += 1

    spin = Gtk.SpinButton.new_with_range(0, 100, 1)
    spin.set_value(42)
    add("Spin", spin)
    progress = Gtk.ProgressBar(fraction=0.62)
    grid.attach(progress, 0, row, 2, 1)
    row += 1
    scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
    scale.set_value(40)
    scale.set_draw_value(False)
    grid.attach(scale, 0, row, 2, 1)
    row += 1

    buttons = Gtk.Box(spacing=6)
    for label, cls in (("Button", None), ("Suggested", "suggested-action"), ("Delete", "destructive-action")):
        b = Gtk.Button(label=label)
        if cls:
            b.get_style_context().add_class(cls)
        buttons.pack_start(b, False, False, 0)
    toggled = Gtk.ToggleButton(label="Toggled", active=True)
    buttons.pack_start(toggled, False, False, 0)
    off = Gtk.Button(label="Off", sensitive=False)
    buttons.pack_start(off, False, False, 0)
    grid.attach(buttons, 0, row, 2, 1)
    row += 1

    linked = Gtk.Box()
    linked.get_style_context().add_class("linked")
    for i, label in enumerate(("Left", "Center", "Right")):
        linked.pack_start(Gtk.ToggleButton(label=label, active=(i == 1)), False, False, 0)
    grid.attach(linked, 0, row, 2, 1)
    row += 1

    lb = Gtk.ListBox()
    for text in ("First row", "Selected row", "Third row"):
        r = Gtk.ListBoxRow()
        r.add(Gtk.Label(label=text, xalign=0, margin=6))
        lb.add(r)
    lb.select_row(lb.get_row_at_index(1))
    frame = Gtk.Frame()
    frame.add(lb)
    grid.attach(frame, 0, row, 2, 1)

    nb.append_page(grid, Gtk.Label(label="General"))
    nb.append_page(Gtk.Label(label="Colors"), Gtk.Label(label="Colors"))
    nb.append_page(Gtk.Label(label="Advanced"), Gtk.Label(label="Advanced"))
    win.add(nb)
    entry.grab_focus()
    return win


def main() -> int:
    args = sys.argv[1:]
    files, view_item = files_window()
    widgets = widgets_window()
    for w in (files, widgets):
        w.connect("destroy", Gtk.main_quit)
        w.show_all()

    if "--menu" in args:
        def open_menu() -> bool:
            menu = view_item.get_submenu()
            menu.popup_at_widget(view_item, 8, 1, None)  # GDK_GRAVITY_SOUTH_WEST, NORTH_WEST
            children = [c for c in menu.get_children() if not isinstance(c, Gtk.SeparatorMenuItem)]
            menu.select_item(children[2])
            return False
        GLib.timeout_add(600, open_menu)
    if "--quit" in args:
        seconds = float(args[args.index("--quit") + 1])
        GLib.timeout_add(int(seconds * 1000), Gtk.main_quit)
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
