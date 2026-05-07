from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

Priority = Literal["low", "med", "high"]


@dataclass
class Todo:
    id: int
    text: str
    created_at: datetime
    done: bool = False
    due: date | None = None
    priority: Priority | None = None
    tags: list[str] = field(default_factory=list)
    project: str | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "done": self.done,
            "due": self.due.isoformat() if self.due else None,
            "priority": self.priority,
            "tags": list(self.tags),
            "project": self.project,
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Todo":
        return cls(
            id=data["id"],
            text=data["text"],
            done=data.get("done", False),
            due=date.fromisoformat(data["due"]) if data.get("due") else None,
            priority=data.get("priority"),
            tags=list(data.get("tags", [])),
            project=data.get("project"),
            created_at=datetime.fromisoformat(data["created_at"]),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
        )
