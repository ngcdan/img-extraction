from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import os
from utils import send_notification

# Cấu hình chung
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'driver-service-account.json'
ROOT_FOLDER_ID = '1FxafcnGt45hEpE5UHrjbQD4yjrEdmTGm'

class DriveService:
    _instance = None
    _service = None

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
                if not os.path.exists(SERVICE_ACCOUNT_FILE):
                    raise FileNotFoundError(f"Không tìm thấy file {SERVICE_ACCOUNT_FILE}")

                credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
                self._service = build('drive', 'v3', credentials=credentials)
            except Exception as e:
                send_notification(f"Lỗi khởi tạo Drive service: {str(e)}", "error")
                raise

    @property
    def service(self):
        """Trả về Drive service instance"""
        return self._service

    @property
    def root_folder_id(self):
        """Trả về ID folder gốc"""
        return ROOT_FOLDER_ID

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

def get_or_create_folder(service, parent_id, folder_name):
    """Tìm folder theo tên hoặc tạo mới nếu chưa tồn tại"""
    try:
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = service.files().list(q=query, spaces='drive', fields='files(id)').execute()
        files = results.get('files', [])

        if files:
            return files[0]['id']
        return create_drive_folder(service, parent_id, folder_name)
    except Exception as e:
        print(f"Lỗi khi tìm/tạo folder: {e}")
        return None

def upload_file_to_drive(file_content, filename, parent_folder_date, custom_no, mimetype='application/pdf'):
    """
    Upload file lên Google Drive với cấu trúc thư mục ngày/số_tờ_khai

    Args:
        file_content: Nội dung file dạng bytes
        filename: Tên file
        parent_folder_date: Tên folder ngày (định dạng DDMMYYYY)
        custom_no: Số tờ khai hải quan
        mimetype: Loại file (mặc định là PDF)
    """
    try:
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_id = drive_instance.root_folder_id

        # Tạo/lấy folder theo ngày
        date_folder_id = get_or_create_folder(service, root_id, parent_folder_date)
        if not date_folder_id:
            raise Exception("Không thể tạo/tìm folder ngày")

        # Tạo/lấy folder số tờ khai
        custom_folder_id = get_or_create_folder(service, date_folder_id, custom_no)
        if not custom_folder_id:
            raise Exception("Không thể tạo/tìm folder số tờ khai")

        # Upload file
        file_metadata = {
            'name': filename,
            'parents': [custom_folder_id]
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

        file_path = f"{parent_folder_date}/{custom_no}/{filename}"

        return {
            'success': True,
            'file_id': file.get('id'),
            'web_view_link': file.get('webViewLink'),
            'file_path': file_path,  # Thêm file_path
            'folder_path': file_path  # Giữ folder_path để tương thích ngược
        }

    except Exception as e:
        error_msg = f"Lỗi khi upload file lên Drive: {str(e)}"
        send_notification(error_msg, "error")
        return {
            'success': False,
            'error': error_msg
        }
