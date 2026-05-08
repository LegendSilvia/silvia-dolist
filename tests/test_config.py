from __future__ import annotations
import json
from pathlib import Path

import pytest

from todo_cli.commands import run_command
from todo_cli.config import Config, SETTABLE_FIELDS
from todo_cli.storage import Storage


@pytest.fixture
def storage(storage_path: Path) -> Storage:
    s = Storage(storage_path)
    s.load()
    return s


def test_load_returns_default_when_file_missing(tmp_path: Path):
    cfg = Config.load(tmp_path / "config.json")
    assert isinstance(cfg, Config)
    assert cfg.agent_terminal_cwd is None


def test_save_creates_file(tmp_path: Path):
    cfg = Config()
    p = tmp_path / "config.json"
    cfg.save(p)
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_load_after_save_round_trips(tmp_path: Path):
    p = tmp_path / "config.json"
    Config(agent_terminal_cwd=str(tmp_path)).save(p)
    cfg2 = Config.load(p)
    assert cfg2.agent_terminal_cwd == str(tmp_path)


def test_settable_fields_includes_cwd():
    keys = [k for k, _ in SETTABLE_FIELDS]
    assert "agent_terminal_cwd" in keys


def test_config_load_ignores_unknown_keys(tmp_path: Path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"agent_terminal_cwd": str(tmp_path), "future_field": 42}))
    loaded = Config.load(p)
    assert loaded.agent_terminal_cwd == str(tmp_path)
    assert not hasattr(loaded, "future_field")


def test_config_command_no_args_shows_settings(storage: Storage):
    c = Config()
    result = run_command("/config", storage, c)
    assert result.renderable is not None


def test_config_command_sets_existing_dir(storage: Storage, tmp_path: Path):
    c = Config()
    run_command(f"/config agent_terminal_cwd {tmp_path}", storage, c)
    assert c.agent_terminal_cwd == str(tmp_path.resolve())


def test_config_command_clear(storage: Storage, tmp_path: Path):
    c = Config(agent_terminal_cwd=str(tmp_path))
    run_command("/config agent_terminal_cwd none", storage, c)
    assert c.agent_terminal_cwd is None


def test_config_command_rejects_unknown_key(storage: Storage):
    c = Config()
    result = run_command("/config bogus_key value", storage, c)
    rendered = str(result.renderable).lower()
    assert "unknown" in rendered


def test_config_command_rejects_nonexistent_path(storage: Storage):
    c = Config()
    result = run_command(
        "/config agent_terminal_cwd /definitely/not/a/path/xyzzy", storage, c
    )
    rendered = str(result.renderable).lower()
    assert "not a directory" in rendered
