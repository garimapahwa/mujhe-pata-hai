"""What's on screen — frontmost app + active browser tab title/domain. Text only, no screenshots.

Frontmost app comes from `lsappinfo` (no permission). Browser tabs are read via AppleScript, only for
browsers that are already running (so we never launch one). If the focused app isn't a browser we still
check open, non-minimized Chrome/Safari windows — Netflix on a second monitor counts.
macOS asks once for Automation access.
"""

from __future__ import annotations

import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

_DISTRACTION_SITES = {
    "netflix.com": "Netflix", "youtube.com": "YouTube", "youtu.be": "YouTube", "instagram.com": "Instagram",
    "hotstar.com": "Hotstar", "primevideo.com": "Prime Video", "jiocinema.com": "JioCinema",
    "twitter.com": "Twitter", "x.com": "X", "reddit.com": "Reddit", "facebook.com": "Facebook",
    "web.whatsapp.com": "WhatsApp", "snapchat.com": "Snapchat", "tiktok.com": "TikTok",
    "amazon.in": "Amazon shopping", "myntra.com": "Myntra", "flipkart.com": "Flipkart", "swiggy.com": "Swiggy",
    "zomato.com": "Zomato", "spotify.com": "Spotify", "linkedin.com": "LinkedIn",
}
_DISTRACTION_APPS = {"WhatsApp", "Spotify", "Music", "TV", "Netflix", "Telegram", "Discord", "Messages", "Photos"}
_STUDY_RE = re.compile(
    r"lecture|tutorial|course|class \d|lesson|explained|crash course|DSA|leetcode|interview prep|"
    r"python|javascript|machine learning|maths?|physics|chemistry|NPTEL|MIT|Khan Academy|पढ़ाई",
    re.I,
)
_BROWSERS = {"com.google.Chrome": "Google Chrome", "com.apple.Safari": "Safari"}

_SCRIPTS = {
    "com.google.Chrome": (
        'tell application "Google Chrome"\n'
        "  set ws to (every window whose minimized is false)\n"
        "  if (count of ws) > 0 then\n"
        "    set t to active tab of (item 1 of ws)\n"
        '    return (title of t) & "\\n" & (URL of t)\n'
        "  end if\n"
        "end tell"
    ),
    "com.apple.Safari": (
        'tell application "Safari"\n'
        "  set ws to (every window whose miniaturized is false)\n"
        "  if (count of ws) > 0 then\n"
        "    set t to current tab of (item 1 of ws)\n"
        '    return (name of t) & "\\n" & (URL of t)\n'
        "  end if\n"
        "end tell"
    ),
}


@dataclass(frozen=True)
class ScreenContext:
    app: str
    title: str = ""
    domain: str = ""
    background: bool = False  # browser open but not the focused app (e.g. on the second monitor)

    @property
    def distraction(self) -> Optional[str]:
        """Name of the distraction on screen (e.g. 'YouTube'), or None."""
        for site, name in _DISTRACTION_SITES.items():
            if self.domain == site or self.domain.endswith("." + site):
                if name == "YouTube" and _STUDY_RE.search(self.title):
                    return None  # a lecture on YouTube is fair
                return name
        return self.app if self.app in _DISTRACTION_APPS else None

    def short(self, limit: int = 60) -> str:
        title = self.title if len(self.title) <= limit else self.title[: limit - 1] + "…"
        where = self.domain or self.app
        text = f"{where} — {title}" if title else where
        return f"{text} (other window/screen)" if self.background else text

    def for_llm(self) -> str:
        if not self.app:
            return "unknown"
        parts = [f"app: {self.app}"]
        if self.domain:
            parts.append(f"site: {self.domain}")
        if self.title:
            parts.append(f'tab title: "{self.title[:120]}"')
        if self.background:
            parts.append("open in a browser window on screen (maybe her second monitor), not the focused app")
        return ", ".join(parts)


def _run(args: list[str], timeout: float = 1.5) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _front_app() -> tuple[str, str]:
    asn = _run(["lsappinfo", "front"])
    if not asn:
        return "", ""
    info = _run(["lsappinfo", "info", "-only", "name", "-only", "bundleid", asn])
    name = re.search(r'"(?:LSDisplayName|name)"="([^"]*)"', info)
    bundle = re.search(r'"CFBundleIdentifier"="([^"]*)"', info)
    return (name.group(1) if name else ""), (bundle.group(1) if bundle else "")


def _is_running(bundle: str) -> bool:
    return bool(_run(["lsappinfo", "find", f"bundleid={bundle}"]))


def _browser_tab(bundle: str, background: bool) -> ScreenContext:
    out = _run(["osascript", "-e", _SCRIPTS[bundle]])
    title, _, url = out.partition("\n")
    domain = (urlparse(url).hostname or "").removeprefix("www.").removeprefix("m.")
    return ScreenContext(app=_BROWSERS[bundle], title=title.strip(), domain=domain, background=background)


def get_screen_context() -> ScreenContext:
    app, bundle = _front_app()
    if bundle in _BROWSERS:
        return _browser_tab(bundle, background=False)
    front = ScreenContext(app=app)
    if front.distraction:
        return front
    # Focused app looks innocent — but is Netflix playing in a browser on the other screen?
    for other in _BROWSERS:
        if _is_running(other):
            tab = _browser_tab(other, background=True)
            if tab.distraction:
                return tab
    return front


class ScreenWatcher(threading.Thread):
    """Background poller so screen-based decisions never block audio or the state machine."""

    def __init__(self, interval: float = 1.0) -> None:
        super().__init__(name="screen-watcher", daemon=True)
        self.interval = interval
        self.latest = ScreenContext(app="")
        self._distracted_since: Optional[float] = None
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            ctx = get_screen_context()
            if self.focused_distraction(ctx):
                if self._distracted_since is None:
                    self._distracted_since = time.monotonic()
            else:
                self._distracted_since = None
            self.latest = ctx
            self._stop.wait(self.interval)

    @staticmethod
    def focused_distraction(ctx: ScreenContext) -> bool:
        """A distraction in the focused window — actively watching/scrolling, not just a tab on the side."""
        return bool(ctx.distraction) and not ctx.background

    @property
    def distracted_for(self) -> float:
        return 0.0 if self._distracted_since is None else time.monotonic() - self._distracted_since

    def restart_timer(self) -> None:
        if self._distracted_since is not None:
            self._distracted_since = time.monotonic()

    def stop(self) -> None:
        self._stop.set()


if __name__ == "__main__":
    print("Switch between apps/tabs — a new line prints whenever it changes. Ctrl+C to quit.")
    last = ""
    try:
        while True:
            ctx = get_screen_context()
            line = ctx.short() + (f"   🚨 {ctx.distraction}" if ctx.distraction else "")
            if line != last:
                print(f"{time.strftime('%H:%M:%S')}  {line}", flush=True)
                last = line
            time.sleep(1)
    except KeyboardInterrupt:
        print()
