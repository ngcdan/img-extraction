from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
import io
import os
import sys
import platform

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)



# Cấu hình chung
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'driver-service-account.json'

# Định nghĩa các ROOT_FOLDER_ID cho từng mục đích sử dụng
DRIVE_FOLDERS = {
    'CUSTOMS': '1FxafcnGt45hEpE5UHrjbQD4yjrEdmTGm',  # Folder gốc cho tờ khai hải quan
    'CAPTCHAS': '1hM0qRY1NkyuXloxHMnCsqe_DD2__D-IW'  # Folder gốc cho captchas
}

class DriveService:
    _instance = None
    _service = None
    _root_folder_id = None

    @classmethod
    def get_instance(cls):
        """Singleton pattern để đảm bảo chỉ tạo một instance của Drive service"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Khởi tạo Drive service"""
        if self._service is None:
            try:
                # Clear cache when initializing service
                DriveCache.get_instance().clear()

                # Thử load file gốc trong development
                cred_path = 'driver-service-account.json'
                if not os.path.exists(cred_path):
                    # Trong production, load file đã được rename
                    cred_path = get_resource_path('data1.bin')

                if not os.path.exists(cred_path):
                    raise FileNotFoundError(f"Không tìm thấy file credentials tại {cred_path}")

                credentials = service_account.Credentials.from_service_account_file(
                    cred_path, scopes=SCOPES)
                self._service = build('drive', 'v3', credentials=credentials)
            except Exception as e:
                raise Exception(f"Không thể khởi tạo Drive service: {str(e)}")

    @property
    def service(self):
        """Trả về Drive service instance"""
        return self._service

    @property
    def root_folder_id(self):
        """Trả về root folder ID"""
        return self._root_folder_id

    @root_folder_id.setter
    def root_folder_id(self, value):
        """Set root folder ID"""
        self._root_folder_id = value

    def get_root_folder_id(self, folder_type='CUSTOMS'):
        """Trả về ID folder gốc theo loại"""
        folder_id = DRIVE_FOLDERS.get(folder_type)
        self.root_folder_id = folder_id  # Cập nhật root_folder_id
        return folder_id

def create_drive_folder(service, parent_id, folder_name):
    """Tạo folder trong Google Drive, trả về folder ID"""
    try:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id] if parent_id else []
        }
        file = service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')
    except Exception as e:
        print(f"Lỗi khi tạo folder {folder_name}: {e}")
        return None

class DriveCache:
    _instance = None

    def __init__(self):
        self.folder_cache = {}  # Cache folder IDs: {parent_id-folder_name: folder_id}
        self.file_cache = {}    # Cache file existence: {parent_id-filename: (exists, file_id)}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def clear(self):
        """Clear all caches"""
        self.folder_cache.clear()
        self.file_cache.clear()

def get_or_create_folder(service, parent_id, folder_name):
    """Tìm folder theo tên hoặc tạo mới nếu chưa tồn tại"""
    try:
        cache = DriveCache.get_instance()
        cache_key = f"{parent_id}-{folder_name}"

        # Check cache first
        if cache_key in cache.folder_cache:
            return cache.folder_cache[cache_key]

        query = [
            f"'{parent_id}' in parents",
            "mimeType = 'application/vnd.google-apps.folder'",
            "trashed = false"
        ]

        # Lấy tất cả folders trong parent_id
        results = service.files().list(
            q=" and ".join(query),
            spaces='drive',
            fields='files(id, name)',
            pageSize=1000  # Tăng pageSize để lấy nhiều kết quả hơn
        ).execute()

        # Cache tất cả folders tìm được
        for folder in results.get('files', []):
            folder_cache_key = f"{parent_id}-{folder['name']}"
            cache.folder_cache[folder_cache_key] = folder['id']

        # Kiểm tra lại cache sau khi đã cập nhật
        if cache_key in cache.folder_cache:
            return cache.folder_cache[cache_key]

        # Nếu không tìm thấy, tạo mới folder
        folder_id = create_drive_folder(service, parent_id, folder_name)
        if folder_id:
            cache.folder_cache[cache_key] = folder_id

        return folder_id
    except Exception as e:
        print(f"Lỗi khi tìm/tạo folder: {e}")
        return None

