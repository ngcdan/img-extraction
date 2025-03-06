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
import asyncio

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
from google_sheet_utils import append_to_google_sheet_new, update_invoice_info

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
        # Danh sách lưu kết quả trích xuất và upload
        extracted_results = []
        drive_upload_results = []

        # 1. Trích xuất thông tin từ tất cả các file trước
        for file_path in files:
            try:
                if not os.path.exists(file_path):
                    print(f"File không tồn tại: {file_path}")
                    continue

                with open(file_path, 'rb') as pdf_file:
                    file_content = pdf_file.read()

                text = extract_text(io.BytesIO(file_content))
                sections = split_sections(text)

                if not sections:
                    print(f"Không thể phân tích file: {file_path}")
                    continue

                header_info = extract_header_info(sections['header'])
                if header_info:
                    header_info.update({
                        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'source_file': os.path.basename(file_path)
                    })

                    # Upload file lên Drive
                    ngay_formatted = header_info['date'].replace('/', '') if header_info.get('date') else datetime.now().strftime('%d%m%Y')
                    upload_result = upload_file_to_drive(
                        file_content=file_content,
                        filename=os.path.basename(file_path),
                        parent_folder_date=ngay_formatted
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
                print(f"Lỗi xử lý file {file_path}: {str(e)}")
                continue

        if not extracted_results:
            raise ValueError("Không có dữ liệu được trích xuất từ các file")

        # Sắp xếp kết quả theo tax_number
        sorted_results = sorted(
            extracted_results,
            key=lambda x: x.get('tax_number', '0')
        )

        # 2. Ghi tất cả dữ liệu vào Google Sheet (thực hiện trước)
        sheet_results = []
        for result in sorted_results:
            try:
                if append_to_google_sheet_new(result):
                    sheet_results.append({
                        'file': result['source_file'],
                        'status': 'success'
                    })
                    print(f"Đã ghi thành công dữ liệu từ file {result['source_file']}")
                else:
                    sheet_results.append({
                        'file': result['source_file'],
                        'status': 'error'
                    })
                    print(f"Lỗi ghi dữ liệu từ file {result['source_file']}")
            except Exception as e:
                print(f"Lỗi khi ghi dữ liệu vào Sheet: {str(e)}")
                sheet_results.append({
                    'file': result['source_file'],
                    'status': 'error',
                    'error': str(e)
                })

        # 3. Group results by tax_number
        grouped_results = {}
        for result in sorted_results:
            tax_number = result.get('tax_number')
            customs_number = result.get('customs_number')

            if tax_number and customs_number:
                if tax_number not in grouped_results:
                    grouped_results[tax_number] = []
                grouped_results[tax_number].append(customs_number)

        # 4. Sau đó mới thực hiện download
        driver = None
        try:
            driver = initialize_chrome()
            if not driver:
                raise Exception("Không thể khởi tạo Chrome driver")

            download_results = []
            for tax_number, customs_numbers in grouped_results.items():
                try:
                    download_status = {'current': 0, 'total': len(customs_numbers), 'success': 0}
                    if process_download(
                        driver=driver,
                        username=tax_number,
                        so_tk_list=customs_numbers,
                        download_status=download_status
                    ):
                        download_results.append({
                            'tax_number': tax_number,
                            'status': 'success',
                            'customs_count': len(customs_numbers),
                            'success_count': download_status['success']
                        })
                        print(f"Đã tải thành công {download_status['success']}/{len(customs_numbers)} biên lai cho MST {tax_number}")
                    else:
                        download_results.append({
                            'tax_number': tax_number,
                            'status': 'error',
                            'customs_count': len(customs_numbers),
                            'success_count': download_status['success']
                        })
                        print(f"Lỗi tải biên lai cho MST {tax_number}")
                except Exception as e:
                    print(f"Lỗi khi tải biên lai: {str(e)}")
                    download_results.append({
                        'tax_number': tax_number,
                        'status': 'error',
                        'error': str(e),
                        'customs_count': len(customs_numbers),
                        'success_count': download_status.get('success', 0)
                    })

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        # Tính toán thống kê
        stats = {
            'total_files': len(files),
            'processed': len(extracted_results),
            'sheet_success': len([r for r in sheet_results if r['status'] == 'success']),
            'sheet_error': len([r for r in sheet_results if r['status'] == 'error']),
            'download_success': len([r for r in download_results if r['status'] == 'success']),
            'download_error': len([r for r in download_results if r['status'] == 'error']),
            'drive_uploads': drive_upload_results
        }

        return {
            'success': True,
            'message': f'Đã xử lý {len(files)} file',
            'stats': stats,
            'sheet_results': sheet_results,
            'download_results': download_results
        }

    except Exception as e:
        print(f"Lỗi trong quá trình xử lý batch: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def initialize_chrome():
    """Khởi tạo Chrome và mở trang web"""
    try:
        print("Đang khởi tạo Chrome driver...")

        # Xác định đường dẫn profile mặc định của Chrome
        if platform.system() == 'Windows':
            default_profile = os.path.join(os.getenv('LOCALAPPDATA'), 'Google', 'Chrome', 'User Data')
        else:  # macOS
            default_profile = os.path.expanduser('~/Library/Application Support/Google/Chrome')

        # Xác định đường dẫn Chrome
        if platform.system() == 'Windows':
            chrome_path = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
            if not os.path.exists(chrome_path):
                chrome_path = 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'
        else:  # macOS
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

        # Kiểm tra xem Chrome có đang chạy với debug port không
        chrome_running = False
        try:
            response = requests.get('http://127.0.0.1:9222/json/version')
            if response.status_code == 200:
                chrome_running = True
                print("Đã tìm thấy Chrome đang chạy với debug port")
        except:
            print("Khởi động Chrome mới với debug port...")

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
            print("Đã kết nối với Chrome thành công")
            return driver
        except Exception as e:
            error_message = f"Lỗi khi kết nối với Chrome: {str(e)}"
            print(error_message)
            return None

    except Exception as e:
        error_message = f"Lỗi khi khởi tạo Chrome: {str(e)}"
        print(error_message)
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

def process_download(driver, username, so_tk_list=None, download_status=None):
    """
    Xử lý quá trình tải biên lai
    Args:
        driver: WebDriver instance
        username: Tên đăng nhập
        so_tk_list: List số tờ khai (optional)
        download_status: Dict để theo dõi trạng thái
    """
    try:
        # Tạo session với SSL verification disabled
        import requests
        session = requests.Session()
        session.verify = False

        # Mở tab mới và switch sang
        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])

        # Xử lý đăng nhập
        def handle_login():
            cookies_loaded = load_cookies(driver, username)
            if cookies_loaded:
                driver.get("http://thuphi.haiphong.gov.vn:8222/Home")
                if not check_login_status(driver):
                    return perform_login()
                print("Đã đăng nhập lại bằng cookies")
                return True
            return perform_login()

        def perform_login():
            driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
            if not fill_login_info(driver, username, username):
                return False
            login_success = collect_captcha_if_login(driver)
            if login_success:
                save_cookies(driver, username)
            return login_success

        # Đăng nhập
        if not handle_login():
            raise Exception("Không thể đăng nhập")

        wait = WebDriverWait(driver, 20)
        total_success = 0

        # Xử lý từng số tờ khai
        if so_tk_list:
            for idx, so_tk in enumerate(so_tk_list, 1):
                print(f"Đang xử lý số tờ khai {idx}/{len(so_tk_list)}: {so_tk}")

                try:
                    # Truy cập trang tìm kiếm
                    driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")
                    time.sleep(1)

                    # Điền số tờ khai và tìm kiếm
                    so_tk_input = wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
                    so_tk_input.clear()
                    so_tk_input.send_keys(so_tk)

                    # Đợi preloader biến mất nếu có
                    try:
                        preloader = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
                        wait.until(EC.invisibility_of_element(preloader))
                    except:
                        pass  # Bỏ qua nếu không tìm thấy preloader

                    # Tìm và click nút tìm kiếm với retry
                    max_retries = 3
                    retry_count = 0
                    while retry_count < max_retries:
                        try:
                            search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                            # Scroll đến nút
                            driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                            time.sleep(0.5)
                            # Thử click bằng JavaScript
                            driver.execute_script("arguments[0].click();", search_button)
                            print("Đã nhấp nút tìm kiếm")
                            break
                        except Exception as e:
                            retry_count += 1
                            print(f"Lần thử {retry_count}: Không thể click nút tìm kiếm. Đang thử lại...")
                            time.sleep(1)
                            if retry_count == max_retries:
                                raise Exception(f"Không thể click nút tìm kiếm sau {max_retries} lần thử: {str(e)}")

                    # Đợi preloader biến mất sau khi click
                    time.sleep(1)
                    try:
                        preloader = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
                        wait.until(EC.invisibility_of_element(preloader))
                    except:
                        pass

                    # Tìm links cho số tờ khai hiện tại
                    current_links = wait.until(EC.presence_of_all_elements_located((
                        By.CSS_SELECTOR,
                        "a.color-blue.underline[href^='http://113.160.97.58:8224/Viewer/HoaDonViewer.aspx?mhd='][href$='iscd=1']"
                    )))

                    if current_links:
                        print(f"Tìm thấy {len(current_links)} biên lai cho số tờ khai {so_tk}")

                        # Download từng biên lai
                        success_count = 0
                        for i, link in enumerate(current_links, 1):
                            if 'Xem' in link.text:
                                try:
                                    print(f"Đang tải biên lai {i}/{len(current_links)}")
                                    if download_pdf(driver, link, session):
                                        success_count += 1
                                        print(f"Thành công biên lai {i}/{len(current_links)}")
                                    else:
                                        print(f"Thất bại biên lai {i}/{len(current_links)}")
                                except Exception as e:
                                    print(f"Lỗi khi tải biên lai {i}/{len(current_links)}: {e}")
                                    continue

                        total_success += success_count
                        print(f"Đã tải xong {success_count}/{len(current_links)} biên lai cho số tờ khai {so_tk}")
                    else:
                        print(f"Không tìm thấy biên lai nào cho số tờ khai {so_tk}")

                except Exception as e:
                    print(f"Lỗi khi xử lý số tờ khai {so_tk}: {str(e)}")
                    continue

                finally:
                    # Dọn dẹp memory sau mỗi lần xử lý
                    import gc
                    gc.collect()

        # Cập nhật trạng thái
        if download_status:
            download_status['success'] = total_success
            download_status['status'] = 'completed'

        cleanup_tabs(driver)
        return True

    except Exception as e:
        print(f"Lỗi: {str(e)}")
        if download_status:
            download_status['status'] = 'error'
        return False

    finally:
        # Đảm bảo dọn dẹp resources
        if 'session' in locals():
            session.close()


