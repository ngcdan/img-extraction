import os
import sys
import platform
import argparse
from receipt_fetcher import batch_process_files
from utils import send_notification

def get_default_customs_dir():
    """Lấy đường dẫn thư mục customs mặc định trên Desktop"""
    system = platform.system()
    if system == 'Windows':
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    elif system == 'Darwin':  # macOS
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    else:
        desktop = os.path.expanduser('~/Desktop')

    customs_dir = os.path.join(desktop, 'customs')

    # Tạo thư mục nếu chưa tồn tại
    if not os.path.exists(customs_dir):
        try:
            os.makedirs(customs_dir)
            print(f"Đã tạo thư mục customs tại: {customs_dir}")
        except Exception as e:
            print(f"Không thể tạo thư mục customs: {str(e)}")
            sys.exit(1)

    return customs_dir

def main():
    parser = argparse.ArgumentParser(description='Process PDF files in batch')
    parser.add_argument('--data-dir', type=str, help='Directory containing PDF files',
                       default=get_default_customs_dir())
    parser.add_argument('--files', type=str, nargs='+', help='List of PDF files to process')
    parser.add_argument('--quiet', action='store_true', help='Suppress notifications')

    args = parser.parse_args()

    # Override send_notification if quiet mode is enabled
    if args.quiet:
        def quiet_notification(message, type=None):
            pass
        global send_notification
        send_notification = quiet_notification

    # Get files to process
    if args.files:
        files_to_process = args.files
    else:
        # Process all PDFs in customs directory
        if not os.path.exists(args.data_dir):
            print(f"Thư mục customs không tồn tại: {args.data_dir}")
            print("Vui lòng tạo thư mục và đặt các file PDF vào đó.")
            input("Nhấn Enter để thoát...")
            sys.exit(1)

        files_to_process = [f for f in os.listdir(args.data_dir) if f.lower().endswith('.pdf')]

        if not files_to_process:
            print(f"Không tìm thấy file PDF nào trong thư mục: {args.data_dir}")
            print("Vui lòng đặt các file PDF cần xử lý vào thư mục này.")
            input("Nhấn Enter để thoát...")
            sys.exit(1)

    file_paths = [os.path.join(args.data_dir, filename) for filename in files_to_process]

    print("\n=== PDF Batch Processor ===")
    print(f"Thư mục xử lý: {args.data_dir}")
    print(f"Số lượng file: {len(files_to_process)}")
    print("========================\n")

    try:
        result = batch_process_files(file_paths)

        if result['success']:
            print("\nKết quả xử lý:")
            print(f"- Tổng số file: {result['stats']['total_files']}")
            print(f"- Đã xử lý: {result['stats']['processed']}")
            print(f"- Thành công: {result['stats']['sheet_success']}")
            print(f"- Thất bại: {result['stats']['sheet_error']}")
        else:
            print(f"\nLỗi: {result['error']}")

    except Exception as e:
        print(f"Lỗi trong quá trình xử lý: {str(e)}")

    input("\nNhấn Enter để thoát...")

if __name__ == "__main__":
    main()
