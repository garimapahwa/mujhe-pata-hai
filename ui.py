"""Rich live dashboard. Devanagari lines sit in side-border-less panels so terminal width quirks can't break borders."""

from __future__ import annotations

import time

from rich import box
from rich.align import Align
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from brain import State, Status
from config import LEVEL_MOODS, MAX_LEVEL

_STYLE: dict[State, tuple[str, str, str]] = {
    # state: (colour, icon, caption)
    State.WORKING: ("green", "💻", "focus mode on — keep going"),
    State.IDLE: ("yellow", "👀", "caught you…"),
    State.NAGGING: ("red", "📢", "speaking…"),
    State.LISTENING: ("cyan", "🎙 ", "listening — say something!"),
    State.RESPONDING: ("blue", "🧠", "understanding you…"),
    State.SNOOZED: ("magenta", "⏳", "snoozed… for now"),
}

# 5-row pixel font, rendered into 3 terminal rows with half blocks.
_FONT: dict[str, list[str]] = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "G": [".###", "#...", "#.##", "#..#", ".###"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "N": ["#..#", "##.#", "#.##", "#..#", "#..#"],
    "O": [".##.", "#..#", "#..#", "#..#", ".##."],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "W": ["#...#", "#...#", "#.#.#", "##.##", "#...#"],
    "Z": ["###", "..#", ".#.", "#..", "###"],
}


def big_text(word: str) -> list[str]:
    rows = ["", "", "", "", ""]
    for ch in word:
        glyph = _FONT.get(ch, ["..", "..", "..", "..", ".."])
        for i in range(5):
            rows[i] += glyph[i] + "."
    rows.append("." * len(rows[0]))
    out = []
    for top, bottom in zip(rows[0::2], rows[1::2]):
        line = ""
        for a, b in zip(top, bottom):
            line += {("#", "#"): "█", ("#", "."): "▀", (".", "#"): "▄"}.get((a, b), " ")
        out.append(line)
    return out


def _bar(fraction: float, width: int, colour: str) -> Text:
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(fraction * width))
    return Text("█" * filled, style=colour) + Text("░" * (width - filled), style="grey35")


def _badge(st: Status) -> Panel:
    colour, icon, caption = _STYLE[st.state]
    art = Text("\n".join(big_text(st.state.value)), style=f"bold {colour}")
    sub = Text(f"{icon} {caption}", style=colour)
    left = st.countdown_until - time.monotonic()
    if left > 0:
        sub += Text(f"   {left:4.1f}s", style=f"bold {colour}")
    body: list[RenderableType] = [Align.center(art), Align.center(sub)]
    if st.state is State.LISTENING:
        body.append(Align.center(Text("mic ") + _bar(st.mic_level, 30, "cyan")))
    return Panel(Group(*body), border_style=colour, box=box.HEAVY, padding=(1, 2))


def _meters(st: Status) -> Panel:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold", width=11)
    grid.add_column()
    threshold = st.timings.idle_threshold
    idle_colour = "green" if st.idle_s < threshold * 0.6 else "yellow" if st.idle_s < threshold else "red"
    grid.add_row("idle", _bar(st.idle_s / threshold, 22, idle_colour) + Text(f" {st.idle_s:5.1f}s / {threshold:.0f}s"))
    grace = st.timings.distraction_grace
    if st.distracted_s > 0:
        grid.add_row(
            "distracted",
            _bar(st.distracted_s / grace, 22, "red") + Text(f" {st.distracted_s:5.1f}s / {grace:.0f}s  mouse moving ≠ work", style="red"),
        )
    else:
        grid.add_row("distracted", Text("—  nothing distracting in focus", style="grey50"))

    level_colours = {1: "yellow", 2: "dark_orange", 3: "red"}
    meter = Text()
    for i in range(1, MAX_LEVEL + 1):
        meter += Text(" ▰▰▰ ", style=f"bold {level_colours[i]}" if i <= st.level else "grey30")
    grid.add_row("level", meter + Text(f"  L{st.level} {LEVEL_MOODS[st.level]}", style=level_colours[st.level]))

    def ms(v: int | None) -> str:
        return "—" if v is None else ("cache" if v == 0 else f"{v} ms")

    grid.add_row(
        "latency",
        Text.assemble(
            ("Bulbul first audio ", "grey62"), (ms(st.tts_ms), "bold cyan"),
            ("  ·  Saaras ", "grey62"), (ms(st.stt_ms), "bold cyan"),
            ("  ·  LLM ", "grey62"), (ms(st.llm_ms), "bold cyan"),
        ),
    )
    grid.add_row("", Text(""))
    tally = Text.assemble(
        ("caught ", "grey62"), (f"{st.caught}", "bold red"),
        ("   excuses ", "grey62"), (f"{st.excuses}", "bold magenta"),
        ("   confessions ", "grey62"), (f"{st.confessions}", "bold green"),
        ("   comebacks ", "grey62"), (f"{st.comebacks}", "bold cyan"),
        ("   lies caught ", "grey62"), (f"{st.lies}", "bold red"),
    )
    grid.add_row("session", tally)
    return Panel(grid, title="[bold]vitals", title_align="left", border_style="grey50", box=box.ROUNDED)


def _dialogue(st: Status) -> Panel:
    t = Table.grid(padding=(0, 1))
    t.add_column(width=12, style="bold")
    t.add_column()
    t.add_row(Text(f"{st.persona.emoji} {st.persona.title}", style="bold magenta"), Text(st.last_bot or "…", style="bold white"))
    t.add_row(Text("🗣  You said", style="bold cyan"), Text(st.last_heard or "…", style="italic cyan"))
    intent = Text(st.intent or "—", style="bold yellow")
    if st.intent_source:
        intent += Text(f"   via {st.intent_source}", style="grey62")
    t.add_row(Text("🎯 Intent", style="bold yellow"), intent)
    if st.screen:
        t.add_row(Text("👀 Screen", style="bold red"), Text(st.screen, style="bold red" if st.screen.startswith("🚨") else "grey70"))
    return Panel(t, title="[bold]conversation", title_align="left", box=box.HORIZONTALS, border_style="grey50")


def _log(st: Status) -> Panel:
    lines = Text.from_markup("\n".join(st.events) or "[grey50]waiting…[/]", style="grey70")
    return Panel(lines, title="[bold]log", title_align="left", box=box.HORIZONTALS, border_style="grey35")


def _header(st: Status) -> Table:
    t = Table.grid(expand=True)
    t.add_column()
    t.add_column(justify="right")
    t.add_row(
        Text.assemble(("  मुझे पता है ", "bold white on red"), ("  Mujhe Pata Hai", "bold red"), ("  · your voice focus buddy", "grey62")),
        Text.assemble(
            ("persona ", "grey62"), (f"{st.persona.emoji} {st.persona.title}", "bold magenta"),
            ("  voice ", "grey62"), (st.speaker, "magenta"),
            ("  mode ", "grey62"), (st.mode.upper(), "bold yellow" if st.mode == "demo" else "bold green"),
            ("  ", ""),
        ),
    )
    return t


def render(st: Status) -> RenderableType:
    footer = Text(
        "  Sarvam AI · Bulbul v4 Flash 🔊  Saaras v4 👂  Sarvam-105B 🧠      Ctrl+C to quit",
        style="grey50",
    )
    return Group(_header(st), Text(""), _badge(st), _meters(st), _dialogue(st), _log(st), footer)
