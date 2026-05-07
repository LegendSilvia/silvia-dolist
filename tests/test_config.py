import json
from pathlib import Path

from todo_cli.config import Config


def test_load_returns_default_when_file_missing(tmp_path: Path):
    cfg = Config.load(tmp_path / "config.json")
    assert isinstance(cfg, Config)


def test_save_creates_file(tmp_path: Path):
    cfg = Config()
    p = tmp_path / "config.json"
    cfg.save(p)
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


def test_load_after_save_round_trips(tmp_path: Path):
    p = tmp_path / "config.json"
    Config().save(p)
    cfg2 = Config.load(p)
    assert cfg2 == Config()
