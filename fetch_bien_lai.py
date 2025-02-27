from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import subprocess
import time
import requests
import os
import base64
import tkinter as tk
from tkinter import messagebox, simpledialog
import platform
from datetime import datetime

def is_chrome_running_with_debug():
    """Kiểm tra xem Chrome có đang chạy với debug port không"""
    try:
        response = requests.get('http://127.0.0.1:9222/json/version')
        return response.status_code == 200
    except:
        return False

def get_chrome_driver():
    """Khởi tạo hoặc kết nối với Chrome driver"""

    # Kiểm tra xem Chrome có đang chạy với debug port không
    if is_chrome_running_with_debug():
        print("Tìm thấy Chrome đang chạy với debug port, đang kết nối...")
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        try:
            driver = webdriver.Chrome(options=chrome_options)
            print("Đã kết nối thành công với Chrome đang chạy")
            return driver
        except Exception as e:
            print(f"Không thể kết nối với Chrome đang chạy: {e}")

    print("Không tìm thấy Chrome với debug port, khởi động Chrome mới...")

    # Xác định đường dẫn Chrome
    if platform.system() == 'Windows':
        chrome_path = 'C:\\Program Files\\Google Chrome\\chrome.exe'
        if not os.path.exists(chrome_path):
            chrome_path = 'C:\\Program Files (x86)\\Google Chrome\\chrome.exe'
    else:  # macOS
        chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

    # Tạo thư mục profile
    user_data_dir = os.path.expanduser('~/chrome-debug-profile')
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)

    # Đóng tất cả các tiến trình Chrome hiện tại
    if platform.system() == 'Windows':
        os.system('taskkill /f /im chrome.exe')
    else:
        os.system("pkill -f 'Google Chrome'")
    time.sleep(2)

    # Khởi động Chrome với debug port
    try:
        subprocess.Popen([
            chrome_path,
            f'--user-data-dir={user_data_dir}',
            '--remote-debugging-port=9222',
            '--no-first-run',
            '--no-default-browser-check',
            '--start-maximized',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-plugins',
            '--disable-extensions',
            '--disable-default-apps',
            'about:blank'
        ])
        print("Đã khởi động Chrome với debug port")
        time.sleep(3)  # Đợi Chrome khởi động

        # Kết nối với Chrome vừa khởi động
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=chrome_options)
        print("Đã kết nối thành công với Chrome")
        return driver

    except Exception as e:
        print(f"Lỗi khi khởi động và kết nối Chrome: {e}")
        return None


# Cập nhật phần mở trang đăng nhập
def navigate_to_login(driver):
    """Mở trang đăng nhập với xử lý lỗi"""
    try:
        # Đóng các tab cũ nếu có
        if len(driver.window_handles) > 1:
            for handle in driver.window_handles[1:]:
                driver.switch_to.window(handle)
                driver.close()
            driver.switch_to.window(driver.window_handles[0])

        # Mở trang đăng nhập trong tab mới
        driver.execute_script("window.open('http://thuphi.haiphong.gov.vn:8222/dang-nhap', '_blank');")
        time.sleep(1)

        # Chuyển đến tab mới
        driver.switch_to.window(driver.window_handles[-1])

        # Đợi cho trang load xong
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        return True

    except Exception as e:
        print(f"Lỗi khi mở trang đăng nhập: {str(e)}")
        raise

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

def fill_login_info(driver, username, password, max_retries=3):
    """Điền thông tin đăng nhập với retry và explicit wait"""
    wait = WebDriverWait(driver, 10)  # Đợi tối đa 10 giây
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Đợi cho đến khi form login xuất hiện
            wait.until(EC.presence_of_element_located((By.ID, "form-username")))
            wait.until(EC.element_to_be_clickable((By.ID, "form-username")))

            # Tìm và điền username
            username_input = driver.find_element(By.ID, "form-username")
            username_input.clear()
            username_input.send_keys(username)
            print("Đã điền username")

            # Đợi và điền password
            wait.until(EC.presence_of_element_located((By.ID, "form-password")))
            password_input = driver.find_element(By.ID, "form-password")
            password_input.clear()
            password_input.send_keys(password)
            print("Đã điền password")

            return True

        except (TimeoutException, NoSuchElementException) as e:
            retry_count += 1
            print(f"Lần thử {retry_count}: Không tìm thấy form đăng nhập. Đang thử lại...")

            if retry_count < max_retries:
                # Refresh trang và đợi 2 giây trước khi thử lại
                driver.refresh()
                time.sleep(2)
            else:
                print(f"Lỗi sau {max_retries} lần thử: {str(e)}")
                raise Exception(f"Không thể điền thông tin đăng nhập sau {max_retries} lần thử")

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

        time.sleep(2)

        bien_lai_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href='/danh-sach-tra-cuu-bien-lai-dien-tu']")))
        print("Đã tìm thấy '2. Danh sách biên lai điện tử', chuẩn bị nhấp...")
        actions.move_to_element(bien_lai_link).click().perform()
        print("Đã nhấp vào '2. Danh sách biên lai điện tử'")

        # Nếu có số tờ khai, thực hiện tìm kiếm
        if so_tk:
            try:
                time.sleep(3)  # Đợi trang load xong
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
        so_tk = columns[4].text.strip()
        ngay = columns[5].text.strip()
        ngay_formatted = ngay.replace('/', '')
        filename = f"{so_tk}.pdf"
        filename = "".join(c for c in filename if c.isalnum() or c in ['_', '-', '.'])
        return filename
    except Exception as e:
        print(f"Lỗi khi lấy thông tin file: {e}")
        return None

def download_pdf(driver, link_element):
    try:
        href = link_element.get_attribute('href')
        # Tìm row chứa link (đi ngược lên từ thẻ a đến tr)
        row = link_element.find_element(By.XPATH, "./ancestor::tr")

        # Lấy tất cả các cột trong row
        columns = row.find_elements(By.TAG_NAME, "td")

        # Lấy giá trị từ cột thứ 5 và 6 (index 4 và 5)
        so_tk = columns[4].text.strip()
        ngay = columns[5].text.strip()

        # Chuyển đổi định dạng ngày từ DD/MM/YYYY thành DDMMYYYY
        ngay_formatted = ngay.replace('/', '')

        # Tạo tên file
        filename = get_file_info(driver, link_element)

        # Tạo cấu trúc thư mục
        base_dir = "downloaded_pdfs"
        date_dir = os.path.join(base_dir, ngay_formatted)
        so_tk_dir = os.path.join(date_dir, so_tk)

        # Tạo các thư mục nếu chưa tồn tại
        for directory in [base_dir, date_dir, so_tk_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Đã tạo thư mục: {directory}")

        # Đường dẫn đầy đủ của file (trong thư mục số tờ khai)
        full_path = os.path.join(so_tk_dir, filename)

        # Kiểm tra nếu file đã tồn tại
        if os.path.exists(full_path):
            base_name = os.path.splitext(filename)[0]
            counter = 1
            while os.path.exists(full_path):
                new_filename = f"{base_name}_{counter}.pdf"
                full_path = os.path.join(so_tk_dir, new_filename)
                counter += 1

        print(f"Tên file: {os.path.basename(full_path)}")
        print(f"Đường dẫn: {full_path}")

        # Mở và tải PDF
        driver.execute_script(f"window.open('{href}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        wait = WebDriverWait(driver, 5)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        print_options = {
            'landscape': False,
            'displayHeaderFooter': False,
            'printBackground': True,
            'preferCSSPageSize': True,
        }

        pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
        pdf_data = base64.b64decode(pdf['data'])

        # Lưu file
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