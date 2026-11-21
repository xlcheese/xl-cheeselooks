"""Qt apps in the theme's colours (Integration → "Qt apps"; opt-in, undoable).

Qt apps (VLC, qBittorrent...) don't read GTK colours: on Cinnamon, Qt 5 uses
its GTK 3 platform theme, which brings GTK's file dialogs and fonts but not
the colours, so they stay Qt's light grey and blue. Two routes, both tried
on xl_cheese's desktop with VLC (regular and Flatpak):

  regular Qt apps   a qt5ct colour scheme (~/.config/qt5ct/colors/xl-Cheeselooks.conf),
                    qt5ct.conf pointed at it, and QT_QPA_PLATFORMTHEME=qt5ct in
                    ~/.profile (from the next login; every Qt 5 app). Needs the
                    qt5ct package; file dialogs stay GTK's (standard_dialogs=gtk3).
  Flatpak Qt apps   a KDE colour scheme (kdeglobals) in each KDE-runtime app's own
                    config folder, and a per-app Flatpak override selecting Qt's
                    KDE platform theme, which reads it. The sandbox sees neither
                    qt5ct nor ~/.profile, hence the separate route.

Only colours: Qt still draws its own widget shapes (Fusion). Everything
written is recorded (STATE) so turning the switch off removes exactly that,
putting back any file it replaced (*.xl-backup).
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import palette as pal
from . import paths

SCHEME_NAME = "xl-Cheeselooks"
BACKUP = ".xl-backup"
MARK = "# Written by xl-Cheeselooks (Integration: Qt apps). Turning the switch off removes it."
PROFILE_START = "# >>> xl-Cheeselooks: Qt apps use the theme's colors (Integration tab) >>>"
PROFILE_END = "# <<< xl-Cheeselooks <<<"
PROFILE_LINE = "export QT_QPA_PLATFORMTHEME=qt5ct"
ENV = "QT_QPA_PLATFORMTHEME"
STYLE_ENV = "QT_STYLE_OVERRIDE"


def qt5ct_dir() -> Path:
    return paths._xdg("XDG_CONFIG_HOME", paths.HOME / ".config") / "qt5ct"


def scheme_file() -> Path:
    return qt5ct_dir() / "colors" / f"{SCHEME_NAME}.conf"


def profile_file() -> Path:
    return paths.HOME / ".profile"


def state_file() -> Path:
    return paths.config_dir() / "qt-colors.json"


def qt5ct_installed() -> bool:
    return bool(glob.glob("/usr/lib/*/qt5/plugins/platformthemes/libqt5ct.so")
                or glob.glob("/usr/lib/qt5/plugins/platformthemes/libqt5ct.so"))


def flatpak_qt_apps() -> list[str]:
    """Installed Flatpak apps on the KDE (Qt) runtime, e.g. org.videolan.VLC."""
    if shutil.which("flatpak") is None:
        return []
    try:
        out = subprocess.run(["flatpak", "list", "--app", "--columns=application,runtime"],
                             capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    apps = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith("org.kde.Platform/"):
            apps.append(parts[0])
    return sorted(set(apps))


def kdeglobals_file(app: str) -> Path:
    return paths.HOME / ".var" / "app" / app / "config" / "kdeglobals"


# ---------------------------------------------------------------- colours

def colours(t: dict[str, str]) -> dict[str, str]:
    """The theme's colours as Qt's palette needs them (from the token table)."""
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
    c["white"] = "#FFFFFF"
    return c


def qt5ct_scheme(c: dict[str, str]) -> str:
    # Qt 5's palette roles, in qt5ct's order (WindowText, Button, Light, Midlight,
    # Dark, Mid, Text, BrightText, ButtonText, Base, Window, Shadow, Highlight,
    # HighlightedText, Link, LinkVisited, AlternateBase, NoRole, ToolTipBase,
    # ToolTipText, PlaceholderText)
    roles = ["text", "button", "light", "midlight", "dark", "mid", "text", "white", "text", "base", "bg",
             "shadow", "accent", "accent_fg", "link", "link", "alt_base", "bg", "tip_bg", "tip_text", "text_dim"]

    def row(over: dict[int, str]) -> str:
        return ", ".join("#ff" + c[over.get(i, r)].lstrip("#").lower() for i, r in enumerate(roles))
    disabled = {0: "disabled_text", 6: "disabled_text", 8: "disabled_text", 12: "mid"}
    return (f"{MARK}\n[ColorScheme]\n"
            f"active_colors={row({})}\n"
            f"disabled_colors={row(disabled)}\n"
            f"inactive_colors={row({})}\n")


def kdeglobals(c: dict[str, str]) -> str:
    def rgb(name: str) -> str:
        return ",".join(str(v) for v in pal.to_rgb(c[name]))

    def group(name: str, bg: str, fg: str, alt: str) -> str:
        return (f"[Colors:{name}]\n"
                f"BackgroundNormal={rgb(bg)}\nBackgroundAlternate={rgb(alt)}\n"
                f"ForegroundNormal={rgb(fg)}\nForegroundInactive={rgb('text_dim')}\n"
                f"ForegroundLink={rgb('link')}\nForegroundVisited={rgb('link')}\n"
                f"DecorationFocus={rgb('accent')}\nDecorationHover={rgb('accent')}\n\n")
    return (f"{MARK}\n[General]\nColorScheme={SCHEME_NAME}\n\n[KDE]\nwidgetStyle=Fusion\n\n"
            + group("Window", "bg", "text", "bg")
            + group("View", "base", "text", "alt_base")
            + group("Button", "button", "text", "button")
            + group("Selection", "accent", "accent_fg", "accent")
            + group("Tooltip", "tip_bg", "tip_text", "tip_bg")
            + group("Complementary", "bg", "text", "bg"))


def qss(t: dict[str, str]) -> str:
    """Where Qt's palette has no slot of its own: the menu bar in the title
    bar / toolbar colour (GTK menubars are), and menus hovered as the style's
    GTK menus are, not in the selection's accent. Regular Qt apps only (qt5ct
    loads stylesheets; the Flatpak route can't, Kvantum would)."""
    def grad(top: str, bottom: str) -> str:
        return f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top}, stop:1 {bottom})"
    mb, mi = "w.menubar_item.", "w.menu_item."
    r = t["r"]
    return f"""/* {MARK} */
QMenuBar {{ background-color: {t['header']}; color: {t['text']}; }}
QMenuBar::item {{ background: transparent; padding: 4px 8px; border-radius: {r}px; }}
QMenuBar::item:selected, QMenuBar::item:pressed {{
  background: {grad(t[mb + 'hover_top'], t[mb + 'hover_bottom'])}; color: {t[mb + 'hover_fg']}; }}
QMenu {{ background-color: {t['menu_bg']}; color: {t['text']}; border: 1px solid {t['border']}; padding: 4px 0; }}
QMenu::item {{ padding: 5px 24px 5px 26px; border-radius: {r}px; margin: 0 4px; }}
QMenu::item:selected {{ background: {grad(t[mi + 'hover_top'], t[mi + 'hover_bottom'])}; color: {t[mi + 'hover_fg']}; }}
QMenu::item:disabled {{ color: {t['text_dim']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}
QMenu::icon, QMenu::indicator {{ padding-left: 6px; }}
"""


