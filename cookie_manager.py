import os
import json
from selenium.webdriver.remote.webdriver import WebDriver

class CookieManager:
    COOKIES_DIR = 'cookies'
    TARGET_DOMAIN = "thuphi.haiphong.gov.vn"
    BASE_URL = "http://thuphi.haiphong.gov.vn:8222"

    def __init__(self):
        if not os.path.exists(self.COOKIES_DIR):
            os.makedirs(self.COOKIES_DIR)

    @staticmethod
    def save_cookies(driver: WebDriver, username: str) -> bool:
        """Lưu cookies cho username"""
        try:
            cookies = driver.get_cookies()
            if not os.path.exists(CookieManager.COOKIES_DIR):
                os.makedirs(CookieManager.COOKIES_DIR)
            with open(f'{CookieManager.COOKIES_DIR}/{username}.cookies', 'w') as f:
                json.dump(cookies, f)
            return True
        except Exception as e:
            print(f"Lỗi khi lưu cookies: {e}")
            return False

    @staticmethod
    def load_cookies(driver: WebDriver, username: str) -> bool:
        """Load cookies cho username"""
        try:
            cookie_path = f'{CookieManager.COOKIES_DIR}/{username}.cookies'
            if not os.path.exists(cookie_path) or not os.path.exists(CookieManager.COOKIES_DIR):
                return False

            with open(cookie_path, 'r') as f:
                cookies = json.load(f)

            # Truy cập trang trước khi add cookies
            driver.get(CookieManager.BASE_URL)
            for cookie in cookies:
                driver.add_cookie(cookie)
            return True
        except Exception as e:
            print(f"Lỗi khi load cookies: {e}")
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