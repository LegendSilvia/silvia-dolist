from __future__ import annotations
import argparse
import os
import re
import shlex
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Callable

from todo_cli.config import Config, SETTABLE_FIELDS
from todo_cli.errors import BadCommandUsage, TodoError
from todo_cli.models import Todo
from todo_cli.parse_text import parse_input
from todo_cli.storage import Storage
from todo_cli.suggest import suggest
from todo_cli import ask as ask_mod
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
    "/note", "/ask", "/config", "/help", "/clear", "/exit", "/quit",
]


_KNOWN_SLASH_NAMES = {c.lstrip("/") for c in KNOWN_COMMANDS}

_MSYS_MANGLED_RE = re.compile(r"^[A-Za-z]:[/\\].*[/\\]([^/\\]+)$")


def unmangle_msys_args(args: list[str]) -> list[str]:
    """Recover slash commands that Git Bash / MSYS path-translated.

    On Windows, MSYS shells auto-rewrite argv elements that start with
    `/` by prepending the MSYS install path — so `todo /list` becomes
    `todo C:/Users/foo/AppData/Local/Programs/Git/list`. Without this
    recovery, the CLI sees the path as free-form text and adds a new
    todo titled with the path, silently polluting the list.

    Heuristic: if an arg looks like a Windows path and its basename
    matches one of our known slash command names, restore the leading
    slash. Other Windows paths (e.g. genuine file references) pass
    through unchanged.
    """
    out: list[str] = []
    for arg in args:
        m = _MSYS_MANGLED_RE.match(arg)
        if m and m.group(1) in _KNOWN_SLASH_NAMES:
            out.append("/" + m.group(1))
        else:
            out.append(arg)
    return out


def _tokenize(line: str) -> list[str]:
    """Split a command line into tokens.

    On Windows, use non-POSIX mode so backslashes in paths are preserved
    (otherwise `C:\\Users\\me` becomes `C:Usersme`). Non-POSIX mode keeps
    surrounding quotes in tokens, so strip them after the fact for parity
    with POSIX behavior on the rest of the surface.
    """
    if os.name == "nt":
        tokens = shlex.split(line, posix=False)
        return [_strip_quotes(t) for t in tokens]
    return shlex.split(line)


def _strip_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ('"', "'"):
        return token[1:-1]
    return token


def run_command(line: str, storage: Storage, config: Config) -> CommandResult:
    line = line.strip()
    if not line:
        return CommandResult()
    try:
        tokens = _tokenize(line)
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
    matches = suggest(tokens[0], KNOWN_COMMANDS)
    if matches:
        return CommandResult(
            renderable=render.render_warn(
                f"Did you mean: {matches[0]}? (use /add {tokens[0]} to add as a todo)"
            )
        )
    parsed = parse_input(line)
    text = parsed.text or line
    todo = Todo(
        id=0,
        text=text,
        created_at=datetime.now(),
        due=parsed.due,
        due_time=parsed.due_time,
        priority=parsed.priority,
        tags=parsed.tags,
        project=parsed.project,
    )
    storage.add(todo)
    return CommandResult(renderable=render.render_added(todo))


HELP_TEXT = """\
/add <text>          add (text is parsed for date/priority/#tags/@project)
/list [--all|--done|--tag X|--project P|--overdue|--today]
/show [id]           detail (id optional in TUI: uses ↑↓ selection)
/done [id]           mark complete
/undo [id]           mark incomplete
/edit [id] <field> <value>     fields: text, description, due, due_time,
                                priority, tags, project, done
/note [id] <text>    append a timestamped note to description (won't clobber)
/del [id]            delete
/ask [id]            open new terminal with claude + copy a prompt
                     about the todo (uses text, description, due, etc.)
/config              show settings
/config <key> <val>  set a setting (e.g. agent_terminal_cwd ~/work)
/help                this list
/clear               clear screen
/exit, /quit         save and exit

natural language is parsed before flags. examples:
  finish report by friday #work @q2 p1
  buy milk tmr
  call dentist tonight
explicit --flags always win.
"""


@command("/help")
def _handle_help(args: list[str], storage: Storage, config: Config) -> CommandResult:
    return CommandResult(renderable=render.render_help(HELP_TEXT))


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
    raw_text = " ".join(ns.text)
    parsed = parse_input(raw_text)
    flag_tags = [t.strip() for t in ns.tags.split(",") if t.strip()]
    text = parsed.text or raw_text
    tags = flag_tags or parsed.tags
    todo = Todo(
        id=0,
        text=text,
        created_at=datetime.now(),
        due=ns.due if ns.due is not None else parsed.due,
        due_time=parsed.due_time,
        priority=ns.priority if ns.priority is not None else parsed.priority,
        tags=tags,
        project=ns.project if ns.project is not None else parsed.project,
    )
    storage.add(todo)
    return CommandResult(renderable=render.render_added(todo))


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
        label = "total"
    elif ns.done:
        done_filter = True
        label = "done"
    else:
        done_filter = False
        label = "open"
    todos = storage.list(
        done=done_filter,
        tag=ns.tag,
        project=ns.project,
        overdue=ns.overdue,
        today=ns.today,
    )
    return CommandResult(renderable=render.render_todo_list(todos, label=label))