def download_pdf(driver, link_element, session):
    """Tải file PDF và lưu vào Google Drive"""
    try:
        href = link_element.get_attribute('href')
        current_handle = driver.current_window_handle

        # Lấy thông tin từ bảng
        row = link_element.find_element(By.XPATH, "./ancestor::tr")
        columns = row.find_elements(By.TAG_NAME, "td")
        custom_no = columns[4].text.strip()
        ngay = columns[9].text.strip()
        seriesNo = columns[7].text.strip()
        invoice_no = columns[8].text.strip()
        total = columns[11].text.strip()
        total_amount = convert_price_to_number(total)

        # Format ngày và tên file
        ngay_formatted = ngay.replace('/', '')
        filename = f"CSHT_{invoice_no}.pdf"

        # Kiểm tra file đã tồn tại trong Drive chưa
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_folder_id = drive_instance.root_folder_id

        # Tìm file trong folder ngày
        date_query = f"name = '{ngay_formatted}' and mimeType = 'application/vnd.google-apps.folder' and '{root_folder_id}' in parents"
        date_results = service.files().list(q=date_query, spaces='drive', fields='files(id)').execute()

        if date_results.get('files'):
            date_folder_id = date_results['files'][0]['id']
            file_query = f"name = '{filename}' and mimeType = 'application/pdf' and '{date_folder_id}' in parents"
            file_results = service.files().list(q=file_query, spaces='drive', fields='files(id)').execute()

            if file_results.get('files'):
                print(f"File {filename} đã tồn tại trong thư mục {ngay_formatted}")
                return True

        # Nếu file chưa tồn tại, tiếp tục tải
        driver.execute_script(f"window.open('{href}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(2)  # Đợi trang load

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
            parent_folder_date=ngay_formatted)

        if not upload_result['success']:
            raise Exception(f"Lỗi upload file: {upload_result.get('error')}")

        print(f"Đã tải file lên Google Drive: {upload_result['web_view_link']}")

        invoice_info = {
            'custom_no': custom_no,
            'invoice_no': invoice_no,
            'seriesNo': seriesNo,
            'ngay': ngay,
            'total_amount': total_amount,
            'drive_link': upload_result['web_view_link']  # Thêm link drive vào thông tin
        }

        try:
            if update_invoice_info(invoice_info):
                print("Đã cập nhật thông tin vào Google Sheet")
            else:
                print("Lỗi khi cập nhật Google Sheet")
        except Exception as e:
            print(f"Lỗi khi cập nhật Google Sheet: {str(e)}")
            # Không raise exception ở đây để không ảnh hưởng đến quá trình tải file

        driver.close()
        driver.switch_to.window(current_handle)
        return True

    except Exception as e:
        print(f"Lỗi khi tải PDF: {e}")
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
        print("Đã tìm thấy mục 'Tra cứu', chuẩn bị hover...")

        # Hover vào menu Tra cứu
        actions.move_to_element(tra_cuu_link).perform()
        time.sleep(1)  # Đợi animation hover
        print("Đã hover vào 'Tra cứu'")

        # Click vào menu Tra cứu
        actions.click().perform()
        print("Đã nhấp vào 'Tra cứu'")

        # Đợi và mở rộng menu con
        menu_treeview = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.nav-treeview")))
        driver.execute_script("arguments[0].style.display = 'block'; arguments[0].classList.add('show');", menu_treeview)
        print("Đã hiển thị menu con")
        time.sleep(1)  # Đợi animation menu

        # Tìm link biên lai
        bien_lai_link = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "a[href='/danh-sach-tra-cuu-bien-lai-dien-tu']")
        ))
        print("Đã tìm thấy '2. Danh sách biên lai điện tử', chuẩn bị hover...")

        # Hover và click vào link biên lai
        actions.move_to_element(bien_lai_link).perform()
        time.sleep(1)  # Đợi animation hover
        print("Đã hover vào link biên lai")

        actions.click().perform()
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
                # Hover và click vào nút tìm kiếm
                actions.move_to_element(search_button).perform()
                time.sleep(0.5)
                actions.click().perform()
                print("Đã nhấp nút tìm kiếm")

                time.sleep(3)  # Đợi kết quả tìm kiếm
            except Exception as e:
                print(f"Lỗi khi tìm kiếm theo số tờ khai: {str(e)}")
                raise

    except Exception as e:
        print(f"Lỗi khi điều hướng và tìm kiếm biên lai: {str(e)}")
        raise

