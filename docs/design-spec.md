# xl-Cheeselooks: Design Spec

**Status:** Draft 2 · 9 Nov 2026
**Visual reference:** [`mockup/index.html`](../mockup/index.html) (open it in a browser), version 4. Where the mockup and this spec disagree, this spec wins. The known differences are listed in [§15](#15-differences-from-mockup-v4).

---

## 1. What this is

xl-Cheeselooks is a Linux Mint Cinnamon theme that you style yourself. One installed theme, plus a small settings app. You pick three colors and a few shape settings, click **Apply**, and the whole desktop updates in about a second, with no logout and no second theme folder.

It brings back an idea from GNOME 2's Clearlooks and the GNOME Color Chooser, rebuilt for today's Cinnamon and GTK 3.

### Goals
- Three colors (**accent, background, text**) produce a complete, readable light **or** dark theme. Every other color is calculated from them.
- Size, roundness, gradient, depth and hover timing are sliders, not separate themes.
- The panel and menus, window borders and terminal can each follow the main colors or have their own.
- **Styles** decide how edges are drawn. The first style is **xl-Cheeselooks**, and users can write their own.
- Widgets are drawn with CSS wherever the toolkit allows. Images are used only where the toolkit forces them, and those are generated with the user's colors.

### Not in scope
- GTK 2 (Mint 22.3 ships no GTK 2 apps).
- Xfce and MATE (xfwm4 / Marco).
- Icon sets, cursors, the login screen (slick-greeter), Qt and Electron apps. Icons are a planned later tab ([§13](#13-roadmap)).
- Copying existing themes. Styles are original, with their own names.

### Target platform
| | Version | Notes |
|---|---|---|
| Linux Mint | 22.x (22.3 primary) | |
| Cinnamon | 6.x | Shell CSS (St) |
| Muffin | 6.x | Uses `metacity-1/metacity-theme-3.xml` for window borders |
| GTK 3 | 3.24 | Full theme |
| GTK 4 / libadwaita | 4.14+ / 1.5+ | **Colors only**, through `~/.config/gtk-4.0/gtk.css` |
| Python | 3.12 (ships with Mint 22) | Generator and app. Standard library plus PyGObject, nothing to install |

---

## 2. How it works

```
 Settings app (GTK 3)                       Generator (Python)
 ┌──────────────────────┐   settings.json   ┌───────────────────────────────┐
 │ Global · Style ·     │ ────────────────▶ │ 1. palette  = derive(colors)  │
 │ Panel & Menu ·       │                   │ 2. shape    = sizes, radii…   │
 │ Window Borders ·     │                   │ 3. edges    = style recipe    │
 │ Terminal · (Icons)   │                   │ 4. fill templates → files     │
 └──────────────────────┘                   │ 5. reload Cinnamon + apps     │
                                            └───────────────┬───────────────┘
                                                            ▼
                                 ~/.themes/xl-Cheeselooks/  (rewritten in place)
```

- **Settings** are saved in `~/.config/xl-cheeselooks/settings.json`.
- **The generator** reads the settings, computes every token (color, size, radius, shadow) and fills the templates. It also runs on its own as `cheeselooks apply`.
- **Templates** are the theme files with `{{token}}` placeholders. All math happens in Python, never in CSS. GTK supports `mix()`/`shade()` but Cinnamon doesn't, so one set of computed values serves both.
- **Apply = rewrite, then reload.** The theme folder name never changes. To make everything reload, the generator briefly switches each theme setting away and back:
  - `org.cinnamon.theme name` (Cinnamon shell)
  - `org.cinnamon.desktop.interface gtk-theme` (GTK apps)
  - `org.cinnamon.desktop.wm.preferences theme` (window borders)

  The user sees one short flicker. Running GTK 3 apps restyle themselves, while some apps (Firefox, Electron apps) only partly refresh until they're restarted.

### Settings model (defaults)

```jsonc
{
  "version": 1,
  "global":  { "accent": "#FA8562", "bg": "#F0F0F0", "text": "#303030",
               "size": "normal", "roundness": 20, "gradient": 30,
               "hover_in_ms": 60, "hover_out_ms": 250 },
  "style":   { "name": "xl-Cheeselooks", "depth": 50 },
  "panel":   { "separate_colors": false, "accent": null, "bg": null, "text": null,
               "panel_shape": { "follow_global": true, "roundness": 20, "gradient": 30 },
               "menu_shape":  { "follow_global": true, "roundness": 20, "gradient": 30 } },
  "window_borders": { "separate_colors": false, "title_bar": null, "title_text": null, "border": null,
                      "title_bar_height": 44, "border_width": 1,
                      "button_layout": "right", "button_style": "theme" },
  "terminal": { "separate_colors": false, "bg": null, "text": null },
  "details": {
    "tooltips":    { "custom": false, "bg": null, "text": null },
    "scrollbars":  { "custom": false, "mode": "overlay", "roundness": 100 },
    "sliders":     { "custom": false, "roundness": 100 },
    "switches":    { "custom": false, "roundness": 100 },
    "focus_ring":  { "custom": false, "color": null, "width": 2 }
  },
  "panel_label_weight": "bold",
  "integration": { "libadwaita_colors": true, "libadwaita_accent": true, "flatpak_access": false }
}
```

- `null` means "follow Global."
- Turning a "separate" switch on copies the current Global (or calculated) values in as a starting point.
- **Presets** are the same file format with only the keys they set. Global, Panel and Terminal each have their own list.

---

## 3. Color rules

Notation: `mix(a, b, t)` blends from color `a` toward color `b` by `t` (0–1). `lighter(c, t)` = `mix(c, white, t)`; `darker(c, t)` = `mix(c, black, t)`. **dark** means the background is darker than the text, which decides whether the theme is light or dark.

Each area (Global, Panel & Menu, Window Borders, Terminal) runs these rules on its own three colors.

| Token | Light theme | Dark theme | Used for |
|---|---|---|---|
| `accent` · `bg` · `text` | user | user | |
| `accent_fg` | white, or dark text if the accent is very light (luminance > 0.55) | same | Text and glyphs on accent |
| `select` | accent, darkened in 4% steps until white text reaches 2.6:1 (max 8 steps) | same | Selected rows, file labels, selected text |
| `accent_hover` / `accent_press` | `lighter(accent, .12)` / `darker(accent, .14)` | same | |
| `base` | `mix(bg, white, .75)` | `darker(bg, .18)` | Content areas: file view, entries, lists |
| `button` | `mix(bg, white, .60)` | `mix(bg, text, .08)` | Button face |
| `button_hover` | `lighter(button, .50)` | `mix(button, text, .06)` | |
| `header` | `mix(bg, text, .05)` | `mix(bg, text, .06)` | Menubar, toolbar, bottom of title bar |
| `menubar_hover` | `mix(header, text, .12)` | same | **New:** menubar item hover, a bit darker than general hover |
| `sidebar` | `mix(bg, text, .035)` | `mix(bg, text, .03)` | |
| `sidebar_hover` | `mix(bg, text, .14)` | `mix(bg, text, .13)` | |
| `hover` | `mix(bg, text, .07)` | `mix(bg, text, .08)` | General hover (file items, inactive tabs) |
| `pressed` | `mix(bg, text, .13)` | `mix(bg, text, .15)` | Toggled and pressed buttons, the current path button |
| `border` / `border_strong` | `mix(bg, text, .20 / .30)` | `mix(bg, text, .16 / .26)` | |
| `trough` | `mix(bg, text, .12)` | `mix(bg, text, .14)` | Switch, progress and scale troughs |
| `text_dim` | `mix(text, bg, .38)` | same | Secondary and placeholder text |
| `menu_bg` | `mix(bg, text, .03)` | `mix(bg, text, .04)` | Cinnamon menu and popups, GTK menus |
| `menu_hover` | `mix(menu_bg, text, .10)` | same | **All** menu item hovers (see below) |
| `fav_bg` / `fav_hover` | `mix(bg, text, .075)` / `mix(fav_bg, text, .10)` | `.09` / same step | Cinnamon menu favorites column |
| `panel` | `mix(bg, white, .25)` | `mix(bg, text, .03)` | Panel background, ~90% opaque |
| `pb_rest` | `mix(bg, text, .15)` | `mix(bg, text, .13)` | Running app button |
| `pb_hover` | `lighter(bg, .50)` | `mix(bg, text, .22)` | |
| `pb_focus` | accent | accent | Focused app button |
| `pb_progress` | `darker(accent, .25)` | same | Progress fill on panel buttons |
| `pb_attention` | `mix(bg, #E5534B, .36)` | `mix(bg, #E5534B, .50)` | App needs attention |

**Rule of matching steps:** wherever a hover sits on a section with its own background, the hover is that background plus the **same step** toward text. That's why `menu_hover` and `fav_hover` both use `+.10`, which keeps contrast equal across the Cinnamon menu's three columns. Categories and apps share one hover color.

**Menu item hover (style-dependent):** in xl-Cheeselooks, hovered items in GTK menus (menubar dropdowns, right-click menus) use `menu_hover`, a darker shade of the background, **not** the accent. Other styles may choose `select` instead ([§6](#6-styles)).

**Terminal (when following Global):** background = `base`, text = `text`, cursor = `accent`. The prompt color is the accent, darkened on light backgrounds and lightened on dark ones.

**Readability checks:** the app shows a warning, but never blocks, when:
- text on its background is below 4.5:1, for Global and for each area that has separate colors;
- the accent is below 1.5:1 against the background;
- `accent_fg` on `select` is below 2.5:1.

---

## 4. Shape rules

### Size (Global)
Size changes **spacing and control heights only**. Text size stays with Mint's Font settings.

| | Control height `ctl` | Row padding `pad` | Title glyph |
|---|---|---|---|
| Compact | 26 px | 3 px | 12 px |
| **Normal** | **30 px** | **4 px** | **14 px** |
| Large | 36 px | 6 px | 16 px |

The panel's height and icon sizes belong to Cinnamon's Panel settings, and the theme doesn't set them. Global Size affects the panel's **menus and popups** and the padding inside panel buttons.

### Roundness (0–100%)
A percentage of "fully round," so 100% gives pills at every size:
- controls: `r = round(pct × ctl / 2)`
- windows, menus and popovers: `r2 = min(14 px, round(r × 1.4))`
- panel buttons: `round(pct × panel_height / 2)` (panel height read from Cinnamon, default 40)
- switches: `round(pct × 12 px)`
- checkboxes: `min(r, 5 px)`; radios are always circles
- sidebar rows run **edge to edge (no side margin)** and still take `r`

### Gradient (0–100%), revised
One soft top-to-bottom shade, **skewed darker** so tops don't wash into light backgrounds:

```
gradient(c, g) = [ top: lighter(c, 0.10 × g),  bottom: darker(c, 0.20 × g) ]
```

The previous formula was `+30% / −10%`. The new one keeps the overall brightness close to the base color and gets its shape from a darker bottom.

**What gets a gradient:** buttons, the accent (suggested buttons, switches on, check/radio on, progress), selections, hover highlights (menu items, sidebar, file labels, Cinnamon menu, menubar items), the panel and panel buttons, and the **title bar**.

**What doesn't:** menubars, toolbars, content areas, entries, troughs.

**Title bar:** `[ top: lighter(header, 0.20 × g),  bottom: header ]`. Its bottom edge is exactly the menubar and toolbar color, so title bar, menubar and toolbar read as one block.

### Depth (0–100%, Style tab)
Multiplies the strength of the style's highlights and shadows. At 0 any style draws flat.

### Hover timing (Global)
| Setting | Range | Default |
|---|---|---|
| Hover in | 0–300 ms | 60 ms |
| Hover out | 0–800 ms | 250 ms |

The toolkits use the transition time of the state being **entered**:
- the hover rule carries **Hover in**
- the normal rule carries **Hover out**
- the pressed rule is always `0`, so clicks are instant

Easing is `ease-out` in GTK. Cinnamon supports a duration only. Transitions are skipped when the user turns animations off in Mint.

### Panel & Menu shape
Separate Roundness and Gradient for the **panel** and for its **menus** (main menu, applet popups, calendar, right-click menus). Each has a **Follow Global** switch, on by default.

---

## 5. Widget states (all styles)

| State | Rule |
|---|---|
| Normal | Style's resting edge |
| Hover | Hover color plus the style's hover edge; Hover in timing |
| Pressed / toggled | `pressed` color plus a sunken edge; instant |
| Selected | `select` with `accent_fg` text (rows, labels) |
| Focused (keyboard) | Visible focus ring: 2 px accent at 50% opacity by default, defined by the style, overridable on the Details tab; never removed |
| Disabled | 50% opacity text and edges, no shadow |
| Unfocused window | Title bar flat `bg` (or the area color mixed 50% with `bg`), dimmed title and glyphs; accent widgets keep their color |

**Title bar buttons** (minimize / maximize / close), for both window-manager title bars and GTK headerbars:
- **At rest:** no background, no border, no shadow, glyph only.
- **Hover:** the style's raised button, the same as a toolbar button on hover.
- **Pressed:** sunken.
- **Close on hover:** accent face with `accent_fg` glyph.
- **Size:** the same as toolbar buttons: `min(ctl, title_bar_height − 10)` tall, × 1.12 wide.

---

## 6. Styles

A style decides **how edges are drawn**. It never sets colors directly (it uses palette tokens), radius (Roundness), shading (Gradient) or timing (Hover).

### File format
TOML, which Python 3.11+ reads with no extra packages. Location:
- built-in: `<app>/styles/<name>/style.toml`
- user: `~/.local/share/xl-cheeselooks/styles/<name>/style.toml`, plus an optional `extra.css`

```toml
name = "xl-Cheeselooks"
author = "xl_cheese"
defaults = { roundness = 20, gradient = 30, depth = 50 }   # applied when the style is picked

[edges.raised]
border    = "border_strong"
highlight = { y = 1, color = "white", alpha = 0.60 }        # inset, top
shade     = { y = -1, color = "black", alpha = 0.07 }       # inset, bottom
shadow    = { y = 1, blur = 2, color = "black", alpha = 0.10 }

[edges.sunken]
border    = "border_strong"
inner     = { y = 1, blur = 2, color = "black", alpha = 0.10 }

[edges.flat]
border    = "none"

[widgets]
button          = { edge = "raised", pressed = "sunken" }
suggested       = { edge = "raised", border = "accent_press" }
toolbar_button  = { edge = "flat", hover = "raised", pressed = "sunken" }
title_button    = { like = "toolbar_button" }
entry           = { edge = "sunken", focus = "accent_ring" }
combo           = { like = "button" }
tab             = { kind = "boxed", active_marker = "none", hover_border = true }
menu_item       = { hover = "menu_hover" }        # "select" would use the accent instead
menubar_item    = { hover = "menubar_hover" }
panel_button    = { edge = "raised" }             # Cinnamon fallback: highlight only
```

- Alpha values are multiplied by **Depth**.
- Color names are palette tokens ([§3](#3-color-rules)), `white`/`black`, or `#RRGGBB` for authors who really want fixed colors.
- Any widget or state left out falls back to a built-in default, so a minimal style is about 30 lines.

### Cinnamon limits
Cinnamon's CSS allows **one** box shadow per widget and two-color gradients. When a style asks for more, the generator keeps layers in this order and drops the rest:

**highlight → drop shadow → shade**

### xl-Cheeselooks (default style, v1)
- **Buttons:** raised. 1px `border_strong`, top highlight, faint bottom shade, small drop shadow.
- **Toolbar and title buttons:** flat until hover, then raised.
- **Entries:** sunken, with a 1px accent ring and accent border on focus.
- **Tabs (in-app notebooks, not the settings app's own tabs):**
  - Active tab: `base` background with a `border_strong` border on top and sides. **No accent line.**
  - Inactive tabs: no border, `text_dim`.
  - Hovered inactive tab: `hover` background **and side and top borders** in `border`.
- **Menu items (GTK menus):** hover is `menu_hover`, not the accent.
- **Menubar items:** hover is `menubar_hover`. An open menubar item uses the same color.
- **Panel buttons:** full panel height, raised (highlight only in Cinnamon), running = `pb_rest`, focused = `pb_focus`.

### Float (example style, shipped in docs, not in the app for v1)
Borderless, with soft shadows. Suggested buttons cast a shadow **tinted with the accent**. Entries are borderless with a hairline outline and a 3px accent glow on focus. Tabs are pills in a trough. It exists to prove the format and to give authors a second starting point.

---

## 7. Area details

### Cinnamon panel
- Buttons fill the panel's full height; 3px gap between window-list buttons.
- States: running (`pb_rest`), hover (`pb_hover`), focused (accent, bold label, `accent_fg`), attention (`pb_attention`), progress (`pb_progress` fill from the left).
- Label weight: **Bold** (default, as in the current theme) or **Regular**, chosen on the Panel & Menu tab.
- Drawn entirely in CSS. The Mint-X `panel-assets/*.svg` images are retired.

### Cinnamon menu and popups
- Menu background `menu_bg` at ~98.5% opacity, `r2` corners, shadow.
- The favorites column uses `fav_bg` with `fav_hover`. Categories and apps both use `menu_hover`. The selected category uses `select` with `accent_fg`.
- The search entry uses the style's entry edge (focused look while the menu is open).
- The same rules cover the calendar, sound, network and right-click popups, plus notifications, OSD (volume and brightness) and the alt-tab switcher.

### GTK apps (Nemo and friends)
- **Stacking:** title bar (gradient) → menubar (flat `header`) → toolbar (flat `header`, bottom border).
- Path bar: one raised group, current folder `pressed`.
- Sidebar: `sidebar` background, rows edge to edge, `sidebar_hover`, selected `select`.
- File view: `base`, labels selected with `select`, item hover `hover`.

### Window borders
- **Title bar color:** follows `header`, or a user color.
- **Title text:** `text`, or a user color.
- **Border color and width:** 0–6 px, default 1. Visual only, since Muffin keeps its own invisible resize area.
- **Title bar height:** 30–56 px, default 44.
- **Button layout:** written to Mint's own setting (`org.cinnamon.desktop.wm.preferences button-layout`).
- **Implementation:** drawn by `metacity-theme-3.xml` draw operations (rectangles, lines, title) for traditional title bars, and by GTK CSS for headerbar apps. Both use the same tokens so they match.
- **Button styles:** v1 ships **Theme** only. Dots, Wide and Circles are planned ([§13](#13-roadmap)). Each must be drawn in both the XML and the CSS.
- Window shadows are drawn by Muffin and are out of the theme's reach.

### Terminal
- **Switch off:** follows the theme (light theme, light terminal).
- **Switch on:** the user's background and text, plus Terminal presets.
- **Implementation:** a `vte-terminal` rule in the GTK CSS. This only takes effect when the terminal profile uses system theme colors, which is GNOME Terminal's default on Mint. The README must say so.

### GTK 4 / libadwaita (colors only)
- The generator writes a **marked block** into `~/.config/gtk-4.0/gtk.css`, between `/* xl-cheeselooks begin */` and `/* xl-cheeselooks end */`. The libadwaita named colors go there as both `@define-color` and `:root` variables.
- Anything the user wrote outside the block is preserved. A backup is made the first time.
- An option in the app turns this off.
- **libadwaita accent:** the generator also sets GNOME's `accent-color` key (`org.gnome.desktop.interface`) to the named color nearest the user's accent (blue, teal, green, yellow, orange, red, pink, purple, slate). That gets libadwaita apps that ignore custom CSS close to the accent. It can be turned off in the app.

### Flatpak apps
- Flatpak apps can't see `~/.themes` by default. An opt-in button in the app grants read access to the theme folder for all Flatpak apps, one time. It shows the exact command before running it and offers to undo it. The command will be confirmed during the build.

### Details tab
Fine-grained overrides. Each row has its own switch. **Off** means the item follows the theme; **on** reveals its controls, pre-filled with the theme's current values.

| Item | Controls when switched on | Default when off |
|---|---|---|
| **Tooltips** | Background and text color pickers; presets *Follow menu* and *Classic yellow* (`#FBEAA0` / `#303030`) | Menu colors (`menu_bg`, `text`) |
| **Scrollbars** | *Thin overlay* or *Classic* switch; Roundness slider | Overlay, fully round thumb |
| **Sliders** (volume, zoom, brightness) | Roundness slider for the handle and track | Fully round, as in Mint-Y |
| **Switches** | Roundness slider | Fully round, as in Mint-Y |
| **Focus ring** | Color picker; width 1–3 px | Style's ring (accent at 50%, 2 px) |

Notes:
- Mint-Y keeps sliders, switches and scrollbars round even though the rest of the theme is nearly square. These overrides keep that look possible while Global Roundness is low.
- *Thin overlay* vs *Classic* is partly a Mint setting (the overlay scrollbars switch in Themes settings). The app sets that key and the theme styles both modes, so the two never disagree.
- Tooltips apply to both GTK apps and the Cinnamon shell (`#Tooltip`).

---

## 8. Drawn vs images

| Part | How it's drawn |
|---|---|
| Panel and window-list buttons | CSS |
| GTK buttons, entries, tabs, switches, check/radio boxes | CSS. Checkmark from GTK's recolorable built-in icon |
| Window title bar and buttons | Metacity draw ops (no images) |
| Cinnamon switches, checkboxes, radios | **Generated SVGs** (Cinnamon CSS can't draw a knob or check). Rewritten on every apply |
| Everything else | CSS |

No hand-made bitmap images remain in the theme.

---

## 9. Settings app

- A Python + GTK 3 app called **Cheeselooks Settings**, with a menu entry and the `cheeselooks-settings` command.
- **Tabs:** Global · Style · Panel & Menu · Window Borders · Terminal · Details · *Icons (later)*.
- **Accent from wallpaper:** a button on the Global tab reads the current wallpaper and offers 5–6 accent suggestions as swatches. One click applies one to the Accent picker (preview only until Apply). Implementation: downscale the image, cluster the colors, drop near-greys and colors too close to the background, and rank by how often they appear and how saturated they are. Python standard library plus GdkPixbuf only.
- **Live preview inside the app:** generated CSS loaded into a preview area. The desktop changes only on **Apply**.
- **Buttons:** **Apply**, **Revert** (restore the last applied settings), **Reset to defaults**.
- **Presets:** built-in Global, Panel and Terminal lists, plus **Save preset**, **Import** and **Export** (JSON).
- Readability warnings sit under the controls ([§3](#3-color-rules)).
- Same layout as the mockup. Controls that are off are greyed out with their following values shown.

### Command line
```
cheeselooks apply [--preset NAME | --settings FILE]
cheeselooks check-style PATH        # validate a style file, list problems
cheeselooks export-preset NAME
cheeselooks revert
```

### Safety
- Before writing, the generator renders to a temporary folder and checks that every file is complete. It aborts on any failure and leaves the current theme untouched.
- The last good theme is kept in `~/.cache/xl-cheeselooks/last-good/`. **Revert** restores it.
- If Cinnamon can't load the theme, it falls back to its default theme on its own, so the desktop never becomes unusable.

---

## 10. Files

### Repository
```
xl-cheeselooks/
├─ app/                    settings app (GTK 3, Python)
├─ generator/              palette.py, shape.py, styles.py, render.py, reload.py
├─ templates/
│  ├─ cinnamon/cinnamon.css.tmpl  (+ asset SVG templates)
│  ├─ gtk-3.0/gtk.css.tmpl
│  ├─ gtk-4.0/gtk.css.tmpl        (non-libadwaita GTK 4 apps)
│  ├─ gtk-4.0/libadwaita.css.tmpl (colors block)
│  ├─ metacity-1/metacity-theme-3.xml.tmpl
│  └─ index.theme.tmpl
├─ styles/xl-Cheeselooks/style.toml
├─ presets/                global/, panel/, terminal/
├─ docs/
│  ├─ design-spec.md       (this file)
│  ├─ creating-styles.md   (style author guide)
│  └─ examples/float/style.toml
├─ mockup/                 interactive mockup
├─ AGENTS.md / CLAUDE.md   points AI assistants at docs/creating-styles.md
├─ install.sh
├─ LICENSE                 GPL-3.0
└─ README.md
```

### Installed
```
~/.themes/xl-Cheeselooks/                 generated, rewritten on Apply
~/.config/xl-cheeselooks/settings.json
~/.config/xl-cheeselooks/presets/
~/.local/share/xl-cheeselooks/styles/     user styles
~/.cache/xl-cheeselooks/last-good/
```

### Starting material
| Template | Comes from |
|---|---|
| `gtk-3.0` / `gtk-4.0` | The current xl_cheese-Mint-Y-Variable files (Mint-Y based, coral already in place). Every hard-coded color, radius and shadow becomes a token, and the PNG check/radio/switch images are replaced with CSS |
| `cinnamon` | The current file (Mint-X based panel), with gaps filled from Mint-Y's Cinnamon CSS in the same style |
| `metacity` | Written new |

---

## 11. Credits and license
- GPL-3.0, the same as Mint-Y and Mint-X.
- Credits in the README and `index.theme`: Linux Mint (Mint-Y, Mint-X), the original Mint-X Cinnamon theme authors, and the GNOME Clearlooks / Color Chooser projects as inspiration.
- Built-in style and preset names are original.

---

## 12. Testing

**Before each release,** on Mint 22.3:
- Check the light defaults (Coral), one dark preset, and Anything goes at Compact and Large, 0% and 100% roundness, and 0% and 100% gradient.

**Apps to check:**
- Nemo (icon, list and compact views, sidebar, path bar, menubar)
- Xed, Xviewer, Mint Update Manager, System Settings
- GNOME Terminal, Firefox (GTK integration), Software Manager, LibreOffice
- One libadwaita app (e.g. Text Editor)

**Shell:**
- Panel at bottom, top and side; window list (grouped and classic); Cinnamon menu
- Calendar, sound and network applets; notifications; volume OSD; alt-tab; logout dialog

**Window borders:**
- Focused and unfocused, maximized, dialogs, button layout left and right

**Behavior:**
- Apply while apps are open
- Revert, and a broken user style (must abort cleanly)

**HiDPI:** 2× scaling.

---

## 13. Roadmap

| Phase | Contents |
|---|---|
| **v1** | Generator + templates; Global (colors, size, roundness, gradient, hover in/out); Style tab with **xl-Cheeselooks** and Depth; Panel & Menu (colors, panel shape, menu shape, label weight); Window Borders (colors, height, border width, layout, **Theme** buttons); Terminal; Details (tooltips, scrollbars, sliders, switches, focus ring); libadwaita colors and accent; Flatpak access button; presets; CLI; README; `creating-styles.md`; `AGENTS.md` |
| **v1.x** | Accent from wallpaper. Window button styles: Dots, Wide, Circles. Float shipped as a selectable style. Import/export polish |
| **v2** | Icons tab (recolor the user's Yaru-based folders with the accent); more original styles; in-app style editor |

---

## 14. Decisions log

| # | Idea | Decision |
|---|---|---|
| 1 | Scrollbar style and roundness | **Yes**, on the Details tab |
| 2 | Keyboard focus ring | **Yes**, defined by each style, overridable on Details |
| 3 | Tooltip colors | **Yes**, on Details, with *Classic yellow* preset |
| — | Slider and switch roundness | **Yes**, on Details (added 9 Nov) |
| 4 | Accent from wallpaper | **Yes**, v1.x |
| 5 | Readability auto-fix | Skipped |
| 6 | Day/night preset pair | Skipped (Qredshift covers evening tint) |
| 7 | Flatpak access button | **Yes**, v1 |
| 8 | libadwaita `accent-color` | **Yes**, v1 |
| 9 | Panel label weight | **Yes**, v1 (Bold / Regular) |
| 10 | Unfocused-window dimming slider | Skipped for now |

**Settled:** the tab is named **Details**. No open questions remain.

---

## 15. Differences from mockup v4

The mockup wasn't updated for the review on 9 Nov. These spec items replace what it shows:

1. Title bar buttons have **no background at rest**, only on hover or press ([§5](#5-widget-states-all-styles)).
2. Menubar item hover is darker: `menubar_hover` ([§3](#3-color-rules)).
3. GTK menu item hover uses `menu_hover` (darker background), not the accent, in xl-Cheeselooks ([§6](#6-styles)).
4. Gradient is skewed darker: `+10% / −20%`, and the title bar top is `+20%` ([§4](#4-shape-rules)).
5. Active tab has **no accent line**, and hovered inactive tabs show side and top borders ([§6](#6-styles)).
