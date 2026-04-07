from datetime import date

from customs_bot.features.storage.local import save_pdf


def test_save_pdf_writes_file(tmp_path):
    pdf_bytes = b"%PDF-1.4 fake content"
    saved = save_pdf(
        pdf_bytes=pdf_bytes,
        filename="MHD001.pdf",
        base_dir=tmp_path,
        on_date=date(2026, 4, 7),
    )
    assert saved.exists()
    assert saved.read_bytes() == pdf_bytes
    assert saved.parent.name == "07-04-2026"
    assert saved.parent.parent == tmp_path


def test_save_pdf_creates_date_folder_idempotent(tmp_path):
    save_pdf(b"a", "a.pdf", tmp_path, date(2026, 4, 7))
    save_pdf(b"b", "b.pdf", tmp_path, date(2026, 4, 7))
    folder = tmp_path / "07-04-2026"
    assert (folder / "a.pdf").exists()
    assert (folder / "b.pdf").exists()
