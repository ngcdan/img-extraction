from datetime import date
from pathlib import Path

import pytest

from customs_bot.features.pdf_parsing.parser import parse_invoice
from customs_bot.shared.models import Invoice

# test_parser.py: parents[0]=tests, [1]=pdf_parsing, [2]=features,
# [3]=customs_bot, [4]=src, [5]=repo_root
FIXTURES = Path(__file__).resolve().parents[5] / "tests" / "fixtures" / "samples"


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
