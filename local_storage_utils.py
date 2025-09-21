import os
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from utils import get_default_customs_dir

def get_local_downloads_dir():
    """Lấy đường dẫn thư mục downloads mặc định"""
    system = platform.system()
    if system == 'Windows':
        # Windows: ~/Downloads hoặc ~/Desktop/downloads
        downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'CSHT_PDFs')
    elif system == 'Darwin':  # macOS
        # macOS: ~/Downloads
        downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'CSHT_PDFs')
    else:
        # Linux: ~/Downloads
        downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads', 'CSHT_PDFs')

    # Tạo thư mục nếu chưa tồn tại
    if not os.path.exists(downloads_dir):
        try:
            os.makedirs(downloads_dir)
            print(f"Đã tạo thư mục downloads tại: {downloads_dir}")
        except Exception as e:
            print(f"Không thể tạo thư mục downloads: {str(e)}")
            sys.exit(1)

    return downloads_dir

def get_or_create_date_folder(base_dir: str, date_folder: str) -> str:
    """Tạo thư mục theo ngày nếu chưa tồn tại"""
    date_path = os.path.join(base_dir, date_folder)

    if not os.path.exists(date_path):
        try:
            os.makedirs(date_path)
            print(f"Đã tạo thư mục ngày: {date_path}")
        except Exception as e:
            print(f"Không thể tạo thư mục {date_path}: {str(e)}")
            return base_dir  # Fallback về thư mục gốc

    return date_path

def save_pdf_to_local(pdf_data: bytes, filename: str, date_folder: str, base_dir: str = None) -> Dict[str, Any]:
    """
    Lưu PDF về máy local với cấu trúc thư mục theo ngày

    Args:
        pdf_data: Dữ liệu PDF dạng bytes
        filename: Tên file
        date_folder: Tên thư mục theo ngày (format: ddmmyyyy)
        base_dir: Thư mục gốc (mặc định là Downloads/CSHT_PDFs)

    Returns:
        Dict với thông tin kết quả lưu file
    """
    try:
        if base_dir is None:
            base_dir = get_local_downloads_dir()

        # Tạo thư mục theo ngày
        target_dir = get_or_create_date_folder(base_dir, date_folder)

        # Đường dẫn file đầy đủ
        file_path = os.path.join(target_dir, filename)

        # Kiểm tra file đã tồn tại chưa
        if os.path.exists(file_path):
            print(f"File đã tồn tại: {filename}")
            return {
                'success': True,
                'file_path': file_path,
                'message': f'File already exists: {filename}',
                'already_exists': True
            }

        # Lưu file
        with open(file_path, 'wb') as f:
            f.write(pdf_data)

        # Kiểm tra kích thước file
        file_size = os.path.getsize(file_path)

        print(f"✅ Đã lưu: {filename} ({file_size:,} bytes)")

        return {
            'success': True,
            'file_path': file_path,
            'file_size': file_size,
            'message': f'Successfully saved: {filename}'
        }

    except Exception as e:
        error_msg = f"Lỗi khi lưu file {filename}: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'filename': filename
        }

def batch_save_to_local(files_to_save: List[Dict]) -> List[Dict[str, Any]]:
    """
    Lưu nhiều files PDF về local cùng lúc

    Args:
        files_to_save: List các dict chứa thông tin file {
            'content': bytes,
            'filename': str,
            'date_folder': str,
            'invoice_no': str
        }

    Returns:
        List kết quả cho từng file
    """
    results = []
    base_dir = get_local_downloads_dir()

    print(f"📁 Lưu files vào: {base_dir}")
    print(f"📦 Đang xử lý {len(files_to_save)} files...")

    # Thống kê theo ngày
    date_stats = {}
    total_size = 0

    for file_info in files_to_save:
        try:
            result = save_pdf_to_local(
                pdf_data=file_info['content'],
                filename=file_info['filename'],
                date_folder=file_info['date_folder'],
                base_dir=base_dir
            )

            # Thêm thông tin invoice_no vào kết quả
            result['invoice_no'] = file_info['invoice_no']
            results.append(result)

            # Cập nhật thống kê
            if result['success'] and not result.get('already_exists', False):
                date_folder = file_info['date_folder']
                if date_folder not in date_stats:
                    date_stats[date_folder] = {'count': 0, 'size': 0}

                date_stats[date_folder]['count'] += 1
                date_stats[date_folder]['size'] += result.get('file_size', 0)
                total_size += result.get('file_size', 0)

        except Exception as e:
            error_result = {
                'success': False,
                'error': str(e),
                'invoice_no': file_info.get('invoice_no', ''),
                'filename': file_info.get('filename', '')
            }
            results.append(error_result)
            print(f"❌ Lỗi xử lý file {file_info.get('filename', '')}: {str(e)}")

    # In thống kê
    successful_saves = sum(1 for r in results if r['success'] and not r.get('already_exists', False))
    already_exists = sum(1 for r in results if r.get('already_exists', False))
    failures = len(results) - successful_saves - already_exists

    print(f"\n📊 TỔNG KẾT SAVE LOCAL:")
    print(f"   - ✅ Lưu thành công: {successful_saves}")
    print(f"   - 📁 Đã tồn tại: {already_exists}")
    print(f"   - ❌ Thất bại: {failures}")
    print(f"   - 📦 Tổng dung lượng: {total_size / (1024**2):.1f} MB")

    if date_stats:
        print(f"\n📅 THỐNG KÊ THEO NGÀY:")
        for date_folder, stats in sorted(date_stats.items()):
            print(f"   - {date_folder}: {stats['count']} files ({stats['size'] / (1024**2):.1f} MB)")

    return results

