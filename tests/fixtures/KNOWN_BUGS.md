# Known parser bugs (baseline captured 2026-04-07)

The current pdfminer-based `process_pdf` fails to extract `line_items` for
PDFs whose container table layout causes pdfminer to scatter column headers
across separate lines.

| Sample | Has containers in source? | Baseline `line_items` | Status |
|---|---|---|---|
| Á CHÂU BIHAN007242.pdf | Yes | `[]` | **BUG** — must fix in Phase 3 |
| ASSA ABLOY BLHPH038448.pdf | Yes | `[]` | **BUG** — must fix in Phase 3 |
| Autel NL BEHPH006970.pdf | Yes | 1 item | OK (regression baseline) |

## Phase 3 acceptance criteria

After swapping `pdfminer.six` → `pymupdf`:
- All 3 files MUST return non-empty `line_items` matching the actual containers in source
- Other header fields (`so_ct`, `customs_number`, `tax_number`, `partner_invoice_name`, `date`) MUST match the captured baselines exactly
- Use `page.find_tables()` from pymupdf for structured extraction
