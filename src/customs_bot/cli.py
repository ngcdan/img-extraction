"""Real CLI entry point — wires features into the actual pipeline."""

from __future__ import annotations

import argparse
import contextlib
from pathlib import Path

from loguru import logger

from customs_bot.config import Settings
from customs_bot.features.auth import AccountPool, NoAccountsAvailable
from customs_bot.features.auth.selenium_login import SeleniumLoginError, login
from customs_bot.features.pdf_parsing import parse_invoice
from customs_bot.features.receipt_fetch.downloader import SeleniumPdfDownloader
from customs_bot.features.receipt_fetch.pipeline import PipelineDeps, process_invoice
from customs_bot.features.receipt_fetch.scraper import find_mhd
from customs_bot.features.storage import save_pdf
from customs_bot.logging import setup_logging
from customs_bot.shared.models import ReceiptStatus


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

    # Login (Selenium, captcha tay)
    try:
        session = login(pool.current())
    except SeleniumLoginError as exc:
        logger.error("Login fail: {}", exc)
        return 3

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
    finally:
        with contextlib.suppress(Exception):
            session.driver.quit()

    succeeded = sum(1 for r in receipts if r.status is ReceiptStatus.SUCCESS)
    failed = sum(1 for r in receipts if r.status is ReceiptStatus.FAILED)
    skipped = len(pdfs) - len(receipts)
    total = len(pdfs)

    logger.info(
        "Done: total={} succeeded={} failed={} skipped={}",
        total, succeeded, failed, skipped,
    )
    return 0 if failed == 0 else 1
