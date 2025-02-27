from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
import cv2
import numpy as np
import pytesseract
from PIL import Image
import psutil
import subprocess
import time
import requests
import os

# Cấu hình đường dẫn tesseract cho macOS
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'  # Điều chỉnh nếu cần

# Đường dẫn lưu ảnh captcha
CAPTCHA_DIR = "captchas"
if not os.path.exists(CAPTCHA_DIR):
    os.makedirs(CAPTCHA_DIR)

# Thông tin đăng nhập
USERNAME = "0104232742"
PASSWORD = "0104232742"

def is_chrome_running_with_debug():
    try:
        response = requests.get('http://127.0.0.1:9222/json/version')
        return response.status_code == 200
    except:
        return False

def start_chrome_with_debug():
    chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    user_data_dir = os.path.expanduser('~/chrome-debug-profile')

    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)

    try:
        os.system("pkill -f 'Google Chrome'")
        time.sleep(1)

        subprocess.Popen([
            chrome_path,
            f'--user-data-dir={user_data_dir}',
            '--remote-debugging-port=9222',
            '--no-first-run',
            '--no-default-browser-check',
            'about:blank'
        ])

        time.sleep(3)
        return True
    except Exception as e:
        print(f"Lỗi khi khởi động Chrome: {e}")
        return False

def get_chrome_driver():
    if not is_chrome_running_with_debug():
        print("Khởi động Chrome với debug mode...")
        if not start_chrome_with_debug():
            print("Không thể khởi động Chrome debug mode")
            return None

    print("Kết nối vào Chrome debug mode...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Đã kết nối thành công vào Chrome")
        return driver
    except Exception as e:
        print(f"Lỗi khi kết nối Chrome: {e}")
        return None

def solve_captcha(captured_path, downloaded_path=None):
    try:
        # Thử với ảnh đã chụp
        text = solve_captcha(captured_path)
        if text:
            print(f"Captcha text từ ảnh chụp: {text}")
            return text

    except Exception as e:
        print(f"Lỗi khi giải captcha từ ảnh chụp: {e}")

    if downloaded_path:
        try:
            text = solve_captcha(downloaded_path)
            if text:
                print(f"Captcha text từ ảnh tải về: {text}")
                return text
        except Exception as e:
            print(f"Lỗi khi giải captcha từ ảnh tải về: {e}")

    return ""

def fill_login_info(driver):
    username_input = driver.find_element(By.ID, "form-username")
    username_input.clear()
    username_input.send_keys(USERNAME)
    password_input = driver.find_element(By.ID, "form-password")
    password_input.clear()
    password_input.send_keys(PASSWORD)
    print("Đã điền username và password")

def save_captcha_image(image_data, attempt, suffix="downloaded"):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    captcha_filename = os.path.join(CAPTCHA_DIR, f"captcha_{timestamp}_attempt_{attempt}_{suffix}.png")
    with open(captcha_filename, "wb") as f:
        f.write(image_data)
    return captcha_filename

def capture_captcha_image(element, attempt):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    captcha_filename = os.path.join(CAPTCHA_DIR, f"captcha_{timestamp}_attempt_{attempt}_captured.png")
    element.screenshot(captcha_filename)
    return captcha_filename

