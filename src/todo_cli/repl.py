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
