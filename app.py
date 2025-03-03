from flask import Flask, render_template, request, jsonify, send_file
import threading
from flask_cors import CORS
import time
import os
import io
from datetime import datetime
from utils import init_socketio, send_notification
from receipt_fetcher import (
    initialize_chrome, process_download, fill_login_info,
    navigate_to_bien_lai_list, download_pdf, save_captcha_and_label
)
from extract_info import process_file_content, query_customs_info, append_to_google_sheet

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = init_socketio(app)

# Global variables
driver = None
download_status = {
    'total': 0,
    'current': 0,
    'success': 0,
    'failed': 0,
    'status': 'idle'  # idle, running, completed, error
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_download():
    global driver, download_status

    try:
        username = request.form.get('username')
        if not username or not username.strip().isdigit():
            return jsonify({'error': 'Mã số thuế không hợp lệ'})

        so_tk = request.form.get('so_tk')

        # Khởi tạo driver nếu chưa có hoặc đã bị đóng
        if driver is None or (hasattr(driver, 'service') and not driver.service.is_connectable()):
            driver = initialize_chrome()
            if not driver:
                return jsonify({'error': 'Không thể khởi tạo Chrome'})

        # Reset trạng thái download
        download_status = {
            'total': 0,
            'current': 0,
            'success': 0,
            'failed': 0,
            'status': 'running'
        }

        # Bắt đầu process download trong thread riêng
        download_thread = threading.Thread(
            target=process_download,
            args=(driver, username, so_tk, download_status)
        )
        download_thread.daemon = True
        download_thread.start()

        return jsonify({'status': 'started'})

    except Exception as e:
        error_message = f"Lỗi khi bắt đầu tải: {str(e)}"
        send_notification(error_message, "error")
        return jsonify({'error': error_message})

@app.route('/status')
def get_status():
    return jsonify(download_status)

@app.route('/upload', methods=['POST'])
def upload_file():
    """Route xử lý upload file và trích xuất thông tin"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Không tìm thấy file'})

        file = request.files['file']
        result = process_file_content(file)
        return jsonify(result)

    except Exception as e:
        print(f"Lỗi server: {e}")
        return jsonify({
            'success': False,
            'error': f'Lỗi server: {str(e)}'
        })

def close_specific_tabs(url_pattern):
    """Đóng các tab có địa chỉ chứa url_pattern"""
    global driver
    if not driver:
        return

    try:
        # Lưu lại handle của tab hiện tại
        current_handle = driver.current_window_handle

        # Lấy tất cả các handle
        handles = driver.window_handles

        # Duyệt qua từng handle và đóng tab phù hợp
        for handle in handles[:]:  # Tạo bản sao của list để tránh lỗi khi xóa phần tử
            try:
                driver.switch_to.window(handle)
                if url_pattern in driver.current_url:
                    print(f"Đóng tab: {driver.current_url}")
                    driver.close()
            except:
                continue

        # Kiểm tra xem còn tab nào không
        remaining_handles = driver.window_handles
        if remaining_handles:
            # Chuyển về tab đầu tiên nếu tab hiện tại đã bị đóng
            if current_handle not in remaining_handles:
                driver.switch_to.window(remaining_handles[0])

    except Exception as e:
        print(f"Lỗi khi đóng tab: {e}")

def cleanup():
    """Dọn dẹp tài nguyên khi tắt app"""
    global driver
    if driver:
        try:
            driver.quit()
        except:
            pass
        driver = None

def open_browser():
    """Mở trình duyệt mặc định với trang web của app"""
    import webbrowser
    webbrowser.open('http://localhost:8080')  # Đổi port ở đây

if __name__ == '__main__':
    try:
        # Khởi tạo Chrome trong thread riêng
        chrome_thread = threading.Thread(target=initialize_chrome)
        chrome_thread.daemon = True
        chrome_thread.start()

        # Đăng ký hàm cleanup khi tắt app
        import atexit
        atexit.register(cleanup)

        # Mở trình duyệt sau 2 giây
        threading.Timer(2.0, open_browser).start()

        # Chạy Flask app với port 8080
        socketio.run(app,
            host='0.0.0.0',
            port=8080,  # Đổi port ở đây
            debug=False,
            allow_unsafe_werkzeug=True
        )

    except Exception as e:
        print(f"Lỗi khi khởi động app: {e}")
        cleanup()
