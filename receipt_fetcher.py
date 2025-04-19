
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pyodbc

import json
import random
import platform
import requests
import subprocess
import time
import os
import base64
import json
import asyncio
import shutil
import io
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from pdfminer.high_level import extract_text

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from google_drive_utils import (
    upload_file_to_drive,
    DriveService,
    get_or_create_folder,
    check_file_exists,
    append_to_labels_file, batch_upload_to_drive
)

from google_sheet_utils import batch_append_to_sheet

from pdf_invoice_parser import (
    extract_text_from_pdf,
    extract_header_info,
    convert_price_to_number
)

from utils import get_default_customs_dir, parse_date, format_date
from cookie_manager import CookieManager
from chrome_manager import ChromeManager
from custom_api_client import (
    CustomApiClient,
    ApiCredentials,
    parse_response
)

def extract_files_info(files: List[str]) -> Tuple[List[Dict], Dict]:
    """
    Trích xuất thông tin từ danh sách files PDF

    Args:
        files: Danh sách đường dẫn files

    Returns:
        Tuple[List[Dict], Dict]: (extracted_results, cached_extracted_files)
    """
    extracted_results = []
    cached_extracted_files = {}

    for file_path in files:
        try:
            if not os.path.exists(file_path):
                print(f"File không tồn tại: {file_path}")
                continue

            with open(file_path, 'rb') as pdf_file:
                file_content = pdf_file.read()

            sections = extract_text_from_pdf(io.BytesIO(file_content))
            if not sections:
                print(f"Không thể phân tích file: {file_path}")
                continue

            header_info = extract_header_info(sections['header'])
            if header_info:
                header_info.update({
                    'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source_file': os.path.basename(file_path)
                })

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

    return extracted_results, cached_extracted_files

