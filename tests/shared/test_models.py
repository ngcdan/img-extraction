from datetime import date, datetime

import pytest
from pydantic import ValidationError

from customs_bot.shared.models import (
    Account,
    BatchResult,
    Invoice,
    Receipt,
    ReceiptStatus,
)


def test_account_valid():
    acc = Account(username="0123456789", password="secret")
    assert acc.username == "0123456789"


def test_account_rejects_empty_username():
    with pytest.raises(ValidationError):
        Account(username="", password="secret")


def test_invoice_minimal():
    inv = Invoice(
        customs_number="12345",
        registration_date=date(2026, 4, 7),
        company_name="ACME Co",
        tax_code="0123456789",
        source_file="data/inv1.pdf",
    )
    assert inv.customs_number == "12345"


def test_receipt_status_enum():
    assert ReceiptStatus.SUCCESS.value == "success"
    assert ReceiptStatus.FAILED.value == "failed"
    assert ReceiptStatus.SKIPPED.value == "skipped"


def test_receipt_with_status():
    r = Receipt(
        mhd="MHD001",
        customs_number="12345",
        status=ReceiptStatus.SUCCESS,
        saved_path="/tmp/MHD001.pdf",
        fetched_at=datetime(2026, 4, 7, 10, 0, 0),
    )
    assert r.status is ReceiptStatus.SUCCESS


def test_batch_result_aggregates():
    br = BatchResult(total=10, succeeded=7, failed=2, skipped=1)
    assert br.total == 10
    assert br.succeeded + br.failed + br.skipped == br.total


def test_batch_result_invariant_violation():
    with pytest.raises(ValidationError):
        BatchResult(total=10, succeeded=5, failed=2, skipped=1)


def test_receipt_search_result_valid():
    from customs_bot.shared.models import ReceiptSearchResult
    r = ReceiptSearchResult(
        customs_number="307767153100",
        mhd="abc123",
        trans_id="T1",
        hawb=None,
        partner_name="ACME",
        raw={"foo": "bar"},
    )
    assert r.mhd == "abc123"
    assert r.raw["foo"] == "bar"


def test_receipt_search_result_rejects_empty_mhd():
    from customs_bot.shared.models import ReceiptSearchResult
    with pytest.raises(ValidationError):
        ReceiptSearchResult(
            customs_number="x", mhd="", trans_id=None, hawb=None, partner_name=None, raw={}
        )
