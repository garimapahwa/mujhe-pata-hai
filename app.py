"""Mujhe Pata Hai — menu bar app (native AppKit menu with a toggle switch + volume slider) and floating buddy.

Run: python app.py          (use --on to start switched on)
"""

from __future__ import annotations

import json
import os
import plistlib
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional

import objc
from AppKit import (
    NSAlert,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSImage,
    NSImageView,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSSlider,
    NSStatusBar,
    NSSwitch,
    NSTextField,
    NSVariableStatusItemLength,
    NSView,
)
from Foundation import NSAttributedString, NSObject, NSTimer
from PyObjCTools import AppHelper

import config
from brain import State
from buddy import Buddy
from config import PERSONAS
from engine import Engine
from sarvam_client import SarvamClient, SarvamError

APP_NAME = "Mujhe Pata Hai"
REPO_URL = "https://github.com/garimapahwa/mujhe-pata-hai"
PREFS_PATH = Path.home() / "Library" / "Application Support" / "MujhePataHai" / "prefs.json"
LOGIN_AGENT = Path.home() / "Library" / "LaunchAgents" / "com.mujhepatahai.agent.plist"
DEFAULT_PREFS: dict[str, Any] = {
    "persona": "mummy", "mode": "demo", "volume": 1.0, "screen": True, "show_buddy": True,
    "position": None, "enabled": False,
}
GROUPS = {"घर · Home": ["mummy"], "यार · Friends": ["dost"], "Filmy": ["filmy", "action", "commentator"]}
STATE_SYMBOLS = {
    State.WORKING: "eye", State.IDLE: "eye.trianglebadge.exclamationmark", State.NAGGING: "exclamationmark.bubble.fill",
    State.LISTENING: "mic.fill", State.RESPONDING: "ellipsis.bubble", State.SNOOZED: "hourglass",
}
MENU_WIDTH = 270


# ------------------------------------------------------------------ prefs / key / login item
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


def launch_at_login_enabled() -> bool:
    return LOGIN_AGENT.exists()


def set_launch_at_login(on: bool) -> None:
    if not on:
        LOGIN_AGENT.unlink(missing_ok=True)
        return
    LOGIN_AGENT.parent.mkdir(parents=True, exist_ok=True)
    bundle = Path(os.environ.get("MPH_APP_BUNDLE", ""))
    args = ["/usr/bin/open", "-a", str(bundle)] if bundle.suffix == ".app" else [sys.executable, str(config.ROOT / "app.py")]
    LOGIN_AGENT.write_bytes(plistlib.dumps({"Label": "com.mujhepatahai.agent", "ProgramArguments": args, "RunAtLoad": True}))


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


def grey_title(text: str) -> NSAttributedString:
    attrs = {NSFontAttributeName: NSFont.systemFontOfSize_weight_(11.5, 0.3), NSForegroundColorAttributeName: NSColor.secondaryLabelColor()}
    return NSAttributedString.alloc().initWithString_attributes_(text, attrs)


