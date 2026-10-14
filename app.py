"""Mujhe Pata Hai — minimal menu bar app (on/off switch, voice picker) and a floating buddy.

Run: python app.py          (use --on to start switched on)
"""

from __future__ import annotations

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
    NSColor,
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
from brain import State
from buddy import Buddy
from config import PERSONAS
from engine import Engine
from sarvam_client import SarvamClient, SarvamError

APP_NAME = "Mujhe Pata Hai"
PREFS_PATH = Path.home() / "Library" / "Application Support" / "MujhePataHai" / "prefs.json"
DEFAULT_PREFS: dict[str, Any] = {
    "persona": "mummy", "mode": "demo", "volume": 1.0, "screen": True, "show_buddy": True,
    "position": None, "enabled": False,
}
STATE_SYMBOLS = {
    State.WORKING: "eye", State.IDLE: "eye.trianglebadge.exclamationmark", State.NAGGING: "exclamationmark.bubble.fill",
    State.LISTENING: "mic.fill", State.RESPONDING: "ellipsis.bubble", State.SNOOZED: "hourglass",
}
MENU_WIDTH = 270


# ------------------------------------------------------------------ prefs / key
def load_prefs() -> dict[str, Any]:
    try:
        prefs = {**DEFAULT_PREFS, **json.loads(PREFS_PATH.read_text())}
        if not isinstance(prefs["volume"], (int, float)):
            prefs["volume"] = 1.0
        return prefs
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


def symbol(name: str) -> Optional[NSImage]:
    img = NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    if img is not None:
        img.setTemplate_(True)
    return img






def label(text: str, frame, size: float = 13.5, bold: bool = False, grey: bool = False) -> NSTextField:
    field = NSTextField.labelWithString_(text)
    field.setFrame_(frame)
    field.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    if grey:
        field.setTextColor_(NSColor.secondaryLabelColor())
    return field


