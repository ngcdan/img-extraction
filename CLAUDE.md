# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vietnamese-language CLI tool for downloading e-receipts (bien lai) from `thuphi.haiphong.gov.vn` for customs declarations. Reads PDF declarations, logs into the tax portal via Selenium with account-pool rotation, calls the receipt lookup API, downloads receipt PDFs, saves them locally by date, and logs results to Google Sheets.

v5 architecture: modular feature-based package at `src/customs_bot/` with 64+ tests, replacing the legacy flat-file layout.

## Setup

```bash
python -m venv env && source env/bin/activate
pip install -e ".[dev]"
```

## Common commands

- **Run CLI:** `python -m customs_bot` (process all PDFs in `~/Desktop/customs/`)
- **Run CLI with options:** `python -m customs_bot --data-dir /path --files a.pdf b.pdf --quiet`
- **Run tests:** `pytest -q`
- **Run tests with coverage:** `pytest --cov=customs_bot -q`
- **Lint:** `ruff check src/ tests/`
- **Build binary:** `python build.py` (PyInstaller, outputs `dist/customs-bot`)

## Architecture

Feature-based package at `src/customs_bot/`:

```
src/customs_bot/
  __main__.py          # Entry point: from customs_bot.cli import main
  cli.py               # argparse + pipeline orchestration
  config.py            # Pydantic settings (env vars, .env)
  logging.py           # Loguru configuration
  shared/
    models.py          # Domain models (CustomsDeclaration, ReceiptSearchResult, etc.)
    paths.py           # Path helpers (get_default_customs_dir)
  features/
    auth/              # Account pool, session/cookie store, selenium_login facade
    pdf_parsing/       # Parse PDF declarations via pymupdf (no pdfminer dependency)
    receipt_fetch/     # BeelogisticsApiClient (httpx), MHD scraper, PDF downloader, pipeline
    reporting/         # Google Sheet logging
    storage/           # Local file storage by date
```

Each feature has co-located `tests/` with unit tests.

### Legacy bridge files (still at repo root)

- `chrome_manager.py` -- imported by `features/auth/selenium_login.py` (lazy import). Contains `ChromeManager` class for Chrome remote-debug lifecycle.
- `utils.py` -- imported by `chrome_manager.py`. Provides `get_default_customs_dir()`, `parse_date()`, `format_date()`.
- `receipt_fetcher.py`, `pdf_processor.py` -- legacy entry points, kept for reference. Not imported by the new package.
- `build.py` -- PyInstaller build script, updated for v5.

### Key dependencies

- `httpx` -- async-capable HTTP client (replaces requests)
- `pymupdf` -- PDF text extraction (replaces pdfminer.six)
- `pydantic` / `pydantic-settings` -- config and models
- `loguru` -- structured logging
- `selenium` + `webdriver-manager` -- browser automation
- `google-api-python-client` -- Sheets API

## Notes

- All user-facing strings, prints, and comments are in Vietnamese -- match this style in new code.
- The repo expects a manually managed Chrome debug profile at `~/chrome-debug-profile`.
- Test configuration is in `pyproject.toml` under `[tool.pytest.ini_options]`.
- `accounts.json` and `driver-service-account.json` are sensitive files -- never commit them.
