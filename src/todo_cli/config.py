from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


# Fields the user can set via /config. Each entry is
# (field_name, description). Unknown keys are filtered out on load.
SETTABLE_FIELDS: list[tuple[str, str]] = [
    ("agent_terminal_cwd", "working directory for /ask terminal (path or 'none')"),
    ("done_retention_days", "default age for /purge (integer days, or 'none' to require explicit arg)"),
]


@dataclass
class Config:
    """User settings. Forward-compatible: unknown JSON keys are dropped on load."""

    agent_terminal_cwd: Optional[str] = None
    done_retention_days: Optional[int] = None

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def to_pairs(self) -> list[tuple[str, Any]]:
        return [(k, getattr(self, k)) for k, _ in SETTABLE_FIELDS]
