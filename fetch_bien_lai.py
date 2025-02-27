from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
import subprocess
import time
import requests
import os
import base64
import tkinter as tk
from tkinter import messagebox, simpledialog
import platform

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

def get_login_credentials():
    root = tk.Tk()
    root.withdraw()  # Ẩn cửa sổ chính của Tkinter

    while True:
        username = simpledialog.askstring("Đăng nhập", "Nhập mã số thuế:")
        if username is None:  # Người dùng bấm Cancel
            messagebox.showerror("Lỗi", "Bạn phải nhập mã số thuế để tiếp tục!")
            return None, None
        if not username.strip():  # Chuỗi rỗng
            messagebox.showerror("Lỗi", "Mã số thuế không được để trống!")
            continue
        if not username.strip().isdigit():  # Kiểm tra chỉ có số
            messagebox.showerror("Lỗi", "Mã số thuế chỉ được chứa số!")
            continue
        break

    # Loại bỏ khoảng trắng và trả về username làm password
    username = username.strip()
    return username, username

def start_chrome_with_debug():
    # Kiểm tra hệ điều hành
    if platform.system() == 'Windows':
        chrome_path = 'C:\\Program Files\\Google Chrome\\chrome.exe'
        if not os.path.exists(chrome_path):
            chrome_path = 'C:\\Program Files (x86)\\Google Chrome\\chrome.exe'
    else:  # macOS
        chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

    user_data_dir = os.path.expanduser('~/chrome-debug-profile')

    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)

    try:
        # Đóng Chrome hiện tại
        if platform.system() == 'Windows':
            os.system("taskkill /f /im chrome.exe")
        else:
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

def fill_login_info(driver, username, password):
    username_input = driver.find_element(By.ID, "form-username")
    username_input.clear()
    username_input.send_keys(username)
    password_input = driver.find_element(By.ID, "form-password")
    password_input.clear()
    password_input.send_keys(password)
    print("Đã điền username và password")

def navigate_to_bien_lai_list(driver, so_tk=None):
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

        # Nếu có số tờ khai, thực hiện tìm kiếm
        if so_tk:
            try:
                time.sleep(2)  # Đợi trang load xong
                so_tk_input = wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
                so_tk_input.clear()
                so_tk_input.send_keys(so_tk)
                print(f"Đã điền số tờ khai: {so_tk}")

                search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                search_button.click()
                print("Đã nhấp nút tìm kiếm")

                time.sleep(3)  # Đợi kết quả tìm kiếm
            except Exception as e:
                print(f"Lỗi khi tìm kiếm theo số tờ khai: {e}")
                raise

    except Exception as e:
        print(f"Lỗi khi điều hướng và tìm kiếm biên lai: {e}")
        raise

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
        index = get_next_captcha_index()
        captcha_element = driver.find_element(By.ID, "CaptchaImage")
        image_path = f"training_captchas/captcha_{index}.png"
        captcha_element.screenshot(image_path)
        print(f"Đã lưu ảnh captcha: {image_path}")

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
        row = link_element.find_element(By.XPATH, "./ancestor::tr")
        columns = row.find_elements(By.TAG_NAME, "td")
        so_tien = columns[4].text.strip()
        ngay = columns[5].text.strip()
        ngay_formatted = ngay.replace('/', '')
        filename = f"{ngay_formatted}_{so_tien}.pdf"
        filename = "".join(c for c in filename if c.isalnum() or c in ['_', '-', '.'])
        return filename
    except Exception as e:
        print(f"Lỗi khi lấy thông tin file: {e}")
        return None

def download_pdf(driver, link_element):
    try:
        href = link_element.get_attribute('href')
        print(f"Link gốc: {href}")

        filename = get_file_info(driver, link_element)
        if not filename:
            mhd = href.split('mhd=')[1].split('&')[0]
            filename = f"hoa_don_{mhd}.pdf"

        print(f"Tên file: {filename}")

        driver.execute_script(f"window.open('{href}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        wait = WebDriverWait(driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        if not os.path.exists("downloaded_pdfs"):
            os.makedirs("downloaded_pdfs")

        full_path = os.path.join("downloaded_pdfs", filename)

        print_options = {
            'landscape': False,
            'displayHeaderFooter': False,
            'printBackground': True,
            'preferCSSPageSize': True,
        }

        pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
        pdf_data = base64.b64decode(pdf['data'])

        with open(full_path, 'wb') as f:
            f.write(pdf_data)

        print(f"Đã tải và lưu file: {full_path}")

        driver.close()
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

if __name__ == "__main__":
    try:
        # Lấy thông tin đăng nhập
        username, password = get_login_credentials()
        if not username or not password:
            print("Không có thông tin đăng nhập!")
            exit()

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

        # Sử dụng username và password từ popup
        fill_login_info(driver, username, password)

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

        try:
            current_url = driver.current_url

            while True:
                try:
                    if not captcha_saved:
                        captcha_text = driver.execute_script("return window.getCaptchaValue()")
                        if captcha_text and len(captcha_text) >= 5:
                            save_captcha_and_label(driver, captcha_text)
                            captcha_saved = True
                            print("Đã lưu thông tin captcha, bạn có thể click Đăng nhập")

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
                navigate_to_bien_lai_list(driver, '')
                wait = WebDriverWait(driver, 10)
                links = wait.until(EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    "a.color-blue.underline[href^='http://113.160.97.58:8224/Viewer/HoaDonViewer.aspx?mhd='][href$='iscd=1']"
                )))

                print(f"Tìm thấy {len(links)} biên lai")

                for i, link in enumerate(links, 1):
                    if 'Xem' in link.text:
                        print(f"\nĐang tải PDF {i}/{len(links)}...")
                        if download_pdf(driver, link):
                            print("Tải thành công!")
                        else:
                            print("Tải thất bại!")
                        time.sleep(1)

                print("\nĐã hoàn thành tải tất cả biên lai!")

        except Exception as e:
            print(f"Lỗi hoặc timeout khi đợi đăng nhập: {e}")

        input("Nhấn Enter để đóng trình duyệt...")
        driver.quit()

    except Exception as e:
        print(f"Lỗi khi truy cập trang web: {e}")
        if 'driver' in locals() and driver:
            driver.quit()