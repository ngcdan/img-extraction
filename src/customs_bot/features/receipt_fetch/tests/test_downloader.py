import base64
from unittest.mock import MagicMock, patch

import pytest

from customs_bot.features.receipt_fetch.downloader import (
    DownloadError,
    SeleniumPdfDownloader,
)


def _fake_driver_returning(pdf_bytes: bytes):
    driver = MagicMock()
    driver.current_window_handle = "main"
    driver.window_handles = ["main", "new"]

    def execute_script(script, *args):
        return None

    driver.execute_script.side_effect = execute_script
    driver.execute_cdp_cmd.return_value = {
        "data": base64.b64encode(pdf_bytes).decode()
    }
    return driver


@patch("customs_bot.features.receipt_fetch.downloader.time.sleep", return_value=None)
@patch(
    "customs_bot.features.receipt_fetch.downloader._wait_page_loaded",
    return_value=True,
)
def test_download_returns_pdf_bytes(mock_wait, mock_sleep):
    pdf = b"%PDF-1.4 fake content " + b"x" * 2000
    driver = _fake_driver_returning(pdf)
    downloader = SeleniumPdfDownloader(driver)
    result = downloader.download("MHD123")
    assert result == pdf
    driver.execute_cdp_cmd.assert_called_once()


@patch("customs_bot.features.receipt_fetch.downloader.time.sleep", return_value=None)
@patch(
    "customs_bot.features.receipt_fetch.downloader._wait_page_loaded",
    return_value=True,
)
def test_download_raises_when_pdf_too_small(mock_wait, mock_sleep):
    pdf = b"tiny"
    driver = _fake_driver_returning(pdf)
    downloader = SeleniumPdfDownloader(driver)
    with pytest.raises(DownloadError):
        downloader.download("MHD123")


@patch("customs_bot.features.receipt_fetch.downloader.time.sleep", return_value=None)
@patch(
    "customs_bot.features.receipt_fetch.downloader._wait_page_loaded",
    return_value=False,
)
def test_download_raises_on_page_load_timeout(mock_wait, mock_sleep):
    driver = _fake_driver_returning(b"x" * 2000)
    downloader = SeleniumPdfDownloader(driver)
    with pytest.raises(DownloadError):
        downloader.download("MHD123")
