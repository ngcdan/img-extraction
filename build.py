import PyInstaller.__main__
import sys
import os
import shutil
import platform
import glob
import plistlib

def resource_path(relative_path):
    """Lấy đường dẫn tuyệt đối đến tài nguyên"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def clean_build():
    """Dọn dẹp các thư mục và file build cũ"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                # Thử xóa từng file trong thư mục trước
                for root, dirs, files in os.walk(dir_name, topdown=False):
                    for name in files:
                        try:
                            os.remove(os.path.join(root, name))
                        except Exception as e:
                            print(f"Không thể xóa file {name}: {e}")
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except Exception as e:
                            print(f"Không thể xóa thư mục {name}: {e}")

                # Sau đó xóa thư mục gốc
                os.rmdir(dir_name)
                print(f"Đã xóa thư mục: {dir_name}")
            except Exception as e:
                print(f"Cảnh báo: Không thể xóa hoàn toàn thư mục {dir_name}: {e}")
                # Tiếp tục build ngay cả khi không xóa được hoàn toàn

    for file_pattern in files_to_clean:
        try:
            for file_path in glob.glob(file_pattern):
                try:
                    os.remove(file_path)
                    print(f"Đã xóa file: {file_path}")
                except Exception as e:
                    print(f"Không thể xóa file {file_path}: {e}")
        except Exception as e:
            print(f"Lỗi khi tìm file {file_pattern}: {e}")

def get_additional_files():
    """Danh sách các file và thư mục cần thêm vào package"""
    additional_files = [
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env', '.'),
        ('service-account-key.json', '.'),
        ('cookies', 'cookies'),  # Thêm thư mục cookies
        ('downloads', 'downloads'),  # Thêm thư mục downloads
    ]
    return additional_files

def get_hidden_imports():
    """Danh sách các module cần import"""
    return [
        'flask',
        'flask_cors',
        'selenium',
        'pyodbc',
        'socketio',
        'engineio',
        'eventlet',
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'pdfminer',
        'google.oauth2',
        'googleapiclient',
        'openpyxl',
        'tenacity',
        'webdriver_manager',
        'requests'
    ]

def build_windows():
    """Build package cho Windows"""
    print("Đang build cho Windows...")
    clean_build()

    separator = ';'
    current_dir = os.path.abspath(".")
    app_name = "ImgExtraction-windows"

    params = [
        'app.py',
        f'--name={app_name}',
        '--onefile',  # Build thành 1 file exe duy nhất
        '--noconsole',  # Không hiển thị console
        '--clean',
        '--noconfirm',
    ]

    # Thêm icon nếu có
    icon_path = os.path.join(current_dir, 'static', 'favicon.ico')
    if os.path.exists(icon_path):
        params.append(f'--icon={icon_path}')

    # Thêm các file bổ sung
    for src, dst in get_additional_files():
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src_path}{separator}{dst}')

    # Thêm hidden imports
    for imp in get_hidden_imports():
        params.append(f'--hidden-import={imp}')

    # Thêm các options đặc biệt cho Windows
    params.extend([
        '--collect-submodules=selenium',
        '--collect-submodules=webdriver_manager',
        '--collect-all=webdriver_manager',
        '--collect-all=selenium'
    ])

    PyInstaller.__main__.run(params)
    print(f"Đã build xong file exe tại dist/{app_name}.exe")

def build_macos():
    """Build package cho macOS"""
    print("Đang build cho macOS...")
    clean_build()

    separator = ':'
    current_dir = os.path.abspath(".")
    app_name = "ImgExtraction"

    params = [
        'app.py',
        f'--name={app_name}',
        '--onefile',  # Build thành 1 file thực thi duy nhất
        '--noconsole',  # Không hiển thị terminal
        '--clean',
        '--noconfirm',
    ]

    # Thêm icon nếu có
    icon_path = os.path.join(current_dir, 'static', 'favicon.icns')
    if os.path.exists(icon_path):
        params.append(f'--icon={icon_path}')

    # Thêm các file bổ sung
    for src, dst in get_additional_files():
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src_path}{separator}{dst}')

    # Thêm hidden imports
    for imp in get_hidden_imports():
        params.append(f'--hidden-import={imp}')

    # Thêm các options đặc biệt cho macOS
    params.extend([
        '--collect-submodules=selenium',
        '--collect-submodules=webdriver_manager',
        '--collect-all=webdriver_manager',
        '--collect-all=selenium'
    ])

    PyInstaller.__main__.run(params)
    print(f"Đã build xong file thực thi tại dist/{app_name}")

def main():
    """Hàm chính để chạy build"""
    current_os = platform.system().lower()

    if len(sys.argv) > 1:
        target = sys.argv[1].lower()
        if target == 'windows':
            build_windows()
        elif target == 'macos':
            build_macos()
        else:
            print("Lỗi: Vui lòng chỉ định 'windows' hoặc 'macos'. Ví dụ: python build.py windows")
            sys.exit(1)
    else:
        if 'windows' in current_os:
            build_windows()
        elif 'darwin' in current_os:
            build_macos()
        else:
            print("Hệ điều hành không được hỗ trợ tự động. Vui lòng chỉ định 'windows' hoặc 'macos'.")
            sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Lỗi trong quá trình build: {str(e)}")
        sys.exit(1)
