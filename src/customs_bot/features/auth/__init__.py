"""Authentication feature — account pool, session, login."""

from customs_bot.features.auth.account_pool import AccountPool, NoAccountsAvailable
from customs_bot.features.auth.selenium_login import (
    SeleniumLoginError,
    SeleniumSession,
    login,
)
from customs_bot.features.auth.session import CookieStore

__all__ = [
    "AccountPool",
    "NoAccountsAvailable",
    "CookieStore",
    "SeleniumSession",
    "SeleniumLoginError",
    "login",
]