def qss_file() -> Path:
    return qt5ct_dir() / "qss" / f"{SCHEME_NAME}.qss"


def qt5ct_conf(existing: str) -> str:
    """qt5ct.conf pointed at our scheme and stylesheet, in Qt's Fusion style
    (a Kvantum style would ignore the colours). Anything else you had there is
    kept (fonts, your file dialog choice, stylesheets), and the whole file as
    it was is in the backup, put back when the switch goes off."""
    want = {"Appearance": {"color_scheme_path": str(scheme_file()), "custom_palette": "true",
                           "style": "Fusion"},
            "Interface": {"stylesheets": str(qss_file())}}
    if_missing = {"Appearance": {"standard_dialogs": "gtk3"}}
    sections: list[list] = [[None, []]]            # [name, lines]
    for line in existing.splitlines():
        st = line.strip()
        if st.startswith("[") and st.endswith("]"):
            sections.append([st[1:-1], []])
        else:
            sections[-1][1].append(line)
    for name in list(want) + [n for n in if_missing if n not in want]:
        if not any(sec[0] == name for sec in sections):
            sections.append([name, []])
    out = []
    for name, lines in sections:
        if name is not None:
            out.append(f"[{name}]")
        set_here = dict(want.get(name, {}))
        keys = {ln.split("=", 1)[0].strip() for ln in lines if "=" in ln}
        for ln in lines:
            key = ln.split("=", 1)[0].strip() if "=" in ln else None
            if key == "stylesheets" and name == "Interface":
                # qt5ct writes "@Invalid()" for an empty list: not a stylesheet
                have = [x.strip() for x in ln.split("=", 1)[1].split(",")
                        if x.strip() and not x.strip().startswith("@Invalid")]
                if set_here["stylesheets"] not in have:
                    have.append(set_here["stylesheets"])
                out.append("stylesheets=" + ", ".join(have))
                set_here.pop("stylesheets")
            elif key in set_here:
                out.append(f"{key}={set_here.pop(key)}")
            else:
                out.append(ln)
        while out and not out[-1].strip():
            out.pop()
        out += [f"{k}={v}" for k, v in set_here.items()]
        out += [f"{k}={v}" for k, v in if_missing.get(name, {}).items() if k not in keys]
        out.append("")
    return "\n".join(out).strip() + "\n"


