# PDF Invoice / Biên Lai Processor

Công cụ CLI tự động hóa quy trình lấy biên lai điện tử (hóa đơn) cho các tờ khai hải quan từ cổng `thuphi.haiphong.gov.vn`. Ứng dụng đọc các file PDF tờ khai, đăng nhập tự động bằng pool tài khoản, gọi API và Selenium để tải biên lai PDF tương ứng, lưu vào thư mục local theo ngày, và ghi log kết quả vào Google Sheet.

## Mục đích dự án

- **Đầu vào:** thư mục chứa PDF tờ khai hải quan (mặc định `~/Desktop/customs/`).
- **Xử lý tự động:**
  1. `pdf_invoice_parser` đọc header tờ khai bằng `pdfminer.six` để lấy `customs_number`, ngày đăng ký, tên doanh nghiệp, mã số thuế...
  2. `ChromeManager` khởi động Chrome ở chế độ remote-debug, đăng nhập cổng thuế bằng tài khoản trong `accounts.json` (rotate khi gặp lỗi).
  3. `CustomApiClient` gọi API tra cứu biên lai theo số tờ khai.
  4. Selenium mở `HoaDonViewer.aspx` để tải PDF biên lai gốc.
  5. `local_storage_utils` lưu PDF vào `~/Desktop/customs/<dd-mm-yyyy>/`.
  6. `google_sheet_utils` ghi log batch (mã tờ khai, biên lai, thời gian, trạng thái) lên Google Sheet.
- **Đầu ra:** PDF biên lai đã đặt tên chuẩn theo ngày + dòng log trên Google Sheet.

> Lưu ý: bản trước (`release-v1`..`v3`) là Flask web app + huấn luyện CNN/PaddleOCR giải captcha. Bản hiện tại (`release-v4`) đã chuyển sang **CLI batch processor** và bỏ pipeline OCR/captcha tự động.

## Kiến trúc tổng quan

### 1. End-to-end pipeline

```mermaid
flowchart TD
    A[User chạy CLI<br/>pdf_processor.py] --> B[Đọc args<br/>--data-dir / --files]
    B --> C[Liệt kê PDF tờ khai<br/>~/Desktop/customs/*.pdf]
    C --> D[batch_process_files]
    D --> E[extract_files_info<br/>pdfminer parse header]
    E --> F{Có customs_number?}
    F -- Không --> X[Bỏ qua file]
    F -- Có --> G[ChromeManager<br/>khởi động Chrome debug + login]
    G --> H[CustomApiClient<br/>tra cứu biên lai theo số TK]
    H --> I[Selenium mở<br/>HoaDonViewer.aspx]
    I --> J[Tải PDF biên lai]
    J --> K[local_storage_utils<br/>lưu vào ~/Desktop/customs/&lt;date&gt;/]
    K --> L[google_sheet_utils<br/>append log batch]
    L --> M[Hiển thị thống kê<br/>tk dialog + console]
```

### 2. PDF parsing (`pdf_invoice_parser.py`)

```mermaid
flowchart LR
    A[PDF file] --> B[pdfminer<br/>extract_text_from_pdf]
    B --> C[split_sections<br/>tách header / body / footer]
    C --> D[extract_header_info<br/>regex match]
    D --> E[Header dict<br/>customs_number, ngày,<br/>doanh nghiệp, MST...]
    D --> F[convert_price_to_number<br/>parse số tiền VND]
    E --> G[Trả về cho<br/>receipt_fetcher]
```

### 3. Chrome login pool (`chrome_manager.py`)

```mermaid
flowchart TD
    A[ChromeManager.start] --> B{Chrome debug<br/>đang chạy port 9222?}
    B -- Không --> C[subprocess spawn Chrome<br/>--remote-debugging-port=9222<br/>--user-data-dir]
    B -- Có --> D[Reuse instance]
    C --> E[webdriver.Chrome attach]
    D --> E
    E --> F[Load accounts.json]
    F --> G[Pick account theo index]
    G --> H[Mở trang đăng nhập]
    H --> I[Fill username/password<br/>+ captcha thủ công/cookie]
    I --> J{Login OK?}
    J -- Fail --> K[Rotate sang<br/>account kế tiếp]
    K --> G
    J -- OK --> L[CookieManager.save<br/>lưu phiên]
    L --> M[Trả driver cho<br/>receipt_fetcher]
```

