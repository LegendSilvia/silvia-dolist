# silvia-dolist

A personal todo app with a full-screen TUI and an MCP server, sharing one local JSON file. Designed for daily use; no cloud, no account.

The TUI shows a live landscape (sun/moon/clock/clouds), the open todo list, and an input line. AI agents can read and write the same data via MCP so you can hand a todo over to Claude with one command.

## Install

```powershell
pip install -e .[dev]
```

Installs two console scripts: `todo` (TUI / one-shot CLI) and `todo-mcp` (MCP stdio server).

## Quick start

```powershell
todo                          # full-screen TUI
todo /list                    # one-shot: print the list and exit
todo buy milk tomorrow #shop  # one-shot: add a todo and exit
```

## TUI controls

The TUI is a full-screen layout: landscape on top, todo list, last command output, hint line, input prompt.

**Selection (when input is empty):**
- **↑ / ↓** — move the `›` cursor up and down the open list.
- **space** — toggle done on the selected todo (reversible).
- **enter** — open detail of the selected todo.
- **enter again** (without moving) — hand the same todo to Claude (`/ask`). One press to look, second press to send.
- **esc** — close the edit form (when one is open).

**Commands** are typed at the input. Slash-prefixed; ID is optional when something is selected.

**Quit:** `Ctrl-D` or type `/exit`.

Raw alphabet keys never act on the list — they go to the input. So you can never lose data by pressing one wrong letter.

## Slash commands

ID is optional when an item is selected; the command operates on the selected row. `[id]` below means optional in the TUI.

| Command | Effect |
|---|---|
| `/add <text>` | Add a new todo. Text is parsed for date, priority, `#tags`, `@project`. |
| `/list [--all\|--done\|--tag X\|--project P\|--overdue\|--today]` | List todos. Default is open only. |
| `/show [id]` | Detail view (title, description, due, tags, project, timestamps). |
| `/done [id]` | Mark done. |
| `/undo [id]` | Mark not done. |
| `/edit [id] <field> <value>` | Update one field. See fields below. Replaces. |
| `/note [id] <text>` | Append a timestamped note to the description. Doesn't clobber prior content. |
| `/del [id]` | Delete one (asks y/n). |
| `/purge [days]` | Delete done todos older than N days. Defaults to `done_retention_days` from config when omitted. |
| `/ask [id]` | Open a new terminal with `claude`, copy a prompt about the todo to your clipboard so you can paste it in. |
| `/mcp` | Show how to register the MCP server with Claude Code (`claude mcp add todo todo-mcp` one-liner, plus the JSON snippet for manual config edits) and copy the JSON to your clipboard. |
| `/help` | Command summary. |
| `/clear` | Clear the output panel. |
| `/exit`, `/quit` | Save and exit. |

**Editable fields:** `text`, `description`, `due`, `due_time`, `priority` (`low`/`med`/`high`), `tags` (comma-separated), `project`, `done`. Use `/edit due_time none` to clear a time.

**Edit form.** Typing `/edit` (or `/edit 17`) without a field opens a navigable form panel showing all fields and their current values. Use ↑/↓ to pick a field, Enter to start editing it (the input gets pre-filled with `/edit <id> <field> <current>` so you just modify the value and press Enter), or Esc to close.

After you save a field, the form re-opens automatically so you can keep editing other fields. Press Esc when you're done.

**Delete confirm.** `/del` (or `/del 17`) opens a confirmation panel showing the todo about to be deleted. Press **y** to confirm, **n** or **Esc** to cancel. ↑/↓ and Space are blocked while the confirm is up — only y, n, Esc, or starting to type a new command will dismiss it.

## Free-form input (natural language)

Anything you type without a leading `/` becomes an `/add`. Before storing, the line is parsed for:

- **Dates:** `tomorrow`, `next monday`, `friday`, `in 3 days`, `2026-05-15`, plus short forms `tmr`, `tdy`, `eod`, `eow`, `eom`.
- **Times:** `tonight`, `this evening`, `at 3pm`, `5pm`. Captured into `due_time` so the list shows e.g. `Fri May 08 18:00`.
- **Priority:** `urgent`, `p1`, `high priority` → high. `p2`, `med priority` → med. `p3`, `low priority` → low.
- **Tags:** `#tag`.
- **Project:** `@project`.

Examples:

```
finish report by friday #work @q2 p1
buy milk tmr
call dentist tonight
review pr next monday at 9am
```

The parser is conservative: a date phrase is only stripped if it sits at the end of the line or follows a trigger word (`due`, `by`, `on`, `before`, `after`). Mid-sentence dates (`remember tomorrow's meeting`) are left in the title untouched. Explicit `--flags` always win over the parsed values.

## Due-date colors

The list color-codes the due indicator by how close the deadline is:

| State | Color |
|---|---|
| Overdue | bold red |
| Within the next hour | bold orange |
| Later today | yellow |
| Tomorrow | warm tan |
| This week | default |
| Further out / no due | dim |

## /ask — hand a todo to Claude

