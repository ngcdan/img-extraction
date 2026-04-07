"""Cookie persistence for cross-run session reuse."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from loguru import logger


class CookieStore:
    """Lưu/tải cookies dạng JSON. Detect expiry theo file mtime."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def save(self, cookies: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")

    def load(self) -> list[dict[str, Any]] | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                logger.warning("Cookie store {} chứa data không phải list", self._path)
                return None
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Không đọc được cookie store {}: {}", self._path, exc)
            return None

    def is_expired(self, max_age_hours: float = 8.0) -> bool:
        if not self._path.exists():
            return True
        age_seconds = time.time() - self._path.stat().st_mtime
        return age_seconds > (max_age_hours * 3600)

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
