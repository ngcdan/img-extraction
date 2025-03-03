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
    current_dir = os.path.dirname(os.path.abspath(__file__))
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
        '--clean',                   # Xóa cache trước khi build
        '--noconfirm',               # Không hỏi xác nhận khi xóa
    ]

    # Cấu hình theo hệ điều hành
    if platform.system() == 'Windows':
        params.extend([
            '--onefile',             # Đóng gói thành một file duy nhất cho Windows
            '--noconsole',           # Ẩn console trên Windows
            '--win-private-assemblies',
        ])
        # Thêm icon cho Windows
        icon_path = os.path.join(current_dir, 'static', 'favicon.ico')
        if os.path.exists(icon_path):
            params.append(f'--icon={icon_path}')
    else:  # macOS
        params.extend([
            '--onefile',             # Đóng gói thành một file duy nhất cho macOS
            '--windowed',            # Tạo app bundle cho macOS
        ])
        # Thêm icon cho macOS
        icon_path = os.path.join(current_dir, 'static', 'favicon.icns')
        if os.path.exists(icon_path):
            params.append(f'--icon={icon_path}')

    # Thêm data files
    for src, dst in additional_files:
        src_path = os.path.join(current_dir, src)
        if os.path.exists(src_path):
            params.append(f'--add-data={src}{separator}{dst}')

    # Thêm các hidden imports cho Flask và dependencies
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
