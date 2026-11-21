#!/usr/bin/env python3
"""Draw a title bar the way Cinnamon's window manager (Muffin 6, Mint 22) does.

Muffin no longer reads metacity-1 themes: it draws window borders from the GTK 3
theme's CSS, with style contexts it builds itself (src/ui/theme.c):

    window.background.ssd > decoration > headerbar.titlebar.horizontal.default-decoration
        > label.title,  > button.titlebutton.{close,maximize,minimize} > image

It lays the buttons out itself (min size + padding + border of the button, plus
the image's padding, border and margin; the buttons' margins and a fixed 6px
between them), draws only the button's background and frame (the image node is
never drawn), and draws the icon theme's window-*-symbolic icon at 16px in the
button's colour on top. This script copies that, so themes can be checked
without logging in to Cinnamon.

Usage: tools/muffin-preview.py THEME_DIR OUT.png [--width 360] [--scale 1]
Draws four rows: focused, focused with the pointer on maximize, pressed close,
and unfocused (backdrop).
"""
import argparse
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Gio, GLib  # noqa: E402
import cairo  # noqa: E402

ICON = 16                       # META_MINI_ICON_WIDTH
SPACING = 6                     # titlebar_spacing, hardcoded


def context(parent, gtype, name, *classes, provider):
    path = parent.get_path().copy() if parent else Gtk.WidgetPath()
    path.append_type(gtype)
    path.iter_set_object_name(-1, name)
    for c in classes:
        path.iter_add_class(-1, c)
    ctx = Gtk.StyleContext()
    ctx.set_path(path)
    if parent:
        ctx.set_parent(parent)
    ctx.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_SETTINGS)
    return ctx


def border_of(ctx):
    st = ctx.get_state()
    p, b = ctx.get_padding(st), ctx.get_border(st)
    return (p.left + b.left, p.right + b.right, p.top + b.top, p.bottom + b.bottom)


