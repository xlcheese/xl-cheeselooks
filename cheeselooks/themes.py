"""Themes: named, complete looks.

A theme is a full set of settings (every tab) that points to one style. Many
themes can share a style. Picking a theme sets everything to that theme;
changing anything afterwards turns it into "Custom", which keeps your latest
changes until you pick another theme or save Custom under a name of its own.

    built-in themes   data/themes/*.json in the repository
    your themes       ~/.local/share/xl-cheeselooks/themes/*.json
    Custom            ~/.config/xl-cheeselooks/custom.json

A theme file holds only what differs from the defaults plus the style's own
[defaults], so a theme stays small and follows improvements to its style:

    {"format": 1, "name": "Claude", "settings": {"style": {"name": "xl-Claude"},
                                                 "global": {"accent": "#B85A38", ...}}}

Export packs a theme into one compressed file (<name>.xltheme, a zip) with
everything another person needs: the settings, the tool and format version,
and the style folder when the theme uses one of your own styles.
"""

from __future__ import annotations

import copy
import json
import re
import zipfile
from pathlib import Path

from . import __version__, paths, settings, styles

FORMAT = 1                 # theme file format; a newer one on import gets a warning
CUSTOM = "Custom"
EXTENSION = ".xltheme"


def builtin_dir() -> Path:
    return paths.data_dir() / "data" / "themes"


def user_dir() -> Path:
    return paths._xdg("XDG_DATA_HOME", paths.HOME / ".local" / "share") / "xl-cheeselooks" / "themes"


def custom_file() -> Path:
    return paths.config_dir() / "custom.json"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "theme"


class ThemeError(ValueError):
    pass


def _read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("name"), str) or not isinstance(data.get("settings"), dict):
        raise ThemeError(f"{path} is not a theme file (needs a name and settings)")
    return data


def list_themes() -> list[tuple[str, Path, bool]]:
    """(name, file, built_in) for every theme; yours can't hide a built-in one."""
    out: list[tuple[str, Path, bool]] = []
    seen: set[str] = set()
    for base, builtin in ((builtin_dir(), True), (user_dir(), False)):
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.json")):
            try:
                name = _read(f)["name"]
            except (ThemeError, ValueError, OSError):
                continue
            if name in seen or name == CUSTOM:
                continue
            seen.add(name)
            out.append((name, f, builtin))
    return out


def find(name: str) -> tuple[Path, bool]:
    for n, f, builtin in list_themes():
        if n == name:
            return f, builtin
    raise ThemeError(f"no theme called '{name}'")


def expand(theme_settings: dict, style_dirs: list[Path] | None = None) -> dict:
    """A theme's full settings: the defaults, its style's [defaults], then the theme."""
    base = copy.deepcopy(settings.DEFAULTS)
    style_name = theme_settings.get("style", {}).get("name", base["style"]["name"])
    base["style"]["name"] = style_name
    try:
        style = styles.find(style_name, style_dirs or paths.style_dirs())
        base = settings.apply_style_defaults(base, style.defaults)
    except styles.StyleError:
        pass                       # missing style: the caller reports it when it loads
    return settings.from_dict(settings._deep_merge(base, theme_settings))


def load(name: str) -> dict:
    """Full settings for a named theme (or Custom), with "theme" set to its name."""
    if name == CUSTOM:
        data = load_custom()
        if data is None:
            raise ThemeError("there are no custom settings yet")
        return data
    f, _builtin = find(name)
    data = expand(_read(f)["settings"])
    data["theme"] = name
    return data


def load_custom() -> dict | None:
    f = custom_file()
    if not f.exists():
        return None
    data = settings.from_dict(json.loads(f.read_text(encoding="utf-8")))
    data["theme"] = CUSTOM
    return data


def save_custom(data: dict, based_on: str | None) -> None:
    out = copy.deepcopy(data)
    out["theme"] = CUSTOM
    out["based_on"] = based_on
    f = custom_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def based_on() -> str | None:
    f = custom_file()
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")).get("based_on")
    return None


