"""Account pool with rotation for login retries."""

from __future__ import annotations

import json
from pathlib import Path

from customs_bot.shared.models import Account


class NoAccountsAvailable(Exception):
    """Raised when no more accounts can be rotated to."""


class AccountPool:
    """Pool tài khoản đăng nhập cổng thuế. Rotate khi 1 tài khoản fail."""

    def __init__(self, accounts: list[Account]) -> None:
        if not accounts:
            raise NoAccountsAvailable("Account pool is empty")
        self._accounts = accounts
        self._index = 0

    @classmethod
    def load(cls, path: Path | str) -> AccountPool:
        path = Path(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        accounts = [Account(**item) for item in raw]
        return cls(accounts)

    def __len__(self) -> int:
        return len(self._accounts)

    def current(self) -> Account:
        return self._accounts[self._index]

    def rotate(self) -> Account:
        """Chuyển sang tài khoản tiếp theo. Raises nếu đã hết."""
        if self._index + 1 >= len(self._accounts):
            raise NoAccountsAvailable(
                f"All {len(self._accounts)} accounts exhausted"
            )
        self._index += 1
        return self.current()
