import os
import time
import platform
import logging
from typing import Optional, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from cookie_manager import CookieManager

logger = logging.getLogger(__name__)

class ChromeManager:
    LOGIN_URL = "http://thuphi.haiphong.gov.vn:8222/dang-nhap"
    HOME_URL = "http://thuphi.haiphong.gov.vn:8222/Home"

    @staticmethod
    def initialize_chrome(max_retries: int = 3) -> Optional[webdriver.Chrome]:
        """Khởi tạo Chrome và mở trang web"""
        for attempt in range(max_retries):
            try:
                print(f"Đang khởi tạo Chrome driver... (lần thử {attempt + 1}/{max_retries})")

                # Xác định đường dẫn profile mặc định của Chrome
                if platform.system() == 'Windows':
                    default_profile = os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data')
                    chrome_path = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
                    if not os.path.exists(chrome_path):
                        chrome_path = 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
                else:  # macOS
                    default_profile = os.path.expanduser('~/Library/Application Support/Google/Chrome')
                    chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

                # Kill tất cả các process Chrome debug hiện tại
                if platform.system() == 'Windows':
                    os.system('taskkill /f /im "chrome.exe" >nul 2>&1')
                else:
                    os.system('pkill -f "Chrome.*--remote-debugging-port=9222" >/dev/null 2>&1')

                time.sleep(2)  # Đợi process được kill hoàn toàn

                # Thiết lập options cho Chrome
                chrome_options = webdriver.ChromeOptions()
                chrome_options.add_argument(f'--user-data-dir={default_profile}')
                chrome_options.add_argument('--remote-debugging-port=9222')
                chrome_options.add_argument('--no-first-run')
                chrome_options.add_argument('--no-default-browser-check')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-features=TranslateUI')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                chrome_options.add_argument('--disable-save-password-bubble')  # Tắt popup lưu password
                chrome_options.add_argument('--disable-notifications')  # Tắt tất cả các notifications
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)

                # Tắt hoàn toàn các popup credentials
                prefs = {
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False,
                    "profile.default_content_setting_values.notifications": 2  # 2 = block
                }
                chrome_options.add_experimental_option("prefs", prefs)

                # Khởi tạo service và driver
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                    "userAgent": 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
                })

                # Thiết lập kích thước cửa sổ iPhone 14 Pro Max
                driver.set_window_size(430, 932)
                print("Đã kết nối với Chrome thành công")
                return driver

            except Exception as e:
                print(f"Lỗi khi khởi tạo Chrome (lần {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    print("Đã hết số lần thử khởi tạo Chrome")
                    return None
                time.sleep(3)

        return None

    @staticmethod
    def is_table_loaded_with_data(driver: webdriver.Chrome, short_wait: WebDriverWait) -> bool:
        """Kiểm tra xem bảng dữ liệu đã load hoàn tất và có dữ liệu chưa"""
        try:
            # 1. Kiểm tra sự tồn tại của bảng
            table = short_wait.until(EC.presence_of_element_located((By.ID, "TBLDANHSACH")))

            # 2. Kiểm tra số lượng rows
            rows = table.find_elements(By.TAG_NAME, "tr")
            if len(rows) > 1:  # Có ít nhất 1 row dữ liệu (không tính header)
                return True

            # 3. Kiểm tra thông báo "không có dữ liệu"
            empty_messages = driver.find_elements(By.CSS_SELECTOR, ".dataTables_empty")
            if empty_messages and any(msg.is_displayed() for msg in empty_messages):
                return True

            return False
        except:
            return False

    @staticmethod
    def is_page_loaded(driver: webdriver.Chrome) -> bool:
        """Kiểm tra trang đã load xong chưa"""
        try:
            return driver.execute_script('return document.readyState') == 'complete'
        except:
            return False

    @staticmethod
    def wait_for_page_load(driver: webdriver.Chrome, url: str, timeout: int = 30) -> bool:
        """Đợi cho trang load hoàn tất"""
        try:
            driver.get(url)
            start_time = time.time()
            while time.time() - start_time < timeout:
                if ChromeManager.is_page_loaded(driver):
                    return True
                time.sleep(0.1)
            return False
        except:
            return False

    @staticmethod
    def fill_login_info(driver: webdriver.Chrome, username: str, password: str, max_wait_time: int = 240) -> bool:
        """Điền thông tin đăng nhập và đợi user login thành công"""
        wait = WebDriverWait(driver, 10)
        start_time = time.time()
        last_captcha = {'text': None, 'image': None}

        def is_login_successful() -> bool:
            """Kiểm tra đăng nhập thành công"""
            return (driver.current_url == ChromeManager.HOME_URL or
                    (driver.current_url != ChromeManager.LOGIN_URL and "dang-nhap" not in driver.current_url))

        def needs_refill() -> bool:
            """Kiểm tra xem có cần điền lại thông tin không"""
            try:
                username_input = driver.find_element(By.ID, "form-username")
                return not username_input.get_attribute('value')
            except:
                return False

        def get_current_captcha() -> Optional[str]:
            """Lấy giá trị captcha hiện tại"""
            try:
                captcha_input = driver.find_element(By.ID, "CaptchaInputText")
                return captcha_input.get_attribute('value')
            except:
                return None

        def fill_form() -> bool:
            """Điền thông tin form"""
            try:
                username_input = wait.until(EC.presence_of_element_located((By.ID, "form-username")))
                username_input.clear()
                username_input.send_keys(username)

                password_input = wait.until(EC.presence_of_element_located((By.ID, "form-password")))
                password_input.clear()
                password_input.send_keys(password)

                try:
                    captcha_input = driver.find_element(By.ID, "CaptchaInputText")
                    captcha_input.click()
                except:
                    pass

                return True
            except Exception as e:
                print(f"Lỗi khi điền form: {str(e)}")
                return False

        # Thêm script theo dõi captcha
        js_script = """
        window.captchaValue = '';
        window.lastSubmittedCaptcha = '';
        window.getCaptchaValue = function() {
            return window.captchaValue;
        };

        const captchaInput = document.getElementById('CaptchaInputText');
        if (captchaInput) {
            captchaInput.addEventListener('input', function() {
                window.captchaValue = this.value;
                if (this.value.length >= 5 && this.value !== window.lastSubmittedCaptcha) {
                    window.lastSubmittedCaptcha = this.value;
                    const submitBtn = document.querySelector('button[type="submit"]');
                    if (submitBtn) {
                        console.log('Auto submitting with captcha:', this.value);
                        submitBtn.click();
                    }
                }
            });

            captchaInput.addEventListener('blur', function() {
                window.captchaValue = this.value;
            });
        }
        """
        try:
            driver.execute_script(js_script)
        except:
            print("Không thể thêm script theo dõi captcha")

        # Đảm bảo đang ở trang đăng nhập
        if driver.current_url != ChromeManager.LOGIN_URL:
            driver.get(ChromeManager.LOGIN_URL)
            time.sleep(1)

        # Điền thông tin lần đầu
        if not fill_form():
            raise Exception("Không thể điền thông tin đăng nhập lần đầu")

        # Loop kiểm tra liên tục
        while time.time() - start_time < max_wait_time:
            try:
                current_captcha = get_current_captcha()
                if (current_captcha and
                    len(current_captcha) >= 5 and
                    current_captcha != last_captcha.get('text')):
                    try:
                        captcha_element = driver.find_element(By.ID, "CaptchaImage")
                        last_captcha = {
                            'text': current_captcha,
                            'image': captcha_element.screenshot_as_png
                        }
                        try:
                            submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                            if submit_btn and submit_btn.is_enabled():
                                driver.execute_script("arguments[0].click();", submit_btn)
                        except:
                            pass

                    except:
                        pass

                if is_login_successful():
                    if last_captcha['text'] and last_captcha['image']:
                        ChromeManager.save_captcha_and_label(last_captcha['image'], last_captcha['text'])
                    CookieManager.save_cookies(driver, username)
                    return True

                if "dang-nhap" in driver.current_url:
                    error_messages = driver.find_elements(By.CLASS_NAME, "validation-summary-errors")
                    if error_messages and any(msg.is_displayed() for msg in error_messages):
                        if needs_refill():
                            fill_form()
                    elif needs_refill():
                        fill_form()

                time.sleep(0.5)

            except Exception as e:
                print(f"Lỗi khi kiểm tra trạng thái: {str(e)}")
                try:
                    driver.get(ChromeManager.LOGIN_URL)
                    time.sleep(1)
                    fill_form()
                except:
                    pass

        raise Exception(f"Hết thời gian chờ ({max_wait_time}s) - Người dùng chưa đăng nhập thành công")

    @staticmethod
    def save_captcha_and_label(image_data: bytes, captcha_text: str) -> bool:
        """Lưu captcha và label"""
        try:
            from google_drive_utils import upload_captcha_to_drive, append_to_labels_file
            result = upload_captcha_to_drive(image_data)

            if result['success']:
                append_result = append_to_labels_file(result['filename'], captcha_text)
                return append_result['success']
            return False

        except Exception as e:
            print(f"Lỗi khi lưu captcha và label: {e}")
            return False