def _minimal(data: dict) -> dict:
    """Only what differs from the theme's style defaults (keeps files small)."""
    full = copy.deepcopy(data)
    full.pop("theme", None)
    full.pop("based_on", None)
    full.pop("version", None)
    base = expand({"style": {"name": full["style"]["name"]}})
    base.pop("theme", None)
    base.pop("version", None)

    def diff(a: dict, b: dict) -> dict:
        out = {}
        for k, v in a.items():
            if isinstance(v, dict) and isinstance(b.get(k), dict):
                d = diff(v, b[k])
                if d:
                    out[k] = d
            elif b.get(k) != v:
                out[k] = v
        return out
    out = diff(full, base)
    out.setdefault("style", {})["name"] = full["style"]["name"]
    return out


def save(name: str, data: dict, overwrite: bool = False) -> Path:
    """Save settings as one of your themes. Refuses built-in names and, unless
    overwrite, an existing theme of yours."""
    name = name.strip()
    if not name or name == CUSTOM:
        raise ThemeError("give the theme a name (not \"Custom\")")
    for n, f, builtin in list_themes():
        if n == name and builtin:
            raise ThemeError(f"'{name}' is a built-in theme: choose another name")
        if n == name and not overwrite:
            raise ThemeError(f"you already have a theme called '{name}'")
    f = user_dir() / f"{slug(name)}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    doc = {"format": FORMAT, "name": name, "tool_version": __version__, "settings": _minimal(data)}
    f.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return f


def delete(name: str) -> None:
    f, builtin = find(name)
    if builtin:
        raise ThemeError("built-in themes can't be deleted")
    f.unlink()


# ---------------------------------------------------------------- export / import

def export(name: str, data: dict, dest: Path) -> Path:
    """Write <dest> (.xltheme, a zip): theme.json, plus the style folder when the
    theme uses one of your own styles (built-in styles ship with the tool)."""
    dest = Path(dest)
    if dest.suffix != EXTENSION:
        dest = dest.with_suffix(EXTENSION)
    style_name = data["style"]["name"]
    style = styles.find(style_name, paths.style_dirs())
    builtin_styles = (paths.data_dir() / "styles").resolve()
    own_style = style.path is not None and builtin_styles not in style.path.resolve().parents
    doc = {"format": FORMAT, "name": name, "tool_version": __version__,
           "style_included": own_style, "settings": _minimal(data)}
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("theme.json", json.dumps(doc, indent=2) + "\n")
        if own_style:
            folder = style.path.parent
            for f in sorted(folder.rglob("*")):
                if f.is_file():
                    z.write(f, f"style/{f.relative_to(folder)}")
    return dest


def import_file(src: Path) -> tuple[str, list[str]]:
    """Install a .xltheme: its style (if included) and the theme. Returns the
    theme's name and plain-language notes (a newer format, renamed name...)."""
    notes: list[str] = []
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        if "theme.json" not in names:
            raise ThemeError(f"{Path(src).name} isn't an xl-Cheeselooks theme file")
        doc = json.loads(z.read("theme.json"))
        if doc.get("format", 1) > FORMAT:
            notes.append(f"This theme was made with a newer xl-Cheeselooks ({doc.get('tool_version', '?')}). "
                         "Some of it may not show as intended; updating xl-Cheeselooks is recommended.")
        style_name = doc["settings"].get("style", {}).get("name")
        if doc.get("style_included") and style_name:
            target = paths.style_dirs()[0] / slug(style_name)
            if target.exists():
                notes.append(f"You already have a style folder '{target.name}': kept yours, "
                             "so the theme uses your copy of that style.")
            else:
                for n in names:
                    if n.startswith("style/") and not n.endswith("/"):
                        rel = Path(n).relative_to("style")
                        if ".." in rel.parts:
                            raise ThemeError("the theme file contains an unsafe path")
                        out = target / rel
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(z.read(n))
    name = doc["name"]
    existing = {n for n, _f, _b in list_themes()}
    final = name
    i = 2
    while final in existing or final == CUSTOM:
        final = f"{name} ({i})"
        i += 1
    if final != name:
        notes.append(f"A theme called '{name}' already exists: imported as '{final}'.")
    f = user_dir() / f"{slug(final)}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({**doc, "name": final}, indent=2) + "\n", encoding="utf-8")
    try:
        styles.find(style_name, paths.style_dirs())
    except styles.StyleError:
        notes.append(f"The style '{style_name}' isn't installed, so this theme can't be used until it is.")
    return final, notes
