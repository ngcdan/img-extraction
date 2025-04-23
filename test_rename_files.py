import os
from google_drive_utils import DriveService

def rename_files_in_folder():
    """
    Đọc và đổi tên các file trong thư mục 09042025 trên Google Drive
    Thay thế dấu '_' thành '-' trong tên file
    """
    try:
        # Khởi tạo Drive service
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_id = drive_instance.get_root_folder_id('CUSTOMS')

        if not root_id:
            raise Exception("Không tìm thấy folder CUSTOMS")

        # Tìm folder 09042025
        query = [
            f"'{root_id}' in parents",
            "name = '17042025'",
            "mimeType = 'application/vnd.google-apps.folder'",
            "trashed = false"
        ]

        results = service.files().list(
            q=" and ".join(query),
            spaces='drive',
            fields='files(id, name)',
        ).execute()

        folders = results.get('files', [])
        if not folders:
            raise Exception("Không tìm thấy thư mục 20042025")

        target_folder_id = folders[0]['id']

        # Lấy danh sách các file PDF trong folder
        query = [
            f"'{target_folder_id}' in parents",
            "mimeType = 'application/pdf'",
            "trashed = false"
        ]

        results = service.files().list(
            q=" and ".join(query),
            spaces='drive',
            fields='files(id, name)',
        ).execute()

        files = results.get('files', [])

        print(f"Tìm thấy {len(files)} file PDF")

        # Loop qua từng file và rename nếu cần
        for file in files:
            old_name = file['name']
            if '_' in old_name:
                new_name = old_name.replace('_', '-')
                print(f"Đổi tên: {old_name} -> {new_name}")

                # Update tên file
                file_metadata = {'name': new_name}
                service.files().update(
                    fileId=file['id'],
                    body=file_metadata,
                ).execute()
                print(f"Đã đổi tên thành công: {new_name}")

        print("Hoàn thành việc đổi tên files")

    except Exception as e:
        print(f"Lỗi: {str(e)}")

if __name__ == "__main__":
    rename_files_in_folder()