`/ask` takes a todo, builds a prompt that includes the title, description, due, priority, tags, and project, then opens a new terminal with `claude` started **interactively with the prompt already loaded** — no pasting needed. The prompt also tells Claude how to read the rest of your list using the `todo` CLI itself (`todo /list`, `todo /show <id>`) so it has cross-context before answering. Claude is asked to *propose* state changes rather than run them — you stay in control of edits and deletes.

**Resumable sessions.** First `/ask` on a todo names a Claude session like `todo-17-abc12345` and stores the name on the todo. Subsequent `/ask` calls resume that same session via `claude --resume <name>`, so the conversation picks up where it left off — useful when a todo isn't solved in one day. The session name shows up in `/show` detail and in the edit form (you can clear it with `/edit claude_session none` to start fresh next time).

**Working directory.** By default, the new terminal opens in todo-cli's own working directory. Set `agent_terminal_cwd` to make it open somewhere else (your project root, your scratch dir, etc.):

```
/config agent_terminal_cwd C:\Users\me\projects\foo
/config agent_terminal_cwd ~/work        # ~ expands
/config agent_terminal_cwd none          # clear
/config                                  # show all settings
```

Settings persist in `~/.todo/config.json`.

## Done todos and cleanup

`/done` doesn't delete — it sets `done: true` and stamps `completed_at`. Done todos stay in storage so you can look back at what you've finished. They're hidden from `/list` by default; use `/list --done` to see them or `/list --all` for everything.

When you want to clean up old completed work:

```
/purge 30                                # delete done todos older than 30 days
/purge                                   # uses done_retention_days from config
/config done_retention_days 30           # set the default
```

Only done todos older than the cutoff are removed; open todos and recently-done todos are untouched. Run it whenever you want — there's no auto-purge.

**Detail view.** Pressing Enter on a selected todo opens its detail in the output panel — title, description, due, priority, tags, project, timestamps. Esc closes it. ↑/↓ also closes it (you've moved on). The detail re-renders live so changes from the MCP server show up.

**Two-step flow.** `/ask` is gated behind a detail view so you confirm what's about to be sent off:

1. Select the todo with ↑/↓.
2. Press **Enter** to open its detail panel — review what's there.
3. Press **Enter again** (without moving the selection) to send it to Claude — same as typing `/ask`. The prompt goes to your clipboard and a new terminal pops up with `claude`.

You can also type `/ask` instead of pressing Enter twice; same guard applies.

If you call `/ask` without first viewing the detail (or if you've moved the selection / done another command since), the TUI will tell you to press Enter first. Add an explicit ID (`/ask 7`) and view that ID's detail (`/show 7`) if you want to keep the selection elsewhere.

Requirements:
- `claude` must be on your PATH (Claude Code).
- Clipboard: Windows uses `clip.exe` (built-in). macOS uses `pbcopy`. Linux tries `xclip` then `xsel`.
- New terminal: Windows tries Windows Terminal (`wt`) then falls back to `cmd`. macOS uses `osascript` + Terminal.app. Linux tries common emulators (`gnome-terminal`, `konsole`, `xterm`).

If a step fails (no clipboard, no terminal launcher), `/ask` reports what worked and what didn't — the prompt is still in the output you can copy manually.

## Storage

- **File:** `%USERPROFILE%\.todo\todos.json` (Windows) or `~/.todo/todos.json` (POSIX).
- Atomic writes (`os.replace`); a `.bak` is kept beside the live file each save.
- Sidecar `.lock` file coordinates concurrent access between the TUI and the MCP server.
- Schema is versioned (`version: 1`). Unknown fields in old JSON are tolerated, so adding new optional fields (like `description`, `due_time`) doesn't require migration.

## Concurrency

The TUI and the MCP server can run simultaneously against the same file. Mutations are serialized through an OS file lock (`msvcrt` on Windows, `fcntl` elsewhere). Reads inside the TUI are debounced by the prompt_toolkit refresh interval (2 s).

## Tests

```powershell
pytest
```

## Project layout

```
src/todo_cli/
  __main__.py     entry point: TUI when no args, one-shot otherwise
  tui.py          full-screen prompt_toolkit Application
  repl.py         older scrolling REPL (kept as fallback)
  commands.py     slash command handlers, free-form add
  parse_text.py   natural-language extraction (dates, tags, priority)
  render.py       clack-style renderers (gutter blocks, list, detail)
  symbols.py      unicode glyphs + ASCII fallbacks
  sky.py          decorative landscape (sun/moon/stars/clock/clouds)
  ask.py          /ask helper (clipboard + new terminal)
  storage.py      JSON storage with file locking
  models.py       Todo dataclass + JSON round-trip
  config.py       optional user config (forward-compat)
  mcp_server.py   MCP stdio server exposing todo tools
  errors.py       typed exceptions
  suggest.py      typo suggestions for slash commands
```

## For AI agents

See [AGENTS.md](AGENTS.md) for the MCP tool surface and recommended usage patterns.
