import PyInstaller.__main__
import sys
import os
import shutil
import platform
import glob

def resource_path(relative_path):
    """Lấy đường dẫn tuyệt đối đến tài nguyên, hoạt động cho cả dev và PyInstaller"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def clean_build():
    """Dọn dẹp các thư mục và file build cũ"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Đã xóa thư mục: {dir_name}")

    for file_pattern in files_to_clean:
        for file_path in glob.glob(file_pattern):
            os.remove(file_path)
            print(f"Đã xóa file: {file_path}")

def get_additional_files():
    """Danh sách các file và thư mục cần thêm vào package"""
    additional_files = [
        ('templates', 'templates'),  # Thư mục HTML templates
        ('static', 'static'),        # Thư mục tài nguyên tĩnh (CSS, JS)
        ('.env', '.'),               # File cấu hình môi trường
        ('service-account-key.json', '.'),  # File credentials Google Sheets (nếu có)
    ]
    return additional_files

def build_windows():
    """Build package cho Windows"""
    print("Đang build cho Windows...")
    clean_build()

    separator = ';'  # Dấu phân cách cho Windows
    current_dir = os.path.abspath(".")
    app_name = "ImgExtraction-windows"

    # Danh sách tham số PyInstaller
    params = [
        'app.py',
        f'--name={app_name}',
        '--onefile',  # Đóng gói thành một file duy nhất
        '--windowed',  # Không hiển thị console khi chạy
        '--clean',
        '--noconfirm',
    ]

    # Thêm các file bổ sung
    for src, dst in get_additional_files():
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src_path}{separator}{dst}')
        else:
            print(f"Cảnh báo: Không tìm thấy {src_path}, bỏ qua...")

    # Thêm hidden imports
    hidden_imports = [
        'pyodbc',
        'socketio',
        'engineio',
        'eventlet',
    ]
    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    # Chạy PyInstaller
    PyInstaller.__main__.run(params)
    print(f"Đã build xong package Windows tại dist/{app_name}.exe")

def build_macos():
    print("Đang build cho macOS...")
    clean_build()

    separator = ':'  # Dấu phân cách cho macOS
    current_dir = os.path.abspath(".")
    app_name = "ImgExtraction-macos"

    params = [
        'app.py',
        f'--name={app_name}',
        '--onefile',
        '--clean',
        '--noconfirm',
    ]

    for src, dst in get_additional_files():
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src_path}{separator}{dst}')
        else:
            print(f"Cảnh báo: Không tìm thấy {src_path}, bỏ qua...")

    # Thêm hidden imports, bao gồm eventlet đầy đủ
    hidden_imports = [
        'pyodbc',
        'socketio',
        'engineio',
        'eventlet',
        'eventlet.hubs.epolls',  # Thêm các module phụ của eventlet
        'eventlet.hubs.kqueue',  # Hỗ trợ macOS
        'eventlet.hubs.selects',
    ]
    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    PyInstaller.__main__.run(params)

    app_path = os.path.join('dist', app_name)
    if os.path.exists(app_path):
        os.chmod(app_path, 0o755)
        print(f"Đã cập nhật quyền thực thi cho {app_path}")

    print(f"Đã build xong package macOS tại dist/{app_name}")

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
        elif 'darwin' in current_os:  # Darwin là tên kernel của macOS
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