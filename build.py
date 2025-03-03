import PyInstaller.__main__
import sys
import os

# Đường dẫn tới thư mục hiện tại
current_dir = os.path.dirname(os.path.abspath(__file__))

# Xác định separator dựa trên hệ điều hành
separator = ';' if sys.platform.startswith('win') else ':'

# Danh sách các file và thư mục cần được bundle
additional_files = [
    ('templates', 'templates'),
    ('static', 'static'),
    ('.env', '.'),
    ('service-account-key.json', '.'),
]

# Tạo danh sách các tham số cho PyInstaller
params = [
    'app.py',  # Main script
    '--name=ImgExtraction',  # Tên file exe
    '--onefile',  # Đóng gói thành một file duy nhất
    '--noconsole',  # Không hiển thị console khi chạy
    f'--add-data=templates{separator}templates',  # Bundle thư mục templates
    f'--add-data=static{separator}static',  # Bundle thư mục static
    '--hidden-import=engineio.async_drivers.threading',
    '--hidden-import=flask_socketio',
    '--hidden-import=eventlet.hubs.epolls',
    '--hidden-import=eventlet.hubs.kqueue',
    '--hidden-import=eventlet.hubs.selects',
    '--hidden-import=dns.dnssec',
    '--hidden-import=dns.e164',
    '--hidden-import=dns.hash',
    '--hidden-import=dns.namedict',
    '--hidden-import=dns.tsigkeyring',
    '--hidden-import=dns.update',
    '--hidden-import=dns.version',
    '--hidden-import=dns.zone',
]

# Thêm icon chỉ khi đang chạy trên Windows
if sys.platform.startswith('win'):
    icon_path = os.path.join(current_dir, 'static', 'favicon.ico')
    if os.path.exists(icon_path):
        params.append(f'--icon={icon_path}')

# Thêm các file và thư mục bổ sung
for src, dst in additional_files:
    src_path = os.path.join(current_dir, src)
    if os.path.exists(src_path):
        params.append(f'--add-data={src}{separator}{dst}')

# Chạy PyInstaller
PyInstaller.__main__.run(params)
