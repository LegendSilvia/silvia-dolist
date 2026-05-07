# CLI Todo App — Design

- **Date:** 2026-05-07
- **Status:** Approved (phase 1 scope)
- **Author:** Tanwa (with Claude Code, brainstorming skill)

## Summary

A persistent-REPL Python CLI for managing personal todos with rich metadata (text, due date, priority, tags, project). Slash commands drive all behavior. Free-form text auto-creates a todo. Polished output via `rich`; ergonomic input (history, completion) via `prompt_toolkit`. Storage is a single JSON file under the user's home directory.

The same package ships a second entry point — an MCP server (`todo-mcp`) — so Claude Code and other MCP clients can read and write the same list. The todo list functions as a shared work log between user and AI agents.

Phase 2 (deferred) will add an optional in-app AI layer that parses natural-language REPL input into structured actions via Anthropic Claude. Phase 1 must be fully working and tested before phase 2 begins.

## Goals

- Daily-use personal tool — reliability and ergonomics matter more than feature breadth.
- Persistent REPL feel ("kinda like Claude CLI"): launch once, stay in a prompt loop.
- Slash commands cover every action; nothing requires AI.
- Polished output: colors, tables, panels, spinners.
- Same package ships an MCP server so external AI agents can read/write todos against the same data.
- Clean module boundaries so phase-2 in-app AI integration slots in without churning the core.
- High test coverage on storage and command logic.

## Non-Goals (phase 1)

- Multi-user / multi-machine sync — local-only.
- Networked replication — concurrency between REPL and MCP server is in scope (file locking), but nothing crosses machines.
- Recurring todos, subtasks, attachments — out of scope for v1.
- In-app natural-language parsing of free-form REPL input — phase 2. (External AI access via MCP is in phase 1.)
- TUI (full-screen widgets) — REPL only.
- Time-of-day on due dates — date-only.

## Architecture

Single Python package, installable with `pip install -e .`, exposing two console scripts: `todo` (REPL) and `todo-mcp` (MCP stdio server). Both share the same `Storage` against the same `todos.json`.

```
todo-cli/
├── pyproject.toml
├── README.md
├── src/todo_cli/
│   ├── __init__.py
│   ├── __main__.py          # entry point: `python -m todo_cli` or `todo`
│   ├── repl.py              # input loop + prompt_toolkit setup
│   ├── commands.py          # slash command dispatcher + handlers
│   ├── storage.py           # JSON file I/O + file locking, behind a Storage class
│   ├── models.py            # Todo dataclass + serialization
│   ├── config.py            # ~/.todo/config.json (settings)
│   ├── render.py            # rich-based output (tables, panels, spinners)
│   ├── suggest.py           # fuzzy command suggestions
│   ├── mcp_server.py        # stdio MCP server exposing Storage as tools
│   └── errors.py            # typed exceptions
└── tests/
    ├── test_storage.py
    ├── test_models.py
    ├── test_commands.py
    ├── test_suggest.py
    ├── test_render.py
    ├── test_mcp_server.py
    └── test_repl.py
```

### Module boundaries

- `repl.py` — owns input/output. Hands lines to `commands.py`, renders results via `render.py`. Receives `Storage` and `Config` instances from `__main__` rather than constructing them; reads from them only for prompt state (e.g., open-todo count).
- `commands.py` — orchestrator. Parses slash commands, dispatches handlers, invokes `storage`, returns `CommandResult`.
- `storage.py` — sole owner of the JSON file. Wraps mutations in a file lock so REPL and MCP server can run concurrently.
- `models.py` — `Todo` dataclass + (de)serialization. Pure.
- `config.py` — `Config` dataclass + JSON persistence for user settings.
- `render.py` — pure functions returning `rich` renderables.
- `suggest.py` — pure fuzzy-match function. Stdlib only (`difflib`).
- `mcp_server.py` — stdio MCP server. Constructs its own `Storage` instance pointed at the same JSON file the REPL uses. Tool handlers are thin shims over `Storage`; no command parsing, no rendering. Does not import `repl`, `commands`, `render`, or `suggest`.
- `errors.py` — typed exception hierarchy.