def navigate_to_bien_lai_list():
    try:
        wait = WebDriverWait(driver, 15)
        tra_cuu_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[.//p[contains(text(), 'Tra cứu')]]")))
        print("Đã tìm thấy mục 'Tra cứu', chuẩn bị nhấp...")
        actions = ActionChains(driver)
        actions.move_to_element(tra_cuu_link).click().perform()
        print("Đã nhấp vào 'Tra cứu'")

        driver.execute_script("document.querySelector('ul.nav-treeview').style.display = 'block';")
        print("Đã hiển thị menu con (display: block)")

        bien_lai_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/danh-sach-tra-cuu-bien-lai-dien-tu']")))
        print("Đã tìm thấy '2. Danh sách biên lai điện tử', chuẩn bị nhấp...")
        actions.move_to_element(bien_lai_link).click().perform()
        print("Đã nhấp vào '2. Danh sách biên lai điện tử'")

        # so_tk_input = wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
        # so_tk_input.clear()
        # so_tk_input.send_keys("106954206330")
        # print("Đã điền số tờ khai")

        # search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
        # search_button.click()
        # print("Đã nhấp nút tìm kiếm")

        # time.sleep(3)

    except Exception as e:
        print(f"Lỗi khi điều hướng và tìm kiếm biên lai: {e}")


def get_next_captcha_index():
    """Lấy index tiếp theo cho file captcha"""
    if not os.path.exists("training_captchas"):
        os.makedirs("training_captchas")
        return 0

    existing_files = [f for f in os.listdir("training_captchas") if f.startswith("captcha_") and f.endswith(".png")]
    if not existing_files:
        return 0

    indices = [int(f.split('_')[1].split('.')[0]) for f in existing_files]
    return max(indices) + 1

def save_captcha_and_label(driver, captcha_text):
    """Lưu ảnh captcha và label"""
    try:
        # Lấy index mới
        index = get_next_captcha_index()

        # Chụp ảnh captcha
        captcha_element = driver.find_element(By.ID, "CaptchaImage")
        image_path = f"training_captchas/captcha_{index}.png"
        captcha_element.screenshot(image_path)
        print(f"Đã lưu ảnh captcha: {image_path}")

        # Lưu label
        with open("training_captchas/labels.txt", "a") as f:
            f.write(f"captcha_{index}.png\t{captcha_text}\n")
        print(f"Đã lưu label: {captcha_text}")

        return True
    except Exception as e:
        print(f"Lỗi khi lưu captcha và label: {e}")
        return False

def get_file_info(driver, link_element):
    """Lấy thông tin từ row chứa link để đặt tên file"""
    try:
        # Tìm row chứa link (đi ngược lên từ thẻ a đến tr)
        row = link_element.find_element(By.XPATH, "./ancestor::tr")

        # Lấy tất cả các cột trong row
        columns = row.find_elements(By.TAG_NAME, "td")

        # Lấy giá trị từ cột thứ 5 và 6 (index 4 và 5)
        so_tien = columns[4].text.strip()
        ngay = columns[5].text.strip()

        # Chuyển đổi định dạng ngày từ DD/MM/YYYY thành DDMMYYYY
        ngay_formatted = ngay.replace('/', '')

        # Tạo tên file
        filename = f"{ngay_formatted}_{so_tien}.pdf"
        # Loại bỏ các ký tự không hợp lệ trong tên file
        filename = "".join(c for c in filename if c.isalnum() or c in ['_', '-', '.'])

        return filename
    except Exception as e:
        print(f"Lỗi khi lấy thông tin file: {e}")
        return None

def download_pdf(driver, link_element):
    try:
        # Lấy href từ thẻ a
        href = link_element.get_attribute('href')
        print(f"Link gốc: {href}")

        # Lấy tên file dựa trên thông tin từ bảng
        filename = get_file_info(driver, link_element)
        if not filename:
            # Nếu không lấy được thông tin, dùng tên file mặc định với mhd
            mhd = href.split('mhd=')[1].split('&')[0]
            filename = f"hoa_don_{mhd}.pdf"

        print(f"Tên file: {filename}")

        # Mở tab mới với URL của biên lai
        driver.execute_script(f"window.open('{href}', '_blank');")
        # Chuyển sang tab mới
        driver.switch_to.window(driver.window_handles[-1])
        # Đợi trang tải xong
        wait = WebDriverWait(driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Tạo thư mục để lưu PDF nếu chưa tồn tại
        if not os.path.exists("downloaded_pdfs"):
            os.makedirs("downloaded_pdfs")

        # Đường dẫn đầy đủ của file
        full_path = os.path.join("downloaded_pdfs", filename)

        # Sử dụng CDP để in trang thành PDF
        print_options = {
            'landscape': False,
            'displayHeaderFooter': False,
            'printBackground': True,
            'preferCSSPageSize': True,
        }

        # Thực hiện in PDF
        pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)

        # Xử lý base64 đúng cách
        import base64
        pdf_data = base64.b64decode(pdf['data'])

        # Lưu file PDF
        with open(full_path, 'wb') as f:
            f.write(pdf_data)

        print(f"Đã tải và lưu file: {full_path}")

        # Đóng tab hiện tại
        driver.close()

        # Chuyển về tab trước
        driver.switch_to.window(driver.window_handles[-1])

        return True

    except Exception as e:
        print(f"Lỗi khi tải PDF: {e}")
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[-1])
        except:
            pass
        return False

