"""Path helpers shared across features."""

from datetime import date
from pathlib import Path


def date_folder_name(d: date) -> str:
    """Format a date as `dd-mm-yyyy` (theo convention dự án)."""
    return d.strftime("%d-%m-%Y")


def ensure_date_folder(parent: Path, d: date) -> Path:
    """Tạo (nếu chưa có) và trả về thư mục `<parent>/<dd-mm-yyyy>/`."""
    folder = parent / date_folder_name(d)
    folder.mkdir(parents=True, exist_ok=True)
    return folder
