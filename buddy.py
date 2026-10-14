"""The floating on-screen buddy: a transparent, always-on-top, draggable panel rendering buddy.html."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

import objc
from AppKit import (
    NSBackingStoreBuffered,
    NSColor,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSURL, NSObject
from WebKit import WKUserContentController, WKWebView, WKWebViewConfiguration

from brain import State, Status

HTML = Path(__file__).with_name("buddy.html")
WIDTH, HEIGHT = 240, 260
_FLOATING_LEVEL = 3  # NSFloatingWindowLevel

WKScriptMessageHandler = objc.protocolNamed("WKScriptMessageHandler")


class _DragHandler(NSObject, protocols=[WKScriptMessageHandler]):
    """Receives {dx, dy} / {dropped} messages from the page and moves the window."""

    def initWithWindow_onDrop_(self, window, on_drop):  # noqa: N802 (ObjC selector)
        self = objc.super(_DragHandler, self).init()
        if self is None:
            return None
        self.window = window
        self.on_drop = on_drop
        return self

    def userContentController_didReceiveScriptMessage_(self, _controller, message):  # noqa: N802
        body = message.body()
        if body.get("dropped"):
            origin = self.window.frame().origin
            self.on_drop(origin.x, origin.y)
            return
        origin = self.window.frame().origin
        self.window.setFrameOrigin_((origin.x + float(body["dx"]), origin.y - float(body["dy"])))


class Buddy:
    """Create on the main thread; call `push(status)` from a main-thread timer."""

    def __init__(self, position: Optional[tuple[float, float]], on_move: Callable[[float, float], None]) -> None:
        x, y = position if position else self._default_position()
        style = NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel
        self.window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, WIDTH, HEIGHT), style, NSBackingStoreBuffered, False
        )
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setHasShadow_(False)
        self.window.setLevel_(_FLOATING_LEVEL)
        self.window.setHidesOnDeactivate_(False)
        self.window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )

        config = WKWebViewConfiguration.alloc().init()
        controller = WKUserContentController.alloc().init()
        self._handler = _DragHandler.alloc().initWithWindow_onDrop_(self.window, on_move)
        controller.addScriptMessageHandler_name_(self._handler, "buddy")
        config.setUserContentController_(controller)

        self.web = WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, WIDTH, HEIGHT), config)
        self.web.setValue_forKey_(False, "drawsBackground")  # transparent page background
        self.web.loadFileURL_allowingReadAccessToURL_(
            NSURL.fileURLWithPath_(str(HTML)), NSURL.fileURLWithPath_(str(HTML.parent))
        )
        self.window.setContentView_(self.web)
        self._last_lies = 0
        self._last_payload = ""

    @staticmethod
    def _default_position() -> tuple[float, float]:
        frame = NSScreen.mainScreen().visibleFrame()
        return frame.origin.x + frame.size.width - WIDTH - 24, frame.origin.y + 24

    def show(self) -> None:
        self.window.orderFrontRegardless()

    def hide(self) -> None:
        self.window.orderOut_(None)

    @property
    def visible(self) -> bool:
        return bool(self.window.isVisible())

    def push(self, st: Status) -> None:
        busted = st.lies > self._last_lies
        self._last_lies = st.lies
        countdown = max(0.0, st.countdown_until - time.monotonic()) if st.countdown_until else 0.0
        payload = {
            "persona": st.persona.key,
            "state": st.state.value,
            "level": st.level,
            "speaking": st.speaking,
            "text": st.last_bot,
            "heard": st.last_heard if st.state in (State.RESPONDING, State.SNOOZED) else "",
            "mic": round(st.mic_level, 2),
            "countdown": round(countdown, 1),
            "distraction": st.distraction,
            "idle": round(st.idle_s, 1),
            "threshold": st.timings.idle_threshold,
            "busted": busted,
        }
        js = json.dumps(payload, ensure_ascii=False)
        if js == self._last_payload and not busted:
            return
        self._last_payload = js
        self.web.evaluateJavaScript_completionHandler_(f"window.update && update({js})", None)

    def push_sleeping(self, persona_key: str, text: str = "") -> None:
        """Before the engine is up (warming / previewing a voice)."""
        payload = {"persona": persona_key, "state": "WORKING", "level": 1, "speaking": bool(text), "text": text,
                   "heard": "", "mic": 0, "countdown": 0, "distraction": "", "idle": 0, "threshold": 1, "busted": False}
        self._last_payload = ""
        self.web.evaluateJavaScript_completionHandler_(f"window.update && update({json.dumps(payload, ensure_ascii=False)})", None)
