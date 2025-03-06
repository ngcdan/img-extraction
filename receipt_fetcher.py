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

        # 2. Group results by tax_number
        grouped_results = {}
        for result in sorted(extracted_results, key=lambda x: x.get('tax_number', '0')):
            tax_number = result.get('tax_number')
            customs_number = result.get('customs_number')

            if tax_number and customs_number:
                if tax_number not in grouped_results:
                    grouped_results[tax_number] = []
                grouped_results[tax_number].append(customs_number)

        # 3. Thực hiện download và write dữ liệu
        driver = None
        try:
            driver = initialize_chrome()
            if not driver:
                raise Exception("Không thể khởi tạo Chrome driver")

            for tax_number, customs_numbers in grouped_results.items():
                try:
                    session = requests.Session()
                    session.verify = False

                    # Mở tab mới và login
                    driver.execute_script("window.open('about:blank', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])

                    # Login process
                    login_success = False
                    cookies_loaded = load_cookies(driver, tax_number)
                    if cookies_loaded:
                        driver.get("http://thuphi.haiphong.gov.vn:8222/Home")
                        if check_login_status(driver):
                            login_success = True
                            print("Đã đăng nhập lại bằng cookies")

                    if not login_success:
                        driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
                        if fill_login_info(driver, tax_number, tax_number):
                            login_success = collect_captcha_if_login(driver)
                            if login_success:
                                save_cookies(driver, tax_number)

                    if not login_success:
                        raise Exception(f"Không thể đăng nhập với MST {tax_number}")

                    # Lấy tokens và cookies
                    driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")
                    time.sleep(2)

                    request_token_form = driver.find_element(By.NAME, "__RequestVerificationToken").get_attribute("value")
                    browser_cookies = driver.get_cookies()

                    cookies = {}
                    for cookie in browser_cookies:
                        if cookie['name'] in ['__RequestVerificationToken', 'SessionToken', 'ASP.NET_SessionId']:
                            cookies[cookie['name']] = cookie['value']

                    headers = {
                        "Accept": "*/*",
                        "Accept-Encoding": "gzip, deflate",
                        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "Host": "thuphi.haiphong.gov.vn:8222",
                        "Origin": "http://thuphi.haiphong.gov.vn:8222",
                        "Referer": "http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu",
                        "X-Requested-With": "XMLHttpRequest",
                        "__RequestVerificationToken": request_token_form
                    }

                    success_count = 0
                    for idx, so_tk in enumerate(customs_numbers, 1):
                        try:
                            data = {
                                "EinvoiceFrom": "0",
                                "tu_ngay": "01/01/2024",
                                "den_ngay": "31/12/2024",
                                "ma_dn": tax_number,
                                "so_tokhai": so_tk,
                                "pageNum": "1",
                                "__RequestVerificationToken": request_token_form
                            }

                            response = session.post(
                                "http://thuphi.haiphong.gov.vn:8222/DBienLaiThuPhi_TraCuu/GetListEinvoiceByMaDN/",
                                headers=headers,
                                cookies=cookies,
                                data=data
                            )

                            if response.status_code == 200:
                                result = response.json()
                                if result.get("code") == 1 and result.get("DANHSACH"):
                                    for receipt in result['DANHSACH']:
                                        ngay_tk_str = receipt.get('NgayTK', '')
                                        if ngay_tk_str:
                                            # Trích xuất timestamp từ chuỗi "/Date(1740762000000)/"
                                            timestamp = int(ngay_tk_str.split('(')[1].split(')')[0])
                                            # Chuyển timestamp (milliseconds) sang datetime
                                            ngay_tk = datetime.fromtimestamp(timestamp/1000)
                                            # Format ngày thành dd/mm/yyyy
                                            ngay_tk = ngay_tk.strftime('%d/%m/%Y')
                                        else:
                                            ngay_tk = ''

                                        invoice_info = {
                                            'custom_no': receipt.get('SoTK', ''),
                                            'invoice_no': str(receipt.get('SoBienLai', '')),
                                            'seriesNo': receipt.get('MauBienLai', ''),
                                            'ngay': ngay_tk,
                                            'total_amount': receipt.get('TongTien', 0),
                                            'drive_link': receipt.get('InvoiceKey', '')
                                        }

                                        print(f"Xử lý biên lai: {json.dumps(invoice_info, indent=2, ensure_ascii=False)}")

                                        # Tìm thông tin tương ứng trong extracted_results
                                        matching_result = next(
                                            (result for result in extracted_results
                                            if result.get('customs_number') == so_tk),
                                            None
                                        )

                                        if matching_result:
                                            # Merge thông tin từ extracted_results vào invoice_info
                                            invoice_info.update({
                                                'tax_number': tax_number,
                                                'so_ct': matching_result.get('so_ct'),
                                                'partner_invoice_name': matching_result.get('partner_invoice_name'),
                                                'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                            })
                                            print(json.dumps(invoice_info, indent=2, ensure_ascii=False))

                                            # Tạo URL xem biên lai
                                            invoice_url = f"http://thuphi.haiphong.gov.vn:8222/Viewer/HoaDonViewer.aspx?mhd={invoice_info['drive_link']}"

                                            # Mở tab mới để tải PDF
                                            driver.execute_script(f"window.open('{invoice_url}', '_blank');")

                                            driver.switch_to.window(driver.window_handles[-1])
                                            time.sleep(2)

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
                                                filename=f"CSHT_{invoice_info['invoice_no']}.pdf",
                                                parent_folder_date=ngay_tk)

                                            if upload_result['success']:
                                                if append_to_google_sheet_new(invoice_info):
                                                    success_count += 1
                                                    print(f"Đã xử lý thành công biên lai {invoice_info['invoice_no']}")
                                            else:
                                                print(f"Lỗi khi upload file: {upload_result.get('error')}")
                                                raise Exception(f"Lỗi upload file: {upload_result.get('error')}")
                                        else:
                                            print(f"\nKhông tìm thấy thông tin gốc cho số tờ khai: {so_tk}")

                        except Exception as e:
                            print(f"Lỗi khi xử lý số tờ khai {so_tk}: {str(e)}")
                            continue

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
            'download_success': len([r for r in download_results if r['status'] == 'success']),
            'download_error': len([r for r in download_results if r['status'] == 'error']),
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

def process_download(driver, username, so_tk_list=None, download_status=None):
    try:
        session = requests.Session()
        session.verify = False

        # Mở tab mới và login như cũ
        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])

        def perform_login():
            driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
            if not fill_login_info(driver, username, username):
                return False
            login_success = collect_captcha_if_login(driver)
            if login_success:
                save_cookies(driver, username)
            return login_success

        def handle_login():
            cookies_loaded = load_cookies(driver, username)
            if cookies_loaded:
                driver.get("http://thuphi.haiphong.gov.vn:8222/Home")
                if not check_login_status(driver):
                    return perform_login()
                print("Đã đăng nhập lại bằng cookies")
                return True
            return perform_login()

        if not handle_login():
            raise Exception("Không thể đăng nhập")

        # Truy cập trang tra cứu để lấy form token
        driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")
        time.sleep(2)

        # Lấy form token từ trang
        request_token_form = driver.find_element(By.NAME, "__RequestVerificationToken").get_attribute("value")
        print("\nForm token:", request_token_form)

        # Lấy cookies từ browser
        browser_cookies = driver.get_cookies()

        # Tìm token trong cookies
        request_token_cookie = None
        session_token = None
        asp_session_id = None

        for cookie in browser_cookies:
            if cookie['name'] == '__RequestVerificationToken':
                request_token_cookie = cookie['value']
            elif cookie['name'] == 'SessionToken':
                session_token = cookie['value']
            elif cookie['name'] == 'ASP.NET_SessionId':
                asp_session_id = cookie['value']

        print("\nCookies từ browser:")
        print("Request Token Cookie:", request_token_cookie)
        print("Session Token:", session_token)
        print("ASP.NET Session ID:", asp_session_id)

        # Chuẩn bị headers và cookies
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
            "X-Requested-With": "XMLHttpRequest",
            "__RequestVerificationToken": request_token_form  # Sử dụng form token
        }

        cookies = {
            "SessionToken": session_token,
            "ASP.NET_SessionId": asp_session_id,
            "__RequestVerificationToken": request_token_cookie
        }

        print("\nHeaders được chuẩn bị:", json.dumps(headers, indent=2))
        print("\nCookies được chuẩn bị:", json.dumps(cookies, indent=2))

        url = "http://thuphi.haiphong.gov.vn:8222/DBienLaiThuPhi_TraCuu/GetListEinvoiceByMaDN/"

        if so_tk_list:
            for idx, so_tk in enumerate(so_tk_list, 1):
                try:
                    print(f"\nĐang xử lý số tờ khai {idx}/{len(so_tk_list)}: {so_tk}")

                    data = {
                        "EinvoiceFrom": "0",
                        "tu_ngay": "01/01/2024",
                        "den_ngay": "31/12/2024",
                        "ma_dn": username,
                        "so_tokhai": so_tk,
                        "pageNum": "1",
                        "__RequestVerificationToken": request_token_form
                    }

                    print("\nData request:", json.dumps(data, indent=2))

                    response = session.post(url, headers=headers, cookies=cookies, data=data)

                    print("\nStatus code:", response.status_code)
                    if response.status_code == 200:
                        result = response.json()
                        print("Response:", json.dumps(result, indent=2, ensure_ascii=False))

                        if result.get("code") == 1 and result.get("DANHSACH"):
                            print(f"\nTìm thấy {len(result['DANHSACH'])} biên lai")
                            for receipt in result['DANHSACH']:
                                # Chuyển đổi timestamp thành định dạng ngày
                                ngay_tk_str = receipt.get('NgayTK', '')
                                if ngay_tk_str:
                                    # Trích xuất timestamp từ chuỗi "/Date(1740762000000)/"
                                    timestamp = int(ngay_tk_str.split('(')[1].split(')')[0])
                                    # Chuyển timestamp (milliseconds) sang datetime
                                    ngay_tk = datetime.fromtimestamp(timestamp/1000)
                                    # Format ngày thành dd/mm/yyyy
                                    ngay_tk = ngay_tk.strftime('%d/%m/%Y')
                                else:
                                    ngay_tk = ''

                                invoice_info = {
                                    'custom_no': receipt.get('SoTK', ''),
                                    'invoice_no': str(receipt.get('SoBienLai', '')),
                                    'seriesNo': receipt.get('MauBienLai', ''),
                                    'ngay': ngay_tk,
                                    'total_amount': receipt.get('TongTien', 0),
                                    'drive_link': receipt.get('InvoiceKey', '')
                                }

                                print(f"Xử lý biên lai: {json.dumps(invoice_info, indent=2, ensure_ascii=False)}")

                                # Tạo URL xem biên lai
                                invoice_url = f"http://thuphi.haiphong.gov.vn:8222/Viewer/HoaDonViewer.aspx?mhd={invoice_info['drive_link']}"

                                # Mở tab mới để tải PDF
                                driver.execute_script(f"window.open('{invoice_url}', '_blank');")

                                driver.switch_to.window(driver.window_handles[-1])
                                time.sleep(2)

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
                                    filename=f"CSHT_{invoice_info['invoice_no']}.pdf",
                                    parent_folder_date=ngay_tk)

                                if not upload_result['success']:
                                    raise Exception(f"Lỗi upload file: {upload_result.get('error')}")

                                print(f"Đã tải file lên Google Drive: {upload_result['web_view_link']}")

                                # Cập nhật thông tin vào Google Sheet
                                if append_to_google_sheet_new(invoice_info):
                                    print(f"Đã cập nhật thông tin biên lai {invoice_info['invoice_no']} vào Google Sheet")
                                else:
                                    print(f"Lỗi khi cập nhật biên lai {invoice_info['invoice_no']} vào Google Sheet")

                        else:
                            print(f"Không tìm thấy biên lai cho số tờ khai {so_tk}")
                    else:
                        print(f"Request thất bại với mã lỗi {response.status_code}")
                        print("Response:", response.text)

                except Exception as e:
                    print(f"Lỗi khi xử lý số tờ khai {so_tk}: {str(e)}")
                    continue

        driver.close()
        driver.switch_to.window(driver.window_handles[0])
        return True

    except Exception as e:
        print(f"Lỗi: {str(e)}")
        if download_status:
            download_status['status'] = 'error'
        return False

    finally:
        if 'session' in locals():
            session.close()

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


