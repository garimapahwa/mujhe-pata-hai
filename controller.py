"""The menu bar app's non-UI side: settings, the API key, and the engine's on/off, voice and
idle-time controls."""

from __future__ import annotations

import fcntl
import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Optional

import config
from config import PERSONAS
from engine import Engine
from sarvam_client import SarvamClient, SarvamError

APP_NAME = "Side Eye"
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "SideEye"
PREFS_PATH = SUPPORT_DIR / "prefs.json"
DEFAULT_PREFS: dict[str, Any] = {"persona": "mummy", "idle": 8, "volume": 1.0, "screen": True, "enabled": False}
VOICE_GROUPS = {
    "Family": ["mummy", "papa", "dadi", "didi"],
    "Friends & Work": ["dost", "teacher", "boss"],
    "Filmy": ["angry", "romantic", "bhai", "villain", "detective", "news", "commentator"],
}
IDLE_CHOICES = {8: "8 seconds", 30: "30 seconds", 60: "1 minute", 120: "2 minutes", 300: "5 minutes",
                600: "10 minutes", 900: "15 minutes", 1800: "30 minutes"}


# ------------------------------------------------------------------ prefs / key
def load_prefs() -> dict[str, Any]:
    try:
        prefs = {**DEFAULT_PREFS, **json.loads(PREFS_PATH.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULT_PREFS)
    if prefs["persona"] not in PERSONAS:  # a voice that has since been removed
        prefs["persona"] = DEFAULT_PREFS["persona"]
    return prefs


def save_prefs(prefs: dict[str, Any]) -> None:
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(json.dumps(prefs, indent=2))


def save_api_key(key: str) -> None:
    env = config.ROOT / ".env"
    lines = env.read_text().splitlines() if env.exists() else []
    lines = [l for l in lines if not l.startswith("SARVAM_API_KEY=")] + [f"SARVAM_API_KEY={key}"]
    env.write_text("\n".join(lines) + "\n")
    os.environ["SARVAM_API_KEY"] = key


_LOCK = None


def already_running() -> bool:
    """Single instance: hold an exclusive lock on a file for the app's lifetime."""
    global _LOCK
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    _LOCK = open(SUPPORT_DIR / "app.lock", "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        return True


# ------------------------------------------------------------------ engine controls
class Controller:
    """Turns the buddy on/off and applies voice / idle-time picks. Slow work runs on background threads;
    `busy` is True while one is in flight. `ask_key` shows the "paste your API key" prompt."""

    def __init__(self, ask_key: Callable[[], Optional[str]]) -> None:
        self.prefs = load_prefs()
        self.client: Optional[SarvamClient] = None
        self.engine: Optional[Engine] = None
        self.busy = False
        self._ask_key = ask_key

    @property
    def running(self) -> bool:
        return bool(self.engine and self.engine.running)

    @property
    def on(self) -> bool:
        """What the switch should show: running, or starting up."""
        return self.running or (self.busy and bool(self.prefs.get("enabled")))

    def _save(self) -> None:
        save_prefs(self.prefs)

    def ensure_client(self) -> bool:
        if self.client:
            return True
        try:
            self.client = SarvamClient()
        except SarvamError:
            key = (self._ask_key() or "").strip()
            if not key:
                return False
            save_api_key(key)
            try:
                self.client = SarvamClient(key)
            except SarvamError:
                return False
        self.engine = Engine(self.client)
        return True

    def _run(self, fn: Callable[..., None], *args: Any) -> None:
        self.busy = True

        def work() -> None:
            try:
                fn(*args)
            except Exception:  # never let a background error kill the app
                pass
            finally:
                self.busy = False

        threading.Thread(target=work, daemon=True).start()

    def _start_engine(self, hello: bool = True) -> None:
        p, idle = self.prefs["persona"], float(self.prefs["idle"])
        mode = "demo" if idle < 60 else "real"  # short waits get the snappy demo timers for everything else too
        self.engine.start(p, mode, screen=self.prefs["screen"], volume=self.prefs["volume"], log=lambda _m: None, idle=idle)
        if hello:
            self.engine.preview(p, self.prefs["volume"])  # she says hello, so you know it's on

    def turn_on(self) -> bool:
        if self.busy or self.running or not self.ensure_client():
            return self.running
        self.prefs["enabled"] = True
        self._save()
        self._run(self._start_engine)
        return True

    def turn_off(self) -> None:
        self.prefs["enabled"] = False
        self._save()
        if self.engine:
            self.engine.stop()

    def pick_voice(self, key: str) -> None:
        self.prefs["persona"] = key
        self._save()
        if self.busy or not self.ensure_client():
            return
        if self.running:
            self._run(self._start_engine)  # restart with the new voice
        else:
            self._run(self.engine.preview, key, self.prefs["volume"])

    def pick_idle(self, secs: int) -> None:
        self.prefs["idle"] = secs
        self._save()
        if self.running and not self.busy:
            self._run(self._start_engine, False)  # restart quietly

    def stop(self) -> None:
        if self.engine:
            self.engine.stop()
