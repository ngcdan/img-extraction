from flask import Flask, render_template, request, jsonify
import threading
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time

from fetch_bien_lai import get_chrome_driver, fill_login_info, navigate_to_bien_lai_list, download_pdf, save_captcha_and_label

app = Flask(__name__)

CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
    }
})

# Biến global để lưu trạng thái
driver = None
download_status = {
    'total': 0,
    'current': 0,
    'success': 0,
    'failed': 0,
    'status': 'idle'  # idle, running, completed, error
}

def process_download(username, so_tk=None):
    global driver, download_status
    try:
        # Mở trang đăng nhập
        driver.execute_script("window.open('http://thuphi.haiphong.gov.vn:8222/dang-nhap', '_blank');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])

        # Đăng nhập
        fill_login_info(driver, username, username)

        # Thêm script theo dõi captcha
        js_script = """
        window.captchaValue = '';
        window.getCaptchaValue = function() {
            return window.captchaValue;
        };
        const captchaInput = document.getElementById('CaptchaInputText');
        captchaInput.addEventListener('blur', function() {
            window.captchaValue = this.value;
        });
        captchaInput.addEventListener('input', function() {
            if (this.value.length >= 5) {
                window.captchaValue = this.value;
            }
        });
        """
        driver.execute_script(js_script)

        # Đợi đăng nhập thành công và lưu captcha
        current_url = driver.current_url
        timeout = time.time() + 60  # timeout 60 giây
        captcha_saved = False
        login_success = False

        while time.time() < timeout:
            try:
                if not captcha_saved:
                    captcha_text = driver.execute_script("return window.getCaptchaValue()")
                    if captcha_text and len(captcha_text) >= 5:
                        save_captcha_and_label(driver, captcha_text)
                        captcha_saved = True
                        print("Đã lưu thông tin captcha")

                if current_url != driver.current_url:
                    if driver.current_url == "http://thuphi.haiphong.gov.vn:8222/Home":
                        print("Đăng nhập thành công")
                        login_success = True
                        break
                time.sleep(1)
            except Exception as e:
                print(f"Lỗi khi kiểm tra: {e}")
                continue

        if not login_success:
            raise Exception("Đăng nhập không thành công sau 60 giây")

        # Điều hướng và tải file
        navigate_to_bien_lai_list(driver, so_tk)

        wait = WebDriverWait(driver, 10)
        links = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            "a.color-blue.underline[href^='http://113.160.97.58:8224/Viewer/HoaDonViewer.aspx?mhd='][href$='iscd=1']"
        )))

        download_status['total'] = len(links)

        for i, link in enumerate(links, 1):
            if 'Xem' in link.text:
                download_status['current'] = i
                if download_pdf(driver, link):
                    download_status['success'] += 1
                else:
                    download_status['failed'] += 1
                time.sleep(1)

        download_status['status'] = 'completed'

    except Exception as e:
        download_status['status'] = 'error'
        print(f"Lỗi: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_download():
    global driver, download_status

    username = request.form.get('username')
    if not username or not username.strip().isdigit():
        return jsonify({'error': 'Mã số thuế không hợp lệ'})

    so_tk = request.form.get('so_tk')
    try:
        # Khởi tạo driver nếu chưa có
        if not driver:
            driver = get_chrome_driver()
            if not driver:
                return jsonify({'error': 'Không thể khởi tạo Chrome'})

        # Bắt đầu process download trong thread riêng
        download_status = {
            'total': 0,
            'current': 0,
            'success': 0,
            'failed': 0,
            'status': 'running'
        }

        thread = threading.Thread(target=process_download, args=(username, so_tk))
        thread.daemon = True
        thread.start()

        return jsonify({'message': 'Đã bắt đầu tải'})

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/status')
def get_status():
    return jsonify(download_status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)