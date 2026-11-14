# Project brief: four-stop background gradients in Cinnamon

A patch for Cinnamon (`linuxmint/cinnamon`) so its stylesheet engine can draw a
background gradient with a step in the middle: two extra colour stops between
the existing start and end. This is the brief to start a new project with.

## Why

xl-Cheeselooks (github.com/xlcheese/xl-cheeselooks) is a theme generator for
Linux Mint Cinnamon. Its styles can give buttons a glossy face in the
Clearlooks tradition, with a crisp step across the middle:

- **split** (Clearlooks Gummy / Phenix): the top half fades gently, steps at
  the middle, and the bottom half fades on to the bottom colour.
- **glass** (from xl_cheese's GTK 2 xl_cheeselooks, a fork of the Clearlooks
  engine, gnome-look.org/p/1079199): the top half fades darker, steps down to
  the darkest shade at the middle, and the bottom half fades back *lighter*,
  like light reflected from below.

GTK 3 and GTK 4 draw these with CSS `linear-gradient()` and four stops. Muffin's
window borders use SVG images. **Cinnamon's panel, menus and dialogs can't**:
St, Cinnamon's toolkit, only knows a two-colour gradient. So today the theme
falls back to a smooth two-colour fade for everything Cinnamon draws: panel
buttons, menu hovers, applets and dialogs.

## What St does today

Cinnamon's St stylesheet engine supports exactly two gradient colours:

```css
background-gradient-direction: vertical;   /* or horizontal, radial, none */
background-gradient-start: #F8F8F8;
background-gradient-end: #E9E9E9;
```

The cairo pattern it builds has exactly two stops (offset 0 and offset 1).
Cairo itself accepts any number of stops, and two stops at the same offset give
a hard step, which is all that split and glass need.

Code, as of `linuxmint/cinnamon` master `4652585` (2026-11-11, version 6.8.0):

| File | What's there |
|---|---|
| `src/st/st-theme-node-private.h` (~line 41-44) | `ClutterColor background_color;` (the gradient start when a gradient is set), `StGradientType background_gradient_type;`, `ClutterColor background_gradient_end;` |
| `src/st/st-theme-node.c` (~line 2099-2131, in the `background-*` property parsing) | `-gradient-direction`, `-gradient-start` (into `background_color`) and `-gradient-end` (into `background_gradient_end`), read with `get_color_from_term()` |
| `src/st/st-theme-node.c` (~line 1868) | `background_gradient_type = ST_GRADIENT_NONE` reset when the background is computed |
| `src/st/st-theme-node.c` (~line 2245) | `st_theme_node_get_background_gradient()`, the public getter (start and end) |
| `src/st/st-theme-node.c` (~line 4039-4043) | the equality check that decides whether a node's paint changed (compares type and end colour) |
| `src/st/st-theme-node-drawing.c` (~line 564-595) | `create_cairo_pattern_of_background_gradient()`: the two `cairo_pattern_add_color_stop_rgba()` calls |
| `src/st/st-theme-node-drawing.c` (~line 1047-1048) | the "gradient has translucent areas" check (start and end alpha) |
| `src/st/st-theme-node-drawing.c` (~line 545) | `st_theme_node_has_visible_outline()` (end alpha) |
| `src/st/st-theme-node-drawing.c` (~line 1503) | gradients always go through the prerendered (cairo) path |

Line numbers drift; search for `background_gradient_end` to find every place.

## Proposed change

Two optional properties for the middle of the gradient, plus an optional
position:

```css
background-gradient-direction: vertical;
background-gradient-start: #F8F8F8;          /* offset 0 */
background-gradient-middle-start: #F5F5F5;   /* arriving at the middle */
background-gradient-middle-end: #F0F0F0;     /* leaving the middle */
background-gradient-end: #E9E9E9;            /* offset 1 */
background-gradient-middle-position: 50%;    /* optional, default 50% */
```

- With neither middle colour set, St draws exactly as today, so existing themes
  don't change.
- With only one of them set, use it for both, which gives a three-stop gradient
  with no step.
- It works for all three directions. For radial gradients the middle sits at
  that fraction of the radius.

Why separate properties rather than CSS `linear-gradient()`: St's background
parsing works one property, one value at a time (see the `-gradient-start` and
`-gradient-end` branches). Two more colour properties fit that pattern and keep
the patch small, about 40-60 lines. Full `linear-gradient()` parsing would be a
much bigger change, and harder to get accepted.

