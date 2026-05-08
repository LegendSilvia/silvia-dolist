from __future__ import annotations
from datetime import date, datetime, time

from todo_cli.ask import build_prompt
from todo_cli.models import Todo


def _make_todo(**overrides) -> Todo:
    base = dict(
        id=1,
        text="finish report",
        created_at=datetime(2026, 5, 8, 9, 0),
    )
    base.update(overrides)
    return Todo(**base)


def test_prompt_includes_title():
    p = build_prompt(_make_todo())
    assert "finish report" in p


def test_prompt_includes_description():
    p = build_prompt(_make_todo(description="needs to cover Q2 metrics"))
    assert "needs to cover Q2 metrics" in p


def test_prompt_includes_due_date():
    p = build_prompt(_make_todo(due=date(2026, 5, 15)))
    assert "2026-05-15" in p


def test_prompt_includes_due_time_when_set():
    p = build_prompt(_make_todo(due=date(2026, 5, 15), due_time=time(17, 0)))
    assert "17:00" in p


def test_prompt_includes_tags_and_project():
    p = build_prompt(_make_todo(tags=["work", "urgent"], project="q2"))
    assert "work" in p
    assert "urgent" in p
    assert "q2" in p


def test_prompt_minimal_todo():
    # No optional fields — should still be a coherent prompt
    p = build_prompt(_make_todo())
    assert "finish report" in p
    assert "Title" in p
