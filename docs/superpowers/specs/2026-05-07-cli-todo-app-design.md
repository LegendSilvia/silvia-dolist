# CLI Todo App — Design

- **Date:** 2026-05-07
- **Status:** Approved (phase 1 scope)
- **Author:** Tanwa (with Claude Code, brainstorming skill)

## Summary

A persistent-REPL Python CLI for managing personal todos with rich metadata (text, due date, priority, tags, project). Slash commands drive all behavior. Free-form text auto-creates a todo. Polished output via `rich`; ergonomic input (history, completion) via `prompt_toolkit`. Storage is a single JSON file under the user's home directory.

Phase 2 (deferred) will add an optional AI layer that parses natural-language input into structured actions via Anthropic Claude. Phase 1 must be fully working and tested before phase 2 begins.

## Goals

- Daily-use personal tool — reliability and ergonomics matter more than feature breadth.
- Persistent REPL feel ("kinda like Claude CLI"): launch once, stay in a prompt loop.
- Slash commands cover every action; nothing requires AI.
- Polished output: colors, tables, panels, spinners.
- Clean module boundaries so phase-2 AI integration slots in without churning the core.
- High test coverage on storage and command logic.

## Non-Goals (phase 1)

- Multi-user / sync / cloud — single-user, single-machine only.
- Concurrent processes — last-writer-wins is acceptable; documented in README.
- Recurring todos, subtasks, attachments — out of scope for v1.
- AI / natural-language parsing — phase 2.
- TUI (full-screen widgets) — REPL only.
- Time-of-day on due dates — date-only.

## Architecture

Single Python package, installable with `pip install -e .`, exposing a `todo` console script.

```
todo-cli/
├── pyproject.toml
├── README.md
├── src/todo_cli/
│   ├── __init__.py
│   ├── __main__.py          # entry point: `python -m todo_cli` or `todo`
│   ├── repl.py              # input loop + prompt_toolkit setup
│   ├── commands.py          # slash command dispatcher + handlers
│   ├── storage.py           # JSON file I/O behind a Storage class
│   ├── models.py            # Todo dataclass + serialization
│   ├── config.py            # ~/.todo/config.json (settings)
│   ├── render.py            # rich-based output (tables, panels, spinners)
│   ├── suggest.py           # fuzzy command suggestions
│   └── errors.py            # typed exceptions
└── tests/
    ├── test_storage.py
    ├── test_models.py
    ├── test_commands.py
    ├── test_suggest.py
    ├── test_render.py
    └── test_repl.py
```

### Module boundaries

- `repl.py` — owns input/output. Hands lines to `commands.py`, renders results via `render.py`. Receives `Storage` and `Config` instances from `__main__` rather than constructing them; reads from them only for prompt state (e.g., open-todo count).
- `commands.py` — orchestrator. Parses slash commands, dispatches handlers, invokes `storage`, returns `CommandResult`.
- `storage.py` — sole owner of the JSON file. Everyone else goes through it.
- `models.py` — `Todo` dataclass + (de)serialization. Pure.
- `config.py` — `Config` dataclass + JSON persistence for user settings.
- `render.py` — pure functions returning `rich` renderables.
- `suggest.py` — pure fuzzy-match function. Stdlib only (`difflib`).
- `errors.py` — typed exception hierarchy.

Each file is small enough to hold in one reader's head; `commands.py` and `storage.py` are the only modules with non-trivial logic.

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

**Concurrency:** Single-process assumption. Two REPLs running concurrently → last-writer-wins. Documented in README, not solved in code.

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

## Error handling

Operational errors keep the REPL alive. Integrity errors exit cleanly.

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

- **`storage.py`** — full coverage. CRUD round-trips; atomic-write behavior (kill-mid-save sim by patching `os.replace`); filtering; schema-version rejection; corrupt-file handling; backup restore. Real filesystem via `tmp_path` fixture.
- **`models.py`** — serialization round-trip table-driven tests.
- **`commands.py`** — handler functions are pure: `(args, storage, config) → CommandResult`. Test each handler with a real in-memory `Storage` (tmp file). Cover happy paths + every error category.
- **`suggest.py`** — pure function; table-driven tests for fuzzy thresholds.
- **`render.py`** — light: assert renderables don't throw on edge inputs (empty list, very long text, unicode). Visual output not asserted.
- **`repl.py`** — minimal: line dispatch (slash vs free-form auto-add), Ctrl+C/D handling. prompt_toolkit interaction stubbed at the session boundary.

**TDD:** Each module gets tests first per superpowers TDD discipline. Implementation plan reflects this.

**Coverage:** ≥90% target on storage/commands/suggest. Lower acceptable elsewhere. Judgment over coverage worship.

## Phase 2 — AI integration (deferred, sketch only)

Trigger: phase 1 is fully implemented and tested.

**Seam:** `commands.py`'s free-form path is a single function. Phase 2 swaps that function's body to call `ai.parse(text) → Action`, mapping returned `Action` to the same internal handlers slash commands already use.

**Likely additions:**
- `ai.py` — Anthropic SDK client, tool definitions matching command set, prompt caching (system + tools cached ephemeral), cost tracking.
- New commands: `/ai on`, `/ai off`, `/cost`.
- Config keys: `ai_on`, `model`.
- Prompt indicator: `todo (12 open) [AI:on] >`.
- Equivalent-command hint: when AI executes an action, also show the slash command form so the user can learn the manual syntax.

**No code or tests for phase 2 belong in phase 1 deliverables.** Phase 2 will go through its own brainstorm → spec → plan cycle.

## Risks & open items

- `prompt_toolkit` and `rich` are large deps for a small tool. Acceptable trade — they deliver the polish requirement, both are stable.
- Auto-add can surprise a user who expects a slash command and forgets the `/`. The suggest layer mitigates the typo case. Accept the residual risk.
- Atomic write + JSON file is fine up to ~10k todos. If user grows past that, switch storage to SQLite behind the same `Storage` interface — contained change.

## Appendix — pyproject summary (sketch)

- Python ≥ 3.11 (for `Literal`, modern dataclasses, `tomllib`).
- Runtime deps: `prompt_toolkit`, `rich`.
- Dev deps: `pytest`, `pytest-cov`.
- Console script: `todo = todo_cli.__main__:main`.
