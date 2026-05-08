from __future__ import annotations
from datetime import date, datetime, time

from todo_cli.ask import _build_claude_args, build_prompt, new_session_name
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


def test_prompt_asks_for_full_list_context():
    p = build_prompt(_make_todo())
    assert "list_todos" in p


def test_new_session_name_starts_with_todo_id():
    name = new_session_name(_make_todo())
    assert name.startswith("todo-1-")
    # Suffix is uuid-derived hex chars
    assert len(name) == len("todo-1-") + 8


def test_build_claude_args_fresh_session():
    args = _build_claude_args(prompt="hi", session_name="todo-1-abc", resume_session=None)
    assert args[0] == "claude"
    assert "-n" in args
    assert "todo-1-abc" in args
    assert "hi" in args


def test_build_claude_args_resume_skips_prompt():
    args = _build_claude_args(prompt="hi", session_name=None, resume_session="todo-1-abc")
    assert args[0] == "claude"
    assert "--resume" in args
    assert "todo-1-abc" in args
    assert "hi" not in args


def test_build_claude_args_no_session_no_prompt():
    assert _build_claude_args(None, None, None) == ["claude"]
