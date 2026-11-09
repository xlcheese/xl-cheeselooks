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

## Requirements
Linux Mint 22.x with Cinnamon 6.x. No extra packages: everything uses the Python 3 and GTK that Mint already ships.

## Credits
- Built on [Linux Mint](https://github.com/linuxmint/mint-themes)'s Mint-Y and Mint-X themes.
- Inspired by GNOME's Clearlooks theme and the GNOME Color Chooser.

## License
[GPL-3.0](LICENSE)