def header_item(title: str) -> NSMenuItem:
    item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
    item.setAttributedTitle_(grey_title(title))
    item.setEnabled_(False)
    return item


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
        m = self.menu

        # header: name + switch (like Rustyvibes)
        head = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, MENU_WIDTH, 52))
        head.addSubview_(label(APP_NAME, NSMakeRect(16, 24, 180, 20), size=14, bold=True))
        self.status_label = label("Off", NSMakeRect(16, 6, 200, 16), size=11, grey=True)
        head.addSubview_(self.status_label)
        self.switch = NSSwitch.alloc().initWithFrame_(NSMakeRect(MENU_WIDTH - 58, 14, 42, 24))
        self.switch.setTarget_(self._target(self.on_switch))
        self.switch.setAction_("fire:")
        head.addSubview_(self.switch)
        m.addItem_(self._view_item(head))
        m.addItem_(NSMenuItem.separatorItem())

        # character (like "Soundpack")
        m.addItem_(header_item("Character"))
        self.character_item = self._item("")
        sub = NSMenu.alloc().init()
        sub.setAutoenablesItems_(False)
        self.char_items: dict[str, NSMenuItem] = {}
        for group, keys in GROUPS.items():
            sub.addItem_(header_item(group))
            for key in keys:
                p = PERSONAS[key]
                item = self._item(f"{p.emoji}  {p.title}", lambda _s, k=key: self.on_pick_character(k))
                item.setToolTip_(p.tagline)
                self.char_items[key] = item
                sub.addItem_(item)
            sub.addItem_(NSMenuItem.separatorItem())
        sub.addItem_(self._item("🔊  Hear this character", lambda _s: self.on_preview()))
        self.character_item.setSubmenu_(sub)
        m.addItem_(self.character_item)
        m.addItem_(NSMenuItem.separatorItem())

        # volume slider
        m.addItem_(header_item("Volume"))
        vol = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, MENU_WIDTH, 30))
        lo = NSImageView.imageViewWithImage_(symbol("speaker.fill"))
        hi = NSImageView.imageViewWithImage_(symbol("speaker.wave.3.fill"))
        lo.setFrame_(NSMakeRect(16, 6, 16, 18))
        hi.setFrame_(NSMakeRect(MENU_WIDTH - 40, 6, 24, 18))
        self.slider = NSSlider.sliderWithValue_minValue_maxValue_target_action_(
            self.prefs["volume"], 0.3, 1.6, self._target(self.on_volume), "fire:"
        )
        self.slider.setContinuous_(False)  # apply on release
        self.slider.setFrame_(NSMakeRect(38, 5, MENU_WIDTH - 84, 20))
        for v in (lo, hi, self.slider):
            vol.addSubview_(v)
        m.addItem_(self._view_item(vol))
        m.addItem_(NSMenuItem.separatorItem())

        # options with checkmarks
        self.demo_item = self._item("Demo Mode (catches you in 8 s)", self.on_toggle_demo)
        self.buddy_item = self._item("Show Buddy on Screen", self.on_toggle_buddy)
        self.screen_item = self._item("Check My Screen (YouTube, Netflix…)", self.on_toggle_screen)
        self.login_item = self._item("Launch at Login", self.on_toggle_login)
        for item in (self.demo_item, self.buddy_item, self.screen_item, self.login_item):
            m.addItem_(item)
        m.addItem_(NSMenuItem.separatorItem())

        self.tally_item = header_item("Caught 0 · Lies 0 · Excuses 0 · Confessions 0")
        m.addItem_(self.tally_item)
        m.addItem_(NSMenuItem.separatorItem())

        key_item = self._item("Set Sarvam API Key…", lambda _s: self.ask_api_key())
        key_item.setImage_(symbol("key"))
        about = self._item(f"About {APP_NAME}", lambda _s: self.on_about())
        about.setImage_(symbol("info.circle"))
        quit_item = self._item(f"Quit {APP_NAME}", lambda _s: self.on_quit(), key="q")
        quit_item.setImage_(symbol("xmark.square"))
        for item in (key_item, about, quit_item):
            m.addItem_(item)
        self._refresh()

    def _refresh(self) -> None:
        p = PERSONAS[self.prefs["persona"]]
        self.character_item.setTitle_(f"{p.emoji}  {p.title}")
        for key, item in self.char_items.items():
            item.setState_(int(key == self.prefs["persona"]))
        self.demo_item.setState_(int(self.prefs["mode"] == "demo"))
        self.buddy_item.setState_(int(self.prefs["show_buddy"]))
        self.screen_item.setState_(int(self.prefs["screen"]))
        self.login_item.setState_(int(launch_at_login_enabled()))

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

    def on_volume(self, sender) -> None:
        self.prefs["volume"] = round(float(sender.doubleValue()), 1)  # 0.1 steps keep the TTS cache small
        save_prefs(self.prefs)
        if self.engine:
            self.engine.set_volume(self.prefs["volume"])

    def on_toggle_demo(self, _sender) -> None:
        self.prefs["mode"] = "real" if self.prefs["mode"] == "demo" else "demo"
        self._save()
        self._restart_if_running()

    def on_toggle_buddy(self, _sender) -> None:
        self.prefs["show_buddy"] = not self.prefs["show_buddy"]
        self._save()
        if self.prefs["show_buddy"] and (self.running or self.busy):
            self._ensure_buddy().show()
        elif self.buddy:
            self.buddy.hide()

    def on_toggle_screen(self, _sender) -> None:
        self.prefs["screen"] = not self.prefs["screen"]
        self._save()
        self._restart_if_running()

    def on_toggle_login(self, _sender) -> None:
        set_launch_at_login(not launch_at_login_enabled())
        self._refresh()

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

    def on_about(self) -> None:
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(f"{APP_NAME} · मुझे पता है")
        alert.setInformativeText_(
            "A Hinglish voice focus buddy that catches you slacking, listens to your excuses and talks back.\n\n"
            "Voice: Sarvam Bulbul v4 Flash · Ears: Saaras v4 · Brain: Sarvam-105B"
        )
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("View on GitHub")
        if alert.runModal() == 1001:
            webbrowser.open(REPO_URL)

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
            self.status_label.setStringValue_(f"Warming up {p.title}'s voice…")
            if self.buddy and self.buddy.visible:
                self.buddy.push_sleeping(p.key, self.preview_text)
            return
        if self.running and st:
            button.setImage_(symbol(STATE_SYMBOLS.get(st.state, "eye")))
            self.switch.setState_(1)
            self.status_label.setStringValue_(f"{p.emoji} {p.title} is watching · {st.state.value.title()}")
            self.tally_item.setAttributedTitle_(grey_title(
                f"Caught {st.caught} · Lies {st.lies} · Excuses {st.excuses} · Confessions {st.confessions}"
            ))
            if self.buddy and self.buddy.visible:
                if self.preview_text and not st.last_bot:
                    st.last_bot = self.preview_text
                self.buddy.push(st)
            return
        button.setImage_(symbol("eye.slash"))
        self.switch.setState_(0)
        self.status_label.setStringValue_(self.error or "Off · flip the switch to start")
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
