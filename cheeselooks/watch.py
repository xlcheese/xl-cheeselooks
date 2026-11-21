"""The theme watcher (Integration → "Follow Mint's theme setting"; on by default).

Some of what Apply writes lives outside the theme folder and applies whatever
theme is selected: the colour block (and full styling) in
~/.config/gtk-4.0/gtk.css, the Qt colours, the text editors' scheme. Pick
Mint-Y in Mint's Themes settings and GTK 4, Flatpak, Qt and editor apps would
keep xl-Cheeselooks' colours. So a small process started at login waits for
the GTK theme setting to change (gsettings monitor: no CPU while it waits):

  away from xl-Cheeselooks   our extra files are taken out of the apps
                             (set_aside: GTK 4 block, Qt, editors; yours
                             put back, as switching each off does)
  back to xl-Cheeselooks     they're written again from your settings

A change is acted on only once it has settled (Apply's own reload switches the
theme away and back in under a second), and never while Apply is running.
Flatpak access and the GNOME accent are left as they are: harmless with any
theme.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import editor, gtk4, paths, qt, reload, tokens

SCHEMA, KEY = "org.cinnamon.desktop.interface", "gtk-theme"
SETTLE = 2.0                  # seconds a change must last before we act on it
AUTOSTART_NAME = "xl-cheeselooks-watch.desktop"
WATCH_PATTERN = "(theme-roller|cheeselooks) watch"   # the old name too, started before the rename


def is_ours(theme: str | None) -> bool:
    """Our theme, or the short-lived name Apply reloads through."""
    return bool(theme) and theme in (tokens.THEME_NAME, f".{tokens.THEME_NAME}-reloading")


def lock_file() -> Path:
    return paths.config_dir() / "applying"


def set_aside_file() -> Path:
    return paths.config_dir() / "set-aside"


class applying:
    """While Apply runs: the watcher leaves our files alone (Apply writes them,
    and its reload switches the theme away and back)."""
    def __enter__(self):
        f = lock_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(str(os.getpid()), encoding="utf-8")
        if set_aside_file().exists():
            set_aside_file().unlink()        # Apply puts everything back
        return self

    def __exit__(self, *_exc):
        if lock_file().exists():
            lock_file().unlink()
        return False


# ---------------------------------------------------------------- the two actions

def set_aside() -> list[str]:
    """Take our colours out of GTK 4 / libadwaita, Qt and editor apps (yours put
    back), without changing your settings. The next Apply, or switching back
    to xl-Cheeselooks, writes them again."""
    log = []
    line = gtk4.write(paths.gtk4_css(), None)
    if line:
        log.append(line)
    gtk4.remove_assets(paths.gtk4_css())
    if qt.active():
        log += qt.disable(set_aside=True)
    if editor.active():
        log += editor.disable()
    f = set_aside_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("", encoding="utf-8")
    return log or ["nothing of xl-Cheeselooks' was in your apps"]


def restore() -> list[str]:
    """Write the extra files again, from your saved settings."""
    from . import cli, settings
    data = settings.load(paths.settings_file())
    style = cli._load_style(data["style"]["name"], None)
    table = tokens.build(data, style)
    log = cli._libadwaita(data, table)
    if set_aside_file().exists():
        set_aside_file().unlink()
    return log


# ---------------------------------------------------------------- the watcher

def _current() -> str | None:
    return reload.get(SCHEMA, KEY)


def _act(theme: str | None) -> None:
    if theme is None or lock_file().exists():
        return                              # unreadable, or Apply is writing these itself
    if is_ours(theme):
        if set_aside_file().exists():
            restore()
    elif not set_aside_file().exists():
        set_aside()


def run() -> int:
    """Watch the GTK theme setting until logout. Returns an exit code."""
    if not reload.available() or shutil.which("gsettings") is None:
        print("gsettings not found: nothing to watch", file=sys.stderr)
        return 1
    _act(_current())                         # a change made while we weren't running
    proc = subprocess.Popen(["gsettings", "monitor", SCHEMA, KEY],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    for _line in proc.stdout:
        time.sleep(SETTLE)                   # let Apply's away-and-back pass
        _act(_current())
    return proc.wait()


# ---------------------------------------------------------------- start at login

def autostart_file() -> Path:
    return paths._xdg("XDG_CONFIG_HOME", paths.HOME / ".config") / "autostart" / AUTOSTART_NAME


def command() -> list[str]:
    """How to start the watcher: the checkout's bin/theme-roller, or the installed one."""
    checkout = paths.data_dir() / "bin" / "theme-roller"
    if checkout.exists():
        return [sys.executable, str(checkout), "watch"]
    return [shutil.which("theme-roller") or "theme-roller", "watch"]


def autostart_text() -> str:
    exec_line = " ".join(f'"{c}"' if " " in c else c for c in command())
    return ("[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Theme Roller theme watcher\n"
            "Comment=Takes xl-Cheeselooks' colors out of apps when you pick another theme\n"
            f"Exec={exec_line}\n"
            "NoDisplay=true\n"
            "X-GNOME-Autostart-enabled=true\n")


def running() -> bool:
    try:
        out = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", WATCH_PATTERN],
                             capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(pid.strip() and int(pid) != os.getpid() for pid in out.split())


def enable() -> list[str]:
    """Start at login, and now if it isn't running yet."""
    f = autostart_file()
    text = autostart_text()
    log = []
    if not f.exists() or f.read_text(encoding="utf-8") != text:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
        log.append("the theme watcher starts at login")
    if not running():
        try:
            subprocess.Popen(command(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            log.append("theme watcher started")
        except OSError:
            pass
    return log


def disable() -> list[str]:
    log = []
    f = autostart_file()
    if f.exists():
        f.unlink()
        log.append("the theme watcher no longer starts at login")
    try:
        subprocess.run(["pkill", "-u", str(os.getuid()), "-f", WATCH_PATTERN],
                       capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        pass
    return log
