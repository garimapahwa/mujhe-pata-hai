"""State machine: WORKING → IDLE → NAGGING → LISTENING → RESPONDING → (SNOOZED | WORKING)."""

from __future__ import annotations

import hashlib
import os
import re
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterator, Optional

import config
from audio import play_wav_bytes, play_wav_stream, record_utterance
from config import LEVEL_MOODS, MAX_LEVEL, Persona, Prosody, Timings
from idle import IdleMonitor
from lines import BANKS, LineBank, excuse_topic
from screen import ScreenContext, ScreenWatcher
from sarvam_client import SarvamClient, SarvamError


class State(str, Enum):
    WORKING = "WORKING"
    IDLE = "IDLE"
    NAGGING = "NAGGING"
    LISTENING = "LISTENING"
    RESPONDING = "RESPONDING"
    SNOOZED = "SNOOZED"


class Intent(str, Enum):
    EXCUSE = "EXCUSE"
    CONFESS = "CONFESS"
    BACK_TO_WORK = "BACK_TO_WORK"
    UNCLEAR = "UNCLEAR"
    CAUGHT_LYING = "CAUGHT_LYING"
    SILENCE = "SILENCE"


@dataclass
class Status:
    """Everything the dashboard shows. Written by the brain, read by the UI."""

    persona: Persona
    mode: str
    timings: Timings
    speaker: str = ""
    state: State = State.WORKING
    idle_s: float = 0.0
    level: int = 1
    last_bot: str = ""
    last_heard: str = ""
    intent: str = ""
    intent_source: str = ""
    caught: int = 0
    excuses: int = 0
    confessions: int = 0
    comebacks: int = 0
    lies: int = 0
    screen: str = ""
    distracted_s: float = 0.0
    distraction: str = ""  # e.g. "YouTube" while one is in view
    speaking: bool = False
    mic_level: float = 0.0
    countdown_until: float = 0.0
    tts_ms: Optional[int] = None
    stt_ms: Optional[int] = None
    llm_ms: Optional[int] = None
    events: deque[str] = field(default_factory=lambda: deque(maxlen=7))

    def log(self, msg: str) -> None:
        self.events.append(f"{time.strftime('%H:%M:%S')}  {msg}")
        self.trace(msg)

    def trace(self, msg: str) -> None:
        """Opt-in text log (MPH_LOG=1) at .cache/session.log — never audio."""
        if os.getenv("MPH_LOG") != "1":
            return
        with open(config.CACHE_DIR / "session.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} [{self.state.value} L{self.level}] {msg}\n")


class Interrupted(Exception):
    """Keyboard/mouse activity resumed — the user is back."""


