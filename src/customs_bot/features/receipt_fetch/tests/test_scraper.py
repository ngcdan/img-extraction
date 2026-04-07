from unittest.mock import MagicMock

import pytest

from customs_bot.features.receipt_fetch.scraper import ScrapeError, find_mhd


def _make_driver_with_table(rows_data):
    """rows_data = list of cell-text-lists; first list is header (ignored)."""
    driver = MagicMock()
    table = MagicMock()

    rows = []
    for cells_text in rows_data:
        row = MagicMock()
        row.text = " ".join(cells_text)
        cells = []
        for txt in cells_text:
            cell = MagicMock()
            cell.text = txt
            link = MagicMock()
            link.get_attribute.return_value = (
                f"javascript:void(0)?mhd=MHD_{cells_text[4]}"
                if len(cells_text) > 4
                else ""
            )
            cell.find_element.return_value = link
            cells.append(cell)
        row.find_elements.return_value = cells
        rows.append(row)
    table.find_elements.return_value = rows
    driver.find_element.return_value = table
    return driver


def test_find_mhd_returns_value_for_matching_row():
    driver = _make_driver_with_table(
        [
            ["h1", "h2", "h3", "h4", "h5"],
            ["a", "link", "c", "d", "307767153100"],
        ]
    )
    mhd = find_mhd(driver, "307767153100")
    assert mhd == "MHD_307767153100"


def test_find_mhd_raises_when_no_data():
    driver = MagicMock()
    table = MagicMock()
    header = MagicMock()
    header.text = "header"
    no_data = MagicMock()
    no_data.text = "No data available"
    table.find_elements.return_value = [header, no_data]
    driver.find_element.return_value = table
    with pytest.raises(ScrapeError):
        find_mhd(driver, "307767153100")


def test_find_mhd_raises_when_customs_mismatch():
    driver = _make_driver_with_table(
        [
            ["h1", "h2", "h3", "h4", "h5"],
            ["a", "link", "c", "d", "999999"],
        ]
    )
    with pytest.raises(ScrapeError):
        find_mhd(driver, "307767153100")
