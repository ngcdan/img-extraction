"""Shared pytest fixtures for customs_bot tests."""

from datetime import date, datetime

import pytest

from customs_bot.shared.models import Account, Invoice, Receipt, ReceiptStatus


@pytest.fixture
def sample_account() -> Account:
    return Account(username="0123456789", password="secret")


@pytest.fixture
def sample_invoice() -> Invoice:
    return Invoice(
        customs_number="12345",
        registration_date=date(2026, 4, 7),
        company_name="ACME Co",
        tax_code="0123456789",
        source_file="data/inv1.pdf",
    )


@pytest.fixture
def sample_receipt() -> Receipt:
    return Receipt(
        mhd="MHD001",
        customs_number="12345",
        status=ReceiptStatus.SUCCESS,
        saved_path="/tmp/MHD001.pdf",
        fetched_at=datetime(2026, 4, 7, 10, 0, 0),
    )
