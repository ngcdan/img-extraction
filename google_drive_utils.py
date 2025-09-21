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

    def check_storage_quota(self):
        """Kiểm tra dung lượng còn lại của Google Drive"""
        try:
            about = self._service.about().get(fields='storageQuota').execute()
            quota = about.get('storageQuota', {})

            limit = int(quota.get('limit', 0))
            usage = int(quota.get('usage', 0))

            if limit == 0:  # Unlimited storage
                return True, float('inf'), 0

            remaining = limit - usage
            usage_percent = (usage / limit) * 100

            print(f"📊 Google Drive Storage:")
            print(f"   - Đã sử dụng: {usage / (1024**3):.2f} GB ({usage_percent:.1f}%)")
            print(f"   - Còn lại: {remaining / (1024**3):.2f} GB")

            # Cảnh báo nếu sắp hết dung lượng
            if usage_percent > 95:
                print(f"⚠️  CẢNH BÁO: Dung lượng Drive gần hết!")
                return False, remaining, usage_percent
            elif usage_percent > 80:
                print(f"⚡ Lưu ý: Dung lượng Drive đã sử dụng hơn 80%")

            return True, remaining, usage_percent

        except Exception as e:
            error_msg = str(e)
            print(f"Không thể kiểm tra dung lượng Drive: {error_msg}")

            # Phân tích loại lỗi quota
            if 'quotaExceeded' in error_msg or 'rateLimitExceeded' in error_msg:
                print(f"🔥 PHÁT HIỆN LỖI QUOTA:")
                if 'userRateLimitExceeded' in error_msg:
                    print(f"   - Loại: API Rate Limit per User (100 requests/100s)")
                    print(f"   - Khắc phục: Chờ 1-2 phút rồi thử lại")
                elif 'dailyLimitExceeded' in error_msg:
                    print(f"   - Loại: Daily API Limit (1 tỷ requests/day)")
                    print(f"   - Khắc phục: Đợi đến ngày mai")
                elif 'rateLimitExceeded' in error_msg:
                    print(f"   - Loại: General Rate Limit")
                    print(f"   - Khắc phục: Giảm tốc độ upload, thử lại sau")
                else:
                    print(f"   - Loại: Quota limit khác")
                    print(f"   - Chi tiết: {error_msg}")

                print(f"💡 Service Account Quotas:")
                print(f"   - Upload limit: 750GB/day per user")
                print(f"   - API requests: 1,000 per 100 seconds")
                print(f"   - Storage: Phụ thuộc vào owner account")

            return True, 0, 0  # Tiếp tục upload nếu không check được

    def get_service_account_info(self):
        """Lấy thông tin về Service Account đang sử dụng"""
        try:
            about = self._service.about().get(fields='user,storageQuota').execute()
            user_info = about.get('user', {})

            print(f"🤖 Service Account Info:")
            print(f"   - Email: {user_info.get('emailAddress', 'N/A')}")
            print(f"   - Display Name: {user_info.get('displayName', 'N/A')}")
            print(f"   - Permission ID: {user_info.get('permissionId', 'N/A')}")

            return user_info

        except Exception as e:
            print(f"Không thể lấy thông tin Service Account: {str(e)}")
            return None

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

