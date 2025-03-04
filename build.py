import PyInstaller.__main__
import sys
import os
import shutil
import platform
import glob
import plistlib

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
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env', '.'),
        ('service-account-key.json', '.'),
    ]
    return additional_files

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
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
    ]

    for src, dst in get_additional_files():
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src_path}{separator}{dst}')
        else:
            print(f"Cảnh báo: Không tìm thấy {src_path}, bỏ qua...")

    hidden_imports = [
        'pyodbc',
        'socketio',
        'engineio',
        'eventlet',
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
    ]
    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    PyInstaller.__main__.run(params)
    print(f"Đã build xong package Windows tại dist/{app_name}.exe")

def build_macos():
    """Build package cho macOS thành file .app"""
    print("Đang build cho macOS...")
    clean_build()

    separator = ':'
    current_dir = os.path.abspath(".")
    app_name = "ImgExtraction"
    bundle_identifier = "com.yourcompany.imgextraction"  # Thay đổi nếu cần

    # Build với --onedir để tạo thư mục chứa ứng dụng
    params = [
        'app.py',
        f'--name={app_name}',
        '--onedir',  # Tạo thư mục thay vì file đơn
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
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
    ]
    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    # Chạy PyInstaller để tạo thư mục
    PyInstaller.__main__.run(params)

    # Tạo cấu trúc .app
    app_dir = os.path.join('dist', f"{app_name}.app")
    contents_dir = os.path.join(app_dir, 'Contents')
    macos_dir = os.path.join(contents_dir, 'MacOS')
    resources_dir = os.path.join(contents_dir, 'Resources')

    # Tạo các thư mục cần thiết
    for directory in [contents_dir, macos_dir, resources_dir]:
        os.makedirs(directory, exist_ok=True)

    # Di chuyển nội dung từ dist/ImgExtraction sang Contents/MacOS
    src_dir = os.path.join('dist', app_name)
    for item in os.listdir(src_dir):
        shutil.move(os.path.join(src_dir, item), macos_dir)

    # Xóa thư mục dist/ImgExtraction cũ
    shutil.rmtree(src_dir)

    # Tạo file Info.plist
    plist_data = {
        'CFBundleName': app_name,
        'CFBundleIdentifier': bundle_identifier,
        'CFBundleExecutable': app_name,
        'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'LSMinimumSystemVersion': '10.13',  # Phiên bản macOS tối thiểu
    }
    plist_file = os.path.join(contents_dir, 'Info.plist')
    with open(plist_file, 'wb') as f:
        plistlib.dump(plist_data, f)

    # Đặt quyền thực thi cho file thực thi
    executable_path = os.path.join(macos_dir, app_name)
    if os.path.exists(executable_path):
        os.chmod(executable_path, 0o755)
        print(f"Đã cập nhật quyền thực thi cho {executable_path}")

    print(f"Đã build xong package macOS tại dist/{app_name}.app")

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