def batch_process_files(files: List[str]) -> Dict[str, Any]:
    """
    Xử lý nhiều file PDF cùng lúc

    Args:
        files: Danh sách đường dẫn files

    Returns:
        Dict[str, Any]: Kết quả xử lý với thông tin success/error
    """
    driver = None
    try:
        driver = ChromeManager.initialize_chrome()
        if not driver:
            raise Exception("Không thể khởi tạo Chrome driver")

        drive_upload_results = []
        download_results = []
        # 1. Trích xuất thông tin từ files
        extracted_results, cached_extracted_files = extract_files_info(files)

        # Lấy tax_number từ kết quả đầu tiên
        if not extracted_results:
            raise ValueError("Không có dữ liệu được trích xuất")

        tax_number = extracted_results[0].get('tax_number')
        if not tax_number:
            raise ValueError("Không tìm thấy tax_number trong dữ liệu trích xuất")
        # Thực hiện đăng nhập
        login_success = handle_login_process(driver, tax_number)
        if not login_success:
            raise Exception(f"Không thể đăng nhập với MST {tax_number}")

        # Truy cập trang tìm kiếm
        if not ChromeManager.wait_for_page_load(driver, "http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu"):
            raise Exception("Không thể truy cập trang tìm kiếm")

        # Tăng thời gian chờ tối đa lên 60 giây
        wait = WebDriverWait(driver, 60)
        short_wait = WebDriverWait(driver, 2)  # wait ngắn để check nhanh

        # Chờ bảng dữ liệu load xong
        try:
            preloader = short_wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
        except:
            pass

        start_time = time.time()
        while time.time() - start_time < 60:  # Tối đa 60 giây
            preloader_exists = driver.find_elements(By.CLASS_NAME, "preloader-container")

            if not preloader_exists:
                table_loaded = ChromeManager.is_table_loaded_with_data(driver, short_wait)
                if table_loaded:
                    break
            time.sleep(0.5)

        matched_results = []
        unmatched_results = extracted_results.copy()

        # Tìm kiếm trực tiếp theo số tờ khai
        print(f"\nTiến hành tìm kiếm {len(unmatched_results)} tờ khai...")
        max_retries = 3

        # Tạo một list để lưu các customs_number đã match
        matched_customs_numbers = []

        for unmatched in unmatched_results[:]:  # Tạo một copy để iterate
            customs_number = unmatched.get('customs_number')
            if not customs_number:
                continue

            print(f"\nTìm kiếm tờ khai {customs_number}...")
            try:
                # Điền số tờ khai
                so_tk_input = wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
                so_tk_input.clear()
                so_tk_input.send_keys(customs_number)

                # Thực hiện tìm kiếm với retry
                search_success = False
                retry_count = 0

                while retry_count < max_retries:
                    try:
                        search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                        driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                        driver.execute_script("arguments[0].click();", search_button)

                        if ChromeManager.wait_for_search_complete(driver):
                            search_success = True
                            break

                    except Exception as e:
                        retry_count += 1
                        if retry_count == max_retries:
                            print(f"Không thể tìm kiếm tờ khai {customs_number} sau {max_retries} lần thử")
                            break
                        time.sleep(1)

                if not search_success:
                    continue

                # Xử lý kết quả tìm kiếm
                table = driver.find_element(By.ID, "TBLDANHSACH")
                rows = table.find_elements(By.TAG_NAME, "tr")

                if len(rows) <= 1 or "No data available" in rows[1].text:
                    print(f"Không tìm thấy dữ liệu cho tờ khai {customs_number}")
                    continue

                # Lấy thông tin từ row đầu tiên
                first_row = rows[1]
                cells = first_row.find_elements(By.TAG_NAME, "td")
                found_custom_no = str(cells[4].text.strip())

                if found_custom_no == str(customs_number):
                    link_cell = cells[1]
                    link_element = link_cell.find_element(By.TAG_NAME, "a")
                    href = link_element.get_attribute("href")
                    mhd = href.split("mhd=")[-1] if "mhd=" in href else ""

                    raw_series_no = cells[7].text.strip() if len(cells) > 7 else ''
                    seriesNo = raw_series_no.split('/')[-1].strip() if '/' in raw_series_no else raw_series_no

                    matched_result = {
                        'custom_no': found_custom_no,
                        'invoice_no': cells[8].text.strip() if len(cells) > 8 else '',
                        'seriesNo': seriesNo,
                        'ngay': cells[9].text.strip() if len(cells) > 9 else '',
                        'total_amount': convert_price_to_number(cells[11].text.strip()) if len(cells) > 11 else 0,
                        'drive_link': mhd,
                        'tax_number': unmatched.get('tax_number'),
                        'so_ct': unmatched.get('so_ct', ''),
                        'partner_invoice_name': unmatched.get('partner_invoice_name', ''),
                        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    matched_results.append(matched_result)
                    matched_customs_numbers.append(customs_number)
                    print(f"Đã tìm thấy tờ khai {customs_number}")

            except Exception as e:
                print(f"Lỗi khi xử lý tờ khai {customs_number}: {str(e)}")
                continue

        # Remove các kết quả đã match khỏi unmatched_results
        unmatched_results = [result for result in unmatched_results
                           if result.get('customs_number') not in matched_customs_numbers]

        # In thống kê kết quả
        print(f"\nKết quả tìm kiếm:")
        print(f"Tổng số tờ khai: {len(extracted_results)}")
        print(f"Số tờ khai đã match: {len(matched_results)}")
        print(f"Số tờ khai chưa match: {len(unmatched_results)}")

        if unmatched_results:
            print("\nDanh sách tờ khai không tìm thấy:")
            for unmatched in unmatched_results:
                print(f"- Số tờ khai: {unmatched.get('customs_number')}")

        # Xử lý các kết quả đã match
        if matched_results:
            # Query database để lấy thêm thông tin từ API
            customs_numbers = [result['custom_no'] for result in matched_results]

            try:
                api_client = CustomApiClient()
                api_result = api_client.fetch_customs_data(customs_numbers)
                if api_result.status == "OK":
                    db_results = parse_response(api_result.data)
                    db_data = {}
                    for customs_no in customs_numbers:
                        search_customs_no = customs_no
                        if len(customs_no) == 12:
                            search_customs_no = customs_no[:-1]
                        matching_row = next(
                            (row for row in db_results if search_customs_no in row['customs_no']),
                            None
                        )

                        if matching_row:
                            db_data[customs_no] = {
                                'jobId': str(matching_row['TransID']),
                                'hawb': matching_row['hawb'],
                                'partner_id': matching_row['PartnerID'],
                                'partner_name': matching_row['PartnerName3']
                            }

                    for result in matched_results:
                        customs_no = result['custom_no']
                        if customs_no in db_data:
                            result.update({
                                'jobId': db_data[customs_no]['jobId'],
                                'hawb': db_data[customs_no]['hawb'],
                                'partner_invoice_id': db_data[customs_no]['partner_id'],
                                'partner_invoice_name': db_data[customs_no]['partner_name']
                            })
                        else:
                            print(f"Không tìm thấy dữ liệu trong API cho customs number: {customs_no}")

            except Exception as e:
                print(f"Lỗi khi query API: {str(e)}")

            success_count = process_matched_results(driver, matched_results, extracted_results)

        download_results.append({
            'tax_number': tax_number,
            'status': 'success' if success_count > 0 else 'error',
            'customs_count': len(extracted_results),
            'success_count': success_count
        })

        # Tính toán thống kê và trả về kết quả
        stats = {
            'total_files': len(files),
            'processed': len(extracted_results),
            'download_success': sum(r['success_count'] for r in download_results),
            'download_error': sum(r['customs_count'] - r['success_count'] for r in download_results),
            'drive_uploads': drive_upload_results,
            'moved_files': success_count
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
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def download_invoice_pdf(driver, invoice_info):
    """ Download PDF của biên lai từ website """
    try:
        invoice_url = f"http://thuphi.haiphong.gov.vn:8224/Viewer/HoaDonViewer.aspx?mhd={invoice_info['drive_link']}"
        driver.execute_script(f"window.open('{invoice_url}', '_blank');")
        new_handle = driver.window_handles[-1]
        driver.switch_to.window(new_handle)

        start_time = time.time()
        max_wait_time = 120
        while time.time() - start_time < max_wait_time:
            if ChromeManager.is_page_loaded(driver):
                print_options = {
                    'landscape': False,
                    'displayHeaderFooter': False,
                    'printBackground': True,
                    'preferCSSPageSize': True,
                }
                pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                pdf_data = base64.b64decode(pdf['data'])

                if len(pdf_data) < 1000:
                    print("PDF size too small, retrying...")
                    time.sleep(1)
                    continue

                return pdf_data

            time.sleep(0.1)

        raise TimeoutException(f"Timeout {max_wait_time}s chờ trang load")

    except Exception as e:
        print(f"Lỗi không mong đợi khi download biên lai {invoice_info['invoice_no']}: {str(e)}")
        return None
    finally:
        try:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass

def process_and_upload_invoices_batch(invoice_batch):
    """
    Upload nhiều PDF lên drive và append sheet theo batch
    """
    try:
        # Chuẩn bị data cho batch upload
        files_to_upload = []
        sheet_rows = []

        for invoice_info, pdf_data in invoice_batch:
            ngay_formatted = invoice_info['ngay'].replace('/', '') if invoice_info.get('ngay') else datetime.now().strftime('%d%m%Y')

            # Xử lý jobId nếu có
            job_id_prefix = ""
            if invoice_info.get('jobId'):
                # Trim và lấy phần tử đầu tiên nếu có dấu /
                job_id = invoice_info['jobId'].strip()
                if '/' in job_id:
                    job_id = job_id.split('/')[0]
                job_id_prefix = f"{job_id}-"

            filename = f"{job_id_prefix}CSHT{invoice_info['invoice_no']}.pdf"

            files_to_upload.append({
                'content': pdf_data,
                'filename': filename,
                'date_folder': ngay_formatted,
                'invoice_no': invoice_info['invoice_no']
            })

            sheet_rows.append(invoice_info)

        # Batch upload files to Drive
        upload_results = batch_upload_to_drive(files_to_upload)
        print(f"Đã upload {len(upload_results)} files lên Drive")

        # Batch append to sheet
        append_result = batch_append_to_sheet(sheet_rows)
        print(f"Đã append {len(sheet_rows)} dòng vào sheet")

        return True

    except Exception as e:
        print(f"Lỗi khi xử lý batch: {str(e)}")
        return False

def process_matched_results(driver, matched_results, extracted_results, batch_size=10):
    """
    Xử lý danh sách các biên lai đã match theo batch và di chuyển file thành công

    Args:
        driver: WebDriver instance
        matched_results: List các biên lai đã match
        extracted_results: List các kết quả trích xuất ban đầu
        batch_size: Số lượng file xử lý mỗi batch
    """
    success_count = 0
    current_batch = []

    # Get directories
    customs_dir = get_default_customs_dir()
    success_dir = os.path.join(os.path.dirname(customs_dir), 'customs_success')
    os.makedirs(success_dir, exist_ok=True)

    # Create mapping of customs numbers to source files
    customs_to_file = {
        result.get('customs_number'): result.get('source_file')
        for result in extracted_results
        if result.get('customs_number') and result.get('source_file')
    }

    # Download all PDFs first
    for invoice_info in matched_results:
        pdf_data = download_invoice_pdf(driver, invoice_info)
        if pdf_data:

            # Move source PDF file if successful
            customs_no = invoice_info.get('custom_no')
            if customs_no and customs_no in customs_to_file:
                source_file = customs_to_file[customs_no]
                invoice_info['source_file'] = source_file
                source_path = os.path.join(customs_dir, source_file)
                dest_path = os.path.join(success_dir, source_file)

                try:
                    if os.path.exists(source_path):
                        shutil.move(source_path, dest_path)
                        print(f"Đã chuyển file {source_file} sang thư mục success")
                except Exception as e:
                    print(f"Lỗi khi di chuyển file {source_file}: {str(e)}")

            current_batch.append((invoice_info, pdf_data))
            print(f"Đã download biên lai {invoice_info['invoice_no']}")
            # Process batch when reaching batch_size
            if len(current_batch) >= batch_size:
                if process_and_upload_invoices_batch(current_batch):
                    success_count += len(current_batch)
                current_batch = []

    # Process remaining files
    if current_batch:
        if process_and_upload_invoices_batch(current_batch):
            success_count += len(current_batch)

    return success_count


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def handle_login_process(driver, username):
    """
    Xử lý quá trình đăng nhập với MST cho trước

    Args:
        driver: WebDriver instance
        tax_number: Mã số thuế dùng để đăng nhập

    Returns:
        bool: True nếu đăng nhập thành công, False nếu thất bại

    Raises:
        Exception: Nếu không thể đăng nhập sau khi thử
    """
    # Default fallback credentials
    login_username = "0303482440"
    login_password = "@Mst0303482440"

    # Try to load accounts from accounts.json
    try:
        # Thử load file gốc trong development
        accounts_path = 'accounts.json'
        if not os.path.exists(accounts_path):
            # Trong production,
            accounts_path = get_resource_path(accounts_path)

        if os.path.exists(accounts_path):
            with open(accounts_path, 'r') as f:
                accounts = json.load(f)
            # Get random account
            account = random.choice(accounts)
            login_username = account['username']
            login_password = account['password']
            print(f"Sử dụng tài khoản ngẫu nhiên: {login_username}")
        else:
            print(f"Không tìm thấy file accounts tại {accounts_path}")
            print(f"Sử dụng tài khoản mặc định: {login_username}")
    except Exception as e:
        print(f"Lỗi khi đọc file accounts: {str(e)}")
        print(f"Sử dụng tài khoản mặc định: {login_username}")

    # Khởi tạo WebDriverWait với timeout dài hơn
    long_wait = WebDriverWait(driver, 120)  # 2 phút
    short_wait = WebDriverWait(driver, 2)   # 2 giây

    # Kiểm tra URL hiện tại
    current_url = driver.current_url
    is_login_page = "dang-nhap" in current_url
    is_blank_page = current_url in ["about:blank", "chrome://newtab/"]

    # Chỉ mở tab mới nếu không phải trang login hoặc trang trống
    if not (is_login_page or is_blank_page):
        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])

    # Login process
    login_success = False

    cookies_loaded = CookieManager.load_cookies(driver, username)
    if cookies_loaded:
        if ChromeManager.wait_for_page_load(driver, ChromeManager.HOME_URL):
            try:
                long_wait.until(lambda d: ChromeManager.is_page_loaded(d))
                login_success = "dang-nhap" not in driver.current_url
            except:
                print("Timeout khi đợi trang Home load hoàn tất")

    if not login_success:
        if ChromeManager.wait_for_page_load(driver, ChromeManager.LOGIN_URL):
            long_wait.until(EC.presence_of_element_located((By.ID, "form-username")))
            if ChromeManager.fill_login_info(driver, login_username, login_password):
                login_success = True

    if not login_success:
        raise Exception(f"Không thể đăng nhập với MST {username}")

    return login_success
