"""Mujhe Pata Hai — a voice focus buddy that catches you idling and nags you in Hinglish."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.live import Live

import config
from audio import play_wav_stream
from brain import Brain, Status, Voice
from config import LEVELS, PERSONAS, Persona
from idle import IdleMonitor
from screen import ScreenWatcher
from lines import AUDITION_LINE, BANKS
from sarvam_client import SarvamClient, SarvamError
from ui import render

console = Console()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Mujhe Pata Hai — voice focus buddy powered by Sarvam AI")
    p.add_argument("--persona", choices=sorted(PERSONAS), default="mummy")
    p.add_argument("--mode", choices=["demo", "real"], default="demo", help="timer preset (default: demo)")
    p.add_argument("--no-screen", action="store_true", help="don't look at the frontmost app / browser tab")
    p.add_argument("--audition", action="store_true", help="speak a sample line in every candidate voice and exit")
    return p.parse_args()


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


def resolve_speaker(client: SarvamClient, persona: Persona) -> str:
    available: list[str] = []
    for candidate in persona.speakers:
        available = client.check_speaker(candidate)
        if not available:
            return candidate
        console.print(f"[yellow]speaker {candidate} rejected by Bulbul v4 Flash[/]")
    pick = best_alternative(persona.speakers[0], available)
    console.print(f"[yellow]auto-picked {pick} from the live speaker list[/]")
    return pick


# ------------------------------------------------------------------ warmup
def warm_cache(voice: Voice, persona: str) -> None:
    """Level-1 nags + 'aa gayi' lines must be instant: synthesize them before going live."""
    bank = BANKS[persona]
    quick = [(line, LEVELS[1]) for line in bank.nag[1] + bank.welcome_back]
    with console.status("[bold magenta]warming up the voice (pre-synthesizing first lines)…"):
        with ThreadPoolExecutor(max_workers=4) as pool:
            for fut in [pool.submit(voice.prefetch, text, pros) for text, pros in quick]:
                try:
                    fut.result()
                except SarvamError as err:
                    console.print(f"[yellow]couldn't cache a line ({err}); it will stream live[/]")


def warm_rest_in_background(voice: Voice, persona: str) -> None:
    bank = BANKS[persona]
    jobs = [(l, LEVELS[lvl]) for lvl in (2, 3) for l in bank.nag[lvl]]
    jobs += [(l, LEVELS[1]) for l in bank.unclear]

    def run() -> None:
        for text, pros in jobs:
            try:
                voice.prefetch(text, pros)
            except Exception:
                pass

    threading.Thread(target=run, name="warm-rest", daemon=True).start()


# ------------------------------------------------------------------ modes
def audition(client: SarvamClient) -> None:
    speakers = list(dict.fromkeys(config.AUDITION_SPEAKERS + tuple(s for p in PERSONAS.values() for s in p.speakers)))
    console.print(f"[bold]Auditioning {len(speakers)} voices[/] — line: {AUDITION_LINE}\n")
    for speaker in speakers:
        owners = [p.key for p in PERSONAS.values() if speaker in p.speakers]
        console.print(f"🔊 [bold magenta]{speaker}[/] [grey62]{', '.join(owners)}[/]")
        try:
            play_wav_stream(client.tts_stream(AUDITION_LINE, speaker), lambda: False)
        except SarvamError as err:
            console.print(f"   [red]unavailable:[/] {err}")
        time.sleep(0.4)


def run_app(client: SarvamClient, persona: Persona, mode: str, screen: bool = True) -> None:
    speaker = resolve_speaker(client, persona)
    status = Status(persona=persona, mode=mode, timings=config.timings_for(mode), speaker=speaker)
    voice = Voice(client, speaker, status)
    warm_cache(voice, persona.key)
    warm_rest_in_background(voice, persona.key)

    monitor = IdleMonitor()
    watcher = ScreenWatcher() if screen else None
    brain = Brain(client, voice, status, monitor, watcher)
    t = status.timings
    status.log(
        f"ready · idle {t.idle_threshold:.0f}s · listen {t.listen_window:.0f}s · "
        f"snooze {t.snooze_duration:.0f}s · gap {t.escalation_gap:.0f}s · distraction {t.distraction_grace:.0f}s"
    )
    monitor.start()
    if watcher:
        watcher.start()
    worker = threading.Thread(target=brain.run, name="brain", daemon=True)
    worker.start()

    try:
        with Live(render(status), console=console, refresh_per_second=12, screen=True) as live:
            while worker.is_alive():
                live.update(render(status))
                time.sleep(1 / 12)
    except KeyboardInterrupt:
        pass
    finally:
        brain.stop()
        monitor.stop()
        if watcher:
            watcher.stop()
        worker.join(timeout=2)
        console.print(
            f"\n[bold red]मुझे पता है[/] signing off. caught {status.caught}× · "
            f"excuses {status.excuses} · confessions {status.confessions} · comebacks {status.comebacks} · "
            f"lies caught {status.lies}"
        )


def main() -> int:
    args = parse_args()
    try:
        client = SarvamClient()
    except SarvamError as err:
        console.print(f"[red]{err}[/]")
        return 1
    try:
        if args.audition:
            audition(client)
        else:
            run_app(client, PERSONAS[args.persona], args.mode, screen=not args.no_screen)
    except KeyboardInterrupt:
        pass
    except SarvamError as err:
        console.print(f"[red]Sarvam API error at startup:[/] {err}")
        return 1
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
