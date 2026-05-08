"""Decorative landscape with sun, moon, stars, and a clock.

Used as the top panel of the TUI. Sun rises at 6 and sets at 18 in a
parabolic arc. Moon does the inverse arc through the night. Stars only
appear when the sun is down. Star positions are seeded by date so they
don't jitter between renders.
"""
from __future__ import annotations
import math
import random
from datetime import datetime
from typing import Optional

from rich.text import Text

SKY_HEIGHT = 4

_STAR_CHARS = (".", "·", "*", "+", "'", ",")


def _arc_position(t: float, width: int, sky_h: int) -> tuple[int, int]:
    """Map a 0..1 progression along an arc to (row, col)."""
    col = max(0, min(width - 1, int(t * (width - 1))))
    elev = math.sin(t * math.pi)
    row = max(0, min(sky_h - 1, int((1 - elev) * (sky_h - 1))))
    return row, col


def _sun_position(hour: float, width: int, sky_h: int) -> Optional[tuple[int, int]]:
    if not (6.0 <= hour <= 18.0):
        return None
    return _arc_position((hour - 6.0) / 12.0, width, sky_h)


def _moon_position(hour: float, width: int, sky_h: int) -> Optional[tuple[int, int]]:
    if 6.0 <= hour <= 18.0:
        return None
    t = (hour + 6.0) / 12.0 if hour < 6.0 else (hour - 18.0) / 12.0
    return _arc_position(t, width, sky_h)


def _scatter_stars(
    grid: list[list[tuple[str, str]]],
    seed: int,
    density: float,
) -> None:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows == 0 or cols == 0:
        return
    rng = random.Random(seed)
    n = max(1, int(rows * cols * density))
    for _ in range(n):
        r = rng.randrange(rows)
        c = rng.randrange(cols)
        if grid[r][c][0] != " ":
            continue
        grid[r][c] = (rng.choice(_STAR_CHARS), "ansibrightblack")


def _horizon_line(width: int, seed: int) -> Text:
    rng = random.Random(seed)
    pieces: list[tuple[str, str]] = []
    i = 0
    while i < width:
        roll = rng.random()
        if roll < 0.10 and i + 2 <= width:
            pieces.append(("/\\", "green"))
            i += 2
        elif roll < 0.20 and i + 3 <= width:
            pieces.append(("/^\\", "green"))
            i += 3
        else:
            pieces.append(("▁", "green"))
            i += 1
    text = Text()
    for chars, style in pieces:
        text.append(chars, style=style)
    return text


def render_sky(now: Optional[datetime] = None, width: int = 80) -> Text:
    if now is None:
        now = datetime.now()
    width = max(30, width)
    hour = now.hour + now.minute / 60.0
    is_night = hour < 6.0 or hour >= 18.0

    grid: list[list[tuple[str, str]]] = [
        [(" ", "")] * width for _ in range(SKY_HEIGHT)
    ]

    seed = now.year * 10000 + now.month * 100 + now.day
    if is_night:
        _scatter_stars(grid, seed, density=0.05)

    sun = _sun_position(hour, width, SKY_HEIGHT)
    if sun is not None:
        r, c = sun
        grid[r][c] = ("☀", "bold yellow")

    moon = _moon_position(hour, width, SKY_HEIGHT)
    if moon is not None:
        r, c = moon
        grid[r][c] = ("☾", "bold bright_white")

    # Clock in top-right corner
    time_str = now.strftime("%H:%M")
    start_col = width - len(time_str) - 1
    if start_col >= 0:
        for i, ch in enumerate(time_str):
            grid[0][start_col + i] = (ch, "bold cyan")

    text = Text()
    for row_idx, row in enumerate(grid):
        for char, style in row:
            text.append(char, style=style)
        if row_idx < len(grid) - 1:
            text.append("\n")
    text.append("\n")
    text.append(_horizon_line(width, seed))
    return text
