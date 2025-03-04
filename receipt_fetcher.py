from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

import platform
import requests
import subprocess
import time
import os
import base64
from utils import send_notification, get_download_directory
from extract_info import update_last_row_sheet

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from google_drive_utils import upload_file_to_drive

def initialize_chrome():
    """Khởi tạo Chrome và mở trang web"""
    try:
        send_notification("Đang khởi tạo Chrome driver...", "info")

        # Xác định đường dẫn profile mặc định của Chrome
        if platform.system() == 'Windows':
            default_profile = os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data')
        else:  # macOS
            default_profile = os.path.expanduser('~/Library/Application Support/Google/Chrome')

        # Xác định đường dẫn Chrome
        if platform.system() == 'Windows':
            chrome_path = 'C:\\Program Files\\Google Chrome\\chrome.exe'
            if not os.path.exists(chrome_path):
                chrome_path = 'C:\\Program Files (x86)\\Google Chrome\\chrome.exe'
        else:  # macOS
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

        # Kiểm tra xem Chrome có đang chạy với debug port không
        chrome_running = False
        try:
            response = requests.get('http://127.0.0.1:9222/json/version')
            if response.status_code == 200:
                chrome_running = True
                send_notification("Đã tìm thấy Chrome đang chạy với debug port", "info")
        except:
            send_notification("Khởi động Chrome mới với debug port...", "info")

        if not chrome_running:
            # Khởi động Chrome mới mà không cần tắt các instance hiện tại
            subprocess.Popen([
                chrome_path,
                f'--user-data-dir={default_profile}',
                '--remote-debugging-port=9222',
                '--no-first-run',
                '--no-default-browser-check',
                '--start-maximized',
                '--disable-gpu',
                '--disable-dev-shm-usage',
            ])
            time.sleep(3)  # Đợi Chrome khởi động

        # Kết nối với Chrome debug port
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        service = Service(ChromeDriverManager().install())

        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            send_notification("Đã kết nối với Chrome thành công", "success")
            return driver
        except Exception as e:
            error_message = f"Lỗi khi kết nối với Chrome: {str(e)}"
            send_notification(error_message, "error")
            return None

    except Exception as e:
        error_message = f"Lỗi khi khởi tạo Chrome: {str(e)}"
        send_notification(error_message, "error")
        return None

