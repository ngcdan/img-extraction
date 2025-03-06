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

        # Danh sách lưu kết quả trích xuất và upload
        extracted_results = []
        drive_upload_results = []
        download_results = []

        cached_extracted_files = {}  # Dictionary để lưu file đã được trích xuất

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

                    # Cache file với key là customs_number
                    customs_no = header_info.get('customs_number')
                    if customs_no:
                        cached_extracted_files[customs_no] = {
                            'file_content': file_content,
                            'header_info': header_info
                        }
                        extracted_results.append(header_info)
                    else:
                        print(f"Không tìm thấy customs_number trong file: {file_path}")

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

                    # Mở tab mới và login
                    driver.execute_script("window.open('about:blank', '_blank');")
                    driver.switch_to.window(driver.window_handles[-1])

                    # Khởi tạo WebDriverWait với timeout dài hơn
                    long_wait = WebDriverWait(driver, 120)  # 2 phút
                    short_wait = WebDriverWait(driver, 2)   # 2 giây

                    def is_page_loaded():
                        try:
                            return driver.execute_script("return document.readyState") == "complete"
                        except:
                            return False

                    def wait_for_page_load(url, timeout=120):
                        start_time = time.time()
                        driver.get(url)

                        while time.time() - start_time < timeout:
                            try:
                                if is_page_loaded():
                                    # Thêm delay ngắn để đảm bảo JS đã chạy
                                    time.sleep(0.5)
                                    return True
                            except:
                                pass
                            time.sleep(0.5)
                        return False

                    # Login process
                    login_success = False
                    cookies_loaded = load_cookies(driver, tax_number)

                    # Kiểm tra URL sau khi chuyển hướng
                    if cookies_loaded:
                        if wait_for_page_load("http://thuphi.haiphong.gov.vn:8222/Home"):
                            try:
                                # Đợi cho đến khi có thể tương tác với trang
                                long_wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
                                login_success = "dang-nhap" not in driver.current_url
                            except:
                                print("Timeout khi đợi trang Home load hoàn tất")

                    if not login_success:
                        if wait_for_page_load("http://thuphi.haiphong.gov.vn:8222/dang-nhap"):
                            try:
                                # Đợi form login xuất hiện và có thể tương tác
                                long_wait.until(EC.presence_of_element_located((By.ID, "form-username")))

                                if fill_login_info(driver, tax_number, tax_number):
                                    login_success = collect_captcha_if_login(driver)
                                    if login_success:
                                        save_cookies(driver, tax_number)
                            except Exception as e:
                                print(f"Lỗi trong quá trình login: {str(e)}")

                    if not login_success:
                        raise Exception(f"Không thể đăng nhập với MST {tax_number} sau nhiều lần thử")

                    # Truy cập trang tìm kiếm
                    driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")

                    # Tăng thời gian chờ tối đa lên 60 giây
                    wait = WebDriverWait(driver, 60)
                    short_wait = WebDriverWait(driver, 2)  # wait ngắn để check nhanh

                    try:
                        # Đợi cho đến khi preloader xuất hiện (nếu có)
                        try:
                            preloader = short_wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
                        except:
                            print("Không tìm thấy preloader")

                        # Đợi cho đến khi preloader biến mất và bảng xuất hiện với dữ liệu
                        start_time = time.time()
                        while time.time() - start_time < 60:  # Tối đa 60 giây
                            try:
                                # Kiểm tra preloader đã biến mất chưa
                                if not driver.find_elements(By.CLASS_NAME, "preloader-container"):
                                    # Kiểm tra bảng đã load xong chưa
                                    if is_table_loaded_with_data(driver, short_wait):
                                        print(f"Trang đã load hoàn tất sau {time.time() - start_time:.1f} giây")
                                        break
                            except:
                                pass
                            time.sleep(0.5)  # Đợi 500ms trước khi check lại

                        # Kiểm tra lần cuối để đảm bảo dữ liệu đã sẵn sàng
                        if not is_table_loaded_with_data(driver, short_wait):
                            raise Exception("Không thể load dữ liệu bảng sau 60 giây")

                    except Exception as e:
                        raise Exception(f"Lỗi khi đợi trang load: {str(e)}")

                    # get first customs
                    customs = customs_numbers[0]

                    # Lấy ngày đầu tiên của tháng hiện tại
                    today = datetime.now()
                    first_day_of_month = today.replace(day=1)
                    min_date = parse_date(customs['min_date'])


                    # Kiểm tra nếu min_date bé hơn ngày đầu tháng
                    if min_date < first_day_of_month:
                        # Điền form tìm kiếm
                        try:
                            # Đợi và điền ngày bắt đầu
                            tu_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "TU_NGAY")))
                            tu_ngay_input.clear()
                            tu_ngay_input.send_keys(customs['min_date'])

                            # Đợi và điền ngày kết thúc
                            den_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "DEN_NGAY")))
                            den_ngay_input.clear()
                            den_ngay_input.send_keys(customs['max_date'])

                        except Exception as e:
                            raise Exception(f"Lỗi khi điền form tìm kiếm: {str(e)}")

                        # Thực hiện tìm kiếm với retry
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                # Lưu trạng thái bảng hiện tại để so sánh
                                current_rows = len(driver.find_elements(By.CSS_SELECTOR, "#TBLDANHSACH tr"))

                                # Click nút tìm kiếm
                                search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                                driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                                driver.execute_script("arguments[0].click();", search_button)
                                print("Đã click nút tìm kiếm")

                                def is_search_complete():
                                    try:
                                        # Kiểm tra preloader đã biến mất
                                        if driver.find_elements(By.CLASS_NAME, "preloader-container"):
                                            return False

                                        # Kiểm tra bảng đã xuất hiện
                                        table = driver.find_element(By.ID, "TBLDANHSACH")
                                        if not table:
                                            return False

                                        # Kiểm tra có dữ liệu mới hoặc thông báo không có dữ liệu
                                        new_rows = len(driver.find_elements(By.CSS_SELECTOR, "#TBLDANHSACH tr"))
                                        has_no_data = bool(driver.find_elements(By.CSS_SELECTOR, ".dataTables_empty"))

                                        if new_rows > 0 or has_no_data:
                                            return True
                                        return False

                                    except Exception:
                                        return False

                                # Đợi với timeout 30 giây nhưng phản ứng nhanh khi có kết quả
                                start_time = time.time()
                                search_completed = False
                                while time.time() - start_time < 30:
                                    if is_search_complete():
                                        print(f"Tìm kiếm hoàn tất sau {time.time() - start_time:.1f} giây")
                                        search_completed = True
                                        break
                                    time.sleep(0.1)  # Check mỗi 100ms

                                if search_completed:
                                    break  # Thoát khỏi vòng lặp retry
                                else:
                                    raise TimeoutException("Timeout chờ kết quả tìm kiếm")

                            except Exception as e:
                                retry_count += 1
                                print(f"Lần thử {retry_count}: {str(e)}")
                                if retry_count == max_retries:
                                    raise Exception(f"Không thể hoàn thành tìm kiếm sau {max_retries} lần thử")
                                time.sleep(1)

                    # Tìm bảng và trích xuất số tờ khai
                    table = driver.find_element(By.ID, "TBLDANHSACH")
                    rows = table.find_elements(By.TAG_NAME, "tr")

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

                    # Xử lý từng tài liệu một
                    success_count = 0
                    cached_files = {}  # Dictionary để lưu file đã download

                    for invoice_info in matched_results:
                        try:
                            # Mở tab mới
                            invoice_url = f"http://thuphi.haiphong.gov.vn:8224/Viewer/HoaDonViewer.aspx?mhd={invoice_info['drive_link']}"
                            driver.execute_script(f"window.open('{invoice_url}', '_blank');")
                            new_handle = driver.window_handles[-1]
                            driver.switch_to.window(new_handle)

                            # Đợi trang load xong
                            retry_count = 0
                            max_retries = 3
                            while retry_count < max_retries:
                                try:
                                    # Đợi cố định 2 giây để trang load
                                    time.sleep(2)

                                    # Tạo PDF và cache
                                    print_options = {
                                        'landscape': False,
                                        'displayHeaderFooter': False,
                                        'printBackground': True,
                                        'preferCSSPageSize': True,
                                    }
                                    pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                                    pdf_data = base64.b64decode(pdf['data'])

                                    # Kiểm tra kích thước PDF
                                    if len(pdf_data) < 1000:  # Nếu PDF quá nhỏ, có thể chưa load xong
                                        raise Exception("PDF size too small, page might not be fully loaded")

                                    # Cache file đã download
                                    cached_files[invoice_info['invoice_no']] = {
                                        'pdf_data': pdf_data,
                                        'invoice_info': invoice_info
                                    }
                                    print(f"Đã download và cache biên lai {invoice_info['invoice_no']}")
                                    break

                                except Exception as e:
                                    retry_count += 1
                                    print(f"Lỗi khi download biên lai {invoice_info['invoice_no']} (lần {retry_count}): {str(e)}")
                                    if retry_count >= max_retries:
                                        print(f"Không thể download biên lai {invoice_info['invoice_no']} sau {max_retries} lần thử")
                                    time.sleep(2)  # Tăng thời gian chờ lên 2 giây trước khi thử lại

                        except Exception as e:
                            print(f"Lỗi không mong đợi khi download biên lai {invoice_info['invoice_no']}: {str(e)}")

                        finally:
                            # Đóng tab hiện tại và chuyển về tab chính
                            try:
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                            except:
                                pass

                    # Sau khi download xong tất cả, tiến hành upload và append sheet
                    print(f"\nĐã download xong {len(cached_files)} biên lai. Bắt đầu upload lên Drive...")

                    for invoice_no, cache_data in cached_files.items():
                        try:
                            pdf_data = cache_data['pdf_data']
                            invoice_info = cache_data['invoice_info']

                            # Format ngày cho tên file
                            ngay_formatted = invoice_info['ngay'].replace('/', '') if invoice_info.get('ngay') else datetime.now().strftime('%d%m%Y')

                            # Upload lên Drive
                            upload_result = upload_file_to_drive(
                                file_content=pdf_data,
                                filename=f"CSHT_{invoice_no}.pdf",
                                parent_folder_date=ngay_formatted
                            )

                            print(json.dumps(invoice_info, indent=2, ensure_ascii=False))

                            customs_no = invoice_info.get('custom_no')
                            if customs_no and customs_no in cached_extracted_files:
                                try:
                                    cached_extracted_data = cached_extracted_files[customs_no]
                                    file_content = cached_extracted_data['file_content']
                                    header_info = cached_extracted_data['header_info']
                                    filename = header_info['source_file']

                                    upload_result = upload_file_to_drive(
                                        file_content=file_content,
                                        filename=filename,
                                        parent_folder_date=ngay_formatted  # Sử dụng cùng ngày với file biên lai
                                    )

                                    if upload_result['success']:
                                        header_info['drive_file_path'] = upload_result['file_path']
                                        drive_upload_results.append({
                                            'file': filename,
                                            'status': 'success',
                                            'path': upload_result['file_path']
                                        })
                                    else:
                                        drive_upload_results.append({
                                            'file': filename,
                                            'status': 'error',
                                            'error': upload_result.get('error', 'Unknown error')
                                        })
                                except Exception as e:
                                    print(f"Lỗi upload file cho customs_no {customs_no}: {str(e)}")

                            # Upload biên lai
                            if upload_result['success']:
                                if append_to_google_sheet_new(invoice_info):
                                    success_count += 1
                                    print(f"Đã upload và append sheet thành công cho biên lai {invoice_no}")
                            else:
                                print(f"Lỗi upload file: {upload_result.get('error')}")

                        except Exception as e:
                            print(f"Lỗi khi upload/append biên lai {invoice_no}: {str(e)}")

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

