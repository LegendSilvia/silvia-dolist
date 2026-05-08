"""Full-screen interactive interface.

Layout (top to bottom):

    ◆ todos · N open
    │ ...current open todos, always visible...
    ─────
    ◇ ...last command result...
    ─────
    ◆ todo (N) › _

The todo list refreshes after every command. Pressing Enter runs the
input as a REPL line; Ctrl-C / Ctrl-D / /exit quits.
"""
from __future__ import annotations
import io
import shutil
from pathlib import Path
from typing import Optional

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import ANSI, FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from rich.console import Console

from todo_cli import render
from todo_cli import symbols as S
from todo_cli.commands import CommandResult, KNOWN_COMMANDS, run_command
from todo_cli.config import Config
from todo_cli.storage import Storage


def _term_width() -> int:
    return max(40, shutil.get_terminal_size((100, 24)).columns)


def _to_ansi(renderable, width: int) -> ANSI:
    if renderable is None:
        return ANSI("")
    buf = io.StringIO()
    Console(
        file=buf,
        force_terminal=True,
        color_system="truecolor",
        width=width,
    ).print(renderable)
    return ANSI(buf.getvalue().rstrip("\n"))


class _State:
    def __init__(self) -> None:
        self.last_result: Optional[CommandResult] = None


def run(storage: Storage, config: Config, history_path: Path) -> None:
    state = _State()

    def todos_text():
        width = _term_width()
        todos = storage.list(done=False)
        return _to_ansi(render.render_todo_list(todos, label="open"), width)

    def output_text():
        if state.last_result is None or state.last_result.renderable is None:
            return ANSI("")
        return _to_ansi(state.last_result.renderable, _term_width())

    def prompt_prefix(_lineno, _wrap_count):
        n = len(storage.list(done=False))
        return FormattedText(
            [
                ("ansicyan bold", S.ACTIVE + " "),
                ("ansibrightblack", f"todo ({n}) "),
                ("ansicyan", "› "),
            ]
        )

    history_path.parent.mkdir(parents=True, exist_ok=True)
    input_buffer = Buffer(
        completer=WordCompleter(KNOWN_COMMANDS, ignore_case=False),
        history=FileHistory(str(history_path)),
        multiline=False,
    )

    todo_panel = Window(
        content=FormattedTextControl(text=todos_text, focusable=False),
        wrap_lines=False,
        always_hide_cursor=True,
    )

    divider = Window(height=1, char="─", style="fg:ansibrightblack")

    output_panel = Window(
        content=FormattedTextControl(text=output_text, focusable=False),
        wrap_lines=True,
        always_hide_cursor=True,
        dont_extend_height=True,
    )

    input_window = Window(
        content=BufferControl(buffer=input_buffer),
        height=1,
        get_line_prefix=prompt_prefix,
    )

    layout = Layout(
        HSplit([todo_panel, divider, output_panel, divider, input_window]),
        focused_element=input_window,
    )

    kb = KeyBindings()

    @kb.add("enter")
    def _enter(event):
        line = input_buffer.text
        input_buffer.reset()
        result = run_command(line, storage, config)
        if result.clear:
            state.last_result = None
        else:
            state.last_result = result
        if result.exit:
            event.app.exit()

    @kb.add("c-c")
    @kb.add("c-d")
    def _quit(event):
        event.app.exit()

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
    )
    app.run()