# ---------------------------------------------------------------- state

def _load_state() -> dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    f = state_file()
    if not any(state.values()):
        if f.exists():
            f.unlink()
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _is_ours(text: str) -> bool:
    """A file we wrote: marked, or (from earlier versions and the experiment
    script) pointing at our scheme or naming it."""
    return (MARK in text or str(scheme_file()) in text or f"{SCHEME_NAME}.conf" in text
            or f"ColorScheme={SCHEME_NAME}" in text)


def _write(path: Path, text: str, state: dict) -> None:
    """Write a file, keeping the one it replaces (the first time) to put back later."""
    files = state.setdefault("files", {})
    key = str(path)
    if key not in files:
        backup = path.with_name(path.name + BACKUP)
        if path.exists() and not _is_ours(path.read_text(encoding="utf-8", errors="replace")):
            shutil.copy2(path, backup)
            files[key] = "backup"
        else:
            files[key] = "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- ~/.profile

def _profile_without_ours(text: str) -> str:
    out, skipping = [], False
    for line in text.splitlines():
        if line.strip() == PROFILE_START:
            skipping = True
            continue
        if skipping:
            if line.strip() == PROFILE_END:
                skipping = False
            continue
        out.append(line)
    return "\n".join(out).rstrip("\n") + "\n" if out else ""


def _profile_sets_it(text: str) -> bool:
    """Your own ~/.profile chooses a Qt theme or style (outside our block)."""
    return any((ENV in line or STYLE_ENV in line) and not line.lstrip().startswith("#")
               for line in _profile_without_ours(text).splitlines())


def _set_profile(on: bool) -> str | None:
    """Our block goes at the end of ~/.profile, after any Qt line of yours, so it
    wins without your line being touched; removing it lets yours apply again."""
    f = profile_file()
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    has = PROFILE_START in text
    if on and not has:
        block = f"\n{PROFILE_START}\n{PROFILE_LINE}\nunset {STYLE_ENV}\n{PROFILE_END}\n"
        f.write_text(text.rstrip("\n") + "\n" + block if text else block.lstrip("\n"), encoding="utf-8")
        return f"added {PROFILE_LINE} to {f} (Qt apps use it from your next login)"
    if not on and has:
        f.write_text(_profile_without_ours(text), encoding="utf-8")
        return f"removed the Qt lines from {f} (from your next login)"
    return None


# ---------------------------------------------------------------- Flatpak overrides

def overrides_dir() -> Path:
    return paths._xdg("XDG_DATA_HOME", paths.HOME / ".local" / "share") / "flatpak" / "overrides"


def _read_env(path: Path) -> dict[str, str]:
    env, inside = {}, False
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            st = line.strip()
            if st.startswith("["):
                inside = st == "[Environment]"
            elif inside and "=" in st:
                k, v = st.split("=", 1)
                env[k.strip()] = v
    return env


