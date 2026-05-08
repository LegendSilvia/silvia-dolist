from __future__ import annotations

from todo_cli.tui import _autofill_selected_id


def test_done_with_no_id_uses_selected():
    assert _autofill_selected_id("/done", 5) == "/done 5"


def test_done_with_explicit_id_unchanged():
    assert _autofill_selected_id("/done 9", 5) == "/done 9"


def test_del_with_no_id_uses_selected():
    assert _autofill_selected_id("/del", 7) == "/del 7"


def test_show_with_no_id_uses_selected():
    assert _autofill_selected_id("/show", 3) == "/show 3"


def test_undo_with_no_id_uses_selected():
    assert _autofill_selected_id("/undo", 2) == "/undo 2"


def test_edit_field_value_no_id_injects_selected():
    assert _autofill_selected_id("/edit text new label", 8) == "/edit 8 text new label"


def test_edit_explicit_id_unchanged():
    assert _autofill_selected_id("/edit 4 text foo", 8) == "/edit 4 text foo"


def test_no_selection_returns_unchanged():
    assert _autofill_selected_id("/done", None) == "/done"


def test_non_id_command_unchanged():
    assert _autofill_selected_id("/list --tag work", 5) == "/list --tag work"


def test_add_unchanged():
    assert _autofill_selected_id("/add buy milk", 5) == "/add buy milk"


def test_free_form_unchanged():
    assert _autofill_selected_id("buy milk tomorrow", 5) == "buy milk tomorrow"


def test_empty_line_unchanged():
    assert _autofill_selected_id("", 5) == ""


def test_bare_edit_uses_selected():
    assert _autofill_selected_id("/edit", 5) == "/edit 5"
