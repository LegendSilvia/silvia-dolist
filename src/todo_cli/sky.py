"""Decorative landscape with sun, moon, stars, clouds, and a clock.

Used as the top panel of the TUI. Sun rises at 6 and sets at 18 in a
parabolic arc. Moon does the inverse arc through the night. Daytime
gets clouds scattered around; night gets a dense field of stars.
Positions are seeded by date so they stay still between renders.
"""
from __future__ import annotations
import math
import random
from datetime import datetime
from typing import Optional

from rich.text import Text

SKY_HEIGHT = 4

_STAR_CHARS = (".", "·", "*", "+", "'", ",", "✦", "✧")
_CLOUD_CHUNKS = ("▓▓▓", "▓▓▓▓", "▓▓", "▓▓▓▓▓")
_SKY_FILL = "▒"  # square of dots — the "many-dot square" texture

# Subdued sky tones so the texture reads as atmosphere, not a solid bar.
_FG_DAY = "rgb(150,180,210)"
_FG_NIGHT = "rgb(50,70,120)"


def _arc_position(t: float, width: int, sky_h: int) -> tuple[int, int]:
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
        if grid[r][c][0] != _SKY_FILL:
            continue
        ch = rng.choice(_STAR_CHARS)
        style = "bold rgb(255,245,200)" if ch in ("✦", "✧", "*") else "rgb(220,220,200)"
        grid[r][c] = (ch, style)


def _scatter_clouds(
    grid: list[list[tuple[str, str]]],
    seed: int,
    coverage: float,
) -> None:
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows == 0 or cols == 0:
        return
    rng = random.Random(seed + 1)
    target = int(cols * coverage)
    placed = 0
    attempts = 0
    while placed < target and attempts < 50:
        attempts += 1
        chunk = rng.choice(_CLOUD_CHUNKS)
        r = rng.choice([0, 0, 1, 1, 2])
        c = rng.randrange(0, max(1, cols - len(chunk)))
        if any(grid[r][c + i][0] != _SKY_FILL for i in range(len(chunk))):
            continue
        for i, ch in enumerate(chunk):
            grid[r][c + i] = (ch, "rgb(245,245,250)")
        placed += len(chunk)


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

    fill_style = _FG_NIGHT if is_night else _FG_DAY
    grid: list[list[tuple[str, str]]] = [
        [(_SKY_FILL, fill_style) for _ in range(width)] for _ in range(SKY_HEIGHT)
    ]

    seed = now.year * 10000 + now.month * 100 + now.day
    if is_night:
        _scatter_stars(grid, seed, density=0.12)
    else:
        _scatter_clouds(grid, seed, coverage=0.25)

    sun = _sun_position(hour, width, SKY_HEIGHT)
    if sun is not None:
        r, c = sun
        grid[r][c] = ("☀", "bold rgb(255,210,80)")

    moon = _moon_position(hour, width, SKY_HEIGHT)
    if moon is not None:
        r, c = moon
        grid[r][c] = ("☾", "bold rgb(245,245,230)")

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
