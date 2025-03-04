import PyInstaller.__main__
import sys
import os
import shutil
import platform
import glob

def clean_build():
    """Dọn dẹp các thư mục và file build cũ"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"Đã xóa thư mục: {dir_name}")
            except Exception as e:
                print(f"Cảnh báo: Không thể xóa thư mục {dir_name}: {e}")

    for file_pattern in files_to_clean:
        for file_path in glob.glob(file_pattern):
            try:
                os.remove(file_path)
                print(f"Đã xóa file: {file_path}")
            except Exception as e:
                print(f"Không thể xóa file {file_path}: {e}")

def collect_all_files():
    """Thu thập tất cả các file và thư mục cần thiết"""
    items_to_include = [
        'venv',
        'templates',
        'static',
        'cookies',
        'downloads',
        '.env',
        'service-account-key.json',
        'app.py',
        'utils.py',
        'receipt_fetcher.py',
        'extract_info.py',
        'google_sheet_utils.py',
        'google_drive_utils.py',
        'requirements.txt'
    ]

    current_dir = os.path.abspath(".")
    data_files = []

    for item in items_to_include:
        item_path = os.path.join(current_dir, item)
        if os.path.exists(item_path):
            if os.path.isdir(item_path):
                data_files.append((item, item_path))
            else:
                data_files.append((item, item_path))

    return data_files

def build_windows():
    """Build ứng dụng cho Windows"""
    print("Đang build cho Windows...")
    clean_build()

    app_name = "ImgExtraction-windows"
    separator = ';'
    data_files = collect_all_files()

    params = [
        'app.py',
        f'--name={app_name}',
        '--onefile',
        '--noconsole',
        '--clean',
        '--noconfirm',
    ]

    # Thêm icon cho Windows
    icon_path = os.path.join('static', 'favicon.ico')
    if os.path.exists(icon_path):
        params.append(f'--icon={icon_path}')

    # Thêm tất cả file và thư mục
    for dest, src in data_files:
        params.append(f'--add-data={src}{separator}{dest}')

    # Windows-specific imports
    hidden_imports = [
        'flask',
        'flask_cors',
        'flask_socketio',
        'selenium',
        'pyodbc',
        'socketio',
        'engineio',
        'eventlet',
        'dns',
        'dns.resolver',
        'pdfminer',
        'google.oauth2',
        'googleapiclient',
        'openpyxl',
        'tenacity',
        'webdriver_manager',
        'requests',
        'threading',
        'win32com',  # Windows specific
        'win32api',  # Windows specific
    ]

    hidden_imports.extend([
        'engineio.async_drivers.threading',
        'engineio.async_drivers.eventlet',
        'dns.resolver',
        'dns.exception',
        'dns.rdatatype',
        'dns.name',
        'dns.message',
        'dns.query',
        'dns.rdata',
        'dns.rdataclass',
        'dns.rdtypes.*',
        'dns.rdtypes.ANY.*',
        'dns.rdtypes.IN.*'
    ])

    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    params.extend([
        '--collect-submodules=selenium',
        '--collect-submodules=webdriver_manager',
        '--collect-all=webdriver_manager',
        '--collect-all=selenium',
        '--hidden-import=engineio.async_drivers.threading',
        '--hidden-import=engineio.async_drivers.eventlet',
        '--hidden-import=dns',
        '--hidden-import=dns.resolver',
        '--collect-all=dns',
        '--collect-all=engineio',
        '--collect-all=socketio'
    ])

    return params, app_name

def build_macos():
    """Build ứng dụng cho macOS"""
    print("Đang build cho macOS...")
    clean_build()

    app_name = "ImgExtraction"
    separator = ':'
    data_files = collect_all_files()

    params = [
        'app.py',
        f'--name={app_name}',
        '--onefile',
        '--noconsole',
        '--clean',
        '--noconfirm',
    ]

    # Thêm icon cho macOS
    icon_path = os.path.join('static', 'favicon.icns')
    if os.path.exists(icon_path):
        params.append(f'--icon={icon_path}')

    # Thêm tất cả file và thư mục
    for dest, src in data_files:
        params.append(f'--add-data={src}{separator}{dest}')

    # macOS-specific imports
    hidden_imports = [
        'flask',
        'flask_cors',
        'flask_socketio',
        'selenium',
        'pyodbc',
        'socketio',
        'engineio',
        'eventlet',
        'dns',
        'dns.resolver',
        'pdfminer',
        'google.oauth2',
        'googleapiclient',
        'openpyxl',
        'tenacity',
        'webdriver_manager',
        'requests',
        'threading',
        'AppKit',  # macOS specific
        'Foundation',  # macOS specific
    ]

    hidden_imports.extend([
        'engineio.async_drivers.threading',
        'engineio.async_drivers.eventlet',
        'dns.resolver',
        'dns.exception',
        'dns.rdatatype',
        'dns.name',
        'dns.message',
        'dns.query',
        'dns.rdata',
        'dns.rdataclass',
        'dns.rdtypes.*',
        'dns.rdtypes.ANY.*',
        'dns.rdtypes.IN.*'
    ])

    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    params.extend([
        '--collect-submodules=selenium',
        '--collect-submodules=webdriver_manager',
        '--collect-all=webdriver_manager',
        '--collect-all=selenium',
        '--hidden-import=engineio.async_drivers.threading',
        '--hidden-import=engineio.async_drivers.eventlet',
        '--hidden-import=dns',
        '--hidden-import=dns.resolver',
        '--collect-all=dns',
        '--collect-all=engineio',
        '--collect-all=socketio'
    ])

    return params, app_name

def build_app():
    """Build ứng dụng dựa trên hệ điều hành"""
    system = platform.system().lower()

    if system == "windows":
        params, app_name = build_windows()
    elif system == "darwin":  # macOS
        params, app_name = build_macos()
    else:
        print("Hệ điều hành không được hỗ trợ")
        sys.exit(1)

    try:
        print("\nĐang tiến hành build...")
        PyInstaller.__main__.run(params)
        print(f"\nBuild thành công! File thực thi nằm tại: dist/{app_name}")

        print("\nĐang copy các file và thư mục bổ sung...")
        dist_dir = os.path.join('dist')
        data_files = collect_all_files()

        for dest, src in data_files:
            dest_path = os.path.join(dist_dir, dest)
            if os.path.isdir(src):
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(src, dest_path)
            else:
                shutil.copy2(src, dist_dir)

        print("\nĐã copy xong các file bổ sung!")

        # Tạo file README với hướng dẫn
        readme_content = """
