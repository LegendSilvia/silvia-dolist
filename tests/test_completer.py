from __future__ import annotations

from prompt_toolkit.document import Document

from todo_cli.tui import _SlashCompleter


def _completions(text: str) -> list[str]:
    completer = _SlashCompleter()
    doc = Document(text=text, cursor_position=len(text))
    return [c.text for c in completer.get_completions(doc, None)]


def test_slash_alone_offers_all_commands():
    out = _completions("/")
    assert "/add" in out
    assert "/list" in out
    assert "/mcp" in out


def test_partial_prefix_filters():
    out = _completions("/d")
    assert "/done" in out
    assert "/del" in out
    assert "/list" not in out


def test_full_command_still_offered():
    out = _completions("/list")
    assert out == ["/list"]


def test_no_completions_for_free_form():
    assert _completions("buy milk") == []


def test_no_completions_after_first_token():
    # /add followed by space — we're past the command name
    assert _completions("/add ") == []


def test_no_completions_for_empty():
    assert _completions("") == []


def test_completion_has_meta_description():
    completer = _SlashCompleter()
    doc = Document(text="/m", cursor_position=2)
    completions = list(completer.get_completions(doc, None))
    mcp_completion = next((c for c in completions if c.text == "/mcp"), None)
    assert mcp_completion is not None
    assert mcp_completion.display_meta_text  # has description