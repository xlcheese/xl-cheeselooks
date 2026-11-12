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
  "global":  { "accent": "#FA8562", "bg": "#F5F5F5", "text": "#303030",
               "size": "normal", "roundness": 15, "gradient": 10,
               "hover_in_ms": 50, "hover_out_ms": 125, "hover_strength": 50 },
  "style":   { "name": "xl-Cheeselooks", "depth": 50 },
  "panel":   { "separate_colors": false, "accent": null, "bg": null, "text": null,
               "label_weight": "bold", "panel_opacity": 70, "menu_opacity": 94,
               "panel_shape": { "follow_global": true, "roundness": 15, "gradient": 10 },
               "menu_shape":  { "follow_global": true, "roundness": 15, "gradient": 10 } },
  "window_borders": { "separate_colors": false, "title_bar": null, "title_text": null, "border": null,
                      "title_bar_height": 44, "border_width": 1, "title_gradient": 30,
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
| `button` | `mix(bg, white, .30)` | `mix(bg, text, .08)` | Button face, a little below white so hover has room |
| `button_hover` | `lighter(button, .80 × h)`, or `mix(button, text, .05 × h)` if the button is already white | `mix(button, text, .06 × h)` | |
| `border_hover` | `mix(border_strong, text, .15 × h)` (darker) | same formula (lighter on dark) | Hovered button borders, as in Mint-Y |
| `header` | `mix(bg, text, .066)` | same | Menubar, toolbar, title bar (Mint-Y's `#E8E8E8` on the default colors) |
| `menubar_hover` | `mix(header, text, .09 × h)` | same | **New:** menubar item hover, a bit darker than general hover |
| `sidebar` | `mix(bg, text, .035)` | `mix(bg, text, .03)` | |
| `sidebar_hover` | `mix(bg, text, .14)` | `mix(bg, text, .13)` | |
| `hover` | `mix(bg, text, .07)` | `mix(bg, text, .08)` | General hover (file items, inactive tabs) |
| `pressed` | `mix(bg, text, .13)` | `mix(bg, text, .15)` | Toggled and pressed buttons, the current path button |
| `border` / `border_strong` | `mix(bg, text, .20 / .30)` | `mix(bg, text, .16 / .26)` | |
| `trough` | `mix(bg, text, .12)` | `mix(bg, text, .14)` | Switch, progress and scale troughs |
| `text_dim` | `mix(text, bg, .38)` | same | Secondary and placeholder text |
| `menu_bg` | `base` | `base` | GTK menus and popovers (near-white, as Mint-Y) |
| `shell_menu_bg` | `mix(bg, text, .03)` | `mix(bg, text, .04)` | Cinnamon menu and popups (used as `menu_bg` in the Cinnamon templates) |
| `flat_hover` | `lighter(header, .50 × h)` | `mix(header, text, .08 × h)` | Hover for buttons not drawn at rest (toolbar, title buttons) and unselected tabs: softer than a full button hover |
| `menu_hover` | `mix(menu_bg, text, .10 × h)` | same | Menu item hovers; `shell_menu_hover` is the same step on `shell_menu_bg` |
| `fav_bg` / `fav_hover` | `mix(bg, text, .075)` / `mix(fav_bg, text, .10)` | `.09` / same step | Cinnamon menu favorites column |
| `panel` | `mix(bg, white, .25)` | `mix(bg, text, .03)` | Panel background, ~90% opaque |
| `pb_rest` | `mix(bg, text, .15)` | `mix(bg, text, .13)` | Running app button |
| `pb_hover` | `lighter(bg, .50)` | `mix(bg, text, .22)` | |
| `pb_focus` | accent | accent | Focused app button |
| `pb_progress` | `darker(accent, .25)` | same | Progress fill on panel buttons |
| `pb_attention` | `mix(bg, #E5534B, .36)` | `mix(bg, #E5534B, .50)` | App needs attention |

**Hover strength (`h`):** the Global *Hover strength* slider (0–100, default 50) sets `h = value / 50 × 0.8`. The 0.8 calibrates the center (50) to the chosen default look (40 on the original scale); 100 gives 1.6. Every hover step in this table (button, menubar, sidebar, general hover, menu, favorites, panel button and hover borders) is multiplied by `h`, so all hovers get stronger or weaker together and stay balanced. Calibrated to xl_cheese's chosen strength in November 2026.

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

**Title bar:** `[ top: lighter(title, 1.00 × t),  bottom: title ]`, where `t` is the **Title bar gradient** slider on Window Borders (0–100, default 30), separate from Global Gradient so a contrasting title bar color can be tuned on its own. Its bottom edge is exactly the menubar and toolbar color, so title bar, menubar and toolbar read as one block.

### Depth (0–100%, Style tab)
Multiplies the strength of the style's highlights and shadows. At 0 any style draws flat.

### Hover timing (Global)
| Setting | Range | Default |
|---|---|---|
| Hover in | 0–300 ms | 50 ms |
| Hover out | 0–800 ms | 125 ms |

The toolkits use the transition time of the state being **entered**:
- the hover rule carries **Hover in**
- the normal rule carries **Hover out**
- the pressed rule is always `0`, so clicks are instant

Easing is `ease-out` in GTK. Cinnamon supports a duration only. Transitions are skipped when the user turns animations off in Mint.

### Panel & Menu opacity
Two sliders on the Panel & Menu tab, 30–100%: **Panel opacity** (default 70%) and **Menu opacity** (default 94%). Menu opacity also covers popups, notifications and OSDs. Cinnamon doesn't blur what's behind, so below 80% the app shows a readability note. GTK app windows stay opaque on purpose.

### Color formats in templates
Templates never contain literal colors. A solid color is `{{name}}` (hex); a color with opacity is `rgba({{name_rgb}}, alpha)`. When converting Mint-Y, **black with opacity** becomes the **text** color with that opacity, and **white with opacity** becomes the **background** color (or a style highlight), so they flip correctly in dark themes.

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
| Focused (keyboard) | Subtle by default, like Mint-Y: 1px dashed outline in the text color at 25%. GTK shows it only once the keyboard has been used in that window, then it follows mouse clicks too (CSS can't tell them apart). Details tab: your own color and width, or width 0 to turn it off |
| Disabled | 50% opacity text and edges, no shadow |
| Unfocused window | Title bar keeps its color with the gradient removed, so it still matches the menubar and toolbar; dimmed title and glyphs; accent widgets keep their color |

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
- built-in: `<app>/styles/<name>/style.toml` (one folder per style; the file is always `style.toml` and the folder name should match its `name =` line)
- user: `~/.local/share/xl-cheeselooks/styles/<name>/style.toml`, plus an optional `extra.css`

```toml
name = "xl-Cheeselooks"
[defaults]
roundness = 20
gradient = 30
depth = 50

[edges.raised]                                   # a named edge: border + layers
border    = "border_strong"
highlight = { y = 1,  color = "white", alpha = 0.60, alpha_dark = 0.07 }
shade     = { y = -1, color = "black", alpha = 0.07, alpha_dark = 0.20 }
shadow    = { y = 1, blur = 2, color = "black", alpha = 0.10, alpha_dark = 0.30 }

[edges.sunken]
border = "border_strong"
inner  = { y = 1, blur = 2, color = "black", alpha = 0.10, alpha_dark = 0.30 }

[widgets]                                        # which edge each widget uses, per state
button         = { edge = "raised", hover_edge = "raised", pressed_edge = "sunken", hover_color = "button_hover" }
toolbar_button = { edge = "flat", hover_edge = "raised", pressed_edge = "sunken" }
title_button   = { like = "toolbar_button" }
entry          = { edge = "sunken", focus_edge = "focus" }
tab            = { tab_kind = "boxed", active_marker = "none", hover_border = true }
menu_item      = { hover_color = "menu_hover" }  # "select" would use the accent instead
```

The full file is [`styles/xl-Cheeselooks/style.toml`](../styles/xl-Cheeselooks/style.toml); the Float example is in [`docs/examples/float/`](examples/float/style.toml).

- **Layers:** `highlight` (inside the top edge), `sides` (inside the left and right edges; `x` sets the width, default 1px), `left` and `right` (one side each, for bevels: light top and left, dark bottom and right), `shade`, `inner` (inset), `shadow` (outside), `ring` and `outline` (spread rings). `blur` on `highlight`, `shade`, `sides`, `left` and `right` fades the line inward over that many pixels instead of a crisp edge (0 = crisp). The generator keeps each fade on its own edge (it adds a negative spread equal to the blur and moves the offset out by the same amount), so a bottom shade doesn't glow up the sides. Cinnamon allows only one shadow per widget, so it never uses `sides`, `left` or `right`. Examples: `docs/examples/float/` and `docs/examples/bevel/`. Each takes `x`, `y`, `blur`, `spread`, `width`, `color`, `alpha`, optional `alpha_dark` for dark themes, and `grow = true` to make offset and blur grow with Depth.
- **Widgets:** `button`, `suggested`, `destructive`, `linked` (joined button groups: path bars, stack switchers, spin buttons; copies `button` unless set, and never gets a drop shadow), `toolbar_button`, `title_button`, `close_button`, `entry`, `combo`, `tab`, `menu_item`, `menubar_item`, `panel_button`, `check`, `switch`. Widget settings: `like`, `edge`, `hover_edge`, `pressed_edge`, `focus_edge`, `border`, `hover_color`, `tab_kind`, `active_marker`, `hover_fg`. Text on a hover face is picked for contrast (your text color or text-on-accent); `hover_fg` sets it instead, e.g. `menu_item = { hover_color = "accent_hover", hover_fg = "accent_fg" }` for white text on an accent hover (used by `menu_item`, `menubar_item` and `tab`; `panel_button` takes `selected_fg` the same way). A text color goes with its face: a widget that sets its own hover or selected color doesn't inherit the other widget's text color through `like`. `panel_button` also takes `color` (its resting face, default `pb_rest`), `selected_color` (the focused window's button, default `pb_focus`, the accent) and `selected_border` (default `accent_press`), so a style can use a lighter button or keep the accent off the panel; text on each face is picked for contrast (the theme's text-on-accent when the face is the accent). `padding` sets the window-list buttons' left and right padding in pixels (0–24, default 4, as the original xl_cheese; Mint-Y uses 8). Cinnamon caps a button's icon and title at 150px and adds the padding and border on top, so more padding makes wider buttons. `spacing` is the gap between window-list buttons (0–12, default 2). Panel launchers are as tight as Mint-Y-Variable: no gap, no lead-in padding (Mint-Y adds 7px) and no border at rest; their hover outline is a 1px inset shadow, which takes no room. Applets (clock, tray, sound…) have 3px side padding plus a 1px border, the same 8px as Mint-Y-Variable's 4px padding (Mint-Y's 5px made each applet 4px wider, and Cinnamon keeps the centre zone centred, so a full panel squeezed the window list from both sides). Each button also has a real 1px border on both sides (Mint-Y-Variable drew its buttons with a border image, which takes no room), so `spacing = 0` comes closest to Variable's fit when the panel is full. It also takes `active_marker` for the focused window, with the tab names: `none` (default), `line` (a 3px accent line along the bottom of the button) or `glow` (an accent glow rising from the bottom edge, gone by the middle). Cinnamon allows one shadow per widget, so the marker replaces the focused button's highlight, and the glow is one blurred inset shadow (no separate crisp line); on an accent face the marker uses `accent_press`. Written by `cheeselooks/panelmarker.py`. Note `hover_color` expressions see the palette, so `lighter(pb_rest, …)` starts from the built-in `pb_rest`, not the style's `color`.
- **Tabs** take their look from the buttons (edges, toolbar-button hover color and hover border); a style only picks the shape and the selected-tab marker, which combine freely:
  - `tab_kind`: `boxed` (joined to the page, unselected tabs in the toolbar color with a line along the page edge: xl-Cheeselooks), `open` (unselected tabs have no box until hovered: Mint-Y), `pills` (rounded tabs on a strip in the toolbar color, edge to edge; the selected one a raised button).
  - `active_marker`: `none`, `line` (2px accent line on the outer edge), `glow` (a 1px accent line plus an accent gradient fading inward: Clearlooks). The marker follows the tab position (top, bottom, left, right).
  - Boxed and open tabs never get a drop shadow (they are joined to the page). Written by `cheeselooks/tabs.py`, since each shape needs different rules.
- **`[panel]`** sets the panel's own colors. `color` is the panel background (default `panel`: the background moved 25% toward white, or 3% toward the text on dark themes); the panel gradient and opacity are applied to it as usual. Opacity stays a user setting, which a style suggests with `panel_opacity` in `[defaults]`.
- **`[defaults]`** suggests the style's starting point: `roundness`, `gradient`, `depth`, and optionally `panel_roundness`, `panel_gradient`, `menu_roundness`, `menu_gradient`, `panel_opacity`, `menu_opacity` and `panel_label_weight` (`"bold"`/`"regular"`). Panel and menu values left out keep following Global. They are applied on a fresh install (from the default style), when a style is picked, and on *Reset to style defaults*; the user can change anything afterwards. This is how a style ships its own panel feel.
- **Colors** can be a palette name, `#RRGGBB`, or an expression built on the palette: `darker(border_strong, 0.1)`, `lighter(border_strong, 0.1)`, `mix(border_strong, text, 0.2)`, `mix(border_strong, accent, 0.3)`.
- `cheeselooks check-style PATH` lists problems in plain language.

- Alpha values are written for **Depth 50**; Depth scales them (100 doubles them, 0 makes any style flat).
- **Surface layers adapt:** `highlight`, `sides`, `shade` and `inner` are written as they should look on the **normal button**. On a darker or more colored surface (an accent button, a pressed button, a focused panel button) they are toned down so they look about as strong; they are never strengthened. Drop shadows and rings are unaffected (they fall outside the widget). A layer can opt out with `adaptive = false`. The amount is `factor = (want / have) ^ adapt_strength`, where `want` and `have` are the lightness distances (CIE L*) between the layer color and the normal button, and between the layer color and this surface; the factor never drops below 0.15. `adapt_strength` is a top-level style setting from 0 (no adapting) to 1 (fully equal), default 0.6.
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
  - Unselected tabs are drawn (unlike Mint-Y): `header` (toolbar color) with a `border` outline, `text_dim`.
  - Hovered unselected tab: lightens to `flat_hover`, like toolbar buttons.
  - Tabs take the Roundness (top corners for top tabs, and so on).
- **Menu items (GTK menus):** hover is `menu_hover`, not the accent.
- **Menubar items:** hover is `menubar_hover`. An open menubar item uses the same color.
- **Panel buttons:** full panel height, raised (highlight only in Cinnamon), running = `pb_rest`, focused = `pb_focus`.

### Built-in styles (v1)
Designed by xl_cheese; one folder each in `styles/`:
- **xl-Cheeselooks** (default): muted, softly lit buttons with a light border and a gentle drop shadow; boxed tabs. Suggested defaults: roundness 15, gradient 10, depth 50.
- **xl-Gummy**: thick, softly blurred light edges for a soft, pillowy button; boxed tabs with the glow marker. Defaults 20 / 30 / 50.
- **xl-Classic**: a traditional bevel (light top and left, faint dark bottom and right); boxed tabs with the glow marker, as in Clearlooks. Defaults 20 / 30 / 50.

### Float (example style, shipped in docs, not in the app for v1)
Borderless, with soft shadows. Suggested buttons cast a shadow **tinted with the accent**. Entries are borderless with a hairline outline and a 3px accent glow on focus. Tabs are pills in a trough. It exists to prove the format and to give authors a second starting point.

---

## 7. Area details

### Cinnamon panel
- Panel background at **Panel opacity** (default 70%).
- Buttons fill the panel's full height; 3px gap between window-list buttons.
- States: running (`pb_rest`), hover (`pb_hover`), focused (accent, bold label, `accent_fg`), attention (`pb_attention`), progress (`pb_progress` fill from the left).
- Label weight: **Bold** (default, as in the current theme) or **Regular**, chosen on the Panel & Menu tab.
- Drawn entirely in CSS. The Mint-X `panel-assets/*.svg` images are retired.

### Cinnamon menu and popups
- Menu background `menu_bg` at **Menu opacity** (default 94%), `r2` corners, shadow.
- The favorites column uses `fav_bg` with `fav_hover`. Categories and apps both use `menu_hover`. The selected category uses `select` with `accent_fg`.
- The search entry uses the style's entry edge (focused look while the menu is open).
- The same rules cover the calendar, sound, network and right-click popups, plus notifications, OSD (volume and brightness) and the alt-tab switcher.

### GTK apps (Nemo and friends)
- **Stacking:** title bar (gradient) → menubar (flat `header`) → toolbar (flat `header`, bottom border).
- Path bar: one raised group, current folder `pressed`.
- Sidebar: `sidebar` background, rows edge to edge, `sidebar_hover`, selected `select`. Rows take the roundness in list-based sidebars; Nemo's sidebar is a tree view that draws each cell separately, so its rows stay square (rounded cells leave dots between icon and name).
- Grouped (linked) buttons use only the style's inner edges (highlight, shade), never a drop shadow, so neighbours don't overlap.
- File view: `base`, labels selected with `select`, item hover `hover`.

### Window borders
- **Title bar color:** follows `header`, or a user color.
- **Title text:** `text`, or a user color.
- **Border color and width:** color follows `border_strong` (the darker border), or a user color; width 0–6 px, default 1. Visual only, since Muffin keeps its own invisible resize area.
- **Title bar height:** 30–56 px, default 44.
- **Title bar gradient:** its own slider, 0–100, default 30.
- **Reset to Global colors:** a button on this tab (and on Panel & Menu and Terminal) that copies the Global colors back in while the switch stays on, so you can keep the theme's colors and change just one thing.
- **Named colors for any window border theme:** the GTK theme defines `wm_bg`, `wm_bg_unfocused`, `wm_title`, `wm_border` and the other `wm_*` colors from these settings. Window border themes such as Mint-Y's read them, so even Mint-Y's title bars match. `apply` refreshes the window border theme so Muffin picks the colors up.
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
| **Focus ring** | Color picker (default accent); width 0–3 px, 0 turns it off | Subtle 1px dashed, text color at 25%, like Mint-Y |

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
| Check and radio items in GTK popover menus | **Generated SVGs**: GTK draws these only as an image, with no CSS box |
| Buttons in info bars and selected rows | Keep Mint-Y's see-through look so their light text stays readable |
| Everything else | CSS |

No hand-made bitmap images remain in the theme.

---

## 9. Settings app

- A Python + GTK 3 app called **Cheeselooks Settings**, with a menu entry and the `cheeselooks-settings` command.
- **Tabs:** Global · Style · Panel & Menu · Window Borders · Terminal · Details · *Icons (later)*.
- **Style picker:** not toggle buttons (there may be 20+ styles). A list modelled on GNOME 2's *Customize Theme → Controls* tab: each row shows a tiny live sample of that style (a button, a checkbox and a radio, drawn with the current colors) beside its name and author, a search box once the list is long, plus *Open styles folder* and *Import style…*. Picking a style moves Roundness, Gradient and Depth to the style's `[defaults]`.
- **Accent from wallpaper:** a button on the Global tab reads the current wallpaper and offers 5–6 accent suggestions as swatches. One click applies one to the Accent picker (preview only until Apply). Implementation: downscale the image, cluster the colors, drop near-greys and colors too close to the background, and rank by how often they appear and how saturated they are. Python standard library plus GdkPixbuf only.
- **Live preview inside the app:** generated CSS loaded into a preview area. The desktop changes only on **Apply**.
- **Buttons:** **Apply**, **Revert** (restore the last applied settings), **Reset to defaults**.
- **Presets:** built-in Global, Panel and Terminal lists, plus **Save preset**, **Import** and **Export** (JSON).
- Readability warnings sit under the controls ([§3](#3-color-rules)).
- Same layout as the mockup. Controls that are off are greyed out with their following values shown.

### Command line
```
cheeselooks apply [--preset NAME | --settings FILE] [--style NAME] [--style-defaults]
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
├─ cheeselooks/            generator: palette, shape, styles, tokens, render, install, reload, cli
├─ bin/cheeselooks         run the command from a checkout
├─ tests/                  unittest suite (python3 -m unittest discover tests)
├─ templates/
│  ├─ cinnamon/cinnamon.css.tmpl  (+ asset SVG templates)
│  ├─ gtk-3.0/gtk.css.tmpl
│  ├─ gtk-4.0/gtk.css.tmpl        (non-libadwaita GTK 4 apps)
│  ├─ gtk-4.0/libadwaita.css.tmpl (colors block)
│  ├─ metacity-1/metacity-theme-3.xml.tmpl
│  └─ index.theme.tmpl
├─ styles/xl-Cheeselooks/style.toml
├─ presets/                global/, panel/, terminal/
├─ reference/              the original xl_cheese-Mint-Y-Variable text files
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
| `cinnamon` | **Linux Mint's current Mint-Y Cinnamon theme** (linuxmint/mint-themes, Oct 2026), converted by `tools/convert_cinnamon.py` into `templates/cinnamon/base.css.part`; it supports newer Cinnamon features the old Mint-X-based file lacks. The xl_cheese panel look (full-height raised buttons) is drawn by `xl.css.part`. Mint-Y's colored switch and checkbox images are replaced by generated ones; its neutral `common-assets` are copied unchanged |
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
| **Release** | A **Claude** preset: a theme designed by Claude, any way it likes, shipped alongside the other presets |
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

---

## 16. Pending changes (next round)

Agreed but not built yet. Delete each line once it's done.

- **Claude tab style:** designed by Claude together with the Claude preset (see Roadmap).
- **Icon and theme thumbnails:** one static "swirly rainbow" image as the settings app's icon and as the theme's thumbnails in Mint's Themes settings (`gtk-3.0/thumbnail.png`, `cinnamon/thumbnail.png`, `metacity-1/thumbnail.png`), so xl-Cheeselooks is recognizable whatever colors are chosen. Static on purpose: the brand, not a preview of the current colors.