def save_captcha_and_label(driver, captcha_text):
    """Lưu ảnh captcha và nhãn"""
    try:
        captcha_element = driver.find_element(By.ID, "CaptchaImage")
        png_data = captcha_element.screenshot_as_png

        from google_drive_utils import upload_captcha_to_drive, append_to_labels_file
        result = upload_captcha_to_drive(png_data)

        if result['success']:
            print(f"Đã lưu captcha {result['filename']} với label: {captcha_text}")

            # Append vào file labels.txt trên Drive
            append_result = append_to_labels_file(result['filename'], captcha_text)
            if append_result['success']:
                print("Đã thêm label vào file labels.txt trên Drive")
                return True
            else:
                print(f"Lỗi khi thêm label: {append_result.get('error')}")
                return False
        else:
            print(f"Lỗi khi lưu captcha: {result.get('error')}")
            return False

    except Exception as e:
        print(f"Lỗi khi lưu captcha và label: {e}")
        return False


def cleanup_tabs(driver):
    """Đóng các tab phụ an toàn - phiên bản sync"""
    try:
        current_handle = driver.current_window_handle
        for handle in driver.window_handles[:]:
            if handle != current_handle:
                driver.switch_to.window(handle)
                driver.close()
        driver.switch_to.window(current_handle)
    except Exception as e:
        print(f"Warning: Không thể đóng một số tab: {e}")

