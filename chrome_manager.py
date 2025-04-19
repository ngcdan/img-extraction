import os
import sys
import time
import json
import random
import platform
import logging
from typing import Optional, Tuple, Dict, Any, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from cookie_manager import CookieManager

logger = logging.getLogger(__name__)


def get_resource_path(relative_path: str) -> str:
    """Lấy đường dẫn tuyệt đối đến tài nguyên, hoạt động trong cả development và production"""
    try:
        # PyInstaller tạo một thư mục temp và lưu đường dẫn trong _MEIPASS
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
    except Exception:
        return relative_path


class ChromeManager:
    LOGIN_URL = "http://thuphi.haiphong.gov.vn:8222/dang-nhap"
    HOME_URL = "http://thuphi.haiphong.gov.vn:8222/Home"

    @staticmethod
    def initialize_chrome(max_retries: int = 3, auto_login: bool = True) -> Optional[webdriver.Chrome]:
        """Khởi tạo Chrome và tự động đăng nhập nếu được yêu cầu

        Args:
            max_retries: Số lần thử lại tối đa khi khởi tạo Chrome
            auto_login: Tự động đăng nhập sau khi khởi tạo Chrome

        Returns:
            WebDriver instance hoặc None nếu không thể khởi tạo
        """
        # Lấy thông tin đăng nhập trước để tránh đọc file nhiều lần
        login_credentials = ChromeManager._get_login_credentials() if auto_login else None

        for attempt in range(max_retries):
            try:
                # Thiết lập options tối thiểu cho Chrome để mở nhanh nhất
                chrome_options = webdriver.ChromeOptions()

                # Các tham số cần thiết để tăng tốc độ khởi động
                chrome_options.add_argument('--no-first-run')
                chrome_options.add_argument('--no-default-browser-check')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--disable-notifications')
                chrome_options.add_argument('--disable-background-networking')
                chrome_options.add_argument('--disable-background-timer-throttling')
                chrome_options.add_argument('--disable-backgrounding-occluded-windows')

                # Tắt các popup và tối ưu performance
                prefs = {
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False,
                    "browser.startup.homepage": "about:blank",
                    "browser.startup.page": 0
                }
                chrome_options.add_experimental_option("prefs", prefs)

                # Tránh phát hiện automation
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
                chrome_options.add_experimental_option('useAutomationExtension', False)

                # Khởi tạo service và driver
                # Sử dụng cách tiếp cận nhanh hơn để tìm ChromeDriver
                try:
                    # Thử sử dụng ChromeDriver đã cài đặt trước đó
                    service = Service()
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                except:
                    # Nếu không tìm thấy, sử dụng ChromeDriverManager
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=chrome_options)

                print("Đã khởi tạo Chrome thành công")

                # Nếu cần đăng nhập tự động
                if auto_login and login_credentials:
                    try:
                        # Truy cập trang đăng nhập
                        if ChromeManager.wait_for_page_load(driver, ChromeManager.LOGIN_URL):
                            # Đợi form đăng nhập xuất hiện
                            wait = WebDriverWait(driver, 30)
                            wait.until(EC.presence_of_element_located((By.ID, "form-username")))

                            # Điền thông tin đăng nhập
                            if ChromeManager.fill_login_info(driver, login_credentials['username'], login_credentials['password']):
                                print(f"Đã đăng nhập thành công với tài khoản {login_credentials['username']} | Password: {login_credentials['password']}")
                            else:
                                print(f"Không thể đăng nhập tự động với tài khoản {login_credentials['username']} | Password: {login_credentials['password']}")
                    except Exception as e:
                        print(f"Lỗi khi đăng nhập tự động với tài khoản {login_credentials['username']} | Password: {login_credentials['password']}: {str(e)}")
                else:
                    # Mở trang trống nếu không cần đăng nhập
                    driver.get("about:blank")

                return driver

            except Exception as e:
                print(f"Lỗi khi khởi tạo Chrome (lần {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(1)  # Giảm thời gian chờ giữa các lần thử

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
        # last_captcha = {'text': None, 'image': None}  # Comment lại biến lưu captcha

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

        def fill_form() -> bool:
            """Điền thông tin form"""
            try:
                username_input = wait.until(EC.presence_of_element_located((By.ID, "form-username")))
                username_input.clear()
                username_input.send_keys(username)

                password_input = wait.until(EC.presence_of_element_located((By.ID, "form-password")))
                password_input.clear()
                password_input.send_keys(password)

                return True
            except Exception as e:
                print(f"Lỗi khi điền form: {str(e)}")
                return False

        # Comment lại toàn bộ phần script theo dõi captcha
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
                # Comment lại phần xử lý captcha
                # current_captcha = get_current_captcha()
                # if (current_captcha and
                #     len(current_captcha) >= 5 and
                #     current_captcha != last_captcha.get('text')):
                #     try:
                #         captcha_element = driver.find_element(By.ID, "CaptchaImage")
                #         last_captcha = {
                #             'text': current_captcha,
                #             'image': captcha_element.screenshot_as_png
                #         }
                #         try:
                #             submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                #             if submit_btn and submit_btn.is_enabled():
                #                 driver.execute_script("arguments[0].click();", submit_btn)
                #         except:
                #             pass

                #     except:
                #         pass

                if is_login_successful():
                    # Comment lại phần lưu captcha
                    # if last_captcha['text'] and last_captcha['image']:
                    #     ChromeManager.save_captcha_and_label(last_captcha['image'], last_captcha['text'])
                    # CookieManager.save_cookies(driver, username)
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
    def wait_for_search_complete(driver: webdriver.Chrome, timeout: int = 30) -> bool:
        """Chờ cho kết quả tìm kiếm hoàn tất và bảng dữ liệu được load

        Args:
            driver: WebDriver instance
            timeout: Thời gian chờ tối đa (giây)

        Returns:
            bool: True nếu tìm kiếm hoàn tất, False nếu timeout
        """
        def is_search_complete() -> bool:
            try:
                # Kiểm tra preloader đã biến mất
                if driver.find_elements(By.CLASS_NAME, "preloader-container"):
                    return False

                # Kiểm tra bảng dữ liệu
                table = driver.find_element(By.ID, "TBLDANHSACH")
                if not table:
                    return False

                # Kiểm tra số lượng rows hoặc thông báo không có dữ liệu
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) > 1:  # Có ít nhất 1 row dữ liệu (không tính header)
                    return True

                # Kiểm tra thông báo "không có dữ liệu"
                empty_messages = driver.find_elements(By.CSS_SELECTOR, ".dataTables_empty")
                if empty_messages and any(msg.is_displayed() for msg in empty_messages):
                    return True

                return False

            except Exception:
                return False

        # Sử dụng WebDriverWait để tối ưu việc chờ đợi
        try:
            short_wait = WebDriverWait(driver, timeout)
            short_wait.until(lambda d: is_search_complete())
            return True
        except TimeoutException:
            return False

    @staticmethod
    def _get_login_credentials() -> Dict[str, str]:
        """
        Lấy thông tin đăng nhập từ file accounts.json

        Returns:
            Dict[str, str]: Thông tin đăng nhập gồm username và password
        """
        # Giá trị mặc định nếu không tìm thấy file
        default_credentials = {
            "username": "0303482440",
            "password": "@Mst0303482440"
        }

        try:
            # Thử load file accounts.json
            accounts_path = 'accounts.json'
            if not os.path.exists(accounts_path):
                # Trong production, sử dụng đường dẫn tương đối
                accounts_path = get_resource_path(accounts_path)

            if os.path.exists(accounts_path):
                # Đọc file và lấy tài khoản ngẫu nhiên
                with open(accounts_path, 'r') as f:
                    accounts = json.load(f)

                if accounts and len(accounts) > 0:
                    account = random.choice(accounts)
                    return account
                else:
                    print("File accounts.json không có dữ liệu")
            else:
                print(f"Không tìm thấy file accounts tại {accounts_path}")
        except Exception as e:
            print(f"Lỗi khi đọc file accounts: {str(e)}")
        return default_credentials
