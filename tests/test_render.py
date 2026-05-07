from datetime import date, datetime

from todo_cli.models import Todo
from todo_cli.render import (
    render_error,
    render_info,
    render_todo_detail,
    render_todo_list,
)


def _t(id_: int = 1, **kw) -> Todo:
    base = dict(id=id_, text="x", created_at=datetime(2026, 1, 1, 0, 0, 0))
    base.update(kw)
    return Todo(**base)


def test_render_empty_list_does_not_throw():
    table = render_todo_list([])
    assert table is not None


def test_render_full_list():
    items = [
        _t(1, text="a"),
        _t(2, text="b", priority="high", due=date(2026, 6, 1), tags=["work"]),
    ]
    render_todo_list(items)


def test_render_detail_minimal():
    render_todo_detail(_t(1))


def test_render_detail_full():
    t = _t(
        1,
        text="hello",
        project="proj",
        tags=["a", "b"],
        priority="med",
        due=date(2026, 5, 7),
        done=True,
        completed_at=datetime(2026, 5, 7, 12, 0, 0),
    )
    render_todo_detail(t)


def test_render_unicode_in_text():
    render_todo_list([_t(1, text="café 日本語 🚀")])


def test_render_error_and_info():
    render_error("bad")
    render_info("ok")
