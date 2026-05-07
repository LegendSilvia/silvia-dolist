# CLI Todo App Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the phase-1 CLI todo app: a persistent-REPL Python tool with rich output, JSON storage, fuzzy-suggest, and an MCP stdio server — all in one installable package, fully tested.

**Architecture:** Stateless `Storage` class is the only owner of `todos.json`; every public method does an atomic load-modify-save under a file lock. `commands.py` registers handlers in a dict keyed by slash-name; `repl.py` and `mcp_server.py` are thin surfaces that share the same `Storage`. All AI is deferred to phase 2.

**Tech Stack:** Python ≥3.11, `prompt_toolkit`, `rich`, `mcp`, `pytest`, `pytest-cov`. Stdlib only for storage, locking, fuzzy match, argparse, json, dataclasses.

---

## File Structure

Files created in this plan (all paths relative to `C:\Development\todo-cli\`):

```
pyproject.toml
.gitignore
README.md
src/todo_cli/__init__.py
src/todo_cli/__main__.py
src/todo_cli/errors.py
src/todo_cli/models.py
src/todo_cli/storage.py
src/todo_cli/config.py
src/todo_cli/suggest.py
src/todo_cli/render.py
src/todo_cli/commands.py
src/todo_cli/repl.py
src/todo_cli/mcp_server.py
tests/__init__.py
tests/conftest.py
tests/test_errors.py
tests/test_models.py
tests/test_storage.py
tests/test_config.py
tests/test_suggest.py
tests/test_render.py
tests/test_commands.py
tests/test_repl.py
tests/test_mcp_server.py
```

Single responsibility per file (see spec § Module boundaries). `commands.py`, `storage.py`, and `mcp_server.py` are the only modules with non-trivial logic.

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/todo_cli/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "todo-cli"
version = "0.1.0"
description = "Personal todo CLI with REPL and MCP server"
requires-python = ">=3.11"
dependencies = [
    "prompt_toolkit>=3.0",
    "rich>=13.7",
    "mcp>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]

[project.scripts]
todo = "todo_cli.__main__:main"
todo-mcp = "todo_cli.mcp_server:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=todo_cli --cov-report=term-missing"
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
build/
dist/
.venv/
```

- [ ] **Step 3: Create empty package files**

`src/todo_cli/__init__.py` (empty file).
`tests/__init__.py` (empty file).

- [ ] **Step 4: Create `tests/conftest.py`**

```python
from pathlib import Path
import pytest


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "todos.json"
```

- [ ] **Step 5: Create venv and install in editable mode**

Run from `C:\Development\todo-cli`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

Expected: `Successfully installed todo-cli-0.1.0` and dev deps. No errors.

- [ ] **Step 6: Verify pytest discovers tests directory (no tests yet, expect 0 collected)**

```powershell
pytest --collect-only
```

Expected: `no tests ran in 0.00s` or `collected 0 items` with exit code 5 (no tests collected) — both acceptable. No import errors.

- [ ] **Step 7: Commit**

```powershell
git add pyproject.toml .gitignore src/todo_cli/__init__.py tests/__init__.py tests/conftest.py
git commit -m "chore: project scaffolding"
```

---

## Task 2: Exception Hierarchy (`errors.py`)

**Files:**
- Create: `src/todo_cli/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_errors.py`:

```python
import pytest
from todo_cli.errors import (
    TodoError,
    TodoNotFound,
    StorageCorrupt,
    SchemaMismatch,
    BadCommandUsage,
)


def test_subclasses_inherit_from_todo_error():
    assert issubclass(TodoNotFound, TodoError)
    assert issubclass(StorageCorrupt, TodoError)
    assert issubclass(SchemaMismatch, TodoError)
    assert issubclass(BadCommandUsage, TodoError)


def test_can_catch_subclass_as_base():
    with pytest.raises(TodoError):
        raise TodoNotFound("nope")


def test_message_round_trip():
    e = TodoNotFound("missing 7")
    assert str(e) == "missing 7"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_errors.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.errors'`.

- [ ] **Step 3: Implement `errors.py`**

`src/todo_cli/errors.py`:

```python
class TodoError(Exception):
    """Base exception for todo_cli."""


class TodoNotFound(TodoError):
    """Requested todo id does not exist."""


class StorageCorrupt(TodoError):
    """Storage file is unparseable."""


class SchemaMismatch(TodoError):
    """Storage file is a version this build does not support."""


class BadCommandUsage(TodoError):
    """User supplied invalid arguments to a command."""
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_errors.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/errors.py tests/test_errors.py
git commit -m "feat: typed exception hierarchy"
```

---

## Task 3: Todo Data Model (`models.py`)

**Files:**
- Create: `src/todo_cli/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:

```python
from datetime import date, datetime
from todo_cli.models import Todo


def test_minimal_todo_round_trip():
    t = Todo(id=1, text="buy milk", created_at=datetime(2026, 5, 7, 12, 0, 0))
    d = t.to_dict()
    assert d["id"] == 1
    assert d["text"] == "buy milk"
    assert d["due"] is None
    assert d["completed_at"] is None
    t2 = Todo.from_dict(d)
    assert t2 == t


def test_full_todo_round_trip():
    t = Todo(
        id=42,
        text="finish report",
        created_at=datetime(2026, 5, 7, 12, 0, 0),
        done=True,
        due=date(2026, 6, 1),
        priority="high",
        tags=["work", "urgent"],
        project="q3",
        completed_at=datetime(2026, 5, 8, 9, 30, 0),
    )
    t2 = Todo.from_dict(t.to_dict())
    assert t2 == t


def test_tags_default_is_independent_list():
    a = Todo(id=1, text="a", created_at=datetime(2026, 1, 1))
    b = Todo(id=2, text="b", created_at=datetime(2026, 1, 1))
    a.tags.append("x")
    assert b.tags == []
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.models'`.

- [ ] **Step 3: Implement `models.py`**

`src/todo_cli/models.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

Priority = Literal["low", "med", "high"]


@dataclass
class Todo:
    id: int
    text: str
    created_at: datetime
    done: bool = False
    due: date | None = None
    priority: Priority | None = None
    tags: list[str] = field(default_factory=list)
    project: str | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "done": self.done,
            "due": self.due.isoformat() if self.due else None,
            "priority": self.priority,
            "tags": list(self.tags),
            "project": self.project,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Todo":
        return cls(
            id=data["id"],
            text=data["text"],
            done=data.get("done", False),
            due=date.fromisoformat(data["due"]) if data.get("due") else None,
            priority=data.get("priority"),
            tags=list(data.get("tags", [])),
            project=data.get("project"),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_models.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/models.py tests/test_models.py
git commit -m "feat: Todo dataclass with JSON round-trip"
```

---

## Task 4: Storage Scaffold (`storage.py`)

Build `Storage` with stateless read-modify-write semantics from day one. Schema-version validation and atomic-write/backup are baked in. No locking yet — added in Task 8.

**Files:**
- Create: `src/todo_cli/storage.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_storage.py`:

```python
import json
from pathlib import Path

import pytest

from todo_cli.errors import SchemaMismatch, StorageCorrupt
from todo_cli.storage import SCHEMA_VERSION, Storage


def test_load_creates_file_when_missing(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    assert storage_path.exists()
    raw = json.loads(storage_path.read_text(encoding="utf-8"))
    assert raw == {"version": SCHEMA_VERSION, "next_id": 1, "todos": []}


def test_load_does_not_overwrite_existing(storage_path: Path):
    storage_path.write_text(
        json.dumps({"version": 1, "next_id": 5, "todos": []}), encoding="utf-8"
    )
    s = Storage(storage_path)
    s.load()
    raw = json.loads(storage_path.read_text(encoding="utf-8"))
    assert raw["next_id"] == 5


def test_load_rejects_corrupt_json(storage_path: Path):
    storage_path.write_text("not json", encoding="utf-8")
    s = Storage(storage_path)
    with pytest.raises(StorageCorrupt):
        s.load()


def test_load_rejects_unknown_version(storage_path: Path):
    storage_path.write_text(
        json.dumps({"version": 99, "next_id": 1, "todos": []}), encoding="utf-8"
    )
    s = Storage(storage_path)
    with pytest.raises(SchemaMismatch):
        s.load()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_storage.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.storage'`.

- [ ] **Step 3: Implement `storage.py` (no locking yet)**

`src/todo_cli/storage.py`:

```python
from __future__ import annotations
import json
import os
from pathlib import Path

from todo_cli.errors import SchemaMismatch, StorageCorrupt
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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_storage.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/storage.py tests/test_storage.py
git commit -m "feat: Storage scaffold with atomic write, backup, schema check"
```

---

## Task 5: Storage CRUD (`get`, `add`, `delete`)

**Files:**
- Modify: `src/todo_cli/storage.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_storage.py`:

```python
from datetime import datetime
from todo_cli.errors import TodoNotFound
from todo_cli.models import Todo


def _make_todo(text: str = "x") -> Todo:
    return Todo(id=0, text=text, created_at=datetime(2026, 1, 1, 0, 0, 0))


def test_add_assigns_monotonic_ids(storage_path: Path):
    s = Storage(storage_path)
    a = s.add(_make_todo("a"))
    b = s.add(_make_todo("b"))
    assert a.id == 1
    assert b.id == 2


def test_add_persists_to_disk(storage_path: Path):
    s1 = Storage(storage_path)
    s1.add(_make_todo("persisted"))
    s2 = Storage(storage_path)
    assert s2.get(1).text == "persisted"


def test_get_returns_todo(storage_path: Path):
    s = Storage(storage_path)
    t = s.add(_make_todo("hello"))
    assert s.get(t.id).text == "hello"


def test_get_missing_raises(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    with pytest.raises(TodoNotFound):
        s.get(999)


def test_delete_removes(storage_path: Path):
    s = Storage(storage_path)
    t = s.add(_make_todo("x"))
    s.delete(t.id)
    with pytest.raises(TodoNotFound):
        s.get(t.id)


def test_delete_missing_raises(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    with pytest.raises(TodoNotFound):
        s.delete(7)
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_storage.py -v
```

Expected: FAIL on the new tests — `AttributeError: 'Storage' object has no attribute 'add'`.

- [ ] **Step 3: Implement CRUD methods**

In `src/todo_cli/storage.py`, update the import line and append public methods:

Add to imports:

```python
from todo_cli.errors import SchemaMismatch, StorageCorrupt, TodoNotFound
```

Append to the `Storage` class:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_storage.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/storage.py tests/test_storage.py
git commit -m "feat: Storage get/add/delete"
```

---

## Task 6: Storage `update`

**Files:**
- Modify: `src/todo_cli/storage.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_storage.py`:

```python
from todo_cli.errors import BadCommandUsage


def test_update_text(storage_path: Path):
    s = Storage(storage_path)
    t = s.add(_make_todo("old"))
    s.update(t.id, text="new")
    assert s.get(t.id).text == "new"


def test_update_done_sets_completed_at(storage_path: Path):
    s = Storage(storage_path)
    t = s.add(_make_todo("x"))
    assert s.get(t.id).completed_at is None
    s.update(t.id, done=True)
    assert s.get(t.id).completed_at is not None
    assert s.get(t.id).done is True


def test_update_undone_clears_completed_at(storage_path: Path):
    s = Storage(storage_path)
    t = s.add(_make_todo("x"))
    s.update(t.id, done=True)
    s.update(t.id, done=False)
    assert s.get(t.id).completed_at is None


def test_update_rejects_unknown_field(storage_path: Path):
    s = Storage(storage_path)
    t = s.add(_make_todo("x"))
    with pytest.raises(BadCommandUsage):
        s.update(t.id, bogus="y")


def test_update_missing_id_raises(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    with pytest.raises(TodoNotFound):
        s.update(999, text="x")
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_storage.py -v
```

Expected: 5 new failures — `AttributeError: 'Storage' object has no attribute 'update'`.

- [ ] **Step 3: Implement `update`**

Update import line in `src/todo_cli/storage.py`:

```python
from todo_cli.errors import BadCommandUsage, SchemaMismatch, StorageCorrupt, TodoNotFound
```

Add to top imports:

```python
from datetime import datetime
```

Append to the `Storage` class:

```python
    _UPDATABLE_FIELDS = {"text", "done", "due", "priority", "tags", "project"}

    def update(self, id: int, **fields) -> Todo:
        for k in fields:
            if k not in self._UPDATABLE_FIELDS:
                raise BadCommandUsage(f"Cannot update field: {k}")
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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_storage.py -v
```

Expected: 15 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/storage.py tests/test_storage.py
git commit -m "feat: Storage update with field whitelist and completed_at sync"
```

---

## Task 7: Storage `list` with filters

**Files:**
- Modify: `src/todo_cli/storage.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_storage.py`:

```python
from datetime import date


def test_list_all(storage_path: Path):
    s = Storage(storage_path)
    s.add(_make_todo("a"))
    s.add(_make_todo("b"))
    assert len(s.list()) == 2


def test_list_filter_done(storage_path: Path):
    s = Storage(storage_path)
    a = s.add(_make_todo("a"))
    s.add(_make_todo("b"))
    s.update(a.id, done=True)
    assert len(s.list(done=True)) == 1
    assert len(s.list(done=False)) == 1


def test_list_filter_tag(storage_path: Path):
    s = Storage(storage_path)
    t = _make_todo("a")
    t.tags = ["work"]
    s.add(t)
    s.add(_make_todo("b"))
    assert [x.text for x in s.list(tag="work")] == ["a"]


def test_list_filter_project(storage_path: Path):
    s = Storage(storage_path)
    t = _make_todo("a")
    t.project = "p1"
    s.add(t)
    s.add(_make_todo("b"))
    assert [x.text for x in s.list(project="p1")] == ["a"]


def test_list_overdue(storage_path: Path):
    s = Storage(storage_path)
    past = _make_todo("a")
    past.due = date(2020, 1, 1)
    future = _make_todo("b")
    future.due = date(2099, 1, 1)
    s.add(past)
    s.add(future)
    assert [x.text for x in s.list(overdue=True)] == ["a"]


def test_list_overdue_excludes_done(storage_path: Path):
    s = Storage(storage_path)
    past = _make_todo("a")
    past.due = date(2020, 1, 1)
    a = s.add(past)
    s.update(a.id, done=True)
    assert s.list(overdue=True) == []


def test_list_today(storage_path: Path):
    s = Storage(storage_path)
    today_t = _make_todo("today")
    today_t.due = date.today()
    other = _make_todo("other")
    other.due = date(2099, 1, 1)
    s.add(today_t)
    s.add(other)
    assert [x.text for x in s.list(today=True)] == ["today"]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_storage.py -v
```

Expected: 7 new failures — `AttributeError: 'Storage' object has no attribute 'list'`.

- [ ] **Step 3: Implement `list`**

Append to the `Storage` class in `src/todo_cli/storage.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_storage.py -v
```

Expected: 22 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/storage.py tests/test_storage.py
git commit -m "feat: Storage list with done/tag/project/overdue/today filters"
```

---

## Task 8: Storage File Locking

Wraps every public mutation/read in an exclusive cross-platform file lock so the REPL and MCP server can run concurrently. Lock is held against a sidecar `.lock` file.

**Files:**
- Modify: `src/todo_cli/storage.py`
- Modify: `tests/test_storage.py`

- [ ] **Step 1: Add the failing concurrency test**

Append to `tests/test_storage.py`:

```python
import threading


def test_concurrent_adds_do_not_lose_writes(storage_path: Path):
    """Two threads each adding 25 todos via separate Storage instances must
    yield 50 distinct todos with monotonic ids and no torn state."""
    Storage(storage_path).load()  # initialize file

    def add_many(prefix: str) -> None:
        s = Storage(storage_path)
        for i in range(25):
            s.add(_make_todo(f"{prefix}-{i}"))

    t1 = threading.Thread(target=add_many, args=("a",))
    t2 = threading.Thread(target=add_many, args=("b",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    final = Storage(storage_path).list()
    ids = sorted(t.id for t in final)
    assert len(final) == 50
    assert ids == list(range(1, 51))
```

- [ ] **Step 2: Run tests to verify the new one fails (or is flaky without locking)**

```powershell
pytest tests/test_storage.py::test_concurrent_adds_do_not_lose_writes -v
```

Expected: FAIL on most runs — count is less than 50 because of lost writes from interleaved load-modify-save cycles.

- [ ] **Step 3: Add the `_locked` context manager and wrap public methods**

In `src/todo_cli/storage.py`, add to top imports:

```python
import sys
import time
from contextlib import contextmanager
from typing import Iterator
```

Add a module-level helper after the imports (and before `class Storage`):

```python
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
```

Add to the `Storage` class (place near the top of the class body, after `__init__`):

```python
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
```

Now wrap each public method body in `with self._locked():`. Replace the existing `load`, `get`, `add`, `delete`, `update`, `list` with these locked versions:

```python
    def load(self) -> None:
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
```

- [ ] **Step 4: Run the full storage test suite**

```powershell
pytest tests/test_storage.py -v
```

Expected: 23 passed (including the concurrency test).

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/storage.py tests/test_storage.py
git commit -m "feat: cross-platform file locking on Storage operations"
```

---

## Task 9: Config (`config.py`)

Phase-1 `Config` is a no-fields dataclass with load/save plumbing, ready for phase-2 keys (`ai_on`, `model`).

**Files:**
- Create: `src/todo_cli/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:

```python
import json
from pathlib import Path

from todo_cli.config import Config


def test_load_returns_default_when_file_missing(tmp_path: Path):
    cfg = Config.load(tmp_path / "config.json")
    assert isinstance(cfg, Config)


def test_save_creates_file(tmp_path: Path):
    cfg = Config()
    p = tmp_path / "config.json"
    cfg.save(p)
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_load_after_save_round_trips(tmp_path: Path):
    p = tmp_path / "config.json"
    Config().save(p)
    cfg2 = Config.load(p)
    assert cfg2 == Config()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.config'`.

- [ ] **Step 3: Implement `config.py`**

`src/todo_cli/config.py`:

```python
from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Config:
    """User settings. Phase 1 has no fields; phase 2 adds ai_on, model."""

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        # Filter to known fields so unknown keys (e.g., from future versions) don't crash
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/config.py tests/test_config.py
git commit -m "feat: Config load/save plumbing (no-fields placeholder)"
```

---

## Task 10: Suggest Layer (`suggest.py`)

**Files:**
- Create: `src/todo_cli/suggest.py`
- Create: `tests/test_suggest.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_suggest.py`:

```python
from todo_cli.suggest import suggest

COMMANDS = [
    "/add", "/list", "/show", "/done", "/undo", "/edit", "/del",
    "/help", "/clear", "/exit", "/quit",
]


def test_close_match_returns_command():
    assert "/list" in suggest("/lst", COMMANDS)


def test_works_without_slash_prefix():
    assert "/list" in suggest("lst", COMMANDS)


def test_no_match_returns_empty():
    assert suggest("xyzzy", COMMANDS) == []


def test_respects_n_limit():
    out = suggest("/de", COMMANDS, n=1)
    assert len(out) <= 1


def test_low_cutoff_lets_more_through():
    out = suggest("hlp", COMMANDS, cutoff=0.4)
    assert "/help" in out
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_suggest.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.suggest'`.

- [ ] **Step 3: Implement `suggest.py`**

`src/todo_cli/suggest.py`:

```python
from __future__ import annotations
import difflib


def suggest(
    token: str,
    commands: list[str],
    n: int = 3,
    cutoff: float = 0.7,
) -> list[str]:
    """Return up to n close matches for token from commands.

    Token may include a leading '/' or not — matching is consistent.
    Returned strings preserve the form (with slash) found in the commands list.
    """
    needle = token.lstrip("/")
    pool = [c.lstrip("/") for c in commands]
    by_pool = {p: c for p, c in zip(pool, commands)}
    matches = difflib.get_close_matches(needle, pool, n=n, cutoff=cutoff)
    return [by_pool[m] for m in matches]
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_suggest.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/suggest.py tests/test_suggest.py
git commit -m "feat: fuzzy command suggestion via difflib"
```

---

## Task 11: Render Helpers (`render.py`)

Pure functions returning Rich renderables. Tests assert no exceptions on edge inputs; visual output is not asserted.

**Files:**
- Create: `src/todo_cli/render.py`
- Create: `tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:

```python
from datetime import date, datetime

from todo_cli.models import Todo
from todo_cli.render import (
    render_error,
    render_info,
    render_todo_detail,
    render_todo_list,
)


def _t(id_: int = 1, **kw) -> Todo:
    base = dict(id=id_, text="x", created_at=datetime(2026, 1, 1, 0, 0, 0))
    base.update(kw)
    return Todo(**base)


def test_render_empty_list_does_not_throw():
    table = render_todo_list([])
    assert table is not None


def test_render_full_list():
    items = [
        _t(1, text="a"),
        _t(2, text="b", priority="high", due=date(2026, 6, 1), tags=["work"]),
    ]
    render_todo_list(items)


def test_render_detail_minimal():
    render_todo_detail(_t(1))


def test_render_detail_full():
    t = _t(
        1,
        text="hello",
        project="proj",
        tags=["a", "b"],
        priority="med",
        due=date(2026, 5, 7),
        done=True,
        completed_at=datetime(2026, 5, 7, 12, 0, 0),
    )
    render_todo_detail(t)


def test_render_unicode_in_text():
    render_todo_list([_t(1, text="café 日本語 🚀")])


def test_render_error_and_info():
    render_error("bad")
    render_info("ok")
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_render.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.render'`.

- [ ] **Step 3: Implement `render.py`**

`src/todo_cli/render.py`:

```python
from __future__ import annotations
from datetime import date as _date

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from todo_cli.models import Todo

_PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2}
_MAX_DATE = _date(9999, 12, 31)


def _sort_key(t: Todo):
    return (
        _PRIORITY_ORDER.get(t.priority or "", 3),
        t.due or _MAX_DATE,
        t.id,
    )


def render_todo_list(todos: list[Todo]) -> Table:
    table = Table(title=f"Todos ({len(todos)})", show_lines=False)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Done", justify="center")
    table.add_column("Pri", justify="center")
    table.add_column("Due")
    table.add_column("Project")
    table.add_column("Tags")
    table.add_column("Text")
    for t in sorted(todos, key=_sort_key):
        table.add_row(
            str(t.id),
            "[green]✓[/green]" if t.done else "",
            (t.priority or "").upper(),
            t.due.isoformat() if t.due else "",
            t.project or "",
            ", ".join(t.tags),
            t.text,
        )
    return table


def render_todo_detail(t: Todo) -> Panel:
    body = Text()
    body.append(f"#{t.id}  ", style="bold cyan")
    body.append(t.text + "\n\n")
    body.append(f"Done: {'yes' if t.done else 'no'}\n")
    body.append(f"Priority: {t.priority or '—'}\n")
    body.append(f"Due: {t.due.isoformat() if t.due else '—'}\n")
    body.append(f"Project: {t.project or '—'}\n")
    body.append(f"Tags: {', '.join(t.tags) or '—'}\n")
    body.append(f"Created: {t.created_at.isoformat()}\n")
    if t.completed_at:
        body.append(f"Completed: {t.completed_at.isoformat()}\n")
    return Panel(body, title=f"Todo #{t.id}")


def render_error(message: str) -> Text:
    return Text(message, style="bold red")


def render_info(message: str) -> Text:
    return Text(message, style="green")
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_render.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/render.py tests/test_render.py
git commit -m "feat: rich renderables for list, detail, error, info"
```

---

## Task 12: Commands Framework + Static Commands

Build the dispatcher (`run_command`, `command` decorator, `_HANDLERS`) and the three trivial handlers (`/help`, `/clear`, `/exit`) in one task. Free-form path is added in Task 19; specific handlers in Tasks 13-18.

**Files:**
- Create: `src/todo_cli/commands.py`
- Create: `tests/test_commands.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_commands.py`:

```python
from pathlib import Path
import pytest

from todo_cli.commands import CommandResult, KNOWN_COMMANDS, run_command
from todo_cli.config import Config
from todo_cli.storage import Storage


@pytest.fixture
def storage(storage_path: Path) -> Storage:
    s = Storage(storage_path)
    s.load()
    return s


@pytest.fixture
def config() -> Config:
    return Config()


def test_known_commands_includes_core(storage: Storage, config: Config):
    for cmd in ["/add", "/list", "/show", "/done", "/undo", "/edit",
                "/del", "/help", "/clear", "/exit", "/quit"]:
        assert cmd in KNOWN_COMMANDS


def test_empty_line_is_noop(storage: Storage, config: Config):
    result = run_command("", storage, config)
    assert result.renderable is None
    assert result.exit is False
    assert result.clear is False


def test_unknown_command_suggests(storage: Storage, config: Config):
    result = run_command("/lst", storage, config)
    assert result.renderable is not None
    rendered = str(result.renderable)
    assert "Unknown command" in rendered
    assert "/list" in rendered


def test_help_returns_renderable(storage: Storage, config: Config):
    result = run_command("/help", storage, config)
    assert result.renderable is not None
    assert "Commands:" in str(result.renderable)


def test_clear_signals_clear(storage: Storage, config: Config):
    result = run_command("/clear", storage, config)
    assert result.clear is True


def test_exit_and_quit_signal_exit(storage: Storage, config: Config):
    assert run_command("/exit", storage, config).exit is True
    assert run_command("/quit", storage, config).exit is True
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.commands'`.

- [ ] **Step 3: Implement framework + static commands**

`src/todo_cli/commands.py`:

```python
from __future__ import annotations
import shlex
from dataclasses import dataclass
from typing import Any, Callable

from todo_cli.config import Config
from todo_cli.errors import TodoError
from todo_cli.storage import Storage
from todo_cli.suggest import suggest
from todo_cli import render


@dataclass
class CommandResult:
    renderable: Any = None
    exit: bool = False
    clear: bool = False


Handler = Callable[[list[str], Storage, Config], CommandResult]
_HANDLERS: dict[str, Handler] = {}


def command(name: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[name] = fn
        return fn
    return deco


KNOWN_COMMANDS: list[str] = [
    "/add", "/list", "/show", "/done", "/undo", "/edit", "/del",
    "/help", "/clear", "/exit", "/quit",
]


def run_command(line: str, storage: Storage, config: Config) -> CommandResult:
    line = line.strip()
    if not line:
        return CommandResult()
    try:
        tokens = shlex.split(line)
    except ValueError as e:
        return CommandResult(renderable=render.render_error(f"Parse error: {e}"))
    head = tokens[0]
    if head.startswith("/"):
        if head not in _HANDLERS:
            matches = suggest(head, KNOWN_COMMANDS)
            hint = f" Did you mean: {', '.join(matches)}?" if matches else ""
            return CommandResult(
                renderable=render.render_error(f"Unknown command: {head}.{hint}")
            )
        try:
            return _HANDLERS[head](tokens[1:], storage, config)
        except TodoError as e:
            return CommandResult(renderable=render.render_error(str(e)))
    return _free_form(line, tokens, storage, config)


def _free_form(line: str, tokens: list[str], storage: Storage, config: Config) -> CommandResult:
    # Placeholder; filled in Task 19.
    return CommandResult(renderable=render.render_error("free-form not yet implemented"))


HELP_TEXT = """\
Commands:
  /add <text> [--due YYYY-MM-DD] [--priority low|med|high] [--tags a,b] [--project p]
  /list [--all] [--done] [--tag X] [--project P] [--overdue] [--today]
  /show <id>
  /done <id>      mark complete
  /undo <id>      mark incomplete
  /edit <id> <field> <value>
  /del <id>       delete
  /help           this list
  /clear          clear screen
  /exit, /quit    save and exit

Free-form text is added as a new todo.
"""


@command("/help")
def _handle_help(args: list[str], storage: Storage, config: Config) -> CommandResult:
    return CommandResult(renderable=render.render_info(HELP_TEXT))


@command("/clear")
def _handle_clear(args: list[str], storage: Storage, config: Config) -> CommandResult:
    return CommandResult(clear=True)


@command("/exit")
@command("/quit")
def _handle_exit(args: list[str], storage: Storage, config: Config) -> CommandResult:
    return CommandResult(exit=True)
```

Note the stacked `@command` decorators on `_handle_exit` register the same function under two names.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: command dispatcher framework + /help, /clear, /exit, /quit"
```

---

## Task 13: `/add` Handler

**Files:**
- Modify: `src/todo_cli/commands.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_commands.py`:

```python
from datetime import date


def test_add_basic(storage: Storage, config: Config):
    result = run_command("/add buy milk", storage, config)
    assert "Added" in str(result.renderable)
    todos = storage.list()
    assert len(todos) == 1
    assert todos[0].text == "buy milk"


def test_add_with_flags(storage: Storage, config: Config):
    run_command(
        '/add "finish report" --due 2026-06-01 --priority high --tags work,urgent --project q3',
        storage, config,
    )
    todo = storage.list()[0]
    assert todo.text == "finish report"
    assert todo.due == date(2026, 6, 1)
    assert todo.priority == "high"
    assert todo.tags == ["work", "urgent"]
    assert todo.project == "q3"


def test_add_missing_text_errors(storage: Storage, config: Config):
    result = run_command("/add", storage, config)
    rendered = str(result.renderable)
    assert "/add" in rendered or "usage" in rendered.lower()


def test_add_invalid_priority_errors(storage: Storage, config: Config):
    result = run_command("/add foo --priority extreme", storage, config)
    rendered = str(result.renderable)
    assert "priority" in rendered.lower() or "invalid" in rendered.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v -k add
```

Expected: 4 new failures.

- [ ] **Step 3: Implement `/add`**

Append to `src/todo_cli/commands.py`:

```python
import argparse
from datetime import date, datetime

from todo_cli.errors import BadCommandUsage
from todo_cli.models import Todo


def _parse_or_raise(parser: argparse.ArgumentParser, args: list[str]):
    try:
        return parser.parse_args(args)
    except argparse.ArgumentError as e:
        raise BadCommandUsage(f"{parser.prog}: {e}") from e
    except SystemExit as e:
        # exit_on_error=False stops most exits, but argparse may still raise
        # SystemExit on -h or required-arg failures depending on version.
        raise BadCommandUsage(f"{parser.prog}: invalid arguments") from e


def _add_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="/add", exit_on_error=False, add_help=False,
    )
    p.add_argument("text", nargs="+")
    p.add_argument("--due", type=date.fromisoformat, default=None)
    p.add_argument("--priority", choices=["low", "med", "high"], default=None)
    p.add_argument("--tags", default="")
    p.add_argument("--project", default=None)
    return p


@command("/add")
def _handle_add(args: list[str], storage: Storage, config: Config) -> CommandResult:
    ns = _parse_or_raise(_add_parser(), args)
    text = " ".join(ns.text)
    tags = [t.strip() for t in ns.tags.split(",") if t.strip()]
    todo = Todo(
        id=0,
        text=text,
        created_at=datetime.now(),
        due=ns.due,
        priority=ns.priority,
        tags=tags,
        project=ns.project,
    )
    storage.add(todo)
    return CommandResult(renderable=render.render_info(f"Added #{todo.id}: {text}"))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: /add command with flag parsing"
```

---

## Task 14: `/list` Handler

**Files:**
- Modify: `src/todo_cli/commands.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_commands.py`:

```python
def test_list_default_shows_open_only(storage: Storage, config: Config):
    run_command("/add a", storage, config)
    run_command("/add b", storage, config)
    a = storage.list()[0]
    storage.update(a.id, done=True)
    result = run_command("/list", storage, config)
    rendered = str(result.renderable)
    # default = open only; "a" is done, "b" is open
    assert "b" in rendered
    assert "Todos (1)" in rendered


def test_list_all(storage: Storage, config: Config):
    run_command("/add a", storage, config)
    run_command("/add b", storage, config)
    storage.update(storage.list()[0].id, done=True)
    result = run_command("/list --all", storage, config)
    assert "Todos (2)" in str(result.renderable)


def test_list_done_only(storage: Storage, config: Config):
    run_command("/add a", storage, config)
    storage.update(storage.list()[0].id, done=True)
    result = run_command("/list --done", storage, config)
    assert "Todos (1)" in str(result.renderable)


def test_list_filter_tag(storage: Storage, config: Config):
    run_command("/add work-task --tags work", storage, config)
    run_command("/add home-task --tags home", storage, config)
    result = run_command("/list --tag work", storage, config)
    rendered = str(result.renderable)
    assert "work-task" in rendered
    assert "home-task" not in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v -k list
```

Expected: 4 new failures.

- [ ] **Step 3: Implement `/list`**

Append to `src/todo_cli/commands.py`:

```python
def _list_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="/list", exit_on_error=False, add_help=False,
    )
    p.add_argument("--all", action="store_true")
    p.add_argument("--done", action="store_true")
    p.add_argument("--tag", default=None)
    p.add_argument("--project", default=None)
    p.add_argument("--overdue", action="store_true")
    p.add_argument("--today", action="store_true")
    return p


@command("/list")
def _handle_list(args: list[str], storage: Storage, config: Config) -> CommandResult:
    ns = _parse_or_raise(_list_parser(), args)
    if ns.all:
        done_filter: bool | None = None
    elif ns.done:
        done_filter = True
    else:
        done_filter = False
    todos = storage.list(
        done=done_filter,
        tag=ns.tag,
        project=ns.project,
        overdue=ns.overdue,
        today=ns.today,
    )
    return CommandResult(renderable=render.render_todo_list(todos))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 14 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: /list command with filters"
```

---

## Task 15: `/show` Handler

**Files:**
- Modify: `src/todo_cli/commands.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_commands.py`:

```python
def test_show_existing(storage: Storage, config: Config):
    run_command("/add hello", storage, config)
    result = run_command("/show 1", storage, config)
    assert "hello" in str(result.renderable)


def test_show_missing_returns_error(storage: Storage, config: Config):
    result = run_command("/show 999", storage, config)
    assert "999" in str(result.renderable)


def test_show_non_int_id_errors(storage: Storage, config: Config):
    result = run_command("/show abc", storage, config)
    rendered = str(result.renderable).lower()
    assert "id" in rendered or "integer" in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v -k show
```

Expected: 3 new failures.

- [ ] **Step 3: Implement `/show`**

Append to `src/todo_cli/commands.py`:

```python
def _parse_id(args: list[str], cmd: str) -> int:
    if len(args) != 1:
        raise BadCommandUsage(f"{cmd} <id>")
    try:
        return int(args[0])
    except ValueError as e:
        raise BadCommandUsage(f"{cmd} <id> — id must be an integer") from e


@command("/show")
def _handle_show(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/show")
    return CommandResult(renderable=render.render_todo_detail(storage.get(tid)))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 17 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: /show command"
```

---

## Task 16: `/done` and `/undo`

**Files:**
- Modify: `src/todo_cli/commands.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_commands.py`:

```python
def test_done_marks_completed(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/done 1", storage, config)
    assert storage.get(1).done is True


def test_undo_clears_completed(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/done 1", storage, config)
    run_command("/undo 1", storage, config)
    assert storage.get(1).done is False


def test_done_missing_id_returns_error(storage: Storage, config: Config):
    result = run_command("/done 999", storage, config)
    assert "999" in str(result.renderable)
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v -k "done or undo"
```

Expected: 3 new failures.

- [ ] **Step 3: Implement `/done` and `/undo`**

Append to `src/todo_cli/commands.py`:

```python
@command("/done")
def _handle_done(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/done")
    storage.update(tid, done=True)
    return CommandResult(renderable=render.render_info(f"Marked #{tid} done"))


@command("/undo")
def _handle_undo(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/undo")
    storage.update(tid, done=False)
    return CommandResult(renderable=render.render_info(f"Marked #{tid} not done"))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 20 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: /done and /undo commands"
```

---

## Task 17: `/edit` Handler

**Files:**
- Modify: `src/todo_cli/commands.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_commands.py`:

```python
def test_edit_text(storage: Storage, config: Config):
    run_command("/add original", storage, config)
    run_command("/edit 1 text new text", storage, config)
    assert storage.get(1).text == "new text"


def test_edit_due(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/edit 1 due 2026-12-31", storage, config)
    assert storage.get(1).due == date(2026, 12, 31)


def test_edit_priority_valid(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/edit 1 priority high", storage, config)
    assert storage.get(1).priority == "high"


def test_edit_priority_invalid_errors(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    result = run_command("/edit 1 priority extreme", storage, config)
    assert "priority" in str(result.renderable).lower()


def test_edit_tags(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/edit 1 tags work,urgent", storage, config)
    assert storage.get(1).tags == ["work", "urgent"]


def test_edit_unknown_field_errors(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    result = run_command("/edit 1 banana yes", storage, config)
    rendered = str(result.renderable).lower()
    assert "field" in rendered or "banana" in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v -k edit
```

Expected: 6 new failures.

- [ ] **Step 3: Implement `/edit`**

Append to `src/todo_cli/commands.py`:

```python
@command("/edit")
def _handle_edit(args: list[str], storage: Storage, config: Config) -> CommandResult:
    if len(args) < 3:
        raise BadCommandUsage("/edit <id> <field> <value>")
    try:
        tid = int(args[0])
    except ValueError as e:
        raise BadCommandUsage("/edit <id> <field> <value> — id must be an integer") from e
    field = args[1]
    raw_value = " ".join(args[2:])
    value: Any
    if field == "due":
        try:
            value = date.fromisoformat(raw_value)
        except ValueError as e:
            raise BadCommandUsage(f"due must be YYYY-MM-DD: {e}") from e
    elif field == "priority":
        if raw_value not in {"low", "med", "high"}:
            raise BadCommandUsage("priority must be low, med, or high")
        value = raw_value
    elif field == "tags":
        value = [v.strip() for v in raw_value.split(",") if v.strip()]
    elif field == "done":
        value = raw_value.lower() in {"true", "yes", "1"}
    else:
        value = raw_value
    storage.update(tid, **{field: value})
    return CommandResult(renderable=render.render_info(f"Updated #{tid}.{field}"))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 26 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: /edit command with per-field type coercion"
```

---

## Task 18: `/del` Handler

**Files:**
- Modify: `src/todo_cli/commands.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_commands.py`:

```python
def test_del_removes(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/del 1", storage, config)
    assert storage.list(done=None) == []


def test_del_missing_returns_error(storage: Storage, config: Config):
    result = run_command("/del 999", storage, config)
    assert "999" in str(result.renderable)
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v -k del
```

Expected: 2 new failures.

- [ ] **Step 3: Implement `/del`**

Append to `src/todo_cli/commands.py`:

```python
@command("/del")
def _handle_del(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/del")
    storage.delete(tid)
    return CommandResult(renderable=render.render_info(f"Deleted #{tid}"))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 28 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: /del command"
```

---

## Task 19: Free-form Auto-Add Path

Replaces the placeholder `_free_form` from Task 12. When the input doesn't start with `/`, either suggest a typo'd command or auto-add the line as a todo.

**Files:**
- Modify: `src/todo_cli/commands.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_commands.py`:

```python
def test_free_form_auto_adds(storage: Storage, config: Config):
    result = run_command("buy milk", storage, config)
    assert "Added" in str(result.renderable)
    todos = storage.list()
    assert todos[0].text == "buy milk"


def test_free_form_typo_suggests_command(storage: Storage, config: Config):
    result = run_command("lst", storage, config)
    rendered = str(result.renderable)
    assert "/list" in rendered
    # No todo should have been added
    assert storage.list(done=None) == []


def test_free_form_with_dashes_does_not_break_argparse(storage: Storage, config: Config):
    result = run_command("buy --milk and bread", storage, config)
    assert "Added" in str(result.renderable)
    todo = storage.list()[0]
    assert todo.text == "buy --milk and bread"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_commands.py -v -k free_form
```

Expected: 3 new failures — current `_free_form` returns "not yet implemented".

- [ ] **Step 3: Replace `_free_form` body**

In `src/todo_cli/commands.py`, replace the existing `_free_form` function with:

```python
def _free_form(line: str, tokens: list[str], storage: Storage, config: Config) -> CommandResult:
    matches = suggest(tokens[0], KNOWN_COMMANDS)
    if matches:
        return CommandResult(
            renderable=render.render_info(
                f"Did you mean: {matches[0]}? (use /add {tokens[0]} to add as a todo)"
            )
        )
    todo = Todo(id=0, text=line, created_at=datetime.now())
    storage.add(todo)
    return CommandResult(renderable=render.render_info(f"Added #{todo.id}: {line}"))
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_commands.py -v
```

Expected: 31 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/commands.py tests/test_commands.py
git commit -m "feat: free-form auto-add with typo suggestions"
```

---

## Task 20: REPL (`repl.py`)

**Files:**
- Create: `src/todo_cli/repl.py`
- Create: `tests/test_repl.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_repl.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from todo_cli.config import Config
from todo_cli.repl import _process_line, _make_prompt
from todo_cli.storage import Storage


def test_make_prompt_shows_open_count(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    assert _make_prompt(s) == "todo (0 open) > "


def test_process_line_dispatches_slash(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    cfg = Config()
    result = _process_line("/add hello", s, cfg)
    assert "Added" in str(result.renderable)


def test_process_line_handles_exit(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    cfg = Config()
    result = _process_line("/exit", s, cfg)
    assert result.exit is True
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_repl.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.repl'`.

- [ ] **Step 3: Implement `repl.py`**

`src/todo_cli/repl.py`:

```python
from __future__ import annotations
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Console

from todo_cli.commands import CommandResult, KNOWN_COMMANDS, run_command
from todo_cli.config import Config
from todo_cli.storage import Storage


def _make_prompt(storage: Storage) -> str:
    open_count = len(storage.list(done=False))
    return f"todo ({open_count} open) > "


def _process_line(line: str, storage: Storage, config: Config) -> CommandResult:
    return run_command(line, storage, config)


def run(storage: Storage, config: Config, history_path: Path) -> None:
    console = Console()
    completer = WordCompleter(KNOWN_COMMANDS, ignore_case=False)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    session: PromptSession = PromptSession(
        history=FileHistory(str(history_path)),
        completer=completer,
    )
    while True:
        try:
            line = session.prompt(_make_prompt(storage))
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        result = _process_line(line, storage, config)
        if result.clear:
            console.clear()
        if result.renderable is not None:
            console.print(result.renderable)
        if result.exit:
            break
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_repl.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/repl.py tests/test_repl.py
git commit -m "feat: REPL loop with prompt_toolkit + rich"
```

---

## Task 21: Main Entry Point (`__main__.py`)

**Files:**
- Create: `src/todo_cli/__main__.py`

- [ ] **Step 1: Write `__main__.py`**

`src/todo_cli/__main__.py`:

```python
from __future__ import annotations
import sys
from pathlib import Path

from todo_cli.config import Config
from todo_cli.errors import SchemaMismatch, StorageCorrupt
from todo_cli.storage import Storage
from todo_cli import repl


def main() -> int:
    home = Path.home() / ".todo"
    storage_path = home / "todos.json"
    config_path = home / "config.json"
    history_path = home / "history"

    storage = Storage(storage_path)
    try:
        storage.load()
    except (StorageCorrupt, SchemaMismatch) as e:
        print(f"Error: {e}", file=sys.stderr)
        bak = storage_path.with_suffix(storage_path.suffix + ".bak")
        if bak.exists():
            print(f"Backup available: {bak}", file=sys.stderr)
        return 1

    config = Config.load(config_path)
    try:
        repl.run(storage, config, history_path)
    finally:
        config.save(config_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the `todo` console script is wired and starts**

```powershell
todo --help
```

Expected: REPL launches (note: there's no `--help` flag, so it'll start the REPL with that as a prompt input — that's fine, just close with Ctrl+D).

If the script can't be found, re-run `pip install -e .` to refresh the entry point.

- [ ] **Step 3: Commit**

```powershell
git add src/todo_cli/__main__.py
git commit -m "feat: main entry point with storage init and config persistence"
```

---

## Task 22: Manual REPL Smoke Test

This task verifies the REPL works end-to-end. No code; just exercise the binary.

- [ ] **Step 1: Launch the REPL**

```powershell
todo
```

Expected: prompt `todo (0 open) > ` appears.

- [ ] **Step 2: Run a sequence of commands**

Type each line at the prompt, hitting Enter after each:

```
/add buy milk --due 2026-05-08 --priority high --tags home
buy bread
lst
/list
/show 1
/done 1
/list --all
/edit 2 priority low
/del 2
/help
/exit
```

Expected behavior:
- `/add buy milk ...` — "Added #1: buy milk".
- `buy bread` — "Added #2: buy bread" (free-form).
- `lst` — "Did you mean: /list?" (no todo added).
- `/list` — table with #2 only (default = open; #1 still open here).
- `/show 1` — detail panel for "buy milk".
- `/done 1` — "Marked #1 done".
- `/list --all` — table with both.
- `/edit 2 priority low` — "Updated #2.priority".
- `/del 2` — "Deleted #2".
- `/help` — command list.
- `/exit` — exits cleanly.

- [ ] **Step 3: Verify the file landed**

```powershell
type $env:USERPROFILE\.todo\todos.json
```

Expected: JSON with `version: 1`, `next_id` ≥ 3, one done todo (id=1, "buy milk").

- [ ] **Step 4: Verify history**

```powershell
type $env:USERPROFILE\.todo\history
```

Expected: contains the lines you typed.

- [ ] **Step 5: Run full test suite**

```powershell
pytest -v
```

Expected: all tests pass. Coverage for `storage`, `commands`, `suggest` should be ≥90%.

- [ ] **Step 6: Commit any cleanup**

If anything was tweaked during smoke testing, commit it. If not, skip.

---

## Task 23: MCP Server Tool Logic (`mcp_server.py`)

Pure Python tool functions that operate on a `Storage` instance. The stdio glue is added in Task 24. Keeping the logic pure makes it testable without spinning up an actual MCP transport.

**Files:**
- Create: `src/todo_cli/mcp_server.py`
- Create: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_mcp_server.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_mcp_server.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'todo_cli.mcp_server'`.

- [ ] **Step 3: Implement tool functions**

`src/todo_cli/mcp_server.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_mcp_server.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/todo_cli/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: MCP tool functions backed by Storage"
```

---

## Task 24: MCP Stdio Server + Entry Point

Wire the tool functions into an MCP `Server` over stdio. Defines tool schemas, dispatches `call_tool` requests, and provides the `todo-mcp` entry point.

**Files:**
- Modify: `src/todo_cli/mcp_server.py`

- [ ] **Step 1: Add stdio server scaffolding**

Append to `src/todo_cli/mcp_server.py`:

```python
import asyncio
import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from todo_cli.errors import TodoError


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
```

- [ ] **Step 2: Verify `build_server` constructs without error**

Add this test to the END of `tests/test_mcp_server.py`:

```python
def test_build_server_constructs(storage: Storage):
    from todo_cli.mcp_server import build_server
    server = build_server(storage)
    assert server is not None
```

```powershell
pytest tests/test_mcp_server.py -v
```

Expected: 10 passed.

- [ ] **Step 3: Verify `todo-mcp` entry point launches**

```powershell
echo $null | todo-mcp
```

Expected: process starts, reads no stdin (or hangs waiting for input). Press Ctrl+C to kill.

We're not asserting protocol correctness here — that's covered when registered with a real MCP client.

- [ ] **Step 4: Commit**

```powershell
git add src/todo_cli/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: MCP stdio server and todo-mcp entry point"
```

---

## Task 25: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# todo-cli

A personal todo CLI with a persistent REPL and an MCP server, sharing one local JSON file. Designed for daily use; no cloud, no account.

## Install

```powershell
pip install -e .[dev]
```

This installs two console scripts: `todo` (REPL) and `todo-mcp` (MCP stdio server).

## Use the REPL

```powershell
todo
```

You'll get a prompt like:

```
todo (0 open) >
```

Type slash commands or free-form text:

- `/add buy milk --due 2026-05-08 --priority high --tags home` — add with metadata.
- `buy bread` — free-form text auto-adds as a todo.
- `/list` — open todos. `/list --all`, `/list --done`, `/list --tag work`, `/list --overdue`, `/list --today`.
- `/show <id>` — detail panel.
- `/done <id>` / `/undo <id>` — toggle completion.
- `/edit <id> <field> <value>` — fields: `text`, `due`, `priority`, `tags`, `project`, `done`.
- `/del <id>` — delete.
- `/help`, `/clear`, `/exit` (or `/quit`).

Typos like `lst` or `/dn` get suggestions instead of being added as todos.

## Use from Claude Code or another MCP client

Register the server in your MCP client config. For Claude Code (`%USERPROFILE%\.claude\settings.json`):

```json
{
  "mcpServers": {
    "todo": { "command": "todo-mcp" }
  }
}
```

Tools exposed: `list_todos`, `add_todo`, `show_todo`, `mark_done`, `mark_undone`, `edit_todo`, `delete_todo`.

## Storage

- File: `%USERPROFILE%\.todo\todos.json` (Windows) or `~/.todo/todos.json` (POSIX).
- Atomic writes; `.bak` file preserved each save; sidecar `.lock` file coordinates REPL + MCP concurrency.
- Schema versioned (`version: 1`); future builds migrate or refuse incompatible files.

## Concurrency

The REPL and MCP server can run simultaneously against the same file. Mutations are serialized via an OS file lock. Don't run multiple REPLs as a habit — it works, but the prompt's open-count is only refreshed at your prompt.

## Tests

```powershell
pytest
```

## Roadmap

Phase 2 (deferred): in-app AI parsing of free-form input via Anthropic Claude with prompt caching. Will go through its own brainstorm → spec → plan cycle.
```

- [ ] **Step 2: Commit**

```powershell
git add README.md
git commit -m "docs: add README with REPL and MCP usage"
```

---

## Self-Review

After writing the plan, re-read the spec and confirm coverage:

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| Goals — daily use, REPL feel | 20, 22 |
| Goals — slash commands | 12-19 |
| Goals — polished output | 11 |
| Goals — MCP exposure | 23, 24 |
| Goals — phase-2 hook clean | 9 (Config), 19 (free-form path) |
| Goals — high test coverage | every task is TDD |
| Architecture — package layout | 1 |
| Architecture — module boundaries | observed throughout |
| Data model — Todo dataclass | 3 |
| Storage — atomic write + backup | 4 |
| Storage — schema versioning | 4 |
| Storage — file locking | 8 |
| REPL — prompt format | 20 |
| REPL — history + completion | 20 |
| REPL — Ctrl+C / Ctrl+D | 20 |
| Commands — full table | 12-19 |
| Commands — argparse exit_on_error=False | 13, 14 |
| Suggest — unknown slash | 12 |
| Suggest — free-form typo abort | 19 |
| MCP server — tools | 23, 24 |
| MCP server — error mapping | 24 |
| MCP server — shared substrate | 23 (Storage param) |
| Error handling — operational continues | 12 (TodoError catch) |
| Error handling — integrity exits | 21 |
| Testing — per-module focus | tasks 2-23 each include tests |

All sections covered.

**Placeholder scan:** No "TBD", "TODO", "implement later", or "similar to Task N" placeholders. Every code step has full code.

**Type consistency:**
- `CommandResult(renderable, exit, clear)` — same fields used in tasks 12, 19, 20.
- `Storage` method signatures stable from task 4 onwards.
- `Todo` dataclass shape stable from task 3 onwards.
- `Handler = Callable[[list[str], Storage, Config], CommandResult]` — same shape used by all `@command`-decorated handlers.
- `tool_*(storage, args)` functions return `dict | list[dict]` — consistent in tasks 23 and 24.

No issues found.

---

## Execution

Plan complete. Ready for execution.
