import asyncio
import json
from datetime import date
from pathlib import Path

import mcp.types as types
import pytest

from todo_cli.errors import BadCommandUsage, TodoNotFound
from todo_cli.mcp_server import (
    build_server,
    tool_add_todo,
    tool_delete_todo,
    tool_edit_todo,
    tool_list_todos,
    tool_mark_done,
    tool_mark_undone,
    tool_note_todo,
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


def test_build_server_constructs(storage: Storage):
    server = build_server(storage)
    assert server is not None


# ---------------------------------------------------------------------------
# Async _call_tool handler tests via request_handlers introspection
# ---------------------------------------------------------------------------

def _call_tool_via_server(server, name: str, arguments: dict) -> list[types.TextContent]:
    """Invoke the registered call_tool handler directly without stdio transport."""
    handler = None
    for req_type, fn in server.request_handlers.items():
        type_name = getattr(req_type, "__name__", str(req_type))
        if "CallTool" in type_name or "tools/call" in str(req_type):
            handler = fn
            break
    assert handler is not None, "call_tool handler not registered"
    request = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=name, arguments=arguments),
    )
    result = asyncio.run(handler(request))
    # Result is a ServerResult; extract content via .root
    if hasattr(result, "root"):
        result = result.root
    return result.content


def test_mcp_call_tool_add_and_show(storage: Storage):
    server = build_server(storage)
    add_content = _call_tool_via_server(server, "add_todo", {"text": "hello"})
    add_payload = json.loads(add_content[0].text)
    assert add_payload["text"] == "hello"
    assert add_payload["id"] == 1

    show_content = _call_tool_via_server(server, "show_todo", {"id": 1})
    show_payload = json.loads(show_content[0].text)
    assert show_payload["text"] == "hello"


def test_mcp_call_tool_returns_error_code_for_not_found(storage: Storage):
    server = build_server(storage)
    content = _call_tool_via_server(server, "show_todo", {"id": 999})
    payload = json.loads(content[0].text)
    assert payload["code"] == "not_found"
    assert "999" in payload["message"]


def test_mcp_call_tool_returns_error_code_for_invalid_args(storage: Storage):
    # Use priority validation (in tool_edit_todo itself) to trigger BadCommandUsage,
    # bypassing MCP's schema-level enum check for the "field" parameter.
    server = build_server(storage)
    _call_tool_via_server(server, "add_todo", {"text": "x"})
    content = _call_tool_via_server(server, "edit_todo", {"id": 1, "field": "priority", "value": "urgent"})
    payload = json.loads(content[0].text)
    assert payload["code"] == "invalid_args"


def test_mcp_call_tool_list_todos(storage: Storage):
    server = build_server(storage)
    _call_tool_via_server(server, "add_todo", {"text": "a"})
    _call_tool_via_server(server, "add_todo", {"text": "b"})
    content = _call_tool_via_server(server, "list_todos", {})
    payload = json.loads(content[0].text)
    assert len(payload) == 2


def test_mcp_call_tool_mark_done_and_undone(storage: Storage):
    server = build_server(storage)
    _call_tool_via_server(server, "add_todo", {"text": "x"})
    done_content = _call_tool_via_server(server, "mark_done", {"id": 1})
    assert json.loads(done_content[0].text)["done"] is True
    undone_content = _call_tool_via_server(server, "mark_undone", {"id": 1})
    assert json.loads(undone_content[0].text)["done"] is False


def test_mcp_call_tool_delete(storage: Storage):
    server = build_server(storage)
    _call_tool_via_server(server, "add_todo", {"text": "x"})
    content = _call_tool_via_server(server, "delete_todo", {"id": 1})
    payload = json.loads(content[0].text)
    assert payload["status"] == "deleted"


def test_mcp_call_tool_edit_due_null(storage: Storage):
    # Covers the `else None` branch in tool_edit_todo when due is cleared
    server = build_server(storage)
    _call_tool_via_server(server, "add_todo", {"text": "x", "due": "2026-06-01"})
    content = _call_tool_via_server(server, "edit_todo", {"id": 1, "field": "due", "value": ""})
    payload = json.loads(content[0].text)
    assert payload["due"] is None


def test_mcp_call_tool_edit_tags_as_string(storage: Storage):
    # Covers the str-split branch in tool_edit_todo for tags
    server = build_server(storage)
    _call_tool_via_server(server, "add_todo", {"text": "x"})
    content = _call_tool_via_server(server, "edit_todo", {"id": 1, "field": "tags", "value": "work, home"})
    payload = json.loads(content[0].text)
    assert payload["tags"] == ["work", "home"]


def test_mcp_call_tool_unknown_tool_returns_error_result(storage: Storage):
    # MCP SDK 1.27 catches unknown tools before our handler and returns isError=True
    # rather than raising an exception.
    handler = None
    server = build_server(storage)
    for req_type, fn in server.request_handlers.items():
        type_name = getattr(req_type, "__name__", str(req_type))
        if "CallTool" in type_name:
            handler = fn
            break
    assert handler is not None
    request = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name="nonexistent_tool", arguments={}),
    )
    result = asyncio.run(handler(request))
    if hasattr(result, "root"):
        result = result.root
    assert result.isError is True


# ---------------------------------------------------------------------------
# New-field coverage: description, due_time, note_todo
# ---------------------------------------------------------------------------

def test_add_todo_with_description(storage: Storage):
    result = tool_add_todo(storage, {"text": "x", "description": "long context"})
    assert result["description"] == "long context"


def test_add_todo_with_due_time(storage: Storage):
    result = tool_add_todo(storage, {
        "text": "meeting", "due": "2026-05-15", "due_time": "17:00",
    })
    assert result["due_time"] == "17:00"


def test_edit_todo_description(storage: Storage):
    tool_add_todo(storage, {"text": "x"})
    result = tool_edit_todo(storage, {"id": 1, "field": "description", "value": "new"})
    assert result["description"] == "new"


def test_edit_todo_due_time(storage: Storage):
    tool_add_todo(storage, {"text": "x"})
    result = tool_edit_todo(storage, {"id": 1, "field": "due_time", "value": "09:30"})
    assert result["due_time"] == "09:30"


def test_edit_todo_due_time_clear(storage: Storage):
    tool_add_todo(storage, {"text": "x", "due_time": "09:30"})
    result = tool_edit_todo(storage, {"id": 1, "field": "due_time", "value": None})
    assert result["due_time"] is None


def test_edit_todo_claude_session(storage: Storage):
    tool_add_todo(storage, {"text": "x"})
    result = tool_edit_todo(
        storage, {"id": 1, "field": "claude_session", "value": "todo-1-abc12345"}
    )
    assert result["claude_session"] == "todo-1-abc12345"


def test_note_todo_appends_to_empty_description(storage: Storage):
    tool_add_todo(storage, {"text": "x"})
    result = tool_note_todo(storage, {"id": 1, "text": "first note"})
    assert "first note" in result["description"]
    assert "[" in result["description"]  # timestamp


def test_note_todo_does_not_clobber(storage: Storage):
    tool_add_todo(storage, {"text": "x", "description": "kept"})
    result = tool_note_todo(storage, {"id": 1, "text": "appended"})
    assert "kept" in result["description"]
    assert "appended" in result["description"]


def test_note_todo_via_call_tool(storage: Storage):
    server = build_server(storage)
    _call_tool_via_server(server, "add_todo", {"text": "x"})
    content = _call_tool_via_server(
        server, "note_todo", {"id": 1, "text": "logged note"}
    )
    payload = json.loads(content[0].text)
    assert "logged note" in payload["description"]
