import PyInstaller.__main__
import sys
import os
import shutil
import platform

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
    # Đường dẫn tới thư mục hiện tại
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Xác định separator dựa trên hệ điều hành
    separator = ';' if platform.system() == 'Windows' else ':'

    # Danh sách các file và thư mục cần được bundle
    additional_files = [
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env', '.'),
        ('service-account-key.json', '.'),
    ]

    # Tạo danh sách các tham số cho PyInstaller
    params = [
        'app.py',                    # Main script
        '--name=ImgExtraction',      # Tên file exe/binary
        '--onefile',                 # Đóng gói thành một file duy nhất
        '--clean',                   # Xóa cache trước khi build
        '--noconfirm',               # Không hỏi xác nhận khi xóa
    ]

    # Thêm console tùy theo môi trường
    if platform.system() == 'Windows':
        params.append('--noconsole')  # Ẩn console trên Windows

    # Thêm data files
    for src, dst in additional_files:
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src}{separator}{dst}')

    # Thêm icon cho Windows
    if platform.system() == 'Windows':
        icon_path = os.path.join(current_dir, 'static', 'favicon.ico')
        if os.path.exists(icon_path):
            params.append(f'--icon={icon_path}')

    # Thêm các hidden imports
    hidden_imports = [
        'engineio.async_drivers.threading',
        'flask_socketio',
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'dns.dnssec',
        'dns.e164',
        'dns.hash',
        'dns.namedict',
        'dns.tsigkeyring',
        'dns.update',
        'dns.version',
        'dns.zone',
        'rapidfuzz',
        'rapidfuzz.fuzz',
        'rapidfuzz.string_metric',
        'rapidfuzz.process',
    ]

    for imp in hidden_imports:
        params.append(f'--hidden-import={imp}')

    # Thêm các collect submodules
    params.extend([
        '--collect-submodules=rapidfuzz',
        '--exclude-module=rapidfuzz.__pyinstaller',
    ])

    # Chạy PyInstaller
    PyInstaller.__main__.run(params)

if __name__ == '__main__':
    try:
        print(f"Đang build cho hệ điều hành: {platform.system()}")
        clean_build()
        build_app()
        print("Build thành công!")
    except Exception as e:
        print(f"Lỗi trong quá trình build: {str(e)}")
        sys.exit(1)
