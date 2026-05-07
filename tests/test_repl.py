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
