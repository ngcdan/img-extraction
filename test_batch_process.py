import os
from receipt_fetcher import batch_process_files
from utils import send_notification

def test_batch_processing():
    # Đường dẫn tới thư mục data
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    # Danh sách các file cần xử lý
    files_to_process = ['2.pdf', '4.pdf']
    file_paths = [os.path.join(data_dir, filename) for filename in files_to_process]

    # Kiểm tra xem các file có tồn tại không
    missing_files = [f for f in file_paths if not os.path.exists(f)]
    if missing_files:
        print("Không tìm thấy các file sau:")
        for f in missing_files:
            print(f"- {f}")
        return

    print("Bắt đầu xử lý batch...")
    print(f"Files được xử lý: {', '.join(files_to_process)}")

    try:
        # Gọi hàm xử lý batch
        result = batch_process_files(file_paths)

        # In kết quả
        if result['success']:
            print("\nKết quả xử lý:")
            print(f"- Tổng số file: {result['stats']['total_files']}")
            print(f"- Số file đã xử lý: {result['stats']['processed']}")
            print(f"- Thành công: {result['stats']['sheet_success']}")
            print(f"- Thất bại: {result['stats']['sheet_error']}")
        else:
            print(f"\nLỗi: {result['error']}")

    except Exception as e:
        print(f"Lỗi trong quá trình test: {str(e)}")

if __name__ == "__main__":
    test_batch_processing()