def check_file_exists(service, parent_id, filename):
    """Kiểm tra file đã tồn tại trong folder chưa"""
    try:
        cache = DriveCache.get_instance()
        cache_key = f"{parent_id}-{filename}"

        # Check cache first
        if cache_key in cache.file_cache:
            return cache.file_cache[cache_key]

        query = [
            f"'{parent_id}' in parents",
            "trashed = false"
        ]

        # Lấy tất cả files trong parent_id
        results = service.files().list(
            q=" and ".join(query),
            spaces='drive',
            fields='files(id, name)',
            pageSize=1000  # Tăng pageSize để lấy nhiều kết quả hơn
        ).execute()

        # Cache tất cả files tìm được
        for file in results.get('files', []):
            file_cache_key = f"{parent_id}-{file['name']}"
            cache.file_cache[file_cache_key] = (True, file['id'])

        # Kiểm tra lại cache sau khi đã cập nhật
        if cache_key in cache.file_cache:
            return cache.file_cache[cache_key]

        # Nếu không tìm thấy file, cache kết quả negative
        cache.file_cache[cache_key] = (False, None)
        return (False, None)

    except Exception as e:
        print(f"Lỗi khi kiểm tra file {filename}: {str(e)}")
        return False, None

def upload_file_to_drive(file_content, filename, parent_folder_date, mimetype='application/pdf', folder_type='CUSTOMS'):
    """
    Upload file lên Google Drive với cấu trúc thư mục ngày

    Args:
        file_content: Nội dung file dạng bytes
        filename: Tên file
        parent_folder_date: Tên folder ngày (định dạng DDMMYYYY)
        mimetype: Loại file (mặc định là PDF)
        folder_type: Loại folder gốc (mặc định là CUSTOMS)
    """
    try:
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_id = drive_instance.get_root_folder_id(folder_type)

        if not root_id:
            raise Exception(f"Không tìm thấy folder gốc cho loại: {folder_type}")

        # Nếu là CAPTCHAS, tạo folder "captchas"
        if folder_type == 'CAPTCHAS':
            captchas_folder_id = get_or_create_folder(service, root_id, 'captchas')
            if not captchas_folder_id:
                raise Exception("Không thể tạo/tìm folder captchas")

            file_metadata = {
                'name': filename,
                'parents': [captchas_folder_id]
            }

            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mimetype,
                resumable=True
            )

            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()

            return {
                'success': True,
                'file_id': file.get('id'),
                'web_view_link': file.get('webViewLink'),
                'file_path': f"captchas/{filename}"
            }

        # Xử lý cho CUSTOMS - lưu trực tiếp vào folder ngày
        date_folder_id = get_or_create_folder(service, root_id, parent_folder_date)
        if not date_folder_id:
            raise Exception("Không thể tạo/tìm folder ngày")

        file_metadata = {
            'name': filename,
            'parents': [date_folder_id]
        }

        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype=mimetype,
            resumable=True
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        file_path = f"{parent_folder_date}/{filename}"

        return {
            'success': True,
            'file_id': file.get('id'),
            'web_view_link': file.get('webViewLink'),
            'file_path': file_path
        }

    except Exception as e:
        error_msg = f"Lỗi khi upload file lên Drive: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'error': error_msg
        }

def get_next_captcha_index_from_drive(service, root_folder_id):
    """Lấy index tiếp theo cho file captcha từ Google Drive"""
    try:
        query = [
            f"'{root_folder_id}' in parents",
            "name contains 'captcha_'",
            "name contains '.png'",
            "trashed = false"
        ]

        results = service.files().list(
            q=" and ".join(query),
            spaces='drive',
            fields='files(name)',
            orderBy='name desc',
            pageSize=1000
        ).execute()

        files = results.get('files', [])
        if not files:
            return 0

        indices = []
        for file in files:
            try:
                index = int(file['name'].split('_')[1].split('.')[0])
                indices.append(index)
            except (IndexError, ValueError):
                continue

        return max(indices) + 1 if indices else 0

    except Exception as e:
        print(f"Lỗi khi lấy index captcha: {e}")
        return 0

