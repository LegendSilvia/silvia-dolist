"""Renderers in the clack visual idiom.

Every block has the shape:
    ◆  Header
    │
    │  body...
    │
"""
from __future__ import annotations
from datetime import date as _date, datetime as _datetime, time as _time, timedelta as _timedelta

from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.segment import Segment
from rich.style import Style
from rich.table import Table
from rich.text import Text

from todo_cli import symbols as S
from todo_cli.models import Todo


class _GutterBlock:
    """Render header, then every line of body prefixed with `│  ` (dim cyan)."""

    def __init__(self, header: RenderableType, body: RenderableType):
        self.header = header
        self.body = body

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield from console.render(self.header, options)
        bar_style = Style.parse(S.S_GUTTER)
        bar_alone = Segment(S.BAR, bar_style)
        bar_with_pad = Segment(S.BAR + "  ", bar_style)
        yield bar_alone
        yield Segment.line()
        body_opts = options.update(width=max(1, options.max_width - 3))
        for line in console.render_lines(self.body, body_opts, pad=False):
            yield bar_with_pad
            yield from line
            yield Segment.line()
        yield bar_alone
        yield Segment.line()

_PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2}
_MAX_DATE = _date(9999, 12, 31)


def _sort_key(t: Todo):
    return (
        _PRIORITY_ORDER.get(t.priority or "", 3),
        t.due or _MAX_DATE,
        t.id,
    )


def _gutter_block(header: Text, body: RenderableType) -> _GutterBlock:
    return _GutterBlock(header, body)


def _header(symbol: str, sym_style: str, *parts: str | tuple[str, str]) -> Text:
    t = Text()
    t.append(symbol + "  ", style=sym_style)
    for p in parts:
        if isinstance(p, tuple):
            t.append(p[0], style=p[1])
        else:
            t.append(p)
    return t


def _priority_style(priority: str | None) -> str:
    return {
        "high": S.S_PRIORITY_HIGH,
        "med": S.S_PRIORITY_MED,
        "low": S.S_PRIORITY_LOW,
    }.get(priority or "", "")


def _priority_label(priority: str | None) -> Text:
    if not priority:
        return Text("")
    return Text(priority.upper(), style=_priority_style(priority))


def _format_due(d: _date | None, t: _time | None = None) -> str:
    if not d:
        return ""
    base = d.strftime("%a %b %d")
    if t is not None:
        return f"{base} {t.strftime('%H:%M')}"
    return base


def _due_style(d: _date | None, t: _time | None, *, now: _datetime | None = None) -> str:
    """Pick a Rich style for a due indicator based on how close it is."""
    if d is None:
        return S.S_DIM
    if now is None:
        now = _datetime.now()
    if t is not None:
        deadline = _datetime.combine(d, t)
    else:
        # Date-only: treat the deadline as end of day.
        deadline = _datetime.combine(d, _time(23, 59))
    delta = deadline - now
    secs = delta.total_seconds()
    if secs < 0:
        return "bold red"          # overdue
    if secs < 3600:
        return "bold rgb(255,140,40)"   # within 1 hour: bright orange
    if d == now.date():
        return "yellow"            # later today
    if d == now.date() + _timedelta(days=1):
        return "rgb(220,180,100)"  # tomorrow: warm tone
    if d <= now.date() + _timedelta(days=7):
        return ""                  # this week: default
    return S.S_DIM                 # further out: dim


# --- public renderers -------------------------------------------------


def render_added(todo: Todo) -> RenderableType:
    header = _header(
        S.SUBMIT, S.S_SUBMIT,
        "Added ",
        (f"#{todo.id}", S.S_ID),
        f"  {S.DOT}  ",
        todo.text,
    )
    extras: list[str] = []
    if todo.due:
        if todo.due_time:
            extras.append(f"due {todo.due.isoformat()} {todo.due_time.strftime('%H:%M')}")
        else:
            extras.append(f"due {todo.due.isoformat()}")
    if todo.priority:
        extras.append(f"{todo.priority} priority")
    if todo.tags:
        extras.append(", ".join(f"#{t}" for t in todo.tags))
    if todo.project:
        extras.append(f"@{todo.project}")
    if not extras:
        return Group(header)
    body = Text(f"  {S.DOT}  ".join(extras), style=S.S_DIM)
    return _gutter_block(header, body)


