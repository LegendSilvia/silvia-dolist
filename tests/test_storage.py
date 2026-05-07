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
