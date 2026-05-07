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
