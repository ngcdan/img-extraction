"""Scrape mhd (drive_link) for a customs_number from gov site list table.

Adapted from legacy receipt_fetcher.py:200-264. Wraps Selenium driver, returns
typed result. Future: replace with httpx + VIEWSTATE form POST when spike confirms
direct PDF endpoint.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from selenium.webdriver.common.by import By


class ScrapeError(Exception):
    """Raised when mhd cannot be scraped from the list table."""


def find_mhd(driver: Any, customs_number: str) -> str:
    """Trả về mhd cho customs_number. Raises ScrapeError nếu không tìm thấy."""
    try:
        table = driver.find_element(By.ID, "TBLDANHSACH")
    except Exception as exc:
        raise ScrapeError(f"Không tìm thấy bảng TBLDANHSACH: {exc}") from exc

    rows = table.find_elements(By.TAG_NAME, "tr")
    if len(rows) <= 1 or "No data available" in rows[1].text:
        raise ScrapeError(f"Bảng trống cho customs_number {customs_number}")

    first_row = rows[1]
    cells = first_row.find_elements(By.TAG_NAME, "td")
    if len(cells) < 5:
        raise ScrapeError(f"Row format không đúng (chỉ có {len(cells)} cells)")

    found_customs = str(cells[4].text).strip()
    if found_customs != str(customs_number):
        raise ScrapeError(
            f"Customs mismatch: tìm thấy {found_customs!r}, cần {customs_number!r}"
        )

    link_cell = cells[1]
    link = link_cell.find_element(By.TAG_NAME, "a")
    href = link.get_attribute("href") or ""
    if "mhd=" not in href:
        raise ScrapeError(f"Link không có mhd: {href!r}")

    mhd = href.split("mhd=")[-1]
    logger.debug("Scraped mhd={} for customs_number={}", mhd, customs_number)
    return mhd
