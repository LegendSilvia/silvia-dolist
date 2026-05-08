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
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI, FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Float, FloatContainer, HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from rich.console import Console

from todo_cli import render
from todo_cli import symbols as S
from todo_cli.commands import CommandResult, run_command
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
        # Detail view is a modal mode (like the edit form / delete confirm).
        # When set, the output panel renders the detail freshly each tick;
        # esc closes it, enter again triggers /ask, ↑↓ or typing dismisses.
        self.viewing_detail_id: Optional[int] = None
        # Edit-form modal state. None = not in edit mode.
        self.edit_panel_id: Optional[int] = None
        self.edit_field_index: int = 0
        # When set, after the next /edit save the form re-opens for this id
        # at this field index. Lets the user keep editing fields without
        # re-opening the form by hand.
        self.resume_edit_for_id: Optional[int] = None
        # Delete-confirm modal state. None = not asking.
        self.awaiting_delete_id: Optional[int] = None


_ID_OPTIONAL_COMMANDS = {"/done", "/undo", "/show", "/del", "/ask", "/note"}


_COMMAND_HINTS: list[tuple[str, str]] = [
    ("/add", "add a new todo (NL parsed)"),
    ("/list", "list todos"),
    ("/show", "detail for the selected todo"),
    ("/done", "mark complete"),
    ("/undo", "mark not done"),
    ("/edit", "edit a field (or open the form)"),
    ("/note", "append a timestamped note (no clobber)"),
    ("/del", "delete (asks y/n)"),
    ("/ask", "send to claude in a new terminal"),
    ("/mcp", "show MCP registration snippet"),
    ("/config", "view or set settings"),
    ("/help", "command reference"),
    ("/clear", "clear output panel"),
    ("/exit", "save and exit"),
    ("/quit", "save and exit"),
]


