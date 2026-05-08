"""Visual symbols and styles, following the clack prompt idiom.

Constants mirror @clack/prompts so the REPL feels like a clack flow even
though it isn't a wizard. ASCII fallbacks kick in when stdout can't
encode the unicode chars (legacy Windows console with non-utf8
codepage).
"""
from __future__ import annotations
import sys


def _unicode_supported() -> bool:
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in enc


def _u(unicode_char: str, ascii_fallback: str) -> str:
    return unicode_char if _unicode_supported() else ascii_fallback


# Step markers (clack's S_STEP_*)
ACTIVE = _u("◆", "*")
SUBMIT = _u("◇", "o")
CANCEL = _u("■", "x")
WARN_S = _u("▲", "!")

# Bars
BAR = _u("│", "|")
BAR_START = _u("┌", ".")
BAR_END = _u("└", "'")

# State icons (clack's S_INFO/SUCCESS/WARN/ERROR)
INFO = _u("●", "*")
SUCCESS = _u("◆", "*")
WARN = _u("▲", "!")
ERROR = _u("■", "x")

# Selection markers
RADIO_ON = _u("●", ">")
RADIO_OFF = _u("○", " ")

# Inline separator
DOT = _u("·", "-")

# Rich style tokens (used as Rich style strings)
S_ACTIVE = "bold cyan"
S_SUBMIT = "bold green"
S_ERROR = "bold red"
S_WARN = "bold yellow"
S_GUTTER = "dim cyan"
S_DIM = "dim"
S_ID = "cyan"
S_PRIORITY_HIGH = "bold red"
S_PRIORITY_MED = "yellow"
S_PRIORITY_LOW = "dim"
