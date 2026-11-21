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

  "Away" is a short-lived hidden link beside the theme, `.xl-Cheeselooks-reloading` → `xl-Cheeselooks` (`reload._make_swap`), so the desktop shows the new theme under both names and doesn't flash Mint-Y (it did before, asked by xl_cheese); the link is removed once everything is back on the real name, and Mint-Y is the fallback if it can't be made. The user sees at most a short redraw. Running GTK 3 apps restyle themselves, while some apps (Firefox, Electron apps) only partly refresh until they're restarted.

### Settings model (defaults)

```jsonc
{
  "version": 1,
  "global":  { "accent": "#FF8467", "bg": "#F5F5F5", "text": "#303030",
               "size": "normal", "roundness": 15, "gradient": 10,
               "hover_in_ms": 50, "hover_out_ms": 125, "hover_strength": 50 },
  "style":   { "name": "xl-Cheeselooks", "depth": 50 },
  "panel":   { "separate_colors": false, "accent": null, "bg": null, "text": null,
               "label_weight": "bold", "panel_opacity": 70, "menu_opacity": 94,
               "panel_shape": { "follow_global": true, "roundness": 15, "gradient": 10 },
               "menu_shape":  { "follow_global": true, "roundness": 15, "gradient": 10 } },
  "window_borders": { "separate_colors": false, "title_bar": null, "title_text": null, "border": null,
                      "title_bar_height": 44, "border_width": 1, "title_gradient": 30, "window_roundness": None,
                      "button_layout": "right", "button_style": "flat", "button_roundness": null },
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
| `pressed` | `mix(bg, text, .13)` | `darker(bg, .16)` | Toggled and pressed buttons, the current path button. On dark it goes into a well below the surface: toward the text colour (lighter) made pressed buttons look raised |
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
- **Widgets:** `button`, `suggested`, `destructive`, `linked` (joined button groups: path bars, stack switchers, spin buttons; copies `button` unless set; its buttons never get a drop shadow or recess each, the group's box draws them round the whole group), `toolbar_button`, `title_button`, `close_button`, `entry`, `combo`, `tab`, `menu_item`, `menubar_item`, `panel_button`, `check`, `switch`, `scrollbar`. Widget settings: `like`, `edge`, `hover_edge`, `pressed_edge`, `focus_edge`, `border`, `hover_color`, `tab_kind`, `active_marker`, `hover_fg`. Text on a hover face is picked for contrast (your text color or text-on-accent); `hover_fg` sets it instead, e.g. `menu_item = { hover_color = "accent_hover", hover_fg = "accent_fg" }` for white text on an accent hover (used by `menu_item`, `menubar_item` and `tab`; `panel_button` takes `selected_fg` the same way). A text color goes with its face: a widget that sets its own hover or selected color doesn't inherit the other widget's text color through `like`. `button` takes `color` too (done): the resting face of normal buttons, e.g. `color = "darker(button, 0.03)"`. It's read against the usual palette, then the palette is worked out again from it, so the default `button_hover` and the gradient (smooth, split or glass) follow your face, and widgets that copy `button` (combo boxes, joined groups, the xl-Cheeselooks title buttons) get it. Text on it isn't adjusted, so keep it within reach of the theme's text contrast. `panel_button` also takes `color` (its resting face, default `pb_rest`), `selected_color` (the focused window's button, default `pb_focus`, the accent) and `selected_border` (default `accent_press`), so a style can use a lighter button or keep the accent off the panel; text on each face is picked for contrast (the theme's text-on-accent when the face is the accent). `padding` sets the window-list buttons' left and right padding in pixels (0–24, default 4, as the original xl_cheese; Mint-Y uses 8). Cinnamon caps a button's icon and title at 150px and adds the padding and border on top, so more padding makes wider buttons. `spacing` is the gap between window-list buttons (0–12, default 2). Panel launchers are as tight as Mint-Y-Variable: no gap, no lead-in padding (Mint-Y adds 7px) and no border at rest; their hover outline is a 1px inset shadow, which takes no room. Applets (clock, tray, sound…) have 3px side padding plus a 1px border, the same 8px as Mint-Y-Variable's 4px padding (Mint-Y's 5px made each applet 4px wider, and Cinnamon keeps the centre zone centred, so a full panel squeezed the window list from both sides). It also takes `active_marker` for the focused window, with the tab names: `none` (default), `line` (a 3px accent line along the bottom of the button) or `glow` (an accent glow rising from the bottom edge, gone by the middle). Cinnamon allows one shadow per widget, so the marker replaces the focused button's highlight, and the glow is one blurred inset shadow (no separate crisp line); on an accent face the marker uses `accent_press`. Written by `cheeselooks/panelmarker.py`. Note `hover_color` expressions see the palette, so `lighter(pb_rest, …)` starts from the built-in `pb_rest`, not the style's `color`.
- **`scrollbar`** is the scrollbar thumb: `color` (at rest, default Mint-Y's grey `scroll_slider`), `hover_color` (`scroll_hover`), `pressed_color` (while dragging, default `accent_press`) and `border` (an optional crisp 1px outline; default none). xl-Gummy uses accent thumbs with an `accent_press` outline. The thin overlay indicator keeps its own colour.
- **Tabs** take their look from the buttons (edges, toolbar-button hover color and hover border); a style only picks the shape and the selected-tab marker, which combine freely:
  - `tab_kind`: `boxed` (joined to the page, unselected tabs in the toolbar color with a line along the page edge: xl-Cheeselooks), `open` (unselected tabs have no box until hovered: Mint-Y), `pills` (rounded tabs on a strip in the toolbar color, edge to edge; the selected one a raised button), `claude` (designed by Claude: unselected tabs are just text with a soft hover and a light outline; the selected tab is a card in the page colour, joined to the page, with softer corners and a short accent bar centred on its outer edge, drawn as a clipped ellipse gradient). The `glow` marker's accent fade is 35% strong on light themes and 60% on dark ones (`tabs.GLOW_ALPHA`, asked by xl_cheese: a faint fade barely showed on a dark tab). Boxed tabs keep the page's frame line along the edge facing the page when hovered too (the hover border along it read as a shade); the edge layers along that side (highlight, shade) are dropped in every state (`tabs.without_side`).
  - Boxed, open and claude tabs fill their strip out to its outer edge (Mint-Y's 2px strip padding is given to the tabs instead), so there's no gap between them and a toolbar above (asked by xl_cheese: the gap looked busy). Where tabs sit right under a main toolbar (Nemo; Xed and others, whose tabs are in panes after the toolbar: `.primary-toolbar ~ paned … notebook`), the tabs drop their top border and the toolbar's bottom line serves as it (two lines side by side looked busy in Nemo and like a 1px gap in Xed); in a framed notebook the strip already overlaps the frame, so the tabs' top border sits on the frame line. With roundness above 0 the strip is darker than every tab (`tabs.STRIP_DARKER`: 5% on light themes, 20% on dark ones, below the darkest of the background, the toolbar color and the page color), so rounded corners read; at roundness 0 it stays the background.
  - Boxed and open tabs drop the highlight or shade on the edge that faces the page (top tabs: no bottom shade; bottom tabs: no top highlight; left tabs: nothing on the right edge; right tabs: nothing on the left), found from each layer's offset.
  - `active_marker`: `none`, `line` (2px accent line on the outer edge), `glow` (a 1px accent line plus an accent gradient fading inward: Clearlooks). The marker follows the tab position (top, bottom, left, right).
  - Boxed and open tabs never get a drop shadow (they are joined to the page). Written by `cheeselooks/tabs.py`, since each shape needs different rules.
- **`[panel]`** sets the panel's own colors. `color` is the panel background (default `panel`: the background moved 25% toward white, or 3% toward the text on dark themes); the panel gradient and opacity are applied to it as usual. Opacity stays a user setting, which a style suggests with `panel_opacity` in `[defaults]`.
- **Panel height** (done; `panel.panel_height`, 20–60 px, Panel & Menu tab): Cinnamon's own setting (`org.cinnamon panels-height`), the first setting the tool changes outside the theme. Unset (`null`, the default) leaves Cinnamon's height alone and the slider shows the current one; once set, Apply sets every panel to it (keeping their ids, e.g. `['1:32', '2:32']`) and records the old value in the last-good folder (`panels-height`), which Revert puts back. The theme is always built for the height in use, as before. The app's drawn panel preview follows it. **Panel label weight** is Bold, Regular or **Light** (done; weight 300, which needs a font with a Light face, such as Ubuntu, Noto Sans or Inter; without one it shows as Regular). It reaches the window-list buttons too: their labels take the weight of the button box (Cinnamon's grouped window list labels are `.grouped-window-list-button-label`; Mint-Y still styles the old `.grouped-window-list-item-label`, and the classic list's labels have no class), and Mint-Y sets that box bold, so the weight is set on `.window-list-item-box` and `.grouped-window-list-item-box`. The focused window is one step heavier (Light → Regular, Regular → Bold).
- **Window borders on windows Cinnamon decorates (20 Nov, xl_cheese: Border width and colour did nothing there):** Muffin 6 (Mint 22) doesn't read `metacity-1/`; it draws frames from GTK 3 CSS nodes (`window.background.ssd > decoration > headerbar.titlebar.default-decoration`, muffin `src/ui/theme.c`). The frame's visible width is `decoration`'s border plus padding, drawn with `gtk_render_frame`; the title bar is drawn over the frame's top, full width; a box-shadow there lands outside, in the invisible resize area. Ours (and Mint-Y's base) only gave `.ssd decoration` a 1px shadow, so our Border settings reached only the metacity file and windows drawing their own title bar. Now (`gtk-3.0/xl.css.tmpl`): `.ssd decoration` has a `border_width` border in the border colour (unfocused: `wb.border_unfocused`, as the metacity theme), none on top; the title bar's top and sides are inset box-shadow lines (`wb.ssd_title_focused` / `_unfocused`, the style's highlight just under the top line), so the title bar's height and buttons don't move (a real border made it taller by the width); maximized and tiled windows (Muffin's `maximized` / `tiled` classes) have none. `tools/muffin-preview.py` now draws the title bar full width over the frame, as Muffin does, with some window below to show the sides and bottom. Checked there at 1 and 4px (focused, unfocused, maximized). **On Cinnamon (xl_cheese, 4px blue): the title bar's lines showed, the sides and bottom were a 4px see-through gap.** With compositing, Muffin makes the frame's see-through mask from decoration's and the title bar's *backgrounds* only (`frames.c`, `meta_ui_frame_get_mask`), not their borders; ours was transparent, and Mint-Y's base clips backgrounds to the padding box, so the area under the border was masked away. `.ssd decoration` now has a background in the border colour with `background-clip: border-box`. `tools/muffin-preview.py` applies the same mask (see-through parts as a checker), which reproduced the gap before the fix.
- **Window layout (20 Nov, xl_cheese):** a **Theme** tab comes first, holding the theme list (as tall as the window allows) and its Save / Duplicate / Rename / Delete buttons, taken off Global. The settings tabs never scroll: their sliders take the mouse wheel, so a scrolling tab fought it. The window's least height is the tallest settings tab, whole (`app._fit_pages`, measured again after each preview since Size changes every control's height); only Integration, Documentation and About may scroll. The Glyphs picker is two rows of joined buttons (three to a row: 3 + 2 now, 3 + 3 with a sixth set). The preview is as wide as its button row (Button, Suggested, Delete, Toggled), no wider: the Left / Center / Right linked buttons and the text box (filling what's left, never widening it) come second, then Tooltip, the switch, check and radio. The window opens at its smallest (no default size; 973×703 on the default theme; the Style list, like the Theme list, fills its tab): the preview at that width (no fixed divider position), the tabs as wide as their widest (Panel & Menu's sliders; the Theme tab's buttons are Save Theme…, Duplicate, Rename, Delete, short enough not to set it). Folder style pictures are 72px, so four fit. The Icons tab's preview: 48px folders in two rows of four, 24px in one row of seven (the plain folder left out), so it doesn't widen the tabs. "Restart Cinnamon after Apply" heads the Integration tab. Folder style pictures: four to a row at most.
- **Restart Cinnamon after Apply** (done): Muffin only re-reads its window border theme at login or a Cinnamon restart, so a changed window border theme didn't show until the next login. Optional restart after Apply: `cheeselooks apply --restart`, or the checkbox at the top of the Integration tab (an app preference in `app.json`). It calls Cinnamon's D-Bus `org.Cinnamon.RestartCinnamon` (as Ctrl+Alt+Esc does: the panel blinks, windows stay open); X11 only, and if it can't, the log says to press Ctrl+Alt+Esc.
- **Focus ring** (Details tab, done): Color, **Style** (Dashed, Dotted, Solid) and Width (0–3, 0 = off), each changing only itself. Untouched, it's Mint-Y's subtle ring: 1px dashed in the text colour at 25%, and the controls show exactly that (the colour as Follow theme, a soft grey; earlier they showed the accent and width 2, the old custom starting point, and picking a colour switched the ring to solid). On selected rows the ring is your colour blended two-thirds into the selection, or the text-on-accent colour at 35% by default.
- **`[title_bar]`** (done): `highlight` (0–1, default 0.15) and `highlight_dark` (default 0.08) set the 1px light line along the top of header bars, as white at that alpha (0 = none); `highlight_dark` is used when the title bar counts as dark (lighter title text). Mint-Y's base drew this line from the window background (a pale stripe on a dark or coloured title bar); it now follows the title bar. `gradient_shape`, `split_step` and `glass_return` in `[title_bar]` give the focused title bar its own gradient shape (default smooth; the style's top-level shape doesn't apply to title bars), in GTK 3 / 4 / libadwaita header bars (`wb.title_grad`) and Muffin's title bars (`wb.ops.titlebar_focused`: metacity spaces a gradient's colours evenly, so a step is two gradients, top half and bottom half). The range comes from the Window Borders tab's Title bar gradient; with glass the bottom edge lifts back toward the top colour, so it no longer ends exactly in the menubar colour. GTK 3 and 4 header bars; Muffin's title bars have no such line.
- **`[notification]`** (done, step 1 of the notification plan) sets how Cinnamon's notification popups are drawn: `kind = "line"` (default: a 4px accent line along the top, Mint-Y's look), `"flat"` (no accent) or `"bordered"` (a thin 1px border all round), and optionally `color` (the line or border colour, default `accent`). Opacity is a user setting, **Notification opacity** on the Panel & Menu tab (30–100, default 94; popups used to follow Menu opacity); a style can suggest it with `[defaults] notification_opacity`. The built-in styles keep `line`. A `claude` kind (the short accent bar at the top centre) is step 2, together with the panel `bar` marker.
- **`recess` edge layer** (done; from xl_cheese's GTK 2 xl_cheeselooks button): the background around a widget pressed in a little, a ring just outside the border, darker along the top and left (`color`, `alpha`, `alpha_dark`) and lighter along the bottom and right (`light`, default white, with `light_alpha` / `light_alpha_dark`, default the same alpha as the dark side); `width` (default 1px). Drawn as two outer shadows that never overlap (the dark one shifted up-left, the light one down-right; light drawn over a dark ring came out darker than a near-white background), so the border, highlight and shade are untouched; Depth scales it like other layers. Outside the widget, so a joined group's buttons don't each get it (it would overlap the next button); instead the group's box (`.linked`, GTK 3 and 4) draws `linked`'s outer layers, the recess and the drop `shadow`, round the whole group (tokens `w.linked.outer`, `w.linked.g4_outer`), so a joined group lifts or sits in a recess like a single button. In GTK 3, groups side by side now carry them per button too (the box drew the shadow away from the buttons wherever GTK made it taller than they are: a stack switcher in a header bar, or in Cinnamon settings' toolbar, where it left a 1px light line), `w.linked.ltr_*` tokens, leaning right as GTK boxes paint left to right; vertical groups keep the box. Nemo's path bar is a custom container that draws no CSS, so there too the group's outer layers go on the buttons by position (`w.linked.{,hover_,pressed_}{first,middle,last,only}_shadow`, split as for Linked title buttons by `titlebuttons._group_shadow`: recess strips along each button, the ends on the first and last, the drop shadow shifted right by its blur on each button, since buttons are painted left to right: no piece reaches back onto the button before it, the next button's face covers what falls under it, and neighbouring pieces meet edge to edge into one shadow under the group; the last piece is shrunk to stop at the group's right end). Nemo paints its folder buttons right to left (its path bar keeps them deepest first; nemo-pathbar.c), then its ◀ and ▶ `slider-button`s, so there the pieces lean left (`rtl_paint`) and ▶, painted last, takes the left-to-right end piece. In general each piece leans toward whichever neighbour is painted after it (`titlebuttons._lean`, or a `lean` per join); Muffin paints close, maximize, minimize in that order, so its Linked window buttons lean by the layout. Unfocused windows draw every button layer at the Unfocused depth (see Unfocused depth). GTK's own path bar (file dialogs) paints right to left like Nemo's and takes the same rules (`.path-bar.linked > button`). Spin buttons are fields and take it from the entry's edge (add `recess` to `sunken`). Cinnamon (one shadow per widget) doesn't draw it. Example: `recess = { color = "black", alpha = 0.10, light = "white", light_alpha = 0.55 }`.
- **Gradient shape** (top-level keys): `gradient_shape = "smooth"` (default: top fading to bottom) or `"split"`, a glossy face as in Clearlooks Gummy / Clearlooks-Phenix: the top half fades gently, two colour stops at 50% make a crisp step, and the bottom half fades on (`linear-gradient(to bottom, top, upper 50%, middle 50%, bottom)`). `split_step` (0–1, default 0.4) is how much of the top half's fade goes into the step. The Gradient slider still sets the strength. GTK templates use `X_grad` tokens (written by `tokens._add_face_gradients` for every `X_top`/`X_bottom` pair); the title bar stays smooth, and Cinnamon only has two-colour gradients, so the panel and its menus stay smooth. xl-Gummy uses `split` with `split_step = 0.6`. Or `"glass"` (done; xl_cheese's GTK 2 xl_cheeselooks button, his fork of the Clearlooks engine): light reflected from below. The top half fades from the top colour toward the darkest, the face steps down to the darkest at the middle, and the bottom half fades back *lighter* toward the bottom edge. `split_step` sets the step as for split (0 = no step, a smooth dip) and `glass_return` (0-1, default 0.4) how far the bottom climbs back toward the top colour. Both shapes come from `palette.gradient_stops`, used for the CSS (`gradient_css`) and for title button faces drawn as SVG, so **title buttons follow the style's shape** too (done): GTK title buttons and Muffin's window-border buttons get the same split or glass face as the other buttons. Title bars and Cinnamon stay smooth (two-colour gradients only). The Gradient slider sets the range: glass reads best at 60 or more.
- **`[title_buttons]`** (done): the window buttons' own colours, so a style can put light grey buttons on a blue title bar (OS/2) or give close the same hover as the others. Keys: `color` (resting face), `hover_color`, `pressed_color`, `border`, `hover_border`, `glyph`, and `close_hover` (`"accent"` default, `"hover"` = as the other buttons, or a colour). The face keys apply to the button styles that draw the style's own button (xl-Cheeselooks, Linked, Classic); `close_hover` to every style but Dots (its close stays red). Colours are read against the theme's palette, not the title bar's, so `"button"` is the theme's usual button face. With only `color`, hover and pressed follow it (`lift(color, 0.06)`, `darker(color, 0.12)`). Glyphs are picked for contrast with each face (the better of the title text and the theme's text) unless `glyph` is set; a colour `close_hover` gets a darker border and pressed face of its own. The edge layers (recess, drop shadow, highlights) stay the button edge's: the recess is drawn over the title bar outside the face, so it follows the title bar (a light-text bar counts as dark and takes `alpha_dark` / `light_alpha_dark`). Example: `[title_buttons]` `color = "button"`, `close_hover = "hover"`. Tokens `tbtn.*` (tokens._title_button_colors), used by `titlebuttons.faces`.
- **`[defaults]`** suggests the style's starting point: `roundness`, `gradient`, `depth`, and optionally `panel_roundness`, `panel_gradient`, `menu_roundness`, `menu_gradient`, `panel_opacity`, `menu_opacity` and `panel_label_weight` (`"bold"`/`"regular"`). Panel and menu values left out keep following Global. They are applied on a fresh install (from the default style), when a style is picked, and on *Reset to style defaults*; the user can change anything afterwards. This is how a style ships its own panel feel.
- **`lift(color, amount)`** is a hover that works on light and dark surfaces: on a light palette exactly `lighter(color, amount)`; on a dark one (a dark theme or a dark title bar) it moves toward the text colour, a sixth as far (`render.DARK_LIFT`), instead of jumping toward white. The built-in styles' hover colours use it. Its amount follows the Hover strength slider (×1 at the default 50), so style hovers such as tabs and toolbar buttons respond to the slider like the palette's own hovers.
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
- **Toolbar and title buttons:** flat until hover, then raised. Title buttons follow the chosen button style (below).
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
- **Accent and delete button borders** (asked by xl_cheese): the suggested button's border is the style's `suggested` `border` (light styles `accent_press`); the dark xl styles use `darker(accent, 0.4)` and `darker(destructive, 0.4)`, since the accent's own darker shade read as a light rim on a dark window beside the other buttons' dark ones. The destructive button's border now follows the style's `destructive` `border` too (tokens `destructive_border`, `destructive_hover_border`, `destructive_pressed_border`, set outright in every state as the suggested button's are, else the plain buttons' hover border showed through on hover; before, the templates fixed it at `darker(destructive, 0.14)`, which stays the default). The close button's accent hover and pressed faces take the suggested button's border (on the title bar's palette), so an accent face has the same rim everywhere.
- **Headerbar widgets on a title bar of its own colours** take the title bar's palette (`wbp.*`), not the window's: headerbar buttons' text and symbolic icons in its text colour (`wbp.text`, `wb.unfocused_text` when unfocused), and joined groups such as view switchers in its button faces (`wbp.button`, `wbp.w.linked.*`), GTK 3 and 4. (With the theme's own title bar colours `wbp` is the theme, so nothing changes.) A header bar's suggested button (accent face) takes its border and edges from the suggested widget on the title bar's palette, except when the accent is near the title bar's colour (same hue within 20° and contrast below 2, or contrast below 1.15 whatever the hue: xl-Classic, xl-Classic Dark, xl-Vintage): then the accent's own darker border barely showed on the bar and the button looked washed out beside the others, so it takes the title-bar buttons' border and edges (tokens `wbp.sug.*`, `tokens._near_colour`).
- *(done)* **Unfocused depth** (Style tab, `style.unfocused_depth`, 0–100, default 70; a style suggests it with `unfocused_depth` in `[defaults]`): unfocused windows draw every button layer (highlight, shade, recess, drop shadow) at that percentage of its strength, instead of dropping the outer ones: plain, flat, accent and delete buttons, joined groups and view switchers, path bars, and title buttons (flat face, the rest edge's layers faded; Muffin too). 0 = flat, 100 = as focused. Tokens `bd.<token>` for every shadow token (`palette.scale_shadow`: each colour's alpha × the depth). GTK 3; GTK 4 apps keep their full layers for now.
- **Panel & Menu tab layout** (`app.PANEL_LAYOUT`): colours, Label weight, Notification opacity; **Panel style**: Height, Roundness, Gradient, Opacity; **Menu style**: Roundness, Menu-item roundness, Opacity. The settings file keeps Height and the opacities outside the shape groups, so changing them doesn't stop a shape following Global.
- **Menu style** (Cinnamon): Roundness shapes the menu itself and Cinnamon's other popup surfaces (`menu.r`, `menu.r2`); **Menu-item roundness** (`menu_shape.item_roundness`, token `menu.item_r`) only the main menu's items (applications, categories, favourites); the file dialog's places sidebar (GTK 3 `placessidebar`, GTK 4 `.navigation-sidebar`) follows the same rule as stack sidebars (`tokens._lists_css`, asked by xl_cheese); items in every other menu (right-click and applet menus, `.popup-menu-item`) follow GTK menus' rule (`tokens.SQUARE_LISTS_AT`, asked by xl_cheese): square and edge to edge up to Roundness 30; above it rounded at Global roundness (`r`) and inset 6px from the menu's sides (`.popup-menu-content` side padding; the main menu's content keeps none, `.appmenu-background`). Token `popup_items.css`. Menus follow Global's gradient (no menu gradient; a style's `menu_gradient` in `[defaults]` is ignored; `menu_item_roundness` can be suggested). The preview draws the main menu open above a Menu button on the panel. Cinnamon 6.4's main menu uses `appmenu-*` classes (the older `menu-*` ones are styled too); its selected category takes `[panel]` `menu_category` (a colour, default Mint-Y's grey, `mix(menu_bg, text, 0.123)`; e.g. `menu_category = "accent"`; older styles' `menu_item` `selected_color` still works), its hover (apps, categories and the favourites column) takes `[panel]` `menu_hover` and `menu_hover_fg` (asked by xl_cheese; default a step toward the text set by Hover strength, the favourites stepping from their own background; the text, left out, is picked to read on the hover, `accent_fg` on the accent; the favourites column, darker than the menu, gets `menu_hover` moved by as much as it's darker, channel by channel, so the hover reads alike on both, or its own `menu_fav_hover`; its gradient only shades downward, top at the hover colour, since a lightened top washed out on the short square buttons with more gradient, xl-Classic Dark. Cinnamon 6.4's sidebar (`.appmenu-sidebar`: favourites with names, places, system buttons) has its own background, Mint-Y's `mix(menu_bg, text, 0.123)` (token `menu.sidebar_bg`), lighter than the menu on dark themes; its hover (`menu.side_hover`) is the menu's hover moved by as much, or `menu_fav_hover`, also shaded downward only. Before, it took the app list's hover, which on dark themes was about the sidebar's own colour). Right-click and applet menus keep the style's `menu_item` hover. Tokens `menu.category`, `_top`, `_bottom`, `_fg`; `menu.main_hover`, `_top`, `_bottom`, `_fg`, `menu.fav_main_hover`.
- **Dividers** (style key `dividers`, a color or expression): the lines between sections in GTK 3 and 4 (frames, panes, the toolbar's bottom line, list, statusbar, tab-frame and sidebar borders, separators), token `dividers` (and `frame`, `separator_divider`); pane dividers too, and, when a style sets `dividers`, the line under header bars (`wb.line`, resolved on the title bar's own colors; otherwise the window border color as before). Left out: `mix(bg, text, 0.234)` as Mint-Y, lighter than the background on dark themes; e.g. `dividers = "darker(bg, 0.35)"` for darker ones, as Mint-Y Dark.
- **Colors from a picture** (Global, under the color pickers): **Wallpaper** (Cinnamon's `picture-uri`) or **Image…** (any picture). `cheeselooks/imagecolors.py` shrinks it to about 64px, groups pixels by hue (24 steps) and lightness (3), and scores each group's average by how much it covers and how vivid it is (greys last); six distinct colors show as swatches, and the most vivid, brought to a usable lightness (0.42–0.62), becomes the accent. Clicking a swatch uses that color instead. Background and text are left as they are, so a dark theme stays dark whatever the picture.
- **Documentation and About tabs** (settings app): Documentation has short notes on each part of the app (`app.DOC_NOTES`), a link to the full docs online, and **Create a starter style…**, which asks a name and writes `~/.local/share/xl-cheeselooks/styles/<name>/style.toml` from `data/style-template.toml`: every style option, the essentials on and the rest commented out with a note each ("instead of" lines are alternatives to the line above); a test loads it as shipped and with everything switched on. About shows the icon, version, licence (GPL-3.0 or later) and the GitHub link. Under the link, "Enjoying xl-Cheeselooks? It's free and always will be." and a **Leave a tip ☕** button in the accent (a suggested-action button, so it takes the theme's own look; `app.TIP_URL`, xl_cheese's PayPal Donate link; empty hides both). The same link is the repository's GitHub Sponsor button (`.github/FUNDING.yml`).
- **Size** (Global, `global.size`, 24–38 px in 2px steps, default 30): the control height. Even heights only, so 16px icons stay on whole pixels; row padding and the title-button glyph size follow it (`shape.size_params`). The old Compact / Normal / Large settings load as 26 / 30 / 36, which keep exactly their old sizes.
- **Menu items and sidebar rows follow Roundness** (`tokens._lists_css`): at Global Roundness 30 or less, GTK menu items (GTK 3 menus, GTK 4 popover menus: every menu but Cinnamon's main menu) and stack-sidebar rows (`GtkStackSidebar`, the list of pages down the side of a window, as in this app and Cinnamon settings) are square and full width, the sidebar with a 1px divider under each row (`frame`), as in Mint-Y; above 30, rounded, menu items 2px in from the menu's sides and sidebar rows inset as before, so a rounded hover never touches the edge.
- **Scrollbar width** (Details → Scrollbars, `details.scrollbars.width`, 6–16 px, unset = the mode's own: 10 classic, 6 for an overlay scrollbar when it expands): the thumb's width in either mode; the thin overlay indicator stays as it is.
- **Button spacing** (`button_spacing`, 0–12 px, unset = the button style's own): extra space between the window buttons on top of the style's own gap, the same in GTK 3 apps (a margin on each following button turns the header bar's 6px into it), GTK 4 apps (`windowcontrols` border-spacing) and Muffin (a margin taking its fixed 6px back). Defaults: 6 (GTK 3's own), 0 for Classic (4px apart as Clearlooks) and Less Gargantuan; locked at 0 for Gargantuan and xl-Cheeselooks Linked, whose buttons are made to touch (the slider is greyed out). Picking another button style resets it. `titlebuttons.spacing`.
- **Window roundness** (`window_roundness`, 0–100, unset = follow Global's Roundness): the window's top corners (title bars, header bars, GTK 3 and 4 client-side windows, Muffin's borders, Gargantuan's corner close button). Token `wb.r`, worked out as `r2` is (1.4 × the control radius, at most 14px); `r2` itself stays Global's, for popovers, tooltips and cards.
- **Round bottom corners** (`round_bottom`, off by default; **on the back burner**: the switch is hidden and a saved setting ignored while `tokens.ROUND_BOTTOM_READY` is False, see the roadmap): the bottom corners take the Window roundness too (token `wb.r_bottom`, `0` when off), for windows that draw their own header bar: GTK 4 ones, and GTK 3 ones (with apps the Buffet menu app gives a header bar). Best effort: neither GTK 3 nor a plain GTK 4 window trims its contents to its shape (libadwaita's own windows do), so any piece that paints its own background into a bottom corner squares it again. The known ones round that corner too (tokens `wb.bottom3.css`, `wb.bottom4.css`, empty when off): sidebars with the scroller, viewport and list inside them (their outer corner), action bars (Drawing, dialogs) and Xreader's page view (`evview`). Tree views are left out: they draw every row with the view's own style, so Nemo's sidebar rows got the curves. New cases are found by testing; GTK Inspector (`GTK_DEBUG=interactive`) names the piece. Anything an app draws itself (video, terminals, web views) stays square. Muffin-framed windows stay square at the bottom: only the compositor could trim their contents (see the roadmap). Maximized, tiled and full-screen windows are always square.
- **Title bar gradient:** its own slider, 0–100, default 30.
- **Reset to Global colors:** a button on this tab (and on Panel & Menu and Terminal) that copies the Global colors back in while the switch stays on, so you can keep the theme's colors and change just one thing.
- **Named colors for any window border theme:** the GTK theme defines `wm_bg`, `wm_bg_unfocused`, `wm_title`, `wm_border` and the other `wm_*` colors from these settings. Window border themes such as Mint-Y's read them, so even Mint-Y's title bars match. `apply` refreshes the window border theme so Muffin picks the colors up.
- **Button layout:** written to Mint's own setting (`org.cinnamon.desktop.wm.preferences button-layout`).
- **Implementation:** traditional title bars are drawn by `metacity-1/metacity-theme-3.xml` (Muffin), headerbar apps by GTK CSS; both use the same tokens so they match.
  - The template is generated by `tools/gen_metacity_template.py` (every button function × state × focus); `cheeselooks/metacity.py` adds what depends on settings: button padding so the title bar is exactly the chosen height, the corner radius (`r2`, the same as GTK windows), and the border (filled bands on each side plus one arc per pixel around the rounded corners; nothing at width 0).
  - Title bar: the title gradient when focused, flat when unfocused, title centred. Maximized windows have no border and square corners; tiled windows keep only the inner side.
  - Buttons: Mint-Y's grey glyphs (GPL-3+), recoloured per state with `colorize`. Hover and pressed faces are SVGs written from the title-button tokens (`button-hover.svg`, `button-pressed.svg`, `close-hover.svg`, `close-pressed.svg`), so they follow the style.
  - Newer theme features carry version guards (`ellipsize_width` 3.1, attached dialogs 3.2, tiled states 3.3), as Mint-Y does; without them Muffin and Metacity fall back to Adwaita.
  - Test without Cinnamon: `tools/wm-preview.sh THEME_DIR OUT` runs GNOME's Metacity (same theme format) on a virtual display and screenshots two windows.
- **Button styles** (`window_borders.button_style`, drawn by `cheeselooks/titlebuttons.py`): one description per style (a face behind the glyph for each kind of button, minimize / maximize / close / other, and each state: rest, hover, pressed, unfocused) drives all three places title buttons are drawn, so they match: Muffin's window borders (SVG faces and glyphs written at apply time, `"file:<path>"` tokens), GTK 3 header bars and GTK 4 / libadwaita window controls (CSS tokens `titlebuttons.css`, `titlebuttons4.css`). The styles:
  - `flat` (**xl-Cheeselooks Flat**, default; theme xl-Cheeselooks): glyph only at rest; the style's title button on hover; close fills with the accent.
  - `drawn` (**xl-Cheeselooks**; theme xl-Gummy): the style's normal button at rest, its hover and pressed faces; close is a normal button that hovers in the accent.
  - `linked` (**xl-Cheeselooks Linked**): `drawn`'s buttons joined into one group: no gap, one shared border between neighbours (each button draws its left edge, the last its right one too; the hovered or pressed button's border colour goes on the edge it shares), rounded only at the group's two ends, close hovering in the accent. The recess and drop shadow go round the whole group, split between the buttons by position: the recess's dark strip along the top of every button and the left of the first, its light strip along the bottom and the right of the last; a drop shadow pulled in at the sides by its blur so it doesn't spill onto the next button. (A box round the buttons only fitted a header bar exactly the title bar's height; taller ones, such as one holding an Apply button, left a gap under the group.) GTK 3's 6px header bar spacing is cancelled with a negative margin. Muffin's window borders get the joined faces from the button layout (first / middle / last per function) but, as for every style, no outer layers.
  - `classic` (theme xl-Classic): small square buttons drawn like `drawn`, with the style's own button face, border, hover, pressed state and gradient (split or glass included); close hovers like the other two (not in the accent). They're smaller than `drawn` (a square face of 0.72 × the control height, at least 18px), 4px apart as in Clearlooks (GTK 3's own 6px between window buttons is cancelled), with a click area 2px larger at the sides and 4px above and below, and Button roundness 25 by default. (Until v1 they were fixed squares in the title bar's colour, as Clearlooks.)
  - `dots`: red / yellow / green 16px dots (16px so the face holds GTK's 16px icon node exactly, which keeps the glyph centred; their outline is an inset ring), grey for other buttons and unfocused windows; the glyph shows on the hovered dot (window managers can't show it on all three at once).
  - `gargantuan`: borderless faces (a transparent border left a 1px strip of title bar round them), wide (1.16 × title bar height), full-height buttons with no gap, flush with the window edge, with thin 1px glyphs at 150% of the theme's (minus, square, two squares for restore, ×); the style's hover face, close in the accent; close's outer top corner follows the window's roundness (square when maximized or tiled).
  - `gargantuan-circles` (**Less Gargantuan**): the same wide, full-height slots (the whole slot is clickable), with a larger circle (0.8 × title bar height) on hover.
  - `unpretentious` (**Unpretentious**, was Arrows): circles at rest (title bar tinted toward the text), chevron glyphs (down = minimize, up = maximize, a diamond = restore, ×), close hovers in the accent.
  - `unpretentious-flat` (**Unpretentious Flat**, was Arrows Flat): the same, with no circle until hover.
  - `claude` (theme Claude): muted glyphs at rest; on hover a soft squircle with a short accent bar under the glyph, echoing the claude tabs; close fills with the accent.

  **Glyphs** (`window_borders.button_glyphs`, the picker above Button style: joined buttons, each showing its set's minimize, maximize and close glyphs, the name as a tooltip): **Regular** (Mint-Y's window button artwork, GPL-3+, redrawn as our own filled SVGs; `theme` in older settings is converted), **Thin** (1px lines, generated at each style's glyph size so they stay crisp), **Chevrons** (⌄ ⌃ × and ◇ for restore), **Marks** (× – +) and **Icon Theme** (GTK draws the icon theme's `window-*-symbolic` glyphs itself; for Muffin's window borders Apply copies them from the icon theme, following its Inherits, in the glyph colour, falling back to Regular when one is missing). `null` (the default) means the style's own set: Marks for Dots, Thin for the Gargantuans, Chevrons for Unpretentious, Regular for the rest. Glyph SVGs are written at the size they're shown (GTK 3 rasterises an SVG at its own size before scaling it, which blurred 16px glyphs shown at 24 on the Gargantuans). Unlike Button roundness, your choice stays when you change button style. Odd pairings are allowed. Every set but Icon Theme is drawn by us, so apps, window borders and the picker match.

  **Button roundness** (`window_borders.button_roundness`, 0–100, the slider under Button style): how round the faces are, as a percentage of fully round, like the global Roundness. `null` (the default) means the style's own: the theme's Roundness for xl-Cheeselooks and xl-Cheeselooks Flat, Classic 25, Claude 60, Gargantuan 0, and 100 (circles) for Dots, Arrows, Arrows Flat and Less Gargantuan. The slider shows that value until you move it; picking another style puts it back to that style's own. Below 100, circles become rounded squares; Gargantuan's close keeps its window-corner rounding.

  **Click area vs face:** Classic, Dots, Arrows, Arrows flat, Claude and Gargantuan circles draw a face smaller than the button, so the area you can click reaches a few px past the face (3–5 px each side) and covers the gaps. In GTK the face is drawn on the button's icon node, held to the face size by margins; the button itself draws nothing. Faces are even-sized and glyphs are placed in whole pixels (a glyph on a half pixel is blurry).

  Our own glyphs (chevrons, the dots' marks, Gargantuan's thin glyphs) are generated SVGs in the title colour and shown in GTK as a background layer over a hidden icon. In GTK every state of a style is built the same way, so hover fades between like things: circles are the button itself (a round border box with a background colour, never a radial gradient), flat faces are background colours, and the claude bar is a layer in every state (clear when hidden), faded from a clear version of the same colour rather than `transparent`. Fading between differently built backgrounds flashed: a dark ring around circles, an accent wash behind the claude bar (Mint-Y also sizes title button backgrounds at 80px, so every state sets its own size). Old names are migrated (`theme` → `flat`, `wide` → `gargantuan`, `circles` → `arrows`).
- Window shadows are drawn by Muffin and are out of the theme's reach.

### Terminal
- **Switch off:** follows the theme (light theme, light terminal).
- **Switch on:** the user's background and text, plus Terminal presets.
- **Implementation:** a `vte-terminal` rule in the GTK CSS. Checked with VTE the way GNOME Terminal's "Use colors from system theme" reads it (the terminal widget's GTK colour and background). This only takes effect when the terminal profile uses system theme colors, which is GNOME Terminal's default on Mint. The README must say so.

### GTK 4 / libadwaita (colors only)
- The generator writes a **marked block** into `~/.config/gtk-4.0/gtk.css`, between `/* xl-cheeselooks begin */` and `/* xl-cheeselooks end */`. The libadwaita named colors go there as both `@define-color` and `:root` variables.
- Anything the user wrote outside the block is preserved. A backup is made the first time.
- Colours: accent and destructive (backgrounds use the palette colours; `accent_color` and `destructive_color`, used as text, are darkened or lightened until they read at 4.5:1 on the window background), window, view, headerbar, sidebar, card, dialog, popover. libadwaita 1.5 and older take `@define-color` names; 1.6 and newer CSS variables, which are added only when the installed libadwaita (`dpkg-query libadwaita-1-0`) is 1.6+, since older GTK 4 warns on them. Template: `templates/libadwaita.css.part`; code: `cheeselooks/gtk4.py`. `revert` rewrites the block from the restored settings.
- The GNOME `accent-color` key exists from GNOME 47; on Mint 22 (GNOME 46 schemas) it is skipped quietly.
- **Mint's libadwaita reads themes.** Mint ships a patched libadwaita (`1.5.0-2mint3`, github.com/linuxmint/libadwaita) that loads `<theme>/libadwaita-1.5/` from the GTK theme: `base.css` (or `base-hc.css` for high contrast) plus `defaults-light.css` or `defaults-dark.css` (dark falls back to light; no folder falls back to stock). xl-Cheeselooks ships that folder: Mint-Y's `base.css` (GPL-3+, `templates/libadwaita-1.5/mint-base.part`) with its round title buttons replaced by ours, and both defaults files generated from the palette (`colors.part`, shared with the gtk.css block), so either variant gets your colours. `libadwaita-1.7` (Mint 23) can be added the same way when needed. Its `base.css` is Mint-Y's plus the GTK 4 layer (`templates/gtk-4.0/xl.css.tmpl`, included as is, so libadwaita and plain GTK 4 apps get the same buttons, entries, checks, switches, title buttons and selection) plus libadwaita-specific rules: the title bar gradient on toolbar views' top bars (libadwaita paints the bar behind transparent header bars), and cards and boxed lists at the window radius `r2` instead of a fixed 12px. Also: libadwaita's tab bar (AdwTabBar) in the style's tab look (`tabs.adw_css`: boxed and open tabs sit on the page with the selected-tab marker, pills float); no circle behind title-button icons (Mint draws one on an inner image node); overlay toolbars (`.toolbar.osd`, e.g. media controls) keep their dark look and see-through buttons. In GTK 3 too, hover fades colours and gradients only and switches shadows at once: GTK 3 garbles a blurred shadow while animating between two blur sizes (blocks and streaks round the widget when the hover shadow is bigger than the resting one). In GTK 4 the hover transition animates colours only: a gradient can't animate and switches at once, so a shadow fading on its own left a ring behind flat buttons. The GTK 4 layer's button rules exclude `.osd` (dark overlay buttons keep their colours), leave `.opaque` buttons without a gradient (their colour comes from the app), keep `.circular` and `.pill` round, set a 1px solid border (libadwaita buttons and entries have none), and leave entries and spin buttons inside list rows frameless. Preview without Mint's patched libadwaita: load `defaults-light.css` + `base.css` as the user gtk.css under `adwaita-1-demo` (user priority then outranks app CSS, so app-coloured "opaque" buttons look white in the preview only). Plain GTK 4 apps (not libadwaita, e.g. awf-gtk4) use the theme's `gtk-4.0/` folder:
  - `base.css.tmpl` is Mint-Y's GTK 4 stylesheet converted by `tools/convert_gtk4.py` (the GTK 3 converter's rules with Mint-Y GTK 4's reference colours: bg #F8F8F9, text #303030, accent #35A854; the accent's shades become `lighter`/`darker(accent)`; Mint-Y's bluish greys count as greys; the green check, radio and switch images are removed).
  - `xl.css.tmpl` is the GTK 4 version of the GTK 3 layer, with the same tokens: GTK 4 node names (`windowcontrols > button`, popover menus' `modelbutton`, `menubar > item`), no `-gtk-outline-radius` (GTK 4 warns), focus rings on `:focus-visible`, and checks in popover menus drawn as ordinary check nodes.
  - `gtk-dark.css` imports `gtk.css`: your palette decides light or dark.
  - **Blur:** GTK 4 draws a box-shadow blur about half as wide as GTK 3 for the same value, so every edge is also written with the blur doubled (`w.<widget>.g4_shadow`, `g4_inset_shadow`, and `tabs4.css`); the GTK 4 and libadwaita templates use those. Measured on xl-Classic's button: with the doubled blur the GTK 4 highlight and shade fade like GTK 3's. GTK 4.14's default GPU renderer (`ngl`, what Mint users get on real hardware; cairo is the fallback without a GPU) draws partly transparent light inset shadows as solid white whatever their alpha (it treats the colour as premultiplied), so GTK 4 inset layers are written as solid colours: the widget's face with the layer blended in, which every renderer draws the same. Black and outer shadows are unaffected. Test renderers with `GSK_RENDERER=ngl|gl|cairo`. Checked with gtk4-widget-factory, light and dark palettes, no CSS warnings.
- An option in the app turns this off.
- **libadwaita accent:** the generator also sets GNOME's `accent-color` key (`org.gnome.desktop.interface`) to the named color nearest the user's accent (blue, teal, green, yellow, orange, red, pink, purple, slate). That gets libadwaita apps that ignore custom CSS close to the accent. It can be turned off in the app.

### Flatpak apps
- Flatpak apps can't see `~/.themes` (GTK 3 and GTK 4 themes) or `~/.config/gtk-4.0/gtk.css` (the libadwaita colours) by default. `cheeselooks flatpak --enable` (the app's button later) shows and, after a yes, runs `flatpak override --user --filesystem=~/.themes:ro --filesystem=xdg-config/gtk-4.0:ro`: read-only, for all Flatpak apps. Apps learn the theme's name from Cinnamon's XSettings, so nothing else is needed. It records which of the two entries it added (`~/.config/xl-cheeselooks/flatpak-added`); `--disable` removes only those from Flatpak's user override file (`~/.local/share/flatpak/overrides/global`), keeping every other override, including a `~/.themes` grant you made yourself (`flatpak override --reset` would wipe them all). `cheeselooks flatpak` shows the state. Tested with Flatpak 1.14.
- Flatpak libadwaita apps use their runtime's libadwaita (often 1.6+, upstream: colours only), so the gtk.css block always includes the CSS variables too; GTK 4.14 accepts them without warnings.

### Details tab
Fine-grained overrides. Each row has its own switch. **Off** means the item follows the theme; **on** reveals its controls, pre-filled with the theme's current values.

| Item | Controls when switched on | Default when off |
|---|---|---|
| **Tooltips** | Background and text color pickers; presets *Follow menu* and *Classic yellow* (`#FBEAA0` / `#303030`) | Menu colors (`menu_bg`, `text`) |
| **Scrollbars** | *Thin overlay* or *Classic* switch; Roundness slider | Overlay, fully round thumb. When set, `apply` also turns Mint's "Use overlay scroll bars" (`org.cinnamon.desktop.interface gtk-overlay-scrollbars`) on or off to match; when not set, the theme follows that switch |
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
- **README and GitHub pitch: include this line** (xl_cheese's request), in a section on colours / the style tester:
  > "Decent" is a floor, not a promise. On a truly clashing scheme the tool can keep things readable and usable, and it already warns about poor text contrast. But it can't make ugly colours pretty. That part stays the user's choice.
- README notes to remember: Mint's Themes window doesn't refresh while open (reopen it to see the new name and thumbnail); the terminal follows the theme only when its profile uses system theme colours (GNOME Terminal's default on Mint).
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
| **v1.x** | Accent from wallpaper. More window button styles. Float shipped as a selectable style. Import/export polish. **Full styling for Flatpak libadwaita apps** (opt-in, off by default; **built 20 Nov**: Integration → "Full styling for libadwaita apps", `integration.libadwaita_full`; the gtk.css block then also carries the GTK 4 layer (`gtk-4.0/xl.css.tmpl`) and the libadwaita additions (`libadwaita-1.5/adw-extra.part`, split out of the theme's `base.css`), with its pictures copied to `~/.config/gtk-4.0/xl-cheeselooks-assets/` (readable by Flatpak apps through the Flatpak apps switch); tested with an unpatched libadwaita 1.5 window: buttons, title buttons, entries, switches and checks in the style. Found: a button an app colours with its own class gets our face but kept the app's text colour (white on white), so the block starts with `button:not(.opaque) { color: text; }` (least specific, our own rules still win; libadwaita's `.opaque` buttons keep the app's colours). Trade-off stays: app-coloured buttons lose their colour. On xl_cheese's Flatpak Calculator (newer libadwaita): it works; window buttons came out 33px for a 26px style, since current libadwaita's 47px header bar (6px padding above, 7 below) stretches them over the 34px between: the block adds vertical margins worked out from each style's button height (`gtk4._window_button_margins`; 3px for xl-Gummy, none where the style is already that tall), harmless where buttons aren't stretched. Also found: picking a theme reset the Integration switches to the theme file's values; Integration is per-user (`settings.PER_USER`), so picking a theme, Reset All and `apply --theme` now keep yours): Flatpak apps use upstream libadwaita, which ignores themes, so v1 gives them colours only. The whole libadwaita layer could go into the shared `~/.config/gtk-4.0/gtk.css` block instead; trade-offs to test first: that file outranks an app's own CSS (app-coloured buttons lose their colours), and it also applies to apps from Mint's repositories on top of the theme folder |
| **Release** | The **xl-Claude** style (done: `styles/xl-Claude`, soft paper buttons with a faint top light and a border that warms on hover, terracotta focus ring, menus hovered with a light accent tint and dark text, `claude` tabs, a panel a shade darker than the windows with outline-free paper-chip buttons and a line marker; roundness 35, gradient 10, depth 45), with a **Claude** preset (done: `presets/global/claude.json`, warm ivory #F4F2EC, warm charcoal #2E2A25, terracotta #B85A38; text 12.7:1, white on the accent 4.6:1) and the `claude` tab kind, both designed by Claude |
| **Release** | **Dark styles.** Light-theme habits don't carry to dark, so dark looks get their own styles rather than one style serving both. First: **xl-Claude-Dark** (done: `styles/xl-Claude-Dark`) with the **Claude Dark** theme (done: `data/themes/5-claude-dark.json`, warm charcoal #2A2925, warm ivory text #EAE6DD, terracotta #D97757, Claude title buttons). What dark needed: outlines in dark ink (`darker(bg, .42)`), darker than the surface, instead of light grey lines (they look like wireframes); a faint top glint (white 7%) with a stronger drop shadow (black 30%) doing the lifting; hover borders warmed toward the accent; fields and checks in a darker well, with checks, radios and switches given their own visible outline (`mix(bg, text, .34)`), since the field's ink outline vanishes on a dark field; menus hovered with a stronger accent tint (24%); a panel darker than the windows (`darker(bg, .28)`) with soft chips. Generator fixes found on the way: `pressed` goes darker on dark; lists set their text colour (a light system theme's black showed through in the app's preview). Then **xl-Cheeselooks-Dark**, **xl-Classic-Dark** and **xl-Gummy-Dark** (done, xl_cheese's styles with dark tuning by Claude) with the themes **xl-Cheeselooks Dark** (#2C2C2C / #E6E6E6, xl-Cheeselooks Flat buttons, title gradient 10), **xl-Classic Dark** (#2F2F2F / #E4E4E4, Classic buttons, 15) and **xl-Gummy Dark** (#323232 / #EBEBEB, xl-Cheeselooks buttons, 15), all with the coral #FA8562. Each keeps its light sibling's character (Cheeselooks muted with a faint top and side glint; Classic's soft blurred bevel, with the shade below and right doing more of the shaping, and accent menu hovers; Gummy crisp, split gradient, glow marker, accent scrollbar) and gets the same dark treatment as Claude Dark: ink outlines, faint lights, stronger shadows, hover borders brightening toward the text (tabs included), visible check outlines, a darker panel with soft chips. Claude Dark's title gradient is 10. Second pass on xl-Claude-Dark (19 Nov), with the newer tools: terracotta and red buttons get a dark rim (`darker(accent, 0.45)`, `darker(destructive, 0.45)`; also the close button's terracotta hover), and the Cinnamon main menu hovers with the same warm tint as the other menus (`[panel]` `menu_hover = mix(menu_bg, accent, 0.24)`, a stronger `menu_category` at 0.42; light xl-Claude got the same, at 0.14 and 0.28, matching its own menu hover). Ink `dividers` were tried and dropped: the notebook frame, the selected tab's outline and the line under the header bar vanished against the dark pages. Later the three xl dark styles were replaced by xl_cheese's own tuned versions (`data/themes/06`–`08`). Accents retuned by xl_cheese after seeing folders in them (20 Nov): xl-Cheeselooks #FF8467 (also the Tool's built-in default accent), xl-Cheeselooks Dark #DA7259. Mint-Y's own borders in `base.css` (list frames, progress troughs) are still lighter than the surface on dark |
| **v2** | **Icons tab**: a matching icon theme, folders in the theme's accent (see *Icons tab* below); more original styles; in-app style editor |
| **Later (lowest priority)** | **GNOME / Ubuntu.** (1) *Apps only:* GTK 3 and plain GTK 4 themes already work on any desktop; the tool needs to detect GNOME and use its settings (`org.gnome.desktop.interface gtk-theme`, accent-color) instead of Cinnamon's. Window title bars there come from the GTK 3 headerbar rules (Mutter ignores `metacity-1/`). libadwaita apps get colours only (the gtk.css block and the accent key): upstream libadwaita doesn't read themes, which is a Mint patch. (2) *Desktop:* a GNOME Shell theme (`gnome-shell/gnome-shell.css`, loaded through the User Themes extension); same St CSS dialect as Cinnamon but different class names, so a new template about the size of the Cinnamon one |

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
- *(done)* **Icon and theme thumbnails:** a static silky swirl (`data/icons/xl-cheeselooks.svg`, drawn by `tools/make_icon.py`: about 520 fine strands over a soft blurred wash, winding into an eye at the lower right with a broad wave further out; colours blend round a loop of hues with green in it and some darker strands; seeded, so it's reproducible). The theme thumbnails (what Mint's Themes settings shows, 120x35 as Mint-Y's) are xl_cheese's comet: the icon's swirl with its strands streaming left (`data/thumbnails/comet-source.webp`, made into the 120x35 master `comet.png` by `tools/make_thumbnail.py`, near-white wisps made see-through so it sits on dark buttons too). At Apply `cheeselooks/thumbnail.py` recolours it toward the theme's accent (each hue pulled most of the way to the accent's, `KEEP` 0.12 of its distance kept for a little variety; lightness, saturation and transparency as painted; GdkPixbuf) and writes it into gtk-3.0, cinnamon and metacity-1; the templates hold the rainbow master as the fallback. Cinnamon settings frames the Applications and Desktop thumbnails in a GtkFrame inside the button; our GTK 3 CSS drops that frame's border (`button > box > frame > border`), so the comet sits on the button as icon and pointer pictures do.
- **xl-Claude extras, with the title button styles:** (1) a `bar` active marker of Claude's design: a short accent bar centred under the focused window's panel button (and the tab's outer edge), echoing the `claude` tabs. Cinnamon can't draw a short centred gradient and allows one shadow, so it needs a small generated image at the bottom centre; St also can't put an image over a gradient, so the focused button drops its gradient. Needs testing on a live panel. (2) Done: the `claude` title button style.
- **Short-term roadmap: notification popups** (step 1 done; step 2 next) (asked by xl_cheese). Plan, in two steps: (1) `line`, `flat`, `bordered` and the opacity control (plain CSS, low risk); (2) `claude` together with the panel `bar` marker, since both need the same small generated accent-bar image (via the `file:` tokens, rebuilt on every Apply) and one round of live testing on Cinnamon covers both. A `claude` popup has a flat background (St can't put an image over a gradient). If step 2 proves fiddly on a live panel it can be dropped without affecting step 1. Cinnamon's notification popup currently has an accent line along the top (like Classic's tabs). Add a style setting for it, e.g. `[notification] kind = "line"`, with: `line` (today's look), `flat` (no accent), `bordered` (a thin accent border all round) and `claude` (the short rounded accent bar at the top centre, as on claude tabs; St allows one shadow and no short centred gradient, so it likely needs a small generated image, like the planned `bar` panel marker). Plus an **opacity** control for the popup (xl_cheese likes a little transparency), probably on the Panel & Menu tab next to Menu opacity. Built-in styles pick their kind (Classic `line`, Claude `claude`).

## Settings app (v1, step 6)
- `bin/cheeselooks-settings` (`cheeselooks/app.py`), GTK 3 + Python like Cinnamon's own settings tools; launcher `data/io.github.xlcheese.Cheeselooks.desktop`. Sidebar tabs: Global, Style, Panel & Menu, Window Borders, Terminal, Details, Integration, Import & Export.
- **Themes** (`cheeselooks/themes.py`): a theme is a complete set of settings pointing to one style; many themes can share a style. Built-in themes are `data/themes/*.json` (xl-Cheeselooks, xl-Classic, xl-Gummy in coral, and Claude); yours are in `~/.local/share/xl-cheeselooks/themes/`. The Theme tab (first) holds the theme list, as tall as the window allows: picking one sets every tab. Changing anything turns it into **Custom** (`~/.config/xl-cheeselooks/custom.json`, remembering the theme it started from), which comes back when you pick Custom again. **Save Theme…** (only on Custom) names it as your theme; **Delete Theme** removes one of yours. Each tab's **Reset to Theme Defaults** puts that tab back to the theme it started from; when nothing differs any more, the theme is no longer Custom. Picking a style on the Style tab only changes the style (the theme carries the other values). Theme and Style lists (done): a **Sort** dropdown above each (A–Z, Z–A, Newest, Oldest; A–Z is case-insensitive with numbers in order; Newest and Oldest go by the file's modified date, built-in ones by when they were installed or updated), remembered in `~/.config/xl-cheeselooks/app.json`; Custom stays last, its subtitle naming the theme it's based on ("Your latest changes, based on …"). Names longer than fit end in "…" with the full name as a tooltip, so a long name can't widen the window. Theme names are limited to 40 characters when saved (imported longer names are shortened, with a note); the style checker warns about style names over 40. **Save Theme…** opens with the name filled in and selected: your theme's own name (Enter saves over it, after a Replace? confirmation), or "<name> copy" for a built-in theme, which can't be replaced; its dropdown lists your themes to save over. **Duplicate Theme** saves a copy of the selected theme, built-in or yours, as one of yours ("<name> copy", "copy 2"…), and switches to it. **Rename Theme** renames one of yours. Both refuse a name that's taken, empty, "Custom" or over 40 characters, saying why in the dialog; a rename carries over to Custom's "based on".
- No on/off switches: "own colors", "customize" and "follow Global" stay in settings.json but aren't shown; changing a setting behind one turns it on (Follow Global off) by itself, and the tab's Reset button puts it back. Optional colors show "Follow theme" until set, then their hex and RGB. Choices with up to three options are inline buttons. The old colour presets (Coral, Ocean, Marigold, Sea Glass, Steel Blue, Midnight Violet, Coral Night, Anything Goes) aren't shown; they stay for the command line and their names are kept for future themes. The Terminal tab keeps quick picks (Theme default, Paper, Charcoal, Midnight, Green Screen). Depth stays on the Style tab. **Reset buttons** (done) name their tab: Reset Style, Reset Panel & Menu, Reset Window Borders, Reset Terminal, Reset Details; each puts only that tab back to the theme you started from. Global has **Reset Global** and **Reset All to Theme Defaults** (every tab, no confirm: your latest changes stay in Custom, one click away, until you change something else). Integration has none (two switches; Flatpak access is a change to the system that resetting the setting wouldn't undo). Theme names go in the tooltips, not the labels (names can be long). Global's tooltip notes that other tabs' “Follow theme” colours and follow-Global shapes change with it.
- **The window is the preview:** every change regenerates the theme into `~/.cache/xl-cheeselooks/preview` (about 45 ms) and loads its GTK 3 stylesheet into the app only; plus a sample window and a drawn panel.
- **Apply** (header bar, at the outer edge opposite the window buttons) writes the theme to the desktop and switches to it if needed. A **Revert** button then appears next to it; it puts the previous desktop theme back (`cli.revert_desktop`), keeps the app's settings, and hides again. No auto-apply and no timed Keep/Revert dialog (decided: the preview already shows the result, and a dialog would be drawn in the new theme).
- **Import & Export:** one `.xltheme` file (a zip): `theme.json` with the theme's name, the format and tool version and its settings, plus the style folder when the theme uses one of your own styles. Importing a newer format warns; name clashes get " (2)"; an existing style folder of yours is kept. Command line: `cheeselooks themes`, `apply --theme NAME`, `export-theme NAME [FILE]`, `import-theme FILE`.
- Later: dark-tuned style variants (xl-Cheeselooks-Dark, xl-Classic-Dark, xl-Gummy-Dark, with their own `alpha_dark` values), and built-in themes reusing the old preset names.

## Window borders on Mint 22 (Muffin 6)

Cinnamon's window manager no longer reads `metacity-1/`: Muffin 6 draws window
borders from the GTK 3 theme's CSS, through its own style contexts
(`window.background.ssd > decoration > headerbar.titlebar.default-decoration >
button.titlebutton.{close,maximize,minimize} > image`). It sizes the buttons
from the button's min size, padding and border plus the image node's padding,
border and margin; puts a fixed 6px between buttons plus their margins; draws
only the button node's background and frame (never the image node); and draws
the icon theme's `window-*-symbolic` glyph at 16px in the button's colour.

So the GTK 3 title-button CSS has a Muffin block (`.ssd
headerbar.default-decoration`, in `titlebuttons._muffin_css`): title bar height
and side padding, button size, a margin that takes the 6px back, and, for
styles whose face is on the image node in apps (Classic, Dots, Unpretentious,
Claude, Less Gargantuan), the face drawn on the button as an SVG, with the face's box-shadow layers (recess, drop shadow, inner highlights) drawn into it (`shadowed_face_svg`). Linked gets
its corners per function (no siblings in Muffin's path). `metacity-1/` is still
generated for Metacity and Marco. `tools/muffin-preview.py THEME OUT.png` draws
a title bar the way Muffin does (rest, hover, pressed, unfocused).

Spacing between window buttons: each style's own gap plus Button spacing (see
Window Borders), the same in GTK 3 and GTK 4 apps and on Muffin's borders. Gargantuan buttons in apps are at least 46px tall: GTK centres
window buttons in a header bar, and Mint-Y's 6px margins on its other buttons
hold it at 46px, so a shorter button left a strip above. GTK 4 windows take the
same outline and shadow as GTK 3 ones (`window.csd` in gtk-4.0/xl.css).

## Shipped themes and the torture test

Built-in themes (`data/themes/NN-*.json`, listed in file-name order, so two-digit numbers): xl-Cheeselooks (the default), xl-Classic, xl-Gummy, Claude, Claude Dark, xl-Cheeselooks Dark, xl-Classic Dark, xl-Gummy Dark, then the novelties xl-Vintage (OS/2 Warp: hard square bevels, grey buttons on an indigo title bar, its own style) and xl-Organ Harvest (the xl-Cheeselooks style in amber and teal with Gargantuan buttons). The light ones are xl_cheese's own tuning; the shipped style sheets have every white layer given an `alpha_dark` and every recess a `light_alpha_dark` (so they don't glare on dark title bars), hovers in `lift()`, and no switched-off layers.

`tools/torture_test.py [STYLE_DIR ...]` builds each style (all built-ins by default) against its own shipped theme, a dark theme and a colored title bar; runs GTK's parser on each GTK 3 CSS; checks key pairs read (text on bg and base, accent text on the accent, title text on the title bar, text on title-bar buttons, menu and panel text); and draws a contact sheet of a sample window in each (`--out`, default torture.png).

- **Icons tab, step 1 done (20 Nov): Mint-Y's places icons as SVG.** Mint-Y-Blue and the other colours are 18 icons (folder, documents, download, drag-accept, music, pictures, publicshare, recent, saved-search, templates, videos, gtk-network, network-workgroup, user-bookmarks, user-desktop, user-home; user-trash and -full are Mint-Y's own, uncoloured) at 16, 22, 24, 32, 48, 64, 96, 128 and @2x, shipped as PNGs (`Inherits=Mint-Y,Adwaita,gnome,hicolor`). Mint draws them all on one sheet (`src/places/src.svg` in linuxmint/mint-y-icons) and makes each colour by swapping four colours (`generate-color-variations.py`): folder `eeca8f`, backfolder `c89e6b`, paper `e8e8e8`, emblem `575757` (Blue: 5294e2 / 4877b1 / e4e4e4 / 1d344f; there's also a Yaru variant). `tools/import-mint-y-places.py` cuts the 128 icons (16 names × 8 sizes) out once, using Inkscape only for each icon's box, into `data/icons/mint-y/places/<size>/<name>.svg` (~600 KB), each with just the layers' positioning and the definitions it uses; checked against Inkscape's own export of the sheet: average difference under 0.1/255. Licence: the icons are CC BY-SA 4.0 (Sam Hewitt, Alexey Varfolomeev), credited in `data/icons/mint-y/COPYING`. **Step 2 done (20 Nov): the Icons tab** (between Details and Integration; "Icons", as Mint's Themes settings calls them). **Off by default** (xl_cheese: a first look at the Tool shouldn't change icons people chose in Mint's settings; you start on the Theme tab). Settings `icons.enabled` (per-user: stays when you pick a theme, `settings.PER_USER` now takes setting paths), `icons.folder_color` (default: the accent) and `icons.second_color` (choosing either folder colour in the app pins the other at the colour it showed, so both stop following the theme together, xl_cheese: a blue front over a red accent keeps its dark red back; Reset Icons follows again) (the back and tab; default `icons.back_shade` **of the accent**, not of the folder colour, so a grey front keeps an accent back, Yaru's 24.04 look, xl_cheese: fitted to Mint-Y's twelve colours, lightness 0.15 lower and saturation ×0.8, at least 1.6 contrast from the front: Mint's own average 1.7, our first `darker(folder, 0.16)` only 1.4, too close, xl_cheese); paper `#E4E4E4` as Mint's; the emblem `darker(folder, 0.72)`, or near-white where that wouldn't read at 3:1. At Apply (`cheeselooks/icons.py`): the 128 SVGs recoloured as text into `~/.icons/xl-Cheeselooks/places/<size>` (beside `~/.themes`, the traditional places Mint users use; both are searched; the first version's `~/.local/share/icons` copy is removed) and `<size>@2x`, an `index.theme` inheriting your previous icon theme first, then Mint-Y, Adwaita, gnome, hicolor (so every other icon, and the trash, stays yours), the CC BY-SA credit (`COPYING`) alongside, `gtk-update-icon-cache`; Cinnamon's icon theme set to it, your previous one remembered (`~/.config/xl-cheeselooks/icons.json`) and put back when switched off (ours removed). The tab previews the folders at 48 and 24px, live. Mint-Y's other names for these icons are symlinks in each size's places folder (`nemo`, `file-manager`, `system-file-manager` and 14 more → `folder`, `folder-open` → `folder-drag-accept`, `desktop` → `user-desktop`…; 232 over the 8 sizes, recorded by the import tool in `data/icons/mint-y/aliases.txt`), which Mint's colours copy; ours are made at build too, so the Files app's icon on the panel is the recoloured folder (xl_cheese saw his previous theme's there). Checked: GTK finds ours at each size and @2x, and others through the inheritance. **Folder styles (20 Nov): Mint-Y and Yaru**, one shared path (`icons.STYLES`: each style's SVG folder, sizes and placeholder colours; recolouring, writing, aliases and inheritance are common), picked on the tab with a picture of each style's folder in your colours (72px; a selected frame; four to a row at most, more wrap to the next; xl_cheese), under "Folder style: Yaru" (`icons.style`, per-user like the switch). Per-user settings are ignored when the app decides whether your settings are still a named theme or "Custom" (`app._same`): they made every theme show as Custom. Papirus was checked and dropped: Mint-Y's folders are Papirus's drawings (same paths and colours from 22px up). **Yaru**: Ubuntu's sheet (`icons/src/fullcolor/accented-full/places/folders.svg`, CC BY-SA 4.0) draws each icon in a group with a "Baseplate" layer of boxes per size (16, 24, 32, 48, 256; the 256 box is mislabelled 48x48) and the icon's name as text; its build renders each box's area with placeholder colours (`#00ff03` accent, `#008502` darker accent) swapped per accent (`common/colorize-dummy-svg.py`). `tools/import-yaru-places.py` cuts each box (the icon's group cropped to it, drawings for other sizes dropped) into `data/icons/yaru/places/<size>/<name>.svg` (14 icons × 5 sizes, 1.2 MB), and marks the front and back apart by their layers ("Folder (Front Section)", "Folder (Back Section)"; the back's "Darken Overlays" as `backdark`), so front and back take your two colours though Yaru's own are one; checked against Inkscape's render of each area: identical. Current Yaru (2026) is all-accent; Ubuntu 24.04's was a grey front on an accent back, which is now just a grey Folder color. Yaru lacks a drag-accept folder (its open folder stands in, `icons.EXTRA_ALIASES`) and the network, bookmarks, recent and saved-search icons (inherited). **What you choose is what you see** (xl_cheese's GIMP check, 20 Nov: our Yaru front came out #FF967E for an #FF8467 accent). Yaru's layers change the colours under them: a white veil on the front (seen = 38 + 0.851 × drawn, measured by rendering, the same at 24px and up), and darkening layers on the back. The front's veil is worked backwards (`icons.underneath`, `STYLES[...]["seen"]`: #FF8467 is drawn #FF6E4C); the back's darkening layers, there to darken Yaru's single colour at the back, are given the back's own colour (`backdark` 0), so your second colour shows exactly, light or dark (a light back couldn't be reached through them). Checked by rendering: chosen = seen within 2/255 (a test). **The default back** now follows xl_cheese's own coral Yaru folders (#FF8467 front, #D44231 back): lightness −0.19, saturation ×0.64, hue turned 5° (`icons.back_shade`; #FF8467 → #D24433), still at least 1.6 contrast; for every style. **Breeze (20 Nov)**: KDE's folders (github.com/KDE/breeze-icons, `icons/places/<size>/`; LGPL 3+, the licence and its LGPL text in `data/icons/breeze/COPYING`). Breeze draws each size by hand in its own file, so `tools/import-breeze-places.py` copies rather than cuts: 12 icons (folder, documents, download, music = Breeze's folder-sound, open, pictures, publicshare, recent = its folder-temp, templates, videos, network-workgroup, user-home), each a single accent shape (`ColorScheme-Accent`) with the back darkened by a black 33% layer, thin white and dark edge lines, and the picture in the text colour at 60%. Marked: accent → `#3daee9` (front), the 33% layer → `#3dae09` solid (back: your second colour exactly, no veil to work backwards), the picture → `#3dae39` solid (emblem); the edge lines stay. Colour drawings exist at 32, 48, 64, 96px; Breeze's 16 and 22px folders are one-colour outlines, so the 32px drawing stands in at 16, 22 and 24 (84 SVGs, 120 KB). Breeze's desktop is a monitor, not a folder: left to your icon theme. Its open folder stands in for drag-accept. The window's least height is now measured at the width the tabs get (`get_preferred_height_for_width`): at their least width the folder style pictures stacked one per row and the window opened 90px too tall. **Every style covers Mint-Y's set (20 Nov, xl_cheese):** a name a style doesn't draw showed the previous icon theme's icon, in other colours (Breeze's Desktop). Mint makes all its places icons one way, a folder with a picture on the front, so we do the same: first a style's own drawing under another name (Breeze: folder-desktop for user-desktop, folder-bookmark for user-bookmarks, folder-network for gtk-network; a size it skips takes its next size up; newer Breeze files set colours as attributes, read too); otherwise `tools/compose-missing-places.py` (run after the import tools) puts Mint-Y's picture for that icon on the style's plain folder, in the style's picture colour, centred where the style puts its own (the picture of its folder-documents, found by rendering; a square as big as its longer side; each Yaru icon has its own place on Ubuntu's sheet, so boxes are taken from each icon's corner; Yaru's picture is see-through and its colour also marks a line at 256px, so only its main shade counts). Where a style draws no pictures at a size (Yaru's 16px), its plain folder. Made: Yaru's recent, saved-search, gtk-network, network-workgroup, user-bookmarks (25), Breeze's saved-search (7); credited in each style's COPYING (CC BY-SA 4.0, Mint-Y). drag-accept stays the open folder. A test checks every style has every Mint-Y name at every size. **Reloading icons:** rebuilding the theme under the same name didn't tell apps (Nemo kept the previous folder style until reopened; the panel had reloaded); Apply now switches the icon theme to a hidden link to it and back (`icons._reload`, as the GTK theme's reload). **Apply** lights up for per-user changes too (folder style, the Icons switch, Integration): they don't make a theme Custom, but they need an Apply. **Adwaita (20 Nov)**: GNOME's folders (github.com/GNOME/adwaita-icon-theme, `Adwaita/scalable/places`; CC BY-SA 3.0, one of GNOME's two licences, credited in `data/icons/adwaita/COPYING`). Its look is a pale front on a strong back with outline pictures in the back's colour; xl_cheese chose our usual roles instead (front = folder color exactly, back = second color, picture by the emblem rule), so a GNOME look is a light folder color. GNOME draws each folder once at 128px; shrunk, its edges fall between pixels and its pictures go under a pixel (soft at 16-24, where GNOME's own apps use symbolic icons). `tools/import-adwaita-places.py`: every file is back (#438de6, first), front edge gradient (#62a0ea, shine #afd4ff/#c0d5ea), front (#a4caee), picture (#438de6 after the front), marked `438d0e` / `62a00e` / `afd40f` / `a4ca0e` / `438d1e` (new colour roles `frontedge` = folder darker 0.16, `frontshine` = folder 30% to white, in `icons.colours`). 64, 96, 128px as drawn (whole pixels); 32 and 48px stretched under 3% so the folder's outer edges are whole pixels (`snap`); 16, 22, 24px the same with Mint-Y's picture for that icon at its own size, moved by whole pixels onto the front (GNOME's are too thin there). 12 names from GNOME (its desktop is a folder); recent, saved-search, gtk-network, network-workgroup made by compose-missing-places.py (it now refuses a Mint-Y icon that isn't a folder with a picture, as Mint-Y's desktop). Checked side by side with GNOME's own in its own blues, magnified: crisp edges and readable pictures at 16 and 24, the same at 48. Folder style pictures now 64px, three to a row (six styles: two rows of three); the window opens 725px tall (the Icons tab is now the tallest). **Icons tab labels (21 Nov, xl_cheese):** the switch and "Folder style: …" line are one: the switch reads "**Custom** folder style" while off and "**Yaru** folder style" (the chosen style's name, bold) while on; the pictures follow directly (`app._update_icon_labels`). A style may rename the second color for what it colours (`STYLES[...]["second_label"]`, e.g. "Racing stripes" on a binder, which has no back). **Next: xl binder styles (xl_cheese's idea: an 80s zip-flap school binder, Trapper Keeper-like; not its name or cover art, Mead's).** Standing, turned a little right, the top leaning away (drawn in perspective by hand, not with an SVG skew), bound at the bottom, open at the sides (paper showing), a flap over the top with a piping line; open state: flap up. Two styles: a solid one whose second color is "Racing stripes" (a pair, diagonal from bottom left to top right; xl-Big Baddy), and an 80s cover (diagonal bands: confetti, checkers, a zigzag, using the folder and second colors with black and white). Small sizes hand-tuned, upright and pixel-snapped. Then drop Adwaita (Breeze stays: the one square-cornered style; its 16-24px to get the Adwaita treatment: snapped, Mint-Y's pictures). **xl-Big Baddy built (21 Nov)**, `tools/make-xl-binder.py` → `data/icons/xl-big-baddy/places` (16 names × 8 sizes; first in the picker). Shaped with xl_cheese over several rounds from photos and a video of the real binder: wider than tall (96 × 80), one colour (cover and flap), a wedge side (20 at the spine, 9 at the top) with paper and pink pockets showing, the flap's plastic curving over the top of the side to the cover's top-left corner, white piping and a white ring, seen from below-left (yaw 38°, pitch −14°, camera 200: the top leans away). Racing stripes: a parallel pair, the lower from just above the bottom-left corner to the top-right corner (xl_cheese's red line), under the ring and the flap's shadow, on across the flap under its piping. 32px and up: true perspective (every point projected); Mint-Y's picture for each name (its drawing nearest the size) laid on the cover's lower right by the same projection as an affine map of its box, sized like Mint-Y's on its folder (34 units: about 44px at 128); Desktop is our own monitor (Mint-Y's desktop isn't a folder with a picture). 16/22/24px: straight on, on whole pixels (side strip, flap with a piping line, stripes, Mint-Y's small picture placed by whole pixels). Open (drag-accept): the flap standing up behind, leaning a little toward you, its underside plain in the darker shade (no piping: xl_cheese), papers peeking over the cover; velcro strips (xl_cheese: the real flap closes with velcro), centred across, one on the flap's underside near its edge and its partner on the cover where the flap presses down, dark, open binder only (hidden when closed), not at 16-24px. The cover's white ring is the same open or closed (it had grown into the flap's space when open; xl_cheese). The binder fills 72% of the square at first; pulled in to Breeze's margins (114 of 128 wide). Colour roles: `folder` the binder, `frontedge` its side, `backfolder` the stripes, `emblem` the picture. The second color is optional here (`second_optional`): unset, the stripes are the binder's colour and vanish under the rings (`icons.colours`); the row reads "Racing stripes" / "None" (`app._unset_label`), a "No stripes" button beside it (shown while they're on) unsets it, the two colors don't pin each other, and the tab's note is the style's own (`STYLES[...]["note"]`). CC BY-SA 4.0 (Mint-Y's pictures; `data/icons/xl-big-baddy/COPYING`). Still a shared setting: a second color picked for the stripes is every style's second color.
- **Icons tab (v2): a matching icon theme** (asked by xl_cheese, first raised at the very start). How Mint does it: one full base set (Mint-Y; it inherits Adwaita and hicolor for anything it lacks), and each colour choice in Themes settings (Mint-Y-Aqua, -Blue, -Orange…) is a small theme holding mostly the coloured folder and places icons, with `Inherits=Mint-Y`. So a matching theme is the same: generate only the folders and places icons (home, desktop, documents, downloads, music, pictures, videos, network, trash, bookmarks…) in each size Mint-Y ships, and inherit Mint-Y for everything else.
  - **Folder styles** (asked by xl_cheese): the folders come in a few looks, picked on the Icons tab like a button style, each recoloured to the accent; everything else is inherited from the user's own icon theme. Candidates, all SVG with full places sets (licences from memory, confirm each project's COPYING before shipping): **Yaru** (Ubuntu's; xl_cheese uses it today, hue-shifted to coral with a script; CC BY-SA 4.0, which can be shipped alongside GPL code with attribution and recoloured copies kept under CC BY-SA), **Mint-Y** (Mint's own, GPL-3), **Mint-X** (Mint's older flat style, GPL-3), **Adwaita** (GNOME's, LGPL-3 / CC BY-SA 3.0), **Papirus** (GPL-3; its `papirus-folders` script already recolours folders, a precedent for this), plus possibly Numix, Tela or Colloid (GPL-3). Or draw an xl-Cheeselooks folder of our own, as with the window glyphs: no licence questions and a look of its own. Each shipped style keeps its licence and credit in the theme folder and on the About tab.
  - **Recolouring:** Mint-Y's icons are SVG, so the folders can be recoloured as text (their fill colours swapped for shades of the accent, lightness kept so the folder's front, back and shading still read), with no raster work and every size crisp. Same idea as the comet thumbnail (`thumbnail.py`). Generated at every Apply, never stored recoloured. xl_cheese's Yaru hue script is a handy reference for which of Yaru's colours make the folder, not a dependency; the recolour maps each shade to the accent's hue and keeps the folder's light-to-dark steps relative to the accent, so a pale or deep accent gives a folder of that lightness (a plain hue shift keeps Yaru's own lightness). **Our own folder** needs no recolouring at all: it's drawn in code from the accent at Apply (as the Thin glyphs are), every size written as its own crisp SVG. Check which hues a folder uses, so only the folder body changes and its emblem (the house, the music note) keeps its look.
  - **Output:** `~/.local/share/icons/xl-Cheeselooks/` with an `index.theme` (`Inherits=Mint-Y,Adwaita,hicolor`), rebuilt at Apply when the accent changes; refresh the icon cache, and set Cinnamon's icon theme (`org.cinnamon.desktop.interface icon-theme`) only when the user picks it on the Icons tab.
  - **Open questions:** which icons Mint's own colour variants include besides folders (copy the list from an installed variant, e.g. `/usr/share/icons/Mint-Y-Blue`); Mint-Y's licence for redistributing recoloured copies (expected GPL-3, as the window buttons; confirm); what Mint-Y-Blue looks like next to ours (xl_cheese will send screenshots when we start).

- **Release checklist: the README's pitch** (asked by xl_cheese): lines saved in `docs/pitch.md` (what it themes and how far it goes).
- **Release checklist: the README's "Details" section** (asked by xl_cheese). People won't see most of the polish, so show some: a few before-and-after crops (tabs meeting the toolbar line, the 6.4 menu sidebar hover, accent buttons with a dark rim on dark themes, menus square below Roundness 30 and inset above, no Mint-Y flash on Apply), each with one line on why. Every one is recorded in this spec. Plus the numbers, rerun just before release: `python3 tools/project-stats.py --transcripts ~/.claude/projects/<project folder>` (commits, days, lines, tests, spec; messages and screenshots from the session transcripts). On 19 Nov 2026: 346 messages, 135 screenshots, 194 commits over 11 days, 104 tests.

- **Editor colour scheme for Xed and other GTK editors** (asked by xl_cheese). **Built (20 Nov): Integration → "Text editors (Xed…)"** (`integration.editor_colors`, on by default; `cheeselooks/editor.py`). Each Apply writes `xl-cheeselooks.xml` (a GtkSourceView style scheme, id `xl-cheeselooks`) into `gtksourceview-3.0`, `-4`, `-5` and `libgedit-gtksourceview-300` under `~/.local/share/`, and switches Xed (`org.x.editor.preferences.editor scheme`), gedit and Meld to it when installed, remembering each one's previous scheme (`~/.config/xl-cheeselooks/editor-colors.json`); off puts those back and removes the files. Colours: the editor background `base`, gutter between `base` and `bg`, line numbers readable on it (3:1), current line, selection and bracket match tinted with the accent, search in a yellow tint on light themes (accent on dark); syntax: statements in the accent (bold), the others turned round the colour wheel from the accent's hue, each moved in lightness until it reads at 4.5:1 on the editor background (tested on every shipped theme); comments italic, 3:1. Flatpak editors can't see these folders. Original plan: Xed's editing area takes its colours from a GtkSourceView colour scheme, not the GTK theme; the light ones (Classic) on a dark theme gave white line numbers on a fixed light gutter (#EEEEEC) and dark-blue comments on dark. Generate an `xl-Cheeselooks` scheme at Apply from the theme: editor background `base`, text, gutter and line numbers (from `bg` / `text_dim`), current line, selection (`select`), matching brackets and search matches in the accent, syntax colours derived to read on `base` (light or dark, like the terminal palette). Written to `~/.local/share/gtksourceview-4/styles/` (Xed, gedit 3.x-era apps, Meld), plus `-3.0` and `-5` copies (older apps; GNOME Text Editor). Picked in each editor's preferences; the Tool could set Xed's (`org.x.editor.preferences.editor scheme`) when the user opts in, as Integration does for others.
  - **Other apps that keep their own colours, to consider** (most valuable first): **Qt apps** (a qt5ct/qt6ct colour scheme, and possibly a Kvantum theme, so Qt apps such as VLC or qBittorrent match); **VS Code and other Electron editors** (a generated colour theme, packaged as a local extension); **LibreOffice** (its Application Colors as a named scheme in the user profile; its icon theme stays the user's choice); **GIMP 3** (its own GTK 3 theme folder, generated like ours). Firefox and Thunderbird already follow the GTK theme with their "System theme" setting.
  - **On the Integration tab** (xl_cheese's plan): one switch per app ("Xed and other editors", "Qt apps (VLC…)", "VS Code", "LibreOffice", "GIMP 3"), each writing its files at Apply when on, with a short note under it saying where to turn the theme on in that app (e.g. "In Xed: Preferences → Font & Colors → xl-Cheeselooks"; "In GIMP: Edit → Preferences → Interface → Theme"). Off by default, like the Flatpak switch; turning one off removes what it wrote.
  - **Qt / VLC first** (xl_cheese uses VLC). Before building: check what Mint sets for Qt apps (`echo $QT_QPA_PLATFORMTHEME`; Mint has used a GTK platform theme, in which case Qt apps read GTK colours and a `gtk-2.0` part in our theme may be what helps, rather than qt5ct). A qt5ct/qt6ct scheme only works if the user (or the Tool, with a note) sets `QT_QPA_PLATFORMTHEME=qt5ct`, which changes every Qt app; say so in the note. Both routes are needed, for everyone's desktop, not one setup: Mint's Software Manager offers many apps (VLC included) as Flatpaks, and others install the regular package. **Regular Qt apps** on X-Cinnamon use Qt's GTK 3 platform theme by default (`QT_QPA_PLATFORMTHEME` empty, `libqgtk3.so`, as on xl_cheese's machine), which in Qt 5 doesn't carry GTK's colours: route = a qt5ct/qt6ct scheme plus `QT_QPA_PLATFORMTHEME=qt5ct` (all Qt apps; said in the note). **Flatpak Qt apps** (KDE runtime, sandboxed; they see neither qt5ct nor `~/.profile`): route = a KDE colour scheme in `~/.config/kdeglobals` plus a Flatpak override exposing it and selecting the KDE platform theme, as the Flatpak GTK switch does for GTK apps (Kvantum and its Flathub add-on as the heavier alternative). The switch handles whichever the user has, detecting installed Flatpak Qt apps. To test both, install regular VLC next to the Flatpak (`sudo apt install vlc`; they coexist), rather than replacing one. Experiments with `tools/qt-colors-experiment.py` (19 Nov): **regular VLC 3.0.20 with qt5ct works** (xl_cheese, xl-Gummy: window, text, base, buttons, selection and checks in the theme's colours, Fusion style). Learned: qt5ct needs `standard_dialogs=gtk3`, or file dialogs become Qt's own ("Non-native QFileDialog"); VLC paints its seek bar (blue) and volume bar (green) itself, so those stay; its Preferences shows a picture of the old Clearlooks look, VLC's own artwork. **Flatpak VLC with the KDE colour scheme works too** (`QT_QPA_PLATFORMTHEME=kde` and a `kdeglobals` in the app's own config folder; same colours, coral selection with xl-Cheeselooks). Both routes give the theme's **colours** on Qt's Fusion widgets, not our shapes (gradients, borders, roundness, edges). Matching shapes would take a generated **Kvantum** theme (SVG pieces and a kvconfig, drawn from the same tokens as our title-button SVGs; Kvantum is in Mint's repositories and has a Flathub add-on for Flatpak Qt apps): a later, bigger step. Plan: the switch ships colours first, Kvantum after. **Built (20 Nov): Integration → "Qt apps (VLC…)"** (`integration.qt_colors`, **on by default** (xl_cheese: most people wouldn't know to look for it, and would assume their VLC can't match). **A Qt setup of your own is moved aside, never lost** (xl_cheese's call, over asking first: on a Mint desktop running a matching tool, wanting Qt apps different is rare, and switching off is the way out): qt5ct.conf is backed up and rewritten with our colours, stylesheet and Fusion (Kvantum ignores colours); our `~/.profile` block goes at the end, after any Qt line of yours (left untouched), with `export QT_QPA_PLATFORMTHEME=qt5ct` and `unset QT_STYLE_OVERRIDE`; a Flatpak app's override gets `QT_QPA_PLATFORMTHEME=kde` (and an empty `QT_STYLE_OVERRIDE` if a style was set there or globally), its previous values recorded; its kdeglobals is backed up. Our own files are simply rewritten at each Apply. The first time anything of yours is moved aside, one notice says what was saved and that switching off puts it back (`qt.pending_notice`, shown once by the app after Apply; the command line prints it). Switching off restores everything exactly: files from their backups, override values as they were (an emptied section or file removed), our `.profile` block removed. When packaged, list qt5ct as a recommended package so regular Qt apps work out of the box; `cheeselooks/qt.py`). On, each Apply rewrites: the qt5ct scheme (`~/.config/qt5ct/colors/xl-Cheeselooks.conf`) and qt5ct.conf pointed at it (your other qt5ct settings kept; `standard_dialogs=gtk3` and `style=Fusion` only if you hadn't set them), a marked `export QT_QPA_PLATFORMTHEME=qt5ct` block in `~/.profile` (not if your `.profile` already sets that variable), and for each Flatpak app on the KDE runtime a `kdeglobals` in its config folder plus `flatpak override --user --env=QT_QPA_PLATFORMTHEME=kde <app>`. Only if qt5ct is installed for the regular route; the note under the switch gives the install command otherwise. Everything written is recorded in `~/.config/xl-cheeselooks/qt-colors.json`; switching off removes it at the next Apply, putting back any file it replaced (`*.xl-backup`) and unsetting the Flatpak variable. Qt apps read their colours when they start (unlike GTK apps, which restyle live after Apply): open ones pick up a new theme when reopened, and regular Qt apps need one new login the first time (the `~/.profile` line). Tested on xl_cheese's desktop with a Kvantum setup of his own (KvArcDark via qt5ct and a `.profile` line): taken over with the notice, and back exactly when switched off, several times. Qt's palette has one highlight for everything, and paints menu bars with the window colour; so regular Qt apps also get a small Qt stylesheet (`~/.config/qt5ct/qss/xl-Cheeselooks.qss`, added to qt5ct's `stylesheets` beside any of yours): the menu bar in `header` (as GTK menubars), menu bar and menu hovers from the style's `menubar_item` / `menu_item` (the grey step on xl-Cheeselooks, the warm tint on xl-Claude) instead of the accent, menus in `menu_bg` with a thin border; lists and selections keep the accent. Flatpak Qt apps can't load stylesheets: their menu bar stays the window colour and their menus hover in the accent until Kvantum. Seen on xl_cheese's desktop: both VLCs follow a theme change when restarted, no new login needed once `~/.profile` has the line.
  - **GIMP 3**: on Mint usually the Flathub build, whose themes folder is `~/.var/app/org.gimp.GIMP/config/GIMP/3.0/themes/`; the regular one is `~/.config/GIMP/3.0/themes/`. xl_cheese will install GIMP 3 to test.

- **Flatpak access as a switch** (asked by xl_cheese; **built 20 Nov**: Integration → "Flatpak apps", on by default like Qt apps and Text editors; Apply grants the access when on and not yet granted, and removes just our entries when switched off, `cli._flatpak_access`; the old buttons and confirmation dialog are gone; `cheeselooks flatpak --enable/--disable` still works and sets the switch). Plan was: Integration's "Let Flatpak apps see the theme… / Undo" buttons become a switch like the others (Qt apps, Text editors): on grants the read-only access at Apply (`flatpak.enable`), off removes just our entries (`flatpak.disable`); the setting `integration.flatpak_access` already exists. Decide its default then: on would fit Qt apps and Text editors (Flatpak GTK apps would match out of the box); it's a user-wide Flatpak override, so the note under it should say what it grants.

- **Theme watcher and "Take out of apps"** (found by xl_cheese, built 20 Nov). What Apply writes outside the theme folder (the GTK 4 block in `~/.config/gtk-4.0/gtk.css`, with full styling; the Qt colours; the editors' scheme) applied whatever theme was selected: after picking Mint-Y in Mint's Themes settings, GTK 4 apps (Widget Factory) and Flatpak Calculator kept xl-Cheeselooks. Integration → **"Follow Mint's theme setting"** (`integration.watch_theme`, on by default; `cheeselooks/watch.py`) starts `cheeselooks watch` at login (`~/.config/autostart/xl-cheeselooks-watch.desktop`, written or removed at Apply, and started then if not running). It waits on `gsettings monitor org.cinnamon.desktop.interface gtk-theme` (no CPU while waiting); a change is acted on after it has lasted 2 s (Apply's reload goes through `.xl-Cheeselooks-reloading` and back) and never while Apply runs (`~/.config/xl-cheeselooks/applying`). Away from xl-Cheeselooks: `set_aside` takes the GTK 4 block out (only ours), switches Qt and editors off (yours restored), and marks `set-aside`; back: `restore` writes them again from the saved settings. Flatpak access and the GNOME accent stay (harmless with any theme). Tested on xl_cheese's desktop: Mint-Y → Calculator plain GNOME, our block gone; back → our colours. Found then: the Qt notice popped up on the way back, listing leftovers of our own (qt5ct.conf pointing at our scheme, Flatpak overrides with `kde` from earlier versions) as "your setup"; fixed: files and values of ours are recognised (`qt._is_ours`, `qt._ours_env`: marked, pointing at our scheme, or our values) and never kept as yours, switch-off tidies such leftovers away instead of restoring them, and the watcher's own off-and-on (`qt.disable(set_aside=True)`) is silent. Integration also has a **Take out of apps** button (`cheeselooks set-aside`): the same, now, settings unchanged; the next Apply puts it back.

## Distant roadmap

- **Round bottom corners** (parked by xl_cheese to focus on the release; the work is in, behind `tokens.ROUND_BOTTOM_READY`). Done: the window, sidebars, action bars, Xreader's page view, GTK 3 and 4. Open: Celluloid's control bar and dconf Editor's list (need their CSS node names from GTK Inspector), Nemo's corner after leaving its tree view out, a possible notch in Xreader with its side panel open, and a corner-check tool (screenshot each app's bottom corners, report round or square).
  - **The way forward is likely the compositor, not window by window** (xl_cheese's call). A Cinnamon effect that trims every window's corners as it's drawn on screen fixes the contents too (nothing pokes out, no per-piece CSS) and works for every app: Qt, Electron, Java, games. GNOME has one ("Rounded Window Corners", a GNOME Shell extension); Cinnamon is built on the same pieces (Muffin is a fork of GNOME's window manager), so a port looks possible, details unchecked. It belongs with the blur effect below: both are Cinnamon effects rather than theming, so they could share one effect/extension and one round of live testing.
  - **Tried: a footer strip** (xl_cheese's idea, 20 Nov): reserve a strip of window colour along the bottom so no app content reaches the corners, and round that. **GTK 4: works** (`window.background { padding-bottom: 12px; border-radius: ... }` reserves real space; the content stops above it; cost: the strip's height, and a band where the content isn't the window colour). **GTK 3: impossible** from a theme (a GTK 3 window ignores CSS padding, border and its child's margins when sizing the content: tried all three). GNOME itself uses no footer: libadwaita clips the content to the rounded shape. So the compositor effect stays the real fix; the footer is a GTK 4-only fallback.
  - **A stepping stone: Buffet for menu-less apps.** Buffet already gives menu apps a GTK header bar; it could do the same for GTK 3 apps without a menu. GTK has a switch for it: `GTK_CSD=1 app` makes GTK draw the title bar itself (a `headerbar.default-decoration`, the same CSS Muffin's title bars use, so it looks almost the same). Buffet could set it per app (e.g. in its launcher), or give them a real header bar. Limits: (1) the poke-out problem comes along: each converted app's corner pieces need finding, and what an app draws itself (terminal areas, video, web views) stays square; (2) GTK apps only: Qt, Electron, Java apps and games keep Muffin's square frames; (3) side effects: GTK's plainer right-click title bar menu instead of Cinnamon's, and some older apps misplace dialogs or look odd with a header bar, so Buffet would want an opt-out list. Try `GTK_CSD=1` on a couple of apps before building on it.

- **Blur behind the panel and menus** (from the wallpaper), as BlurCinnamon does (github.com/klangman/BlurCinnamon): an effect, not theming (Cinnamon's St CSS has no backdrop blur), so the app would apply it quietly when panel or menu opacity is lowered, making lower opacities usable. Needs research into how BlurCinnamon applies its effect and whether we can bundle or drive it.
- **The tool is Theme Roller (21 Nov, xl_cheese).** The app's title (window, header bar, About, menu entry `Name=`) is "Theme Roller"; the themes, styles, icon theme and files it makes keep the xl-Cheeselooks name (`xl-Cheeselooks` GTK theme, `xl-Cheeselooks` icons, `.xltheme`). Commands, package and repository names unchanged for now.
- **Adwaita retired, Breeze sharpened (21 Nov, xl_cheese).** Adwaita looked too like Mint-Y and Yaru (rounded, facing forward); its icons are removed, its import tool kept (`tools/import-adwaita-places.py`, to bring it back). Breeze, the one square-cornered style, stays; its 16, 22, 24px were its 32px drawing shrunk (edges between pixels, 1px outline pictures at half a pixel). Now, as Adwaita's were: the 32px drawing snapped to whole pixels (`tools/smallsize.py`, shared: `snap`, `mint_picture`), with Mint-Y's picture drawn for that size centred on the front by whole pixels; where Mint-Y has none (Desktop) Breeze's own stays. Checked magnified, before and after. Folder styles now: xl-Big Baddy, Mint-Y, Yaru, Breeze (and Claude's, next).
- **Claude folder style (21 Nov).** First drawn from the "Pocket" sketch (a portfolio with stitching and paper); xl_cheese: too close to his binder, scrap it, use the "Hot Rod" sketch instead, "turned slightly opposite the direction xl-Big Baddy are, but not the same perspective". Now: a wide back with a tab (second color) and a front that's a wedge, 108 wide at the top and 100 at its foot (folder color), a darker band along the foot, a light line along the top edge, the right edges of front and back showing (`frontedge`). Turned gently left (yaw −20°) and seen from a little above (pitch +9°): it sits back where the binder, seen from below-left, stands tall. Open (drag-accept): the front tipped forward 24° about its foot, a sheet inside. Then (xl_cheese): pictures centred on the front; the back 6 units lower (top and tab; a pixel lower at 22/24px) to suit the front; the back's bottom corners rounded and its edge started above them (its square corner showed past the front's rounded one). Then (xl_cheese, with a reference picture of a folder in perspective): front and back are one folded piece, joined at a fold along the bottom, the gap widening upward (`z_back(v)`: 1.5 at the fold to 21.5 at the top), the back as wide as the front, turned more (yaw −36°) so the open side shows on the right: the inside of the fold dark, two sheets' edges in the gap and their tops over the front. Before, the back was a flat panel a constant distance behind, which didn't read as turned with the front. Stray pixels at the lower right corner (xl_cheese) fixed: the fold's inside and the papers now stop where the front's foot starts to round, and the back's bottom-right corner is tucked in behind the front's (sitting further back, it shifted right past it). `tools/make-claude-folder.py`: true perspective at 32px and up, Mint-Y's picture centred on the front (affine over its box; fit measured on the folder alone); 16/22/24 straight on, on whole pixels, the wedge a pixel in at each side of the foot, Mint-Y's small picture (`tools/smallsize.py`); our monitor for Desktop. CC BY-SA 4.0 (Mint-Y's pictures). Second in the picker.
- **xl-Rad, the 80s binder (21 Nov, xl_cheese's mockup and name; first called "xl-80s").** The xl-Big Baddy binder with a different cover: no stripes and no white ring; a checkerboard band across the cover (black and white squares on the cover, projected with it, clipped to the band) between two wavy lines in the second color ("Wavy lines"; a darker shade of the accent until chosen, as other styles' second color). The band sits low (its lines at 9 and 31 of the cover's 80, waving 2.4) so the picture fits above it (21 units, centred between band and flap). Same flap, side, velcro and open binder. 16-24px: a one-row pixel checker band between two lines along the cover's foot, Mint-Y's 16px picture centred above. Made by the same tool (`tools/make-xl-binder.py`: `COVER`, one run makes both styles). Third in the picker; six styles make two rows of three.
- **Names, ready for release (21 Nov, xl_cheese).** Command `theme-roller` (`bin/theme-roller`: no arguments opens the app, otherwise the command line: `theme-roller apply`, `revert`, `watch`…; `prog` in `--help`); the old `bin/cheeselooks` and `bin/cheeselooks-settings` stay as aliases so existing setups keep working (the watcher's login entry pointed at `bin/cheeselooks` until the next Apply rewrites it; `watch.WATCH_PATTERN` finds a watcher started under either name). Repository to be renamed `xlcheese/theme-roller` (GitHub redirects the old address); the app's links point there. Application id and launcher `io.github.xlcheese.ThemeRoller` (`.desktop`, `Exec=theme-roller`). The Python package stays `cheeselooks` (internal, not seen by users). The themes, styles, icon theme and their files keep the xl-Cheeselooks name. Dropped from the plans: lighter folders on dark themes (users set both folder colors as they like).