Each file is small enough to hold in one reader's head; `commands.py`, `storage.py`, and `mcp_server.py` are the only modules with non-trivial logic.

## Data model

```python
@dataclass
class Todo:
    id: int                                          # monotonic, never reused
    text: str
    done: bool = False
    due: date | None = None                          # ISO date, no time
    priority: Literal["low", "med", "high"] | None = None
    tags: list[str] = field(default_factory=list)   # ["work", "urgent"]
    project: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
```

`Todo.to_dict()` / `Todo.from_dict()` handle JSON serialization (dates → ISO strings).

## Storage

**File:** `%USERPROFILE%\.todo\todos.json` (Windows) / `~/.todo/todos.json` (POSIX).

**Format:**

```json
{
  "version": 1,
  "next_id": 42,
  "todos": [ { "id": 1, "text": "...", ... }, ... ]
}
```

**`Storage` class:**

```python
class Storage:
    def __init__(self, path: Path): ...
    def load(self) -> None
    def list(self, *, done: bool | None = None,
             tag: str | None = None,
             project: str | None = None,
             overdue: bool = False,
             today: bool = False) -> list[Todo]
    def get(self, id: int) -> Todo
    def add(self, todo: Todo) -> Todo                # assigns id from next_id
    def update(self, id: int, **fields) -> Todo
    def delete(self, id: int) -> None
```

**Persistence strategy:** Atomic write. Every mutation writes the full JSON to `todos.json.tmp` then `os.replace()` over the real file — no partial writes if the process dies. Previous version kept as `todos.json.bak`. Acceptable up to ~10k todos.

**Concurrency:** REPL and MCP server can run simultaneously, so writers can interleave. `Storage` reads and mutations run inside a file-lock context manager — `msvcrt.locking` on Windows, `fcntl.flock` on POSIX. Writes take an exclusive lock; reads take a shared lock; locks are held only across a single load+modify+atomic-write cycle (millisecond-scale). Stdlib only — no new deps. Lock granularity is the whole file; acceptable at this scale.

**Schema versioning:** Top-level `version: 1` field. Loader rejects unknown versions with a clear error so future migrations have a hook.

## REPL

**Prompt:**

```
todo (12 open) >
```

Open-todo count refreshes after every command.

**Input handling (`repl.py`):**

- `prompt_toolkit.PromptSession` with:
  - Persistent history at `%USERPROFILE%\.todo\history`
  - Slash-command tab-completion
  - Ctrl+C cancels current line; Ctrl+D saves and exits.
- Each line is `shlex.split`. If `tokens[0]` starts with `/`, dispatch to `commands.py`. Otherwise treat as free-form (see below).

**Free-form input (no leading `/`):**

Auto-add. The line becomes `/add <line>`. Example: typing `buy milk` is equivalent to `/add buy milk`. The `suggest.py` layer runs first — if the first token closely matches a known slash command, the REPL surfaces a hint instead of adding (see Suggest layer).

This is the simplest mapping from common typing to common action. Phase 2 replaces this path with AI parsing.

## Commands

| Command | Behavior |
|---|---|
| `/add <text> [--due YYYY-MM-DD] [--priority low\|med\|high] [--tags a,b] [--project p]` | Insert todo |
| `/list [--all] [--done] [--tag X] [--project P] [--overdue] [--today]` | Default: open todos. Rich table sorted by priority then due date |
| `/show <id>` | Detail panel for one todo |
| `/done <id>` / `/undo <id>` | Toggle `done` + set/clear `completed_at` |
| `/edit <id> <field> <value>` | Edit one field (text, due, priority, tags, project) |
| `/del <id>` | Delete (no confirm in v1) |
| `/help` | Print command list |
| `/clear` | Clear screen |
| `/exit` / `/quit` | Save and exit |