Hướng dẫn sử dụng:

1. Đảm bảo đã cài đặt Google Chrome
2. Chạy file thực thi (ImgExtraction hoặc ImgExtraction-windows.exe)
3. Trình duyệt sẽ tự động mở tại địa chỉ http://localhost:8080

Lưu ý:
- Không xóa bất kỳ thư mục nào trong package
- Đảm bảo các thư mục cookies và downloads có quyền ghi
- Nếu gặp lỗi, kiểm tra file .env và service-account-key.json
        """

        with open(os.path.join(dist_dir, 'README.txt'), 'w', encoding='utf-8') as f:
            f.write(readme_content)

        print(f"\nỨng dụng đã được build thành công tại thư mục 'dist'")

    except Exception as e:
        print(f"\nLỗi trong quá trình build: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        if len(sys.argv) > 1:
            target_os = sys.argv[1].lower()
            if target_os not in ['windows', 'macos']:
                print("Sử dụng: python build.py [windows|macos]")
                sys.exit(1)

            if target_os == 'windows' and platform.system().lower() != 'windows':
                print("Không thể build cho Windows trên hệ điều hành khác")
                sys.exit(1)
            elif target_os == 'macos' and platform.system().lower() != 'darwin':
                print("Không thể build cho macOS trên hệ điều hành khác")
                sys.exit(1)

        build_app()
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        sys.exit(1)
