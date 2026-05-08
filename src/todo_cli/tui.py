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
        self.awaiting_delete_id: Optional[int] = None


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
        if state.awaiting_delete_id is not None:
            try:
                target = storage.get(state.awaiting_delete_id)
                return _to_ansi(render.render_confirm_delete(target), _term_width())
            except Exception:
                state.awaiting_delete_id = None
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

    def _cancel_pending_confirms(_buffer=None):
        # Any movement of input or selection cancels a pending delete confirm.
        state.awaiting_delete_id = None

    input_buffer.on_text_changed += _cancel_pending_confirms

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
        if state.awaiting_delete_id is not None:
            return FormattedText([
                ("ansiyellow bold",
                 "  press y to confirm delete  ·  any other key cancels"),
            ])
        return FormattedText([
            ("ansibrightblack",
             "  ↑↓ select  ·  space toggle  ·  enter detail  ·  e edit  ·  d delete (asks y/n)  ·  ctrl-d quit"),
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
    awaiting_delete = Condition(lambda: state.awaiting_delete_id is not None)
    not_awaiting = Condition(lambda: state.awaiting_delete_id is None)

    @kb.add("enter")
    def _enter(event):
        line = input_buffer.text
        if line:
            input_buffer.reset()
            result = run_command(line, storage, config)
            if result.clear:
                state.last_result = None
            else:
                state.last_result = result
            if result.exit:
                event.app.exit()
            return
        # Empty input + Enter: open detail of selected todo
        sel = _selected_todo()
        if sel is not None:
            state.last_result = run_command(f"/show {sel.id}", storage, config)

    @kb.add("up", filter=empty_input)
    def _up(event):
        _cancel_pending_confirms()
        state.selected_index = max(0, state.selected_index - 1)

    @kb.add("down", filter=empty_input)
    def _down(event):
        _cancel_pending_confirms()
        todos = _visible_todos()
        state.selected_index = min(max(0, len(todos) - 1), state.selected_index + 1)

    @kb.add("space", filter=empty_input & not_awaiting)
    def _toggle_done(event):
        sel = _selected_todo()
        if sel is None:
            return
        storage.update(sel.id, done=not sel.done)

    @kb.add("d", filter=empty_input & not_awaiting)
    def _arm_delete(event):
        sel = _selected_todo()
        if sel is None:
            return
        state.awaiting_delete_id = sel.id

    @kb.add("y", filter=empty_input & awaiting_delete)
    def _confirm_delete(event):
        target_id = state.awaiting_delete_id
        state.awaiting_delete_id = None
        if target_id is None:
            return
        try:
            storage.delete(target_id)
        except Exception:
            pass
        state.last_result = None

    @kb.add("n", filter=empty_input & awaiting_delete)
    def _cancel_delete(event):
        state.awaiting_delete_id = None

    @kb.add("e", filter=empty_input & not_awaiting)
    def _prefill_edit(event):
        sel = _selected_todo()
        if sel is None:
            return
        input_buffer.text = f"/edit {sel.id} text "
        input_buffer.cursor_position = len(input_buffer.text)

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