def get_storage_info() -> Dict[str, Any]:
    """Lấy thông tin về dung lượng ổ đĩa local"""
    try:
        downloads_dir = get_local_downloads_dir()

        # Lấy thông tin ổ đĩa
        if platform.system() == 'Windows':
            import shutil
            total, used, free = shutil.disk_usage(downloads_dir)
        else:
            import os
            statvfs = os.statvfs(downloads_dir)
            free = statvfs.f_frsize * statvfs.f_available
            total = statvfs.f_frsize * statvfs.f_blocks
            used = total - free

        usage_percent = (used / total) * 100 if total > 0 else 0

        print(f"💾 Thông tin ổ đĩa ({downloads_dir}):")
        print(f"   - Tổng dung lượng: {total / (1024**3):.1f} GB")
        print(f"   - Đã sử dụng: {used / (1024**3):.1f} GB ({usage_percent:.1f}%)")
        print(f"   - Còn trống: {free / (1024**3):.1f} GB")

        # Cảnh báo nếu ổ đĩa sắp đầy
        if usage_percent > 90:
            print(f"⚠️  CẢNH BÁO: Ổ đĩa gần đầy!")
            return False, free, usage_percent
        elif usage_percent > 80:
            print(f"⚡ Lưu ý: Ổ đĩa đã sử dụng hơn 80%")

        return True, free, usage_percent

    except Exception as e:
        print(f"Không thể kiểm tra dung lượng ổ đĩa: {str(e)}")
        return True, 0, 0

def open_downloads_folder():
    """Mở thư mục downloads trong file explorer"""
    try:
        downloads_dir = get_local_downloads_dir()

        if platform.system() == 'Windows':
            os.startfile(downloads_dir)
        elif platform.system() == 'Darwin':  # macOS
            os.system(f'open "{downloads_dir}"')
        else:  # Linux
            os.system(f'xdg-open "{downloads_dir}"')

        print(f"📂 Đã mở thư mục: {downloads_dir}")
        return True

    except Exception as e:
        print(f"Không thể mở thư mục downloads: {str(e)}")
        return False

def cleanup_old_files(days_old: int = 30) -> Dict[str, Any]:
    """
    Dọn dẹp các file cũ hơn số ngày được chỉ định

    Args:
        days_old: Số ngày để xác định file cũ (mặc định 30 ngày)

    Returns:
        Dict với thông tin về việc dọn dẹp
    """
    try:
        downloads_dir = get_local_downloads_dir()
        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)

        deleted_files = []
        deleted_size = 0

        for root, dirs, files in os.walk(downloads_dir):
            for file in files:
                if file.endswith('.pdf'):
                    file_path = os.path.join(root, file)

                    # Kiểm tra thời gian tạo file
                    if os.path.getctime(file_path) < cutoff_date:
                        try:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_files.append(file)
                            deleted_size += file_size
                        except Exception as e:
                            print(f"Không thể xóa file {file}: {str(e)}")

        print(f"🧹 Dọn dẹp hoàn tất:")
        print(f"   - Đã xóa: {len(deleted_files)} files")
        print(f"   - Dung lượng giải phóng: {deleted_size / (1024**2):.1f} MB")

        return {
            'success': True,
            'deleted_count': len(deleted_files),
            'deleted_size': deleted_size,
            'deleted_files': deleted_files
        }

    except Exception as e:
        error_msg = f"Lỗi khi dọn dẹp files: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }