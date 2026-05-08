from pathlib import Path
from datetime import date
import io
import pytest

from rich.console import Console

from todo_cli.commands import CommandResult, KNOWN_COMMANDS, run_command
from todo_cli.config import Config
from todo_cli.storage import Storage


def _render(renderable) -> str:
    """Render a Rich renderable to plain string for test assertions."""
    buf = io.StringIO()
    Console(file=buf, force_terminal=False, width=200).print(renderable)
    return buf.getvalue()


@pytest.fixture
def storage(storage_path: Path) -> Storage:
    s = Storage(storage_path)
    s.load()
    return s


@pytest.fixture
def config() -> Config:
    return Config()


def test_known_commands_includes_core(storage: Storage, config: Config):
    for cmd in ["/add", "/list", "/show", "/done", "/undo", "/edit",
                "/del", "/help", "/clear", "/exit", "/quit"]:
        assert cmd in KNOWN_COMMANDS


def test_empty_line_is_noop(storage: Storage, config: Config):
    result = run_command("", storage, config)
    assert result.renderable is None
    assert result.exit is False
    assert result.clear is False


def test_unknown_command_suggests(storage: Storage, config: Config):
    result = run_command("/lst", storage, config)
    assert result.renderable is not None
    rendered = str(result.renderable)
    assert "Unknown command" in rendered
    assert "/list" in rendered


def test_help_returns_renderable(storage: Storage, config: Config):
    result = run_command("/help", storage, config)
    assert result.renderable is not None
    assert "Commands" in _render(result.renderable)


def test_clear_signals_clear(storage: Storage, config: Config):
    result = run_command("/clear", storage, config)
    assert result.clear is True


def test_exit_and_quit_signal_exit(storage: Storage, config: Config):
    assert run_command("/exit", storage, config).exit is True
    assert run_command("/quit", storage, config).exit is True


def test_add_basic(storage: Storage, config: Config):
    result = run_command("/add buy milk", storage, config)
    assert "Added" in _render(result.renderable)
    todos = storage.list()
    assert len(todos) == 1
    assert todos[0].text == "buy milk"


def test_add_with_flags(storage: Storage, config: Config):
    run_command(
        '/add "finish report" --due 2026-06-01 --priority high --tags work,urgent --project q3',
        storage, config,
    )
    todo = storage.list()[0]
    assert todo.text == "finish report"
    assert todo.due == date(2026, 6, 1)
    assert todo.priority == "high"
    assert todo.tags == ["work", "urgent"]
    assert todo.project == "q3"


def test_add_missing_text_errors(storage: Storage, config: Config):
    result = run_command("/add", storage, config)
    rendered = str(result.renderable)
    assert "/add" in rendered or "usage" in rendered.lower()


def test_add_invalid_priority_errors(storage: Storage, config: Config):
    result = run_command("/add foo --priority extreme", storage, config)
    rendered = str(result.renderable)
    assert "priority" in rendered.lower() or "invalid" in rendered.lower()


def test_list_default_shows_open_only(storage: Storage, config: Config):
    run_command("/add a", storage, config)
    run_command("/add b", storage, config)
    a = storage.list()[0]
    storage.update(a.id, done=True)
    result = run_command("/list", storage, config)
    rendered = _render(result.renderable)
    # default = open only; "a" is done, "b" is open
    assert "b" in rendered
    assert "1 open" in rendered


def test_list_all(storage: Storage, config: Config):
    run_command("/add a", storage, config)
    run_command("/add b", storage, config)
    storage.update(storage.list()[0].id, done=True)
    result = run_command("/list --all", storage, config)
    assert "2 total" in _render(result.renderable)


def test_list_done_only(storage: Storage, config: Config):
    run_command("/add a", storage, config)
    storage.update(storage.list()[0].id, done=True)
    result = run_command("/list --done", storage, config)
    assert "1 done" in _render(result.renderable)


def test_list_filter_tag(storage: Storage, config: Config):
    run_command("/add work-task --tags work", storage, config)
    run_command("/add home-task --tags home", storage, config)
    result = run_command("/list --tag work", storage, config)
    rendered = _render(result.renderable)
    assert "work-task" in rendered
    assert "home-task" not in rendered


def test_show_existing(storage: Storage, config: Config):
    run_command("/add hello", storage, config)
    result = run_command("/show 1", storage, config)
    assert "hello" in _render(result.renderable)


def test_show_missing_returns_error(storage: Storage, config: Config):
    result = run_command("/show 999", storage, config)
    assert "999" in str(result.renderable)


def test_show_non_int_id_errors(storage: Storage, config: Config):
    result = run_command("/show abc", storage, config)
    rendered = str(result.renderable).lower()
    assert "id" in rendered or "integer" in rendered


