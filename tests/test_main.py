from __future__ import annotations
from pathlib import Path

import pytest

from todo_cli.__main__ import _one_shot
from todo_cli.config import Config
from todo_cli.storage import Storage


@pytest.fixture
def storage(storage_path: Path) -> Storage:
    s = Storage(storage_path)
    s.load()
    return s


def test_one_shot_adds_todo_and_returns_zero(storage: Storage, capsys):
    code = _one_shot(["buy", "milk", "tomorrow"], storage, Config())
    assert code == 0
    todos = storage.list()
    assert len(todos) == 1
    assert todos[0].text == "buy milk"
    assert todos[0].due is not None


def test_one_shot_runs_slash_command(storage: Storage, capsys):
    _one_shot(["/add", "first"], storage, Config())
    todos = storage.list()
    assert len(todos) == 1
    assert todos[0].text == "first"


def test_one_shot_prints_output(storage: Storage, capsys):
    _one_shot(["hello"], storage, Config())
    out = capsys.readouterr().out
    assert "Added" in out
    assert "hello" in out