# ====================================================================== voice
class Voice:
    """Bulbul v4 Flash speech with an in-memory + on-disk cache and streaming fallback."""

    def __init__(self, client: SarvamClient, speaker: str, status: Status) -> None:
        self.client = client
        self.speaker = speaker
        self.status = status
        self._mem: dict[str, bytes] = {}
        self._dir = config.CACHE_DIR / "tts"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, text: str, prosody: Prosody) -> str:
        p = prosody.validated()
        raw = f"{config.TTS_MODEL}|{self.speaker}|{p.pace}|{p.pitch}|{p.loudness}|{text}"
        return hashlib.sha1(raw.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self._dir / f"{key}.wav"

    def cached(self, text: str, prosody: Prosody) -> Optional[bytes]:
        key = self._key(text, prosody)
        if key not in self._mem and self._path(key).exists():
            self._mem[key] = self._path(key).read_bytes()
        return self._mem.get(key)

    def prefetch(self, text: str, prosody: Prosody, persist: bool = True) -> None:
        if self.cached(text, prosody) is not None:
            return
        audio = self.client.tts_bytes(text, self.speaker, prosody)
        key = self._key(text, prosody)
        self._mem[key] = audio
        if persist:
            self._path(key).write_bytes(audio)

    def speak(self, text: str, prosody: Prosody, should_stop: Callable[[], bool]) -> bool:
        """Play `text`. Returns False if interrupted. Never raises on API/audio errors."""
        self.status.speaking = True
        try:
            audio = self.cached(text, prosody)
            if audio is not None:
                self.status.tts_ms = 0
                return play_wav_bytes(audio, should_stop)
            collected: list[bytes] = []
            ok = play_wav_stream(self._timed(self.client.tts_stream(text, self.speaker, prosody), collected), should_stop)
            if ok:
                self._mem[self._key(text, prosody)] = b"".join(collected)
            return ok
        except SarvamError as err:
            self.status.log(f"[red]TTS error:[/] {err}")
        except Exception as err:  # audio device hiccups must not kill the demo
            self.status.log(f"[red]audio error:[/] {err}")
        finally:
            self.status.speaking = False
        return not should_stop()

    def _timed(self, chunks: Iterator[bytes], sink: list[bytes]) -> Iterator[bytes]:
        start = time.monotonic()
        for chunk in chunks:
            if not sink:
                self.status.tts_ms = int((time.monotonic() - start) * 1000)
            sink.append(chunk)
            yield chunk


# ====================================================================== intents
_BACK_KEYS = ("back to work", "i'm back", "im back", "i am back", "back", "ab kaam", "kaam kar rahi",
              "kaam karti", "working now", "अब काम", "काम कर रही", "काम करती", "वापस", "बैक")
_CONFESS_KEYS = ("sorry", "सॉरी", "सोरी", "phone", "फोन", "फ़ोन", "chala", "चला", "reels", "रील", "instagram",
                 "scroll", "haan", "हाँ", "हां", "maaf", "माफ़", "माफ")
_EXCUSE_KEYS = ("padh", "पढ़", "पढ", "read", "रीड", "meeting", "मीटिंग", "call", "कॉल", "soch", "सोच",
                "research", "article", "book", "किताब", "think")
_WORK_KEYS = ("kaam", "काम", "work", "वर्क")
_ROMAN_HINDI = re.compile(r"\b(hai|nahi|kya|karo|chalo|beta|tum|kar|raha|rahi|abhi|bolo|haan|accha)\b", re.I)
_APOLOGY = re.compile(r"sorry|सॉरी|सोरी|maaf|माफ़|माफ", re.I)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def classify_locally(text: str) -> Intent:
    t = text.lower()
    if any(k in t for k in _BACK_KEYS):
        return Intent.BACK_TO_WORK
    if any(k in t for k in _CONFESS_KEYS):
        return Intent.CONFESS
    if any(k in t for k in _EXCUSE_KEYS):
        return Intent.EXCUSE
    if any(k in t for k in _WORK_KEYS):
        return Intent.BACK_TO_WORK
    return Intent.UNCLEAR


def looks_romanized(reply: str) -> bool:
    return not _DEVANAGARI.search(reply) and bool(_ROMAN_HINDI.search(reply))


# ====================================================================== prompts
_RULES = """You are "मुझे पता है" (Mujhe Pata Hai), a voice focus-buddy. The user is a young woman who is supposed to be working at her laptop, but she went idle and you caught her. Everything you write is spoken aloud by a Hindi text-to-speech voice.

WRITING RULES (critical, the voice breaks otherwise):
- Hinglish: Hindi words MUST be in Devanagari, English words in Latin script. Example: "आपका order confirm हो गया।" NEVER romanized Hindi like "kya kar rahi ho".
- 1–2 short sentences, at most 20 words total. Use punctuation for rhythm: commas for short pauses, । or . to end, ! for emphasis, … rarely.
- No emojis, no SSML, no quotes, no markdown, no stage directions.
- Be funny and stay in character.

YOUR CHARACTER: {tone}"""

_CLASSIFY = """Context: escalation level {level}/3 ({mood}). Excuses she has given this session: {excuses}. Excuses in a row right now: {streak}. Her previous excuse: "{last_excuse}".
What is on her laptop screen right now: {screen}.

She just said (speech-to-text, may be imperfect): "{heard}"

1) Classify her intent:
- EXCUSE: claims something legit (reading, पढ़ रही थी, meeting, call, thinking, research).
- CONFESS: admits phone/reels/distraction, or says sorry.
- BACK_TO_WORK: says she is back / working now (even if she also admits the phone).
- CAUGHT_LYING: she gives an EXCUSE (studying, reading, working, meeting) but her screen clearly shows entertainment or social media unrelated to that claim (a TV show, Netflix, Instagram, shopping). A lecture or docs on screen is NOT a lie. If she admits it or says sorry, that is CONFESS, never CAUGHT_LYING.
- UNCLEAR: gibberish, unrelated, or impossible to tell.
2) Write your spoken reply:
- EXCUSE and excuses-in-a-row is 0: calm but clearly unconvinced. Do NOT scold, order or accuse her yet. Start with "अच्छा अच्छा…" and add at most 4 words, like "अच्छा अच्छा… okay." or "अच्छा अच्छा… ठीक है बेटा।"
- EXCUSE and excuses-in-a-row is 1 or more: noticeably more sarcastic; jab at the repeated excuse.
- CONFESS: forgive warmly with a little taunt and send her back to work, like "चलो, सच तो बोला! वापस काम पे।"
- BACK_TO_WORK: short and proud, like "That's my girl! चलो।"
- CAUGHT_LYING: bust her gleefully by naming exactly what is on her screen (show name or site). Do NOT start with "अच्छा अच्छा". Like "पढ़ाई? Screen पे तो Netflix चल रहा है! मुझे सब पता है।"
- UNCLEAR: ask her to repeat, max 5 words, like "क्या? ठीक से बोलो!"

Return ONLY JSON: {{"intent": "EXCUSE|CONFESS|BACK_TO_WORK|CAUGHT_LYING|UNCLEAR", "reply": "..."}}"""

_FOLLOWUP = """Earlier she gave this excuse: "{excuse}". You let her be for a bit, but she is STILL idle. Excuses in a row: {streak}.
What is on her laptop screen right now: {screen}. If it is entertainment that contradicts her excuse, call that out by name instead.
Write ONE suspicious line as you come back, referencing her specific excuse (e.g. if she said she was reading an article: "वो article अभी तक ख़त्म नहीं हुआ? या phone चल रहा है?"). Max 18 words.
Return ONLY JSON: {{"reply": "..."}}"""

_CAUGHT = """{reason} Her screen shows: {screen}. That is clearly not work.
Write ONE opening line that calls her out by naming exactly what she is watching or scrolling (use the show/video name if the title has one, shortened). Escalation level {level}/3 ({mood}). Max 16 words. End with "मुझे पता है!" if it fits.
Return ONLY JSON: {{"reply": "..."}}"""


@dataclass
class Understanding:
    intent: Intent
    reply: str
    source: str


# ====================================================================== brain
class Brain:
    def __init__(
        self,
        client: SarvamClient,
        voice: Voice,
        status: Status,
        monitor: IdleMonitor,
        watcher: Optional[ScreenWatcher] = None,
    ) -> None:
        self.client = client
        self.voice = voice
        self.st = status
        self.persona = status.persona
        self.t = status.timings
        self.bank: LineBank = BANKS[self.persona.key]
        self.monitor = monitor
        self.shutdown = threading.Event()
        self.activity = threading.Event()
        self._interruptible = False
        self._working_since = time.monotonic()
        self._streak = 0
        self._last_excuse = ""
        self.watcher = watcher
        self.volume = 1.0  # menu: Soft 0.6 / Normal 1.0 / Loud 1.4 (Bulbul loudness multiplier)
        self._screen = ScreenContext(app="")
        self._trigger = "idle"  # what started the current episode: "idle" | "distracted"
        self._fake_seen = threading.Event()  # mouse moved but the distraction is still focused
        self._fake_called_out = False
        self._bg = ThreadPoolExecutor(max_workers=2, thread_name_prefix="brain-bg")
        monitor.subscribe(self._on_idle)

    # ---------------------------------------------------------------- idle feed
    def _on_idle(self, hid_idle: float) -> None:
        # After a voice-only return to work the HID counter keeps running, so measure from then.
        self.st.idle_s = min(hid_idle, time.monotonic() - self._working_since)
        self._look()
        self.st.distracted_s = self.watcher.distracted_for if self.watcher else 0.0
        if self._interruptible and hid_idle < config.ACTIVITY_IDLE_S:
            # Moving the mouse on YouTube is not "back to work" — only activity on a non-distraction counts.
            if self.watcher and ScreenWatcher.focused_distraction(self._screen):
                self._fake_seen.set()
            else:
                self.activity.set()

    def _stopped(self) -> bool:
        return self.shutdown.is_set() or self.activity.is_set()

    def _check(self) -> None:
        if self.shutdown.is_set():
            raise SystemExit
        if self.activity.is_set():
            raise Interrupted

    # ---------------------------------------------------------------- main loop
    def run(self) -> None:
        try:
            while not self.shutdown.is_set():
                self._work_until_idle()
                self._episode()
        except SystemExit:
            pass

    def _prosody(self, level: int) -> Prosody:
        return self.persona.prosody(level, self.volume)

    def _set(self, state: State) -> None:
        self.st.state = state

    def _work_until_idle(self) -> None:
        self._set(State.WORKING)
        self.monitor.fast.clear()
        while not self.shutdown.wait(0.2):
            if self.st.idle_s >= self.t.idle_threshold:
                self._trigger = "idle"
                return
            if self.watcher and self.watcher.distracted_for >= self.t.distraction_grace:
                self._trigger = "distracted"
                return
        raise SystemExit

    def _episode(self) -> None:
        self._interruptible = True
        self.activity.clear()
        self._fake_seen.clear()
        self._fake_called_out = False
        self.monitor.fast.set()
        self.st.caught += 1
        self._set(State.IDLE)
        if self._trigger == "distracted":
            self.st.log(f"on [bold]{self._screen.distraction}[/] for {self.t.distraction_grace:.0f}s (mouse moving ≠ work)")
        else:
            self.st.log(f"caught idle for {self.st.idle_s:.0f}s → nag L{self.st.level}")
        try:
            self._converse(self._opening_line())
        except Interrupted:
            self._welcome_back()
        finally:
            self._interruptible = False
            self._working_since = time.monotonic()
            self.activity.clear()
            if self.watcher:
                self.watcher.restart_timer()  # fresh grace period after every return to work

    def _converse(self, line: str) -> None:
        unclear_once = False
        while True:
            self._set(State.NAGGING)
            self._say(line, interruptible=True)
            heard = self._listen()
            result = self._understand(heard) if heard else Understanding(Intent.SILENCE, "", "local")
            self.st.intent, self.st.intent_source = result.intent.value, result.source

            if result.intent is Intent.UNCLEAR and not unclear_once:
                unclear_once = True
                line = result.reply or self.bank.pick("unclear")
                continue
            if result.intent in (Intent.SILENCE, Intent.UNCLEAR):
                line = self._escalate()
                continue
            unclear_once = False

            if result.intent is Intent.CAUGHT_LYING:
                line = self._handle_lie(result.reply)
                continue
            if result.intent is Intent.EXCUSE:
                line = self._handle_excuse(heard or "", result.reply)
                continue
            # CONFESS / BACK_TO_WORK
            if result.intent is Intent.CONFESS:
                self.st.confessions += 1
            self._set(State.RESPONDING)
            self._say(result.reply, interruptible=False)
            self._reset_after_return(f"{result.intent.value} → back to WORKING")
            return

    # ---------------------------------------------------------------- steps
    def _say(self, text: str, interruptible: bool) -> None:
        self.st.last_bot = text
        self.st.trace(f"BOT: {text}")
        stop = self._stopped if interruptible else self.shutdown.is_set
        self.voice.speak(text, self._prosody(self.st.level), stop)
        if interruptible:
            self._check()

    def _listen(self) -> Optional[str]:
        """None == silence. '' == heard something but couldn't transcribe."""
        self._set(State.LISTENING)
        self._wait(0.15)  # let the speaker tail die out
        self.st.countdown_until = time.monotonic() + self.t.listen_window
        rec = record_utterance(self.t.listen_window, self._stopped, self._on_mic)
        self.st.countdown_until = 0.0
        self._check()
        if rec.status == "no_mic":
            self.st.log("[yellow]mic gave silence — allow Microphone access for your terminal[/]")
            return None
        if rec.status != "speech":
            self.st.log("no reply… (silence)")
            return None
        self._set(State.RESPONDING)
        t0 = time.monotonic()
        try:
            text = self.client.transcribe(rec.wav)
        except SarvamError as err:
            self.st.log(f"[red]STT error:[/] {err}")
            return ""
        self.st.stt_ms = int((time.monotonic() - t0) * 1000)
        self.st.last_heard = text or "…"
        self.st.log(f"heard: {text or '(nothing)'}")
        return text

    def _on_mic(self, level: float) -> None:
        self.st.mic_level = level

    def _understand(self, heard: str) -> Understanding:
        if not heard.strip():
            return Understanding(Intent.UNCLEAR, self.bank.pick("unclear"), "local")
        user = _CLASSIFY.format(
            level=self.st.level,
            mood=LEVEL_MOODS[self.st.level],
            excuses=self.st.excuses,
            streak=self._streak,
            last_excuse=self._last_excuse or "none",
            heard=heard,
            screen=self._look().for_llm(),
        )
        t0 = time.monotonic()
        try:
            data = self.client.chat_json(self._system(), user)
            self.st.llm_ms = int((time.monotonic() - t0) * 1000)
            intent = Intent(str(data.get("intent", "")).upper().strip())
            if intent is Intent.SILENCE:
                raise ValueError("SILENCE is decided locally")
            reply = str(data.get("reply", "")).strip()
            if intent is Intent.CAUGHT_LYING and not self._screen.distraction:
                intent, reply = Intent.EXCUSE, ""  # never accuse without evidence on screen
            if intent is Intent.CAUGHT_LYING and _APOLOGY.search(heard):
                intent, reply = Intent.CONFESS, ""  # owning up is a confession, not a lie
            if not reply or looks_romanized(reply):
                reply = self._bank_reply(intent)
            return Understanding(intent, reply, f"LLM {self.st.llm_ms} ms")
        except (SarvamError, ValueError) as err:
            self.st.log(f"[yellow]LLM fallback:[/] {str(err)[:60]}")
            intent = classify_locally(heard)
            if intent is Intent.EXCUSE and self._screen.distraction:
                intent = Intent.CAUGHT_LYING
            return Understanding(intent, self._bank_reply(intent), "keyword fallback")

    def _bank_reply(self, intent: Intent) -> str:
        kind = {
            Intent.EXCUSE: "excuse_repeat" if self._streak else "excuse_first",
            Intent.CONFESS: "confess",
            Intent.BACK_TO_WORK: "back_to_work",
            Intent.CAUGHT_LYING: "busted",
        }.get(intent, "unclear")
        return self.bank.pick(kind).format(site=self._screen.distraction or "phone")

    def _system(self) -> str:
        return _RULES.format(tone=self.persona.tone)

    # ---------------------------------------------------------------- screen
    def _look(self) -> ScreenContext:
        """Refresh what's on screen (app + browser tab). Text only; disabled with --no-screen."""
        if not self.watcher:
            return self._screen
        self._screen = self.watcher.latest
        self.st.distraction = self._screen.distraction or ""
        self.st.screen = self._screen.short()
        if self._screen.distraction:
            self.st.screen = f"🚨 {self.st.screen}"
        return self._screen

    def _opening_line(self) -> str:
        """Generic cached nag — or, if a distraction is on screen, call it out by name."""
        site = self._look().distraction
        if not site:
            return self.bank.pick("nag", self.st.level)
        self.st.log(f"screen shows [bold]{site}[/] — calling it out")
        try:
            data = self.client.chat_json(
                self._system(),
                _CAUGHT.format(
                    reason=(
                        "She IS using her laptop — moving the mouse, scrolling — but not for work."
                        if self._trigger == "distracted"
                        else "You just caught her idle (no keyboard or mouse for a while)."
                    ),
                    screen=self._screen.for_llm(),
                    level=self.st.level,
                    mood=LEVEL_MOODS[self.st.level],
                ),
                timeout=2.5,
            )
            line = str(data.get("reply", "")).strip()
            if line and not looks_romanized(line):
                return line
        except SarvamError:
            pass
        return self.bank.pick("caught").format(site=site)

    def _handle_lie(self, reply: str) -> str:
        """Excuse contradicted by the screen: no snooze, escalate, and make her answer again."""
        self.st.lies += 1
        self._streak += 1
        self.st.level = min(MAX_LEVEL, self.st.level + 1)
        self.st.log(f"[bold red]LIE[/] — screen says {self._screen.distraction} → L{self.st.level}")
        return reply

    def _escalate(self) -> str:
        self.st.level = min(MAX_LEVEL, self.st.level + 1)
        self.st.log(f"silence → escalate to L{self.st.level} ({LEVEL_MOODS[self.st.level]})")
        line = self.bank.pick("nag", self.st.level)
        site = self._screen.distraction
        if self._fake_seen.is_set() and not self._fake_called_out and site:
            self._fake_called_out = True
            self.st.log(f"mouse moved, but {site} is still in focus — not buying it")
            line = self.bank.pick("fake_comeback").format(site=site)
        self._bg.submit(self._safe_prefetch, line, self._prosody(self.st.level))
        self._set(State.IDLE)
        self._countdown(self.t.escalation_gap)
        return line

    def _handle_excuse(self, heard: str, reply: str) -> str:
        self.st.excuses += 1
        self._streak += 1
        self._last_excuse = heard
        self._set(State.RESPONDING)
        self._say(reply, interruptible=False)

        snooze = self.t.snooze_duration if self._streak == 1 else max(3.0, self.t.snooze_duration / 2)
        self.st.log(f"excuse #{self._streak} in a row → snooze {snooze:.0f}s")
        followup: Future[str] = self._bg.submit(self._prepare_followup, heard)
        self.activity.clear()
        self._set(State.SNOOZED)
        self._countdown(snooze)
        try:
            return followup.result(timeout=0.5)
        except Exception:
            return self.bank.pick("followup").format(topic=excuse_topic(heard))

    def _prepare_followup(self, excuse: str) -> str:
        """Runs during the snooze: write the suspicious line, then pre-synthesize it."""
        line = ""
        try:
            data = self.client.chat_json(self._system(), _FOLLOWUP.format(excuse=excuse, streak=self._streak, screen=self._look().for_llm()))
            line = str(data.get("reply", "")).strip()
        except SarvamError:
            pass
        if not line or looks_romanized(line):
            line = self.bank.pick("followup").format(topic=excuse_topic(excuse))
        self._safe_prefetch(line, self._prosody(self.st.level), persist=False)
        return line

    def _safe_prefetch(self, text: str, prosody: Prosody, persist: bool = True) -> None:
        try:
            self.voice.prefetch(text, prosody, persist=persist)
        except Exception:
            pass  # speak() will stream it live instead

    def _countdown(self, seconds: float) -> None:
        self.st.countdown_until = time.monotonic() + seconds
        try:
            self._wait(seconds)
        finally:
            self.st.countdown_until = 0.0

    def _wait(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self._check()
            time.sleep(0.05)
        self._check()

    def _welcome_back(self) -> None:
        self.st.comebacks += 1
        self._set(State.WORKING)
        self.st.intent, self.st.intent_source = "ACTIVITY", "keyboard/mouse"
        line = self.bank.pick("welcome_back")
        self.st.last_bot = line
        self.st.trace(f"BOT: {line}")
        self.voice.speak(line, self._prosody(1), self.shutdown.is_set)
        self._reset_after_return("keyboard/mouse activity → WORKING")

    def _reset_after_return(self, why: str) -> None:
        self.st.level = 1
        self._streak = 0
        self._last_excuse = ""
        self.st.log(why)

    def stop(self) -> None:
        self.shutdown.set()
        self._bg.shutdown(wait=False, cancel_futures=True)