**Handler shape:** Each command is a function `(args: list[str], storage: Storage, config: Config) -> CommandResult`. `CommandResult` carries either a renderable (table/panel/text) or an error message. `repl.py` hands the result to `render.py`.

**Argument parsing:** stdlib `argparse.ArgumentParser` per command, configured with `exit_on_error=False` so a bad flag surfaces as an error message rather than killing the REPL.

## Suggest layer (`suggest.py`)

Pure stdlib function:

```python
def suggest(input_token: str, commands: list[str], n: int = 3) -> list[str]
```

Wraps `difflib.get_close_matches`. Two trigger points in `commands.py`:

1. **Unknown slash command** (`/lst buy milk`):
   ```
   Unknown command: /lst
   Did you mean: /list, /done?
   ```
   No execution. User retries.

2. **Free-form, first token close-matches a command** (`lst`):
   ```
   Did you mean: /list? (use /add lst to add as a todo)
   ```
   Auto-add is aborted to avoid creating a phantom todo from a typo. To add the literal text, the user retypes with an explicit `/add` prefix. Threshold is conservative (`cutoff=0.7`) so common words don't trigger.

## MCP server (`mcp_server.py`)

A second entry point packaged in the same module as the REPL. Run via:

```
todo-mcp
```

Communicates over stdio per the MCP standard. Registered in an MCP client's config (e.g., Claude Code's `settings.json`):

```json
{
  "mcpServers": {
    "todo": { "command": "todo-mcp" }
  }
}
```

**Tools exposed** (1:1 with command handlers, but pre-parsed args from the SDK):

| MCP tool | Backed by |
|---|---|
| `list_todos(done?, tag?, project?, overdue?, today?)` | `Storage.list` |
| `add_todo(text, due?, priority?, tags?, project?)` | `Storage.add` |
| `mark_done(id)` / `mark_undone(id)` | `Storage.update` |
| `edit_todo(id, field, value)` | `Storage.update` |
| `delete_todo(id)` | `Storage.delete` |
| `show_todo(id)` | `Storage.get` |

Each tool returns structured JSON (todo dicts or status strings). No rendering — that's the client's job.

**Implementation:** Built on Anthropic's `mcp` Python SDK. Each tool handler is a thin shim:
1. Receive arguments as a dict from the SDK.
2. Call the corresponding `Storage` method.
3. Serialize result via `Todo.to_dict()` (or raise — exceptions get mapped to MCP error responses).

**Shared substrate:** The MCP server constructs its own `Storage` pointed at the canonical `todos.json`. The REPL does the same in its own process. File locking in `Storage` keeps them safe to interleave. The JSON file is the single source of truth — no caches, no in-memory replicas.

