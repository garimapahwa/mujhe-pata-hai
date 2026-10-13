"""Interruptible streaming playback + mic recording with a simple RMS VAD."""

from __future__ import annotations

import io
import struct
import time
import wave
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Literal, Optional

import numpy as np
import sounddevice as sd

from config import MIC_SAMPLE_RATE, TRAILING_SILENCE_S

StopFn = Callable[[], bool]
LevelFn = Callable[[float], None]

_WRITE_FRAMES = 1024  # ~43 ms at 24 kHz: granularity of interruption checks


# ---------------------------------------------------------------- playback
class WavStreamParser:
    """Turns a chunked WAV byte stream (header w/ unknown sizes) into raw PCM."""

    def __init__(self) -> None:
        self._buf = b""
        self.sample_rate: Optional[int] = None
        self.channels = 1
        self._in_data = False

    def feed(self, chunk: bytes) -> bytes:
        if self._in_data:
            return chunk
        self._buf += chunk
        if len(self._buf) < 12 or not self._buf.startswith(b"RIFF"):
            if len(self._buf) >= 12 and not self._buf.startswith(b"RIFF"):
                raise ValueError("stream is not WAV")
            return b""
        pos = 12
        while pos + 8 <= len(self._buf):
            cid, size = self._buf[pos : pos + 4], struct.unpack("<I", self._buf[pos + 4 : pos + 8])[0]
            if cid == b"fmt ":
                if pos + 8 + 16 > len(self._buf):
                    return b""
                self.channels, self.sample_rate = struct.unpack("<HI", self._buf[pos + 10 : pos + 16])
            if cid == b"data":
                self._in_data = True
                pcm, self._buf = self._buf[pos + 8 :], b""
                return pcm
            pos += 8 + size
        return b""


def play_wav_stream(chunks: Iterable[bytes], should_stop: StopFn) -> bool:
    """Play WAV bytes as they arrive. Returns False if interrupted by `should_stop`."""
    parser = WavStreamParser()
    stream: Optional[sd.RawOutputStream] = None
    pending = b""
    frame_bytes = 2
    try:
        for chunk in chunks:
            if should_stop():
                return False
            pending += parser.feed(chunk)
            if parser.sample_rate is None:
                continue
            if stream is None:
                frame_bytes = 2 * parser.channels
                stream = sd.RawOutputStream(
                    samplerate=parser.sample_rate, channels=parser.channels, dtype="int16", latency="low"
                )
                stream.start()
            step = _WRITE_FRAMES * frame_bytes
            while len(pending) >= step:
                if should_stop():
                    return False
                stream.write(pending[:step])
                pending = pending[step:]
        if stream is not None and pending and not should_stop():
            usable = len(pending) - len(pending) % frame_bytes
            stream.write(pending[:usable])
        return not should_stop()
    finally:
        if stream is not None:
            if should_stop():
                stream.abort()
            else:
                stream.stop()  # drains the remaining buffer
            stream.close()


def play_wav_bytes(data: bytes, should_stop: StopFn) -> bool:
    return play_wav_stream(_chunked(data, 8192), should_stop)


def _chunked(data: bytes, size: int) -> Iterator[bytes]:
    for i in range(0, len(data), size):
        yield data[i : i + size]


# ---------------------------------------------------------------- recording
@dataclass
class Recording:
    status: Literal["speech", "silence", "interrupted", "no_mic"]
    wav: bytes = b""
    seconds: float = 0.0


def pcm_to_wav(pcm: bytes, sample_rate: int = MIC_SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(block.astype(np.float32) ** 2))) if block.size else 0.0


def record_utterance(
    window_s: float,
    should_stop: StopFn,
    on_level: Optional[LevelFn] = None,
    silence_after_s: float = TRAILING_SILENCE_S,
    max_extra_s: float = 4.0,
) -> Recording:
    """Listen up to `window_s` for speech; once speech starts, stop on trailing silence.

    If the user is mid-sentence when the window ends we allow `max_extra_s` more.
    """
    block_s = 0.05
    block = int(MIC_SAMPLE_RATE * block_s)
    min_rms = 350.0  # int16 units; below this is room noise for a laptop mic
    blocks: list[np.ndarray] = []
    noise: list[float] = []
    voiced_total = 0
    onset_idx: Optional[int] = None
    silence_run = 0.0
    peak = 0.0
    start = time.monotonic()

    try:
        with sd.InputStream(samplerate=MIC_SAMPLE_RATE, channels=1, dtype="int16", blocksize=block) as mic:
            while True:
                if should_stop():
                    return Recording("interrupted")
                data, _ = mic.read(block)
                mono = data[:, 0].copy()
                blocks.append(mono)
                level = _rms(mono)
                peak = max(peak, level)
                if len(noise) < 6:
                    noise.append(level)
                threshold = max(min_rms, float(np.median(noise)) * 2.5)
                if on_level:
                    on_level(min(1.0, level / 4000))

                voiced = level > threshold
                elapsed = time.monotonic() - start
                if voiced:
                    voiced_total += 1
                    silence_run = 0.0
                    if onset_idx is None and voiced_total >= 3:
                        onset_idx = max(0, len(blocks) - 3 - 6)  # keep ~300 ms pre-roll
                else:
                    silence_run += block_s

                if onset_idx is not None and silence_run >= silence_after_s:
                    break
                if elapsed >= window_s and (onset_idx is None or silence_run > 0.4):
                    break
                if elapsed >= window_s + max_extra_s:
                    break
    except sd.PortAudioError:
        return Recording("no_mic")
    finally:
        if on_level:
            on_level(0.0)

    if peak == 0.0:
        return Recording("no_mic")  # all-zero input: mic permission denied
    if onset_idx is None:
        return Recording("silence")
    pcm = np.concatenate(blocks[onset_idx:]).tobytes()
    return Recording("speech", pcm_to_wav(pcm), len(pcm) / 2 / MIC_SAMPLE_RATE)


if __name__ == "__main__":
    print("Say something (6s window)…")
    rec = record_utterance(6, lambda: False, lambda lv: print(f"\r{'█' * int(lv * 40):<40}", end=""))
    print(f"\n{rec.status} {rec.seconds:.1f}s")
    if rec.wav:
        print("Playing it back…")
        play_wav_bytes(rec.wav, lambda: False)