Implementation sketch:

1. `st-theme-node-private.h`: add `ClutterColor background_gradient_middle_start;`,
   `ClutterColor background_gradient_middle_end;`, `gboolean background_gradient_has_middle;`
   and `double background_gradient_middle_position;` (default 0.5).
2. `st-theme-node.c`, background parsing: branches for `-gradient-middle-start`,
   `-gradient-middle-end` (`get_color_from_term()`) and
   `-gradient-middle-position` (a percentage, clamped to 0-1). Reset all of them
   next to the existing `background_gradient_type = ST_GRADIENT_NONE`.
3. `st-theme-node-drawing.c`, `create_cairo_pattern_of_background_gradient()`:
   when `has_middle`, add stops at `middle_position` for middle-start, then
   middle-end, between the existing 0 and 1 stops (same offset twice is a hard
   step in cairo).
4. Translucency check (~line 1047): also look at the middle colours' alpha.
5. Equality check (~line 4039): also compare the middle colours, `has_middle`
   and the position, or a change to only the middle won't repaint.
6. Optionally: extend or add a getter (e.g.
   `st_theme_node_get_background_gradient_middle()`) for JS callers. Not needed
   for themes.
7. Document the new properties wherever St's supported CSS is documented in the
   repo (search `docs/` for `background-gradient-start`).

## How xl-Cheeselooks would use it

The generator already computes the four stops
(`cheeselooks/palette.py`, `gradient_stops()`), for a face from `top` to `bottom`:

- **split**, with `step` 0-1:
  `top` at 0 → `mix(top, bottom, 0.5 × (1 − step))` at 50% → `mix(top, bottom, 0.5)`
  at 50% → `bottom` at 1
- **glass**, with `step` 0-1 and `return` 0-1:
  `top` at 0 → `mix(top, bottom, 1 − 0.5 × step)` at 50% → `bottom` at 50% →
  `mix(bottom, top, return)` at 1

The Cinnamon template (`templates/cinnamon/xl.css.part`) would write
`background-gradient-middle-start` and `-middle-end` alongside today's start and
end. Older Cinnamon versions ignore the unknown properties and keep drawing the
smooth fade, so no version check is needed. (Check this: St should ignore
unknown `background-*` properties without breaking the rest of the rule. If it
warns, we may need to write them only for Cinnamon versions that support them.)

## Testing

Needs a Mint machine (or VM) with Cinnamon to build and run:

```bash
sudo apt build-dep cinnamon
git clone https://github.com/<your-account>/cinnamon && cd cinnamon
meson setup build --prefix=/usr && ninja -C build
sudo ninja -C build install    # or test in a VM: this replaces the system Cinnamon
cinnamon --replace &           # or log out and in
```

Test cases, with screenshots for the pull request:

- A theme without the new properties: no visible change (panel, menus, dialogs).
- Split and glass panel buttons and menu hovers (xl-Cheeselooks with xl-Gummy,
  and with a glass style).
- Translucent colours (a panel at 70% opacity): the step stays translucent with
  no dark edges.
- Horizontal and radial directions.
- Changing only a middle colour while Cinnamon is running (via a theme reload)
  repaints, which checks the equality change.
- HiDPI (scale 2).

## Getting it upstream

1. Fork `linuxmint/cinnamon` on xl_cheese's GitHub account. The pull request
   should come from a person the Mint team can talk to.
2. A branch such as `st-gradient-middle-stops`, one focused commit. Follow the
   surrounding code style (GNU style, 2-space indent, as in `st-theme-node.c`).
3. A pull request describing the use case (Clearlooks-style glossy themes),
   the new properties, that existing themes are unchanged, and before/after
   screenshots.
4. Be patient: review can take weeks to months. If it's merged, it ships in a
   later Cinnamon release (Mint 23 or later), and xl-Cheeselooks starts writing
   the middle stops.

Optional: open an issue first ("St: allow a step in background gradients for
Clearlooks-style themes") to see whether the Mint developers like the property
names before writing the code.

## Related, for later

- St can't put a background image over a gradient ("strictly either/or" in
  `st-theme-node-drawing.c`). xl-Cheeselooks works around this for the planned
  panel `bar` marker and the `claude` notification style. A separate patch could
  lift that too.
- St allows one `box-shadow` per widget, which limits Cinnamon's panel buttons
  to one shadow layer. Also a possible separate patch.
