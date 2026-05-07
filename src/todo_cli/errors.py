class TodoError(Exception):
    """Base exception for todo_cli."""


class TodoNotFound(TodoError):
    """Requested todo id does not exist."""


class StorageCorrupt(TodoError):
    """Storage file is unparseable."""


class SchemaMismatch(TodoError):
    """Storage file is a version this build does not support."""


class BadCommandUsage(TodoError):
    """User supplied invalid arguments to a command."""
