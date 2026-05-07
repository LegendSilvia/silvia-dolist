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