def process_download(driver, username, so_tk=None, download_status=None):
    """Xử lý quá trình tải biên lai"""
    try:
        # Lưu handle của tab hiện tại
        current_handle = driver.current_window_handle
        actions = ActionChains(driver)

        # Mở trang đăng nhập trong tab mới
        driver.execute_script("window.open('http://thuphi.haiphong.gov.vn:8222/dang-nhap', '_blank');")
        # Đăng nhập
        if fill_login_info(driver, username, username):
            send_notification("Đăng nhập thành công", "success")
        else:
            raise Exception("Không thể đăng nhập")

        # Thêm script theo dõi captcha
        js_script = """
        window.captchaValue = '';
        window.getCaptchaValue = function() {
            return window.captchaValue;
        };
        const captchaInput = document.getElementById('CaptchaInputText');
        if (captchaInput) {
            captchaInput.addEventListener('blur', function() {
                window.captchaValue = this.value;
            });
            captchaInput.addEventListener('input', function() {
                if (this.value.length >= 5) {
                    window.captchaValue = this.value;
                }
            });
        }
        """
        driver.execute_script(js_script)

        # Đợi đăng nhập thành công và lưu captcha
        current_url = driver.current_url
        timeout = time.time() + 60  # timeout 60 giây
        captcha_saved = False
        login_success = False

        while time.time() < timeout:
            try:
                if not captcha_saved:
                    captcha_text = driver.execute_script("return window.getCaptchaValue()")
                    if captcha_text and len(captcha_text) >= 5:
                        save_captcha_and_label(driver, captcha_text)
                        captcha_saved = True

                if current_url != driver.current_url:
                    if driver.current_url == "http://thuphi.haiphong.gov.vn:8222/Home":
                        login_success = True
                        break
            except Exception as e:
                continue

        if not login_success:
            raise Exception("Đăng nhập không thành công sau 60 giây")

        # Truy cập trực tiếp trang danh sách biên lai
        wait = WebDriverWait(driver, 20)
        bien_lai_url = "http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu"
        driver.get(bien_lai_url)
        send_notification("Đang chuyển đến trang danh sách biên lai...", "info")

        # Nếu có số tờ khai, thực hiện tìm kiếm
        if so_tk:
            try:
                time.sleep(3)  # Đợi trang load xong
                so_tk_input = wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
                so_tk_input.clear()
                so_tk_input.send_keys(so_tk)
                send_notification(f"Đã điền số tờ khai: {so_tk}")

                search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                # Hover và click vào nút tìm kiếm
                actions.move_to_element(search_button).perform()
                time.sleep(1)
                actions.click().perform()
                send_notification("Đã nhấp nút tìm kiếm")

                time.sleep(3)  # Đợi kết quả tìm kiếm
            except Exception as e:
                send_notification(f"Lỗi khi tìm kiếm theo số tờ khai: {str(e)}", "error")
                raise

        # Tìm các link biên lai
        links = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            "a.color-blue.underline[href^='http://113.160.97.58:8224/Viewer/HoaDonViewer.aspx?mhd='][href$='iscd=1']"
        )))

        if not links:
            send_notification("Không tìm thấy biên lai nào", "warning")
            return False

        total_links = len(links)
        send_notification(f"Tìm thấy {total_links} biên lai", "info")

        if download_status:
            download_status['total'] = total_links

        for i, link in enumerate(links, 1):
            if 'Xem' in link.text:
                if download_status:
                    download_status['current'] = i
                send_notification(f"Đang tải biên lai {i}/{total_links}", "info")

                if download_pdf(driver, link):
                    if download_status:
                        download_status['success'] += 1
                    send_notification(f"Tải thành công biên lai {i}/{total_links}", "success")
                else:
                    if download_status:
                        download_status['failed'] += 1
                    send_notification(f"Tải thất bại biên lai {i}/{total_links}", "error")
                time.sleep(1)

        if download_status:
            download_status['status'] = 'completed'

        success_rate = (download_status['success'] / total_links) * 100 if total_links > 0 else 0
        send_notification(
            f"Hoàn tất tải xuống: {download_status['success']}/{total_links} biên lai thành công ({success_rate:.1f}%)",
            "success" if success_rate > 90 else "warning"
        )

        # Lưu handle của tất cả tabs
        all_handles = driver.window_handles
        localhost_handle = None

        # Tìm và đóng tab biên lai, đồng thời tìm tab localhost
        for handle in all_handles[:]:  # Dùng copy của list để tránh lỗi khi xóa phần tử
            driver.switch_to.window(handle)
            current_url = driver.current_url

            if "http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu" in current_url:
                driver.close()
            elif "http://localhost:8080" in current_url:
                localhost_handle = handle

        # Chuyển về tab localhost nếu tìm thấy
        if localhost_handle and localhost_handle in driver.window_handles:
            driver.switch_to.window(localhost_handle)
            send_notification("Đã trở về trang chủ", "info")
        return True
    except Exception as e:
        error_msg = f"Lỗi: {str(e)}"
        print(error_msg)
        send_notification(error_msg, "error")
        if download_status:
            download_status['status'] = 'error'
        return False

def fill_login_info(driver, username, password, max_retries=3):
    """Điền thông tin đăng nhập với retry và explicit wait"""
    wait = WebDriverWait(driver, 20)  # Đợi tối đa 10 giây
    retry_count = 0
    login_url = "http://thuphi.haiphong.gov.vn:8222/dang-nhap"

    while retry_count < max_retries:
        try:
            # Kiểm tra URL hiện tại
            current_url = driver.current_url
            if current_url != login_url:
                print(f"URL hiện tại không phải trang đăng nhập: {current_url}")
                # Tìm tab có URL đăng nhập
                login_tab_found = False
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    if driver.current_url == login_url:
                        print("Đã tìm thấy tab đăng nhập")
                        login_tab_found = True
                        break

                if not login_tab_found:
                    print("Không tìm thấy tab đăng nhập")
                    return False

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
                driver.get(login_url)  # Refresh về trang đăng nhập
                time.sleep(2)
            else:
                print(f"Lỗi sau {max_retries} lần thử: {str(e)}")
                raise Exception(f"Không thể điền thông tin đăng nhập sau {max_retries} lần thử")

