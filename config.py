"""Modes, timers, prosody levels, model IDs and persona definitions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / ".cache"

# --- Sarvam models / endpoints (verified against docs.sarvam.ai + live API) ---
API_BASE = "https://api.sarvam.ai"
TTS_STREAM_URL = f"{API_BASE}/text-to-speech/stream"
TTS_MODEL = "bulbul:v4-flash"
TTS_LANGUAGE = "hi-IN"
TTS_SAMPLE_RATE = 24000  # max supported on HTTP streaming
STT_MODEL = "saaras:v4"
STT_MODE = "codemix"  # Hindi in Devanagari, English in Latin script
STT_LANGUAGE = "hi-IN"
LLM_MODEL = "sarvam-105b-conversations"  # the real-time / voice-agent variant
LLM_TIMEOUT_S = 4.0
LLM_MAX_TOKENS = 160

# --- Audio ---
MIC_SAMPLE_RATE = 16000
TRAILING_SILENCE_S = 1.2
ACTIVITY_IDLE_S = 2.0  # idle below this == "user touched keyboard/mouse"


@dataclass(frozen=True)
class Timings:
    idle_threshold: float
    listen_window: float
    snooze_duration: float
    escalation_gap: float
    distraction_grace: float  # focused on YouTube/Netflix this long (even while active) → caught


_MODES: dict[str, Timings] = {
    "demo": Timings(idle_threshold=8, listen_window=6, snooze_duration=12, escalation_gap=5, distraction_grace=8),
    "real": Timings(
        idle_threshold=420, listen_window=8, snooze_duration=600, escalation_gap=60, distraction_grace=90
    ),
}


def timings_for(mode: str) -> Timings:
    """Mode defaults, each overridable via env var (e.g. IDLE_THRESHOLD=15)."""
    base = _MODES[mode]

    def pick(name: str, default: float) -> float:
        raw = os.getenv(name)
        try:
            return float(raw) if raw else default
        except ValueError:
            return default

    return Timings(
        idle_threshold=pick("IDLE_THRESHOLD", base.idle_threshold),
        listen_window=pick("LISTEN_WINDOW", base.listen_window),
        snooze_duration=pick("SNOOZE_DURATION", base.snooze_duration),
        escalation_gap=pick("ESCALATION_GAP", base.escalation_gap),
        distraction_grace=pick("DISTRACTION_GRACE", base.distraction_grace),
    )


# --- Escalation prosody (Bulbul v4 Flash ranges) ---
PACE_RANGE = (0.5, 2.0)
PITCH_RANGE = (-0.5, 0.5)
LOUDNESS_RANGE = (0.1, 2.5)


@dataclass(frozen=True)
class Prosody:
    pace: float = 1.0
    pitch: float = 0.0
    loudness: float = 1.0

    def validated(self) -> "Prosody":
        def clamp(v: float, lo_hi: tuple[float, float]) -> float:
            return round(max(lo_hi[0], min(lo_hi[1], v)), 2)

        return Prosody(
            pace=clamp(self.pace, PACE_RANGE),
            pitch=clamp(self.pitch, PITCH_RANGE),
            loudness=clamp(self.loudness, LOUDNESS_RANGE),
        )


LEVELS: dict[int, Prosody] = {
    1: Prosody(pace=1.0, pitch=0.0, loudness=1.0),   # teasing
    2: Prosody(pace=1.15, pitch=0.1, loudness=1.6),  # annoyed
    3: Prosody(pace=1.3, pitch=0.2, loudness=2.2),   # full drama
}
MAX_LEVEL = 3
LEVEL_MOODS = {1: "teasing", 2: "annoyed", 3: "FULL DRAMA"}


# --- Personas ---
@dataclass(frozen=True)
class Persona:
    key: str
    title: str
    speakers: tuple[str, ...]  # preferred first; validated at startup
    tone: str  # LLM system-prompt tone
    emoji: str = ""
    tagline: str = ""  # shown in the menu bar picker
    intro: str = ""  # spoken when you pick this character
    base: Prosody = Prosody()  # voice colour applied on top of every escalation level

    def prosody(self, level: int, volume: float = 1.0) -> Prosody:
        lv = LEVELS[level]
        return Prosody(
            pace=lv.pace * self.base.pace,
            pitch=lv.pitch + self.base.pitch,
            loudness=lv.loudness * self.base.loudness * volume,
        ).validated()


PERSONAS: dict[str, Persona] = {
    "mummy": Persona(
        key="mummy",
        title="Mummy",
        emoji="👩",
        tagline="strict, dramatic, loving",
        intro="बेटा, मैं आ गई हूँ। अब phone उठाया ना, तो मुझे पता चल जाएगा!",
        speakers=("simran_hi_recovery", "aarti_hi_customer"),
        tone=(
            "You are a strict, dramatic, deeply loving Indian mom. You call the user 'बेटा'. "
            "You guilt-trip theatrically (\"मैंने इतनी मेहनत से पढ़ाया…\", \"शर्मा जी की बेटी…\"), "
            "but you melt instantly when she is honest. You are a woman; use feminine verb forms for yourself."
        ),
    ),
    "dost": Persona(
        key="dost",
        title="Dost",
        emoji="😎",
        tagline="Gen-Z roast best friend",
        intro="Bro, मैं on हूँ। Reels खोली ना, तो roast पक्का!",
        speakers=("ishita_enhi_customer", "simran_enhi_customer"),
        tone=(
            "You are the user's chill Gen-Z best friend who roasts her lovingly. Use slang like "
            "'bro', 'literally', 'no cap', 'scene kya hai', 'reels'. Short, punchy, sarcastic, never mean. "
            "You are a woman; use feminine verb forms for yourself."
        ),
    ),
    "commentator": Persona(
        key="commentator",
        title="Commentator",
        emoji="🏏",
        tagline="live procrastination commentary",
        intro="नमस्कार दर्शकों! आज का match है, focus versus phone। Live commentary शुरू!",
        speakers=("ratan_hi_customer_expressive", "sunny_en_social"),
        tone=(
            "You are an over-excited Indian cricket commentator narrating the user's procrastination LIVE, "
            "in third person, like a match: wickets, boundaries, run-rate, third umpire, DRS, crowd going wild. "
            "You are a man; use masculine verb forms for yourself."
        ),
    ),
    "filmy": Persona(
        key="filmy",
        title="Filmy Narrator",
        emoji="🎬",
        tagline="deep, dramatic baritone",
        intro="देवियों और सज्जनों… आज से इस laptop की रखवाली, हम करेंगे।",
        speakers=("anand_hi_documentary", "girish_hi_devotional", "mahesh_hi_documentary"),
        base=Prosody(pace=0.9, pitch=-0.1, loudness=1.1),
        tone=(
            "You are a legendary, deep-voiced 1970s-80s Bollywood hero-narrator: slow, grand, theatrical, "
            "full of pauses (use commas and …), speaking of yourself as 'हम'. Every scolding sounds like an "
            "iconic movie dialogue about duty, destiny and deadlines. Write ORIGINAL dialogues only: never quote "
            "or imitate any real actor's famous lines or catchphrases, and never name real actors. "
            "You are a man; use masculine verb forms for yourself."
        ),
    ),
    "action": Persona(
        key="action",
        title="Action Hero",
        emoji="💪",
        tagline="loud, table-thumping hero",
        intro="सुन लो! आज से इस desk पे सिर्फ़ काम चलेगा। और कुछ नहीं!",
        speakers=("shubh_hi_stories_dramatic", "aryaman_hi_ads"),
        base=Prosody(pace=1.05, pitch=-0.05, loudness=1.3),
        tone=(
            "You are a loud, furious, over-the-top 90s Bollywood action hero who shouts, thumps tables and makes "
            "everything sound like a final showdown, but you are secretly soft-hearted. Short explosive sentences "
            "with lots of '!'. Write ORIGINAL dialogues only: never quote or imitate any real actor's famous lines "
            "or catchphrases, and never name real actors. You are a man; use masculine verb forms for yourself."
        ),
    ),
}

# Voices auditioned by `--audition`
AUDITION_SPEAKERS: tuple[str, ...] = (
    "simran_hi_recovery",
    "aarti_hi_customer",
    "ishita_enhi_customer",
    "simran_enhi_customer",
    "ratan_hi_customer_expressive",
    "sunny_en_social",
    "anand_hi_documentary",
    "girish_hi_devotional",
    "shubh_hi_stories_dramatic",
    "aryaman_hi_ads",
)
