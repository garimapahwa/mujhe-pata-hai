"""Mujhe Pata Hai — menu bar app: an eye icon whose menu is just an on/off switch.

Run: python app.py          (use --on to start switched on)
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional

import objc
from AppKit import (
    NSAlert,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSFont,
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSSwitch,
    NSTextField,
    NSVariableStatusItemLength,
    NSView,
)
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper

import config
from engine import Engine
from sarvam_client import SarvamClient, SarvamError

APP_NAME = "Mujhe Pata Hai"
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "MujhePataHai"
PREFS_PATH = SUPPORT_DIR / "prefs.json"
DEFAULT_PREFS: dict[str, Any] = {"persona": "mummy", "mode": "demo", "volume": 1.0, "screen": True, "enabled": False}
MENU_WIDTH = 240


# ------------------------------------------------------------------ prefs / key
def load_prefs() -> dict[str, Any]:
    try:
        return {**DEFAULT_PREFS, **json.loads(PREFS_PATH.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULT_PREFS)


def save_prefs(prefs: dict[str, Any]) -> None:
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, indent=2))


def save_api_key(key: str) -> None:
    env = config.ROOT / ".env"
    lines = env.read_text().splitlines() if env.exists() else []
    lines = [l for l in lines if not l.startswith("SARVAM_API_KEY=")] + [f"SARVAM_API_KEY={key}"]
    env.write_text("\n".join(lines) + "\n")
    os.environ["SARVAM_API_KEY"] = key


# ------------------------------------------------------------------ AppKit helpers
class _Action(NSObject):
    """Bridges an AppKit target/action to a Python callable."""

    def initWithCallback_(self, cb):  # noqa: N802
        self = objc.super(_Action, self).init()
        if self is None:
            return None
        self.cb = cb
        return self

    def fire_(self, sender):  # noqa: N802
        self.cb(sender)


def eye_icon() -> NSImage:
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_("eye", APP_NAME)
    img.setTemplate_(True)  # monochrome, matches the other menu bar icons
    return img


# ------------------------------------------------------------------ app
class MenuBarApp:
    def __init__(self) -> None:
        self.prefs = load_prefs()
        self.client: Optional[SarvamClient] = None
        self.engine: Optional[Engine] = None
        self.busy = False
        self._actions: list[_Action] = []  # keep ObjC targets alive

        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.status_item.setAutosaveName_("MujhePataHai")
        self.status_item.button().setImage_(eye_icon())
        self.status_item.button().setToolTip_(APP_NAME)
        self.status_item.setMenu_(self._build_menu())
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.25, self._target(self.tick), "fire:", None, True
        )

    def _target(self, cb: Callable[[Any], None]) -> _Action:
        action = _Action.alloc().initWithCallback_(cb)
        self._actions.append(action)
        return action

    def _build_menu(self) -> NSMenu:
        """The whole menu: the app's name and a switch."""
        head = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, MENU_WIDTH, 40))
        name = NSTextField.labelWithString_(APP_NAME)
        name.setFrame_(NSMakeRect(16, 10, 160, 20))
        name.setFont_(NSFont.boldSystemFontOfSize_(13.5))
        head.addSubview_(name)
        self.switch = NSSwitch.alloc().initWithFrame_(NSMakeRect(MENU_WIDTH - 58, 8, 42, 24))
        self.switch.setTarget_(self._target(self.on_switch))
        self.switch.setAction_("fire:")
        head.addSubview_(self.switch)
        item = NSMenuItem.alloc().init()
        item.setView_(head)
        menu = NSMenu.alloc().init()
        menu.addItem_(item)
        return menu

    # ---------------------------------------------------------------- engine plumbing
    @property
    def running(self) -> bool:
        return bool(self.engine and self.engine.running)

    def _ensure_client(self) -> bool:
        if self.client:
            return True
        try:
            self.client = SarvamClient()
            self.engine = Engine(self.client)
            return True
        except SarvamError:
            return self.ask_api_key()

    def _start_engine(self) -> None:
        try:
            p = self.prefs["persona"]
            self.engine.start(p, self.prefs["mode"], screen=self.prefs["screen"], volume=self.prefs["volume"], log=lambda _m: None)
            self.engine.preview(p, self.prefs["volume"])  # she says hello, so you know it's on
        except Exception:  # never let a background error kill the menu bar app
            pass
        finally:
            self.busy = False

    def turn_on(self) -> None:
        if self.busy or self.running or not self._ensure_client():
            self.switch.setState_(int(self.running))
            return
        self.prefs["enabled"] = True
        save_prefs(self.prefs)
        self.busy = True
        threading.Thread(target=self._start_engine, daemon=True).start()

    def turn_off(self) -> None:
        self.prefs["enabled"] = False
        save_prefs(self.prefs)
        if self.engine:
            self.engine.stop()

    def on_switch(self, sender) -> None:
        if sender.state():
            self.turn_on()
        else:
            self.turn_off()

    def ask_api_key(self) -> bool:
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Sarvam AI API key")
        alert.setInformativeText_("Paste your key from dashboard.sarvam.ai. It's saved only on this Mac.")
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        field.setPlaceholderString_("sk_...")
        alert.setAccessoryView_(field)
        alert.window().setInitialFirstResponder_(field)
        if alert.runModal() != 1000:  # NSAlertFirstButtonReturn
            return False
        key = str(field.stringValue()).strip()
        if not key:
            return False
        save_api_key(key)
        try:
            self.client = SarvamClient(key)
            self.engine = Engine(self.client)
            return True
        except SarvamError:
            return False

    # ---------------------------------------------------------------- main-thread tick
    def tick(self, _timer) -> None:
        on = self.running or self.busy
        self.switch.setState_(int(on))
        self.status_item.button().setAlphaValue_(1.0 if on else 0.45)  # dimmed eye when off


def already_running() -> bool:
    """Single instance: hold an exclusive lock for the app's lifetime."""
    global _LOCK
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    _LOCK = open(SUPPORT_DIR / "app.lock", "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


def main() -> None:
    if already_running():
        return
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # menu bar only, no Dock icon
    menubar = MenuBarApp()
    if "--on" in sys.argv or menubar.prefs.get("enabled"):
        AppHelper.callLater(0.5, menubar.turn_on)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
