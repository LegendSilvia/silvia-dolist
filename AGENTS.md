# Agent guide for todo-cli

This file is for AI agents (Claude, GPT, custom tools) that connect to this project's MCP server. It explains the data model, the available tools, and what to expect.

## How to connect

`todo-mcp` is a stdio MCP server. Register it in your client config:

```json
{
  "mcpServers": {
    "todo": { "command": "todo-mcp" }
  }
}
```

The server reads and writes the same JSON file (`~/.todo/todos.json`) that the user's `todo` TUI uses. Concurrent access is safe — both processes coordinate through a sidecar `.lock` file.

## Data model

A todo has these fields. Treat any that aren't listed in your input schema as optional/null.

| Field | Type | Notes |
|---|---|---|
| `id` | int | Stable, monotonically increasing. |
| `text` | string | Short title — what the user calls the task. |
| `description` | string \| null | Longer notes, multi-line. Use this for context the title can't carry. |
| `done` | bool | Default false. |
| `due` | ISO date (`YYYY-MM-DD`) \| null | Date only; pair with `due_time` for a specific moment. |
| `due_time` | ISO time (`HH:MM`) \| null | If set, `due` should also be set. |
| `priority` | `"low"` \| `"med"` \| `"high"` \| null | |
| `tags` | string[] | Free-form labels. The user types them as `#tag`. |
| `project` | string \| null | Single project label. The user types it as `@project`. |
| `created_at` | ISO datetime | Set by the server on add. |
| `completed_at` | ISO datetime \| null | Set when `done` flips to true; cleared when flipped back. |

## Tools

The MCP server exposes these tools. Errors come back as objects with a `code` field: `not_found`, `invalid_args`, or `internal`.

### `list_todos`
List todos. All filter args are optional and combine with AND.
- `done`: bool — true to include only done items, false (default) for open only, omit for both.
- `tag`: string
- `project`: string
- `overdue`: bool — past `due` and not done.
- `today`: bool — `due == today`.

Returns: array of todo objects.

### `add_todo`
Create a new todo.
- `text` (required): string
- `description`: string
- `due`: ISO date string
- `due_time`: ISO time string
- `priority`: `"low"` | `"med"` | `"high"`
- `tags`: string[]
- `project`: string

Returns: the created todo (with assigned `id`).

### `show_todo`
- `id` (required): int.

Returns: the matching todo, or `not_found` error.

### `mark_done` / `mark_undone`
- `id` (required): int.

Returns: the updated todo.

### `edit_todo`
- `id` (required): int
- Any subset of mutable fields: `text`, `description`, `due`, `due_time`, `priority`, `tags`, `project`, `done`.

Returns: the updated todo.

### `delete_todo`
- `id` (required): int.

Returns: confirmation. Deletes are not reversible — be cautious.

## Patterns and conventions

**Picking what to update.** When the user describes a todo by content rather than ID ("the dentist one"), call `list_todos` first, find the best match by `text`/`description`/`tags`, then act on the `id`.

**Adding rich context.** If the user gives you a multi-paragraph briefing, put the headline in `text` and the rest in `description`. The TUI list shows just `text`; `description` shows up in `/show`.

**Dates and times.** Always send ISO strings. The user's TUI parses natural language for them; the MCP surface is structured to keep agents deterministic. If you derive a date from "next Friday", compute it before calling, don't pass the phrase.

**Priority semantics.** `high` is for "do today / blocking". `med` is the unmarked default for important work. `low` is "if I have time". Don't escalate priority without explicit user signal.

**Don't auto-delete.** Even if a user says "clean up old todos", prefer marking them done over deleting. Delete is permanent; done is reversible (`mark_undone`).

**Tag and project hygiene.** Reuse existing tags/projects when they fit — call `list_todos` to see what's in use rather than inventing variants (`work` vs `Work` vs `wrk`). The user types these by hand and inconsistencies hurt their filters.

**Concurrent edits.** The user may be in the TUI while you're acting. After a destructive op, re-read with `show_todo` or `list_todos` rather than assuming local state. The TUI auto-refreshes on its 2s tick.

## What's NOT exposed

Some things the user can do are deliberately TUI-only and have no MCP equivalent:

- The `/ask` command (which calls back into Claude) — agents don't need to recurse.
- TUI navigation (selection, hotkeys).
- Settings / config.

If the user wants you to do something that maps to a TUI-only action, do the underlying state change via the regular tools and tell them what you did.

## How `/ask` reaches you

The user can press a single command in their TUI (`/ask` after viewing a todo's detail) to spawn a new terminal running `claude` with a pre-built prompt copied to their clipboard. The prompt format is:

```
I'm working on this todo and would like your help:

- Title: ...
- Description: ...
- Due: 2026-05-15 17:00
- Priority: high
- Tags: work, urgent
- Project: q2

Please help me think through how to approach this — break it into steps,
surface anything I might be missing, and suggest a concrete first action.
```

When you receive that prompt, you don't need to fetch the todo via MCP — the user already has the context inline. Acknowledge what they're working on, then engage with the actual task. If they want you to update the todo afterwards (mark done, add a note, change priority), use `edit_todo` / `mark_done` / `mark_undone`.
