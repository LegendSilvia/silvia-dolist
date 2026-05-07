from __future__ import annotations
from datetime import date as _date

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from todo_cli.models import Todo

_PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2}
_MAX_DATE = _date(9999, 12, 31)


def _sort_key(t: Todo):
    return (
        _PRIORITY_ORDER.get(t.priority or "", 3),
        t.due or _MAX_DATE,
        t.id,
    )


def render_todo_list(todos: list[Todo]) -> Table:
    table = Table(title=f"Todos ({len(todos)})", show_lines=False)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Done", justify="center")
    table.add_column("Pri", justify="center")
    table.add_column("Due")
    table.add_column("Project")
    table.add_column("Tags")
    table.add_column("Text")
    for t in sorted(todos, key=_sort_key):
        table.add_row(
            str(t.id),
            "[green]✓[/green]" if t.done else "",
            (t.priority or "").upper(),
            t.due.isoformat() if t.due else "",
            t.project or "",
            ", ".join(t.tags),
            t.text,
        )
    return table


def render_todo_detail(t: Todo) -> Panel:
    body = Text()
    body.append(f"#{t.id}  ", style="bold cyan")
    body.append(t.text + "\n\n")
    body.append(f"Done: {'yes' if t.done else 'no'}\n")
    body.append(f"Priority: {t.priority or '—'}\n")
    body.append(f"Due: {t.due.isoformat() if t.due else '—'}\n")
    body.append(f"Project: {t.project or '—'}\n")
    body.append(f"Tags: {', '.join(t.tags) or '—'}\n")
    body.append(f"Created: {t.created_at.isoformat()}\n")
    if t.completed_at:
        body.append(f"Completed: {t.completed_at.isoformat()}\n")
    return Panel(body, title=f"Todo #{t.id}")


def render_error(message: str) -> Text:
    return Text(message, style="bold red")


def render_info(message: str) -> Text:
    return Text(message, style="green")
