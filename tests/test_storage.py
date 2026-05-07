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