def render_info(message: str) -> Text:
    return _header(S.INFO, S.S_ACTIVE, message)


def render_error(message: str) -> Text:
    return _header(S.ERROR, S.S_ERROR, message)


def render_warn(message: str) -> Text:
    return _header(S.WARN, S.S_WARN, message)


def render_todo_list(
    todos: list[Todo],
    *,
    label: str = "open",
    selected_id: int | None = None,
) -> RenderableType:
    count = len(todos)
    header = _header(
        S.ACTIVE, S.S_ACTIVE,
        "Todos  ", (S.DOT + "  ", S.S_DIM),
        (f"{count} {label}", S.S_DIM),
    )
    if count == 0:
        return _gutter_block(header, Text("No todos.", style=S.S_DIM))

    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column(no_wrap=True)  # cursor marker
    table.add_column(no_wrap=True)  # done glyph
    table.add_column(justify="right", no_wrap=True)  # id
    table.add_column(no_wrap=True)  # priority
    table.add_column(no_wrap=True)  # due
    table.add_column(overflow="fold")  # text + meta

    for t in sorted(todos, key=_sort_key):
        is_selected = selected_id is not None and t.id == selected_id
        cursor = Text("›" if is_selected else " ", style=S.S_ACTIVE if is_selected else "")
        row_style = "reverse" if is_selected else ""
        glyph_style = S.S_SUBMIT if t.done else S.S_DIM
        glyph = Text(S.SUBMIT if t.done else S.RADIO_OFF, style=glyph_style)
        id_text = Text(f"#{t.id}", style=S.S_ID)
        text_cell = Text(t.text, style=S.S_DIM if t.done else "")
        if t.description:
            text_cell.append("  ")
            text_cell.append("ⓘ", style=S.S_DIM)
        meta = []
        if t.tags:
            meta.append(" ".join(f"#{x}" for x in t.tags))
        if t.project:
            meta.append(f"@{t.project}")
        if meta:
            text_cell.append("  ")
            text_cell.append(f"  {S.DOT}  ".join(meta), style=S.S_DIM)
        due_style = _due_style(t.due, t.due_time) if not t.done else S.S_DIM
        table.add_row(
            cursor,
            glyph,
            id_text,
            _priority_label(t.priority),
            Text(_format_due(t.due, t.due_time), style=due_style),
            text_cell,
            style=row_style,
        )
    return _gutter_block(header, table)


def render_todo_detail(t: Todo) -> RenderableType:
    header = _header(
        S.ACTIVE, S.S_ACTIVE,
        "Todo ",
        (f"#{t.id}", S.S_ID),
    )
    lines: list[Text] = []
    title = Text(t.text, style="bold")
    if t.done:
        title.stylize(S.S_DIM)
    lines.append(title)
    if t.description:
        lines.append(Text(""))
        lines.append(Text(t.description, style=S.S_DIM if t.done else ""))
    lines.append(Text(""))

    facts: list[Text] = []
    facts.append(Text(f"status: {'done' if t.done else 'open'}", style=S.S_DIM))
    if t.priority:
        p = Text("priority: ", style=S.S_DIM)
        p.append(t.priority, style=_priority_style(t.priority))
        facts.append(p)
    if t.due:
        due_label = Text("due:      ", style=S.S_DIM)
        due_value = _format_due(t.due, t.due_time)
        due_label.append(due_value, style=_due_style(t.due, t.due_time))
        facts.append(due_label)
    if t.project:
        facts.append(Text(f"project:  @{t.project}", style=S.S_DIM))
    if t.tags:
        facts.append(Text("tags:     " + " ".join(f"#{x}" for x in t.tags), style=S.S_DIM))
    if t.claude_session:
        facts.append(Text(f"claude:   session {t.claude_session}", style=S.S_DIM))
    facts.append(Text(f"created:  {t.created_at.isoformat(timespec='minutes')}", style=S.S_DIM))
    if t.completed_at:
        facts.append(Text(f"done at:  {t.completed_at.isoformat(timespec='minutes')}", style=S.S_DIM))
    lines.extend(facts)
    return _gutter_block(header, Group(*lines))


