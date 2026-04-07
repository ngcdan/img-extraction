# Customs Receipt Bot

Công cụ CLI tự động hóa quy trình lấy biên lai điện tử (hóa đơn) cho các tờ khai hải quan từ cổng `thuphi.haiphong.gov.vn`. Ứng dụng đọc các file PDF tờ khai, đăng nhập tự động bằng pool tài khoản, gọi API và Selenium để tải biên lai PDF tương ứng, lưu vào thư mục local theo ngày, và ghi log kết quả vào Google Sheet.

## Mục đích dự án

- **Đầu vào:** thư mục chứa PDF tờ khai hải quan (mặc định `~/Desktop/customs/`).
- **Xử lý tự động:**
  1. `pdf_parsing` đọc header tờ khai bằng `pymupdf` để lấy `customs_number`, ngày đăng ký, tên doanh nghiệp, mã số thuế...
  2. `auth` khởi động Chrome ở chế độ remote-debug, đăng nhập cổng thuế bằng tài khoản trong `accounts.json` (rotate khi gặp lỗi).
  3. `receipt_fetch` gọi API tra cứu biên lai theo số tờ khai, dùng Selenium tải PDF biên lai gốc.
  4. `storage` lưu PDF vào `~/Desktop/customs/<dd-mm-yyyy>/`.
  5. `reporting` ghi log batch lên Google Sheet.
- **Đầu ra:** PDF biên lai đã đặt tên chuẩn theo ngày + dòng log trên Google Sheet.

## Yêu cầu hệ thống

- Python **3.10+**
- Google Chrome đã cài (ChromeDriver tự động tải qua `webdriver-manager`).
- macOS hoặc Windows. Linux có thể chạy nhưng chưa được test.

## Cài đặt

```bash
git clone <repo-url>
cd customs-receipt-bot

python3 -m venv env
source env/bin/activate      # Windows: .\env\Scripts\activate

pip install --upgrade pip
pip install -e ".[dev]"
```

## Cấu hình trước khi chạy

1. **Tài khoản đăng nhập** — file `accounts.json` ở thư mục gốc:
   ```json
   [
     { "username": "0123456789", "password": "Mat_khau_1" },
     { "username": "9876543210", "password": "Mat_khau_2" }
   ]
   ```
   **Không commit file này.**

2. **Google Service Account** — bắt buộc nếu cần ghi log lên Sheet:
   - Tạo project trong Google Cloud Console, enable Google Sheets API.
   - Tạo Service Account, tải JSON key thành `driver-service-account.json`, đặt ở thư mục gốc.
   - Share spreadsheet cho email của Service Account với quyền Editor.

3. **Thư mục input** — đặt PDF tờ khai vào `~/Desktop/customs/` (sẽ tự tạo nếu chưa có).

4. **(Tuỳ chọn) `.env`** — copy từ `.env.example` (nếu có) và set các biến môi trường cần thiết.

## Chạy ứng dụng

```bash
# Xử lý toàn bộ PDF trong ~/Desktop/customs
python -m customs_bot

# Chỉ định thư mục input khác
python -m customs_bot --data-dir /path/to/customs

# Chỉ xử lý các file cụ thể
python -m customs_bot --files INV001.pdf INV002.pdf

# Tắt popup thông báo (chạy headless / scheduled job)
python -m customs_bot --quiet
```

Khi chạy:
- Tool sẽ mở Chrome (remote-debug port `9222`) — đảm bảo đóng các Chrome instance khác trước.
- Đăng nhập tự động và tải biên lai về `~/Desktop/customs/<dd-mm-yyyy>/`.
- Cuối phiên hiển thị thống kê: tổng file, đã xử lý, thành công, thất bại.

## Chạy test

```bash
pytest -q                          # chạy toàn bộ test
pytest --cov=customs_bot -q        # chạy + coverage
ruff check src/ tests/             # lint
```

## Build binary (PyInstaller)

Đóng gói thành executable một file:

```bash
# macOS / Linux
python build.py

# Windows (giấu console window)
python build.py --no-console
```

Output tại `dist/customs-bot` (macOS) hoặc `dist/customs-bot.exe` (Windows).

## Cấu trúc thư mục

```
customs-receipt-bot/
├── src/customs_bot/
│   ├── __main__.py              # Entry point
│   ├── cli.py                   # Argument parsing + orchestration
│   ├── config.py                # Pydantic settings
│   ├── logging.py               # Loguru setup
│   ├── shared/
│   │   ├── models.py            # Shared domain models
│   │   └── paths.py             # Path helpers
│   └── features/
│       ├── auth/                # Chrome login, account pool, session/cookie
│       ├── pdf_parsing/         # Parse PDF tờ khai (pymupdf)
│       ├── receipt_fetch/       # API client, scraper, PDF downloader, pipeline
│       ├── reporting/           # Google Sheet logging
│       └── storage/             # Local file storage
├── tests/                       # Integration / CLI tests
├── chrome_manager.py            # Legacy bridge (auth/selenium_login imports)
├── utils.py                     # Legacy helpers (used by chrome_manager)
├── build.py                     # PyInstaller build script
├── pyproject.toml
└── accounts.json                # Pool tài khoản (KHÔNG commit)
```

## Xử lý sự cố

- **Chrome không mở:** đóng toàn bộ Chrome đang chạy, xóa profile debug nếu treo.
- **Không tìm thấy `driver-service-account.json`:** tạo Service Account theo bước Cấu hình ở trên.
- **Selenium timeout/login fail:** kiểm tra tài khoản trong `accounts.json` còn hợp lệ, thử rotate.
- **Port 9222 bị chiếm:** kill Chrome instance đang dùng debug port.

## License

[MIT License](LICENSE)
