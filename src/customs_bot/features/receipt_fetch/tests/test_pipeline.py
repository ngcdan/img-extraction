from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from customs_bot.features.receipt_fetch.downloader import DownloadError
from customs_bot.features.receipt_fetch.pipeline import PipelineDeps, process_invoice
from customs_bot.features.receipt_fetch.scraper import ScrapeError
from customs_bot.shared.models import Invoice, ReceiptStatus


@pytest.fixture
def invoice():
    return Invoice(
        customs_number="307767153100",
        registration_date=date(2026, 4, 7),
        company_name="ACME",
        tax_code="0123456789",
        source_file="data/inv.pdf",
    )


def _make_deps(scrape_returns=None, scrape_raises=None,
               download_returns=None, download_raises=None,
               saved_path=None):
    scraper_fn = MagicMock()
    if scrape_raises:
        scraper_fn.side_effect = scrape_raises
    else:
        scraper_fn.return_value = scrape_returns or "MHD123"

    downloader = MagicMock()
    if download_raises:
        downloader.download.side_effect = download_raises
    else:
        downloader.download.return_value = download_returns or b"%PDF" + b"x" * 2000

    storage_fn = MagicMock(return_value=saved_path or Path("/tmp/MHD123.pdf"))

    return PipelineDeps(
        scraper_fn=scraper_fn,
        downloader=downloader,
        storage_fn=storage_fn,
    )


def test_process_invoice_success(invoice, tmp_path):
    deps = _make_deps(saved_path=tmp_path / "MHD123.pdf")
    driver = MagicMock()
    receipt = process_invoice(invoice, driver, tmp_path, deps)
    assert receipt.status is ReceiptStatus.SUCCESS
    assert receipt.mhd == "MHD123"
    assert receipt.customs_number == invoice.customs_number
    assert receipt.saved_path == str(tmp_path / "MHD123.pdf")
    assert receipt.error is None
    deps.scraper_fn.assert_called_once_with(driver, invoice.customs_number)
    deps.downloader.download.assert_called_once_with("MHD123")
    deps.storage_fn.assert_called_once()


def test_process_invoice_scrape_failure(invoice, tmp_path):
    deps = _make_deps(scrape_raises=ScrapeError("not found"))
    driver = MagicMock()
    receipt = process_invoice(invoice, driver, tmp_path, deps)
    assert receipt.status is ReceiptStatus.FAILED
    assert "not found" in (receipt.error or "")
    deps.downloader.download.assert_not_called()


def test_process_invoice_download_failure(invoice, tmp_path):
    deps = _make_deps(download_raises=DownloadError("pdf too small"))
    driver = MagicMock()
    receipt = process_invoice(invoice, driver, tmp_path, deps)
    assert receipt.status is ReceiptStatus.FAILED
    assert "pdf too small" in (receipt.error or "")
    assert receipt.mhd == "MHD123"
    assert receipt.saved_path is None


def test_process_invoice_storage_called_with_correct_args(invoice, tmp_path):
    deps = _make_deps()
    driver = MagicMock()
    process_invoice(invoice, driver, tmp_path, deps)
    call = deps.storage_fn.call_args
    assert call.kwargs["base_dir"] == tmp_path or call.args[2] == tmp_path
    fname = call.kwargs.get("filename") or call.args[1]
    assert "MHD123" in fname