# ------------------------------------------------------------------ app
class MenuBarApp:
    def __init__(self) -> None:
        self.prefs = load_prefs()
        self.client: Optional[SarvamClient] = None
        self.engine: Optional[Engine] = None
        self.buddy: Optional[Buddy] = None
        self.busy = False
        self.preview_text = ""
        self.error = ""
        self._actions: list[_Action] = []  # keep ObjC targets alive

        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.status_item.button().setImage_(symbol("eye.slash"))
        self.status_item.button().setToolTip_(APP_NAME)
        self.menu = NSMenu.alloc().init()
        self.menu.setAutoenablesItems_(False)
        self._build_menu()
        self.status_item.setMenu_(self.menu)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1, self._target(self.tick), "fire:", None, True
        )

    # ---------------------------------------------------------------- menu
    def _target(self, cb: Callable[[Any], None]) -> _Action:
        action = _Action.alloc().initWithCallback_(cb)
        self._actions.append(action)
        return action

    def _item(self, title: str, cb: Optional[Callable[[Any], None]] = None, key: str = "") -> NSMenuItem:
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "fire:" if cb else None, key)
        if cb:
            item.setTarget_(self._target(cb))
        return item

    def _view_item(self, view: NSView) -> NSMenuItem:
        item = NSMenuItem.alloc().init()
        item.setView_(view)
        return item

    def _build_menu(self) -> None:
        """Minimal: name + switch, Voice ›, Quit. Everything else uses sensible defaults."""
        m = self.menu
        head = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, MENU_WIDTH, 36))
        head.addSubview_(label(APP_NAME, NSMakeRect(16, 8, 160, 20), size=13.5, bold=True))
        self.switch = NSSwitch.alloc().initWithFrame_(NSMakeRect(MENU_WIDTH - 58, 6, 42, 24))
        self.switch.setTarget_(self._target(self.on_switch))
        self.switch.setAction_("fire:")
        head.addSubview_(self.switch)
        m.addItem_(self._view_item(head))
        m.addItem_(NSMenuItem.separatorItem())

        self.character_item = self._item("Voice")
        sub = NSMenu.alloc().init()
        sub.setAutoenablesItems_(False)
        self.char_items: dict[str, NSMenuItem] = {}
        for key, p in PERSONAS.items():
            item = self._item(p.title, lambda _s, k=key: self.on_pick_character(k))
            self.char_items[key] = item
            sub.addItem_(item)
        self.character_item.setSubmenu_(sub)
        m.addItem_(self.character_item)
        m.addItem_(NSMenuItem.separatorItem())
        m.addItem_(self._item("Quit", lambda _s: self.on_quit(), key="q"))
        self._refresh()

    def _refresh(self) -> None:
        for key, item in self.char_items.items():
            item.setState_(int(key == self.prefs["persona"]))

    def _save(self) -> None:
        save_prefs(self.prefs)
        self._refresh()

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

    def _ensure_buddy(self) -> Buddy:
        if self.buddy is None:
            self.buddy = Buddy(self.prefs.get("position"), self._on_buddy_moved)
        return self.buddy

    def _on_buddy_moved(self, x: float, y: float) -> None:
        self.prefs["position"] = [x, y]
        save_prefs(self.prefs)

    def _in_background(self, fn: Callable[..., None], *args: Any) -> None:
        def run() -> None:
            self.busy = True
            self.error = ""
            try:
                fn(*args)
            except SarvamError as err:
                self.error = f"Sarvam: {str(err)[:60]}"
            except Exception as err:  # never let a background error kill the menu bar app
                self.error = str(err)[:70]
            finally:
                self.busy = False
                self.preview_text = ""

        threading.Thread(target=run, daemon=True).start()

    def _start_engine(self) -> None:
        p = PERSONAS[self.prefs["persona"]]
        self.preview_text = p.intro
        self.engine.start(p.key, self.prefs["mode"], screen=self.prefs["screen"], volume=self.prefs["volume"], log=lambda _m: None)
        self.engine.preview(p.key, self.prefs["volume"])

    def turn_on(self) -> None:
        if self.busy or self.running or not self._ensure_client():
            self.switch.setState_(int(self.running))
            return
        self.prefs["enabled"] = True
        save_prefs(self.prefs)
        if self.prefs["show_buddy"]:
            self._ensure_buddy().show()
        self._in_background(self._start_engine)

    def turn_off(self) -> None:
        self.prefs["enabled"] = False
        save_prefs(self.prefs)
        if self.engine:
            self.engine.stop()
        if self.buddy:
            self.buddy.hide()

    def _restart_if_running(self) -> None:
        if self.running and not self.busy:
            self._in_background(self._start_engine)

    # ---------------------------------------------------------------- actions
    def on_switch(self, sender) -> None:
        if sender.state():
            self.turn_on()
        else:
            self.turn_off()

    def on_pick_character(self, key: str) -> None:
        self.prefs["persona"] = key
        self._save()
        if self.running:
            self._restart_if_running()
        else:
            self.on_preview()

    def on_preview(self) -> None:
        if self.busy or not self._ensure_client():
            return
        p = PERSONAS[self.prefs["persona"]]
        self.preview_text = p.intro
        if self.prefs["show_buddy"]:
            self._ensure_buddy().show()
        self._in_background(self.engine.preview, p.key, self.prefs["volume"])

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

    def on_quit(self) -> None:
        if self.engine:
            self.engine.stop()
        if self.client:
            self.client.close()
        NSApplication.sharedApplication().terminate_(None)

    # ---------------------------------------------------------------- main-thread tick
    def tick(self, _timer) -> None:
        p = PERSONAS[self.prefs["persona"]]
        st = self.engine.status if self.engine else None
        button = self.status_item.button()
        if self.busy and not self.running:
            button.setImage_(symbol("hourglass"))
            if self.buddy and self.buddy.visible:
                self.buddy.push_sleeping(p.key, self.preview_text)
            return
        if self.running and st:
            button.setImage_(symbol(STATE_SYMBOLS.get(st.state, "eye")))
            self.switch.setState_(1)
            if self.buddy and self.buddy.visible:
                if self.preview_text and not st.last_bot:
                    st.last_bot = self.preview_text
                self.buddy.push(st)
            return
        button.setImage_(symbol("eye.slash"))
        self.switch.setState_(0)
        if self.buddy and self.buddy.visible and not self.busy:
            self.buddy.hide()


def main() -> None:
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # menu bar only, no Dock icon
    menubar = MenuBarApp()
    if "--on" in sys.argv or menubar.prefs.get("enabled"):
        AppHelper.callLater(0.5, menubar.turn_on)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
