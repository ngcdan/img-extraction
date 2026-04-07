"""PDF download via Chrome DevTools Page.printToPDF.

Adapted from legacy receipt_fetcher.py:385-470. Wraps Selenium driver behind
PdfDownloader Protocol so we can swap to httpx-based impl when spike confirms
direct PDF endpoint exists.
"""

from __future__ import annotations

import base64
import time
from typing import Any, Protocol

from loguru import logger

VIEWER_URL = "http://thuphi.haiphong.gov.vn:8224/Viewer/HoaDonViewer.aspx?mhd={mhd}"
MIN_PDF_BYTES = 1000
PAGE_LOAD_TIMEOUT_SEC = 60.0
POLL_INTERVAL_SEC = 0.1


class DownloadError(Exception):
    """Raised when receipt PDF cannot be downloaded."""


class PdfDownloader(Protocol):
    def download(self, mhd: str) -> bytes: ...


def _wait_page_loaded(driver: Any, timeout: float) -> bool:
    """Poll document.readyState until 'complete' or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            state = driver.execute_script("return document.readyState")
            if state == "complete":
                return True
        except Exception:
            pass
        time.sleep(POLL_INTERVAL_SEC)
    return False


class SeleniumPdfDownloader:
    """Default impl: open viewer page in new tab, Page.printToPDF CDP, return bytes."""

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def download(self, mhd: str) -> bytes:
        url = VIEWER_URL.format(mhd=mhd)
        logger.debug("Opening viewer: {}", url)

        original = self._driver.current_window_handle
        self._driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(0.5)

        new_handles = [h for h in self._driver.window_handles if h != original]
        if not new_handles:
            raise DownloadError("Tab mới không mở được")
        new_handle = new_handles[-1]
        self._driver.switch_to.window(new_handle)

        try:
            if not _wait_page_loaded(self._driver, PAGE_LOAD_TIMEOUT_SEC):
                raise DownloadError(f"Timeout load viewer cho mhd={mhd}")

            time.sleep(0.5)

            print_options = {
                "landscape": False,
                "displayHeaderFooter": False,
                "printBackground": True,
                "preferCSSPageSize": True,
                "scale": 1.0,
            }
            result = self._driver.execute_cdp_cmd("Page.printToPDF", print_options)
            pdf_bytes = base64.b64decode(result["data"])

            if len(pdf_bytes) < MIN_PDF_BYTES:
                raise DownloadError(
                    f"PDF quá nhỏ ({len(pdf_bytes)} bytes) cho mhd={mhd}"
                )

            logger.info("Downloaded PDF {} bytes for mhd={}", len(pdf_bytes), mhd)
            return pdf_bytes
        finally:
            try:
                self._driver.close()
                self._driver.switch_to.window(original)
            except Exception as exc:
                logger.warning("Không cleanup được tab: {}", exc)
