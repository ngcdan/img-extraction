# Chuyển đổi từ Google Drive sang Local Storage - Tóm tắt thay đổi

## Thay đổi chính

### 1. Tạo mới local_storage_utils.py
- **Chức năng**: Thay thế hoàn toàn google_drive_utils.py
- **Tính năng chính**:
  - `get_local_downloads_dir()`: Tạo thư mục downloads trong thư mục user
  - `save_pdf_to_local()`: Lưu PDF vào thư mục local theo ngày
  - `batch_save_to_local()`: Xử lý batch nhiều files
  - `get_storage_info()`: Kiểm tra dung lượng ổ đĩa
  - `cleanup_old_files()`: Dọn dẹp files cũ
  - `open_downloads_folder()`: Mở thư mục downloads

### 2. Cập nhật receipt_fetcher.py
- **Thay đổi import**: Từ `google_drive_utils` sang `local_storage_utils`
- **Đổi tên function**: `process_and_upload_invoices_batch()` → `process_and_save_invoices_batch()`
- **Cập nhật logic**:
  - Thay thế tất cả upload lên Drive bằng lưu local
  - Thêm kiểm tra dung lượng ổ đĩa trước khi xử lý
  - Cập nhật thông báo và log messages
  - Xử lý files được tải về theo cấu trúc thư mục ngày

### 3. Cấu trúc thư mục mới
```
~/Downloads/pdf-invoices/
├── 2024-12-19/          # Thư mục theo ngày
│   ├── CSHT112855.pdf   # Files PDF được tải
│   └── ...
├── 2024-12-20/
└── ...
```

## Chi tiết thay đổi

### Trước (Google Drive):
- Upload files lên Google Drive
- Tạo links chia sẻ
- Lưu links trong Google Sheets
- Phụ thuộc vào quota Google Drive

### Sau (Local Storage):
- Lưu files trong máy local
- Tổ chức theo thư mục ngày
- Lưu đường dẫn local trong sheets
- Không giới hạn quota (chỉ giới hạn bởi ổ đĩa)

## Lợi ích

1. **Không giới hạn quota**: Không còn lỗi "quota exceeded"
2. **Tốc độ nhanh hơn**: Không cần upload qua mạng
3. **Độc lập**: Không phụ thuộc Google Drive API
4. **Tổ chức tốt**: Files được sắp xếp theo ngày
5. **Tiện lợi**: Có thể mở thư mục downloads trực tiếp

## Files đã thay đổi

1. **Mới**: `local_storage_utils.py` - Utility functions cho local storage
2. **Sửa**: `receipt_fetcher.py` - Logic chính thay đổi từ upload sang local
3. **Giữ nguyên**: `google_sheet_utils.py` - Chỉ cập nhật source_file field
4. **Test**: `test_local_storage.py` - Script kiểm tra functionality

## Cách sử dụng

Sau khi cập nhật, chỉ cần chạy script như bình thường:
```bash
python receipt_fetcher.py
```

Files sẽ được lưu tại: `~/Downloads/pdf-invoices/YYYY-MM-DD/`

## Ghi chú

- Google Sheets vẫn hoạt động bình thường
- Service Account credentials vẫn cần thiết cho Sheets API
- Files cũ trên Google Drive không bị ảnh hưởng
- Có thể dọn dẹp files cũ bằng `cleanup_old_files()`