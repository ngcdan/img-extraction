import os
import sys
import time
import json
import random
import platform
import logging
import warnings
import os.path
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

# Tắt các warning và log không cần thiết
warnings.filterwarnings("ignore")

# Tắt các log của TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # 0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR
os.environ['PYTHONWARNINGS'] = 'ignore'

# Tắt các log của Selenium
logging.getLogger('selenium').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('webdriver_manager').setLevel(logging.ERROR)


def get_resource_path(relative_path: str) -> str:
    """Lấy đường dẫn tuyệt đối đến tài nguyên, hoạt động trong cả development và production"""
    try:
        # PyInstaller tạo một thư mục temp và lưu đường dẫn trong _MEIPASS
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
    except Exception:
        return relative_path


class ChromeManager:
    LOGIN_URL = "https://pus.customs.gov.vn/faces/ContainerBarcode"
    HOME_URL = "https://pus.customs.gov.vn/faces/ContainerBarcode"

    @staticmethod
    def initialize_chrome(max_retries: int = 3, auto_login: bool = True) -> Optional[webdriver.Chrome]:
        """Khởi tạo Chrome và tự động đăng nhập nếu được yêu cầu

        Args:
            max_retries: Số lần thử lại tối đa khi khởi tạo Chrome
            auto_login: Tự động đăng nhập sau khi khởi tạo Chrome

        Returns:
            WebDriver instance hoặc None nếu không thể khởi tạo
        """
        for attempt in range(max_retries):
            try:
                # Thiết lập options tối thiểu cho Chrome để mở nhanh nhất
                chrome_options = webdriver.ChromeOptions()

                # Thêm chế độ ẩn danh
                # chrome_options.add_argument('--incognito')

                # Thêm experimental options
                prefs = {
                    "profile.default_content_settings.cookies": 2,  # Block all cookies
                    "profile.block_third_party_cookies": True,
                    "session.restore_on_startup": 4,  # Don't restore session
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False,
                }
                chrome_options.add_experimental_option("prefs", prefs)

                # Tắt các log và warning
                chrome_options.add_argument('--log-level=3')  # Chỉ hiển thị lỗi nghiêm trọng
                chrome_options.add_argument('--silent')  # Chế độ im lặng
                chrome_options.add_argument('--disable-logging')  # Tắt logging
                chrome_options.add_argument('--disable-dev-shm-usage')  # Tránh lỗi shared memory
                chrome_options.add_argument('--disable-gpu')  # Tắt GPU (giúp tránh nhiều warning)
                chrome_options.add_argument('--disable-infobars')  # Tắt infobar
                chrome_options.add_argument('--disable-breakpad')  # Tắt crash reporting
                # Các tham số cần thiết để tăng tốc độ khởi động
                chrome_options.add_argument('--no-first-run')
                chrome_options.add_argument('--no-default-browser-check')
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-extensions')
                # chrome_options.add_argument('--disable-popup-blocking')
                chrome_options.add_argument('--disable-notifications')
                chrome_options.add_argument('--disable-background-networking')
                chrome_options.add_argument('--disable-background-timer-throttling')
                chrome_options.add_argument('--disable-backgrounding-occluded-windows')

                # Tắt các popup, log và tối ưu performance
                prefs = {
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False,
                    "browser.startup.homepage": "about:blank",
                    "browser.startup.page": 0,
                    "profile.default_content_setting_values.notifications": 2,  # Tắt thông báo
                    "profile.exit_type": "Normal",  # Tránh thông báo crash
                    "browser.enable_automation": False,  # Tránh thông báo automation
                    "devtools.preferences.deviceDiscoveryEnabled": False,  # Tắt device discovery
                    "devtools.preferences.currentDockState": "\"undocked\"",  # Tránh mở DevTools
                    "download.prompt_for_download": False,  # Tắt hộp thoại download
                    "safebrowsing.enabled": False  # Tắt safe browsing warnings
                }
                chrome_options.add_experimental_option("prefs", prefs)

                # Tránh phát hiện automation và tắt logging
                chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                chrome_options.add_experimental_option('useAutomationExtension', False)

                # Enable Performance Logging
                chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

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

