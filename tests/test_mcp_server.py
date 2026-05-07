from datetime import date
from pathlib import Path

import pytest

from todo_cli.errors import BadCommandUsage, TodoNotFound
from todo_cli.mcp_server import (
    tool_add_todo,
    tool_delete_todo,
    tool_edit_todo,
    tool_list_todos,
    tool_mark_done,
    tool_mark_undone,
    tool_show_todo,
)
from todo_cli.storage import Storage


@pytest.fixture
def storage(storage_path: Path) -> Storage:
    s = Storage(storage_path)
    s.load()
    return s


def test_add_todo_returns_dict_with_id(storage: Storage):
    result = tool_add_todo(storage, {"text": "hello"})
    assert isinstance(result, dict)
    assert result["id"] == 1
    assert result["text"] == "hello"


def test_add_todo_full_fields(storage: Storage):
    result = tool_add_todo(storage, {
        "text": "complex",
        "due": "2026-06-01",
        "priority": "high",
        "tags": ["work"],
        "project": "q3",
    })
    assert result["due"] == "2026-06-01"
    assert result["priority"] == "high"
    assert result["tags"] == ["work"]


def test_list_todos_default(storage: Storage):
    tool_add_todo(storage, {"text": "a"})
    tool_add_todo(storage, {"text": "b"})
    out = tool_list_todos(storage, {})
    assert len(out) == 2


def test_list_todos_with_filters(storage: Storage):
    tool_add_todo(storage, {"text": "w", "tags": ["work"]})
    tool_add_todo(storage, {"text": "h", "tags": ["home"]})
    out = tool_list_todos(storage, {"tag": "work"})
    assert len(out) == 1
    assert out[0]["text"] == "w"


def test_mark_done_and_undone(storage: Storage):
    tool_add_todo(storage, {"text": "x"})
    tool_mark_done(storage, {"id": 1})
    assert tool_show_todo(storage, {"id": 1})["done"] is True
    tool_mark_undone(storage, {"id": 1})
    assert tool_show_todo(storage, {"id": 1})["done"] is False


def test_edit_todo(storage: Storage):
    tool_add_todo(storage, {"text": "old"})
    out = tool_edit_todo(storage, {"id": 1, "field": "text", "value": "new"})
    assert out["text"] == "new"


def test_delete_todo(storage: Storage):
    tool_add_todo(storage, {"text": "x"})
    tool_delete_todo(storage, {"id": 1})
    with pytest.raises(TodoNotFound):
        tool_show_todo(storage, {"id": 1})


def test_show_missing_raises(storage: Storage):
    with pytest.raises(TodoNotFound):
        tool_show_todo(storage, {"id": 999})


def test_edit_unknown_field_raises(storage: Storage):
    tool_add_todo(storage, {"text": "x"})
    with pytest.raises(BadCommandUsage):
        tool_edit_todo(storage, {"id": 1, "field": "banana", "value": "y"})
