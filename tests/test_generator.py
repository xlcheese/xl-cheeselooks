"""Tests for the generator core. Run with: python3 -m unittest discover tests"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from cheeselooks import cli, install, palette, render, settings, shape, styles, tokens

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
        self.assertEqual(s["global"]["accent"], "#FA8562")

    def test_all_builtin_presets_load(self):
        for f in (REPO / "presets").rglob("*.json"):
            with self.subTest(preset=f.name):
                settings.apply_preset(defaults(), json.loads(f.read_text()))


class StyleTests(unittest.TestCase):
    def test_builtin_styles_are_clean(self):
        for path in (DEFAULT_STYLE, FLOAT_STYLE):
            with self.subTest(style=path.name):
                st = styles.load(path)
                self.assertEqual(st.warnings, [])

    def test_raised_edge_has_all_layers_for_gtk_one_for_cinnamon(self):
        st = styles.load(DEFAULT_STYLE)
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        t = styles.widget_tokens(st, p, 50)
        self.assertEqual(t["w.button.shadow"].count("rgba("), 3)
        self.assertEqual(t["w.button.st_shadow"].count("rgba("), 1)
        self.assertTrue(t["w.button.st_shadow"].startswith("inset 0 1px"))  # highlight kept first

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
        st = styles.load(DEFAULT_STYLE)
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
        self.assertEqual(t["accent"], "#FA8562")
        self.assertEqual(t["accent_rgb"], "250, 133, 98")
        self.assertEqual(t["is_dark"], "false")
        self.assertEqual(t["panel.accent"], t["accent"])  # panel follows Global
        self.assertEqual(t["wb.title_bottom"], t["header"])  # title bar ends on toolbar color
        self.assertEqual(t["term.bg"], t["base"])
        self.assertEqual(t["tooltip.bg"], t["menu_bg"])
        self.assertEqual(t["switch.r"], "11")  # fully round by default (22px tall)
        self.assertEqual(t["w.tab.active_shadow"], "none")
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
            self.assertEqual(restored["global"]["accent"], "#FA8562")

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
