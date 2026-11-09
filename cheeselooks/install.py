"""Write the generated theme safely.

Render into a temporary folder next to the theme, check it, keep a copy of
the current theme as "last good", then swap the new one in. If anything
fails before the swap, the installed theme is untouched.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import render

REQUIRED_FILES = ("index.theme",)


class InstallError(RuntimeError):
    pass


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def build(template_dir: Path, tokens: dict[str, str], out_dir: Path) -> list[Path]:
    """Render templates into out_dir (which must not exist yet) and check the result."""
    if out_dir.exists():
        raise InstallError(f"{out_dir} already exists")
    out_dir.mkdir(parents=True)
    written = render.render_tree(template_dir, out_dir, tokens)
    for name in REQUIRED_FILES:
        if not (out_dir / name).is_file():
            raise InstallError(f"generated theme is missing {name}")
    for path in written:
        if path.suffix in (".css", ".xml", ".theme", ".svg") and "{{" in path.read_text(encoding="utf-8"):
            raise InstallError(f"{path.relative_to(out_dir)} still contains a placeholder")
    return written


def install(template_dir: Path, tokens: dict[str, str], theme_dir: Path,
            last_good: Path, settings: dict | None = None) -> list[Path]:
    """Generate and swap in the theme. Returns the files written."""
    theme_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = theme_dir.with_name(f".{theme_dir.name}.new")
    old = theme_dir.with_name(f".{theme_dir.name}.old")
    _remove(staging)
    _remove(old)
    try:
        written = build(template_dir, tokens, staging)
    except Exception:
        _remove(staging)
        raise

    if theme_dir.exists():
        _remove(last_good)
        last_good.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(theme_dir, last_good / "theme", symlinks=True)
        previous = theme_dir.parent / f".{theme_dir.name}.settings.json"
        if previous.exists():
            shutil.copy2(previous, last_good / "settings.json")
        theme_dir.rename(old)
    staging.rename(theme_dir)
    _remove(old)

    if settings is not None:
        (theme_dir.parent / f".{theme_dir.name}.settings.json").write_text(
            json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return [theme_dir / p.relative_to(staging) for p in written]


def revert(theme_dir: Path, last_good: Path) -> dict | None:
    """Put the last good theme back. Returns its settings if they were saved."""
    saved = last_good / "theme"
    if not saved.is_dir():
        raise InstallError("there is no earlier theme to go back to yet")
    old = theme_dir.with_name(f".{theme_dir.name}.old")
    _remove(old)
    if theme_dir.exists():
        theme_dir.rename(old)
    shutil.copytree(saved, theme_dir, symlinks=True)
    _remove(old)
    settings_path = last_good / "settings.json"
    if settings_path.exists():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        shutil.copy2(settings_path, theme_dir.parent / f".{theme_dir.name}.settings.json")
        return data
    return None
