from pathlib import Path

from customs_bot.config import Settings


def test_settings_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("CUSTOMS_BOT_DATA_DIR", str(tmp_path))
    s = Settings()
    assert s.data_dir == tmp_path
    assert s.log_level == "INFO"


def test_settings_log_level_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CUSTOMS_BOT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CUSTOMS_BOT_LOG_LEVEL", "DEBUG")
    s = Settings()
    assert s.log_level == "DEBUG"


def test_settings_data_dir_must_be_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CUSTOMS_BOT_DATA_DIR", str(tmp_path / "nested"))
    s = Settings()
    assert isinstance(s.data_dir, Path)