def _set_env(path: Path, updates: dict[str, str | None]) -> None:
    """Set (or, with None, remove) keys in an override file's [Environment],
    leaving everything else in it as it is (what `flatpak override` writes)."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, inside, done, had = [], False, set(), False
    for line in lines:
        st = line.strip()
        if st.startswith("["):
            if inside:
                out += [f"{k}={v}" for k, v in updates.items() if v is not None and k not in done]
                done |= set(updates)
            inside = st == "[Environment]"
            had = had or inside
            out.append(line)
            continue
        key = st.split("=", 1)[0].strip() if inside and "=" in st else None
        if key in updates:
            if updates[key] is not None and key not in done:
                out.append(f"{key}={updates[key]}")
            done.add(key)
            continue
        out.append(line)
    if inside:
        out += [f"{k}={v}" for k, v in updates.items() if v is not None and k not in done]
    elif not had and any(v is not None for v in updates.values()):
        out += (["", "[Environment]"] if out else ["[Environment]"])
        out += [f"{k}={v}" for k, v in updates.items() if v is not None]
    # a section left with nothing in it goes too (and the file, if that was all)
    kept: list[str] = []
    for n, line in enumerate(out):
        if line.strip().startswith("["):
            rest = out[n + 1:]
            nxt = next((k for k, l in enumerate(rest) if l.strip().startswith("[")), len(rest))
            if not any(l.strip() for l in rest[:nxt]):
                continue
        kept.append(line)
    out = kept
    while out and not out[-1].strip():
        out.pop()
    path.parent.mkdir(parents=True, exist_ok=True)
    if out:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    elif path.exists():
        path.unlink()


def _ours_env(key: str, value: str | None) -> bool:
    return value is not None and ((key == ENV and value == "kde") or (key == STYLE_ENV and value == ""))


def _flatpak_app_on(app: str, state: dict, found: list[str]) -> None:
    """The app picks Qt's KDE platform theme, which reads our kdeglobals; a Qt
    style of yours (e.g. Kvantum, which ignores colours) is set aside. Your
    previous values are recorded the first time, to put back."""
    f = overrides_dir() / app
    before = _read_env(f)
    prev = state.setdefault("flatpak_prev", {})
    if app not in prev:
        # values an earlier version of this switch wrote ("kde", an emptied
        # style) are ours, not yours: nothing to keep or put back
        prev[app] = {k: (None if _ours_env(k, before.get(k)) else before.get(k)) for k in (ENV, STYLE_ENV)}
        if any(v for v in prev[app].values()):
            found.append(f"{app}'s Qt setting")
    style_set = before.get(STYLE_ENV) or _read_env(overrides_dir() / "global").get(STYLE_ENV)
    _set_env(f, {ENV: "kde", **({STYLE_ENV: ""} if style_set else {})})


def _flatpak_app_off(app: str, before: dict[str, str | None]) -> None:
    # values of ours recorded as "before" by an earlier version are removed, not put back
    _set_env(overrides_dir() / app, {k: (None if _ours_env(k, v) else v) for k, v in before.items()})


# ---------------------------------------------------------------- on / off

def _yours_qt5ct(text: str) -> bool:
    """qt5ct settings of yours: your own colours or Kvantum. Settings pointing at
    our scheme are left from an earlier time the switch was on: ours."""
    if str(scheme_file()) in text or f"{SCHEME_NAME}.conf" in text:
        return False
    return "custom_palette=true" in text or "kvantum" in text.lower()


def _found_setup() -> list[str]:
    """A Qt setup of yours that our colours now take the place of (kept, and
    back when the switch goes off): for the one-time notice."""
    found = []
    if os.environ.get(ENV, "") not in ("", "qt5ct") or os.environ.get(STYLE_ENV):
        found.append("your session's Qt theme setting")
    f = profile_file()
    if f.exists() and _profile_sets_it(f.read_text(encoding="utf-8", errors="replace")):
        found.append(f"the Qt line in {f} (left in place, ours comes after it)")
    conf = qt5ct_dir() / "qt5ct.conf"
    if conf.exists():
        text = conf.read_text(encoding="utf-8", errors="replace")
        if _yours_qt5ct(text):
            found.append(f"your qt5ct settings ({conf}, saved as {conf.name}{BACKUP})")
    return found


def enable(t: dict[str, str]) -> list[str]:
    """Write (or rewrite) the colour schemes from the theme's tokens. Our own
    files are simply rewritten at each Apply; anything of yours is moved
    aside the first time and kept. Returns log lines."""
    log = []
    state = _load_state()
    first = not state.get("files") and not state.get("flatpak_prev") and not state.pop("set_aside", False)
    found = _found_setup() if first else []
    c = colours(t)
    if qt5ct_installed():
        _write(scheme_file(), qt5ct_scheme(c), state)
        _write(qss_file(), qss(t), state)
        conf = qt5ct_dir() / "qt5ct.conf"
        current = conf.read_text(encoding="utf-8") if conf.exists() else ""
        _write(conf, qt5ct_conf(current), state)
        line = _set_profile(True)
        if line:
            log.append(line)
        log.append("Qt apps: colors written for qt5ct")
    else:
        log.append("Qt apps: qt5ct isn't installed (sudo apt install qt5ct), so regular Qt apps "
                   "keep Qt's colors; Flatpak Qt apps are still done")
    done = []
    for app in flatpak_qt_apps():
        kde = kdeglobals_file(app)
        if first and kde.exists() and not _is_ours(kde.read_text(encoding="utf-8", errors="replace")):
            found.append(f"{app}'s KDE colors")
        _write(kde, kdeglobals(c), state)
        _flatpak_app_on(app, state, found)
        done.append(app)
    if done:
        log.append(f"Qt apps: colors written for Flatpak {', '.join(done)} (reopen them to see it)")
    if found:
        state["notice"] = found
        log.append("Qt apps: your previous Qt setup is saved: " + "; ".join(found))
    _save_state(state)
    return log


def disable(set_aside: bool = False) -> list[str]:
    """Remove everything enable() wrote, putting back what it replaced. From the
    watcher (set_aside), it remembers that it was on, so putting it back when
    you return to xl-Cheeselooks doesn't count as a first time (no notice)."""
    state = _load_state()
    if not state or set(state) == {"set_aside"}:
        return []
    log = []
    for key, how in state.get("files", {}).items():
        path = Path(key)
        backup = path.with_name(path.name + BACKUP)
        if how == "backup" and backup.exists():
            if _is_ours(backup.read_text(encoding="utf-8", errors="replace")):
                backup.unlink()               # a leftover of ours, kept by mistake: tidy it away
                if path.exists():
                    path.unlink()
            else:
                shutil.move(str(backup), path)
        elif path.exists():
            path.unlink()
    for app, before in state.get("flatpak_prev", {}).items():
        _flatpak_app_off(app, before)
    line = _set_profile(False)
    if line:
        log.append(line)
    _save_state({"set_aside": True} if set_aside else {})
    log.append("Qt apps: our colors removed (your own Qt setup, if any, is back)")
    return log


def active() -> bool:
    state = _load_state()
    return bool(state) and set(state) != {"set_aside"}


def pending_notice() -> str | None:
    """Once, after our colours first took the place of a Qt setup of yours:
    what was kept, and how to get it back. None otherwise."""
    found = _load_state().get("notice")
    if not found:
        return None
    return ("Your Qt apps now use xl-Cheeselooks colors.\n\n"
            "Your previous Qt setup is saved: " + "; ".join(found) + ".\n\n"
            "Turning off Integration → Qt apps puts it back.")


def notice_shown() -> None:
    state = _load_state()
    if state.pop("notice", None) is not None:
        _save_state(state)


def note() -> str:
    """The line under the switch: when it takes effect, and what it needs."""
    text = ("Your colors in Qt apps such as VLC (Qt keeps its own shapes). Qt apps read "
            "their colors when they start: reopen any that are open. The first time, regular "
            "Qt apps need you to log out and back in. A Qt setup of your own is saved and "
            "comes back when this is off.")
    if not qt5ct_installed():
        text += "\nRegular Qt apps need qt5ct: sudo apt install qt5ct"
    return text
