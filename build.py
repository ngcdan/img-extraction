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
        'templates',
        'static',
        'cookies',
        'downloads',
        '.env',
        'service-account-key.json',
        'test_batch_process.py',
        'receipt_fetcher.py',
        'extract_info.py',
        'google_sheet_utils.py',
        'google_drive_utils.py',
        'utils.py',
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

    app_name = "CustomsPDFProcessor"
    separator = ';'
    data_files = collect_all_files()

    params = [
        'test_batch_process.py',
        f'--name={app_name}',
        '--onefile',
        '--noconsole',  # Chuyển sang GUI mode
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
        'selenium',
        'pyodbc',
        'google.oauth2',
        'googleapiclient',
        'openpyxl',
        'tenacity',
        'webdriver_manager',
        'requests',
        'threading',
        'win32com',
        'win32api',
    ]

    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    return params, app_name

def build_macos():
    """Build ứng dụng cho macOS"""
    print("Đang build cho macOS...")
    clean_build()

    app_name = "CustomsPDFProcessor"
    separator = ':'
    data_files = collect_all_files()

    params = [
        'test_batch_process.py',
        f'--name={app_name}',
        '--onefile',
        '--noconsole',  # Chuyển sang GUI mode
        '--clean',
        '--noconfirm',
        '--windowed',  # Thêm flag cho macOS app
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
        'selenium',
        'pyodbc',
        'google.oauth2',
        'googleapiclient',
        'openpyxl',
        'tenacity',
        'webdriver_manager',
        'requests',
        'threading',
        'AppKit',
        'Foundation',
    ]

    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

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
Hướng dẫn sử dụng Customs PDF Processor:

1. Đặt các file PDF cần xử lý vào thư mục 'customs' trên Desktop
2. Chạy ứng dụng CustomsPDFProcessor
3. Ứng dụng sẽ tự động xử lý tất cả file PDF trong thư mục

Lưu ý:
- Thư mục 'customs' sẽ được tự động tạo trên Desktop nếu chưa tồn tại
- Kết quả xử lý sẽ được hiển thị trên màn hình
- Nhấn Enter để đóng ứng dụng sau khi xử lý xong
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
