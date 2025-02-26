Dưới đây là nội dung ngắn gọn nhưng đầy đủ cho file `README.md` của dự án "image-extraction":

```markdown
# Image Extraction

Dự án trích xuất thông tin từ file PDF theo mẫu chung bằng Layout-Parser.

## Yêu cầu
- Python 3.10+
- macOS (đã kiểm tra với Python 3.10.10)

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

## Sử dụng
- Đặt file PDF mẫu vào thư mục dự án.
- Chạy mã chính (sẽ cập nhật sau khi hoàn thiện).

## Ghi chú
- Sử dụng EfficientDet để phân tích bố cục.
- Tesseract hỗ trợ OCR cho PDF dạng ảnh.

## Tài liệu tham khảo
- [Layout-Parser Docs](https://layout-parser.readthedocs.io/)
- [Tesseract Installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
```

