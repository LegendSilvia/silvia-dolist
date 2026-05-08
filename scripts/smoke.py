"""End-to-end smoke driver. Run: python scripts/smoke.py"""
from __future__ import annotations
import shutil
import sys
import tempfile
from pathlib import Path

from rich.console import Console

from todo_cli.commands import run_command
from todo_cli.config import Config
from todo_cli.storage import Storage


def step(console: Console, storage: Storage, config: Config, line: str) -> None:
    console.rule(f"[bold cyan]> {line}")
    result = run_command(line, storage, config)
    if result.clear:
        console.print("[dim](screen clear requested)[/dim]")
    if result.renderable is not None:
        console.print(result.renderable)
    if result.exit:
        console.print("[dim](exit requested)[/dim]")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="todo-smoke-"))
    try:
        storage = Storage(tmp / "todos.json")
        storage.load()
        config = Config.load(tmp / "config.json")
        console = Console()

        sequence = [
            "/help",
            "/list",
            "/add buy milk",
            "buy bread",
            "/list",
            "/add finish report --due 2026-05-09 --priority high --tags work,urgent --project Q2",
            "/list",
            "/list --tag work",
            "/list --today",
            "/list --overdue",
            "/show 3",
            "/done 1",
            "/list",
            "/list --done",
            "/undo 1",
            "/edit 2 text whole-grain-bread",
            "/del 2",
            "/list",
            "/lst",
            "",
            "/help xyz",
            "/show 999",
        ]

        for line in sequence:
            step(console, storage, config, line)

        console.rule("[bold green]Smoke complete")
        console.print(f"Data dir: {tmp}")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