def is_table_loaded_with_data(driver, short_wait):
    """
    Kiểm tra xem bảng dữ liệu đã load hoàn tất và có dữ liệu chưa

    Args:
        driver: WebDriver instance
        short_wait: WebDriverWait instance với timeout ngắn

    Returns:
        bool: True nếu bảng đã load hoàn tất và có dữ liệu/thông báo empty
    """
    try:
        # 1. Kiểm tra sự tồn tại của bảng
        table = short_wait.until(EC.presence_of_element_located((By.ID, "TBLDANHSACH")))
        if not table:
            return False

        # 2. Kiểm tra xem bảng có đang trong trạng thái loading không
        loading_elements = driver.find_elements(By.CSS_SELECTOR, ".dataTables_processing")
        if loading_elements and loading_elements[0].is_displayed():
            return False

        # 3. Kiểm tra các row trong bảng
        rows = table.find_elements(By.TAG_NAME, "tr")

        # Nếu có nhiều hơn 1 row (tính cả header), tức là có dữ liệu
        if len(rows) > 1:
            # Kiểm tra thêm xem row đầu tiên (sau header) có cells không
            if len(rows[1].find_elements(By.TAG_NAME, "td")) > 0:
                return True

        # 4. Kiểm tra thông báo "No data available"
        empty_messages = driver.find_elements(By.CSS_SELECTOR, ".dataTables_empty")
        if empty_messages:
            # Kiểm tra xem thông báo có hiển thị không
            if empty_messages[0].is_displayed():
                return True

        # 5. Kiểm tra footer của bảng
        footer_info = driver.find_elements(By.CSS_SELECTOR, ".dataTables_info")
        if footer_info:
            footer_text = footer_info[0].text.lower()
            # Nếu footer hiển thị thông tin về số lượng bản ghi
            if "showing" in footer_text or "hiển thị" in footer_text:
                return True

        return False

    except Exception as e:
        print(f"Lỗi khi kiểm tra trạng thái bảng: {str(e)}")
        return False

