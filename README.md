# Img Extraction

Dự án trích xuất thông tin từ file PDF theo mẫu chung bằng Layout-Parser.

## Cài đặt
1. Tạo và kích hoạt virtual environment:
   ```bash
   python -m venv env
   source env/bin/activate
   ```
2. Cài thư viện:
   ```bash
   pip install "layoutparser[effdet,ocr]"
   ```
3. Cài Tesseract-OCR (cho OCR):
   ```bash
   brew install tesseract
   ```

## Ghi chú
- Sử dụng EfficientDet để phân tích bố cục.
- Tesseract hỗ trợ OCR cho PDF dạng ảnh.

## Tài liệu tham khảo
- [Layout-Parser Docs](https://layout-parser.readthedocs.io/)
- [Tesseract Installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
```