**Error mapping:** `TodoNotFound` → MCP error with `code: "not_found"`. `BadCommandUsage` → `code: "invalid_args"`. `StorageCorrupt` / `SchemaMismatch` → `code: "internal"` and the server exits (we don't hand back inconsistent state). All others propagate.

## Error handling

Operational errors keep the REPL alive; integrity errors exit cleanly. The MCP server maps the same exception hierarchy to MCP error responses (see above).

| Error | Source | User sees | REPL |
|---|---|---|---|
| Bad slash flag | `argparse` (no-exit) | Red error + usage string | Continues |
| Unknown command | dispatcher | "Unknown command: X — did you mean: ..." | Continues |
| Bad ID (`/done 999`) | `Storage.get` raises `TodoNotFound` | "No todo with id 999" | Continues |
| Corrupt `todos.json` | `Storage.load` JSONDecodeError | Path printed, offers restore from `.bak` | Exits |
| Unknown schema version | `Storage.load` | "File is version N, build supports 1" | Exits |
| Permission denied on storage dir | `Storage.__init__` | Path + actionable message | Exits |
| Ctrl+C mid-line | prompt_toolkit | Cancels current line | Continues |
| Ctrl+D | prompt_toolkit | Saves, clean exit | Exits |

**Exception hierarchy (`errors.py`):**

```
TodoError
├── TodoNotFound
├── StorageCorrupt
├── SchemaMismatch
└── BadCommandUsage
```

`repl.py` catches `TodoError` to distinguish "show error and continue" from unhandled exceptions (which propagate and exit).

## Testing

**Stack:** `pytest`, `pytest-cov`. No mocking framework beyond stdlib `unittest.mock`. Most modules are pure.

**Per-module focus:**

- **`storage.py`** — full coverage. CRUD round-trips; atomic-write behavior (kill-mid-save sim by patching `os.replace`); filtering; schema-version rejection; corrupt-file handling; backup restore; **file-lock contention** (two `Storage` instances against the same path interleaving writes — assert no torn state). Real filesystem via `tmp_path` fixture.
- **`models.py`** — serialization round-trip table-driven tests.
- **`commands.py`** — handler functions are pure: `(args, storage, config) → CommandResult`. Test each handler with a real in-memory `Storage` (tmp file). Cover happy paths + every error category.
- **`suggest.py`** — pure function; table-driven tests for fuzzy thresholds.
- **`render.py`** — light: assert renderables don't throw on edge inputs (empty list, very long text, unicode). Visual output not asserted.
- **`repl.py`** — minimal: line dispatch (slash vs free-form auto-add), Ctrl+C/D handling. prompt_toolkit interaction stubbed at the session boundary.
- **`mcp_server.py`** — each tool handler tested with a real `Storage` (tmp file), asserting JSON-serializable returns and error mapping. MCP framing/transport not tested here; that's SDK territory.

**TDD:** Each module gets tests first per superpowers TDD discipline. Implementation plan reflects this.

**Coverage:** ≥90% target on storage/commands/suggest/mcp_server. Lower acceptable elsewhere. Judgment over coverage worship.

## Phase 2 — In-app AI parsing (deferred, sketch only)

This is distinct from the phase-1 MCP server. The MCP server gives *external* AI agents access to the todo list. Phase 2 adds an *internal* AI layer that parses free-form REPL input from the user.

Trigger: phase 1 (REPL + MCP) is fully implemented and tested.

**Seam:** `commands.py`'s free-form path is a single function (currently auto-add). Phase 2 swaps that function's body to call `ai.parse(text) → Action`, mapping the returned `Action` to the same internal handlers slash commands already use.

**Likely additions:**
- `ai.py` — Anthropic SDK client, tool definitions matching command set, prompt caching (system + tools cached ephemeral), cost tracking.
- New REPL commands: `/ai on`, `/ai off`, `/cost`.
- Config keys: `ai_on`, `model`.
- Prompt indicator: `todo (12 open) [AI:on] >`.
- Equivalent-command hint: when AI executes an action, also show the slash command form so the user can learn the manual syntax.

**No code or tests for phase 2 belong in phase 1 deliverables.** Phase 2 will go through its own brainstorm → spec → plan cycle.

## Risks & open items

- `prompt_toolkit` and `rich` are large deps for a small tool. Acceptable trade — they deliver the polish requirement, both are stable.
- Auto-add can surprise a user who expects a slash command and forgets the `/`. The suggest layer mitigates the typo case. Accept the residual risk.
- Atomic write + JSON file is fine up to ~10k todos. If user grows past that, switch storage to SQLite behind the same `Storage` interface — contained change.
- File locking is whole-file, not row-level. With only two writers (REPL + MCP) and millisecond-scale operations, contention is negligible. Documented as a known trade-off.
- MCP SDK version churn: the `mcp` Python package is young. Pin a specific version in `pyproject.toml` and treat upgrades as deliberate.

## Appendix — pyproject summary (sketch)

- Python ≥ 3.11 (for `Literal`, modern dataclasses, `tomllib`).
- Runtime deps: `prompt_toolkit`, `rich`, `mcp` (pinned).
- Dev deps: `pytest`, `pytest-cov`.
- Console scripts:
  - `todo = todo_cli.__main__:main` — REPL.
  - `todo-mcp = todo_cli.mcp_server:main` — MCP stdio server.
