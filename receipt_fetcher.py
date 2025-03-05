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
import json
from utils import send_notification, get_download_directory
from extract_info import update_last_row_sheet

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
from google_drive_utils import upload_file_to_drive, DriveService

import os
import sys
from datetime import datetime
from typing import List, Dict, Any
from pdfminer.high_level import extract_text
from utils import send_notification
from google_sheet_utils import append_to_google_sheet_new

# Import các hàm helper từ extract_info.py
from extract_info import (
    split_sections,
    extract_header_info,
    convert_price_to_number
)

def batch_process_files(files: List[str]) -> Dict[str, Any]:
    """
    Xử lý nhiều file PDF cùng lúc, trích xuất thông tin header và ghi vào Google Sheet

    Args:
        files: List of file paths to process

    Returns:
        dict: Kết quả xử lý với thông tin success/error
    """
    try:
        # Khởi tạo Chrome driver một lần cho toàn bộ quá trình
        driver = initialize_chrome()
        if not driver:
            raise Exception("Không thể khởi tạo Chrome driver")

        # Danh sách lưu kết quả trích xuất
        extracted_results = []
        drive_upload_results = []

        for file_path in files:
            try:
                # Kiểm tra file tồn tại
                if not os.path.exists(file_path):
                    print(f"File không tồn tại: {file_path}")
                    continue

                # Đọc và trích xuất text từ PDF
                with open(file_path, 'rb') as pdf_file:
                    file_content = pdf_file.read()

                text = extract_text(io.BytesIO(file_content))
                sections = split_sections(text)

                if not sections:
                    print(f"Không thể phân tích file: {file_path}")
                    continue

                # Trích xuất thông tin header
                header_info = extract_header_info(sections['header'])
                if header_info:
                    # Thêm metadata
                    header_info.update({
                        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source_file': os.path.basename(file_path)
                    })

                    # Upload file lên Drive với cấu trúc thư mục
                    ngay_formatted = header_info['date'].replace('/', '') if header_info.get('date') else datetime.now().strftime('%d%m%Y')

                    upload_result = upload_file_to_drive(
                        file_content=file_content,
                        filename=os.path.basename(file_path),
                        parent_folder_date=ngay_formatted,
                        custom_no=header_info.get('customs_number', '')
                    )

                    if upload_result['success']:
                        header_info['drive_file_path'] = upload_result['file_path']
                        drive_upload_results.append({
                            'file': os.path.basename(file_path),
                            'status': 'success',
                            'path': upload_result['file_path']
                        })
                    else:
                        drive_upload_results.append({
                            'file': os.path.basename(file_path),
                            'status': 'error',
                            'error': upload_result.get('error', 'Unknown error')
                        })

                    extracted_results.append(header_info)

            except Exception as e:
                error_msg = f"Lỗi xử lý file {file_path}: {str(e)}"
                print(error_msg)
                send_notification(error_msg, "error")
                continue

        if not extracted_results:
            raise ValueError("Không có dữ liệu được trích xuất từ các file")

        # Sắp xếp kết quả theo tax_number
        sorted_results = sorted(
            extracted_results,
            key=lambda x: x.get('tax_number', '0')
        )
        print(json.dumps(sorted_results, indent=4, ensure_ascii=False))

        # Xử lý download cho từng kết quả
        download_success = 0
        download_error = 0

        for result in sorted_results:
            try:
                tax_number = result.get('tax_number')
                customs_number = result.get('customs_number')

                if tax_number and customs_number:
                    download_status = {'current': 0, 'total': 1, 'success': 0}
                    if process_download(
                        driver=driver,
                        username=tax_number,
                        so_tk=customs_number,
                        download_status=download_status
                    ):
                        download_success += 1
                        send_notification(
                            f"Đã tải thành công biên lai cho MST {tax_number}",
                            "success"
                        )
                    else:
                        download_error += 1
                        send_notification(
                            f"Lỗi tải biên lai cho MST {tax_number}",
                            "error"
                        )
            except Exception as e:
                error_msg = f"Lỗi khi tải biên lai: {str(e)}"
                print(error_msg)
                send_notification(error_msg, "error")
                download_error += 1

        # Ghi từng record vào Google Sheet
        sheet_success = 0
        sheet_error = 0

        for result in sorted_results:
            try:
                if append_to_google_sheet_new(result):
                    sheet_success += 1
                    send_notification(
                        f"Đã ghi thành công dữ liệu từ file {result['source_file']}",
                        "success"
                    )
                else:
                    sheet_error += 1
                    send_notification(
                        f"Lỗi ghi dữ liệu từ file {result['source_file']}",
                        "error"
                    )
            except Exception as e:
                error_msg = f"Lỗi khi ghi dữ liệu vào Sheet: {str(e)}"
                print(error_msg)
                send_notification(error_msg, "error")
                sheet_error += 1

        # Đóng driver sau khi hoàn thành
        try:
            driver.quit()
        except:
            pass

        return {
            'success': True,
            'message': f'Đã xử lý {len(files)} file',
            'stats': {
                'total_files': len(files),
                'processed': len(extracted_results),
                'download_success': download_success,
                'download_error': download_error,
                'sheet_success': sheet_success,
                'sheet_error': sheet_error,
                'drive_uploads': drive_upload_results
            }
        }

    except Exception as e:
        error_msg = f"Lỗi trong quá trình xử lý batch: {str(e)}"
        print(error_msg)
        send_notification(error_msg, "error")
        # Đảm bảo đóng driver trong trường hợp lỗi
        try:
            if driver:
                driver.quit()
        except:
            pass
        return {
            'success': False,
            'error': error_msg
        }

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