def test_done_marks_completed(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/done 1", storage, config)
    assert storage.get(1).done is True


def test_undo_clears_completed(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/done 1", storage, config)
    run_command("/undo 1", storage, config)
    assert storage.get(1).done is False


def test_done_missing_id_returns_error(storage: Storage, config: Config):
    result = run_command("/done 999", storage, config)
    assert "999" in str(result.renderable)


def test_edit_text(storage: Storage, config: Config):
    run_command("/add original", storage, config)
    run_command("/edit 1 text new text", storage, config)
    assert storage.get(1).text == "new text"


def test_edit_due(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/edit 1 due 2026-12-31", storage, config)
    assert storage.get(1).due == date(2026, 12, 31)


def test_edit_priority_valid(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/edit 1 priority high", storage, config)
    assert storage.get(1).priority == "high"


def test_edit_priority_invalid_errors(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    result = run_command("/edit 1 priority extreme", storage, config)
    assert "priority" in str(result.renderable).lower()


def test_edit_tags(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/edit 1 tags work,urgent", storage, config)
    assert storage.get(1).tags == ["work", "urgent"]


def test_edit_unknown_field_errors(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    result = run_command("/edit 1 banana yes", storage, config)
    rendered = str(result.renderable).lower()
    assert "field" in rendered or "banana" in rendered


def test_del_removes(storage: Storage, config: Config):
    run_command("/add x", storage, config)
    run_command("/del 1", storage, config)
    assert storage.list(done=None) == []


def test_del_missing_returns_error(storage: Storage, config: Config):
    result = run_command("/del 999", storage, config)
    assert "999" in str(result.renderable)


def test_free_form_auto_adds(storage: Storage, config: Config):
    result = run_command("buy milk", storage, config)
    assert "Added" in _render(result.renderable)
    todos = storage.list()
    assert todos[0].text == "buy milk"


def test_free_form_typo_suggests_command(storage: Storage, config: Config):
    result = run_command("lst", storage, config)
    rendered = str(result.renderable)
    assert "/list" in rendered
    # No todo should have been added
    assert storage.list(done=None) == []


def test_free_form_with_dashes_does_not_break_argparse(storage: Storage, config: Config):
    result = run_command("buy --milk and bread", storage, config)
    assert "Added" in _render(result.renderable)
    todo = storage.list()[0]
    assert todo.text == "buy --milk and bread"


def test_free_form_extracts_nl_date(storage: Storage, config: Config):
    run_command("finish report by friday", storage, config)
    todo = storage.list()[0]
    assert todo.text == "finish report"
    assert todo.due is not None


def test_free_form_extracts_tags_and_project(storage: Storage, config: Config):
    run_command("review pr #code @backend", storage, config)
    todo = storage.list()[0]
    assert todo.text == "review pr"
    assert todo.tags == ["code"]
    assert todo.project == "backend"


def test_free_form_extracts_priority(storage: Storage, config: Config):
    run_command("hotfix urgent", storage, config)
    todo = storage.list()[0]
    assert todo.priority == "high"


def test_add_nl_extraction_when_no_flags(storage: Storage, config: Config):
    run_command("/add ship release tomorrow #release @platform p1", storage, config)
    todo = storage.list()[0]
    assert todo.text == "ship release"
    assert todo.due is not None
    assert todo.tags == ["release"]
    assert todo.project == "platform"
    assert todo.priority == "high"


def test_add_explicit_flag_overrides_nl_date(storage: Storage, config: Config):
    run_command(
        "/add ship release tomorrow --due 2030-01-01",
        storage, config,
    )
    todo = storage.list()[0]
    assert todo.due == date(2030, 1, 1)


def test_add_explicit_flag_overrides_nl_priority(storage: Storage, config: Config):
    run_command("/add hotfix urgent --priority low", storage, config)
    todo = storage.list()[0]
    assert todo.priority == "low"


def test_add_explicit_tags_override_nl_tags(storage: Storage, config: Config):
    run_command("/add task #parsed --tags explicit", storage, config)
    todo = storage.list()[0]
    assert todo.tags == ["explicit"]


def test_added_summary_shows_extracted_fields(storage: Storage, config: Config):
    result = run_command("review pr #code @backend tomorrow", storage, config)
    rendered = _render(result.renderable)
    assert "code" in rendered
    assert "backend" in rendered


def test_render_list_marks_selected_row(storage: Storage, config: Config):
    from todo_cli.render import render_todo_list
    run_command("/add first", storage, config)
    run_command("/add second", storage, config)
    todos = storage.list()
    sel_id = todos[0].id
    rendered = _render(render_todo_list(todos, selected_id=sel_id))
    # cursor glyph appears next to the selected row
    assert "›" in rendered


def test_edit_description(storage: Storage, config: Config):
    run_command("/add deploy service", storage, config)
    run_command("/edit 1 description needs-canary-then-full-rollout", storage, config)
    assert storage.get(1).description == "needs-canary-then-full-rollout"


def test_show_includes_description(storage: Storage, config: Config):
    run_command("/add deploy service", storage, config)
    run_command("/edit 1 description rollback plan ready", storage, config)
    result = run_command("/show 1", storage, config)
    assert "rollback plan ready" in _render(result.renderable)


def test_list_marks_todos_with_description(storage: Storage, config: Config):
    run_command("/add task one", storage, config)
    run_command("/add task two", storage, config)
    run_command("/edit 1 description some notes here", storage, config)
    result = run_command("/list", storage, config)
    rendered = _render(result.renderable)
    # Indicator glyph appears for the one with a description
    assert "ⓘ" in rendered
