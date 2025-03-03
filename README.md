# Img Extraction

Dự án trích xuất thông tin từ file PDF theo mẫu chung bằng Layout-Parser.

## Yêu cầu hệ thống

### Windows
- Python 3.8 trở lên
- Google Chrome
- SQL Server ODBC Driver 17
- Tesseract-OCR

### macOS
- Python 3.8 trở lên
- Google Chrome
- SQL Server ODBC Driver 17
- Tesseract-OCR
- Homebrew (để cài đặt các dependencies)

## Hướng dẫn cài đặt

### Windows

1. Cài đặt Python:
   - Tải Python từ [python.org](https://www.python.org/downloads/)
   - Trong quá trình cài đặt, đảm bảo tích chọn "Add Python to PATH"

2. Cài đặt SQL Server ODBC Driver:
   - Tải và cài đặt [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

3. Cài đặt Tesseract-OCR:
   - Tải Tesseract installer từ [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
   - Chạy installer và ghi nhớ đường dẫn cài đặt (mặc định: `C:\Program Files\Tesseract-OCR`)
   - Thêm đường dẫn Tesseract vào PATH của Windows

4. Tạo và kích hoạt môi trường ảo:
   ```bash
   python -m venv env
   .\env\Scripts\activate
   ```

5. Cài đặt các thư viện Python:
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

3. Cài đặt SQL Server ODBC Driver:
   ```bash
   brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
   brew update
   brew install msodbcsql17
   ```

4. Cài đặt Tesseract-OCR:
   ```bash
   brew install tesseract
   ```

5. Tạo và kích hoạt môi trường ảo:
   ```bash
   python3 -m venv env
   source env/bin/activate
   ```

6. Cài đặt các thư viện Python:
   ```bash
   pip install -r requirements.txt
   ```

## Cấu hình môi trường

1. Tạo file `.env` từ mẫu:
   ```bash
   cp .env.example .env
   ```

2. Cập nhật các biến môi trường trong file `.env`:
   - Thông tin kết nối database
   - Cấu hình ứng dụng
   - Đường dẫn Tesseract (nếu khác mặc định)
   - API keys và các thông tin bảo mật khác

3. Cài đặt dependencies:
   ```bash
   # Windows
   pip install -r requirements.txt

   # macOS
   pip3 install -r requirements.txt
   ```

Lưu ý: File `.env` chứa thông tin nhạy cảm và đã được thêm vào `.gitignore`. Không commit file này lên repository.

## Cấu hình ứng dụng

1. Kiểm tra cài đặt Tesseract:
   - Windows: Đảm bảo biến môi trường PATH chứa đường dẫn Tesseract
   - macOS: Tesseract sẽ tự động được thêm vào PATH

2. Cấu trúc thư mục:
   ```
   project/
   ├── data/           # Thư mục chứa dữ liệu PDF
   ├── downloaded_pdfs/# Thư mục lưu PDF đã tải
   ├── env/           # Môi trường ảo Python
   ├── templates/     # Templates HTML
   └── ...
   ```

## Chạy ứng dụng

1. Kích hoạt môi trường ảo:
   - Windows: `.\env\Scripts\activate`
   - macOS: `source env/bin/activate`

2. Chạy ứng dụng:
   ```bash
   python app.py
   ```

3. Truy cập ứng dụng:
   - Mở trình duyệt và truy cập: `http://localhost:8080`

## Ghi chú
- Ứng dụng sẽ tự động mở Chrome với cấu hình debug
- Đảm bảo đóng tất cả cửa sổ Chrome trước khi chạy ứng dụng
- Kiểm tra quyền truy cập thư mục khi lưu file

## Xử lý sự cố

### Windows
- Nếu gặp lỗi Tesseract: Kiểm tra PATH và cài đặt lại Tesseract
- Lỗi ODBC: Đảm bảo đã cài đặt đúng phiên bản Driver 17

### macOS
- Lỗi quyền truy cập: Chạy với sudo nếu cần
- Lỗi Tesseract: Cài đặt lại qua Homebrew

## Tài liệu tham khảo
- [Layout-Parser Docs](https://layout-parser.readthedocs.io/)
- [Tesseract Documentation](https://tesseract-ocr.github.io/)
- [SQL Server ODBC Documentation](https://learn.microsoft.com/en-us/sql/connect/odbc/microsoft-odbc-driver-for-sql-server)

## Hướng dẫn build ứng dụng

### Chuẩn bị môi trường

1. Tạo và kích hoạt môi trường ảo:

Windows:
```bash
python -m venv env
.\env\Scripts\activate
```

macOS:
```bash
python3 -m venv env
source env/bin/activate
```

2. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

### Build ứng dụng

1. Chạy script build:
```bash
python build.py
```

2. File thực thi sẽ được tạo trong thư mục `dist`:
- Windows: `dist/ImgExtraction.exe`
- macOS: `dist/ImgExtraction`

### Chạy ứng dụng đã build

Windows:
```bash
.\dist\ImgExtraction.exe
```

macOS:
```bash
./dist/ImgExtraction
```

### Xử lý lỗi thường gặp

1. Lỗi "Permission denied" trên macOS:
```bash
chmod +x ./dist/ImgExtraction
```

2. Lỗi không tìm thấy Chrome:
- Đảm bảo đã cài đặt Google Chrome
- Kiểm tra đường dẫn Chrome trong file `receipt_fetcher.py`

3. Lỗi không tìm thấy templates/static:
- Kiểm tra cấu trúc thư mục
- Đảm bảo các file templates và static được copy vào dist

4. Lỗi thiếu dependencies:
```bash
pip install -r requirements.txt --upgrade
```

### Cấu trúc thư mục sau khi build

```
dist/
├── ImgExtraction (hoặc ImgExtraction.exe)
├── templates/
├── static/
└── .env
```

### Ghi chú quan trọng

1. Trước khi build:
- Đảm bảo đã cài đặt đầy đủ dependencies
- Kiểm tra file `.env` đã được cấu hình đúng
- Đóng tất cả các instance của Chrome

2. Sau khi build:
- Kiểm tra file thực thi trong thư mục `dist`
- Test ứng dụng trên môi trường mục tiêu
- Backup file thực thi và các resources

3. Môi trường production:
- Copy toàn bộ thư mục `dist` tới máy đích
- Cấu hình `.env` theo môi trường
- Cấp quyền thực thi nếu cần

# Cài đặt paddlepaddle (CPU version)
python -m pip install paddlepaddle

# Cài đặt paddleocr và các dependencies
pip install "paddleocr>=2.0.1"
pip install shapely pyclipper opencv-python

pip install tensorflow pillow numpy scikit-learn
