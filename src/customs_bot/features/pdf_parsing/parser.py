"""Typed wrapper around legacy pdf_invoice_parser.process_pdf.

Phase 1: thin adapter that returns pydantic Invoice.
Phase 3: rewrite internals to use pymupdf.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from customs_bot.shared.models import Invoice

# Legacy module lives at repo root, not on default sys.path when running as installed pkg.
# parser.py: parents[0]=pdf_parsing, [1]=features, [2]=customs_bot, [3]=src, [4]=repo_root
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pdf_invoice_parser import process_pdf  # noqa: E402


def parse_invoice(pdf_path: Path | str) -> Invoice:
    """Parse a tờ khai PDF and return a typed Invoice.

    Raises ValueError if customs_number cannot be extracted.
    """
    path = Path(pdf_path)
    raw = process_pdf(str(path))

    if not raw:
        raise ValueError(f"Cannot parse {path}")

    customs_number = (raw.get("customs_number") or "").strip()
    if not customs_number:
        raise ValueError(f"Cannot extract customs_number from {path}")

    date_str = raw.get("date") or ""
    try:
        registration_date = datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date {date_str!r} in {path}") from exc

    return Invoice(
        customs_number=customs_number,
        registration_date=registration_date,
        company_name=(raw.get("partner_invoice_name") or raw.get("partner_invoke_name") or "").strip() or "UNKNOWN",
        tax_code=(raw.get("tax_number") or "").strip() or "UNKNOWN",
        source_file=str(path),
    )
