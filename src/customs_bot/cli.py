"""Real CLI entry point — wires features into the actual pipeline."""

from __future__ import annotations

import argparse
import contextlib
import os
from pathlib import Path

from loguru import logger

from customs_bot.config import Settings
from customs_bot.features.auth import AccountPool, NoAccountsAvailable
from customs_bot.features.auth.selenium_login import SeleniumLoginError, login
from customs_bot.features.auth.session import CookieStore
from customs_bot.features.pdf_parsing import parse_invoice
from customs_bot.features.receipt_fetch.downloader import SeleniumPdfDownloader
from customs_bot.features.receipt_fetch.pipeline import PipelineDeps, process_invoice
from customs_bot.features.receipt_fetch.scraper import find_mhd
from customs_bot.features.reporting.sheet_client import SheetReporter
from customs_bot.features.storage import save_pdf
from customs_bot.logging import setup_logging
from customs_bot.shared.models import BatchResult, ReceiptStatus


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="customs-bot",
        description="Tai bien lai dien tu tu thuphi.haiphong.gov.vn",
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Thu muc chua PDF to khai (default tu env CUSTOMS_BOT_DATA_DIR)",
    )
    p.add_argument(
        "--files",
        nargs="*",
        type=Path,
        default=None,
        help="Chi xu ly cac file cu the thay vi ca thu muc",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Giam log output",
    )
    return p


def _maybe_build_reporter(settings: Settings) -> SheetReporter | None:
    """Build SheetReporter if credentials + spreadsheet ID are available."""
    spreadsheet_id = os.environ.get("CUSTOMS_BOT_SPREADSHEET_ID", "")
    if not spreadsheet_id:
        logger.info("CUSTOMS_BOT_SPREADSHEET_ID chưa set — bỏ qua Sheet logging")
        return None
    if not settings.service_account_file.exists():
        logger.warning("Service account file không tồn tại — bỏ qua Sheet logging")
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            str(settings.service_account_file),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return SheetReporter(service=service, spreadsheet_id=spreadsheet_id)
    except Exception as exc:
        logger.warning("Không khởi tạo được SheetReporter: {}", exc)
        return None


def _list_pdfs(data_dir: Path, files: list[Path] | None) -> list[Path]:
    if files:
        return [data_dir / f if not f.is_absolute() else f for f in files]
    return sorted(data_dir.glob("*.pdf"))


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    settings = Settings()
    if args.data_dir:
        settings = settings.model_copy(update={"data_dir": args.data_dir})

    setup_logging(level="WARNING" if args.quiet else settings.log_level)
    logger.info("customs-bot v5 starting (data_dir={})", settings.data_dir)

    if not settings.data_dir.exists():
        logger.error("Thu muc data khong ton tai: {}", settings.data_dir)
        return 2

    pdfs = _list_pdfs(settings.data_dir, args.files)
    if not pdfs:
        logger.warning("Khong co PDF nao de xu ly trong {}", settings.data_dir)
        return 0
    logger.info("Tim thay {} PDF", len(pdfs))

    # Load accounts
    try:
        pool = AccountPool.load(settings.accounts_file)
    except (FileNotFoundError, NoAccountsAvailable) as exc:
        logger.error("Khong load duoc accounts: {}", exc)
        return 2

    # Cookie store: persist cookies for potential future httpx-based flow.
    # TODO Phase 2a: dùng cookies trực tiếp với httpx thay vì Selenium.
    cookie_store = CookieStore(settings.cookie_store)
    if not cookie_store.is_expired():
        logger.info(
            "Cookies khả dụng tại {} — TODO Phase 2a: dùng httpx thay Selenium",
            cookie_store.path,
        )

    # Login (Selenium, captcha tay)
    try:
        session = login(pool.current())
    except SeleniumLoginError as exc:
        logger.error("Login fail: {}", exc)
        cookie_store.clear()
        return 3

    # Persist cookies for future runs
    try:
        cookie_store.save(session.cookies)
        logger.info("Saved {} cookies to {}", len(session.cookies), cookie_store.path)
    except Exception as exc:
        logger.warning("Không save được cookies: {}", exc)

    reporter = _maybe_build_reporter(settings)

    deps = PipelineDeps(
        scraper_fn=find_mhd,
        downloader=SeleniumPdfDownloader(session.driver),
        storage_fn=save_pdf,
    )

    receipts = []
    try:
        for pdf in pdfs:
            try:
                invoice = parse_invoice(pdf)
            except Exception as exc:
                logger.error("Parse fail {}: {}", pdf, exc)
                continue
            receipt = process_invoice(invoice, session.driver, settings.data_dir, deps)
            receipts.append(receipt)
            if reporter is not None:
                try:
                    reporter.append_receipt(receipt)
                except Exception as exc:
                    logger.warning("Không ghi log Sheet cho {}: {}", pdf, exc)
    finally:
        with contextlib.suppress(Exception):
            session.driver.quit()

    total = len(pdfs)
    succeeded = sum(1 for r in receipts if r.status is ReceiptStatus.SUCCESS)
    failed = sum(1 for r in receipts if r.status is ReceiptStatus.FAILED)
    skipped = total - len(receipts)

    summary = BatchResult(total=total, succeeded=succeeded, failed=failed, skipped=skipped)
    logger.info(
        "Done: total={} succeeded={} failed={} skipped={}",
        summary.total, summary.succeeded, summary.failed, summary.skipped,
    )
    return 0 if summary.failed == 0 else 1
