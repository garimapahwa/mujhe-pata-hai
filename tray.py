"""Side Eye — Windows tray app: an eye by the clock. Click it to switch on/off; right-click for the
same menu as on macOS (on/off, voices, remind after, start with Windows, quit).

Run: pythonw tray.py          (use --on to start switched on)
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Optional

import pystray
from PIL import Image, ImageDraw

import config
from config import PERSONAS
from controller import APP_NAME, IDLE_CHOICES, VOICE_GROUPS, Controller, already_running, save_prefs

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "SideEye"
PINK, CREAM, NAVY, GREY = (214, 120, 127), (241, 233, 226), (46, 44, 69), (138, 135, 150)


# ------------------------------------------------------------------ start with Windows (HKCU Run key)
def _command() -> str:
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return f'"{pythonw if pythonw.exists() else exe}" "{config.ROOT / "tray.py"}"'


def start_with_windows() -> bool:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
        return True
    except OSError:
        return False


def set_start_with_windows(on: bool) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except OSError:
                pass


# ------------------------------------------------------------------ icon / key prompt
def eye_image(on: bool, size: int = 64) -> Image.Image:
    """A cream almond eye on a pink disc (grey when off): readable on light and dark taskbars.
    Drawn 4x larger and scaled down for smooth edges."""
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, big - 1, big - 1), fill=PINK if on else GREY)
    cx, cy, half_w, lid = big / 2, big / 2, big * 0.34, big * 0.20
    steps = [i / 40 for i in range(41)]
    top = [(cx - half_w + 2 * half_w * t, cy - lid * (1 - (2 * t - 1) ** 2)) for t in steps]
    bottom = [(cx - half_w + 2 * half_w * t, cy + lid * (1 - (2 * t - 1) ** 2)) for t in reversed(steps)]
    d.polygon(top + bottom, fill=CREAM)
    r = big * 0.135
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=NAVY)
    g = big * 0.04
    d.ellipse((cx + r * 0.25, cy - r * 0.65, cx + r * 0.25 + 2 * g, cy - r * 0.65 + 2 * g), fill=CREAM)  # glint
    return img.resize((size, size), Image.LANCZOS)


def ask_api_key() -> Optional[str]:
    import tkinter as tk
    from tkinter import simpledialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return simpledialog.askstring(
            "Sarvam AI API key", "Paste your key from dashboard.sarvam.ai.\nIt's saved only on this PC.", parent=root
        )
    finally:
        root.destroy()


# ------------------------------------------------------------------ app
class TrayApp:
    def __init__(self) -> None:
        self.ctl = Controller(ask_api_key)
        self.icon = pystray.Icon(RUN_NAME, eye_image(False), APP_NAME, self._menu())
        self._shown_on: Optional[bool] = None

    def _menu(self) -> pystray.Menu:
        item, sep = pystray.MenuItem, pystray.Menu.SEPARATOR
        voices: list = []
        for i, (group, keys) in enumerate(VOICE_GROUPS.items()):
            if i:
                voices.append(sep)
            voices.append(item(group, None, enabled=False))
            for key in keys:
                voices.append(item(PERSONAS[key].title, self._pick_voice(key), checked=self._is_voice(key), radio=True))
        times = [item("Idle for", None, enabled=False)] + [
            item(label, self._pick_idle(secs), checked=self._is_idle(secs), radio=True) for secs, label in IDLE_CHOICES.items()
        ]
        return pystray.Menu(
            item(APP_NAME, self.on_toggle, checked=lambda _it: self.ctl.on, default=True),  # default = left click
            sep,
            item("Voices", pystray.Menu(*voices)),
            item("Remind After", pystray.Menu(*times)),
            sep,
            item("Start with Windows", self.on_toggle_login, checked=lambda _it: start_with_windows()),
            sep,
            item(f"Quit {APP_NAME}", self.on_quit),
        )

    # pystray checks callback arity, so each menu row gets its own small closure
    def _pick_voice(self, key: str):
        return lambda: self.ctl.pick_voice(key)

    def _is_voice(self, key: str):
        return lambda _item: self.ctl.prefs["persona"] == key

    def _pick_idle(self, secs: int):
        return lambda: self.ctl.pick_idle(secs)

    def _is_idle(self, secs: int):
        return lambda _item: self.ctl.prefs["idle"] == secs

    def on_toggle(self, _icon=None, _item=None) -> None:
        if self.ctl.on:
            self.ctl.turn_off()
        else:
            self.ctl.turn_on()

    def on_toggle_login(self, _icon=None, _item=None) -> None:
        set_start_with_windows(not start_with_windows())

    def on_quit(self, _icon=None, _item=None) -> None:
        self.ctl.stop()
        self.icon.stop()

    def _watch(self) -> None:
        """Keep the icon in step with the engine (bright when on, grey when off)."""
        while True:
            on = self.ctl.on
            if on != self._shown_on:
                self._shown_on = on
                self.icon.icon = eye_image(on)
                self.icon.title = f"{APP_NAME}: {'on' if on else 'off'}"
                self.icon.update_menu()
            threading.Event().wait(0.4)

    def _setup(self, icon: pystray.Icon) -> None:
        icon.visible = True
        if not self.ctl.prefs.get("welcomed"):
            self.ctl.prefs["welcomed"] = True
            save_prefs(self.ctl.prefs)
            try:
                icon.notify("Click the eye to switch on. Right-click for voices and settings.", APP_NAME)
            except Exception:
                pass
        if "--on" in sys.argv or self.ctl.prefs.get("enabled"):
            self.ctl.turn_on()
        threading.Thread(target=self._watch, daemon=True).start()

    def run(self) -> None:
        self.icon.run(self._setup)


def main() -> None:
    if already_running():
        return
    TrayApp().run()


if __name__ == "__main__":
    main()