def is_page_loaded(driver, short_wait=None):
    """
    Kiểm tra xem trang web đã load hoàn tất chưa

    Args:
        driver: WebDriver instance
        short_wait: WebDriverWait instance với timeout ngắn (optional)

    Returns:
        bool: True nếu trang đã load hoàn tất
    """
    try:
        # 1. Kiểm tra document.readyState
        ready_state = driver.execute_script('return document.readyState')
        if ready_state != 'complete':
            return False

        # 2. Kiểm tra jQuery (nếu trang sử dụng jQuery)
        jquery_ready = driver.execute_script('''
            if (typeof jQuery !== 'undefined') {
                return jQuery.active === 0;
            }
            return true;
        ''')
        if not jquery_ready:
            return False

        # 3. Kiểm tra các request AJAX đang pending
        ajax_complete = driver.execute_script('''
            if (window.XMLHttpRequest) {
                var openRequests = 0;
                var oldSend = XMLHttpRequest.prototype.send;

                if (typeof window._activeRequests === 'undefined') {
                    window._activeRequests = 0;
                    XMLHttpRequest.prototype.send = function() {
                        window._activeRequests++;
                        this.addEventListener('readystatechange', function() {
                            if (this.readyState === 4) {
                                window._activeRequests--;
                            }
                        });
                        oldSend.apply(this, arguments);
                    };
                }
                return window._activeRequests === 0;
            }
            return true;
        ''')
        if not ajax_complete:
            return False

        # 4. Kiểm tra các element loading phổ biến
        loading_indicators = [
            '.loading',
            '.spinner',
            '.preloader',
            '.preloader-container',
            '#loading',
            '#spinner',
            '.loading-overlay',
            '.processing'
        ]

        for indicator in loading_indicators:
            elements = driver.find_elements(By.CSS_SELECTOR, indicator)
            for element in elements:
                try:
                    if element.is_displayed():
                        return False
                except:
                    continue

        # 5. Kiểm tra animation
        animations_complete = driver.execute_script('''
            var animations = document.getAnimations
                ? document.getAnimations()
                : document.getElementsByClassName('animated');
            return animations.length === 0;
        ''')
        if not animations_complete:
            return False

        # 6. Kiểm tra các iframe (nếu có)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            try:
                if iframe.is_displayed():
                    driver.switch_to.frame(iframe)
                    iframe_ready = driver.execute_script('return document.readyState') == 'complete'
                    driver.switch_to.parent_frame()
                    if not iframe_ready:
                        return False
            except:
                driver.switch_to.parent_frame()
                continue

        # 7. Kiểm tra error messages
        error_indicators = [
            '.error',
            '.error-message',
            '#error',
            '.alert-error',
            '.alert-danger'
        ]

        for indicator in error_indicators:
            elements = driver.find_elements(By.CSS_SELECTOR, indicator)
            for element in elements:
                try:
                    if element.is_displayed():
                        error_text = element.text.lower()
                        if 'error' in error_text or 'lỗi' in error_text:
                            print(f"Phát hiện lỗi: {error_text}")
                            return False
                except:
                    continue

        return True

    except Exception as e:
        print(f"Lỗi khi kiểm tra trạng thái trang: {str(e)}")
        return False

def wait_for_page_load(driver, url, timeout=120):
    """
    Đợi cho trang web load hoàn tất

    Args:
        driver: WebDriver instance
        url: URL cần truy cập
        timeout: Thời gian tối đa chờ đợi (giây)

    Returns:
        bool: True nếu trang load thành công
    """
    short_wait = WebDriverWait(driver, 2)
    start_time = time.time()

    try:
        driver.get(url)

        while time.time() - start_time < timeout:
            if is_page_loaded(driver, short_wait):
                print(f"Trang {url} đã load hoàn tất sau {time.time() - start_time:.1f} giây")
                return True
            time.sleep(0.5)

        print(f"Timeout: Trang {url} không load hoàn tất sau {timeout} giây")
        return False

    except Exception as e:
        print(f"Lỗi khi load trang {url}: {str(e)}")
        return False
