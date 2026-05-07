from __future__ import annotations
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from todo_cli.errors import BadCommandUsage, TodoError
from todo_cli.models import Todo
from todo_cli.storage import Storage


def tool_add_todo(storage: Storage, args: dict[str, Any]) -> dict[str, Any]:
    text = args["text"]
    due = date.fromisoformat(args["due"]) if args.get("due") else None
    priority = args.get("priority")
    tags = list(args.get("tags") or [])
    project = args.get("project")
    todo = Todo(
        id=0,
        text=text,
        created_at=datetime.now(),
        due=due,
        priority=priority,
        tags=tags,
        project=project,
    )
    storage.add(todo)
    return todo.to_dict()


def tool_list_todos(storage: Storage, args: dict[str, Any]) -> list[dict[str, Any]]:
    todos = storage.list(
        done=args.get("done"),
        tag=args.get("tag"),
        project=args.get("project"),
        overdue=bool(args.get("overdue", False)),
        today=bool(args.get("today", False)),
    )
    return [t.to_dict() for t in todos]


def tool_show_todo(storage: Storage, args: dict[str, Any]) -> dict[str, Any]:
    return storage.get(int(args["id"])).to_dict()


def tool_mark_done(storage: Storage, args: dict[str, Any]) -> dict[str, Any]:
    return storage.update(int(args["id"]), done=True).to_dict()


def tool_mark_undone(storage: Storage, args: dict[str, Any]) -> dict[str, Any]:
    return storage.update(int(args["id"]), done=False).to_dict()


def tool_edit_todo(storage: Storage, args: dict[str, Any]) -> dict[str, Any]:
    field = args["field"]
    value = args["value"]
    if field == "due":
        value = date.fromisoformat(value) if value else None
    elif field == "priority":
        if value not in {"low", "med", "high"}:
            raise BadCommandUsage("priority must be low, med, or high")
    elif field == "tags":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
    return storage.update(int(args["id"]), **{field: value}).to_dict()


def tool_delete_todo(storage: Storage, args: dict[str, Any]) -> dict[str, Any]:
    storage.delete(int(args["id"]))
    return {"status": "deleted", "id": int(args["id"])}


_TOOL_DEFINITIONS: list[types.Tool] = [
    types.Tool(
        name="list_todos",
        description="List todos with optional filters.",
        inputSchema={
            "type": "object",
            "properties": {
                "done": {"type": "boolean"},
                "tag": {"type": "string"},
                "project": {"type": "string"},
                "overdue": {"type": "boolean"},
                "today": {"type": "boolean"},
            },
        },
    ),
    types.Tool(
        name="add_todo",
        description="Create a new todo.",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "due": {"type": "string", "format": "date"},
                "priority": {"type": "string", "enum": ["low", "med", "high"]},
                "tags": {"type": "array", "items": {"type": "string"}},
                "project": {"type": "string"},
            },
            "required": ["text"],
        },
    ),
    types.Tool(
        name="show_todo",
        description="Get a single todo by id.",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="mark_done",
        description="Mark a todo complete.",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="mark_undone",
        description="Mark a todo incomplete.",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    ),
    types.Tool(
        name="edit_todo",
        description="Edit one field of a todo.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "field": {
                    "type": "string",
                    "enum": ["text", "done", "due", "priority", "tags", "project"],
                },
                "value": {},
            },
            "required": ["id", "field", "value"],
        },
    ),
    types.Tool(
        name="delete_todo",
        description="Delete a todo by id.",
        inputSchema={
            "type": "object",
            "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        },
    ),
]


_TOOL_DISPATCH = {
    "list_todos": tool_list_todos,
    "add_todo": tool_add_todo,
    "show_todo": tool_show_todo,
    "mark_done": tool_mark_done,
    "mark_undone": tool_mark_undone,
    "edit_todo": tool_edit_todo,
    "delete_todo": tool_delete_todo,
}


def build_server(storage: Storage) -> Server:
    server: Server = Server("todo")

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return _TOOL_DEFINITIONS

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        if name not in _TOOL_DISPATCH:
            raise ValueError(f"Unknown tool: {name}")
        try:
            result = _TOOL_DISPATCH[name](storage, arguments)
        except TodoError as e:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": type(e).__name__, "message": str(e)}),
            )]
        return [types.TextContent(type="text", text=json.dumps(result))]

    return server


async def _run() -> None:
    home = Path.home() / ".todo"
    storage = Storage(home / "todos.json")
    storage.load()
    server = build_server(storage)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(_run())
