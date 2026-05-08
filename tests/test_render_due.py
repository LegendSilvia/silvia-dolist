from __future__ import annotations
from datetime import date, datetime, time, timedelta

from todo_cli.render import _due_style, _format_due


NOW = datetime(2026, 5, 8, 12, 0)


def test_format_due_date_only():
    assert "May 08" in _format_due(date(2026, 5, 8))


def test_format_due_with_time():
    formatted = _format_due(date(2026, 5, 8), time(18, 30))
    assert "18:30" in formatted
    assert "May 08" in formatted


def test_overdue_is_red():
    style = _due_style(date(2026, 5, 7), None, now=NOW)
    assert "red" in style


def test_within_one_hour_is_orange():
    style = _due_style(date(2026, 5, 8), time(12, 30), now=NOW)
    # < 1 hour from NOW (12:00)
    assert "rgb(255,140,40)" in style


def test_today_later_is_yellow():
    style = _due_style(date(2026, 5, 8), time(20, 0), now=NOW)
    # 8 hours from NOW
    assert "yellow" in style


def test_tomorrow_is_warm():
    style = _due_style(date(2026, 5, 9), None, now=NOW)
    assert "rgb(220,180,100)" in style


def test_far_future_is_dim():
    style = _due_style(date(2026, 6, 1), None, now=NOW)
    assert "dim" in style.lower()


def test_no_due_is_dim():
    style = _due_style(None, None, now=NOW)
    assert "dim" in style.lower()
