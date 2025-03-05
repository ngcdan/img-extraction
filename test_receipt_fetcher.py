import unittest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from receipt_fetcher import (
    initialize_chrome,
    save_cookies,
    load_cookies,
    fill_login_info,
    download_pdf,
    main,
    check_login_status
)

class TestReceiptFetcher(unittest.TestCase):
    def test_full_workflow(self):
        """Test toàn bộ luồng từ đăng nhập đến tải PDF"""
        username = "0901067514"
        password = "0901067514"
        so_tk = "307154371000"
        driver = None

        try:
            # 1. Khởi tạo driver
            print("1. Khởi tạo Chrome driver...")
            driver = initialize_chrome()
            self.assertIsNotNone(driver, "Không thể khởi tạo Chrome driver")

            # 2. Thử load cookies có sẵn
            print("2. Kiểm tra cookies...")
            cookies_loaded = load_cookies(driver, username)

            # 3. Đăng nhập
            print("3. Tiến hành đăng nhập...")
            if cookies_loaded:
                if not check_login_status(driver):
                    driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
                    self.assertTrue(
                        fill_login_info(driver, username, password),
                        "Đăng nhập thất bại"
                    )
                    save_cookies(driver, username)
            else:
                driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
                self.assertTrue(
                    fill_login_info(driver, username, password),
                    "Đăng nhập thất bại"
                )
                save_cookies(driver, username)

            # 4. Truy cập trang danh sách biên lai
            print("4. Truy cập danh sách biên lai...")
            driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")

            # 5. Tìm và tải các biên lai
            print("5. Tìm kiếm các biên lai...")
            wait = WebDriverWait(driver, 20)
            links = wait.until(EC.presence_of_all_elements_located((
                By.CSS_SELECTOR,
                "a.color-blue.underline[href^='http://113.160.97.58:8224/Viewer/HoaDonViewer.aspx?mhd='][href$='iscd=1']"
            )))

            self.assertGreater(len(links), 0, "Không tìm thấy biên lai nào")

            # 6. Tải PDF
            print(f"6. Tải PDF (tìm thấy {len(links)} biên lai)...")
            success_count = 0
            for i, link in enumerate(links, 1):
                if 'Xem' in link.text:
                    print(f"   Đang tải biên lai {i}/{len(links)}")
                    if download_pdf(driver, link):
                        success_count += 1
                        print(f"   ✓ Tải thành công biên lai {i}")
                    else:
                        print(f"   ✗ Tải thất bại biên lai {i}")

            print(f"\nKết quả: Tải thành công {success_count}/{len(links)} biên lai")
            self.assertGreater(success_count, 0, "Không tải được biên lai nào")

        except Exception as e:
            self.fail(f"Test thất bại: {str(e)}")

        finally:
            if driver:
                driver.quit()

if __name__ == '__main__':
    unittest.main(verbosity=2)