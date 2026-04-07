import json
from datetime import date
from pathlib import Path

import pytest

from customs_bot.features.pdf_parsing.parser import parse_invoice
from customs_bot.shared.models import Invoice

# test_parser.py: parents[0]=tests, [1]=pdf_parsing, [2]=features,
# [3]=customs_bot, [4]=src, [5]=repo_root
FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "samples"
BASELINES = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "baselines"


@pytest.mark.parametrize(
    "filename,expected_customs",
    [
        ("Á CHÂU BIHAN007242.pdf", "107525367240"),
        ("ASSA ABLOY BLHPH038448.pdf", "307767153100"),
        ("Autel NL BEHPH006970.pdf", "307773856850"),
    ],
)
def test_parse_invoice_returns_invoice(filename, expected_customs):
    pdf = FIXTURES / filename
    if not pdf.exists():
        pytest.skip(f"fixture missing: {pdf}")
    inv = parse_invoice(pdf)
    assert isinstance(inv, Invoice)
    assert inv.customs_number == expected_customs
    assert inv.tax_code
    assert inv.company_name
    assert isinstance(inv.registration_date, date)
    assert inv.source_file == str(pdf)


def test_all_samples_have_line_items():
    """Phase 3 acceptance: all 3 PDFs must have non-empty line_items."""
    for pdf in sorted(FIXTURES.glob("*.pdf")):
        if not pdf.exists():
            pytest.skip(f"fixture missing: {pdf}")
        inv = parse_invoice(pdf)
        assert len(inv.line_items) > 0, f"{pdf.name} has empty line_items"


def test_header_fields_match_baselines():
    """Header fields must match captured pdfminer baselines exactly."""
    for pdf in sorted(FIXTURES.glob("*.pdf")):
        baseline_path = BASELINES / f"{pdf.stem}.json"
        if not baseline_path.exists():
            pytest.skip(f"baseline missing: {baseline_path}")
        baseline = json.loads(baseline_path.read_text())
        inv = parse_invoice(pdf)
        assert inv.customs_number == baseline["customs_number"], (
            f"{pdf.name} customs_number mismatch"
        )
        assert inv.tax_code == baseline["tax_number"], (
            f"{pdf.name} tax_number mismatch"
        )
        assert inv.company_name == baseline["partner_invoice_name"], (
            f"{pdf.name} company_name mismatch"
        )
        assert inv.registration_date.strftime("%d/%m/%Y") == baseline["date"], (
            f"{pdf.name} date mismatch"
        )


def test_autel_line_item_matches_baseline():
    """Autel baseline had 1 line_item -- verify regression."""
    pdf = FIXTURES / "Autel NL BEHPH006970.pdf"
    if not pdf.exists():
        pytest.skip("fixture missing")
    inv = parse_invoice(pdf)
    assert len(inv.line_items) == 1
    item = inv.line_items[0]
    assert item.container_no == "ZCSU7595256"
    assert item.unit_price == 500000
    assert item.quantity == 1
    assert item.amount == 500000
