from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from todo_cli.commands import run_command
from todo_cli.config import Config
from todo_cli.storage import Storage


@pytest.fixture
def storage(storage_path: Path) -> Storage:
    s = Storage(storage_path)
    s.load()
    return s


def _add_then_done_with_age(storage: Storage, text: str, age_days: int) -> int:
    """Create a done todo whose completed_at is age_days in the past."""
    config = Config()
    run_command(f"/add {text}", storage, config)
    # Pull last id
    todos = storage.list()
    tid = todos[-1].id
    storage.update(tid, done=True)
    # Backdate completed_at
    todos = storage.list(done=True)
    for t in todos:
        if t.id == tid:
            t.completed_at = datetime.now() - timedelta(days=age_days)
            # write through the storage helper so it persists
            from todo_cli.storage import Storage as _S
            with storage._locked():  # type: ignore[attr-defined]
                next_id, all_todos = storage._read()
                for stored in all_todos:
                    if stored.id == tid:
                        stored.completed_at = t.completed_at
                storage._write(next_id, all_todos)
            break
    return tid


def test_purge_removes_old_done_todos(storage: Storage):
    config = Config()
    old_id = _add_then_done_with_age(storage, "old task", age_days=60)
    new_id = _add_then_done_with_age(storage, "fresh task", age_days=1)
    run_command("/purge 30", storage, config)
    remaining_ids = {t.id for t in storage.list(done=None)}
    assert old_id not in remaining_ids
    assert new_id in remaining_ids


def test_purge_keeps_open_todos(storage: Storage):
    config = Config()
    run_command("/add still open", storage, config)
    run_command("/purge 0", storage, config)  # cutoff = now; only done items qualify
    todos = storage.list(done=False)
    assert len(todos) == 1


def test_purge_no_arg_uses_config_default(storage: Storage):
    config = Config(done_retention_days=14)
    old_id = _add_then_done_with_age(storage, "two weeks old", age_days=20)
    run_command("/purge", storage, config)
    remaining_ids = {t.id for t in storage.list(done=None)}
    assert old_id not in remaining_ids


def test_purge_no_arg_no_default_errors(storage: Storage):
    config = Config()  # no done_retention_days set
    result = run_command("/purge", storage, config)
    rendered = str(result.renderable).lower()
    assert "/purge" in rendered or "config" in rendered


def test_purge_reports_count(storage: Storage):
    config = Config()
    _add_then_done_with_age(storage, "old 1", age_days=60)
    _add_then_done_with_age(storage, "old 2", age_days=60)
    result = run_command("/purge 30", storage, config)
    rendered = str(result.renderable)
    assert "2" in rendered


def test_purge_negative_days_errors(storage: Storage):
    config = Config()
    result = run_command("/purge -5", storage, config)
    rendered = str(result.renderable).lower()
    assert ">=" in rendered or "must be" in rendered


def test_config_done_retention_days_set_and_clear(storage: Storage):
    config = Config()
    run_command("/config done_retention_days 30", storage, config)
    assert config.done_retention_days == 30
    run_command("/config done_retention_days none", storage, config)
    assert config.done_retention_days is None


def test_config_done_retention_days_rejects_non_int(storage: Storage):
    config = Config()
    result = run_command("/config done_retention_days forever", storage, config)
    rendered = str(result.renderable).lower()
    assert "integer" in rendered
