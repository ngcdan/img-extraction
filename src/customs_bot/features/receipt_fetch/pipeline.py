"""Orchestration: invoice -> scrape mhd -> download pdf -> save -> Receipt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from customs_bot.features.receipt_fetch.downloader import DownloadError, PdfDownloader
from customs_bot.features.receipt_fetch.scraper import ScrapeError
from customs_bot.shared.models import Invoice, Receipt, ReceiptStatus


@dataclass
class PipelineDeps:
    scraper_fn: Callable[[Any, str], str]
    downloader: PdfDownloader
    storage_fn: Callable[..., Path]


def process_invoice(
    invoice: Invoice,
    driver: Any,
    base_dir: Path,
    deps: PipelineDeps,
) -> Receipt:
    """Xử lý 1 invoice end-to-end. Luôn trả về Receipt (success hoặc failed)."""
    now = datetime.now()
    customs_number = invoice.customs_number

    try:
        mhd = deps.scraper_fn(driver, customs_number)
    except ScrapeError as exc:
        logger.warning("Scrape fail cho {}: {}", customs_number, exc)
        return Receipt(
            mhd="UNKNOWN",
            customs_number=customs_number,
            status=ReceiptStatus.FAILED,
            fetched_at=now,
            error=f"scrape: {exc}",
        )

    try:
        pdf_bytes = deps.downloader.download(mhd)
    except DownloadError as exc:
        logger.warning("Download fail mhd={}: {}", mhd, exc)
        return Receipt(
            mhd=mhd,
            customs_number=customs_number,
            status=ReceiptStatus.FAILED,
            fetched_at=now,
            error=f"download: {exc}",
        )

    filename = f"{mhd}.pdf"
    saved_path = deps.storage_fn(
        pdf_bytes=pdf_bytes,
        filename=filename,
        base_dir=base_dir,
        on_date=invoice.registration_date,
    )

    logger.info("Saved {} → {}", customs_number, saved_path)
    return Receipt(
        mhd=mhd,
        customs_number=customs_number,
        status=ReceiptStatus.SUCCESS,
        saved_path=str(saved_path),
        fetched_at=now,
    )
