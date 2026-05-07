from todo_cli.suggest import suggest

COMMANDS = [
    "/add", "/list", "/show", "/done", "/undo", "/edit", "/del",
    "/help", "/clear", "/exit", "/quit",
]


def test_close_match_returns_command():
    assert "/list" in suggest("/lst", COMMANDS)


def test_works_without_slash_prefix():
    assert "/list" in suggest("lst", COMMANDS)


def test_no_match_returns_empty():
    assert suggest("xyzzy", COMMANDS) == []


def test_respects_n_limit():
    out = suggest("/de", COMMANDS, n=1)
    assert len(out) <= 1


def test_low_cutoff_lets_more_through():
    out = suggest("hlp", COMMANDS, cutoff=0.4)
    assert "/help" in out
