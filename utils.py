import os
import sys
import platform
from datetime import datetime
import base64, json

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

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def parse_date(date_str):
    """Chuyển đổi chuỗi ngày dạng 'dd/mm/yyyy' thành đối tượng datetime"""
    try:
        return datetime.strptime(date_str, '%d/%m/%Y')
    except (ValueError, TypeError):
        return None

def format_date(date_obj):
    """Chuyển đổi đối tượng datetime thành chuỗi 'dd/mm/yyyy'"""
    return date_obj.strftime('%d/%m/%Y') if date_obj else None


class IOUtil:
    @staticmethod
    def read_bytes(file_path: str):
        data: bytes|None = None;
        with open(file_path, mode='rb') as file: # b is important -> binary
            data = file.read()
            file.close();
        return data;

    @staticmethod
    def read_text(file_path: str, encoding: str = 'utf-8'):
        data: str|None = None;
        with open(file_path, mode='r', encoding=encoding) as file: # b is important -> binary
            data = file.read()
            file.close();
        return data;

    @staticmethod
    def read_json_as_dict(file_path: str, encoding: str = 'utf-8'):
        data: str = IOUtil.read_text(file_path, encoding);
        obj = json.loads(data);
        return obj;


class Base64Util:
    @staticmethod
    def encode(data: bytes):
        encoded_string = base64.b64encode(data)
        base64_string = encoded_string.decode('ascii')
        return base64_string

    @staticmethod
    def decode(string: str|None):
        if not string:
            return bytes(0);
        data = string.encode('ascii')
        decode_data = base64.b64decode(data);
        return decode_data;