def upload_captcha_to_drive(captcha_content, filename=None, mimetype='image/png'):
    """
    Upload captcha lên Google Drive với tên file tự động tăng

    Args:
        captcha_content: Nội dung file captcha dạng bytes
        filename: Tên file (nếu None sẽ tự động tạo)
        mimetype: Loại file (mặc định là image/png)
    """
    try:
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_id = drive_instance.get_root_folder_id('CAPTCHAS')

        if not root_id:
            raise Exception("Không tìm thấy folder gốc cho captchas")

        if filename is None:
            next_index = get_next_captcha_index_from_drive(service, root_id)
            filename = f"captcha_{next_index:03d}.png"

        file_metadata = {
            'name': filename,
            'parents': [root_id]
        }

        media = MediaIoBaseUpload(
            io.BytesIO(captcha_content),
            mimetype=mimetype,
            resumable=True
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        return {
            'success': True,
            'file_id': file.get('id'),
            'web_view_link': file.get('webViewLink'),
            'filename': filename
        }

    except Exception as e:
        error_msg = f"Lỗi khi upload captcha lên Drive: {str(e)}"
        print(error_msg)
        return {
            'success': False,
            'error': error_msg
        }

def append_to_labels_file(filename, label):
    """
    Append captcha filename và label vào file labels.txt trên Drive

    Args:
        filename: Tên file captcha (e.g., 'captcha_123.png')
        label: Label của captcha
    """
    try:
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_id = drive_instance.get_root_folder_id('CAPTCHAS')

        if not root_id:
            raise Exception("Không tìm thấy folder CAPTCHAS")

        # Tìm file labels.txt
        query = [
            f"'{root_id}' in parents",
            "name = 'labels.txt'",
            "trashed = false"
        ]

        results = service.files().list(
            q=" and ".join(query),
            spaces='drive',
            fields='files(id)',
        ).execute()

        files = results.get('files', [])

        if not files:
            # Tạo file labels.txt nếu chưa tồn tại
            file_metadata = {
                'name': 'labels.txt',
                'parents': [root_id],
                'mimeType': 'text/plain'
            }
            labels_file = service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            labels_file_id = labels_file['id']
        else:
            labels_file_id = files[0]['id']

        # Đọc nội dung hiện tại
        content = ""
        try:
            request = service.files().get_media(fileId=labels_file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            content = fh.getvalue().decode('utf-8')
        except:
            # File có thể rỗng hoặc mới tạo
            pass

        # Thêm dòng mới
        new_line = f"{filename}\t{label}\n"
        updated_content = content + new_line

        # Upload nội dung mới
        file_metadata = {'name': 'labels.txt'}
        media = MediaIoBaseUpload(
            io.BytesIO(updated_content.encode('utf-8')),
            mimetype='text/plain',
            resumable=True
        )

        service.files().update(
            fileId=labels_file_id,
            body=file_metadata,
            media_body=media
        ).execute()

        return {
            'success': True
        }

    except Exception as e:
        error_msg = f"Lỗi khi append vào labels.txt: {str(e)}"
        return {
            'success': False,
            'error': error_msg
        }

def batch_upload_to_drive(files_to_upload):
    """
    Upload nhiều files lên Drive cùng lúc
    """
    results = []
    drive_instance = DriveService.get_instance()
    service = drive_instance.service
    root_id = drive_instance.get_root_folder_id('CUSTOMS')

    # Cache folder IDs to avoid repeated API calls
    folder_cache = {}

    for file_info in files_to_upload:
        try:
            date_folder = file_info['date_folder']

            # Get folder ID from cache or create new
            if date_folder not in folder_cache:
                folder_id = get_or_create_folder(service, root_id, date_folder)
                folder_cache[date_folder] = folder_id

            file_metadata = {
                'name': file_info['filename'],
                'parents': [folder_cache[date_folder]]
            }

            media = MediaIoBaseUpload(
                io.BytesIO(file_info['content']),
                mimetype='application/pdf',
                resumable=True
            )

            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            results.append({
                'invoice_no': file_info['invoice_no'],
                'file_id': file.get('id'),
                'success': True
            })

        except Exception as e:
            print(f"Lỗi upload file {file_info['filename']}: {str(e)}")
            results.append({
                'invoice_no': file_info['invoice_no'],
                'error': str(e),
                'success': False
            })

    return results
