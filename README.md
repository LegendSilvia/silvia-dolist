# todo-cli

A personal todo CLI with a persistent REPL and an MCP server, sharing one local JSON file. Designed for daily use; no cloud, no account.

## Install

```powershell
pip install -e .[dev]
```

This installs two console scripts: `todo` (REPL) and `todo-mcp` (MCP stdio server).

## Use the REPL

```powershell
todo
```

You'll get a prompt like:

```
todo (0 open) >
```

Type slash commands or free-form text:

- `/add buy milk --due 2026-05-08 --priority high --tags home` — add with metadata.
- `buy bread` — free-form text auto-adds as a todo.
- `/list` — open todos. `/list --all`, `/list --done`, `/list --tag work`, `/list --overdue`, `/list --today`.
- `/show <id>` — detail panel.
- `/done <id>` / `/undo <id>` — toggle completion.
- `/edit <id> <field> <value>` — fields: `text`, `due`, `priority`, `tags`, `project`, `done`.
- `/del <id>` — delete.
- `/help`, `/clear`, `/exit` (or `/quit`).

Typos like `lst` or `/dn` get suggestions instead of being added as todos.

## Use from Claude Code or another MCP client

Register the server in your MCP client config. For Claude Code (`%USERPROFILE%\.claude\settings.json`):

```json
{
  "mcpServers": {
    "todo": { "command": "todo-mcp" }
  }
}
```

Tools exposed: `list_todos`, `add_todo`, `show_todo`, `mark_done`, `mark_undone`, `edit_todo`, `delete_todo`.

## Storage

- File: `%USERPROFILE%\.todo\todos.json` (Windows) or `~/.todo/todos.json` (POSIX).
- Atomic writes; `.bak` file preserved each save; sidecar `.lock` file coordinates REPL + MCP concurrency.
- Schema versioned (`version: 1`); future builds migrate or refuse incompatible files.

## Concurrency

The REPL and MCP server can run simultaneously against the same file. Mutations are serialized via an OS file lock. Don't run multiple REPLs as a habit — it works, but the prompt's open-count is only refreshed at your prompt.

## Tests

```powershell
pytest
```

## Roadmap

Phase 2 (deferred): in-app AI parsing of free-form input via Anthropic Claude with prompt caching. Will go through its own brainstorm → spec → plan cycle.
