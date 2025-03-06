import requests
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from receipt_fetcher import initialize_chrome, fill_login_info, collect_captcha_if_login, save_cookies, load_cookies, check_login_status

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_tokens(driver):
    """Lấy các token cần thiết sau khi đăng nhập"""
    try:
        # Truy cập trang tra cứu
        driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")
        time.sleep(2)

        # Lấy form token
        request_token_form = driver.find_element(By.NAME, "__RequestVerificationToken").get_attribute("value")

        # Lấy cookies
        cookies = driver.get_cookies()
        cookie_dict = {}

        for cookie in cookies:
            if cookie['name'] in ['SessionToken', 'ASP.NET_SessionId', '__RequestVerificationToken']:
                cookie_dict[cookie['name']] = cookie['value']

        return request_token_form, cookie_dict
    except Exception as e:
        logger.error(f"Lỗi khi lấy tokens: {str(e)}")
        return None, None

def main():
    tax_number = "0800470967"

    # Khởi tạo driver
    driver = initialize_chrome()
    if not driver:
        return

    def perform_login():
        driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
        if not fill_login_info(driver, tax_number, tax_number):
            return False
        login_success = collect_captcha_if_login(driver)
        if login_success:
            save_cookies(driver, tax_number)
        return login_success

    def handle_login():
        cookies_loaded = load_cookies(driver, tax_number)
        if cookies_loaded:
            driver.get("http://thuphi.haiphong.gov.vn:8222/Home")
            if not check_login_status(driver):
                return perform_login()
            logger.info("Đã đăng nhập lại bằng cookies")
            return True
        return perform_login()

    try:
        if not handle_login():
            raise Exception("Không thể đăng nhập")


        # Đợi login thành công và lấy tokens
        time.sleep(2)
        request_token_form, cookies = get_tokens(driver)

        if not request_token_form or not cookies:
            logger.error("Không thể lấy được tokens")
            return

        # Cập nhật headers và cookies
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Host": "thuphi.haiphong.gov.vn:8222",
            "Origin": "http://thuphi.haiphong.gov.vn:8222",
            "Pragma": "no-cache",
            "Referer": "http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu",
            "User-Agent": driver.execute_script("return navigator.userAgent"),
            "X-Requested-With": "XMLHttpRequest",
            "__RequestVerificationToken": request_token_form
        }

        # Chuẩn bị data request
        data = {
            "EinvoiceFrom": "0",
            "tu_ngay": "01/03/2025",
            "den_ngay": "06/03/2025",
            "ma_dn": tax_number,
            "so_tokhai": "106980540920",
            "pageNum": "1",
            "__RequestVerificationToken": request_token_form
        }

        # Gửi request
        url = "http://thuphi.haiphong.gov.vn:8222/DBienLaiThuPhi_TraCuu/GetListEinvoiceByMaDN/"
        response = requests.post(url, headers=headers, cookies=cookies, data=data)

        logger.info("\nHeaders: %s", headers)
        logger.info("\nCookies: %s", cookies)
        logger.info("\nData: %s", data)

        if response.status_code == 200:
            logger.info("\nPhản hồi thành công: %s", response.text)
        else:
            logger.error("\nYêu cầu thất bại với mã trạng thái %d", response.status_code)

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
