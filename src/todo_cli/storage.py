from __future__ import annotations
import json
import os
from pathlib import Path

from todo_cli.errors import SchemaMismatch, StorageCorrupt, TodoNotFound
from todo_cli.models import Todo

SCHEMA_VERSION = 1


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)

    # -- internal helpers --

    def _read(self) -> tuple[int, list[Todo]]:
        if not self.path.exists():
            return 1, []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise StorageCorrupt(f"Cannot parse {self.path}: {e}") from e
        version = raw.get("version")
        if version != SCHEMA_VERSION:
            raise SchemaMismatch(
                f"{self.path} is schema version {version}, "
                f"this build supports {SCHEMA_VERSION}"
            )
        return raw["next_id"], [Todo.from_dict(d) for d in raw.get("todos", [])]

    def _write(self, next_id: int, todos: list[Todo]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        if self.path.exists():
            backup.write_bytes(self.path.read_bytes())
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {
            "version": SCHEMA_VERSION,
            "next_id": next_id,
            "todos": [t.to_dict() for t in todos],
        }
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    # -- public API --

    def load(self) -> None:
        """Ensure file exists and is parseable. Idempotent."""
        next_id, todos = self._read()
        if not self.path.exists():
            self._write(next_id, todos)

    def get(self, id: int) -> Todo:
        _, todos = self._read()
        for t in todos:
            if t.id == id:
                return t
        raise TodoNotFound(f"No todo with id {id}")

    def add(self, todo: Todo) -> Todo:
        next_id, todos = self._read()
        todo.id = next_id
        todos.append(todo)
        self._write(next_id + 1, todos)
        return todo

    def delete(self, id: int) -> None:
        next_id, todos = self._read()
        for i, t in enumerate(todos):
            if t.id == id:
                del todos[i]
                self._write(next_id, todos)
                return
        raise TodoNotFound(f"No todo with id {id}")
