"""The `cheeselooks` command."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from . import __version__, install, paths, reload, settings, styles, tokens
from .shape import DEFAULT_PANEL_HEIGHT


def _err(msg: str) -> None:
    print(f"cheeselooks: {msg}", file=sys.stderr)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --------------------------------------------------------------------------
# Presets
# --------------------------------------------------------------------------

def preset_files() -> list[Path]:
    files: list[Path] = []
    for base in (paths.user_presets_dir(), paths.builtin_presets_dir()):
        if base.is_dir():
            files.extend(sorted(base.rglob("*.json")))
    return files


def find_preset(name: str) -> dict:
    p = Path(name)
    if p.suffix == ".json" and p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    for f in preset_files():
        data = json.loads(f.read_text(encoding="utf-8"))
        if name in (data.get("name"), f.stem) or _slug(name) == f.stem:
            return data
    raise KeyError(name)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def _load_settings(args: argparse.Namespace) -> dict:
    path = Path(args.settings) if args.settings else paths.settings_file()
    fresh = not path.exists()
    data = settings.load(path)
    new_style = getattr(args, "style", None)
    if new_style:
        data["style"]["name"] = new_style
    if fresh or new_style or getattr(args, "style_defaults", False):
        # fresh install, a newly picked style, or "reset to style defaults":
        # start from the style's suggested [defaults]
        style = _load_style(data["style"]["name"], getattr(args, "style_dir", None))
        data = settings.apply_style_defaults(data, style.defaults)
    for name in args.preset or []:
        try:
            data = settings.apply_preset(data, find_preset(name))
        except KeyError:
            raise settings.SettingsError([f"no preset called '{name}' (see: cheeselooks presets)"])
    return data


def _load_style(name: str, extra_dir: str | None) -> styles.Style:
    dirs = ([Path(extra_dir)] if extra_dir else []) + paths.style_dirs()
    return styles.find(name, dirs)


def _where(style: styles.Style) -> str:
    """The style's file, and whether it replaces a built-in style of the same name."""
    if style.path is None:
        return "(built in)"
    folder = style.path.parent
    builtin = paths.data_dir() / "styles"
    try:
        folder.relative_to(builtin)
        return str(style.path)
    except ValueError:
        pass
    try:
        styles.find(style.name, [builtin])
    except styles.StyleError:
        return str(style.path)
    return f"{style.path} (your copy, used instead of the built-in {style.name})"


def cmd_apply(args: argparse.Namespace) -> int:
    data = _load_settings(args)
    style = _load_style(data["style"]["name"], args.style_dir)
    for w in style.warnings:
        _err(f"style warning: {w}")
    height = reload.panel_height(DEFAULT_PANEL_HEIGHT) if not args.no_reload else DEFAULT_PANEL_HEIGHT
    table = tokens.build(data, style, panel_height=height)
    if args.theme_dir:
        theme_dir = Path(args.theme_dir)
        last_good = theme_dir.with_name(f".{theme_dir.name}.last-good")
    else:
        theme_dir, last_good = paths.theme_dir(), paths.last_good_dir()
    written = install.install(paths.templates_dir(), table, theme_dir, last_good, data)
    if not args.no_save and not args.settings:
        settings.save(data, paths.settings_file())
    print(f"Wrote {len(written)} files to {theme_dir}")
    print(f"  style: {style.name} from {_where(style)}")
    for note in tokens.warnings(data):
        print(f"  note: {note}")
    if not args.no_reload and not args.theme_dir:
        layout = table["wb.button_layout"] if (theme_dir / "metacity-1").is_dir() else None
        for line in reload.apply(tokens.THEME_NAME, layout, activate=args.activate, theme_dir=theme_dir):
            print(f"  {line}")
    return 0


