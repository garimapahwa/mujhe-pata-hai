"""Side Eye — terminal version with the rich dashboard. For the menu bar app run `python app.py`."""

from __future__ import annotations

import argparse
import sys
import time

from rich.console import Console
from rich.live import Live

import config
from audio import play_wav_stream
from config import PERSONAS
from engine import VOLUMES, Engine
from lines import AUDITION_LINE
from sarvam_client import SarvamClient, SarvamError
from ui import render

console = Console()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Side Eye — voice focus buddy powered by Sarvam AI")
    p.add_argument("--persona", choices=list(PERSONAS), default="mummy")
    p.add_argument("--mode", choices=["demo", "real"], default="demo", help="timer preset (default: demo)")
    p.add_argument("--volume", choices=list(VOLUMES), default="Normal")
    p.add_argument("--no-screen", action="store_true", help="don't look at the frontmost app / browser tab")
    p.add_argument("--audition", action="store_true", help="speak a sample line in every candidate voice and exit")
    return p.parse_args()


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


def run_terminal(client: SarvamClient, args: argparse.Namespace) -> None:
    engine = Engine(client)
    with console.status("[bold magenta]warming up the voice (pre-synthesizing first lines)…"):
        status = engine.start(
            args.persona, args.mode, screen=not args.no_screen, volume=VOLUMES[args.volume],
            log=lambda m: console.print(f"[yellow]{m}[/]"),
        )
    try:
        with Live(render(status), console=console, refresh_per_second=12, screen=True) as live:
            while engine.running:
                live.update(render(status))
                time.sleep(1 / 12)
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        console.print(
            f"\n[bold red]Side Eye[/] signing off. caught {status.caught}× · "
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
            run_terminal(client, args)
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
