# Phase 2 Spike — Investigate PDF Endpoint

## Mục đích

Phase 2 ban đầu giả định có thể bỏ Selenium download bằng cách: Selenium login →
extract cookies → httpx GET PDF. Sau khi đọc code thật:

- API client (`custom_api_client.py`) gọi bên thứ 3 (beelogistics.cloud) bằng API key
  → KHÔNG cần cookies từ Selenium.
- Receipt download (`receipt_fetcher.py`) mở `HoaDonViewer.aspx` rồi dùng Chrome DevTools
  `Page.printToPDF` để **render trang ASPX → PDF**. Đây có thể là viewer page chứ không
  phải direct PDF binary.

Spike này sẽ trả lời câu hỏi: **HoaDonViewer.aspx có direct PDF endpoint nào trong
network requests không?** Nếu có → Phase 2 dùng httpx GET trực tiếp được. Nếu không →
phải giữ Selenium cho phần download (Phase 2 reduced scope).

## Cần chuẩn bị

1. Account thật trên `thuphi.haiphong.gov.vn` (đã trong `accounts.json`)
2. 1 mã `mhd` (drive_link) thật từ kết quả API beelogistics. Cách lấy:
   - Chạy `python custom_api_client.py` với customs_number thật, copy `drive_link` từ output
   - Hoặc tìm trong log run cũ
3. Chrome đã đóng hết (kill mọi instance)

## Các bước chạy

### 1. Mở Chrome debug

```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=$HOME/chrome-debug-profile
```

### 2. Login thủ công

Trong cửa sổ Chrome vừa mở, vào https://thuphi.haiphong.gov.vn và login bình thường
(nhập username/password/captcha).

### 3. Chạy spike script

```bash
source env/bin/activate
python scripts/spike_inspect_pdf_endpoint.py <MHD>
```

Trong đó `<MHD>` là mã drive_link bạn đã chuẩn bị ở bước "Cần chuẩn bị".

### 4. Đọc kết quả

Output: `spike_output.json` ở repo root.

Quan trọng nhất là field `summary`:

```json
{
  "summary": {
    "total_resources": 42,
    "pdf_resources_found": 1,
    "verdict": "DIRECT_PDF_ENDPOINT_EXISTS"
  }
}
```

- **`DIRECT_PDF_ENDPOINT_EXISTS`** → đọc `pdf_candidates[]` để lấy URL pattern.
  Phase 2 sẽ dùng httpx GET URL này với cookies từ Selenium login. Đi theo plan gốc.

- **`NO_DIRECT_PDF_ENDPOINT_FOUND`** → không có direct PDF, viewer thực sự render
  HTML rồi printToPDF. Phase 2 sẽ giữ Selenium cho phần download (Hướng B). Vẫn refactor
  được module structure, chỉ là không bỏ được Selenium.

### 5. Báo lại

Gửi nội dung `spike_output.json` (hoặc ít nhất phần `summary` + `pdf_candidates`) để
quyết định Phase 2 plan chính xác.

## Lưu ý bảo mật

`spike_output.json` có thể chứa cookies session. **Không commit file này.** Đã được
gitignore (xem `.gitignore`).
