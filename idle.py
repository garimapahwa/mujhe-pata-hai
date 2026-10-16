"""System idle time (seconds since the last keyboard/mouse event). No special permission needed.

macOS: `ioreg` HIDIdleTime.  Windows: GetLastInputInfo.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from typing import Callable

_IDLE_RE = re.compile(rb'"HIDIdleTime"\s*=\s*(\d+)')


def _mac_idle_seconds() -> float:
    try:
        out = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem", "-d", "4"],
            capture_output=True,
            timeout=2,
            check=False,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0.0
    match = _IDLE_RE.search(out)
    return int(match.group(1)) / 1e9 if match else 0.0


def _windows_idle_seconds() -> float:
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    now = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
    return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0  # both wrap every ~49 days


def get_idle_seconds() -> float:
    """Seconds since the last keyboard/mouse event. Returns 0.0 if it can't be read."""
    return _windows_idle_seconds() if sys.platform == "win32" else _mac_idle_seconds()


class IdleMonitor(threading.Thread):
    """Background poller. Keeps `idle_seconds` fresh and calls `on_poll` each tick."""

    def __init__(self, fast_interval: float = 0.25, slow_interval: float = 1.0) -> None:
        super().__init__(name="idle-monitor", daemon=True)
        self.fast_interval = fast_interval
        self.slow_interval = slow_interval
        self.fast = threading.Event()  # set when interruption needs to be snappy
        self.idle_seconds = 0.0
        self._listeners: list[Callable[[float], None]] = []
        self._stop = threading.Event()

    def subscribe(self, fn: Callable[[float], None]) -> None:
        self._listeners.append(fn)

    def run(self) -> None:
        while not self._stop.is_set():
            self.idle_seconds = get_idle_seconds()
            for fn in self._listeners:
                fn(self.idle_seconds)
            self._stop.wait(self.fast_interval if self.fast.is_set() else self.slow_interval)

    def stop(self) -> None:
        self._stop.set()


if __name__ == "__main__":
    print("Live idle time — don't touch anything. Ctrl+C to quit.")
    try:
        while True:
            print(f"\ridle: {get_idle_seconds():6.1f}s ", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print()