def navigate_to_bien_lai_list(driver, so_tk=None):
    """Điều hướng đến trang danh sách biên lai"""
    try:
        wait = WebDriverWait(driver, 15)
        actions = ActionChains(driver)

        # Tìm và hover vào menu Tra cứu
        tra_cuu_link = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[.//p[contains(text(), 'Tra cứu')]]")
        ))
        send_notification("Đã tìm thấy mục 'Tra cứu', chuẩn bị hover...")

        # Hover vào menu Tra cứu
        actions.move_to_element(tra_cuu_link).perform()
        time.sleep(1)  # Đợi animation hover
        send_notification("Đã hover vào 'Tra cứu'")

        # Click vào menu Tra cứu
        actions.click().perform()
        send_notification("Đã nhấp vào 'Tra cứu'")

        # Đợi và mở rộng menu con
        menu_treeview = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.nav-treeview")))
        driver.execute_script("arguments[0].style.display = 'block'; arguments[0].classList.add('show');", menu_treeview)
        send_notification("Đã hiển thị menu con")
        time.sleep(1)  # Đợi animation menu

        # Tìm link biên lai
        bien_lai_link = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "a[href='/danh-sach-tra-cuu-bien-lai-dien-tu']")
        ))
        send_notification("Đã tìm thấy '2. Danh sách biên lai điện tử', chuẩn bị hover...")

        # Hover và click vào link biên lai
        actions.move_to_element(bien_lai_link).perform()
        time.sleep(1)  # Đợi animation hover
        send_notification("Đã hover vào link biên lai")

        actions.click().perform()
        send_notification("Đã nhấp vào '2. Danh sách biên lai điện tử'")

        # Nếu có số tờ khai, thực hiện tìm kiếm
        if so_tk:
            try:
                time.sleep(3)  # Đợi trang load xong
                so_tk_input = wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
                so_tk_input.clear()
                so_tk_input.send_keys(so_tk)
                send_notification(f"Đã điền số tờ khai: {so_tk}")

                search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                # Hover và click vào nút tìm kiếm
                actions.move_to_element(search_button).perform()
                time.sleep(0.5)
                actions.click().perform()
                send_notification("Đã nhấp nút tìm kiếm")

                time.sleep(3)  # Đợi kết quả tìm kiếm
            except Exception as e:
                send_notification(f"Lỗi khi tìm kiếm theo số tờ khai: {str(e)}", "error")
                raise

    except Exception as e:
        send_notification(f"Lỗi khi điều hướng và tìm kiếm biên lai: {str(e)}", "error")
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
    """Lưu ảnh captcha và nhãn"""
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

def download_pdf(driver, link_element):
    """Tải file PDF và lưu vào Google Drive"""
    try:
        href = link_element.get_attribute('href')
        current_handle = driver.current_window_handle

        # Lấy thông tin từ bảng
        row = link_element.find_element(By.XPATH, "./ancestor::tr")
        columns = row.find_elements(By.TAG_NAME, "td")
        custom_no = columns[4].text.strip()
        ngay = columns[5].text.strip()
        invoice_no = columns[8].text.strip()

        # Format ngày và tên file
        ngay_formatted = ngay.replace('/', '')
        filename = f"CSHT_{invoice_no}.pdf"

        # Tải PDF
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

        # Upload lên Drive
        upload_result = upload_file_to_drive(
            file_content=pdf_data,
            filename=filename,
            parent_folder_date=ngay_formatted,
            custom_no=custom_no
        )

        if not upload_result['success']:
            raise Exception(f"Lỗi upload file: {upload_result.get('error')}")

        print(f"Đã tải file lên Google Drive: {upload_result['web_view_link']}")
        send_notification(f"Đã lưu file {filename} vào Google Drive", "success")

        driver.close()
        driver.switch_to.window(current_handle)
        return True

    except Exception as e:
        print(f"Lỗi khi tải PDF: {e}")
        send_notification(f"Lỗi khi tải file: {str(e)}", "error")
        return False

