from __future__ import annotations
import io
from datetime import datetime

from rich.console import Console

from todo_cli.sky import render_sky


def _to_str(now: datetime, width: int = 80) -> str:
    buf = io.StringIO()
    Console(file=buf, force_terminal=False, width=width).print(render_sky(now, width=width))
    return buf.getvalue()


def test_clock_shows_in_panel():
    s = _to_str(datetime(2026, 5, 8, 14, 37))
    assert "14:37" in s


def test_sun_visible_at_noon():
    s = _to_str(datetime(2026, 5, 8, 12, 0))
    assert "☀" in s
    assert "☾" not in s


def test_moon_visible_at_night():
    s = _to_str(datetime(2026, 5, 8, 22, 0))
    assert "☾" in s
    assert "☀" not in s


def test_horizon_line_present():
    s = _to_str(datetime(2026, 5, 8, 12, 0))
    # Either grass underline or hill peaks
    assert "▁" in s or "/\\" in s


def test_stars_only_at_night():
    night = _to_str(datetime(2026, 5, 8, 23, 0))
    day = _to_str(datetime(2026, 5, 8, 12, 0))
    star_chars = [".", "·", "*", "+", "'", ","]
    night_stars = sum(night.count(c) for c in star_chars)
    day_stars = sum(day.count(c) for c in star_chars)
    assert night_stars > day_stars


def test_deterministic_for_same_day():
    a = _to_str(datetime(2026, 5, 8, 23, 0))
    b = _to_str(datetime(2026, 5, 8, 23, 0))
    assert a == b
