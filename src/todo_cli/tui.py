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
from datetime import datetime
from pathlib import Path
from typing import Optional

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition
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
from todo_cli.sky import SKY_HEIGHT, render_sky
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
        self.selected_index: int = 0
        # Tracks which todo's detail panel has been opened most recently.
        # /ask requires viewing the detail first, so the user has a moment
        # to confirm what's about to be handed off to Claude.
        self.last_viewed_id: Optional[int] = None


_ID_OPTIONAL_COMMANDS = {"/done", "/undo", "/show", "/del", "/ask"}


def _extract_command_id(line: str) -> Optional[int]:
    """Pull the numeric id out of a slash command, after autofill."""
    parts = line.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _autofill_selected_id(line: str, sel_id: Optional[int]) -> str:
    """Inject the selected todo's ID into a slash command that takes an ID
    when the user didn't type one. Returns the line unchanged if not
    applicable.
    """
    if sel_id is None:
        return line
    parts = line.split(maxsplit=2)
    if not parts:
        return line
    cmd = parts[0]
    if cmd in _ID_OPTIONAL_COMMANDS:
        if len(parts) == 1:
            return f"{cmd} {sel_id}"
    elif cmd == "/edit":
        if len(parts) >= 2:
            try:
                int(parts[1])
                return line  # explicit ID already present
            except ValueError:
                rest = line[len(cmd):].strip()
                return f"{cmd} {sel_id} {rest}"
    return line


def run(storage: Storage, config: Config, history_path: Path) -> None:
    state = _State()

    def sky_text():
        width = _term_width()
        return _to_ansi(render_sky(datetime.now(), width=width), width)

    def _visible_todos():
        # Same sort order as render_todo_list so cursor index lines up.
        from todo_cli.render import _sort_key  # local import: private helper
        return sorted(storage.list(done=False), key=_sort_key)

    def _clamp_selection(todos):
        if not todos:
            state.selected_index = 0
        else:
            state.selected_index = max(0, min(state.selected_index, len(todos) - 1))

    def _selected_todo():
        todos = _visible_todos()
        _clamp_selection(todos)
        return todos[state.selected_index] if todos else None

    def todos_text():
        width = _term_width()
        todos = _visible_todos()
        _clamp_selection(todos)
        sel = todos[state.selected_index].id if todos else None
        return _to_ansi(
            render.render_todo_list(todos, label="open", selected_id=sel),
            width,
        )

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

    sky_panel = Window(
        content=FormattedTextControl(text=sky_text, focusable=False),
        wrap_lines=False,
        always_hide_cursor=True,
        height=SKY_HEIGHT + 1,  # 4 sky rows + 1 horizon
    )

    todo_panel = Window(
        content=FormattedTextControl(text=todos_text, focusable=False),
        wrap_lines=False,
        always_hide_cursor=True,
    )

    def _divider() -> Window:
        return Window(height=1, char="─", style="fg:ansibrightblack")

    output_panel = Window(
        content=FormattedTextControl(text=output_text, focusable=False),
        wrap_lines=True,
        always_hide_cursor=True,
        dont_extend_height=True,
    )

    def hints_text():
        if input_buffer.text:
            return ANSI("")
        return FormattedText([
            ("ansibrightblack",
             "  ↑↓ select  ·  space toggle  ·  enter detail  ·  /done /del /edit act on selected  ·  /ask after enter  ·  ctrl-d quit"),
        ])

    hints_window = Window(
        content=FormattedTextControl(text=hints_text, focusable=False),
        height=1,
        always_hide_cursor=True,
    )

    input_window = Window(
        content=BufferControl(buffer=input_buffer),
        height=1,
        get_line_prefix=prompt_prefix,
    )

    layout = Layout(
        HSplit([
            sky_panel,
            _divider(),
            todo_panel,
            _divider(),
            output_panel,
            _divider(),
            hints_window,
            input_window,
        ]),
        focused_element=input_window,
    )

    kb = KeyBindings()
    empty_input = Condition(lambda: not input_buffer.text)

    @kb.add("enter")
    def _enter(event):
        line = input_buffer.text.strip()
        if not line:
            # Empty + Enter: open detail of selected todo and arm /ask.
            sel = _selected_todo()
            if sel is not None:
                state.last_viewed_id = sel.id
                state.last_result = run_command(f"/show {sel.id}", storage, config)
            return
        sel = _selected_todo()
        line = _autofill_selected_id(line, sel.id if sel else None)

        # /ask requires that the user has just viewed the detail — gives a
        # beat to read what's about to be handed off to Claude.
        if line.startswith("/ask"):
            target_id = _extract_command_id(line)
            if target_id is None or state.last_viewed_id != target_id:
                input_buffer.reset()
                state.last_result = CommandResult(
                    renderable=render.render_warn(
                        "Press enter to view the todo's detail first, then /ask."
                    )
                )
                return

        input_buffer.reset()
        result = run_command(line, storage, config)
        if result.clear:
            state.last_result = None
        else:
            state.last_result = result
        # /show updates last_viewed_id; other commands invalidate the prior
        # view so /ask requires a fresh look.
        if line.startswith("/show"):
            shown_id = _extract_command_id(line)
            if shown_id is not None:
                state.last_viewed_id = shown_id
        else:
            state.last_viewed_id = None
        if result.exit:
            event.app.exit()

    @kb.add("up", filter=empty_input)
    def _up(event):
        state.selected_index = max(0, state.selected_index - 1)

    @kb.add("down", filter=empty_input)
    def _down(event):
        todos = _visible_todos()
        state.selected_index = min(max(0, len(todos) - 1), state.selected_index + 1)

    @kb.add("space", filter=empty_input)
    def _toggle_done(event):
        # Space (non-alphabet) is safe — toggling done is reversible.
        sel = _selected_todo()
        if sel is None:
            return
        storage.update(sel.id, done=not sel.done)

    @kb.add("c-c")
    @kb.add("c-d")
    def _quit(event):
        event.app.exit()

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
        refresh_interval=2.0,  # animate cloud drift; clock ticks too
    )
    app.run()
