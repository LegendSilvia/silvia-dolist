from pathlib import Path
import pytest


@pytest.fixture
def storage_path(tmp_path: Path) -> Path:
    return tmp_path / "todos.json"
