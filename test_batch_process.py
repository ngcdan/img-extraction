import os
import sys
import platform
import argparse
from receipt_fetcher import batch_process_files
import tkinter as tk
from tkinter import messagebox

# Suppress Tk deprecation warning
os.environ['TK_SILENCE_DEPRECATION'] = '1'

def show_message_dialog(message, title="Thông báo"):
    """Hiển thị dialog thông báo trên cả Windows và macOS"""
    try:
        # Tạo root window
        root = tk.Tk()
        # Ẩn cửa sổ chính
        root.withdraw()

        # Đặt window lên trên cùng
        root.lift()
        root.attributes('-topmost', True)

        # Hiển thị dialog
        messagebox.showinfo(title, message)

        # Dọn dẹp
        root.destroy()
    except Exception as e:
        # Fallback về print nếu có lỗi với GUI
        print(message)
        if platform.system() == 'Windows':
            input("Nhấn Enter để thoát...")

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

    # Get files to process
    if args.files:
        files_to_process = args.files
    else:
        # Process all PDFs in customs directory
        if not os.path.exists(args.data_dir):
            show_message_dialog(
                f"Thư mục customs không tồn tại: {args.data_dir}\n"
                "Vui lòng tạo thư mục và đặt các file PDF vào đó.",
                "Lỗi"
            )
            sys.exit(1)

        files_to_process = [f for f in os.listdir(args.data_dir) if f.lower().endswith('.pdf')]

        if not files_to_process:
            show_message_dialog(
                f"Không tìm thấy file PDF nào trong thư mục: {args.data_dir}\n"
                "Vui lòng đặt các file PDF cần xử lý vào thư mục này.",
                "Cảnh báo"
            )
            sys.exit(1)

    file_paths = [os.path.join(args.data_dir, filename) for filename in files_to_process]

    print("\n=== PDF Batch Processor ===")
    print(f"Thư mục xử lý: {args.data_dir}")
    print(f"Số lượng file: {len(files_to_process)}")
    print("========================\n")

    try:
        result = batch_process_files(file_paths)

        if result['success']:
            summary = (
                "\nKết quả xử lý:\n"
                f"- Tổng số file: {result['stats']['total_files']}\n"
                f"- Đã xử lý: {result['stats']['processed']}\n"
                f"- Thành công: {result['stats']['download_success']}\n"
                f"- Thất bại: {result['stats']['download_error']}"
            )
            print(summary)
            show_message_dialog(summary, "Kết quả xử lý")
        else:
            error_msg = f"\nLỗi: {result['error']}"
            print(error_msg)
            show_message_dialog(error_msg, "Lỗi")

    except Exception as e:
        error_msg = f"Lỗi trong quá trình xử lý: {str(e)}"
        print(error_msg)
        show_message_dialog(error_msg, "Lỗi")

if __name__ == "__main__":
    main()
