from __future__ import annotations
import argparse
import shlex
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable

from todo_cli.config import Config
from todo_cli.errors import BadCommandUsage, TodoError
from todo_cli.models import Todo
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


def _parse_or_raise(parser: argparse.ArgumentParser, args: list[str]):
    try:
        return parser.parse_args(args)
    except argparse.ArgumentError as e:
        raise BadCommandUsage(f"{parser.prog}: {e}") from e
    except SystemExit as e:
        # exit_on_error=False stops most exits, but argparse may still raise
        # SystemExit on -h or required-arg failures depending on version.
        raise BadCommandUsage(f"{parser.prog}: invalid arguments") from e


def _add_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="/add", exit_on_error=False, add_help=False,
    )
    p.add_argument("text", nargs="+")
    p.add_argument("--due", type=date.fromisoformat, default=None)
    p.add_argument("--priority", choices=["low", "med", "high"], default=None)
    p.add_argument("--tags", default="")
    p.add_argument("--project", default=None)
    return p


@command("/add")
def _handle_add(args: list[str], storage: Storage, config: Config) -> CommandResult:
    ns = _parse_or_raise(_add_parser(), args)
    text = " ".join(ns.text)
    tags = [t.strip() for t in ns.tags.split(",") if t.strip()]
    todo = Todo(
        id=0,
        text=text,
        created_at=datetime.now(),
        due=ns.due,
        priority=ns.priority,
        tags=tags,
        project=ns.project,
    )
    storage.add(todo)
    return CommandResult(renderable=render.render_info(f"Added #{todo.id}: {text}"))


def _list_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="/list", exit_on_error=False, add_help=False,
    )
    p.add_argument("--all", action="store_true")
    p.add_argument("--done", action="store_true")
    p.add_argument("--tag", default=None)
    p.add_argument("--project", default=None)
    p.add_argument("--overdue", action="store_true")
    p.add_argument("--today", action="store_true")
    return p


@command("/list")
def _handle_list(args: list[str], storage: Storage, config: Config) -> CommandResult:
    ns = _parse_or_raise(_list_parser(), args)
    if ns.all:
        done_filter: bool | None = None
    elif ns.done:
        done_filter = True
    else:
        done_filter = False
    todos = storage.list(
        done=done_filter,
        tag=ns.tag,
        project=ns.project,
        overdue=ns.overdue,
        today=ns.today,
    )
    return CommandResult(renderable=render.render_todo_list(todos))
