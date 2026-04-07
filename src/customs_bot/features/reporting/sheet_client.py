"""Google Sheets reporter for batch processing logs."""

from __future__ import annotations

from typing import Any

from customs_bot.shared.models import Receipt


class SheetReporter:
    """Append receipt log rows to a Google Sheet."""

    def __init__(self, service: Any, spreadsheet_id: str, range_a1: str = "Sheet1!A:F") -> None:
        self._service = service
        self._spreadsheet_id = spreadsheet_id
        self._range = range_a1

    def append_receipt(self, receipt: Receipt) -> None:
        row = [
            receipt.fetched_at.isoformat(timespec="seconds"),
            receipt.customs_number,
            receipt.mhd,
            receipt.status.value,
            receipt.saved_path or "",
            receipt.error or "",
        ]
        self._service.spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=self._range,
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        ).execute()
