import os
import sys
import platform

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