def _parse_id(args: list[str], cmd: str) -> int:
    if len(args) != 1:
        raise BadCommandUsage(f"{cmd} <id>")
    try:
        return int(args[0])
    except ValueError as e:
        raise BadCommandUsage(f"{cmd} <id> — id must be an integer") from e


@command("/show")
def _handle_show(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/show")
    return CommandResult(renderable=render.render_todo_detail(storage.get(tid)))


@command("/done")
def _handle_done(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/done")
    storage.update(tid, done=True)
    return CommandResult(renderable=render.render_info(f"Marked #{tid} done"))


@command("/undo")
def _handle_undo(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/undo")
    storage.update(tid, done=False)
    return CommandResult(renderable=render.render_info(f"Marked #{tid} not done"))


@command("/edit")
def _handle_edit(args: list[str], storage: Storage, config: Config) -> CommandResult:
    if len(args) < 3:
        raise BadCommandUsage("/edit <id> <field> <value>")
    try:
        tid = int(args[0])
    except ValueError as e:
        raise BadCommandUsage("/edit <id> <field> <value> — id must be an integer") from e
    field = args[1]
    raw_value = " ".join(args[2:])
    value: Any
    if field == "due":
        try:
            value = date.fromisoformat(raw_value)
        except ValueError as e:
            raise BadCommandUsage(f"due must be YYYY-MM-DD: {e}") from e
    elif field == "due_time":
        if not raw_value or raw_value.lower() in {"none", "null", "clear"}:
            value = None
        else:
            try:
                value = time.fromisoformat(raw_value)
            except ValueError as e:
                raise BadCommandUsage(f"due_time must be HH:MM: {e}") from e
    elif field == "priority":
        if raw_value not in {"low", "med", "high"}:
            raise BadCommandUsage("priority must be low, med, or high")
        value = raw_value
    elif field == "tags":
        value = [v.strip() for v in raw_value.split(",") if v.strip()]
    elif field == "done":
        value = raw_value.lower() in {"true", "yes", "1"}
    else:
        value = raw_value
    storage.update(tid, **{field: value})
    return CommandResult(renderable=render.render_info(f"Updated #{tid}.{field}"))


@command("/del")
def _handle_del(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/del")
    storage.delete(tid)
    return CommandResult(renderable=render.render_info(f"Deleted #{tid}"))


@command("/note")
def _handle_note(args: list[str], storage: Storage, config: Config) -> CommandResult:
    """Append a timestamped note to a todo's description without clobbering."""
    if len(args) < 2:
        raise BadCommandUsage("/note <id> <text>")
    try:
        tid = int(args[0])
    except ValueError as e:
        raise BadCommandUsage("/note <id> <text> — id must be an integer") from e
    text = " ".join(args[1:])
    todo = storage.get(tid)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{stamp}] {text}"
    new_desc = f"{todo.description}\n\n{line}" if todo.description else line
    storage.update(tid, description=new_desc)
    return CommandResult(renderable=render.render_info(f"Noted #{tid}"))


@command("/ask")
def _handle_ask(args: list[str], storage: Storage, config: Config) -> CommandResult:
    tid = _parse_id(args, "/ask")
    todo = storage.get(tid)
    prompt = ask_mod.build_prompt(todo)
    copied = ask_mod.copy_to_clipboard(prompt)
    cwd = config.agent_terminal_cwd

    if todo.claude_session:
        opened = ask_mod.open_terminal_with_claude(
            resume_session=todo.claude_session,
            cwd=cwd,
        )
        action = f"resumed session {todo.claude_session}"
    else:
        session_name = ask_mod.new_session_name(todo)
        opened = ask_mod.open_terminal_with_claude(
            prompt=prompt,
            session_name=session_name,
            cwd=cwd,
        )
        if opened:
            storage.update(tid, claude_session=session_name)
        action = f"started session {session_name}"

    bits = [action] if opened else []
    if copied:
        bits.append("prompt copied to clipboard")
    if not opened:
        bits.append("could not launch new terminal — paste from clipboard manually")
    msg = f"/ask #{tid}: " + "; ".join(bits)
    return CommandResult(renderable=render.render_info(msg))


@command("/config")
def _handle_config(args: list[str], storage: Storage, config: Config) -> CommandResult:
    if not args:
        return CommandResult(renderable=render.render_config(config, SETTABLE_FIELDS))
    if len(args) < 2:
        raise BadCommandUsage("/config <key> <value>  (or just /config to view)")
    key = args[0]
    raw_value = " ".join(args[1:])
    valid_keys = {k for k, _ in SETTABLE_FIELDS}
    if key not in valid_keys:
        raise BadCommandUsage(
            f"unknown config key: {key} (valid: {', '.join(sorted(valid_keys))})"
        )
    value: Any
    if raw_value.lower() in {"none", "null", "clear"}:
        value = None
    elif key == "agent_terminal_cwd":
        from pathlib import Path as _Path
        expanded = _Path(raw_value).expanduser()
        if not expanded.is_dir():
            raise BadCommandUsage(f"not a directory: {expanded}")
        value = str(expanded.resolve())
    else:
        value = raw_value
    setattr(config, key, value)
    return CommandResult(renderable=render.render_info(f"set {key} = {value}"))
