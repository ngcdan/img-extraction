import os
import json
import time
from selenium.webdriver.remote.webdriver import WebDriver

class CookieManager:
    COOKIES_DIR = 'cookies'
    TARGET_DOMAIN = "https://pus.customs.gov.vn"
    BASE_URL = "https://pus.customs.gov.vn"

    def __init__(self):
        if not os.path.exists(self.COOKIES_DIR):
            os.makedirs(self.COOKIES_DIR)

    @staticmethod
    def is_cookie_valid(cookie):
        """Kiểm tra tính hợp lệ của cookie"""
        current_timestamp = int(time.time())
        # Kiểm tra expiry
        if 'expiry' in cookie:
            if cookie['expiry'] <= current_timestamp:
                return False
        # Kiểm tra domain
        if 'domain' not in cookie or CookieManager.TARGET_DOMAIN not in cookie['domain']:
            return False
        return True

    @staticmethod
    def save_cookies(driver: WebDriver, username: str) -> bool:
        """Lưu cookies cho username"""
        try:
            cookies = driver.get_cookies()
            # Chỉ lưu cookies hợp lệ
            valid_cookies = [cookie for cookie in cookies if CookieManager.is_cookie_valid(cookie)]

            if not valid_cookies:
                print(f"Không có cookies hợp lệ để lưu cho {username}")
                return False

            if not os.path.exists(CookieManager.COOKIES_DIR):
                os.makedirs(CookieManager.COOKIES_DIR)

            with open(f'{CookieManager.COOKIES_DIR}/{username}.cookies', 'w') as f:
                json.dump(valid_cookies, f)
            return True
        except Exception as e:
            print(f"Lỗi khi lưu cookies: {str(e)}")
            return False

    @staticmethod
    def load_cookies(driver: WebDriver, username: str) -> bool:
        """Load cookies cho username"""
        try:
            cookie_path = f'{CookieManager.COOKIES_DIR}/{username}.cookies'
            if not os.path.exists(cookie_path):
                return False

            with open(cookie_path, 'r') as f:
                cookies = json.load(f)

            # Lọc cookies hết hạn
            valid_cookies = [cookie for cookie in cookies if CookieManager.is_cookie_valid(cookie)]

            if not valid_cookies:
                print(f"Không tìm thấy cookies hợp lệ cho {username}")
                return False

            # Truy cập trang trước khi add cookies
            driver.get(CookieManager.BASE_URL)

            # Xóa cookies hiện tại
            driver.delete_all_cookies()

            # Thêm cookies mới
            for cookie in valid_cookies:
                try:
                    # Loại bỏ trường 'expiry' nếu là None
                    if 'expiry' in cookie and cookie['expiry'] is None:
                        del cookie['expiry']
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"Lỗi khi thêm cookie: {str(e)}")
                    return False

            return True
        except Exception as e:
            print(f"Lỗi khi load cookies: {str(e)}")
            return False

    @staticmethod
    def clear_all_cookies_and_sessions(driver: WebDriver) -> bool:
        """Xóa cookies và sessions của domain thuphi.haiphong.gov.vn"""
        try:
            # Lấy tất cả cookies hiện tại
            all_cookies = driver.get_cookies()

            # Chỉ xóa cookies của domain cần thiết
            for cookie in all_cookies:
                if CookieManager.TARGET_DOMAIN in cookie.get('domain', ''):
                    driver.delete_cookie(cookie['name'])

            # Xóa localStorage và sessionStorage chỉ khi đang ở domain cần thiết
            current_url = driver.current_url
            if CookieManager.TARGET_DOMAIN in current_url:
                driver.execute_script("""
                    window.localStorage.clear();
                    window.sessionStorage.clear();
                """)
                # Refresh trang để đảm bảo các thay đổi có hiệu lực
                driver.refresh()

            return True
        except Exception as e:
            print(f"Lỗi khi xóa cookies và sessions: {str(e)}")
            return False
