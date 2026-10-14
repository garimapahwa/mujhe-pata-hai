"""Start/stop the whole pipeline (voice, idle + screen watchers, brain). Shared by the CLI and the menu bar app."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import config
from audio import play_wav_bytes
from brain import Brain, Status, Voice
from config import PERSONAS, Persona
from idle import IdleMonitor
from lines import BANKS
from screen import ScreenWatcher
from sarvam_client import SarvamClient, SarvamError

LogFn = Callable[[str], None]
VOLUMES = {"Soft": 0.6, "Normal": 1.0, "Loud": 1.4}


# ------------------------------------------------------------------ speakers
def _parts(speaker: str) -> tuple[str, str, str]:
    bits = speaker.split("_")
    return bits[0], bits[1] if len(bits) > 1 else "", "_".join(bits[2:])


def best_alternative(wanted: str, available: list[str]) -> str:
    """Same language + style first, then same language, then same voice name."""
    name, lang, style = _parts(wanted)

    def score(candidate: str) -> int:
        c_name, c_lang, c_style = _parts(candidate)
        return (
            4 * (c_lang == lang)
            + 2 * (c_style.split("_")[0] == style.split("_")[0])
            + 1 * (c_name == name)
            + 1 * (c_lang in ("hi", "enhi"))
        )

    return max(available, key=score)


def resolve_speaker(client: SarvamClient, persona: Persona, log: LogFn = print) -> str:
    available: list[str] = []
    for candidate in persona.speakers:
        available = client.check_speaker(candidate)
        if not available:
            return candidate
        log(f"speaker {candidate} rejected by Bulbul v4 Flash")
    pick = best_alternative(persona.speakers[0], available)
    log(f"auto-picked {pick} from the live speaker list")
    return pick


# ------------------------------------------------------------------ warmup
def warm_cache(voice: Voice, persona: Persona, volume: float = 1.0, log: LogFn = print) -> None:
    """Level-1 nags + 'aa gayi' lines must be instant: synthesize them before going live."""
    bank = BANKS[persona.key]
    quick = [(line, persona.prosody(1, volume)) for line in bank.nag[1] + bank.welcome_back]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for fut in [pool.submit(voice.prefetch, text, pros) for text, pros in quick]:
            try:
                fut.result()
            except SarvamError as err:
                log(f"couldn't cache a line ({err}); it will stream live")


def warm_rest_in_background(voice: Voice, persona: Persona, volume: float = 1.0) -> None:
    bank = BANKS[persona.key]
    jobs = [(l, persona.prosody(lvl, volume)) for lvl in (2, 3) for l in bank.nag[lvl]]
    jobs += [(l, persona.prosody(1, volume)) for l in bank.unclear]

    def run() -> None:
        for text, pros in jobs:
            try:
                voice.prefetch(text, pros)
            except Exception:
                pass

    threading.Thread(target=run, name="warm-rest", daemon=True).start()


# ------------------------------------------------------------------ engine
class Engine:
    """One running buddy session. `start()` is blocking-safe to call from a background thread."""

    def __init__(self, client: SarvamClient) -> None:
        self.client = client
        self.status: Optional[Status] = None
        self.brain: Optional[Brain] = None
        self._monitor: Optional[IdleMonitor] = None
        self._watcher: Optional[ScreenWatcher] = None
        self._worker: Optional[threading.Thread] = None
        self._speakers: dict[str, str] = {}
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def speaker_for(self, persona: Persona, log: LogFn = print) -> str:
        if persona.key not in self._speakers:
            self._speakers[persona.key] = resolve_speaker(self.client, persona, log)
        return self._speakers[persona.key]

    def start(self, persona_key: str, mode: str, screen: bool = True, volume: float = 1.0, log: LogFn = print) -> Status:
        with self._lock:
            self.stop()
            persona = PERSONAS[persona_key]
            status = Status(persona=persona, mode=mode, timings=config.timings_for(mode))
            status.speaker = self.speaker_for(persona, log)
            voice = Voice(self.client, status.speaker, status)
            warm_cache(voice, persona, volume, log)
            warm_rest_in_background(voice, persona, volume)

            self._monitor = IdleMonitor()
            self._watcher = ScreenWatcher() if screen else None
            self.brain = Brain(self.client, voice, status, self._monitor, self._watcher)
            self.brain.volume = volume
            t = status.timings
            status.log(
                f"ready · idle {t.idle_threshold:.0f}s · listen {t.listen_window:.0f}s · snooze "
                f"{t.snooze_duration:.0f}s · gap {t.escalation_gap:.0f}s · distraction {t.distraction_grace:.0f}s"
            )
            self._monitor.start()
            if self._watcher:
                self._watcher.start()
            self._worker = threading.Thread(target=self.brain.run, name="brain", daemon=True)
            self._worker.start()
            self.status = status
            return status

    def stop(self) -> None:
        if self.brain:
            self.brain.stop()
        if self._monitor:
            self._monitor.stop()
        if self._watcher:
            self._watcher.stop()
        if self._worker:
            self._worker.join(timeout=2)
        self.brain = self._monitor = self._watcher = self._worker = None

    def set_volume(self, volume: float) -> None:
        if self.brain:
            self.brain.volume = volume

    def preview(self, persona_key: str, volume: float = 1.0) -> None:
        """Speak the character's intro line (blocking — call from a thread)."""
        persona = PERSONAS[persona_key]
        speaker = self.speaker_for(persona)
        audio = self.client.tts_bytes(persona.intro, speaker, persona.prosody(1, volume))
        play_wav_bytes(audio, lambda: False)
