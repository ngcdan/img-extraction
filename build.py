import PyInstaller.__main__
import sys
import os
import shutil
import platform

def get_odbc_driver_path():
    """Lấy đường dẫn tới ODBC driver trong virtual environment"""
    if platform.system() == 'Windows':
        return os.path.join(os.environ['VIRTUAL_ENV'], 'Lib', 'site-packages', 'pyodbc', 'drivers')
    else:
        return os.path.join(os.environ['VIRTUAL_ENV'], 'lib', 'python3.8', 'site-packages', 'pyodbc', 'drivers')

def clean_build():
    """Dọn dẹp các thư mục build cũ"""
    dirs_to_clean = ['build', 'dist']
    files_to_clean = ['*.spec']

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)

    for file_pattern in files_to_clean:
        import glob
        for file_path in glob.glob(file_pattern):
            os.remove(file_path)

def build_app():
    """Build ứng dụng với PyInstaller"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    separator = ';' if platform.system() == 'Windows' else ':'

    # Danh sách các file và thư mục cần được bundle
    additional_files = [
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env', '.'),
        ('drivers', 'drivers'),  # Thêm thư mục drivers
    ]

    # Thêm ODBC driver vào bundle
    odbc_path = get_odbc_driver_path()
    if os.path.exists(odbc_path):
        additional_files.append((odbc_path, 'drivers'))

    # Các tham số PyInstaller
    params = [
        'app.py',
        '--name=ImgExtraction',
        '--onefile',
        '--clean',
        '--noconfirm',
    ]

    # Thêm data files
    for src, dst in additional_files:
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src}{separator}{dst}')

    # Thêm các hidden imports
    hidden_imports = [
        'pyodbc',
        'unixodbc',  # Cho macOS/Linux
    ]

    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    # Chạy PyInstaller
    PyInstaller.__main__.run(params)

def post_build():
    """Xử lý sau khi build"""
    if platform.system() == 'Darwin':  # macOS
        app_path = os.path.join('dist', 'ImgExtraction')
        if os.path.exists(app_path):
            os.chmod(app_path, 0o755)
            print("Đã cập nhật quyền thực thi cho file binary")

if __name__ == '__main__':
    try:
        print(f"Đang build cho hệ điều hành: {platform.system()}")
        clean_build()
        build_app()
        post_build()
        print("Build thành công!")
    except Exception as e:
        print(f"Lỗi trong quá trình build: {str(e)}")
        sys.exit(1)
