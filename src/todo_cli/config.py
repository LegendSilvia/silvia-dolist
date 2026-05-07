from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Config:
    """User settings. Phase 1 has no fields; phase 2 adds ai_on, model."""

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        # Filter to known fields so unknown keys (e.g., from future versions) don't crash
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
