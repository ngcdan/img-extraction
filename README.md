# PDF Information Extraction Tool

Ứng dụng trích xuất thông tin từ file PDF tự động, sử dụng OCR và xử lý hình ảnh.

## Cài đặt từ đầu

### Windows

1. Cài đặt Python:
   - Tải Python 3.8+ từ [python.org](https://www.python.org/downloads/)
   - ⚠️ Khi cài đặt, PHẢI chọn "Add Python to PATH"
   - Kiểm tra cài đặt:
   ```bash
   python --version
   pip --version
   ```

2. Cài đặt Git (nếu chưa có):
   - Tải từ [git-scm.com](https://git-scm.com/download/win)
   - Chọn cài đặt mặc định

3. Clone project:
   ```bash
   git clone <repository-url>
   cd <project-directory>
   ```

4. Tạo và kích hoạt môi trường ảo:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

5. Cài đặt dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### macOS

1. Cài đặt Homebrew (nếu chưa có):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Cài đặt Python:
   ```bash
   brew install python@3.8
   ```

3. Cài đặt Git (nếu chưa có):
   ```bash
   brew install git
   ```

4. Clone project:
   ```bash
   git clone <repository-url>
   cd <project-directory>
   ```

5. Tạo và kích hoạt môi trường ảo:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

6. Cài đặt dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Cấu hình môi trường

1. Tạo file `.env`:
   ```bash
   cp .env.example .env
   ```

2. Chỉnh sửa `.env` với nội dung:
   ```env
   # App Settings
   FLASK_ENV=development
   PORT=8080

   # Google Sheets Integration
   GOOGLE_SHEETS_ID=your_sheet_id

   # Chrome Settings (tự động detect nếu để trống)
   CHROME_BINARY_PATH=
   ```

3. Cấu hình Google Sheets (nếu cần):
   - Tạo project trong Google Cloud Console
   - Enable Google Sheets API
   - Tạo Service Account và tải file credentials
   - Đặt file credentials vào thư mục gốc với tên `service-account-key.json`

## Cấu trúc thư mục
```
project/
├── app.py                    # Entry point
├── utils.py                  # Utility functions
├── receipt_fetcher.py        # PDF download logic
├── extract_info.py           # PDF processing
├── requirements.txt          # Dependencies
├── .env                      # Environment variables
├── .gitignore               # Git ignore rules
├── templates/               # HTML templates
│   └── index.html
├── static/                  # Static assets
│   ├── css/
│   └── js/
└── data/                    # Data directory
    ├── downloads/           # Downloaded PDFs
    └── output/             # Processed results
```

## Chạy ứng dụng

1. Kích hoạt môi trường ảo:
```bash
# Windows
.\venv\Scripts\activate

# macOS
source venv/bin/activate
```

2. Chạy server:
```bash
python app.py
```

Ứng dụng sẽ tự động:
- Mở Chrome với debug port
- Mở trình duyệt mặc định tại http://localhost:8080

## Xử lý sự cố thường gặp

### Lỗi khi cài đặt dependencies

1. Lỗi về Microsoft Visual C++:
   ```bash
   # Windows: Cài đặt Build Tools
   pip install --upgrade setuptools wheel
   ```

2. Lỗi về PaddlePaddle:
   ```bash
   # Thử cài đặt phiên bản CPU only
   pip install paddlepaddle
   ```

3. Lỗi về OpenCV:
   ```bash
   # Windows
   pip install opencv-python-headless

   # macOS
   brew install opencv
   pip install opencv-python
   ```

### Lỗi khi chạy ứng dụng

1. Chrome không mở được:
   - Kiểm tra Chrome đã được cài đặt
   - Đóng tất cả cửa sổ Chrome đang chạy
   - Xóa thư mục Chrome debug nếu tồn tại

2. Port 8080 bị chiếm:
   - Thay đổi port trong `.env`
   - Kiểm tra và tắt các ứng dụng đang sử dụng port 8080

3. Lỗi về OCR:
   - Kiểm tra PaddleOCR đã cài đặt đúng
   - Đảm bảo đủ RAM (tối thiểu 4GB)

## Phát triển

1. Format code:
   ```bash
   pip install black
   black .
   ```

2. Kiểm tra lỗi:
   ```bash
   pip install flake8
   flake8
   ```

## Build ứng dụng

```bash
# Windows
pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" app.py

# macOS
pyinstaller --onefile --add-data "templates:templates" --add-data "static:static" app.py
```

File thực thi sẽ được tạo trong thư mục `dist/`

## License

[MIT License](LICENSE)
