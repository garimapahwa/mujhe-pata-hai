"""Thin wrappers over Sarvam AI: Bulbul v4 Flash (stream TTS), Saaras v4 (STT), Sarvam LLM.

One keep-alive httpx.Client is shared by the streaming TTS calls and the official SDK.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Callable, Iterator, Optional, TypeVar

import httpx
from dotenv import load_dotenv
from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

import config
from config import Prosody

T = TypeVar("T")
_RETRYABLE = {429, 500, 502, 503}


class SarvamError(Exception):
    pass


class SpeakerError(SarvamError):
    def __init__(self, speaker: str, available: list[str]) -> None:
        super().__init__(f"speaker {speaker!r} not available")
        self.speaker = speaker
        self.available = available


def _backoff(attempt: int) -> float:
    """Exponential backoff with full jitter: ~0.3s, 0.6s, 1.2s…"""
    return random.uniform(0.5, 1.0) * 0.3 * (2**attempt)


def _parse_speakers(message: str) -> list[str]:
    match = re.search(r"are:\s*(.+)", message)
    if not match:
        return []
    return [s.strip(" .'\"") for s in match.group(1).split(",") if s.strip(" .'\"")]


class SarvamClient:
    def __init__(self, api_key: Optional[str] = None) -> None:
        load_dotenv()
        key = api_key or os.getenv("SARVAM_API_KEY")
        if not key:
            raise SarvamError("SARVAM_API_KEY missing — copy .env.example to .env and add your key")
        self.http = httpx.Client(
            headers={"api-subscription-key": key},
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=120),
        )
        self.sdk = SarvamAI(api_subscription_key=key, httpx_client=self.http)
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sarvam")

    # ------------------------------------------------------------------ TTS
    def tts_stream(self, text: str, speaker: str, prosody: Prosody = Prosody()) -> Iterator[bytes]:
        """Yield WAV bytes (24 kHz mono) as Bulbul streams them. Retries 429/5xx before first byte."""
        p = prosody.validated()
        body = {
            "text": text,
            "model": config.TTS_MODEL,
            "language_code": config.TTS_LANGUAGE,
            "speaker": speaker,
            "pace": p.pace,
            "pitch": p.pitch,
            "loudness": p.loudness,
            "speech_sample_rate": config.TTS_SAMPLE_RATE,
            "output_audio_codec": "wav",
            "enable_preprocessing": True,
        }
        for attempt in range(4):
            with self.http.stream("POST", config.TTS_STREAM_URL, json=body) as resp:
                if resp.status_code == 200:
                    yield from resp.iter_bytes()
                    return
                resp.read()
                if resp.status_code == 400 and "speaker" in resp.text.lower():
                    msg = resp.json().get("error", {}).get("message", resp.text)
                    raise SpeakerError(speaker, _parse_speakers(msg))
                if resp.status_code not in _RETRYABLE or attempt == 3:
                    raise SarvamError(f"TTS HTTP {resp.status_code}: {resp.text[:200]}")
            time.sleep(_backoff(attempt))

    def tts_bytes(self, text: str, speaker: str, prosody: Prosody = Prosody()) -> bytes:
        return b"".join(self.tts_stream(text, speaker, prosody))

    def check_speaker(self, speaker: str) -> list[str]:
        """Tiny TTS call. Returns [] if the speaker works, else the live speaker list."""
        try:
            self.tts_bytes("हाँ।", speaker)
            return []
        except SpeakerError as err:
            return err.available or ["<unknown>"]

    # ------------------------------------------------------------------ STT
    def transcribe(self, wav: bytes) -> str:
        """Saaras v4 in codemix mode: Hindi → Devanagari, English → Latin."""

        def call() -> str:
            resp = self.sdk.speech_to_text.transcribe(
                file=("speech.wav", wav, "audio/wav"),
                model=config.STT_MODEL,
                mode=config.STT_MODE,
                language_code=config.STT_LANGUAGE,
                request_options={"timeout_in_seconds": 10, "max_retries": 0},
            )
            return (resp.transcript or "").strip()

        return self._retry(call)

    # ------------------------------------------------------------------ LLM
    def chat_json(self, system: str, user: str, timeout: float = config.LLM_TIMEOUT_S) -> dict[str, Any]:
        """One low-latency chat call returning parsed JSON. Hard total timeout."""

        def call() -> dict[str, Any]:
            resp = self.sdk.chat.completions(
                model=config.LLM_MODEL,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.8,
                max_tokens=config.LLM_MAX_TOKENS,
                response_format={"type": "json_object"},
                request_options={
                    "timeout_in_seconds": int(timeout) + 1,
                    "max_retries": 0,
                    # docs: reasoning is disabled by sending an explicit null
                    "additional_body_parameters": {"reasoning_effort": None},
                },
            )
            content = resp.choices[0].message.content or ""
            return _extract_json(content)

        future = self._pool.submit(self._retry, call, time.monotonic() + timeout)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout as err:
            raise SarvamError(f"LLM timed out after {timeout}s") from err

    # ------------------------------------------------------------------ misc
    def _retry(self, fn: Callable[[], T], deadline: Optional[float] = None) -> T:
        for attempt in range(4):
            try:
                return fn()
            except ApiError as err:
                status = err.status_code or 0
                wait = _backoff(attempt)
                out_of_time = deadline is not None and time.monotonic() + wait >= deadline
                if status not in _RETRYABLE or attempt == 3 or out_of_time:
                    raise SarvamError(f"HTTP {status}: {str(err.body)[:200]}") from err
                time.sleep(wait)
            except httpx.HTTPError as err:
                raise SarvamError(f"network: {err}") from err
        raise SarvamError("unreachable")

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
        self.http.close()


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise SarvamError(f"no JSON in LLM output: {text[:120]!r}")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as err:
        raise SarvamError(f"bad JSON: {err}") from err
    if not isinstance(data, dict):
        raise SarvamError("LLM JSON is not an object")
    return data


if __name__ == "__main__":
    from audio import play_wav_stream

    client = SarvamClient()
    line = "क्या चल रहा है? Phone चला रही हो? मुझे पता है, मुझे पता है…"
    t0 = time.monotonic()
    first: list[float] = []

    def timed(chunks: Iterator[bytes]) -> Iterator[bytes]:
        for c in chunks:
            if not first:
                first.append(time.monotonic() - t0)
            yield c

    play_wav_stream(timed(client.tts_stream(line, config.PERSONAS["mummy"].speakers[0])), lambda: False)
    print(f"first audio byte after {first[0] * 1000:.0f} ms" if first else "no audio")
    client.close()
