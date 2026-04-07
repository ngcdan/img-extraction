"""Parse tờ khai PDFs using pymupdf (fitz) for text + table extraction.

Phase 3 rewrite: replaces pdfminer-based legacy parser.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import fitz

from customs_bot.shared.models import Invoice, LineItem


def _extract_text_with_spaces(page: fitz.Page) -> str:
    """Extract text using character bounding-box positions to recover missing spaces.

    pymupdf sometimes drops inter-word spaces when the preceding character
    carries Vietnamese diacritical marks.  By inspecting the horizontal gap
    between consecutive character bboxes we can re-insert those spaces.
    """
    rawdict = page.get_text("rawdict")
    lines_text: list[str] = []

    for block in rawdict["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            chars: list[dict] = []
            for span in line["spans"]:
                if "chars" in span:
                    chars.extend(span["chars"])

            if not chars:
                continue

            widths = [c["bbox"][2] - c["bbox"][0] for c in chars if c["c"].strip()]
            avg_width = sum(widths) / len(widths) if widths else 5.0
            space_threshold = avg_width * 0.3

            text_parts = [chars[0]["c"]]
            for i in range(1, len(chars)):
                gap = chars[i]["bbox"][0] - chars[i - 1]["bbox"][2]
                if (
                    gap > space_threshold
                    and chars[i]["c"] != " "
                    and chars[i - 1]["c"] != " "
                ):
                    text_parts.append(" ")
                text_parts.append(chars[i]["c"])

            lines_text.append("".join(text_parts).strip())

    return "\n".join(lines_text)


def _parse_int(s: str) -> int:
    """Parse Vietnamese number format: dots as thousands separator."""
    return int(s.replace(".", "").replace(",", "").strip()) if s.strip() else 0


def _parse_float(s: str) -> float:
    """Parse quantity: may use comma as decimal separator."""
    s = s.strip()
    if not s:
        return 0.0
    # Vietnamese format: 2,432 means 2.432
    return float(s.replace(".", "").replace(",", "."))


def _extract_header(text: str) -> dict:
    """Extract header fields from full page text using line-by-line matching."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    result: dict = {
        "so_ct": None,
        "date": None,
        "tax_number": None,
        "customs_number": None,
        "partner_invoice_name": None,
    }

    for i, line in enumerate(lines):
        if (
            (line.startswith("Mẫu số:") or line.startswith("Mau so:"))
            and i + 1 < len(lines)
            and lines[i + 1].startswith("Số:")
        ):
            so_ct = lines[i + 1].replace("Số:", "").strip()
            if so_ct.isdigit() and len(so_ct) >= 4:
                result["so_ct"] = so_ct

    for i, line in enumerate(lines):
        if line == "Kính gửi:":
            if i + 1 < len(lines):
                result["partner_invoice_name"] = lines[i + 1].strip()
            break

    for i, line in enumerate(lines):
        if "Mã số thuế:" in line:
            for j in range(i + 1, min(i + 4, len(lines))):
                potential = lines[j].strip()
                if potential.isdigit():
                    result["tax_number"] = potential
                    break
            break

    customs_variants = [
        "Số tờ khai Hải quan",
        "Số tờ khai hải quan",
        "Số tờ khai HQ",
        "Số tờ khai",
        "Tờ khai HQ số",
        "Tờ khai số",
        "STK HQ",
        "Số TK HQ",
        "Số TK:",
        "TK HQ số",
    ]
    for i, line in enumerate(lines):
        if any(v in line for v in customs_variants):
            for j in range(i + 1, min(i + 6, len(lines))):
                potential = lines[j].strip()
                if potential.isdigit() and len(potential) == 12:
                    result["customs_number"] = potential
                    # Date may be several lines after customs_number
                    # (two-column layout interleaves lines)
                    for k in range(j + 1, min(j + 8, len(lines))):
                        d = lines[k].strip()
                        if len(d) == 10 and d[2] == "/" and d[5] == "/":
                            result["date"] = d
                            break
                    break
            if result["customs_number"]:
                break

    return result


def _extract_line_items(page: fitz.Page) -> list[LineItem]:
    """Extract line items from the first table on the page."""
    tables = page.find_tables()
    if not tables.tables:
        return []

    rows = tables[0].extract()
    # Skip header rows (row 0 = column names, row 1 = column numbers like (1)(2)...)
    items: list[LineItem] = []
    for row in rows[2:]:
        if len(row) < 7:
            continue
        stt = (row[0] or "").strip()
        if not stt or not stt.isdigit():
            continue  # empty padding row

        container_no = (row[2] or "").strip()
        label = (row[1] or "").strip()
        unit = (row[3] or "").strip()
        unit_price_str = (row[4] or "").strip()
        quantity_str = (row[5] or "").strip()
        amount_str = (row[6] or "").strip()

        items.append(
            LineItem(
                container_no=container_no,
                label=label,
                unit=unit,
                unit_price=_parse_int(unit_price_str),
                quantity=_parse_float(quantity_str),
                amount=_parse_int(amount_str),
            )
        )
    return items


def parse_invoice(pdf_path: Path | str) -> Invoice:
    """Parse a tờ khai PDF and return a typed Invoice.

    Raises ValueError if customs_number cannot be extracted.
    """
    path = Path(pdf_path)
    doc = fitz.open(str(path))
    page = doc[0]

    text = _extract_text_with_spaces(page)
    header = _extract_header(text)

    customs_number = (header.get("customs_number") or "").strip()
    if not customs_number:
        doc.close()
        raise ValueError(f"Cannot extract customs_number from {path}")

    date_str = header.get("date") or ""
    try:
        registration_date = datetime.strptime(date_str, "%d/%m/%Y").date()
    except ValueError as exc:
        doc.close()
        raise ValueError(f"Invalid date {date_str!r} in {path}") from exc

    line_items = _extract_line_items(page)
    doc.close()

    return Invoice(
        customs_number=customs_number,
        registration_date=registration_date,
        company_name=(header.get("partner_invoice_name") or "").strip() or "UNKNOWN",
        tax_code=(header.get("tax_number") or "").strip() or "UNKNOWN",
        source_file=str(path),
        line_items=line_items,
    )
