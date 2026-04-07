"""Capture current pdfminer parser output as golden baseline for Phase 3."""

import json
from pathlib import Path

from pdf_invoice_parser import process_pdf

SAMPLES = Path("tests/fixtures/samples")
BASELINES = Path("tests/fixtures/baselines")


def main() -> int:
    BASELINES.mkdir(parents=True, exist_ok=True)
    for pdf in sorted(SAMPLES.glob("*.pdf")):
        result = process_pdf(str(pdf))
        out = BASELINES / f"{pdf.stem}.json"
        out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
