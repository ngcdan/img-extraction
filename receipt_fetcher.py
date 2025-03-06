from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, TimeoutException
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
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pdfminer.high_level import extract_text
from google_sheet_utils import append_to_google_sheet_new

# Import các hàm helper từ extract_info.py
from extract_info import (
    split_sections,
    extract_header_info,
    convert_price_to_number
)

def parse_date(date_str):
    """Chuyển đổi chuỗi ngày dạng 'dd/mm/yyyy' thành đối tượng datetime"""
    try:
        return datetime.strptime(date_str, '%d/%m/%Y')
    except (ValueError, TypeError):
        return None

def format_date(date_obj):
    """Chuyển đổi đối tượng datetime thành chuỗi 'dd/mm/yyyy'"""
    return date_obj.strftime('%d/%m/%Y') if date_obj else None

def batch_process_files(files: List[str]) -> Dict[str, Any]:
    """
    Xử lý nhiều file PDF cùng lúc, trích xuất thông tin header và ghi vào Google Sheet

    Args:
        files: List of file paths to process

    Returns:
        dict: Kết quả xử lý với thông tin success/error
    """
    driver = None
    try:
        # Khởi tạo driver ngay từ đầu
        driver = initialize_chrome()
        if not driver:
            raise Exception("Không thể khởi tạo Chrome driver")

        # Create a reusable WebDriverWait object
        wait = WebDriverWait(driver, 10)

        # Danh sách lưu kết quả trích xuất và upload
        extracted_results = []
        drive_upload_results = []
        download_results = []

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

        # 2. Group results by tax_number and customs_number
        grouped_results = {}

        # Sắp xếp theo tax_number để dễ theo dõi
        for result in sorted(extracted_results, key=lambda x: x.get('tax_number', '0')):
            tax_number = result.get('tax_number')
            customs_number = result.get('customs_number')
            date_str = result.get('date')

            if tax_number and customs_number and date_str:
                if tax_number not in grouped_results:
                    grouped_results[tax_number] = []

                # Chuyển đổi ngày từ chuỗi sang datetime để so sánh
                current_date = parse_date(date_str)
                if not current_date:
                    print(f"Warning: Invalid date format for {date_str}")
                    continue

                # Kiểm tra xem customs_number đã tồn tại chưa
                existing_customs = next(
                    (item for item in grouped_results[tax_number]
                     if item['customs_number'] == customs_number),
                    None
                )

                if existing_customs:
                    # Chuyển đổi các ngày hiện có sang datetime để so sánh
                    existing_min_date = parse_date(existing_customs['min_date'])
                    existing_max_date = parse_date(existing_customs['max_date'])

                    # Cập nhật min_date và max_date
                    if current_date < existing_min_date:
                        existing_customs['min_date'] = format_date(current_date)
                    if current_date > existing_max_date:
                        # Tăng max_date thêm 2 ngày
                        next_day = current_date + timedelta(days=2)
                        existing_customs['max_date'] = format_date(next_day)
                else:
                    # Copy tất cả các field từ result gốc
                    new_entry = result.copy()
                    # Thêm min_date và max_date (max_date + 2 days)
                    new_entry['min_date'] = format_date(current_date)
                    new_entry['max_date'] = format_date(current_date + timedelta(days=2))
                    grouped_results[tax_number].append(new_entry)

        # 3. Thực hiện download và write dữ liệu
        try:
            for tax_number, customs_numbers in grouped_results.items():
                print(json.dumps(customs_numbers, indent=2, ensure_ascii=False))
                print("\n\n - - - - - - - - - - - - \n")
                try:
                    session = requests.Session()
                    session.verify = False
                    success_count = 0

                    # Open new tab and login
                    driver.execute_script("window.open('about:blank', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])

                    # Optimize login process
                    login_success = False
                    if load_cookies(driver, tax_number):
                        driver.get("http://thuphi.haiphong.gov.vn:8222/Home")
                        login_success = "dang-nhap" not in driver.current_url

                    if not login_success:
                        driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
                        if fill_login_info(driver, tax_number, tax_number):
                            login_success = collect_captcha_if_login(driver)
                            if login_success:
                                save_cookies(driver, tax_number)

                    if not login_success:
                        raise Exception(f"Không thể đăng nhập với MST {tax_number}")

                    # Access search page
                    driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")

                    # Đợi cho đến khi preloader biến mất (nếu có)
                    try:
                        print("check preloader...")
                        preloader = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
                        wait.until(EC.invisibility_of_element(preloader))
                    except:
                        print("Không tìm thấy preloader, tiếp tục...")

                    # Wait for table to be interactive
                    table = wait.until(
                        EC.presence_of_element_located((By.ID, "TBLDANHSACH"))
                    )

                    # Wait for table to load data
                    wait.until(
                        lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "#TBLDANHSACH tr")) > 0
                    )

                    # Tìm bảng và trích xuất số tờ khai
                    table = driver.find_element(By.ID, "TBLDANHSACH")
                    rows = table.find_elements(By.TAG_NAME, "tr")

                    # get first customs
                    customs = customs_numbers[0]

                    # Lấy ngày đầu tiên của tháng hiện tại
                    today = datetime.now()
                    first_day_of_month = today.replace(day=1)
                    min_date = parse_date(customs['min_date'])

                    # Kiểm tra nếu min_date bé hơn ngày đầu tháng
                    if min_date < first_day_of_month:
                        # Điền ngày bắt đầu (TU_NGAY)
                        tu_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "TU_NGAY")))
                        tu_ngay_input.clear()
                        tu_ngay_input.send_keys(customs['min_date'])

                        # Điền ngày kết thúc (DEN_NGAY)
                        den_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "DEN_NGAY")))
                        den_ngay_input.clear()
                        den_ngay_input.send_keys(customs['max_date'])

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

                                # Đợi preloader xuất hiện
                                try:
                                    preloader = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
                                except:
                                    print("Không tìm thấy preloader, tiếp tục kiểm tra kết quả")

                                # Đợi preloader biến mất (nếu có)
                                try:
                                    wait.until(EC.invisibility_of_element(preloader))
                                except:
                                    pass

                                # Đợi bảng kết quả xuất hiện và có sự thay đổi
                                try:
                                    # Đợi bảng xuất hiện
                                    table = wait.until(EC.presence_of_element_located((By.ID, "TBLDANHSACH")))

                                    # Đợi có ít nhất một row mới hoặc thông báo không có dữ liệu
                                    wait.until(lambda driver: (
                                        len(driver.find_elements(By.CSS_SELECTOR, "#TBLDANHSACH tr")) > len(rows)
                                    ))
                                    rows = table.find_elements(By.TAG_NAME, "tr")
                                    print("Trang đã load xong với kết quả mới")
                                    break

                                except TimeoutException:
                                    raise Exception("Timeout chờ kết quả tìm kiếm")

                            except Exception as e:
                                retry_count += 1
                                print(f"Lần thử {retry_count}: Không thể hoàn thành tìm kiếm. Đang thử lại...")
                                time.sleep(1)
                                if retry_count == max_retries:
                                    raise Exception(f"Không thể hoàn thành tìm kiếm sau {max_retries} lần thử: {str(e)}")

                    matched_results = []
                    for row in rows[1:]:  # Bỏ qua row đầu tiên (header)
                        try:
                            cells = row.find_elements(By.TAG_NAME, "td")

                            if len(cells) == 1 and "No data available" in cells[0].text:
                                print("Không tìm thấy dữ liệu trong bảng")
                                continue

                            custom_no = str(cells[4].text.strip())  # Đảm bảo là string

                            matching_customs = next(
                                (customs for customs in customs_numbers
                                    if str(customs['customs_number']) == custom_no),  # Đảm bảo là string
                                None
                            )

                            if matching_customs:
                                link_cell = cells[1]
                                link_element = link_cell.find_element(By.TAG_NAME, "a")
                                href = link_element.get_attribute("href")
                                mhd = href.split("mhd=")[-1] if "mhd=" in href else ""

                                result = {
                                    'custom_no': custom_no,
                                    'invoice_no': cells[8].text.strip() if len(cells) > 8 else '',
                                    'seriesNo': cells[7].text.strip() if len(cells) > 7 else '',
                                    'ngay': cells[9].text.strip() if len(cells) > 9 else '',
                                    'total_amount': convert_price_to_number(cells[11].text.strip()) if len(cells) > 11 else 0,
                                    'drive_link': mhd,
                                    'tax_number': tax_number,
                                    'so_ct': matching_customs.get('so_ct', ''),
                                    'partner_invoice_name': matching_customs.get('partner_invoice_name', ''),
                                    'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                matched_results.append(result)

                        except Exception as e:
                            print(f"Lỗi khi xử lý row: {str(e)}")
                            print(f"Chi tiết row: {row.text}")
                            continue

                    if len(matched_results) != len(customs_numbers):
                        print("\nDanh sách thông tin tờ khai đã khớp:")
                        print(json.dumps(matched_results, indent=2, ensure_ascii=False))

                        print("\nDanh sách thông tin tờ khai cần xử lý:")
                        print(json.dumps(customs_numbers, indent=2, ensure_ascii=False))

                        raise Exception("Số lượng biên lai khớp không bằng số lượng tờ khai cần xử lý")

                    # Xử lý theo batch, mỗi batch 2 tab
                    batch_size = 2
                    for i in range(0, len(matched_results), batch_size):
                        batch = matched_results[i:i + batch_size]
                        current_handle = driver.current_window_handle
                        opened_tabs = {}  # Lưu mapping giữa drive_link và handle

                        # Mở 2 tab cùng lúc
                        for invoice_info in batch:
                            invoice_url = f"http://thuphi.haiphong.gov.vn:8224/Viewer/HoaDonViewer.aspx?mhd={invoice_info['drive_link']}"
                            driver.execute_script(f"window.open('{invoice_url}', '_blank');")
                            new_handle = driver.window_handles[-1]
                            opened_tabs[invoice_info['drive_link']] = {
                                'handle': new_handle,
                                'invoice_info': invoice_info,
                                'retry_count': 0,
                                'processed': False
                            }

                        # Wait for all tabs to open
                        wait.until(lambda d: len(d.window_handles) == len(batch) + 1)

                        # Xử lý các tab cho đến khi tất cả đều được xử lý
                        while any(not tab['processed'] for tab in opened_tabs.values()):
                            for drive_link, tab_info in opened_tabs.items():
                                if tab_info['processed']:
                                    continue

                                try:
                                    driver.switch_to.window(tab_info['handle'])

                                    # Kiểm tra xem trang đã load xong chưa
                                    page_ready = False
                                    try:
                                        page_ready = wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                                    except:
                                        continue  # Skip to next tab if this one isn't ready

                                    if not page_ready:
                                        continue

                                    # Check and wait for preloader
                                    try:
                                        preloader = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
                                        wait.until(EC.invisibility_of_element(preloader))
                                    except:
                                        pass  # Preloader might not exist

                                    print_options = {
                                        'landscape': False,
                                        'displayHeaderFooter': False,
                                        'printBackground': True,
                                        'preferCSSPageSize': True,
                                    }
                                    pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                                    pdf_data = base64.b64decode(pdf['data'])

                                    invoice_info = tab_info['invoice_info']
                                    ngay_formatted = invoice_info['ngay'].replace('/', '') if invoice_info.get('ngay') else datetime.now().strftime('%d%m%Y')

                                    # Upload lên Drive
                                    upload_result = upload_file_to_drive(
                                        file_content=pdf_data,
                                        filename=f"CSHT_{invoice_info['invoice_no']}.pdf",
                                        parent_folder_date=ngay_formatted
                                    )

                                    if upload_result['success']:
                                        if append_to_google_sheet_new(invoice_info):
                                            success_count += 1
                                            driver.close()
                                            tab_info['processed'] = True
                                    else:
                                        raise Exception(f"Lỗi upload file: {upload_result.get('error')}")

                                except Exception as e:
                                    print(f"Lỗi khi xử lý biên lai {tab_info['invoice_info']['invoice_no']} (lần {tab_info['retry_count'] + 1}): {str(e)}")
                                    tab_info['retry_count'] += 1
                                    if tab_info['retry_count'] >= 3:  # max_retries = 3
                                        print(f"Không thể xử lý biên lai {tab_info['invoice_info']['invoice_no']} sau 3 lần thử")
                                        tab_info['processed'] = True  # Mark as processed to move on
                                        try:
                                            driver.close()
                                        except:
                                            pass

                            time.sleep(0.5)  # Short delay before checking tabs again

                        # Switch back to main handle after processing batch
                        driver.switch_to.window(current_handle)

                    download_results.append({
                        'tax_number': tax_number,
                        'status': 'success' if success_count > 0 else 'error',
                        'customs_count': len(customs_numbers),
                        'success_count': success_count
                    })

                except Exception as e:
                    print(f"Lỗi khi xử lý MST {tax_number}: {str(e)}")
                    download_results.append({
                        'tax_number': tax_number,
                        'status': 'error',
                        'error': str(e),
                        'customs_count': len(customs_numbers),
                        'success_count': 0
                    })
                finally:
                    if 'session' in locals():
                        session.close()

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
            'download_success': sum(r['success_count'] for r in download_results),
            'download_error': sum(r['customs_count'] - r['success_count'] for r in download_results),
            'drive_uploads': drive_upload_results
        }

        return {
            'success': True,
            'message': f'Đã xử lý {len(files)} file',
            'stats': stats,
            'download_results': download_results
        }

    except Exception as e:
        print(f"Lỗi trong quá trình xử lý batch: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

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