# Main execution
if __name__ == "__main__":
    try:
        driver = get_chrome_driver()
        if driver is None:
            raise Exception("Không thể khởi tạo Chrome driver")

        driver.execute_script("window.open('http://thuphi.haiphong.gov.vn:8222/dang-nhap', '_blank');")
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(("tag name", "body"))
        )

        login_success = False
        captcha_saved = False
        print("Vui lòng điền thông tin đăng nhập và captcha...")

        # Điền thông tin đăng nhập
        fill_login_info(driver)

        # Thêm JavaScript để theo dõi input captcha
        js_script = """
        window.captchaValue = '';

        window.getCaptchaValue = function() {
            return window.captchaValue;
        };

        const captchaInput = document.getElementById('CaptchaInputText');

        // Theo dõi khi blur
        captchaInput.addEventListener('blur', function() {
            window.captchaValue = this.value;
        });

        // Theo dõi khi nhập
        captchaInput.addEventListener('input', function() {
            if (this.value.length >= 5) {
                window.captchaValue = this.value;
            }
        });
        """
        driver.execute_script(js_script)

        # Đợi URL thay đổi sau khi user click đăng nhập
        try:
            current_url = driver.current_url

            while True:
                try:
                    # Kiểm tra giá trị captcha nếu chưa lưu
                    if not captcha_saved:
                        captcha_text = driver.execute_script("return window.getCaptchaValue()")
                        if captcha_text and len(captcha_text) >= 5:
                            # Lưu captcha khi có giá trị và chưa lưu trước đó
                            save_captcha_and_label(driver, captcha_text)
                            captcha_saved = True
                            print("Đã lưu thông tin captcha, bạn có thể click Đăng nhập")

                    # Kiểm tra URL có thay đổi không
                    if current_url != driver.current_url:
                        if driver.current_url == "http://thuphi.haiphong.gov.vn:8222/Home":
                            print("Đăng nhập thành công")
                            login_success = True
                            break
                    time.sleep(1)
                except Exception as e:
                    print(f"Lỗi khi kiểm tra: {e}")
                    continue

            if login_success:
                navigate_to_bien_lai_list()
                # Đợi và tìm tất cả các link xem biên lai với điều kiện cụ thể
                wait = WebDriverWait(driver, 10)
                links = wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    "a.color-blue.underline[href^='http://113.160.97.58:8224/Viewer/HoaDonViewer.aspx?mhd='][href$='iscd=1']"
                )))

                print(f"Tìm thấy {len(links)} biên lai")

                # Download từng biên lai
                for i, link in enumerate(links, 1):
                    if 'Xem' in link.text:
                        print(f"\nĐang tải PDF {i}/{len(links)}...")
                        if download_pdf(driver, link):
                            print("Tải thành công!")
                        else:
                            print("Tải thất bại!")
                        time.sleep(1)  # Đợi 1 giây giữa các lần tải

                print("\nĐã hoàn thành tải tất cả biên lai!")

        except Exception as e:
            print(f"Lỗi hoặc timeout khi đợi đăng nhập: {e}")

        # Giữ trình duyệt mở để kiểm tra
        input("Nhấn Enter để đóng trình duyệt...")
        driver.quit()

    except Exception as e:
        print(f"Lỗi khi truy cập trang web: {e}")
        if 'driver' in locals() and driver:
            driver.quit()