"""Loguru configuration for customs_bot."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def setup_logging(level: str = "INFO", log_file: Path | None = None):
    """Configure loguru sinks. Returns the loguru logger."""
    logger.remove()
    logger.add(lambda msg: print(msg, end=""), level=level, format=_FORMAT, colorize=True)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level=level, format=_FORMAT, rotation="10 MB", retention=5)
    return logger
