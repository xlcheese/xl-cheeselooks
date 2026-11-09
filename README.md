# xl-Cheeselooks

A Linux Mint Cinnamon theme you style yourself. Pick an **accent**, a **background** and a **text** color, set size, roundness, gradient and a few other sliders, click **Apply**, and the whole desktop restyles itself in about a second: the panel, menus, GTK apps, window borders and the terminal.

It's a throwback to GNOME 2's Clearlooks and its Color Chooser, rebuilt for today's Cinnamon and GTK 3.

> **Status: in development.** Nothing is installable yet. See the [design spec](docs/design-spec.md) and the [interactive mockup](mockup/index.html) (download and open it in a browser).

## Planned for v1
- **Global:** three colors make a complete light *or* dark theme; size, roundness, gradient, hover in/out timing.
- **Style:** how edges are drawn (borders, highlights, shadows), with a Depth slider. Ships with the *xl-Cheeselooks* style; users can write their own.
- **Panel & Menu:** optional separate colors and shape for the panel and its menus, with presets.
- **Window Borders:** title bar colors, height, border thickness, button layout.
- **Terminal:** follows the theme, or its own colors.
- **Details:** tooltips, scrollbars, sliders, switches, focus ring.
- libadwaita color and accent integration, Flatpak access, presets, and a `cheeselooks` command.

## Trying it (early testers)
**GTK 3 apps work now** (Nemo, Xed, settings windows and so on). The Cinnamon panel, menus and window borders come next. On Linux Mint 22, from a checkout of this repository:

```bash
./bin/cheeselooks apply --activate
```

That writes `~/.themes/xl-Cheeselooks`, switches your apps to it and saves your settings to `~/.config/xl-cheeselooks/settings.json`. Change colors with presets (stack as many as you like), or edit that settings file and run `apply` again:

```bash
./bin/cheeselooks apply --preset "Coral Night"
```

```bash
./bin/cheeselooks presets
```

To go back to what you had before the last apply:

```bash
./bin/cheeselooks revert
```

To go back to Mint's own theme, pick it again in **System Settings → Themes**.

Preview without touching your desktop (opens two sample windows):

```bash
./bin/cheeselooks apply --theme-dir /tmp/xl-Cheeselooks --no-save
```

```bash
GTK_THEME=xl-Cheeselooks XDG_DATA_HOME=/tmp/xlc python3 tools/showcase.py
```

(For the second command, first run `mkdir -p /tmp/xlc/themes && ln -s /tmp/xl-Cheeselooks /tmp/xlc/themes/`.)

### Developers
- Tests: `python3 -m unittest discover tests`
- Every computed value: `./bin/cheeselooks tokens [filter]`
- Check a style file: `./bin/cheeselooks check-style PATH`
- Screenshots on a virtual display: `tools/preview.sh THEME_DIR out.png` (needs Xvfb and ImageMagick)

## Requirements
Linux Mint 22.x with Cinnamon 6.x. No extra packages: everything uses the Python 3 and GTK that Mint already ships.

## Credits
- Built on [Linux Mint](https://github.com/linuxmint/mint-themes)'s Mint-Y and Mint-X themes.
- Inspired by GNOME's Clearlooks theme and the GNOME Color Chooser.

## License
[GPL-3.0](LICENSE)
