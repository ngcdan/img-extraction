from loguru import logger

from customs_bot.logging import setup_logging


def test_setup_logging_returns_logger():
    log = setup_logging(level="INFO")
    assert log is logger


def test_setup_logging_accepts_level(tmp_path):
    log_file = tmp_path / "test.log"
    setup_logging(level="DEBUG", log_file=log_file)
    logger.debug("hello")
    assert log_file.exists()
    assert "hello" in log_file.read_text()
