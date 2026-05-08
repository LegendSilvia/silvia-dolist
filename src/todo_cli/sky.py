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

# Background colors, picked to read like a sky:
#   day: light sky-cyan
#   night: deep midnight blue
_BG_DAY = "on rgb(135,206,235)"
_BG_NIGHT = "on rgb(20,28,80)"
_BG_TWILIGHT = "on rgb(95,80,140)"


def _sky_bg(hour: float) -> str:
    if 6.5 <= hour <= 17.5:
        return _BG_DAY
    if 5.5 <= hour < 6.5 or 17.5 < hour < 18.5:
        return _BG_TWILIGHT
    return _BG_NIGHT


def _merge(fg: str, bg: str) -> str:
    return f"{fg} {bg}".strip() if fg else bg


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
    bg: str,
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
        grid[r][c] = (rng.choice(_STAR_CHARS), _merge("rgb(255,245,200)", bg))


def _horizon_line(width: int, seed: int, ground_bg: str) -> Text:
    rng = random.Random(seed)
    pieces: list[tuple[str, str]] = []
    i = 0
    fg = "rgb(40,90,40)"
    while i < width:
        roll = rng.random()
        if roll < 0.10 and i + 2 <= width:
            pieces.append(("/\\", _merge(fg, ground_bg)))
            i += 2
        elif roll < 0.20 and i + 3 <= width:
            pieces.append(("/^\\", _merge(fg, ground_bg)))
            i += 3
        else:
            pieces.append(("▁", _merge(fg, ground_bg)))
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
    bg = _sky_bg(hour)

    grid: list[list[tuple[str, str]]] = [
        [(" ", bg)] * width for _ in range(SKY_HEIGHT)
    ]

    seed = now.year * 10000 + now.month * 100 + now.day
    if is_night:
        _scatter_stars(grid, seed, density=0.05, bg=bg)

    sun = _sun_position(hour, width, SKY_HEIGHT)
    if sun is not None:
        r, c = sun
        grid[r][c] = ("☀", _merge("bold rgb(255,210,80)", bg))

    moon = _moon_position(hour, width, SKY_HEIGHT)
    if moon is not None:
        r, c = moon
        grid[r][c] = ("☾", _merge("bold rgb(245,245,230)", bg))

    # Clock in top-right corner
    time_str = now.strftime("%H:%M")
    clock_fg = "bold rgb(20,28,80)" if not is_night else "bold rgb(255,245,200)"
    start_col = width - len(time_str) - 1
    if start_col >= 0:
        for i, ch in enumerate(time_str):
            grid[0][start_col + i] = (ch, _merge(clock_fg, bg))

    text = Text()
    for row_idx, row in enumerate(grid):
        for char, style in row:
            text.append(char, style=style)
        if row_idx < len(grid) - 1:
            text.append("\n")
    text.append("\n")
    ground_bg = "on rgb(35,55,30)"
    text.append(_horizon_line(width, seed, ground_bg))
    return text
