from datetime import datetime
from unittest.mock import MagicMock

import pytest

from customs_bot.features.reporting.sheet_client import SheetReporter
from customs_bot.shared.models import Receipt, ReceiptStatus


@pytest.fixture
def mock_service():
    return MagicMock()


@pytest.fixture
def receipt():
    return Receipt(
        mhd="MHD001",
        customs_number="307767153100",
        status=ReceiptStatus.SUCCESS,
        saved_path="/tmp/MHD001.pdf",
        fetched_at=datetime(2026, 4, 7, 10, 0, 0),
    )


def test_append_receipt_calls_service(mock_service, receipt):
    reporter = SheetReporter(service=mock_service, spreadsheet_id="SHEET_ID")
    reporter.append_receipt(receipt)
    assert mock_service.spreadsheets.return_value.values.return_value.append.called


def test_append_receipt_passes_row_data(mock_service, receipt):
    reporter = SheetReporter(service=mock_service, spreadsheet_id="SHEET_ID")
    reporter.append_receipt(receipt)
    call = mock_service.spreadsheets.return_value.values.return_value.append.call_args
    body = call.kwargs["body"]
    row = body["values"][0]
    assert "MHD001" in row
    assert "307767153100" in row
    assert "success" in row
