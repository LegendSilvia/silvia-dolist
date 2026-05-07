from __future__ import annotations
import difflib


def suggest(
    token: str,
    commands: list[str],
    n: int = 3,
    cutoff: float = 0.7,
) -> list[str]:
    """Return up to n close matches for token from commands.

    Token may include a leading '/' or not — matching is consistent.
    Returned strings preserve the form (with slash) found in the commands list.
    """
    needle = token.lstrip("/")
    pool = [c.lstrip("/") for c in commands]
    by_pool = {p: c for p, c in zip(pool, commands)}
    matches = difflib.get_close_matches(needle, pool, n=n, cutoff=cutoff)
    return [by_pool[m] for m in matches]
