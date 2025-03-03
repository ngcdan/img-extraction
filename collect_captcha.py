from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import psutil
import subprocess
import requests
import os
import time
from receipt_fetcher import initialize_chrome

def collect_captcha_samples(num_samples=1000):
    SAVE_DIR = "training_captchas"
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    driver = initialize_chrome()
    if driver is None:
        print("Không thể khởi tạo Chrome driver")
        return

    try:
        for i in range(num_samples):
            print(f"Đang thu thập mẫu thứ {i+1}/{num_samples}")

            # Mở trang login trong tab mới
            driver.execute_script("window.open('http://thuphi.haiphong.gov.vn:8222/dang-nhap', '_blank');")
            time.sleep(1)

            # Chuyển đến tab mới
            driver.switch_to.window(driver.window_handles[-1])

            # Đợi trang load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))

            # Lấy captcha
            captcha_element = driver.find_element(By.ID, "CaptchaImage")

            # Tải và lưu ảnh
            img_path = os.path.join(SAVE_DIR, f"captcha_{i}.png")
            captcha_element.screenshot(img_path)
            print(f"Đã lưu ảnh: {img_path}")

            # Đóng tab hiện tại
            driver.close()

            # Chuyển về tab đầu tiên
            driver.switch_to.window(driver.window_handles[0])

            # Delay ngẫu nhiên để tránh bị block
            time.sleep(2)

    except Exception as e:
        print(f"Lỗi trong quá trình thu thập: {e}")
    finally:
        print("Hoàn thành thu thập dữ liệu")
        # Không đóng driver để có thể kiểm tra
        input("Nhấn Enter để đóng trình duyệt...")
        driver.quit()

if __name__ == "__main__":
    try:
        num_samples = int(input("Nhập số lượng mẫu cần thu thập (mặc định 1000): ") or "1000")
        collect_captcha_samples(num_samples)
    except ValueError:
        print("Vui lòng nhập số hợp lệ")
        collect_captcha_samples(1000)