def batch_upload_to_drive(files_to_upload):
    """
    Upload nhiều files lên Drive cùng lúc với kiểm tra quota
    """
    results = []
    drive_instance = DriveService.get_instance()
    service = drive_instance.service
    root_id = drive_instance.get_root_folder_id('CUSTOMS')

    # Kiểm tra dung lượng trước khi upload
    quota_ok, remaining_bytes, usage_percent = drive_instance.check_storage_quota()

    if not quota_ok:
        print(f"❌ Dừng upload do dung lượng Drive không đủ!")
        for file_info in files_to_upload:
            results.append({
                'invoice_no': file_info['invoice_no'],
                'error': f'Drive storage quota exceeded ({usage_percent:.1f}% used)',
                'success': False,
                'quota_exceeded': True
            })
        return results

    # Ước tính dung lượng cần thiết
    total_size = sum(len(file_info['content']) for file_info in files_to_upload)
    print(f"📦 Chuẩn bị upload {len(files_to_upload)} files (~{total_size / (1024**2):.1f} MB)")

    if remaining_bytes != float('inf') and total_size > remaining_bytes * 0.9:  # Để lại 10% buffer
        print(f"⚠️  CẢNH BÁO: Dung lượng cần thiết có thể vượt quá dung lượng còn lại!")

    # Cache folder IDs to avoid repeated API calls
    folder_cache = {}
    quota_exceeded = False

    for file_info in files_to_upload:
        try:
            # Skip remaining files if quota exceeded
            if quota_exceeded:
                results.append({
                    'invoice_no': file_info['invoice_no'],
                    'error': 'Quota exceeded - skipped upload',
                    'success': False,
                    'quota_exceeded': True
                })
                continue

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
            error_str = str(e)

            # Phân loại các lỗi quota khác nhau
            quota_error_type = None
            if 'storageQuotaExceeded' in error_str:
                quota_error_type = 'storage'
                quota_exceeded = True
                print(f"💾 LỖI STORAGE QUOTA:")
                print(f"   - File: {file_info['filename']}")
                print(f"   - Nguyên nhân: Owner account hết dung lượng Drive")
                print(f"   - Khắc phục: Dọn dẹp Google Drive của owner account")

            elif 'userRateLimitExceeded' in error_str:
                quota_error_type = 'user_rate'
                print(f"⚡ LỖI USER RATE LIMIT:")
                print(f"   - File: {file_info['filename']}")
                print(f"   - Nguyên nhân: Vượt quá 100 requests/100s per user")
                print(f"   - Khắc phục: Chờ 1-2 phút rồi thử lại")

            elif 'rateLimitExceeded' in error_str:
                quota_error_type = 'rate_limit'
                print(f"🔥 LỖI RATE LIMIT:")
                print(f"   - File: {file_info['filename']}")
                print(f"   - Nguyên nhân: Vượt quá giới hạn API requests")
                print(f"   - Khắc phục: Giảm tốc độ upload")

            elif 'dailyLimitExceeded' in error_str:
                quota_error_type = 'daily_limit'
                quota_exceeded = True
                print(f"📅 LỖI DAILY LIMIT:")
                print(f"   - File: {file_info['filename']}")
                print(f"   - Nguyên nhân: Vượt quá giới hạn API requests/ngày")
                print(f"   - Khắc phục: Đợi đến ngày mai")

            elif 'quotaExceeded' in error_str or 'quota' in error_str.lower():
                quota_error_type = 'other_quota'
                quota_exceeded = True
                print(f"⚠️  LỖI QUOTA KHÁC:")
                print(f"   - File: {file_info['filename']}")
                print(f"   - Chi tiết: {error_str}")

            elif '403' in error_str:
                quota_error_type = 'permission'
                print(f"🚫 LỖI PERMISSION:")
                print(f"   - File: {file_info['filename']}")
                print(f"   - Nguyên nhân: Service Account không có quyền")
                print(f"   - Khắc phục: Kiểm tra quyền chia sẻ folder")

            else:
                print(f"❌ Lỗi upload file {file_info['filename']}: {error_str}")

            results.append({
                'invoice_no': file_info['invoice_no'],
                'error': error_str,
                'success': False,
                'quota_exceeded': quota_error_type in ['storage', 'daily_limit', 'other_quota'],
                'quota_error_type': quota_error_type
            })

    # Print detailed summary
    successful_uploads = sum(1 for r in results if r['success'])
    quota_errors = [r for r in results if r.get('quota_exceeded', False)]
    other_errors = len(results) - successful_uploads - len(quota_errors)

    if quota_errors or other_errors > 0:
        print(f"\n📊 TỔNG KẾT UPLOAD:")
        print(f"   - ✅ Thành công: {successful_uploads}")
        print(f"   - ❌ Lỗi quota: {len(quota_errors)}")
        print(f"   - ⚠️  Lỗi khác: {other_errors}")

        # Phân tích các loại lỗi quota
        if quota_errors:
            error_types = {}
            for r in quota_errors:
                error_type = r.get('quota_error_type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1

            print(f"\n🔍 PHÂN TÍCH LỖI QUOTA:")
            for error_type, count in error_types.items():
                if error_type == 'storage':
                    print(f"   - 💾 Storage quota ({count} files): Owner account hết dung lượng")
                elif error_type == 'user_rate':
                    print(f"   - ⚡ User rate limit ({count} files): Quá 100 requests/100s")
                elif error_type == 'rate_limit':
                    print(f"   - 🔥 Rate limit ({count} files): Quá nhiều API requests")
                elif error_type == 'daily_limit':
                    print(f"   - 📅 Daily limit ({count} files): Hết quota ngày")
                elif error_type == 'permission':
                    print(f"   - 🚫 Permission ({count} files): Không có quyền truy cập")
                else:
                    print(f"   - ❓ {error_type} ({count} files): Lỗi không xác định")

            print(f"\n💡 HƯỚNG DẪN KHẮC PHỤC:")
            if 'storage' in error_types:
                print(f"   🔹 Storage quota: Dọn dẹp Google Drive owner account")
                print(f"      → https://drive.google.com")
                print(f"      → Xóa files cũ và empty trash")
            if 'user_rate' in error_types or 'rate_limit' in error_types:
                print(f"   🔹 Rate limits: Giảm tần suất upload")
                print(f"      → Chờ 1-2 phút rồi thử lại")
                print(f"      → Upload ít files hơn mỗi lần")
            if 'daily_limit' in error_types:
                print(f"   🔹 Daily limit: Chờ đến ngày mai")
            if 'permission' in error_types:
                print(f"   🔹 Permission: Kiểm tra quyền Service Account")
                print(f"      → Đảm bảo Service Account có quyền write vào folder")

    return results