class _SlashCompleter(Completer):
    """Inline completion for slash commands with one-line descriptions."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        # Only complete while typing the first token, and only if it starts with /
        if " " in text.strip() or "\t" in text:
            return
        first = text.lstrip()
        if not first.startswith("/"):
            return
        for cmd, desc in _COMMAND_HINTS:
            if cmd.startswith(first):
                yield Completion(
                    cmd,
                    start_position=-len(first),
                    display_meta=desc,
                )

# Field name + display label for the edit form, in the order shown.
_EDITABLE_FIELDS = [
    ("text", "Title"),
    ("description", "Description"),
    ("due", "Due date"),
    ("due_time", "Due time"),
    ("priority", "Priority"),
    ("tags", "Tags"),
    ("project", "Project"),
    ("claude_session", "Claude session"),
]


def _extract_command_id(line: str) -> Optional[int]:
    """Pull the numeric id out of a slash command, after autofill."""
    parts = line.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


_ID_PLUS_TEXT_COMMANDS = {"/edit", "/note"}


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
    if cmd in _ID_PLUS_TEXT_COMMANDS:
        if len(parts) == 1:
            return f"{cmd} {sel_id}"
        try:
            int(parts[1])
            return line  # explicit ID already present
        except ValueError:
            rest = line[len(cmd):].strip()
            return f"{cmd} {sel_id} {rest}"
    if cmd in _ID_OPTIONAL_COMMANDS:
        if len(parts) == 1:
            return f"{cmd} {sel_id}"
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
        if state.awaiting_delete_id is not None:
            try:
                target = storage.get(state.awaiting_delete_id)
                return _to_ansi(render.render_confirm_delete(target), _term_width())
            except Exception:
                state.awaiting_delete_id = None
        if state.edit_panel_id is not None:
            try:
                target = storage.get(state.edit_panel_id)
                return _to_ansi(
                    render.render_edit_form(target, _EDITABLE_FIELDS, state.edit_field_index),
                    _term_width(),
                )
            except Exception:
                state.edit_panel_id = None
        if state.viewing_detail_id is not None:
            try:
                target = storage.get(state.viewing_detail_id)
                return _to_ansi(render.render_todo_detail(target), _term_width())
            except Exception:
                state.viewing_detail_id = None
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
        completer=_SlashCompleter(),
        complete_while_typing=True,
        history=FileHistory(str(history_path)),
        multiline=False,
    )

    def _on_input_changed(_buffer):
        # Typing into the input dismisses any modal panel — the user
        # is clearly switching to typed-command mode. resume_edit_for_id
        # is intentionally preserved so the form can re-open after a save.
        state.awaiting_delete_id = None
        state.edit_panel_id = None
        state.viewing_detail_id = None

    input_buffer.on_text_changed += _on_input_changed

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
                 "  press y to confirm delete  ·  n or esc cancels"),
            ])
        if state.edit_panel_id is not None:
            return FormattedText([
                ("ansicyan",
                 "  ↑↓ pick field  ·  enter to edit value  ·  esc cancel"),
            ])
        if state.viewing_detail_id is not None:
            return FormattedText([
                ("ansicyan",
                 "  enter again = /ask claude  ·  esc close  ·  ↑↓ moves selection"),
            ])
        return FormattedText([
            ("ansibrightblack",
             "  ↑↓ select  ·  space toggle  ·  enter detail (twice = /ask)  ·  /edit opens form  ·  /del asks y/n  ·  ctrl-d quit"),
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

    main_split = HSplit([
        sky_panel,
        _divider(),
        todo_panel,
        _divider(),
        output_panel,
        _divider(),
        hints_window,
        input_window,
    ])

    layout = Layout(
        FloatContainer(
            content=main_split,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=8, scroll_offset=1),
                ),
            ],
        ),
        focused_element=input_window,
    )

    kb = KeyBindings()
    empty_input = Condition(lambda: not input_buffer.text)
    awaiting_delete = Condition(lambda: state.awaiting_delete_id is not None)

    def _enter_edit_value():
        """Inside the edit form: take the highlighted field, prefill the
        input with a /edit command pre-loaded with the current value, and
        close the form so the user types the new value and hits Enter.
        Mark the form to resume after the save."""
        target_id = state.edit_panel_id
        idx = state.edit_field_index
        state.edit_panel_id = None
        if target_id is None or not (0 <= idx < len(_EDITABLE_FIELDS)):
            return
        field, _label = _EDITABLE_FIELDS[idx]
        try:
            target = storage.get(target_id)
        except Exception:
            return
        value = getattr(target, field, None)
        if value is None:
            value_str = ""
        elif isinstance(value, list):
            value_str = ",".join(str(v) for v in value)
        elif hasattr(value, "isoformat"):
            value_str = value.isoformat()
        else:
            value_str = str(value)
        prefix = f"/edit {target_id} {field} "
        input_buffer.text = prefix + value_str
        input_buffer.cursor_position = len(input_buffer.text)
        state.resume_edit_for_id = target_id

    @kb.add("enter")
    def _enter(event):
        # Delete confirm is up: Enter is a no-op (must press y/n/esc).
        if state.awaiting_delete_id is not None and not input_buffer.text:
            return
        # Edit form is open: Enter picks the field to edit.
        if state.edit_panel_id is not None and not input_buffer.text:
            _enter_edit_value()
            return

        line = input_buffer.text.strip()
        if not line:
            sel = _selected_todo()
            if sel is None:
                return
            # Enter twice on the same selection: detail → /ask.
            if state.viewing_detail_id == sel.id:
                state.viewing_detail_id = None
                state.last_result = run_command(f"/ask {sel.id}", storage, config)
            else:
                state.viewing_detail_id = sel.id
                state.last_result = None
            return

        sel = _selected_todo()
        line = _autofill_selected_id(line, sel.id if sel else None)

        # /edit with just an id opens the visual edit form.
        if line.startswith("/edit"):
            parts = line.split(maxsplit=2)
            if len(parts) <= 2:
                target_id = None
                if len(parts) == 2:
                    try:
                        target_id = int(parts[1])
                    except ValueError:
                        target_id = None
                if target_id is None and sel is not None:
                    target_id = sel.id
                if target_id is None:
                    input_buffer.reset()
                    state.last_result = CommandResult(
                        renderable=render.render_warn("nothing selected to edit")
                    )
                    return
                try:
                    storage.get(target_id)
                except Exception:
                    input_buffer.reset()
                    state.last_result = CommandResult(
                        renderable=render.render_error(f"no todo with id {target_id}")
                    )
                    return
                state.edit_panel_id = target_id
                state.edit_field_index = 0
                state.viewing_detail_id = None
                input_buffer.reset()
                return

        # /del opens a confirm panel instead of executing immediately.
        if line.startswith("/del"):
            target_id = _extract_command_id(line)
            if target_id is None:
                input_buffer.reset()
                state.last_result = CommandResult(
                    renderable=render.render_warn("nothing selected to delete")
                )
                return
            try:
                storage.get(target_id)
            except Exception:
                input_buffer.reset()
                state.last_result = CommandResult(
                    renderable=render.render_error(f"no todo with id {target_id}")
                )
                return
            state.awaiting_delete_id = target_id
            input_buffer.reset()
            return

        # /ask still requires a prior view (typed-command path).
        if line.startswith("/ask"):
            target_id = _extract_command_id(line)
            if target_id is None or state.viewing_detail_id != target_id:
                input_buffer.reset()
                state.last_result = CommandResult(
                    renderable=render.render_warn(
                        "Press enter to view the todo's detail first, then /ask."
                    )
                )
                return

        # Typed /show enters detail mode directly (skip the run_command
        # path so the panel stays live, refreshes from state, and esc
        # closes it like any modal).
        if line.startswith("/show"):
            shown_id = _extract_command_id(line)
            if shown_id is not None:
                try:
                    storage.get(shown_id)
                    state.viewing_detail_id = shown_id
                    state.last_result = None
                    input_buffer.reset()
                    return
                except Exception:
                    pass

        input_buffer.reset()
        result = run_command(line, storage, config)
        if result.clear:
            state.last_result = None
        else:
            state.last_result = result
        # Any non-/show command invalidates the detail view.
        state.viewing_detail_id = None

        # If this was a /edit save and we have a pending resume marker,
        # re-open the edit form so the user can keep editing fields.
        if line.startswith("/edit") and state.resume_edit_for_id is not None:
            try:
                storage.get(state.resume_edit_for_id)
                state.edit_panel_id = state.resume_edit_for_id
                # Keep the same field index so the user can move with ↑↓.
            except Exception:
                pass
            state.resume_edit_for_id = None

        if result.exit:
            event.app.exit()

    @kb.add("up", filter=empty_input)
    def _up(event):
        if state.awaiting_delete_id is not None:
            return  # blocked while delete confirm is up; press y/n/esc
        if state.edit_panel_id is not None:
            state.edit_field_index = max(0, state.edit_field_index - 1)
            return
        state.selected_index = max(0, state.selected_index - 1)
        state.viewing_detail_id = None  # selection moved → /ask must re-view

    @kb.add("down", filter=empty_input)
    def _down(event):
        if state.awaiting_delete_id is not None:
            return
        if state.edit_panel_id is not None:
            state.edit_field_index = min(
                len(_EDITABLE_FIELDS) - 1, state.edit_field_index + 1
            )
            return
        todos = _visible_todos()
        state.selected_index = min(max(0, len(todos) - 1), state.selected_index + 1)
        state.viewing_detail_id = None

    @kb.add("space", filter=empty_input)
    def _toggle_done(event):
        if state.awaiting_delete_id is not None or state.edit_panel_id is not None:
            return
        sel = _selected_todo()
        if sel is None:
            return
        storage.update(sel.id, done=not sel.done)

    @kb.add("escape", eager=True)
    def _escape(event):
        # Esc cancels any open modal panel.
        cancelled = False
        if state.awaiting_delete_id is not None:
            state.awaiting_delete_id = None
            cancelled = True
        if state.edit_panel_id is not None:
            state.edit_panel_id = None
            cancelled = True
        if state.viewing_detail_id is not None:
            state.viewing_detail_id = None
            cancelled = True
        if state.resume_edit_for_id is not None:
            state.resume_edit_for_id = None
        if cancelled:
            state.last_result = None

    @kb.add("y", filter=empty_input & awaiting_delete)
    def _confirm_delete(event):
        target_id = state.awaiting_delete_id
        state.awaiting_delete_id = None
        if target_id is None:
            return
        try:
            storage.delete(target_id)
            state.last_result = CommandResult(
                renderable=render.render_info(f"Deleted #{target_id}")
            )
        except Exception:
            pass
        state.viewing_detail_id = None

    @kb.add("n", filter=empty_input & awaiting_delete)
    def _cancel_delete(event):
        state.awaiting_delete_id = None
        state.last_result = None

    @kb.add("c-c")
    @kb.add("c-d")
    def _quit(event):
        event.app.exit()

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
        refresh_interval=0.5,  # snappy redraws; cloud drift animates smoothly
    )
    app.run()
