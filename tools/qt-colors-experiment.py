#!/usr/bin/env python3
"""Experiment: Qt apps (VLC) in the applied theme's colours, before building
the Integration switch. Writes two colour schemes from your current settings:

  regular Qt apps   ~/.config/qt5ct/colors/xl-Cheeselooks.conf and qt5ct.conf
                    (used only when an app runs with QT_QPA_PLATFORMTHEME=qt5ct)
  Flatpak VLC       ~/.var/app/org.videolan.VLC/config/kdeglobals
                    (used only when it runs with QT_QPA_PLATFORMTHEME=kde)

Nothing changes for any app run normally. Files it would overwrite are kept
as *.xl-backup; --remove deletes what it wrote and puts those back.

    python3 tools/qt-colors-experiment.py            # write, print the test commands
    python3 tools/qt-colors-experiment.py --remove   # undo
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cheeselooks import palette as pal, paths, settings, styles, tokens  # noqa: E402

HOME = Path.home()
QT5CT = HOME / ".config" / "qt5ct"
SCHEME = QT5CT / "colors" / "xl-Cheeselooks.conf"
QT5CT_CONF = QT5CT / "qt5ct.conf"
VLC_FLATPAK = "org.videolan.VLC"
KDEGLOBALS = HOME / ".var" / "app" / VLC_FLATPAK / "config" / "kdeglobals"
WRITTEN = (SCHEME, QT5CT_CONF, KDEGLOBALS)
BACKUP = ".xl-backup"


def theme_colours() -> dict[str, str]:
    data = settings.load(paths.settings_file())
    style = styles.find(data["style"]["name"], paths.style_dirs())
    t = tokens.build(data, style)
    dark = pal.luminance(t["bg"]) < 0.25
    c = {k: t[k] for k in ("bg", "base", "text", "text_dim", "button", "accent", "accent_fg")}
    c["alt_base"] = pal.mix(t["base"], t["text"], 0.04)
    c["tip_bg"], c["tip_text"] = t["tooltip.bg"], t["tooltip.text"]
    # Qt draws bevels and frames from these, round the button colour
    c["light"] = pal.lighter(t["button"], 0.25 if dark else 0.6)
    c["midlight"] = pal.mix(c["light"], t["button"], 0.5)
    c["dark"] = pal.darker(t["button"], 0.45 if dark else 0.3)
    c["mid"] = pal.mix(c["dark"], t["button"], 0.5)
    c["shadow"] = pal.darker(t["button"], 0.7)
    c["link"] = t["accent"]
    c["disabled_text"] = pal.mix(t["text"], t["bg"], 0.55)
    return c


def qt5ct_scheme(c: dict[str, str]) -> str:
    # Qt 5's palette roles, in qt5ct's order
    roles = ["text", "button", "light", "midlight", "dark", "mid", "text", "white", "text", "base", "bg",
             "shadow", "accent", "accent_fg", "link", "link", "alt_base", "bg", "tip_bg", "tip_text", "text_dim"]
    c = {**c, "white": "#FFFFFF"}

    def row(over: dict[int, str]) -> str:
        return ", ".join("#ff" + c[over.get(i, r)].lstrip("#").lower() for i, r in enumerate(roles))
    disabled = {0: "disabled_text", 6: "disabled_text", 8: "disabled_text", 12: "mid"}
    return ("[ColorScheme]\n"
            f"active_colors={row({})}\n"
            f"disabled_colors={row(disabled)}\n"
            f"inactive_colors={row({})}\n")


def qt5ct_conf() -> str:
    return ("[Appearance]\n"
            f"color_scheme_path={SCHEME}\n"
            "custom_palette=true\n"
            "standard_dialogs=gtk3\n"     # keep GTK's file dialogs (in our theme), as without qt5ct
            "style=Fusion\n")


def kdeglobals(c: dict[str, str]) -> str:
    def rgb(name: str) -> str:
        return ",".join(str(v) for v in pal.to_rgb(c[name]))

    def group(name: str, bg: str, fg: str, alt: str) -> str:
        return (f"[Colors:{name}]\n"
                f"BackgroundNormal={rgb(bg)}\nBackgroundAlternate={rgb(alt)}\n"
                f"ForegroundNormal={rgb(fg)}\nForegroundInactive={rgb('text_dim')}\n"
                f"ForegroundLink={rgb('link')}\nForegroundVisited={rgb('link')}\n"
                f"DecorationFocus={rgb('accent')}\nDecorationHover={rgb('accent')}\n\n")
    return ("[General]\nColorScheme=xl-Cheeselooks\n\n[KDE]\nwidgetStyle=Fusion\n\n"
            + group("Window", "bg", "text", "bg")
            + group("View", "base", "text", "alt_base")
            + group("Button", "button", "text", "button")
            + group("Selection", "accent", "accent_fg", "accent")
            + group("Tooltip", "tip_bg", "tip_text", "tip_bg")
            + group("Complementary", "bg", "text", "bg"))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + BACKUP)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text)
    print(f"  wrote {path}")


def remove() -> None:
    for path in WRITTEN:
        backup = path.with_name(path.name + BACKUP)
        if backup.exists():
            shutil.move(backup, path)
            print(f"  restored {path}")
        elif path.exists():
            path.unlink()
            print(f"  removed {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove", action="store_true", help="undo: delete what this wrote, restore backups")
    if ap.parse_args().remove:
        remove()
        return 0
    c = theme_colours()
    print(f"Colours from your current settings (background {c['bg']}, text {c['text']}, accent {c['accent']}):")
    write(SCHEME, qt5ct_scheme(c))
    write(QT5CT_CONF, qt5ct_conf())
    write(KDEGLOBALS, kdeglobals(c))
    print("\nTest 1, regular VLC (needs qt5ct: sudo apt install qt5ct):")
    print("  QT_QPA_PLATFORMTHEME=qt5ct vlc")
    print("\nTest 2, Flatpak VLC:")
    print(f"  flatpak run --env=QT_QPA_PLATFORMTHEME=kde {VLC_FLATPAK}")
    print("\nUndo: python3 tools/qt-colors-experiment.py --remove")
    return 0


if __name__ == "__main__":
    sys.exit(main())
