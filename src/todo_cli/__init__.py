"""todo_cli package init.

Reconfigure stdout/stderr to utf-8 with errors='replace' so the clack
unicode glyphs in symbols.py render correctly on Windows shells whose
default codepage isn't utf-8 (e.g. cp874). Done here so it happens
before any submodule import reads sys.stdout.encoding.
"""
from __future__ import annotations
import sys


def _ensure_utf8(stream) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass


_ensure_utf8(sys.stdout)
_ensure_utf8(sys.stderr)
