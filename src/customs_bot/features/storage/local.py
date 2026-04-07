"""Local file storage for downloaded receipt PDFs."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from customs_bot.shared.paths import ensure_date_folder


def save_pdf(
    pdf_bytes: bytes,
    filename: str,
    base_dir: Path | str,
    on_date: date,
) -> Path:
    """Lưu PDF biên lai vào `<base_dir>/<dd-mm-yyyy>/<filename>` và trả về path."""
    folder = ensure_date_folder(Path(base_dir), on_date)
    target = folder / filename
    target.write_bytes(pdf_bytes)
    return target