### 4. API + download biên lai (`custom_api_client.py` + `receipt_fetcher.py`)

```mermaid
sequenceDiagram
    participant RF as receipt_fetcher
    participant API as CustomApiClient
    participant Web as thuphi.haiphong.gov.vn
    participant SE as Selenium driver
    participant FS as local_storage_utils

    RF->>API: search(customs_number)
    API->>Web: POST /api/tra-cuu (cookies)
    Web-->>API: JSON response
    API->>API: parse_response()
    API-->>RF: invoice_info (mhd, drive_link...)
    RF->>SE: execute_script(window.open HoaDonViewer.aspx)
    SE->>Web: GET HoaDonViewer.aspx?mhd=...
    Web-->>SE: PDF binary
    SE-->>RF: pdf_bytes
    RF->>FS: save_pdf_to_local(pdf_bytes, date_folder, filename)
    FS-->>RF: saved_path
```

### 5. Local storage + Google Sheet logging

```mermaid
flowchart LR
    subgraph Local [local_storage_utils]
        A1[batch_save_to_local] --> A2[Tạo thư mục<br/>~/Desktop/customs/&lt;dd-mm-yyyy&gt;]
        A2 --> A3[Ghi PDF<br/>theo filename]
        A3 --> A4[get_storage_info<br/>kiểm tra dung lượng]
    end

    subgraph Sheet [google_sheet_utils]
        B1[batch_append_to_sheet] --> B2[SheetService singleton<br/>load service-account]
        B2 --> B3[get_or_create_sheet<br/>theo ngày]
        B3 --> B4[values.append<br/>Sheets API]
    end

    RF[receipt_fetcher] --> A1
    RF --> B1
    A4 --> RF
    B4 --> RF
```

### 6. Build pipeline (`build.py`)

```mermaid
flowchart TD
    A[python build.py] --> B[install_requirements<br/>pip install -r]
    B --> C[prepare_icon<br/>avatar.jpg → .icns/.ico]
    C --> D[prepare_sensitive_files<br/>copy accounts.json,<br/>service-account, .env<br/>vào build/sensitive]
    D --> E[Compose PyInstaller args<br/>--onefile --add-data ...]
    E --> F[subprocess.run pyinstaller]
    F --> G[dist/pdf_processor<br/>dist/pdf_processor.exe]
```

Các module phụ trợ:
- `cookie_manager.py` — lưu/khôi phục cookie phiên đăng nhập.
- `utils.py` — helper path/date dùng chung; `get_default_customs_dir()` trả về `~/Desktop/customs`.
- `build.py` — đóng gói thành binary bằng PyInstaller.

## Yêu cầu hệ thống

- Python **3.10+** (project test với 3.10.10 trên Windows, Python 3 mặc định trên macOS).
- Google Chrome đã cài (ChromeDriver tự động tải qua `webdriver-manager`).
- macOS hoặc Windows. Linux có thể chạy nhưng chưa được test.
- (Tuỳ chọn) ODBC driver hệ thống nếu sử dụng `pyodbc` (`brew install unixodbc` trên macOS).

## Cài đặt

### macOS

```bash
git clone <repo-url>
cd img-extraction

python3 -m venv env
source env/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

### Windows

```powershell
git clone <repo-url>
cd img-extraction

python -m venv env
.\env\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

## Cấu hình trước khi chạy

1. **Tài khoản đăng nhập** — file `accounts.json` ở thư mục gốc, định dạng:
   ```json
   [
     { "username": "0123456789", "password": "Mat_khau_1" },
     { "username": "9876543210", "password": "Mat_khau_2" }
   ]
   ```
   `ChromeManager` sẽ duyệt qua từng tài khoản nếu một tài khoản fail. **Không commit file này.**

