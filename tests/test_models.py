from datetime import date, datetime
from todo_cli.models import Todo


def test_minimal_todo_round_trip():
    t = Todo(id=1, text="buy milk", created_at=datetime(2026, 5, 7, 12, 0, 0))
    d = t.to_dict()
    assert d["id"] == 1
    assert d["text"] == "buy milk"
    assert d["due"] is None
    assert d["completed_at"] is None
    t2 = Todo.from_dict(d)
    assert t2 == t


def test_full_todo_round_trip():
    t = Todo(
        id=42,
        text="finish report",
        created_at=datetime(2026, 5, 7, 12, 0, 0),
        done=True,
        due=date(2026, 6, 1),
        priority="high",
        tags=["work", "urgent"],
        project="q3",
        completed_at=datetime(2026, 5, 8, 9, 30, 0),
    )
    t2 = Todo.from_dict(t.to_dict())
    assert t2 == t


def test_tags_default_is_independent_list():
    a = Todo(id=1, text="a", created_at=datetime(2026, 1, 1))
    b = Todo(id=2, text="b", created_at=datetime(2026, 1, 1))
    a.tags.append("x")
    assert b.tags == []
