from __future__ import annotations
from datetime import date, datetime
from typing import Any

from todo_cli.errors import BadCommandUsage
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