def min_size(ctx):
    st = ctx.get_state()
    return ctx.get_property("min-width", st), ctx.get_property("min-height", st)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("theme")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=360)
    ap.add_argument("--layout", default=":minimize,maximize,close")
    ap.add_argument("--title", default="Window title")
    ap.add_argument("--maximized", action="store_true")
    a = ap.parse_args()

    provider = Gtk.CssProvider()
    provider.load_from_path(f"{a.theme}/gtk-3.0/gtk.css")

    def build(backdrop):
        win = context(None, Gtk.Window, "window", "background", "ssd",
                      *(["maximized"] if a.maximized else []), provider=provider)
        frame = context(win, Gtk.Window, "decoration", provider=provider)
        bar = context(frame, Gtk.HeaderBar, "headerbar", "titlebar", "horizontal", "default-decoration",
                      provider=provider)
        title = context(bar, Gtk.Label, "label", "title", provider=provider)
        button = context(bar, Gtk.Button, "button", "titlebutton", provider=provider)
        image = context(button, Gtk.Image, "image", provider=provider)
        if backdrop:
            for c in (win, frame, bar, title, button, image):
                c.set_state(Gtk.StateFlags.BACKDROP)
        return win, frame, bar, title, button, image

    rows = [("rest", None, False), ("hover", "maximize", False), ("pressed", "close", False),
            ("backdrop", None, True)]
    images = []
    for _name, hot, backdrop in rows:
        win, frame, bar, title, button, image = build(backdrop)
        fb = border_of(frame)
        tb = border_of(bar)
        bb = list(border_of(button))
        ib = border_of(image)
        imgm = image.get_margin(image.get_state())
        bb = [bb[0] + ib[0] + imgm.left, bb[1] + ib[1] + imgm.right,
              bb[2] + ib[2] + imgm.top, bb[3] + ib[3] + imgm.bottom]
        bmin = list(min_size(button))
        imin = min_size(image)
        bmin = [max(bmin[0], imin[0]), max(bmin[1], imin[1])]
        bm = button.get_margin(button.get_state())
        tm = title.get_margin(title.get_state())
        bw = max(ICON, bmin[0]) + bb[0] + bb[1]
        bh = max(ICON, bmin[1]) + bb[2] + bb[3]
        buttons_h = bh + bm.top + bm.bottom
        # title text height
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
        layout = Gtk.Label().create_pango_layout(a.title)
        layout.set_font_description(title.get_property("font", title.get_state()))
        text_h = tm.top + layout.get_pixel_size()[1] + tm.bottom
        content_h = max(max(buttons_h, text_h), min_size(bar)[1]) + tb[2] + tb[3]
        top = fb[2] + content_h
        W, H = a.width, top + 30          # some window below, to show the frame's sides and bottom
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        cr = cairo.Context(surf)
        Gtk.render_background(frame, cr, 0, 0, W, H)
        Gtk.render_frame(frame, cr, 0, 0, W, H)
        # with compositing, Muffin keeps only what the frame's and title bar's
        # backgrounds cover (frames.c, meta_ui_frame_get_mask): the rest of the
        # frame shows as see-through, here as a checker
        mask = cairo.ImageSurface(cairo.FORMAT_A8, W, H)
        mc = cairo.Context(mask)
        Gtk.render_background(frame, mc, 0, 0, W, H)
        Gtk.render_background(bar, mc, 0, 0, W, fb[2] + (top - fb[2]))
        checker = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
        cc = cairo.Context(checker)
        for yy in range(0, H, 4):
            for xx in range(0, W, 4):
                v = 0.55 if (xx // 4 + yy // 4) % 2 else 0.8
                cc.set_source_rgb(v, v, v)
                cc.rectangle(xx, yy, 4, 4)
                cc.fill()
        cr.save()
        cr.set_operator(cairo.OPERATOR_DEST_IN)
        cr.mask_surface(mask, 0, 0)
        cr.restore()
        cr.set_operator(cairo.OPERATOR_DEST_OVER)
        cr.set_source_surface(checker, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgb(1, 1, 1)                                     # the window's contents
        cr.rectangle(fb[0], top, W - fb[0] - fb[1], H - top - fb[3])
        cr.fill()
        # the title bar over the frame's top, full width (muffin theme.c: titlebar_rect)
        tx, ty, tw, th = 0, 0, W, top
        Gtk.render_background(bar, cr, tx, ty, tw, th)
        Gtk.render_frame(bar, cr, tx, ty, tw, th)
        # content: inside the title bar's padding and border
        cx0, cx1 = tx + tb[0], tx + tw - tb[1]
        cy, ch = ty + tb[2], th - tb[2] - tb[3]
        by = cy + (ch - bh) // 2
        left, right = (s.split(",") if s else [] for s in a.layout.split(":"))
        rects = {}
        x = cx1
        for fn in reversed([f for f in right if f]):
            x -= bm.right
            rects[fn] = (x - bw, by, bw, bh)
            x = x - bw - bm.left - SPACING
        x = cx0
        for fn in [f for f in left if f]:
            x += bm.left
            rects[fn] = (x, by, bw, bh)
            x = x + bw + bm.right + SPACING
        theme = Gtk.IconTheme.get_default()
        for fn, (x, y, w, h) in rects.items():
            button.add_class(fn)
            st = button.get_state()
            if fn == hot:
                button.set_state(st | (Gtk.StateFlags.ACTIVE if _name == "pressed" else Gtk.StateFlags.PRELIGHT))
            Gtk.render_background(button, cr, x, y, w, h)
            Gtk.render_frame(button, cr, x, y, w, h)
            icon = {"close": "window-close-symbolic", "minimize": "window-minimize-symbolic",
                    "maximize": "window-restore-symbolic" if a.maximized else "window-maximize-symbolic"}[fn]
            info = theme.lookup_by_gicon_for_scale(Gio.ThemedIcon.new_with_default_fallbacks(icon), ICON, 1,
                                                   Gtk.IconLookupFlags.USE_BUILTIN)
            if info:
                pb = info.load_symbolic_for_context(button)[0] if info.is_symbolic() else info.load_icon()
                s = Gdk.cairo_surface_create_from_pixbuf(pb, 1, None)
                Gtk.render_icon_surface(button, cr, s, x + (w - ICON) / 2.0, y + (h - ICON) / 2.0)
            button.set_state(st)
            button.remove_class(fn)
        images.append(surf)
        sys.stderr.write(f"{_name}: button {bw}x{bh}, margin {bm.left}/{bm.right}, title bar {top}px, "
                         f"buttons at {sorted((r[0], r[0] + r[2]) for r in rects.values())}\n")
    W = a.width
    H = sum(s.get_height() for s in images)
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    cr = cairo.Context(out)
    y = 0
    for s in images:
        cr.set_source_surface(s, 0, y)
        cr.paint()
        y += s.get_height()
    out.write_to_png(a.out)


if __name__ == "__main__":
    main()
