import io
from pathlib import Path

from rich.console import Console

from todo_cli.config import Config
from todo_cli.repl import _process_line, _make_prompt
from todo_cli.storage import Storage


def _render(renderable) -> str:
    buf = io.StringIO()
    Console(file=buf, force_terminal=False, width=200).print(renderable)
    return buf.getvalue()


def test_make_prompt_shows_open_count(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    fragments = _make_prompt(s)
    text = "".join(seg for _style, seg in fragments)
    assert "todo (0 open)" in text


def test_process_line_dispatches_slash(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    cfg = Config()
    result = _process_line("/add hello", s, cfg)
    assert "Added" in _render(result.renderable)


def test_process_line_handles_exit(storage_path: Path):
    s = Storage(storage_path)
    s.load()
    cfg = Config()
    result = _process_line("/exit", s, cfg)
    assert result.exit is True
