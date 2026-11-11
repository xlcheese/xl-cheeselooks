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
        st = styles.load(DEFAULT_STYLE)
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

    def test_panel_marker(self):
        p = palette.derive("#FA8562", "#F5F5F5", "#303030")
        none = tokens.build(defaults(), styles.Style(name="Fixture", path=None))
        self.assertNotIn("box-shadow", none["panel_marker.css"])
        for kind, want in (("line", "inset 0 -2px 0 0 "), ("accent_bottom", "inset 0 -2px 0 0 "),
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
        self.assertEqual(t["accent"], "#FA8562")
        self.assertEqual(t["accent_rgb"], "250, 133, 98")
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

    def test_tab_kinds_and_markers(self):
        s = defaults()
        css = tokens.build(s, self.style)["tabs.css"]
        self.assertIn("tabs: boxed, selected marker: none", css)
        for kind, marker, expect, bottom in (("open", "line", "inset 0 2px 0", "inset 0 -2px 0"),
                                             ("pills", "glow", "8px -8px", "inset 0 -1px 0 #"),
                                             ("boxed", "accent_top", "inset 0 2px 0", "inset 0 -2px 0")):
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
