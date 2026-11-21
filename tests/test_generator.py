"""Tests for the generator core. Run with: python3 -m unittest discover tests"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from cheeselooks import cli, editor, flatpak, icons, qt, reload, watch, gtk4, install, tabs, themes, palette, render, settings, shape, styles, tokens, titlebuttons

REPO = Path(__file__).resolve().parents[1]
DEFAULT_STYLE = REPO / "styles" / "xl-Cheeselooks"
FLOAT_STYLE = REPO / "docs" / "examples" / "float"


def defaults() -> dict:
    return copy.deepcopy(settings.DEFAULTS)


class PaletteTests(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(palette.normalize("fa8562"), "#FA8562")
        self.assertEqual(palette.normalize("#abc"), "#AABBCC")
        with self.assertRaises(ValueError):
            palette.normalize("#12345")

    def test_mix_endpoints(self):
        self.assertEqual(palette.mix("#000000", "#FFFFFF", 0), "#000000")
        self.assertEqual(palette.mix("#000000", "#FFFFFF", 1), "#FFFFFF")
        self.assertEqual(palette.mix("#000000", "#FFFFFF", 0.5), "#808080")

    def test_contrast(self):
        self.assertAlmostEqual(palette.contrast("#000000", "#FFFFFF"), 21.0, places=1)
        self.assertAlmostEqual(palette.contrast("#777777", "#777777"), 1.0)

    def test_light_theme(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        self.assertFalse(palette.is_dark(p))
        self.assertEqual(p["accent_fg"], "#FFFFFF")
        # selection is darkened until white text reaches 2.6:1
        self.assertGreaterEqual(palette.contrast(p["select"], "#FFFFFF"), 2.6)
        self.assertNotEqual(p["select"], p["accent"])
        # content area is lighter than the window background in light themes
        self.assertGreater(palette.luminance(p["base"]), palette.luminance(p["bg"]))

    def test_dark_theme(self):
        p = palette.derive("#FA8562", "#2B2B2B", "#E4E4E4")
        self.assertTrue(palette.is_dark(p))
        self.assertLess(palette.luminance(p["base"]), palette.luminance(p["bg"]))

    def test_very_light_accent_gets_dark_text(self):
        p = palette.derive("#FFE680", "#F5F5F5", "#303030")
        self.assertNotEqual(p["accent_fg"], "#FFFFFF")

    def test_menu_hover_steps_match(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        a = palette.contrast(p["menu_hover"], p["menu_bg"])
        b = palette.contrast(p["fav_hover"], p["fav_bg"])
        self.assertAlmostEqual(a, b, delta=0.06)

    def test_menubar_hover_darker_than_general_hover(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        self.assertLess(palette.luminance(p["menubar_hover"]), palette.luminance(p["hover"]))

    def test_hover_strength(self):
        base = palette.derive("#FA8562", "#F5F5F5", "#303030")
        strong = palette.derive("#FA8562", "#F5F5F5", "#303030", hover=2.0)
        none = palette.derive("#FA8562", "#F5F5F5", "#303030", hover=0.0)
        self.assertEqual(none["menu_hover"], none["menu_bg"])
        self.assertGreater(palette.contrast(strong["menu_hover"], strong["menu_bg"]),
                           palette.contrast(base["menu_hover"], base["menu_bg"]))
        # light theme: hover lighter, border darker
        self.assertGreater(palette.luminance(base["button_hover"]), palette.luminance(base["button"]))
        self.assertLess(palette.luminance(base["border_hover"]), palette.luminance(base["border_strong"]))
        # dark theme: border gets lighter on hover
        dark = palette.derive("#FA8562", "#2B2B2B", "#E4E4E4")
        self.assertGreater(palette.luminance(dark["border_hover"]), palette.luminance(dark["border_strong"]))
        # a white surface has no room to go lighter, so it goes darker
        white = palette.derive("#FA8562", "#FFFFFF", "#303030")
        self.assertLess(palette.luminance(white["pb_hover"]), palette.luminance(white["bg"]))

    def test_gradient_skews_darker(self):
        top, bottom = palette.gradient("#808080", 1.0)
        base = palette.luminance("#808080")
        self.assertLess(palette.luminance(top) - base, base - palette.luminance(bottom))
        self.assertEqual(palette.gradient("#808080", 0), ("#808080", "#808080"))

    def test_title_gradient_ends_on_toolbar_color(self):
        top, bottom = palette.title_gradient("#E8E8E8", 0.6)
        self.assertEqual(bottom, "#E8E8E8")
        self.assertGreater(palette.luminance(top), palette.luminance(bottom))

    def test_terminal_follows_theme(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = palette.terminal_colors(p, None, None)
        self.assertEqual(t["bg"], p["base"])
        self.assertEqual(t["text"], p["text"])

    def test_readability_warnings(self):
        good = palette.derive("#FA8562", "#F5F5F5", "#303030")
        self.assertEqual(palette.readability_warnings(good), [])
        bad = palette.derive("#39FF14", "#FF2DA6", "#1A1AFF")
        self.assertTrue(palette.readability_warnings(bad))


class ShapeTests(unittest.TestCase):
    def test_full_roundness_is_pill_at_every_size(self):
        for size, (ctl, _, _) in shape.SIZES.items():
            self.assertEqual(shape.shape_tokens(size, 100)["r"], round(ctl / 2))

    def test_window_radius_capped(self):
        self.assertEqual(shape.shape_tokens("large", 100)["r2"], shape.WINDOW_RADIUS_MAX)

    def test_square(self):
        t = shape.shape_tokens("normal", 0)
        self.assertEqual((t["r"], t["r2"], t["r_switch"]), (0, 0, 0))


class SettingsTests(unittest.TestCase):
    def test_defaults_are_valid(self):
        self.assertEqual(settings.validate(defaults()), [])

    def test_partial_file_is_merged(self):
        s = settings.from_dict({"global": {"accent": "2e9e92"}})
        self.assertEqual(s["global"]["accent"], "#2E9E92")
        self.assertEqual(s["global"]["bg"], "#F5F5F5")

    def test_bad_values_are_reported(self):
        with self.assertRaises(settings.SettingsError) as ctx:
            settings.from_dict({"global": {"accent": "orange", "roundness": 140, "size": "huge"}})
        text = " ".join(ctx.exception.problems)
        self.assertIn("global.accent", text)
        self.assertIn("global.roundness", text)
        self.assertIn("global.size", text)

    def test_preset_merges(self):
        s = settings.apply_preset(defaults(), {"name": "x", "panel": {"separate_colors": True, "bg": "#222222"}})
        self.assertTrue(s["panel"]["separate_colors"])
        self.assertEqual(s["panel"]["bg"], "#222222")
        self.assertEqual(s["global"]["accent"], settings.DEFAULTS["global"]["accent"])

    def test_all_builtin_presets_load(self):
        for f in (REPO / "presets").rglob("*.json"):
            with self.subTest(preset=f.name):
                settings.apply_preset(defaults(), json.loads(f.read_text()))


class StyleTests(unittest.TestCase):
    def test_builtin_styles_are_clean(self):
        builtin = sorted((REPO / "styles").iterdir())
        paths = builtin + sorted((REPO / "docs" / "examples").iterdir())
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            with self.subTest(style=path.name):
                st = styles.load(path)
                self.assertEqual(st.warnings, [])
                if path in builtin:
                    self.assertEqual(st.name, path.name)   # folder name matches the style's name
                tokens.build(defaults(), st)           # and it builds

    def test_raised_edge_has_all_layers_for_gtk_one_for_cinnamon(self):
        st = styles.Style(name="Fixture", path=None)
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertEqual(t["w.button.shadow"].count("rgba("), 3)
        self.assertEqual(t["w.button.st_shadow"].count("rgba("), 1)
        self.assertTrue(t["w.button.st_shadow"].startswith("inset 0 1px"))  # highlight kept first

    def test_seam_shadow_draws_the_shared_edge_in_the_border_color(self):
        st = styles.load(DEFAULT_STYLE)
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        for state in ("hover_", "pressed_"):
            seam = t[f"w.linked.{state}seam_shadow"]
            self.assertTrue(seam.startswith(f"1px 0 0 0 {t[f'w.linked.{state}border']}"))
            inset = t[f"w.linked.{state}inset_shadow"]
            if inset != "none":
                self.assertTrue(seam.endswith(inset))

    def test_panel_button_colors_default_to_the_panel_palette(self):
        st = styles.Style(name="Fixture", path=None)   # built-in widget defaults only
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertEqual(t["w.panel_button.color"], p["pb_rest"])
        self.assertEqual(t["w.panel_button.selected_color"], p["accent"])
        self.assertEqual(t["w.panel_button.selected_border"], p["accent_press"])
        table = tokens.build(defaults(), st)
        self.assertEqual(table["panel.w.panel_button.selected_fg"], table["panel.accent_fg"])
        self.assertEqual(table["panel.w.panel_button.color_top"], table["panel.pb_rest_top"])

    def test_style_can_set_panel_button_colors(self):
        st = styles.Style(name="Fixture", path=None,
                          widgets={"panel_button": {"color": "mix(bg, text, 0.08)",
                                                    "selected_color": "mix(bg, text, 0.30)"}})
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertEqual(t["w.panel_button.color"], palette.mix(p["bg"], p["text"], 0.08))
        self.assertNotEqual(t["w.panel_button.selected_color"], p["accent"])
        table = tokens.build(defaults(), st)
        self.assertEqual(table["panel.w.panel_button.selected_fg"], table["panel.text"])

    def test_panel_button_padding(self):
        t = tokens.build(defaults(), styles.Style(name="Fixture", path=None))
        self.assertEqual(t["panel.w.panel_button.padding"], "4")
        st = styles.Style(name="Fixture", path=None, widgets={"panel_button": {"padding": 8}})
        self.assertEqual(tokens.build(defaults(), st)["panel.w.panel_button.padding"], "8")
        self.assertEqual(t["panel.w.panel_button.spacing"], "2")
        st = styles.Style(name="Fixture", path=None, widgets={"panel_button": {"spacing": 0}})
        self.assertEqual(tokens.build(defaults(), st)["panel.w.panel_button.spacing"], "0")
        d = Path(tempfile.mkdtemp())
        (d / "style.toml").write_text('name = "T"\n[widgets]\npanel_button = { padding = 99 }\n')
        with self.assertRaises(styles.StyleError):
            styles.load(d)

    def test_style_can_choose_hover_text(self):
        st = styles.Style(name="Fixture", path=None, widgets={
            "menu_item": {"hover_color": "accent_hover", "hover_fg": "accent_fg"},
            "menubar_item": {"like": "menu_item", "hover_color": "menubar_hover"}})
        t = tokens.build(defaults(), st)
        self.assertEqual(t["w.menu_item.hover_fg"], t["accent_fg"])
        self.assertEqual(t["menu.w.menu_item.hover_fg"], t["menu.accent_fg"])
        # menubar sets its own face, so it doesn't inherit the white text
        self.assertEqual(t["w.menubar_item.hover_fg"], t["text"])
        # without hover_fg the contrast pick stays
        plain = tokens.build(defaults(), styles.Style(name="Fixture", path=None,
                             widgets={"menu_item": {"hover_color": "accent_hover"}}))
        self.assertEqual(plain["w.menu_item.hover_fg"], plain["text"])

    def test_style_panel_color(self):
        base = tokens.build(defaults(), styles.Style(name="Fixture", path=None))
        st = styles.Style(name="Fixture", path=None, panel={"color": "mix(bg, white, 0.4)"})
        t = tokens.build(defaults(), st)
        self.assertEqual(t["panel.panel"], palette.mix(t["panel.bg"], "#FFFFFF", 0.4))
        self.assertNotEqual(t["panel.panel"], base["panel.panel"])
        out = render.render_text("rgba({{panel.panel_rgb}}, {{panel.opacity}})", t)
        self.assertEqual(out, f"rgba({palette.rgb_triplet(t['panel.panel'])}, {t['panel.opacity']})")
        d = Path(tempfile.mkdtemp())
        (d / "style.toml").write_text('name = "T"\n[panel]\ncolor = "nonsense("\n')
        with self.assertRaises(styles.StyleError):
            styles.load(d)

    def test_scrollbar_widget(self):
        t = tokens.build(defaults(), styles.Style(name="Fixture", path=None))
        self.assertEqual(t["w.scrollbar.color"], t["scroll_slider"])
        self.assertEqual(t["w.scrollbar.pressed_color"], t["accent_press"])
        self.assertEqual(t["w.scrollbar.outline"], "transparent")
        st = styles.Style(name="Fixture", path=None, widgets={"scrollbar": {
            "color": "accent", "hover_color": "accent_hover", "border": "accent_press"}})
        t = tokens.build(defaults(), st)
        self.assertEqual(t["w.scrollbar.color"], t["accent"])
        self.assertEqual(t["w.scrollbar.outline"], t["accent_press"])

    def test_scrollbar_mode_follows_mint_unless_chosen(self):
        st = styles.Style(name="Fixture", path=None)
        self.assertEqual(tokens.build(defaults(), st)["scrollbar.mode"], "overlay")
        off = tokens.build(defaults(), st, overlay_scrollbars=False)
        self.assertEqual((off["scrollbar.mode"], off["scrollbar.width"]), ("classic", "10"))
        s = defaults()
        s["details"]["scrollbars"].update(custom=True, mode="overlay")
        self.assertEqual(tokens.build(s, st, overlay_scrollbars=False)["scrollbar.mode"], "overlay")

    def test_scrollbar_radius_includes_the_clear_border(self):
        st = styles.Style(name="Fixture", path=None)
        for r, want in ((0, 4), (50, 6), (100, 9)):      # classic: 10px thumb + 4px clear border
            s = defaults()
            s["details"]["scrollbars"].update(custom=True, mode="classic", roundness=r)
            self.assertEqual(tokens.build(s, st)["scrollbar.r"], str(want), r)

    def test_gtk4_shadows_double_the_blur(self):
        st = styles.Style(name="Fixture", path=None, edges={"raised": {
            "border": "border_strong", "highlight": {"y": 2, "blur": 2, "color": "white", "alpha": 0.6}}})
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertIn("inset 0 4px 2px -2px", t["w.button.shadow"])        # GTK 3
        self.assertIn("inset 0 6px 4px -4px", t["w.button.g4_shadow"])     # GTK 4: blur x2
        # GTK 4 inset layers are solid colours (GTK 4.14's GPU renderer draws
        # partly transparent light shadows as solid white)
        self.assertNotIn("rgba(255, 255, 255", t["w.button.g4_shadow"])
        self.assertIn("rgba(255, 255, 255, 0.6)", t["w.button.shadow"])  # GTK 3 unchanged

    def test_tabs_drop_the_page_facing_layer(self):
        sh = ("inset 0 4px 2px -2px rgba(255, 255, 255, 0.6), inset 3px 0 2px -2px rgba(255, 255, 255, 0.5), "
              "inset -5px 0 3px -3px rgba(0, 0, 0, 0.03), inset 0 -5px 3px -3px rgba(0, 0, 0, 0.03)")
        self.assertNotIn("inset 0 4px", tabs.without_side(sh, "top"))       # bottom tabs: no highlight
        self.assertNotIn("inset -5px", tabs.without_side(sh, "right"))      # left tabs: no right edge
        self.assertEqual(len(tabs.split_shadows(tabs.without_side(sh, "bottom"))), 3)
        self.assertEqual(tabs.without_side("none", "top"), "none")
        t = tokens.build(defaults(), styles.load(REPO / "styles" / "xl-Classic"))
        self.assertIn("g4_", "".join(k for k in t if k.startswith("w.button.g4")))
        self.assertNotEqual(t["tabs.css"], t["tabs4.css"])                 # GTK 4 tabs use GTK 4 blur

    def test_glass_gradient(self):
        g = palette.gradient_css("#FFFFFF", "#000000", "glass", 0.6, 0.4)
        stops = g[len("linear-gradient(to bottom, "):-1].split(", ")
        self.assertEqual(stops[0], "#FFFFFF")
        self.assertEqual(stops[2], "#000000 50%")              # the darkest at the middle
        self.assertEqual(stops[3], palette.mix("#000000", "#FFFFFF", 0.4))   # back up, lighter
        self.assertGreater(palette.luminance(stops[3]), palette.luminance("#000000"))
        errors, warnings = styles.check({"name": "G", "gradient_shape": "glass", "glass_return": 0.5})
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        errors, _w = styles.check({"name": "G", "gradient_shape": "glass", "glass_return": 2})
        self.assertTrue(any("glass_return" in e for e in errors))
        _e, warnings = styles.check({"name": "G", "glass_return": 0.5})        # not glass: ignored
        self.assertTrue(any("glass_return" in w for w in warnings))

    def test_split_gradient(self):
        self.assertEqual(palette.gradient_css("#FFFFFF", "#000000"), "linear-gradient(to bottom, #FFFFFF, #000000)")
        split = palette.gradient_css("#FFFFFF", "#000000", "split", 1.0)
        self.assertIn("#FFFFFF 50%", split)                    # step 1: flat top half
        self.assertEqual(split.count("50%"), 2)                # two stops at the middle: the step
        st = styles.Style(name="Fixture", path=None, gradient_shape="split", split_step=0.6)
        t = tokens.build(defaults(), st)
        self.assertIn("50%", t["button_grad"])
        self.assertNotIn("50%", tokens.build(defaults(), styles.Style(name="F", path=None))["button_grad"])
        d = Path(tempfile.mkdtemp())
        (d / "style.toml").write_text('name = "T"\ngradient_shape = "wavy"\n')
        with self.assertRaises(styles.StyleError):
            styles.load(d)

    def test_lift_is_lighter_on_light_and_gentle_on_dark(self):
        light = {"bg": "#F5F5F5", "text": "#303030", "header": "#E8E8E8"}
        self.assertEqual(render.evaluate("lift(header, 0.7)", light), render.evaluate("lighter(header, 0.7)", light))
        dark = {"bg": "#2B2D31", "text": "#E6E6E6", "header": "#3B4252"}
        lifted = render.evaluate("lift(header, 0.7)", dark)
        self.assertLess(palette.luminance(lifted), 0.2)                   # still a dark face
        self.assertGreater(palette.luminance(lifted), palette.luminance("#3B4252"))

    def test_lift_follows_hover_strength(self):
        st = styles.load(DEFAULT_STYLE)
        base = tokens.build(defaults(), st)["w.tab.hover_color"]
        strong = defaults(); strong["global"]["hover_strength"] = 100
        weak = defaults(); weak["global"]["hover_strength"] = 10
        hs, hw = tokens.build(strong, st)["w.tab.hover_color"], tokens.build(weak, st)["w.tab.hover_color"]
        tokens.build(defaults(), st)                          # leave the default scale behind
        self.assertGreater(palette.luminance(hs), palette.luminance(base))
        self.assertLess(palette.luminance(hw), palette.luminance(base))

    def test_title_bar_buttons_follow_a_contrasting_title_bar(self):
        st = styles.load(DEFAULT_STYLE)
        same = tokens.build(defaults(), st)
        self.assertEqual(same["wbp.w.title_button.hover_color"], same["w.title_button.hover_color"])
        s = defaults()
        s["window_borders"].update(separate_colors=True, title_bar="#3B4252", title_text="#ECEFF4")
        t = tokens.build(s, st)
        self.assertLess(palette.luminance(t["wbp.w.title_button.hover_color"]), 0.2)   # dark, not light

    def test_claude_tabs_and_preset(self):
        st = styles.Style(name="Fixture", path=None, widgets={"tab": {"tab_kind": "claude"}})
        t = tokens.build(defaults(), st)
        self.assertIn("radial-gradient(ellipse 16px 3px at 50% 0", t["tabs.css"])   # top tabs: bar on top
        self.assertIn("at 50% 100%", t["tabs.css"])                                 # bottom tabs: on the bottom
        self.assertIn("radial-gradient", t["tabs_adw.css"])                         # libadwaita tab bar too
        preset = json.loads((REPO / "presets" / "global" / "claude.json").read_text())
        p = palette.derive(preset["global"]["accent"], preset["global"]["bg"], preset["global"]["text"])
        self.assertGreaterEqual(palette.contrast(p["text"], p["bg"]), 7)
        self.assertGreaterEqual(palette.contrast(p["accent_fg"], p["accent"]), 4.5)  # text on accent readable

    def test_panel_marker(self):
        p = palette.derive(settings.DEFAULTS["global"]["accent"], "#F5F5F5", "#303030")
        none = tokens.build(defaults(), styles.Style(name="Fixture", path=None))
        self.assertNotIn("box-shadow", none["panel_marker.css"])
        for kind, want in (("line", "inset 0 -3px 0 0 "),
                           ("glow", "inset 0 -30px 20px -20px rgba(")):
            st = styles.Style(name="Fixture", path=None,
                              widgets={"panel_button": {"active_marker": kind,
                                                        "selected_color": "mix(bg, text, 0.3)"}})
            t = tokens.build(defaults(), st, panel_height=40)
            self.assertIn(want, t["panel_marker.css"])
            self.assertIn(":focus", t["panel_marker.css"])
        # on an accent face the marker uses the darker accent so it still shows
        st = styles.Style(name="Fixture", path=None, widgets={"panel_button": {"active_marker": "line"}})
        self.assertIn(p["accent_press"], tokens.build(defaults(), st)["panel_marker.css"])

    def test_title_buttons_have_nothing_at_rest(self):
        st = styles.load(DEFAULT_STYLE)
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertEqual(t["w.title_button.border"], "transparent")
        self.assertEqual(t["w.title_button.shadow"], "none")
        self.assertNotEqual(t["w.title_button.hover_shadow"], "none")
        self.assertEqual(t["w.close_button.hover_color"], p["accent"])

    def test_depth_zero_is_flat(self):
        st = styles.load(DEFAULT_STYLE)
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 0)
        self.assertEqual(t["w.button.shadow"], "none")

    def test_depth_scales_alpha(self):
        st = styles.Style(name="Fixture", path=None)
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        lo = styles.widget_tokens(st, p, 25)["w.button.shadow"]
        hi = styles.widget_tokens(st, p, 100)["w.button.shadow"]
        self.assertIn("0.3)", lo)   # highlight 0.6 × 0.5
        self.assertIn(", 1)", hi)   # highlight 0.6 × 2, capped at 1

    def test_float_accent_shadow_is_tinted(self):
        st = styles.load(FLOAT_STYLE)
        p = palette.derive("#2F7DE1", "#EEF1F5", "#2A3140")
        t = styles.widget_tokens(st, p, 60)
        self.assertIn(palette.rgb_triplet("#2F7DE1"), t["w.suggested.shadow"])
        self.assertEqual(t["w.suggested.border"], "transparent")

    def test_menu_item_hover_color(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        cheese = styles.widget_tokens(styles.load(DEFAULT_STYLE), p, 50)
        flt = styles.widget_tokens(styles.load(FLOAT_STYLE), p, 50)
        self.assertEqual(cheese["w.menu_item.hover_color"], p["menu_hover"])
        self.assertEqual(flt["w.menu_item.hover_color"], p["select"])

    def test_check_reports_problems(self):
        errors, warnings = styles.check({
            "name": "Broken",
            "edges": {"raised": {"border": "chartreuse", "shadow": {"y": 1}}},
            "widgets": {"button": {"edge": "missing"}, "gizmo": {}, "combo": {"like": "combo"}},
        })
        joined = " ".join(errors)
        self.assertIn("edges.raised.border", joined)
        self.assertIn("needs a color", joined)
        self.assertIn("doesn't exist", joined)
        self.assertIn("circle", joined)
        self.assertTrue(any("gizmo" in w for w in warnings))

    def test_surface_layers_adapt_to_darker_buttons(self):
        st = styles.Style(name="X", path=None, edges={"raised": {
            "border": "border_strong",
            "highlight": {"y": 1, "color": "white", "alpha": 0.6},
            "shadow": {"y": 1, "blur": 2, "color": "black", "alpha": 0.1}}})
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        normal = t["w.button.shadow"].split(", 0 1px 2px")[0]
        coral = t["w.suggested.shadow"].split(", 0 1px 2px")[0]
        self.assertIn("0.6)", normal)                  # as written on the normal button
        self.assertNotIn("0.6)", coral)                # toned down on coral
        self.assertIn("0 1px 2px rgba(0, 0, 0, 0.1)", t["w.suggested.shadow"])  # drop shadow unchanged
        st.edges["raised"]["highlight"]["adaptive"] = False
        t = styles.widget_tokens(st, p, 50)
        self.assertIn("rgba(255, 255, 255, 0.6)", t["w.suggested.shadow"])

    def test_adapt_strength_and_destructive(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        edges = {"raised": {"border": "border_strong", "highlight": {"y": 1, "color": "white", "alpha": 0.6}}}
        full = styles.Style(name="X", path=None, edges=edges, adapt_strength=1.0)
        soft = styles.Style(name="X", path=None, edges=edges, adapt_strength=0.6)
        none = styles.Style(name="X", path=None, edges=edges, adapt_strength=0.0)
        a = lambda st, w: float(styles.widget_tokens(st, p, 50)[f"w.{w}.shadow"].split(", ")[-1].rstrip(")"))
        self.assertLess(a(full, "suggested"), a(soft, "suggested"))
        self.assertEqual(a(none, "suggested"), 0.6)
        self.assertLess(a(soft, "destructive"), 0.6)   # red buttons adapt too
        errors, _ = styles.check({"name": "X", "edges": {"raised": {
            "highlight": {"y": 1, "color": "white", "alpha": 0.5, "adaptive": False}}}})
        self.assertEqual(errors, [])   # adaptive = false is accepted
        errors, _ = styles.check({"name": "X", "adapt_strength": 2})
        self.assertTrue(errors)

    def test_style_defaults(self):
        s = settings.apply_style_defaults(defaults(), {"roundness": 30, "gradient": 5, "depth": 70})
        self.assertEqual((s["global"]["roundness"], s["global"]["gradient"], s["style"]["depth"]), (30, 5, 70))
        self.assertTrue(s["panel"]["panel_shape"]["follow_global"])
        s = settings.apply_style_defaults(defaults(), {"roundness": 30, "panel_gradient": 40,
                                                      "panel_label_weight": "regular", "menu_opacity": 90})
        ps = s["panel"]["panel_shape"]
        self.assertEqual((ps["follow_global"], ps["roundness"], ps["gradient"]), (False, 30, 40))
        self.assertTrue(s["panel"]["menu_shape"]["follow_global"])
        self.assertEqual((s["panel"]["label_weight"], s["panel"]["menu_opacity"]), ("regular", 90))
        errors, warnings = styles.check({"name": "X", "defaults": {"panel_label_weight": "heavy",
                                                                   "panel_opacity": 10, "nope": 1}})
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("nope" in w for w in warnings))

    def test_fresh_install_uses_style_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "missing.json"
            theme = Path(tmp) / "xl-Cheeselooks"
            rc = cli.main(["apply", "--settings", str(cfg), "--theme-dir", str(theme), "--no-save"])
            self.assertEqual(rc, 0)
            saved = json.loads((Path(tmp) / ".xl-Cheeselooks.settings.json").read_text())
            st = styles.load(DEFAULT_STYLE)
            self.assertEqual(saved["global"]["roundness"], st.defaults["roundness"])

    def test_linked_widget(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        base = styles.Style(name="X", path=None)
        t = styles.widget_tokens(base, p, 50)
        self.assertEqual(t["w.linked.hover_border"], t["w.button.hover_border"])   # copies button by default
        tuned = styles.Style(name="X", path=None,
                             edges={"linked_hover": {"border": "darker(border_hover, 0.3)"}},
                             widgets={"linked": {"like": "button", "hover_edge": "linked_hover"}})
        t2 = styles.widget_tokens(tuned, p, 50)
        self.assertEqual(t2["w.linked.hover_border"], palette.darker(p["border_hover"], 0.3))
        self.assertEqual(t2["w.button.hover_border"], t["w.button.hover_border"])  # buttons unchanged

    def test_focus_ring(self):
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        self.assertEqual((t["focus.style"], t["focus.width"]), ("dashed", "1"))
        s = defaults()
        s["details"]["focus_ring"].update({"custom": True, "width": 0})
        self.assertEqual(tokens.build(s, styles.load(DEFAULT_STYLE))["focus.style"], "none")

    def test_sides_layer(self):
        st = styles.Style(name="X", path=None, edges={"raised": {
            "border": "border_strong",
            "highlight": {"y": 1, "color": "white", "alpha": 0.6},
            "sides": {"color": "white", "alpha": 0.5}}})
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertIn("inset 1px 0 0 rgba(255, 255, 255, 0.5), inset -1px 0 0 rgba(255, 255, 255, 0.5)",
                      t["w.button.shadow"])
        self.assertNotIn("-1px 0 0", t["w.button.st_shadow"])  # Cinnamon keeps one layer only
        self.assertEqual(styles.check({"name": "X", "edges": {"raised": {
            "sides": {"color": "white", "alpha": 0.5}}}})[0], [])
        st = styles.Style(name="X", path=None, edges={"raised": {
            "border": "border_strong",
            "highlight": {"y": 2, "color": "white", "alpha": 0.6, "adaptive": False},
            "left": {"x": 2, "blur": 2, "color": "white", "alpha": 0.6, "adaptive": False},
            "right": {"color": "black", "alpha": 0.3, "adaptive": False},
            "shade": {"y": -2, "blur": 2, "color": "black", "alpha": 0.3, "adaptive": False}}})
        t = styles.widget_tokens(st, p, 50)["w.button.shadow"]
        self.assertIn("inset 4px 0 2px -2px rgba(255, 255, 255, 0.6)", t)  # left, fading, kept off top/bottom
        self.assertIn("inset -1px 0 0 rgba(0, 0, 0, 0.3)", t)            # right, crisp
        self.assertIn("inset 0 -4px 2px -2px rgba(0, 0, 0, 0.3)", t)      # bottom, fading, kept off the sides
        _, warnings = styles.check({"name": "X", "edges": {"raised": {
            "sides": {"y": 1, "color": "white", "alpha": 0.5}}}})
        self.assertTrue(any("width is x" in w for w in warnings))

    def test_color_expressions_in_styles(self):
        errors, _ = styles.check({"name": "X", "edges": {"raised": {"border": "darker(border_strong, 0.1)"}}})
        self.assertEqual(errors, [])
        errors, _ = styles.check({"name": "X", "edges": {"raised": {"border": "darker(nope, 0.1)"}}})
        self.assertTrue(errors)
        st = styles.Style(name="X", path=None, edges={"raised": {"border": "darker(border_strong, 0.5)"}})
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertEqual(t["w.button.border"], palette.darker(p["border_strong"], 0.5))

    def test_cli_check_style(self):
        self.assertEqual(cli.main(["check-style", str(DEFAULT_STYLE)]), 0)


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.style = styles.load(DEFAULT_STYLE)

    def test_build_defaults(self):
        t = tokens.build(defaults(), self.style)
        self.assertEqual(t["accent"], settings.DEFAULTS["global"]["accent"])
        self.assertEqual(t["accent_rgb"], palette.rgb_triplet(settings.DEFAULTS["global"]["accent"]))
        self.assertEqual(t["is_dark"], "false")
        self.assertEqual(t["panel.accent"], t["accent"])  # panel follows Global
        self.assertEqual(t["wb.title_bottom"], t["header"])  # title bar ends on toolbar color
        self.assertEqual(t["term.bg"], t["base"])
        self.assertEqual(t["tooltip.bg"], t["menu_bg"])
        self.assertEqual(t["switch.r"], "11")  # fully round by default (22px tall)
        self.assertEqual(t["w.menu_item.hover_fg"], t["text"])
        self.assertTrue(all(isinstance(v, str) for v in t.values()))

    def test_separate_panel_colors(self):
        s = settings.apply_preset(defaults(), json.loads(
            (REPO / "presets/panel/coral-night-panel.json").read_text()))
        t = tokens.build(s, self.style)
        self.assertEqual(t["panel.bg"], "#2B2B2B")
        self.assertEqual(t["menu.bg"], "#2B2B2B")
        self.assertEqual(t["bg"], "#F5F5F5")

    def test_panel_and_menu_shapes(self):
        s = defaults()
        s["panel"]["panel_shape"] = {"follow_global": False, "roundness": 100, "gradient": 0}
        s["panel"]["menu_shape"] = {"follow_global": False, "roundness": 0, "gradient": 0}
        t = tokens.build(s, self.style, panel_height=40)
        self.assertEqual(t["panel.r"], "20")
        self.assertEqual(t["menu.r"], "0")
        self.assertEqual(t["panel.pb_rest_top"], t["panel.pb_rest_bottom"])

    def test_opacity(self):
        t = tokens.build(defaults(), self.style)
        self.assertEqual((t["panel.opacity"], t["menu.opacity"]), ("0.7", "0.94"))
        s = defaults()
        s["panel"]["menu_opacity"] = 60
        self.assertTrue(any("see-through" in n for n in tokens.warnings(s)))
        with self.assertRaises(settings.SettingsError):
            settings.from_dict({"panel": {"panel_opacity": 10}})

    def test_old_marker_names_are_rejected(self):
        d = Path(tempfile.mkdtemp())
        (d / "style.toml").write_text('name = "T"\n[widgets]\ntab = { active_marker = "accent_top" }\n')
        with self.assertRaises(styles.StyleError):
            styles.load(d)

    def test_tab_kinds_and_markers(self):
        s = defaults()
        css = tokens.build(s, self.style)["tabs.css"]
        self.assertIn("tabs: boxed, selected marker: none", css)
        for kind, marker, expect, bottom in (("open", "line", "inset 0 2px 0", "inset 0 -2px 0"),
                                             ("pills", "glow", "8px -8px", "inset 0 -1px 0 #"),
                                             ("boxed", "line", "inset 0 2px 0", "inset 0 -2px 0")):
            st = styles.Style(name="T", path=None, widgets={"tab": {"tab_kind": kind, "active_marker": marker}})
            css = tokens.build(s, st)["tabs.css"]
            self.assertIn(expect, css, (kind, marker))
            self.assertIn(bottom, css)          # bottom tabs get the marker on their bottom edge
        self.assertIn("border-bottom-style: solid", tokens.build(s, self.style)["tabs.css"])  # boxed: edge facing the page
        st = styles.Style(name="T", path=None, widgets={"tab": {"tab_kind": "pills", "active_marker": "glow"}})
        t = tokens.build(s, st)
        self.assertIn(f"padding: 3px;\n  background-color: {t['header']}", t["tabs.css"])  # trough = toolbar color
        self.assertIn("inset 0 1px 0", t["tabs.css"])      # glow edge line is 1px

    def test_layout_and_accent_name(self):
        s = defaults()
        s["window_borders"]["button_layout"] = "left"
        t = tokens.build(s, self.style)
        self.assertEqual(t["wb.button_layout"], "close,minimize,maximize:")
        self.assertEqual(t["adw.accent_name"], "orange")
        self.assertEqual(tokens.nearest_adw_accent("#3584E4"), "blue")
        self.assertEqual(tokens.nearest_adw_accent("#808080"), "slate")


class RenderAndInstallTests(unittest.TestCase):
    def test_unknown_token_is_an_error(self):
        with self.assertRaises(render.TemplateError) as ctx:
            render.render_text("a {{accent}}\nb {{nope}}", {"accent": "#000000"}, "x.css")
        self.assertIn("x.css:2", ctx.exception.problems[0])

    def test_window_borders_xml(self):
        import xml.dom.minidom
        st = styles.load(DEFAULT_STYLE)
        for width in (0, 1, 6):
            s = defaults()
            s["window_borders"]["border_width"] = width
            with tempfile.TemporaryDirectory() as tmp:
                theme = Path(tmp) / "xl-Cheeselooks"
                install.install(REPO / "templates", tokens.build(s, st), theme, Path(tmp) / "good")
                meta = theme / "metacity-1"
                text = (meta / "metacity-theme-3.xml").read_text()
                doc = xml.dom.minidom.parseString(text)          # well-formed
                border = [d for d in doc.getElementsByTagName("draw_ops")
                          if d.getAttribute("name") == "border_focused"][0]
                drawn = border.getElementsByTagName("rectangle") + border.getElementsByTagName("arc")
                self.assertEqual(bool(drawn), width > 0, width)   # nothing at all at width 0
                # Metacity/Muffin reject newer features without version guards
                for title in doc.getElementsByTagName("title"):
                    if title.hasAttribute("ellipsize_width"):
                        self.assertEqual(title.getAttribute("version"), ">= 3.1")
                for name in ("close-icon.svg", "max-icon.svg"):
                    self.assertTrue((meta / name).exists(), name)
                # every image a draw op names is in the theme
                for img in doc.getElementsByTagName("image"):
                    self.assertTrue((meta / img.getAttribute("filename")).exists(), img.getAttribute("filename"))
                self.assertNotIn("{{", text)

    def test_title_button_styles(self):
        import xml.dom.minidom
        from cheeselooks import titlebuttons
        st = styles.load(DEFAULT_STYLE)
        for name in titlebuttons.STYLES:
            for layout in ("right", "left"):
                s = defaults()
                s["window_borders"]["button_style"] = name
                s["window_borders"]["button_layout"] = layout
                with tempfile.TemporaryDirectory() as tmp:
                    theme = Path(tmp) / "xl-Cheeselooks"
                    install.install(REPO / "templates", tokens.build(s, st), theme, Path(tmp) / "good")
                    meta = theme / "metacity-1"
                    doc = xml.dom.minidom.parseString((meta / "metacity-theme-3.xml").read_text())
                    for img in doc.getElementsByTagName("image"):
                        f = meta / img.getAttribute("filename")
                        self.assertTrue(f.exists(), (name, f.name))
                        if f.name.startswith("tb-"):
                            xml.dom.minidom.parseString(f.read_text())     # well-formed SVG
                    for css in ("gtk-3.0/xl.css", "gtk-4.0/xl.css"):
                        text = (theme / css).read_text()
                        self.assertIn(f"Title buttons: {titlebuttons.STYLES[name]}", text)
                    import re as _re
                    for folder in ("gtk-3.0", "gtk-4.0", "libadwaita-1.5"):
                        for css in (theme / folder).glob("*.css"):
                            for url in _re.findall(r'url\("(assets/tb-[^"]+)"\)', css.read_text()):
                                self.assertTrue((theme / folder / url).exists(), (name, folder, url))

    def test_glyph_sets(self):
        import re as _re
        import xml.dom.minidom
        from cheeselooks import titlebuttons
        st = styles.load(DEFAULT_STYLE)
        for style in ("drawn", "dots", "gargantuan", "classic"):
            for glyphs in list(titlebuttons.GLYPH_SET_NAMES) + [None]:
                s = defaults()
                s["window_borders"].update(button_style=style, button_glyphs=glyphs)
                with tempfile.TemporaryDirectory() as tmp:
                    theme = Path(tmp) / "xl-Cheeselooks"
                    install.install(REPO / "templates", tokens.build(s, st), theme, Path(tmp) / "good")
                    meta = theme / "metacity-1"
                    doc = xml.dom.minidom.parseString((meta / "metacity-theme-3.xml").read_text())
                    for img in doc.getElementsByTagName("image"):
                        self.assertTrue((meta / img.getAttribute("filename")).exists(), (style, glyphs))
                    css = (theme / "gtk-3.0" / "xl.css").read_text()
                    for url in _re.findall(r'url\("(assets/tb-[^"]+)"\)', css):
                        self.assertTrue((theme / "gtk-3.0" / url).exists(), (style, glyphs, url))
        self.assertEqual(titlebuttons.glyph_set("dots", None), "marks")       # the style's own
        self.assertEqual(titlebuttons.glyph_set("dots", "thin"), "thin")      # yours wins
        s = defaults()
        s["window_borders"]["button_style"] = "arrows"                        # renamed
        self.assertEqual(settings.from_dict(s)["window_borders"]["button_style"], "unpretentious")

    def test_old_button_style_names(self):
        s = defaults()
        s["window_borders"]["button_style"] = "theme"
        self.assertEqual(settings.from_dict(s)["window_borders"]["button_style"], "flat")

    def test_libadwaita_block(self):
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        self.assertGreaterEqual(palette.contrast(t["adw.accent_text"], t["bg"]), 4.5)
        old_style = gtk4.block(REPO / "templates", t, css_variables=False)
        new_style = gtk4.block(REPO / "templates", t, css_variables=True)
        self.assertIn(f"@define-color accent_bg_color {t['accent']};", old_style)
        self.assertNotIn(":root", old_style)
        self.assertIn(f"--accent-bg-color: {t['accent']};", new_style)
        self.assertTrue(old_style.startswith(gtk4.BEGIN) and old_style.rstrip().endswith(gtk4.END))

    def test_libadwaita_theme_folder(self):
        # Mint's patched libadwaita reads <theme>/libadwaita-1.5/
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "xl-Cheeselooks"
            t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
            install.install(REPO / "templates", t, theme, Path(tmp) / "good")
            adw = theme / "libadwaita-1.5"
            for name in ("base.css", "base-hc.css", "defaults-light.css", "defaults-dark.css"):
                self.assertTrue((adw / name).is_file(), name)
            light = (adw / "defaults-light.css").read_text()
            self.assertEqual(light, (adw / "defaults-dark.css").read_text())   # your colours either way
            self.assertIn(f"@define-color accent_bg_color {t['accent']};", light)
            base = (adw / "base.css").read_text()
            self.assertIn("xl-Cheeselooks for libadwaita", base)          # our layer is appended
            self.assertIn("windowcontrols > button:not(.osd):hover", base)  # our title buttons
            self.assertIn("toolbarview > .top-bar", base)                   # title gradient on headers
            self.assertIn("libadwaita tab bar", base)                       # AdwTabBar in the tab style
            self.assertIn("windowcontrols > button:hover > image", base)    # no circle behind icons
            self.assertNotIn("{{", base)
            self.assertNotIn("@mint_button_hover; border-radius: 100%", base)   # Mint's round ones gone
            self.assertFalse(list(adw.glob("*.part")))
            self.assertTrue((adw / "assets").is_dir())

    def test_gtk4_theme_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "xl-Cheeselooks"
            t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
            install.install(REPO / "templates", t, theme, Path(tmp) / "good")
            g4 = theme / "gtk-4.0"
            for name in ("gtk.css", "gtk-dark.css", "base.css", "xl.css",
                         "assets/check-symbolic.svg", "assets/bullet-symbolic.svg"):
                self.assertTrue((g4 / name).is_file(), name)
            base = (g4 / "base.css").read_text()
            self.assertNotIn("#35A854", base.upper())        # Mint's green accent is gone
            self.assertNotIn('url("assets/checkbox', base)   # green check images removed
            xl = (g4 / "xl.css").read_text()
            self.assertIn("windowcontrols > button:hover", xl)
            self.assertNotIn("-gtk-outline-radius", xl)      # GTK 4 would warn
            self.assertIn(t["accent"], xl)

    def test_libadwaita_block_keeps_the_users_css(self):
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        blk = gtk4.block(REPO / "templates", t, css_variables=False)
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "gtk.css"
            css.write_text("window { font-size: 12pt; }\n")
            self.assertIn("added", gtk4.write(css, blk))
            backup = css.with_name("gtk.css.xl-cheeselooks-backup")
            self.assertEqual(backup.read_text(), "window { font-size: 12pt; }\n")
            self.assertEqual(gtk4.write(css, blk), "")                 # unchanged: nothing to do
            blk2 = blk.replace(t["accent"], "#123456")
            gtk4.write(css, blk2)
            text = css.read_text()
            self.assertEqual(text.count(gtk4.BEGIN), 1)                # replaced, not added twice
            self.assertIn("#123456", text)
            self.assertIn("window { font-size: 12pt; }", text)         # the user's line is kept
            backup.write_text("first backup")
            gtk4.write(css, blk)
            self.assertEqual(backup.read_text(), "first backup")       # backup only the first time
            self.assertIn("removed", gtk4.write(css, None))
            self.assertEqual(css.read_text().strip(), "window { font-size: 12pt; }")
            fresh = Path(tmp) / "new" / "gtk.css"
            gtk4.write(fresh, blk)                                     # no file yet: created
            self.assertTrue(fresh.read_text().startswith(gtk4.BEGIN))

    def test_flatpak_undo_keeps_other_overrides(self):
        text = "[Context]\nfilesystems=~/Music:ro;xdg-config/gtk-4.0:ro;~/.themes:ro;\n[Environment]\nFOO=1\n"
        out = flatpak.remove_ours(text)
        self.assertIn("filesystems=~/Music:ro;", out)
        self.assertNotIn("~/.themes", out)
        self.assertIn("FOO=1", out)                                   # other sections untouched
        only_ours = "[Context]\nfilesystems=~/.themes:ro;xdg-config/gtk-4.0:ro;\n"
        self.assertNotIn("filesystems", flatpak.remove_ours(only_ours))
        # only what we added is removed: a ~/.themes grant you had stays
        kept = flatpak.remove_ours("[Context]\nfilesystems=~/.themes:ro;xdg-config/gtk-4.0:ro;\n",
                                   ["xdg-config/gtk-4.0:ro"])
        self.assertIn("~/.themes:ro", kept)

    def test_theme_thumbnails_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "xl-Cheeselooks"
            install.install(REPO / "templates", tokens.build(defaults(), styles.load(DEFAULT_STYLE)),
                            theme, Path(tmp) / "good")
            for part in ("gtk-3.0", "cinnamon", "metacity-1"):
                data = (theme / part / "thumbnail.png").read_bytes()
                self.assertTrue(data.startswith(b"\x89PNG"), part)

    def test_settings_app_preview_css(self):
        from cheeselooks import app
        t = tokens.build(defaults(), styles.load(REPO / "styles" / "xl-Claude"))
        css = app.SettingsWindow._extra_css(None, t)          # the drawn panel and terminal sample
        self.assertIn(t["panel.w.panel_button.selected_color"], css)
        self.assertEqual(css.count("{"), css.count("}"))              # balanced rules
        controls = {path for path, kind, extra in settings._RULES}
        self.assertIn(("global", "accent"), controls)          # every rule gets a control

    def test_themes_load_save_export_import(self):
        import os, zipfile
        from unittest import mock
        names = [n for n, _f, _b in themes.list_themes()]
        self.assertEqual(names[:4], ["xl-Cheeselooks", "xl-Classic", "xl-Gummy", "Claude"])
        claude = themes.load("Claude")
        self.assertEqual((claude["theme"], claude["style"]["name"], claude["global"]["accent"]),
                         ("Claude", "xl-Claude", "#B85A38"))
        self.assertEqual(claude["global"]["roundness"], 35)          # the style's [defaults] apply
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as home2:
            def use(h):
                return mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": f"{h}/c", "XDG_DATA_HOME": f"{h}/d"})
            with use(home):
                data = copy.deepcopy(claude)
                data["global"]["accent"] = "#2F7DE1"
                themes.save("Blue Claude", data)
                with self.assertRaises(themes.ThemeError):
                    themes.save("Claude", data)                       # built-in names are taken
                with self.assertRaises(themes.ThemeError):
                    themes.save("Blue Claude", data)                  # no silent overwrite
                self.assertEqual(themes.load("Blue Claude")["global"]["accent"], "#2F7DE1")
                themes.save_custom(data, "Claude")
                self.assertEqual((themes.load("Custom")["theme"], themes.based_on()), ("Custom", "Claude"))
                out = themes.export("Blue Claude", data, Path(home) / "blue")
                self.assertEqual(zipfile.ZipFile(out).namelist(), ["theme.json"])   # built-in style: not packed
            with use(home2):
                name, notes = themes.import_file(out)
                self.assertEqual((name, notes), ("Blue Claude", []))
                self.assertEqual(themes.load(name)["global"]["accent"], "#2F7DE1")

    def test_panel_height_apply_and_revert(self):
        from unittest import mock
        from cheeselooks import reload
        store = {"panels-height": "['1:40', '2:30']"}

        def fake_run(cmd, schema, key, value=None):
            if cmd == "get":
                return store.get(key, "''")
            store[key] = value
            return ""
        st = styles.load(DEFAULT_STYLE)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            with mock.patch.object(reload, "_run", fake_run), \
                    mock.patch.object(reload, "available", lambda: True), \
                    mock.patch.object(reload, "apply", lambda *a, **k: []), \
                    mock.patch.object(cli, "_libadwaita", lambda *a: []), \
                    mock.patch.object(cli.paths, "theme_dir", lambda: tmp / "themes" / "xl-Cheeselooks"), \
                    mock.patch.object(cli.paths, "last_good_dir", lambda: tmp / "good"), \
                    mock.patch.object(cli.paths, "settings_file", lambda: tmp / "settings.json"):
                s = defaults()
                cli.apply_to_desktop(s, st)                          # unset: Cinnamon's height untouched
                self.assertEqual(store["panels-height"], "['1:40', '2:30']")
                s["panel"]["panel_height"] = 32
                log = cli.apply_to_desktop(s, st)
                self.assertEqual(store["panels-height"], "['1:32', '2:32']")   # every panel, ids kept
                self.assertIn("panel height set to 32px", log)
                cli.revert_desktop()
                self.assertEqual(store["panels-height"], "['1:40', '2:30']")   # Revert puts it back

    def test_theme_duplicate_and_rename(self):
        import os
        from unittest import mock
        with tempfile.TemporaryDirectory() as home, \
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": f"{home}/c", "XDG_DATA_HOME": f"{home}/d"}):
            self.assertEqual(themes.duplicate("xl-Classic"), "xl-Classic copy")      # built-in -> yours
            self.assertEqual(themes.copy_name("xl-Classic"), "xl-Classic copy 2")
            self.assertEqual(themes.load("xl-Classic copy")["style"]["name"], "xl-Classic")
            themes.save_custom(themes.load("xl-Classic copy"), "xl-Classic copy")
            themes.rename("xl-Classic copy", "Blue Classic")
            names = [n for n, _f, _b in themes.list_themes()]
            self.assertIn("Blue Classic", names)
            self.assertNotIn("xl-Classic copy", names)
            self.assertEqual(themes.based_on(), "Blue Classic")                      # Custom follows
            with self.assertRaises(themes.ThemeError):
                themes.rename("Blue Classic", "xl-Gummy")                           # taken
            with self.assertRaises(themes.ThemeError):
                themes.rename("xl-Gummy", "Mine")                                   # built-in
            with self.assertRaises(themes.ThemeError):
                themes.rename("Blue Classic", "x" * 41)                             # too long

    def test_install_and_revert(self):
        st = styles.load(DEFAULT_STYLE)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            theme, good = tmp / "themes" / "xl-Cheeselooks", tmp / "cache" / "last-good"
            s1 = defaults()
            install.install(REPO / "templates", tokens.build(s1, st), theme, good, s1)
            self.assertTrue((theme / "index.theme").is_file())
            self.assertNotIn("{{", (theme / "index.theme").read_text())

            s2 = settings.apply_preset(defaults(), {"global": {"accent": "#2E9E92"}})
            install.install(REPO / "templates", tokens.build(s2, st), theme, good, s2)
            self.assertTrue((good / "theme" / "index.theme").is_file())

            restored = install.revert(theme, good)
            self.assertEqual(restored["global"]["accent"], settings.DEFAULTS["global"]["accent"])

    def test_cinnamon_theme(self):
        st = styles.load(DEFAULT_STYLE)
        s = settings.apply_preset(defaults(), json.loads(
            (REPO / "presets/panel/coral-night-panel.json").read_text()))
        t = tokens.build(s, st)
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "xl-Cheeselooks"
            install.install(REPO / "templates", t, theme, Path(tmp) / "good")
            css = (theme / "cinnamon" / "cinnamon.css").read_text()
            self.assertNotIn("{{", css)
            self.assertFalse(any(theme.rglob("*.part")))          # parts are only included
            self.assertTrue((theme / "cinnamon" / "assets" / "switch-on.svg").is_file())
            self.assertTrue((theme / "cinnamon" / "common-assets" / "misc" / "close.svg").is_file())
            self.assertIn(f"rgba({t['panel.panel_rgb']}, 0.7)", css)   # separate dark panel at 70%
            self.assertTrue(t["panel.panel"].startswith("#2") or t["panel.panel"].startswith("#3"))
            self.assertNotIn("#35a854", css.lower())             # no Mint green left
            self.assertEqual(css.count("{"), css.count("}"))

    def test_find_style_by_name_not_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            mine = Path(tmp) / "xl-Cheeselooks"                 # a copy, renamed only inside
            mine.mkdir()
            (mine / "style.toml").write_text(
                (REPO / "styles" / "xl-Cheeselooks" / "style.toml").read_text()
                .replace('name = "xl-Cheeselooks"', 'name = "xl-Cheeselooks-mine"', 1))
            dirs = [Path(tmp), REPO / "styles"]
            self.assertEqual(styles.find("xl-Cheeselooks", dirs).path.parent, REPO / "styles" / "xl-Cheeselooks")
            self.assertEqual(styles.find("xl-Cheeselooks-mine", dirs).path.parent, mine)

    def test_recess_layer(self):
        pal_ = palette.derive("#FA8562", "#F5F5F5", "#303030")
        css = styles.edge_css({"border": "border_strong",
                               "recess": {"color": "black", "alpha": 0.1, "light": "white", "light_alpha": 0.5}},
                              pal_, 50)
        # dark up-left, light down-right: they never overlap
        self.assertTrue(css["shadow"].startswith("1px 1px 0 rgba(255, 255, 255, 0.5), -1px -1px 0 rgba(0, 0, 0, 0.1)"))
        self.assertEqual(css["inset_shadow"], "none")             # outside the button: not for joined groups
        errors, _w = styles.check({"name": "R", "edges": {"raised": {"recess": {"color": "black", "light": "nope"}}}})
        self.assertTrue(any("light" in e for e in errors))

    def test_focus_ring(self):
        st = styles.load(DEFAULT_STYLE)
        s = defaults()
        t = tokens.build(s, st)
        self.assertEqual((t["focus.style"], t["focus.width"]), ("dashed", "1"))   # Mint-Y's default
        self.assertIn("0.25)", t["focus.ring"])
        s["details"]["focus_ring"].update(custom=True, color="#3366CC")          # a colour only
        t = tokens.build(s, st)
        self.assertEqual((t["focus.style"], t["focus.width"], t["focus.ring"]),
                         ("dashed", "1", "rgba(51, 102, 204, 1)"))                 # still dashed, 1px
        s["details"]["focus_ring"].update(style="dotted", width=2)
        t = tokens.build(s, st)
        self.assertEqual((t["focus.style"], t["focus.width"]), ("dotted", "2"))
        s["details"]["focus_ring"]["width"] = 0
        self.assertEqual(tokens.build(s, st)["focus.style"], "none")              # width 0: off

    def test_button_color(self):
        base = styles.load(DEFAULT_STYLE)
        plain = tokens.build(defaults(), base)
        widgets = {**base.widgets, "button": {**base.widgets.get("button", {}), "color": "darker(button, 0.1)"}}
        st = styles.Style(**{**base.__dict__, "widgets": widgets})
        t = tokens.build(defaults(), st)
        self.assertEqual(t["button"], palette.darker(plain["button"], 0.1))      # read once, not twice
        self.assertNotEqual(t["button_hover"], plain["button_hover"])           # the hover follows it
        self.assertIn(t["button_top"], t["button_grad"])
        _e, warnings = styles.check({"name": "B", "widgets": {"button": {"color": "darker(button, 0.1)"}}})
        self.assertFalse(any("button.color" in w for w in warnings))

    def test_notification_kinds(self):
        base = styles.load(DEFAULT_STYLE)
        s = defaults()
        s["panel"]["notification_opacity"] = 80
        for kind, want in (("line", "border-top: 4px solid"), ("flat", "border: none;"),
                           ("bordered", "border: 1px solid")):
            st = styles.Style(**{**base.__dict__, "notification": {"kind": kind}})
            t = tokens.build(s, st)
            self.assertIn(want, t["notification.css"])
            self.assertEqual(t["notification.opacity"], "0.8")
        plain = styles.Style(**{**base.__dict__, "notification": {}})    # a style that doesn't set it
        self.assertIn("border-top: 4px solid", tokens.build(s, plain)["notification.css"])  # default: line
        errors, _w = styles.check({"name": "N", "notification": {"kind": "wavy"}})
        self.assertTrue(any("notification.kind" in e for e in errors))

    def test_gtk3_css_parses_at_extremes(self):
        """GTK's own parser accepts the CSS at Depth 0 and 100 (a shadow list
        joined with a "none" once broke the preview at Depth 0)."""
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            from gi.repository import Gtk
        except (ImportError, ValueError):
            self.skipTest("no GTK 3")
        for depth, unfocused in ((0, 0), (100, 100), (50, 70)):
            s = defaults()
            s["style"].update(depth=depth, unfocused_depth=unfocused)
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "theme"
                install.build(REPO / "templates", tokens.build(s, styles.load(DEFAULT_STYLE)), out)
                errors = []
                prov = Gtk.CssProvider()
                prov.connect("parsing-error", lambda _p, sec, err: errors.append(
                    f"{sec.get_file().get_basename() if sec.get_file() else ''}:{sec.get_start_line() + 1}: {err.message}"))
                try:
                    prov.load_from_path(str(out / "gtk-3.0" / "gtk.css"))
                except Exception as exc:       # GLib raises on the first error too
                    errors.append(str(exc))
                self.assertEqual(errors, [], f"depth {depth}, unfocused {unfocused}")

    def test_colors_from_a_picture(self):
        try:
            import gi
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf
        except (ImportError, ValueError):
            self.skipTest("no GdkPixbuf")
        from cheeselooks import imagecolors
        # a mostly grey picture with a band of deep blue: the blue is the accent
        w, h = 40, 40
        data = bytearray()
        for y in range(h):
            for x in range(w):
                data += bytes((40, 90, 200)) if 15 <= y < 25 else bytes((128, 128, 128))
        pix = GdkPixbuf.Pixbuf.new_from_data(bytes(data), GdkPixbuf.Colorspace.RGB, False, 8, w, h, w * 3)
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "p.png"
            pix.savev(str(f), "png", [], [])
            found = imagecolors.colors(f)
        self.assertGreaterEqual(len(found), 2)
        r, g, b = palette.to_rgb(found[0])
        self.assertGreater(b, r + 60)                       # the blue comes first, before the grey
        acc = imagecolors.accent(found)
        self.assertGreater(palette.to_rgb(acc)[2], palette.to_rgb(acc)[0])

    def test_dividers(self):
        base = styles.load(DEFAULT_STYLE)
        s = defaults()
        s["global"].update(bg="#2C2C2C", text="#E6E6E6")
        t = tokens.build(s, base)
        self.assertGreater(palette.luminance(t["dividers"]), palette.luminance("#2C2C2C"))   # default: lighter
        dark = styles.Style(**{**base.__dict__, "dividers": "darker(bg, 0.35)"})
        t = tokens.build(s, dark)
        self.assertLess(palette.luminance(t["dividers"]), palette.luminance("#2C2C2C"))      # the style's: darker
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "theme"
            install.build(REPO / "templates", t, out)
            css = (out / "gtk-3.0" / "base.css").read_text()
        self.assertIn(t["dividers"], css)
        self.assertEqual(styles.check({"name": "N", "dividers": "nope"})[0][0][:8], "dividers")

    def test_menu_category_colour(self):
        base = styles.load(DEFAULT_STYLE)
        plain = styles.Style(**{**base.__dict__, "panel": {}})           # a style that doesn't set it
        t = tokens.build(defaults(), plain)
        self.assertEqual(t["menu.category"], palette.mix(t["menu.menu_bg"], t["menu.text"], 0.123))  # Mint-Y's grey
        accent = styles.Style(**{**base.__dict__, "panel": {**base.panel, "menu_category": "accent"}})
        t = tokens.build(defaults(), accent)
        self.assertEqual((t["menu.category"], t["menu.category_fg"]), (t["menu.accent"], t["menu.accent_fg"]))
        errors, _w = styles.check({"name": "N", "panel": {"menu_category": "accent"}})
        self.assertEqual(errors, [])

    def test_menu_hover_colour(self):
        base = styles.load(DEFAULT_STYLE)
        plain = styles.Style(**{**base.__dict__, "panel": {}})           # a style that doesn't set it
        t = tokens.build(defaults(), plain)
        self.assertEqual((t["menu.main_hover"], t["menu.main_hover_fg"]), (t["menu.menu_hover"], t["menu.text"]))
        self.assertEqual(t["menu.fav_main_hover"], t["menu.fav_hover"])
        accent = styles.Style(**{**base.__dict__, "panel": {"menu_hover": "accent"}})
        t = tokens.build(defaults(), accent)
        self.assertEqual((t["menu.main_hover"], t["menu.main_hover_fg"]), (t["menu.accent"], t["menu.accent_fg"]))
        # the favorites column is darker: its hover is too, by as much
        dm = palette.luminance(t["menu.menu_bg"]) - palette.luminance(t["menu.fav_bg"])
        self.assertGreater(dm, 0)
        self.assertLess(palette.luminance(t["menu.fav_main_hover"]), palette.luminance(t["menu.accent"]))
        fav = styles.Style(**{**base.__dict__, "panel": {"menu_hover": "accent", "menu_fav_hover": "#334455"}})
        self.assertEqual(tokens.build(defaults(), fav)["menu.fav_main_hover"], "#334455")
        own = styles.Style(**{**base.__dict__, "panel": {"menu_hover": "#DDEEFF", "menu_hover_fg": "#112233"}})
        self.assertEqual(tokens.build(defaults(), own)["menu.main_hover_fg"], "#112233")
        errors, _w = styles.check({"name": "N", "panel": {"menu_hover": "accent", "menu_hover_fg": "accent_fg",
                                                          "menu_fav_hover": "accent"}})
        self.assertEqual(errors, [])

    def test_suggested_near_title_bar(self):
        st = styles.load(DEFAULT_STYLE)
        s = defaults()
        s["global"]["accent"] = "#7A9CCF"                         # xl-Classic Dark: a blue accent...
        s["window_borders"].update(separate_colors=True, title_bar="#5178B2", title_text="#FFFFFF")
        t = tokens.build(s, st)                                    # ...on a blue title bar
        self.assertEqual(t["wbp.sug.border"], t["wbp.w.button.border"])
        self.assertIn("bd.wbp.sug.shadow", t)
        s["global"]["accent"] = "#FA8562"                          # coral on blue: its own edges
        t = tokens.build(s, st)
        self.assertEqual(t["wbp.sug.border"], t["wbp.w.suggested.border"])

    def test_reload_swap_link(self):
        # Apply reloads by switching to a hidden link to our own theme and back
        # (Mint-Y flashed before): made beside the theme, removed after
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "xl-Cheeselooks"
            (theme / "gtk-3.0").mkdir(parents=True)
            swap = reload._make_swap(theme, "xl-Cheeselooks")
            self.assertEqual(swap.name, ".xl-Cheeselooks-reloading")
            self.assertTrue((swap / "gtk-3.0").is_dir())             # the same theme, another name
            self.assertEqual(reload._make_swap(theme, "xl-Cheeselooks"), swap)   # a leftover is replaced
            reload._remove_swap(swap)
            self.assertFalse(swap.is_symlink() or swap.exists())
            self.assertTrue(theme.is_dir())                          # the theme itself untouched
            self.assertIsNone(reload._make_swap(Path(tmp) / "missing", "missing"))

    def test_qt_colors_switch(self):
        from unittest import mock
        import os
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            own_profile = "# mine\nexport PATH=$PATH:~/bin\n"
            (home / ".profile").write_text(own_profile)
            conf = home / ".config" / "qt5ct" / "qt5ct.conf"
            conf.parent.mkdir(parents=True)
            conf.write_text("[Appearance]\nicon_theme=Mint-Y\nstandard_dialogs=default\n\n[Fonts]\nfixed=Mono\n")
            original_conf = conf.read_text()
            share = home / ".local" / "share"
            env = {"XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(share)}
            with mock.patch.dict(os.environ, env), \
                 mock.patch.object(qt.paths, "HOME", home), \
                 mock.patch.object(qt, "qt5ct_installed", return_value=True), \
                 mock.patch.object(qt, "flatpak_qt_apps", return_value=["org.videolan.VLC"]):
                os.environ.pop("QT_QPA_PLATFORMTHEME", None)
                os.environ.pop("QT_STYLE_OVERRIDE", None)
                t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
                qt.enable(t)
                scheme = qt.scheme_file().read_text()
                self.assertIn("#ff" + t["accent"].lstrip("#").lower(), scheme)       # highlight = accent
                text = conf.read_text()
                self.assertIn(f"color_scheme_path={qt.scheme_file()}", text)
                self.assertIn("custom_palette=true", text)
                self.assertIn("icon_theme=Mint-Y", text)                                # yours kept
                self.assertIn("standard_dialogs=default", text)                         # your choice kept
                self.assertIn("[Fonts]\nfixed=Mono", text)
                self.assertIn(f"stylesheets={qt.qss_file()}", text)
                qss = qt.qss_file().read_text()
                self.assertIn(f"QMenuBar {{ background-color: {t['header']};", qss)        # the title bar colour
                self.assertIn(t["w.menu_item.hover_top"], qss)                         # GTK's menu hover, not the accent
                profile = (home / ".profile").read_text()
                self.assertIn(qt.PROFILE_LINE, profile)
                self.assertTrue(profile.startswith("# mine"))
                kde = qt.kdeglobals_file("org.videolan.VLC").read_text()
                self.assertIn("[Colors:Selection]", kde)
                override = share / "flatpak" / "overrides" / "org.videolan.VLC"
                self.assertIn("QT_QPA_PLATFORMTHEME=kde", override.read_text())
                self.assertIsNone(qt.pending_notice())                                  # nothing of yours replaced
                qt.enable(t)                                                            # a second Apply
                self.assertEqual((home / ".profile").read_text().count(qt.PROFILE_START), 1)
                qt.disable()
                self.assertEqual(conf.read_text(), original_conf)                       # put back as it was
                self.assertFalse(qt.scheme_file().exists())
                self.assertFalse(qt.qss_file().exists())
                self.assertFalse(qt.kdeglobals_file("org.videolan.VLC").exists())
                self.assertFalse(override.exists())                                     # nothing of ours left
                self.assertEqual((home / ".profile").read_text(), own_profile)
                self.assertFalse(qt.active())

                # A Qt setup of yours: ours takes its place, yours is kept and comes back
                kvantum = "[Appearance]\nstyle=kvantum\ncustom_palette=true\ncolor_scheme_path=/mine.conf\n"
                conf.write_text(kvantum)
                (home / ".profile").write_text("export QT_STYLE_OVERRIDE=kvantum\n")
                override.write_text("[Context]\nfilesystems=xdg-config/Kvantum:ro\n\n"
                                    "[Environment]\nQT_STYLE_OVERRIDE=kvantum\n")
                own_override = override.read_text()
                qt.kdeglobals_file("org.videolan.VLC").write_text("[Colors:Window]\nBackgroundNormal=1,2,3\n")
                qt.enable(t)
                text = conf.read_text()
                self.assertIn("style=Fusion", text)                                     # Kvantum ignores colours
                self.assertIn(f"color_scheme_path={qt.scheme_file()}", text)
                self.assertTrue(conf.with_name("qt5ct.conf" + qt.BACKUP).exists())
                profile = (home / ".profile").read_text()
                self.assertTrue(profile.startswith("export QT_STYLE_OVERRIDE=kvantum"))  # your line untouched...
                self.assertIn("unset QT_STYLE_OVERRIDE", profile)                       # ...ours, after it, wins
                ov = override.read_text()
                self.assertIn("QT_QPA_PLATFORMTHEME=kde", ov)
                self.assertIn("QT_STYLE_OVERRIDE=\n", ov)
                self.assertIn("filesystems=xdg-config/Kvantum:ro", ov)                 # the rest of it kept
                notice = qt.pending_notice()
                self.assertIn("qt5ct", notice)
                self.assertIn("org.videolan.VLC", notice)
                qt.notice_shown()
                self.assertIsNone(qt.pending_notice())                                  # once only
                qt.enable(t)                                                            # next Apply: no new notice
                self.assertIsNone(qt.pending_notice())
                qt.disable()
                self.assertEqual(conf.read_text(), kvantum)
                self.assertEqual((home / ".profile").read_text(), "export QT_STYLE_OVERRIDE=kvantum\n")
                self.assertEqual(override.read_text(), own_override)
                self.assertEqual(qt.kdeglobals_file("org.videolan.VLC").read_text(),
                                 "[Colors:Window]\nBackgroundNormal=1,2,3\n")

            # Leftovers of our own (earlier versions, the experiment script) aren't
            # "your setup": no notice, and switching off tidies them away
            with mock.patch.dict(os.environ, env), \
                 mock.patch.object(qt.paths, "HOME", home), \
                 mock.patch.object(qt, "qt5ct_installed", return_value=True), \
                 mock.patch.object(qt, "flatpak_qt_apps", return_value=["org.videolan.VLC"]):
                (home / ".profile").write_text("# mine\n")
                conf.write_text(f"[Appearance]\ncustom_palette=true\ncolor_scheme_path={qt.scheme_file()}\n")
                override.write_text("[Environment]\nQT_QPA_PLATFORMTHEME=kde\n")
                qt.kdeglobals_file("org.videolan.VLC").write_text("[General]\nColorScheme=xl-Cheeselooks\n")
                qt.enable(t)
                self.assertIsNone(qt.pending_notice())
                self.assertFalse(conf.with_name("qt5ct.conf" + qt.BACKUP).exists())
                # the watcher's round trip: off and back on, silently
                qt.disable(set_aside=True)
                self.assertFalse(qt.active())
                qt.enable(t)
                self.assertIsNone(qt.pending_notice())
                self.assertTrue(qt.active())
                qt.disable()
                self.assertFalse(conf.exists())                                       # nothing of ours left
                self.assertFalse(override.exists())
                self.assertFalse(qt.kdeglobals_file("org.videolan.VLC").exists())
        self.assertTrue(settings.DEFAULTS["integration"]["qt_colors"])                  # on by default

    def test_editor_colors(self):
        import xml.etree.ElementTree as ET
        from unittest import mock
        import os
        # every shipped theme: valid XML, and every syntax colour reads on the editor
        for f in sorted((REPO / "data" / "themes").glob("*.json")):
            data = settings.from_dict(json.loads(f.read_text())["settings"])
            t = tokens.build(data, styles.find(data["style"]["name"], [REPO / "styles"]))
            root = ET.fromstring(editor.scheme_xml(t))
            self.assertEqual(root.get("id"), editor.SCHEME_ID)
            c = editor.colours(t)
            for k in ("statement", "type", "constant", "string", "identifier", "preprocessor", "special",
                      "added", "removed", "text"):
                self.assertGreaterEqual(palette.contrast(c[k], c["bg"]), 4.5, f"{f.name}: {k}")
            self.assertGreaterEqual(palette.contrast(c["comment"], c["bg"]), 3.0, f.name)
            self.assertGreaterEqual(palette.contrast(c["line_numbers"], c["gutter"]), 3.0, f.name)
        # on: written to every GtkSourceView folder, Xed switched; off: Xed's own back, files gone
        gs = {("org.x.editor.preferences.editor", "scheme"): "classic"}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(Path(tmp) / "share"),
                                          "XDG_CONFIG_HOME": str(Path(tmp) / "config")}), \
             mock.patch.object(editor.reload, "available", return_value=True), \
             mock.patch.object(editor.reload, "get", side_effect=lambda sc, k: gs.get((sc, k))), \
             mock.patch.object(editor.reload, "set_value", side_effect=lambda sc, k, v: gs.__setitem__((sc, k), v) or True):
            t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
            editor.enable(t)
            self.assertTrue(all(f.exists() for f in editor.scheme_files()))
            self.assertEqual(gs[("org.x.editor.preferences.editor", "scheme")], editor.SCHEME_ID)
            editor.enable(t)                                                   # a second Apply
            editor.disable()
            self.assertEqual(gs[("org.x.editor.preferences.editor", "scheme")], "classic")
            self.assertFalse(any(f.exists() for f in editor.scheme_files()))
            self.assertFalse(editor.active())
        self.assertTrue(settings.DEFAULTS["integration"]["editor_colors"])

    def test_flatpak_access_switch(self):
        from unittest import mock
        calls = []
        with mock.patch.object(cli.flatpak, "available", return_value=True), \
             mock.patch.object(cli.flatpak, "enable", side_effect=lambda: calls.append("on") or []), \
             mock.patch.object(cli.flatpak, "disable", side_effect=lambda: calls.append("off") or True):
            with mock.patch.object(cli.flatpak, "granted", return_value=[]):
                self.assertTrue(cli._flatpak_access(True))            # on, not granted yet: granted
            with mock.patch.object(cli.flatpak, "granted", return_value=list(cli.flatpak.FILESYSTEMS)):
                self.assertEqual(cli._flatpak_access(True), [])       # already granted: nothing to do
            with tempfile.TemporaryDirectory() as tmp:
                rec = Path(tmp) / "flatpak-added"
                with mock.patch.object(cli.flatpak, "added_file", return_value=rec):
                    self.assertEqual(cli._flatpak_access(False), [])  # off, nothing of ours: left alone
                    rec.write_text("~/.themes:ro\n")
                    self.assertTrue(cli._flatpak_access(False))       # off: ours removed
        self.assertEqual(calls, ["on", "off"])
        self.assertTrue(settings.DEFAULTS["integration"]["flatpak_access"])

    def test_libadwaita_full_styling(self):
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        plain = gtk4.block(REPO / "templates", t, css_variables=True)
        full = gtk4.block(REPO / "templates", t, css_variables=True, full=True)
        self.assertNotIn("windowcontrols", plain)                              # off: colours only
        self.assertTrue(full.startswith(plain[:200]))                          # on: the colours, then...
        self.assertIn("windowcontrols", full)                                  # ...our title buttons,
        self.assertIn("toolbarview > .top-bar", full)                          # libadwaita additions
        self.assertIn(f"button:not(.opaque) {{ color: {t['text']}; }}", full)  # readable app-coloured buttons
        self.assertNotIn('url("assets/', full)                                 # pictures beside gtk.css
        names = gtk4.asset_names(full)
        self.assertIn("check-symbolic.svg", names)
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "theme"
            install.build(REPO / "templates", t, theme)
            css = Path(tmp) / "config" / "gtk-4.0" / "gtk.css"
            gtk4.write(css, full)
            gtk4.copy_assets(full, theme, css)
            for n in names:
                self.assertTrue((css.parent / gtk4.ASSETS / n).exists(), n)
            gtk4.remove_assets(css)
            self.assertFalse((css.parent / gtk4.ASSETS).exists())
        self.assertFalse(settings.DEFAULTS["integration"]["libadwaita_full"])  # opt-in

    def test_theme_change_keeps_integration(self):
        mine = defaults()
        mine["integration"].update(libadwaita_full=True, qt_colors=False)
        theme = themes.load("xl-Classic")
        kept = settings.keep_per_user(theme, mine)
        self.assertTrue(kept["integration"]["libadwaita_full"])
        self.assertFalse(kept["integration"]["qt_colors"])
        self.assertEqual(kept["global"], theme["global"])                    # the look is the theme's

    def test_theme_watcher(self):
        from unittest import mock
        import os
        self.assertTrue(watch.is_ours("xl-Cheeselooks"))
        self.assertTrue(watch.is_ours(".xl-Cheeselooks-reloading"))          # Apply's reload name
        self.assertFalse(watch.is_ours("Mint-Y"))
        calls = []
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), \
             mock.patch.object(watch, "set_aside", side_effect=lambda: calls.append("aside") or
                               (watch.set_aside_file().parent.mkdir(parents=True, exist_ok=True),
                                watch.set_aside_file().write_text(""))), \
             mock.patch.object(watch, "restore", side_effect=lambda: calls.append("back") or
                               watch.set_aside_file().unlink()):
            watch._act(None)                         # setting unreadable: nothing to do
            watch._act("xl-Cheeselooks")             # ours, nothing set aside: nothing to do
            watch._act("Mint-Y")                     # away: set aside
            watch._act("Mint-L")                     # still away: once is enough
            watch._act("xl-Cheeselooks")             # back: restored
            with watch.applying():
                watch._act("Mint-Y")                 # Apply running: hands off
            self.assertFalse(watch.lock_file().exists())
            self.assertEqual(calls, ["aside", "back"])
            # the login entry starts the checkout's command
            text = watch.autostart_text()
            self.assertIn("watch", text)
            self.assertIn("X-GNOME-Autostart-enabled=true", text)
            self.assertTrue(str(watch.autostart_file()).startswith(tmp))
        self.assertTrue(settings.DEFAULTS["integration"]["watch_theme"])

    def test_set_aside_takes_our_colors_out(self):
        from unittest import mock
        import os
        with tempfile.TemporaryDirectory() as tmp:
            css = Path(tmp) / "gtk-4.0" / "gtk.css"
            css.parent.mkdir(parents=True)
            css.write_text("/* mine */\n")
            t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
            gtk4.write(css, gtk4.block(REPO / "templates", t, css_variables=True))
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp}), \
                 mock.patch.object(watch.qt, "active", return_value=False), \
                 mock.patch.object(watch.editor, "active", return_value=False):
                watch.set_aside()
                self.assertEqual(css.read_text().strip(), "/* mine */")       # only ours taken out
                self.assertTrue(watch.set_aside_file().exists())

    def test_qt5ct_empty_stylesheet_list(self):
        out = qt.qt5ct_conf("[Interface]\nstylesheets=@Invalid()\n")
        self.assertIn(f"stylesheets={qt.qss_file()}\n", out)                   # qt5ct's "empty" dropped

    def test_folder_icons(self):
        from unittest import mock
        import os
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        c = icons.colours(t, {})
        self.assertEqual(c["folder"], t["accent"])                              # follows the accent
        self.assertGreaterEqual(palette.contrast(c["emblem"], c["folder"]), 3.0)  # the emblem reads
        grey = icons.colours(t, {"folder_color": "#7A7A7A"})
        self.assertEqual(grey["backfolder"], icons.back_shade(t["accent"]))      # a grey front keeps an accent back
        mine = icons.colours(t, {"folder_color": "#336699", "second_color": "#112233"})
        self.assertEqual((mine["folder"], mine["backfolder"]), ("#336699", "#112233"))
        for light in ("#F9C470", "#B8D8EB", "#FFFFFF"):                        # light folders: dark emblem
            self.assertGreaterEqual(palette.contrast(icons.colours(t, {"folder_color": light})["emblem"], light), 3.0)
        svg = (icons.source_dir() / "48" / "folder-music.svg").read_text()
        out = icons.recolour(svg, c)
        for src in icons.SOURCE.values():
            self.assertNotIn(src, out.lower())                                  # every source colour swapped
        gs = {icons.KEY: "Mint-Y-Sand"}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(Path(tmp) / "share"),
                                          "XDG_CONFIG_HOME": str(Path(tmp) / "config")}), \
             mock.patch.object(icons.paths, "HOME", Path(tmp)), \
             mock.patch.object(icons.reload, "available", return_value=True), \
             mock.patch.object(icons.reload, "get", side_effect=lambda *k: gs.get(k)), \
             mock.patch.object(icons.reload, "set_value", side_effect=lambda *a: gs.__setitem__(a[:2], a[2]) or True):
            old = icons.old_theme_dir()
            old.mkdir(parents=True)                                             # the first version's place
            icons.enable(t, {})
            d = icons.theme_dir()
            self.assertEqual(d, Path(tmp) / ".icons" / icons.THEME)              # beside ~/.themes
            self.assertFalse(old.exists())                                      # the old copy cleared away
            files = [f for f in d.glob("places/*/*.svg") if not f.is_symlink()]
            self.assertEqual(len(files), 128 * 2)                                # every size, and @2x
            nemo = d / "places" / "48" / "nemo.svg"                              # the Files app's icon...
            self.assertTrue(nemo.is_symlink())
            self.assertEqual(nemo.resolve(), (d / "places" / "48" / "folder.svg").resolve())  # ...is the folder
            index = (d / "index.theme").read_text()
            self.assertIn("Inherits=Mint-Y-Sand,Mint-Y,Adwaita,gnome,hicolor", index)  # yours fills in the rest
            self.assertIn("[places/48@2x]\nSize=48\nScale=2", index)
            self.assertTrue((d / "COPYING").exists())                           # CC BY-SA credit travels along
            self.assertEqual(gs[icons.KEY], icons.THEME)
            icons.enable(t, {})                                                 # a second Apply: still yours behind
            self.assertIn("Inherits=Mint-Y-Sand,", (d / "index.theme").read_text())
            icons.disable()
            self.assertEqual(gs[icons.KEY], "Mint-Y-Sand")
            self.assertFalse(d.exists())
        self.assertFalse(settings.DEFAULTS["icons"]["enabled"])                 # off by default
        kept = settings.keep_per_user(themes.load("xl-Classic"), {**defaults(), "icons": {"enabled": True,
                                      "folder_color": "#000000", "second_color": None}})
        self.assertTrue(kept["icons"]["enabled"])                               # the switch stays...
        self.assertIsNone(kept["icons"]["folder_color"])                        # ...the colours are the theme's

    def test_file_dialog_sidebar_follows_list_roundness(self):
        g3, g4 = tokens._lists_css(15, 2, "#ccc")
        self.assertIn("filechooser placessidebar.sidebar list row.sidebar-row", g3)
        self.assertIn("{ margin: 0; border-radius: 0; }", g3.split("filechooser placessidebar")[1])
        self.assertIn(".navigation-sidebar > row { margin: 0; border-radius: 0; }", g4)
        g3, g4 = tokens._lists_css(40, 9, "#ccc")
        self.assertIn("placessidebar row { margin: 1px 6px; border-radius: 9px; }", g3)
        self.assertIn(".navigation-sidebar > row { margin: 1px 6px; border-radius: 9px; }", g4)
        self.assertGreaterEqual(palette.contrast("#B85A38", icons.back_shade("#B85A38")), 1.6)  # Mint-like folder back

    def test_folder_colors_pin_together(self):
        import types
        from cheeselooks import app
        def window():
            d = defaults()
            d["global"]["accent"] = "#E01B24"
            return types.SimpleNamespace(data=d, syncing=False, after_change=lambda: None)
        w = window()
        app.SettingsWindow.changed(w, ("icons", "folder_color"), "#3584E4")      # a blue front...
        self.assertEqual(w.data["icons"]["second_color"], icons.back_shade("#E01B24"))  # ...the back stays dark red
        w = window()
        app.SettingsWindow.changed(w, ("icons", "second_color"), "#2EC27E")      # a green back...
        self.assertEqual(w.data["icons"]["folder_color"], "#E01B24")            # ...the front stays red

    def test_icons_survive_a_theme_pick_and_apply(self):
        """xl_cheese, 20 Nov: Icons on, pick Claude Dark, Apply: the switch and
        folder style stay; flipping either afterwards needs an Apply."""
        from cheeselooks import app
        mine = defaults()
        mine["icons"].update(enabled=True, style="breeze")
        picked = settings.keep_per_user(themes.load("Claude Dark"), mine)      # as the theme list does
        self.assertEqual((picked["icons"]["enabled"], picked["icons"]["style"]), (True, "breeze"))
        self.assertTrue(app._needs_apply(picked, mine))
        with tempfile.TemporaryDirectory() as tmp:                             # Apply saves; the app reopens
            f = Path(tmp) / "settings.json"
            settings.save(picked, f)
            applied = settings.load(f)
        self.assertEqual((applied["icons"]["enabled"], applied["icons"]["style"]), (True, "breeze"))
        self.assertFalse(app._needs_apply(copy.deepcopy(applied), applied))
        for path, value in ((("icons", "enabled"), False), (("icons", "style"), "yaru"),
                            (("integration", "qt_colors"), False)):
            changed = copy.deepcopy(applied)
            changed[path[0]][path[1]] = value
            self.assertTrue(app._needs_apply(changed, applied), path)
            self.assertTrue(app._same(changed, applied), path)                 # but still the same theme

    def test_yaru_folders(self):
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        yaru = {"style": "yaru", "folder_color": "#7A7A7A", "second_color": "#E8795E"}
        c = icons.colours(t, yaru)
        svg = (icons.source_dir("yaru") / "48" / "folder-music.svg").read_text()
        out = icons.recolour(svg, c, "yaru")
        for src in icons.STYLES["yaru"]["source"].values():
            self.assertNotIn(src, out.lower())                                  # every placeholder swapped
        # what you choose is what you see: Yaru's own veils worked backwards
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        big = icons.recolour((icons.source_dir("yaru") / "256" / "folder.svg").read_text(), c, "yaru")
        loader = GdkPixbuf.PixbufLoader()
        loader.write(big.encode())
        loader.close()
        pb = loader.get_pixbuf()

        def seen(x, y):
            i = y * pb.get_rowstride() + x * pb.get_n_channels()
            return pb.get_pixels()[i:i + 3]
        for (x, y), want in (((176, 144), "#7A7A7A"), ((72, 56), "#E8795E")):   # the front, the back
            for got, w in zip(seen(x, y), palette.to_rgb(want)):
                self.assertLessEqual(abs(got - w), 2, (x, y, want))
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "t"
            n = icons.build(t, yaru, ["Mint-Y"], d)
            self.assertEqual(n, 19 * 5)                                         # 19 icons, 16-256px
            self.assertIn("[places/256]", (d / "index.theme").read_text())
            self.assertIn("Yaru's", (d / "index.theme").read_text())
            self.assertIn("Canonical", (d / "COPYING").read_text())
            nemo = d / "places" / "48" / "nemo.svg"                              # the Files app: the folder
            self.assertEqual(nemo.resolve(), (d / "places" / "48" / "folder.svg").resolve())
            drag = d / "places" / "48" / "folder-drag-accept.svg"                # Yaru's open folder
            self.assertEqual(drag.resolve(), (d / "places" / "48" / "folder-open.svg").resolve())
            self.assertFalse((d / "places" / "48" / "folder-open.svg").is_symlink())  # a real icon, not replaced

    def test_big_baddy_stripes(self):
        """xl-Big Baddy: no racing stripes until you pick a color (unset, they're
        the binder's color, under its white rings, so nothing shows); then that
        color; every placeholder swapped at every size."""
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        off = icons.colours(t, {"style": "xl-big-baddy"})
        self.assertEqual(off["backfolder"], off["folder"])
        on = icons.colours(t, {"style": "xl-big-baddy", "second_color": "#1A1A1A"})
        self.assertEqual(on["backfolder"], "#1A1A1A")
        self.assertEqual(icons.STYLES["xl-big-baddy"]["second_label"], "Racing stripes")
        for size in icons.STYLES["xl-big-baddy"]["sizes"]:
            for f in (icons.source_dir("xl-big-baddy") / str(size)).glob("*.svg"):
                out = icons.recolour(f.read_text(), on, "xl-big-baddy")
                for src in icons.STYLES["xl-big-baddy"]["source"].values():
                    self.assertNotIn(src, out.lower(), f)

    def test_every_style_covers_mint_y(self):
        """Every style draws Mint-Y's places icons (its own, or its folder with
        Mint-Y's picture), at every size: none left to another icon theme."""
        mint = {f.stem for f in (icons.source_dir("mint-y") / "48").glob("*.svg")}
        for style, spec in icons.STYLES.items():
            for size in spec["sizes"]:
                have = {f.stem for f in (icons.source_dir(style) / str(size)).glob("*.svg")}
                have |= {a for a, t in icons.aliases(style).items() if t in have}
                self.assertEqual(mint - have, set(), (style, size))

    def test_breeze_folders(self):
        t = tokens.build(defaults(), styles.load(DEFAULT_STYLE))
        breeze = {"style": "breeze", "folder_color": "#7A7A7A", "second_color": "#E8795E"}
        c = icons.colours(t, breeze)
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        for size in icons.STYLES["breeze"]["sizes"]:
            for f in (icons.source_dir("breeze") / str(size)).glob("*.svg"):
                out = icons.recolour(f.read_text(), c, "breeze")
                for src in icons.STYLES["breeze"]["source"].values():
                    self.assertNotIn(src, out.lower(), f)                       # every placeholder swapped
        loader = GdkPixbuf.PixbufLoader()
        loader.write(icons.recolour((icons.source_dir("breeze") / "96" / "folder.svg").read_text(), c,
                                    "breeze").encode())
        loader.close()
        pb = loader.get_pixbuf()
        self.assertEqual(pb.get_width(), 96)

        def seen(x, y):
            i = y * pb.get_rowstride() + x * pb.get_n_channels()
            return pb.get_pixels()[i:i + 3]
        for (x, y), want in (((48, 60), "#7A7A7A"), ((15, 20), "#E8795E")):     # the front, the back: exact
            self.assertEqual(tuple(seen(x, y)), palette.to_rgb(want), (x, y))
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "t"
            self.assertEqual(icons.build(t, breeze, ["Mint-Y"], d), 16 * 7)    # 16 icons, 16-96px (16-24 from the 32)
            self.assertIn("Lesser General Public", (d / "COPYING").read_text())
            drag = d / "places" / "48" / "folder-drag-accept.svg"
            self.assertEqual(drag.resolve(), (d / "places" / "48" / "folder-open.svg").resolve())

    def test_theme_stays_itself_with_per_user_settings(self):
        from cheeselooks import app
        theme = themes.load("xl-Cheeselooks")
        mine = settings.keep_per_user(theme, {**theme, "integration": {**theme["integration"], "libadwaita_full": True},
                                              "icons": {**theme["icons"], "enabled": True, "style": "yaru"}})
        self.assertTrue(app._same(mine, theme))                       # still xl-Cheeselooks, not Custom
        mine["global"] = {**mine["global"], "accent": "#123456"}
        self.assertFalse(app._same(mine, theme))                      # a real change: Custom

    def test_unreadable_style_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "b-mine"
            d.mkdir()
            (d / "style.toml").write_text('name = "Mine"\n[edges.sunken]\nrecess = { color = "black", alpha = }\n')
            with self.assertRaises(styles.StyleError) as ctx:
                styles.find("Mine", [Path(tmp)])
            text = " ".join(ctx.exception.problems)
            self.assertIn("can't be read", text)
            self.assertIn("line 3", text)

    def test_thumbnail_follows_the_accent(self):
        from cheeselooks import thumbnail
        blue, orange = thumbnail.render("#3A6FD8"), thumbnail.render("#FA8562")
        if blue is None:
            self.skipTest("no GdkPixbuf")
        self.assertNotEqual(blue, orange)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "theme"
            s = defaults()
            s["global"]["accent"] = "#3A6FD8"
            install.build(REPO / "templates", tokens.build(s, styles.load(DEFAULT_STYLE)), out)
            for part in thumbnail.PARTS:
                self.assertEqual((out / part / "thumbnail.png").read_bytes(), blue)

    def test_starter_style_sheet(self):
        """The starter style sheet is valid as shipped, and with every option
        switched on (except the "instead of" alternatives)."""
        import re
        text = (REPO / "data" / "style-template.toml").read_text().replace("{{name}}", "Starter")
        on = "\n".join(l[1:] if re.match(r"^#(\[|[a-z_]+\s*=)", l) and "instead of" not in l else l
                       for l in text.split("\n"))
        for body in (text, on):
            with tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp) / "Starter"
                d.mkdir()
                (d / "style.toml").write_text(body)
                st = styles.load(d)
                self.assertEqual(st.name, "Starter")
                tokens.build(defaults(), st)

    def test_unfocused_depth(self):
        st = styles.load(DEFAULT_STYLE)
        s = defaults()
        self.assertEqual(s["style"]["unfocused_depth"], 70)
        t = tokens.build(s, st)
        self.assertEqual(palette.scale_shadow("0 1px 2px rgba(0, 0, 0, 0.5)", 0.7), "0 1px 2px rgba(0, 0, 0, 0.35)")
        self.assertEqual(t["bd.w.button.shadow"], palette.scale_shadow(t["w.button.shadow"], 0.7))
        s["style"]["unfocused_depth"] = 0
        self.assertEqual(tokens.build(s, st)["bd.w.button.shadow"], "none")
        out = settings.apply_style_defaults(defaults(), {"unfocused_depth": 40})
        self.assertEqual(out["style"]["unfocused_depth"], 40)

    def test_menu_style(self):
        s = defaults()
        s["global"].update(roundness=40, gradient=60)
        s["panel"]["menu_shape"] = {"follow_global": False, "roundness": 0, "item_roundness": 100}
        st = styles.load(DEFAULT_STYLE)
        t = tokens.build(s, st)
        self.assertEqual(t["menu.r"], "0")                                   # the menu itself
        self.assertEqual(t["menu.item_r"], str(shape.radius(100, 30)))       # the main menu's items
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "theme"
            install.build(REPO / "templates", t, out)
            css = (out / "cinnamon" / "cinnamon.css").read_text()
        # other menus: Global roundness, inset from the sides above 30...
        self.assertIn(f".popup-menu-item {{ border-radius: {t['r']}px; }}", css)
        self.assertIn(".popup-menu-content { padding-left: 6px; padding-right: 6px; }", css)
        s["global"]["roundness"] = 30                                        # ...square, edge to edge, up to it
        self.assertEqual(tokens.build(s, st)["popup_items.css"], ".popup-menu-item { border-radius: 0; }")
        self.assertIn(f".menu-application-button, .menu-category-button, .menu-category-button-greyed {{\n  border-radius: {t['menu.item_r']}px;", css)
        self.assertEqual(t["menu.w.menu_item.hover_top"], tokens.build(s, st)["menu.w.menu_item.hover_top"])
        self.assertEqual(settings.apply_style_defaults(defaults(), {"menu_roundness": 50})["panel"]["menu_shape"]["item_roundness"], 50)

    def test_scrollbar_width(self):
        st = styles.load(DEFAULT_STYLE)
        s = defaults()
        s["details"]["scrollbars"].update(custom=True, mode="classic")
        self.assertEqual(tokens.build(s, st)["scrollbar.width"], "10")        # unset: the mode's own
        s["details"]["scrollbars"]["width"] = 14
        self.assertEqual(tokens.build(s, st)["scrollbar.width"], "14")
        s["details"]["scrollbars"]["mode"] = "overlay"                         # either mode
        self.assertEqual(tokens.build(s, st)["scrollbar.width"], "14")

    def test_button_spacing(self):
        self.assertEqual(titlebuttons.spacing("drawn"), 6)
        self.assertEqual(titlebuttons.spacing("gargantuan-circles"), 0)
        self.assertEqual(titlebuttons.spacing("drawn", {"wb.button_spacing": "2"}), 2)
        for locked in titlebuttons.SPACING_LOCKED:             # made to touch
            self.assertEqual(titlebuttons.spacing(locked, {"wb.button_spacing": "8"}), 0)
        s = defaults()
        s["window_borders"].update(button_style="drawn", button_spacing=2)
        t = tokens.build(s, styles.load(DEFAULT_STYLE))
        self.assertIn("windowcontrols { border-spacing: 2px; }", t["titlebuttons4.css"])

    def test_window_roundness(self):
        st = styles.load(DEFAULT_STYLE)
        s = defaults()
        t = tokens.build(s, st)
        self.assertEqual(t["wb.r"], t["r2"])                       # unset: follows Global
        s["window_borders"]["window_roundness"] = 0
        t = tokens.build(s, st)
        self.assertEqual(t["wb.r"], "0")
        s["window_borders"]["window_roundness"] = 100
        self.assertEqual(tokens.build(s, st)["wb.r"], str(shape.WINDOW_RADIUS_MAX))

    def test_round_bottom_corners(self):
        s = defaults()
        s["window_borders"].update(window_roundness=50, round_bottom=True)
        if not tokens.ROUND_BOTTOM_READY:                         # on the back burner: ignored
            self.assertEqual(tokens.build(s, styles.load(DEFAULT_STYLE))["wb.r_bottom"], "0")
        ready, tokens.ROUND_BOTTOM_READY = tokens.ROUND_BOTTOM_READY, True
        self.addCleanup(setattr, tokens, "ROUND_BOTTOM_READY", ready)
        st = styles.load(DEFAULT_STYLE)
        s = defaults()
        s["window_borders"]["window_roundness"] = 50
        t = tokens.build(s, st)
        self.assertEqual(t["wb.r_bottom"], "0")                    # off by default: square
        s["window_borders"]["round_bottom"] = True
        t = tokens.build(s, st)
        self.assertEqual(t["wb.r_bottom"], t["wb.r"])
        with tempfile.TemporaryDirectory() as tmp:
            install.build(REPO / "templates", t, Path(tmp) / "theme")
            css4 = (Path(tmp) / "theme" / "gtk-4.0" / "xl.css").read_text()
            css3 = (Path(tmp) / "theme" / "gtk-3.0" / "xl.css").read_text()
        r = t["wb.r"]
        self.assertIn(f"border-radius: {r}px {r}px {r}px {r}px;", css4)
        self.assertIn(f"border-bottom-left-radius: {r}px;", css3)
        self.assertIn("window.csd evview", css3)
        self.assertIn("window.csd actionbar > revealer > box", css4)
        self.assertNotIn("treeview", t["wb.bottom3.css"])           # Nemo's sidebar rows
        s["window_borders"]["round_bottom"] = False
        self.assertEqual(tokens.build(s, st)["wb.bottom3.css"], "")

    def test_title_button_colors(self):
        base = styles.load(DEFAULT_STYLE)
        s = defaults()
        s["window_borders"].update(separate_colors=True, title_bar="#5B7FB5", title_text="#FFFFFF",
                                   button_style="drawn")
        plain = tokens.build(s, base)
        self.assertEqual(plain["tbtn.color"], "")
        grey = styles.Style(**{**base.__dict__, "title_buttons": {"color": "#C0C0C0", "close_hover": "hover"}})
        t = tokens.build(s, grey)
        self.assertEqual(t["tbtn.color"], "#C0C0C0")
        self.assertTrue(t["tbtn.hover_color"] and t["tbtn.pressed_color"])     # follow the face
        f = titlebuttons.faces("drawn", t)
        self.assertEqual(f[("minimize", "rest")].glyph, t["tbtn.color_fg"])
        self.assertLess(palette.luminance(f[("minimize", "rest")].glyph), 0.2)  # dark glyph on grey, not white
        self.assertEqual(f[("close", "hover")], f[("minimize", "hover")])      # close hovers like the others
        red = styles.Style(**{**base.__dict__, "title_buttons": {"close_hover": "#CC3333"}})
        t = tokens.build(s, red)
        for style in ("drawn", "flat", "unpretentious", "claude"):
            self.assertEqual(titlebuttons.faces(style, t)[("close", "hover")].top,
                             t["tbtn.close_hover_top"], style)
        errors, warns = styles.check({"name": "N", "title_buttons": {"color": "nope", "shine": 1}})
        self.assertTrue(any("title_buttons.color" in e for e in errors))
        self.assertTrue(any("title_buttons.shine" in w for w in warns))

    def test_include(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "a.part").write_text("A {{accent}}")
            (tmp / "x.css.tmpl").write_text('top\n{{include "a.part"}}\n')
            out = tmp / "out"
            render.render_tree(tmp, out, {"accent": "#FA8562"})
            self.assertEqual((out / "x.css").read_text(), "top\nA #FA8562\n")
            self.assertFalse((out / "a.part").exists())

    def test_failed_render_leaves_theme_untouched(self):
        st = styles.load(DEFAULT_STYLE)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            theme, good = tmp / "xl-Cheeselooks", tmp / "good"
            install.install(REPO / "templates", tokens.build(defaults(), st), theme, good)
            before = (theme / "index.theme").read_text()
            bad_templates = tmp / "bad"
            bad_templates.mkdir()
            (bad_templates / "index.theme.tmpl").write_text("{{does_not_exist}}")
            with self.assertRaises(render.TemplateError):
                install.install(bad_templates, {}, theme, good)
            self.assertEqual((theme / "index.theme").read_text(), before)
            self.assertFalse((tmp / ".xl-Cheeselooks.new").exists())


if __name__ == "__main__":
    unittest.main()
