from datetime import date

from customs_bot.shared.paths import date_folder_name, ensure_date_folder


def test_date_folder_name_format():
    assert date_folder_name(date(2026, 4, 7)) == "07-04-2026"


def test_ensure_date_folder_creates(tmp_path):
    folder = ensure_date_folder(tmp_path, date(2026, 4, 7))
    assert folder.exists()
    assert folder.name == "07-04-2026"
    assert folder.parent == tmp_path


def test_ensure_date_folder_idempotent(tmp_path):
    f1 = ensure_date_folder(tmp_path, date(2026, 4, 7))
    f2 = ensure_date_folder(tmp_path, date(2026, 4, 7))
    assert f1 == f2