def cmd_revert(args: argparse.Namespace) -> int:
    data = install.revert(paths.theme_dir(), paths.last_good_dir())
    if data:
        settings.save(settings.from_dict(data), paths.settings_file())
    print("Restored the previous theme.")
    if not args.no_reload:
        for line in reload.apply(tokens.THEME_NAME, theme_dir=paths.theme_dir()):
            print(f"  {line}")
    return 0


def cmd_tokens(args: argparse.Namespace) -> int:
    data = _load_settings(args)
    style = _load_style(data["style"]["name"], args.style_dir)
    table = tokens.build(data, style)
    for key in sorted(table):
        if args.filter and args.filter not in key:
            continue
        value = table[key].replace("\n", "\\n")
        print(f"{key:40} {value[:120]}")
    return 0


def cmd_check_style(args: argparse.Namespace) -> int:
    try:
        style = styles.load(Path(args.path))
    except styles.StyleError as exc:
        print(f"{args.path}: {len(exc.problems)} problem(s)")
        for p in exc.problems:
            print(f"  error: {p}")
        return 1
    print(f"{style.name}: OK")
    for w in style.warnings:
        print(f"  warning: {w}")
    return 0


def cmd_presets(args: argparse.Namespace) -> int:
    for f in preset_files():
        data = json.loads(f.read_text(encoding="utf-8"))
        sections = [k for k in data if k not in ("name", "version")]
        print(f"{data.get('name', f.stem):28} {'/'.join(sections):10} {f}")
    return 0


def cmd_export_preset(args: argparse.Namespace) -> int:
    data = settings.load(paths.settings_file())
    section = args.section
    preset = {"name": args.name, section: data[section]}
    out = paths.user_presets_dir() / section / f"{_slug(args.name)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(preset, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cheeselooks",
                                     description="Generate and apply the xl-Cheeselooks theme.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--settings", help="use this settings file instead of your saved settings")
        p.add_argument("--preset", action="append",
                       help="apply a preset on top (name or .json file; can repeat)")
        p.add_argument("--style-dir", help="extra folder to look for styles in")

    p = sub.add_parser("apply", help="generate the theme and reload the desktop")
    common(p)
    p.add_argument("--theme-dir", help="write the theme here instead of ~/.themes (no reload)")
    p.add_argument("--style", help="switch to this style and start from its suggested defaults")
    p.add_argument("--style-defaults", action="store_true",
                   help="reset roundness, gradient, depth and panel/menu shape to the style's defaults")
    p.add_argument("--activate", action="store_true", help="also switch Cinnamon to this theme")
    p.add_argument("--no-reload", action="store_true", help="write files only")
    p.add_argument("--no-save", action="store_true", help="don't save the settings used")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("revert", help="go back to the previously applied theme")
    p.add_argument("--no-reload", action="store_true")
    p.set_defaults(func=cmd_revert)

    p = sub.add_parser("tokens", help="list every computed value (for template and style authors)")
    common(p)
    p.add_argument("filter", nargs="?", help="only show tokens containing this text")
    p.set_defaults(func=cmd_tokens)

    p = sub.add_parser("check-style", help="check a style file for problems")
    p.add_argument("path")
    p.set_defaults(func=cmd_check_style)

    p = sub.add_parser("presets", help="list available presets")
    p.set_defaults(func=cmd_presets)

    p = sub.add_parser("export-preset", help="save part of your current settings as a preset")
    p.add_argument("name")
    p.add_argument("--section", choices=("global", "panel", "terminal"), default="global")
    p.set_defaults(func=cmd_export_preset)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:  # output piped into e.g. `head`
        sys.stderr.close()
        return 0
    except (settings.SettingsError, styles.StyleError) as exc:
        for problem in exc.problems:
            _err(problem)
        return 2
    except (install.InstallError, OSError) as exc:
        _err(str(exc))
        return 1
    except Exception as exc:  # template problems and anything unexpected
        problems = getattr(exc, "problems", None)
        for problem in problems or [str(exc)]:
            _err(problem)
        return 1