def render_help(text: str) -> RenderableType:
    header = _header(S.ACTIVE, S.S_ACTIVE, "Commands")
    body = Text(text, style=S.S_DIM)
    return _gutter_block(header, body)


def render_mcp_setup(snippet: str, copied: bool) -> RenderableType:
    header = _header(S.ACTIVE, S.S_ACTIVE, "MCP setup")
    body = Text()
    body.append(
        "Add this to your MCP client config and reload it.\n",
        style=S.S_DIM,
    )
    body.append(
        "  Claude Code:  ~/.claude.json   (or %USERPROFILE%\\.claude.json)\n"
        "  Per-project:  .mcp.json in the project root\n\n",
        style=S.S_DIM,
    )
    body.append(snippet, style="cyan")
    body.append("\n")
    if copied:
        body.append("\nCopied to clipboard.", style="green")
    else:
        body.append(
            "\nClipboard tool not available — copy the block above manually.",
            style=S.S_WARN,
        )
    return _gutter_block(header, body)


def render_config(config, fields: list[tuple[str, str]]) -> RenderableType:
    header = _header(S.ACTIVE, S.S_ACTIVE, "Config")
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column(no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold")
    for field_name, description in fields:
        value = getattr(config, field_name, None)
        value_str = "(unset)" if value is None else str(value)
        value_style = S.S_DIM if value is None else ""
        table.add_row(
            Text(field_name, style=S.S_ID),
            Text(value_str, style=value_style),
            Text(description, style=S.S_DIM),
        )
    return _gutter_block(header, table)


def _value_repr(value):
    """How to display a Todo field value in the edit form."""
    if value is None:
        return "(none)", S.S_DIM
    if isinstance(value, list):
        if not value:
            return "(none)", S.S_DIM
        return ", ".join(str(v) for v in value), ""
    if isinstance(value, bool):
        return "yes" if value else "no", ""
    if hasattr(value, "isoformat"):
        # date / time
        return value.isoformat(), ""
    return str(value), ""


def render_confirm_delete(t: Todo) -> RenderableType:
    header = _header(
        S.WARN, S.S_WARN,
        "Delete ", (f"#{t.id}", S.S_ID), "?",
    )
    body = Text()
    body.append(t.text + "\n", style="bold")
    body.append("press ", style=S.S_DIM)
    body.append("y", style="bold green")
    body.append(" to confirm, ", style=S.S_DIM)
    body.append("esc", style="bold")
    body.append(" or any other key cancels.", style=S.S_DIM)
    return _gutter_block(header, body)


def render_edit_form(t: Todo, fields: list[tuple[str, str]], selected_index: int) -> RenderableType:
    title = t.text[:60] + ("…" if len(t.text) > 60 else "")
    header = _header(
        S.ACTIVE, S.S_ACTIVE,
        "Edit ", (f"#{t.id}", S.S_ID), f"  {S.DOT}  ", title,
    )
    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column(no_wrap=True)  # cursor
    table.add_column(no_wrap=True)  # label
    table.add_column(overflow="fold")  # value

    for i, (field, label) in enumerate(fields):
        is_selected = i == selected_index
        cursor = Text("›" if is_selected else " ",
                      style=S.S_ACTIVE if is_selected else "")
        row_style = "reverse" if is_selected else ""
        value_str, value_style = _value_repr(getattr(t, field, None))
        table.add_row(
            cursor,
            Text(label, style="" if is_selected else S.S_DIM),
            Text(value_str, style=value_style),
            style=row_style,
        )
    return _gutter_block(header, table)