def save_cookies(driver, username):
    """Lưu cookies cho username"""
    try:
        cookies = driver.get_cookies()
        if not os.path.exists('cookies'):
            os.makedirs('cookies')
        with open(f'cookies/{username}.cookies', 'w') as f:
            json.dump(cookies, f)
        return True
    except Exception as e:
        print(f"Lỗi khi lưu cookies: {e}")
        return False

def load_cookies(driver, username):
    """Load cookies cho username"""
    try:
        if not os.path.exists(f'cookies/{username}.cookies'):
            return False
        with open(f'cookies/{username}.cookies', 'r') as f:
            cookies = json.load(f)
        # Truy cập trang trước khi add cookies
        driver.get("http://thuphi.haiphong.gov.vn:8222")
        for cookie in cookies:
            driver.add_cookie(cookie)
        return True
    except Exception as e:
        print(f"Lỗi khi load cookies: {e}")
        return False

def check_login_status(driver):
    """Kiểm tra trạng thái đăng nhập"""
    try:
        driver.get("http://thuphi.haiphong.gov.vn:8222/Home")
        time.sleep(2)
        # Kiểm tra URL sau khi chuyển hướng
        return "dang-nhap" not in driver.current_url
    except:
        return False

def collect_captcha_if_login(driver):
    """Thu thập captcha nếu cần đăng nhập"""
    try:
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
            except Exception:
                continue
            time.sleep(0.5)

        return login_success
    except Exception as e:
        print(f"Lỗi khi thu thập captcha: {e}")
        return False

def process_download(driver, username, so_tk=None, download_status=None):
    """Xử lý quá trình tải biên lai"""
    try:
        # Mở tab mới
        driver.execute_script("window.open('');")
        # Chuyển đến tab mới (tab cuối cùng trong danh sách)
        driver.switch_to.window(driver.window_handles[-1])

        # Thử dùng cookies đã lưu
        cookies_loaded = load_cookies(driver, username)
        if cookies_loaded:
            # Kiểm tra trạng thái đăng nhập
            if check_login_status(driver):
                send_notification("Đã đăng nhập lại bằng cookies", "success")
            else:
                # Nếu cookies không còn hiệu lực, đăng nhập lại
                driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
                if not fill_login_info(driver, username, username):
                    raise Exception("Không thể đăng nhập")
                if not collect_captcha_if_login(driver):
                    raise Exception("Đăng nhập không thành công sau 60 giây")
                save_cookies(driver, username)
        else:
            # Đăng nhập thông thường nếu không có cookies
            driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
            if fill_login_info(driver, username, username):
                if not collect_captcha_if_login(driver):
                    raise Exception("Đăng nhập không thành công sau 60 giây")
                send_notification("Đăng nhập thành công", "success")
                save_cookies(driver, username)
            else:
                raise Exception("Không thể đăng nhập")

        # Truy cập trang danh sách biên lai
        wait = WebDriverWait(driver, 20)
        driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")
        send_notification("Đang chuyển đến trang danh sách biên lai...", "info")

        # Đợi và tìm các link biên lai
        links = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR,
            "a.color-blue.underline[href^='http://113.160.97.58:8224/Viewer/HoaDonViewer.aspx?mhd='][href$='iscd=1']"
        )))

        if not links:
            send_notification("Không tìm thấy biên lai nào", "warning")
            return False

        total_links = len(links)
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
                # time.sleep(1)

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

        # Kiểm tra file đã tồn tại trong Drive chưa
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_folder_id = drive_instance.root_folder_id

        # Tìm folder ngày
        date_query = f"name = '{ngay_formatted}' and mimeType = 'application/vnd.google-apps.folder' and '{root_folder_id}' in parents"
        date_results = service.files().list(q=date_query, spaces='drive', fields='files(id)').execute()

        if date_results.get('files'):
            date_folder_id = date_results['files'][0]['id']

            # Tìm folder số tờ khai trong folder ngày
            custom_query = f"name = '{custom_no}' and mimeType = 'application/vnd.google-apps.folder' and '{date_folder_id}' in parents"
            custom_results = service.files().list(q=custom_query, spaces='drive', fields='files(id)').execute()

            if custom_results.get('files'):
                custom_folder_id = custom_results['files'][0]['id']

                # Tìm file trong folder số tờ khai
                file_query = f"name = '{filename}' and mimeType = 'application/pdf' and '{custom_folder_id}' in parents"
                file_results = service.files().list(q=file_query, spaces='drive', fields='files(id)').execute()

                if file_results.get('files'):
                    print(f"File {filename} đã tồn tại trong thư mục {ngay_formatted}/{custom_no}")
                    send_notification(f"File {filename} đã tồn tại trong Drive", "info")
                    return True

        # Nếu file chưa tồn tại, tiếp tục tải
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

