from __future__ import annotations
import sys
from pathlib import Path

from todo_cli.config import Config
from todo_cli.errors import SchemaMismatch, StorageCorrupt
from todo_cli.storage import Storage
from todo_cli import repl


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    home = Path.home() / ".todo"
    storage_path = home / "todos.json"
    config_path = home / "config.json"
    history_path = home / "history"

    storage = Storage(storage_path)
    try:
        storage.load()
    except (StorageCorrupt, SchemaMismatch) as e:
        print(f"Error: {e}", file=sys.stderr)
        bak = storage_path.with_suffix(storage_path.suffix + ".bak")
        if bak.exists():
            print(f"Backup available: {bak}", file=sys.stderr)
        return 1

    config = Config.load(config_path)
    try:
        repl.run(storage, config, history_path)
    finally:
        config.save(config_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
