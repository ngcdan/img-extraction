"""Facade wrapping legacy ChromeManager for login flow.

Manual smoke test only — requires real Chrome + captcha. Run via the real CLI.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from customs_bot.shared.models import Account

# Legacy module is at repo root, not on installed path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class SeleniumLoginError(Exception):
    """Raised when Selenium-based login fails."""


@dataclass
class SeleniumSession:
    driver: Any  # webdriver.Chrome
    account: Account
    cookies: list[dict] = field(default_factory=list)


def login(account: Account, *, headless: bool = False) -> SeleniumSession:
    """Đăng nhập cổng thuế bằng Selenium (captcha tay).

    Returns SeleniumSession on success. Raises SeleniumLoginError on failure.
    Caller responsibility: gọi `session.driver.quit()` khi xong.
    """
    from chrome_manager import ChromeManager  # noqa: E402

    logger.info("Khởi động Chrome cho login (account={})", account.username)
    driver = ChromeManager.initialize_chrome(auto_login=False, headless=headless)
    if driver is None:
        raise SeleniumLoginError("Không khởi động được Chrome")

    logger.info("Submitting login form...")
    ok = ChromeManager.fill_login_info(driver, account.username, account.password)
    if not ok:
        try:
            driver.quit()
        except Exception:
            pass
        raise SeleniumLoginError(f"Login fail cho account {account.username}")

    cookies = driver.get_cookies() or []
    logger.info("Login OK, lấy được {} cookies", len(cookies))
    return SeleniumSession(driver=driver, account=account, cookies=cookies)