2. **Google Service Account** — bắt buộc nếu cần ghi log lên Sheet:
   - Tạo project trong Google Cloud Console, enable Google Sheets API.
   - Tạo Service Account → tải JSON key → đổi tên thành `driver-service-account.json`, đặt ở thư mục gốc.
   - Share spreadsheet `SPREADSHEET_ID` (định nghĩa trong `google_sheet_utils.py`) cho email của Service Account với quyền Editor.

3. **Thư mục input** — đặt PDF tờ khai vào `~/Desktop/customs/` (sẽ tự tạo nếu chưa có).

4. **(Tuỳ chọn) `.env`** — copy từ `.env.example` (nếu có) và set các biến môi trường cần thiết.

## Chạy ứng dụng

Kích hoạt venv rồi chạy CLI:

```bash
# Xử lý toàn bộ PDF trong ~/Desktop/customs
python pdf_processor.py

# Chỉ định thư mục input khác
python pdf_processor.py --data-dir /path/to/customs

# Chỉ xử lý các file cụ thể
python pdf_processor.py --files INV001.pdf INV002.pdf

# Tắt popup thông báo (chạy headless / scheduled job)
python pdf_processor.py --quiet
```

Khi chạy:
- Tool sẽ mở Chrome (remote-debug port `9222`) — đảm bảo đóng các Chrome instance khác trước.
- Đăng nhập tự động và tải biên lai về `~/Desktop/customs/<dd-mm-yyyy>/`.
- Cuối phiên hiển thị thống kê: tổng file, đã xử lý, thành công, thất bại.

## Build binary (PyInstaller)

Đóng gói thành executable một file để chạy trên máy không cài Python:

```bash
# macOS / Linux
python build.py

# Windows (giấu console window)
python build.py --no-console
```

`build.py` sẽ:
1. Cài lại requirements.
2. Convert `avatar.jpg` thành `icon.icns` (macOS) hoặc `icon.ico` (Windows).
3. Copy các file nhạy cảm (`accounts.json`, `driver-service-account.json`, `.env`) vào `build/sensitive/` rồi bundle vào binary.
4. Chạy PyInstaller với `--onefile` → output tại `dist/pdf_processor` (macOS) hoặc `dist/pdf_processor.exe` (Windows).

## Cấu trúc thư mục

```
img-extraction/
├── pdf_processor.py         # Entry point CLI
├── receipt_fetcher.py       # Pipeline chính (orchestration)
├── pdf_invoice_parser.py    # Parse PDF tờ khai (pdfminer)
├── chrome_manager.py        # Selenium + login pool
├── custom_api_client.py     # HTTP client cho API thuế
├── cookie_manager.py        # Quản lý cookie phiên
├── google_sheet_utils.py    # Ghi log lên Google Sheet
├── google_drive_utils.py    # (legacy) upload Drive
├── local_storage_utils.py   # Lưu PDF local theo ngày
├── utils.py                 # Helper path/date
├── build.py                 # PyInstaller build script
├── accounts.json            # Pool tài khoản đăng nhập (KHÔNG commit)
├── requirements.txt
├── static/                  # Icon, asset
└── tests:
    ├── test_local_storage.py
    └── test_rename_files.py
```

## Xử lý sự cố

- **Chrome không mở:** đóng toàn bộ Chrome đang chạy, xóa profile debug nếu treo.
- **Không tìm thấy `driver-service-account.json`:** tạo Service Account theo bước Cấu hình ở trên.
- **`pyodbc` build fail trên macOS:** `brew install unixodbc` rồi `pip install pyodbc` lại.
- **Selenium timeout/login fail:** kiểm tra tài khoản trong `accounts.json` còn hợp lệ, thử rotate.
- **Port 9222 bị chiếm:** kill Chrome instance đang dùng debug port.

## License

[MIT License](LICENSE)
