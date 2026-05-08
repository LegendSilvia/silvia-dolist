from __future__ import annotations
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from todo_cli.errors import BadCommandUsage, SchemaMismatch, StorageCorrupt, TodoNotFound
from todo_cli.models import Todo

SCHEMA_VERSION = 1


if sys.platform == "win32":
    import msvcrt

    def _platform_lock(fp) -> None:
        while True:
            try:
                msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.01)

    def _platform_unlock(fp) -> None:
        try:
            fp.seek(0)
            msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _platform_lock(fp) -> None:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)

    def _platform_unlock(fp) -> None:
        fcntl.flock(fp.fileno(), fcntl.LOCK_UN)


class Storage:
    def __init__(self, path: Path):
        self.path = Path(path)

    # -- internal helpers --

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.with_suffix(self.path.suffix + ".lock")
        with open(lock_file, "a+b") as fp:
            _platform_lock(fp)
            try:
                yield
            finally:
                _platform_unlock(fp)

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
        with self._locked():
            next_id, todos = self._read()
            if not self.path.exists():
                self._write(next_id, todos)

    def get(self, id: int) -> Todo:
        with self._locked():
            _, todos = self._read()
            for t in todos:
                if t.id == id:
                    return t
            raise TodoNotFound(f"No todo with id {id}")

    def add(self, todo: Todo) -> Todo:
        with self._locked():
            next_id, todos = self._read()
            todo.id = next_id
            todos.append(todo)
            self._write(next_id + 1, todos)
            return todo

    def delete(self, id: int) -> None:
        with self._locked():
            next_id, todos = self._read()
            for i, t in enumerate(todos):
                if t.id == id:
                    del todos[i]
                    self._write(next_id, todos)
                    return
            raise TodoNotFound(f"No todo with id {id}")

    _UPDATABLE_FIELDS = {"text", "done", "due", "due_time", "priority", "tags", "project", "description", "claude_session"}

    def update(self, id: int, **fields) -> Todo:
        for k in fields:
            if k not in self._UPDATABLE_FIELDS:
                raise BadCommandUsage(f"Cannot update field: {k}")
        with self._locked():
            next_id, todos = self._read()
            for t in todos:
                if t.id == id:
                    for k, v in fields.items():
                        setattr(t, k, v)
                    if "done" in fields:
                        t.completed_at = datetime.now() if fields["done"] else None
                    self._write(next_id, todos)
                    return t
            raise TodoNotFound(f"No todo with id {id}")

    def list(
        self,
        *,
        done: bool | None = None,
        tag: str | None = None,
        project: str | None = None,
        overdue: bool = False,
        today: bool = False,
    ) -> list[Todo]:
        from datetime import date as _date

        with self._locked():
            _, todos = self._read()
        results = list(todos)
        if done is not None:
            results = [t for t in results if t.done == done]
        if tag is not None:
            results = [t for t in results if tag in t.tags]
        if project is not None:
            results = [t for t in results if t.project == project]
        if overdue:
            cutoff = _date.today()
            results = [
                t for t in results
                if t.due is not None and t.due < cutoff and not t.done
            ]
        if today:
            cutoff = _date.today()
            results = [t for t in results if t.due == cutoff]
        return results