def download_pdf(driver, link_element, session):
    """Tải file PDF và lưu vào Google Drive"""
    try:
        href = link_element.get_attribute('href')
        current_handle = driver.current_window_handle

        # Lấy thông tin từ bảng
        row = link_element.find_element(By.XPATH, "./ancestor::tr")
        columns = row.find_elements(By.TAG_NAME, "td")
        custom_no = columns[4].text.strip()
        ngay = columns[9].text.strip()
        seriesNo = columns[7].text.strip()
        invoice_no = columns[8].text.strip()
        total = columns[11].text.strip()
        total_amount = convert_price_to_number(total)

        # Format ngày và tên file
        ngay_formatted = ngay.replace('/', '')
        filename = f"CSHT_{invoice_no}.pdf"

        # Kiểm tra file đã tồn tại trong Drive chưa
        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_folder_id = drive_instance.root_folder_id

        # Tìm file trong folder ngày
        date_query = f"name = '{ngay_formatted}' and mimeType = 'application/vnd.google-apps.folder' and '{root_folder_id}' in parents"
        date_results = service.files().list(q=date_query, spaces='drive', fields='files(id)').execute()

        if date_results.get('files'):
            date_folder_id = date_results['files'][0]['id']
            file_query = f"name = '{filename}' and mimeType = 'application/pdf' and '{date_folder_id}' in parents"
            file_results = service.files().list(q=file_query, spaces='drive', fields='files(id)').execute()

            if file_results.get('files'):
                print(f"File {filename} đã tồn tại trong thư mục {ngay_formatted}")
                return True

        # Nếu file chưa tồn tại, tiếp tục tải
        driver.execute_script(f"window.open('{href}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(2)  # Đợi trang load

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
            parent_folder_date=ngay_formatted)

        if not upload_result['success']:
            raise Exception(f"Lỗi upload file: {upload_result.get('error')}")

        print(f"Đã tải file lên Google Drive: {upload_result['web_view_link']}")

        # Cập nhật thông tin vào Google Sheet
        invoice_info = {
            'custom_no': custom_no,
            'invoice_no': invoice_no,
            'seriesNo': seriesNo,
            'ngay': ngay,
            'total_amount': total_amount
        }
        if update_invoice_info(invoice_info):
            print("Đã cập nhật thông tin vào Google Sheet")
        else:
            print("Lỗi khi cập nhật Google Sheet")

        driver.close()
        driver.switch_to.window(current_handle)
        return True

    except Exception as e:
        print(f"Lỗi khi tải PDF: {e}")
        return False

