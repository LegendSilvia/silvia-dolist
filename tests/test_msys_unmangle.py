from __future__ import annotations

from todo_cli.commands import unmangle_msys_args


def test_recovers_known_slash_command():
    args = ["C:/Users/foo/AppData/Local/Programs/Git/list"]
    assert unmangle_msys_args(args) == ["/list"]


def test_recovers_with_subsequent_args():
    args = ["C:/Users/foo/AppData/Local/Programs/Git/add", "buy", "milk"]
    assert unmangle_msys_args(args) == ["/add", "buy", "milk"]


def test_handles_backslash_paths():
    args = [r"C:\Program Files\Git\done"]
    assert unmangle_msys_args(args) == ["/done"]


def test_skips_non_path_args():
    args = ["/list", "--tag", "work"]
    assert unmangle_msys_args(args) == ["/list", "--tag", "work"]


def test_skips_path_with_unknown_basename():
    # Genuine file path the user might pass — leave alone
    args = ["C:/path/to/some/document.txt"]
    assert unmangle_msys_args(args) == args


def test_skips_path_to_known_directory_name_only_one():
    # Directory called "list" deeper in a tree, but not at end → unchanged
    args = ["C:/projects/list/notes.md"]
    assert unmangle_msys_args(args) == args


def test_recovers_show_done_undo_edit_del():
    for cmd in ("show", "done", "undo", "edit", "del", "ask", "config", "help", "clear", "exit", "quit"):
        args = [f"C:/Program Files/Git/{cmd}"]
        assert unmangle_msys_args(args) == [f"/{cmd}"]


def test_empty_args_is_empty():
    assert unmangle_msys_args([]) == []
