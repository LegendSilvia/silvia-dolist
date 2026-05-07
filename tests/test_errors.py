import pytest
from todo_cli.errors import (
    TodoError,
    TodoNotFound,
    StorageCorrupt,
    SchemaMismatch,
    BadCommandUsage,
)


def test_subclasses_inherit_from_todo_error():
    assert issubclass(TodoNotFound, TodoError)
    assert issubclass(StorageCorrupt, TodoError)
    assert issubclass(SchemaMismatch, TodoError)
    assert issubclass(BadCommandUsage, TodoError)


def test_can_catch_subclass_as_base():
    with pytest.raises(TodoError):
        raise TodoNotFound("nope")


def test_message_round_trip():
    e = TodoNotFound("missing 7")
    assert str(e) == "missing 7"
