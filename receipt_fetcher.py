
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

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
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Set
from pdfminer.high_level import extract_text

# Remove Google Drive imports - now using local storage
# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from googleapiclient.http import MediaIoBaseUpload

from local_storage_utils import batch_save_to_local, get_storage_info, open_downloads_folder
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
                # Create enhanced header info with processing metadata
                enhanced_header = {
                    **header_info,
                    'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source_file': os.path.basename(file_path)
                }
                header_info = enhanced_header

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
        # Khởi tạo Chrome trong chế độ headless
        # driver = ChromeManager.initialize_chrome(auto_login=False, headless=True)
        if not driver:
            raise Exception("Không thể khởi tạo Chrome driver")

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

        drive_upload_results = []
        download_results = []

        # 1. Trích xuất thông tin từ files
        extracted_results, cached_extracted_files = extract_files_info(files)

        # Lấy tax_number từ kết quả đầu tiên
        if not extracted_results:
            raise ValueError("Không có dữ liệu được trích xuất")

        matched_results = []
        unmatched_results = extracted_results.copy()

        # Tìm kiếm trực tiếp theo số tờ khai
        max_retries = 3

        # Tạo một list để lưu các customs_number đã match
        matched_customs_numbers = []

        for unmatched in unmatched_results[:]:  # Tạo một copy để iterate
            customs_number = unmatched.get('customs_number')
            if not customs_number:
                continue
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

                    # Debug: Kiểm tra giá trị invoice_no từ web page
                    raw_invoice_no = cells[8].text.strip() if len(cells) > 8 else ''
                    print(f"DEBUG - RAW invoice_no từ web: '{raw_invoice_no}' (type: {type(raw_invoice_no)})")
                    print(f"DEBUG - Raw invoice_no repr: {repr(raw_invoice_no)}")

                    # Debug: Kiểm tra HTML raw của cell
                    if len(cells) > 8:
                        html_content = cells[8].get_attribute('innerHTML')
                        print(f"DEBUG - HTML content của cell[8]: {repr(html_content)}")

                        # Thử lấy từ các attribute khác
                        value_attr = cells[8].get_attribute('value')
                        title_attr = cells[8].get_attribute('title')
                        data_value = cells[8].get_attribute('data-value')
                        print(f"DEBUG - value attribute: {repr(value_attr)}")
                        print(f"DEBUG - title attribute: {repr(title_attr)}")
                        print(f"DEBUG - data-value attribute: {repr(data_value)}")

                    # Thử khôi phục số 0 bằng cách thêm vào đầu nếu thiếu
                    if raw_invoice_no and raw_invoice_no.isdigit() and len(raw_invoice_no) == 6:
                        # Nếu là 6 chữ số, có thể thiếu số 0 ở đầu
                        invoice_no_final = '0' + raw_invoice_no
                        print(f"DEBUG - Đã thêm số 0: '{invoice_no_final}'")
                    else:
                        invoice_no_final = str(raw_invoice_no) if raw_invoice_no else ''
                        print(f"DEBUG - Giữ nguyên: '{invoice_no_final}'")

                    print(f"DEBUG - Final invoice_no: '{invoice_no_final}' (type: {type(invoice_no_final)})")

                    matched_result = {
                        'custom_no': found_custom_no,
                        'invoice_no': invoice_no_final,
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

        if unmatched_results:
            print("\nDanh sách tờ khai không tìm thấy:")
            for unmatched in unmatched_results:
                print(f"- Số tờ khai: {unmatched.get('customs_number')}")

        # Xử lý các kết quả đã match
        if matched_results:
            for result in matched_results:
                customs_no = result['custom_no']
                try:
                    api_client = CustomApiClient()
                    api_result = api_client.fetch_customs_data([customs_no])

                    if api_result.status == "OK":
                        db_results = parse_response(api_result.data)
                        if db_results:
                            search_customs_no = customs_no
                            if len(customs_no) == 12:
                                search_customs_no = customs_no[:-1]

                            matching_row = next(
                                (row for row in db_results if search_customs_no in row['customs_no']),
                                None
                            )

                            if matching_row:
                                result.update({
                                    'jobId': str(matching_row['TransID']),
                                    'hawb': matching_row['hawb'],
                                    'partner_invoice_id': matching_row['PartnerID'],
                                    'partner_invoice_name': matching_row['PartnerName3']
                                })
                            else:
                                print(f"Không tìm thấy dữ liệu trong API cho customs number: {customs_no}")
                    else:
                        print(f"API trả về lỗi cho customs number: {customs_no}")

                except Exception as e:
                    print(f"Lỗi khi query API cho customs number {customs_no}: {str(e)}")
                    continue

            # Kiểm tra storage trước khi xử lý
            storage_ok, free_space, usage_percent = get_storage_info()
            if not storage_ok:
                print(f"⚠️  Cảnh báo: Dung lượng ổ đĩa không đủ để lưu files!")

            success_count = process_matched_results(driver, matched_results, extracted_results)
        else:
            success_count = 0

        download_results.append({
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

def download_invoice_pdf(driver, invoice_info, lock=None, max_retries=2):
    """
    Download PDF của biên lai từ website với cơ chế retry và tối ưu hóa

    Args:
        driver: WebDriver instance
        invoice_info: Thông tin biên lai cần tải
        lock: Threading lock để đồng bộ hóa truy cập vào driver (cho multithreading)
        max_retries: Số lần thử lại tối đa nếu gặp lỗi

    Returns:
        bytes: Dữ liệu PDF hoặc None nếu có lỗi
    """
    original_window = None
    new_handle = None

    # Sử dụng lock nếu được cung cấp (cho multithreading)
    if lock:
        lock.acquire()

    try:
        # Lưu lại handle của cửa sổ hiện tại
        original_window = driver.current_window_handle

        # Tạo URL và mở tab mới
        invoice_url = f"http://thuphi.haiphong.gov.vn:8224/Viewer/HoaDonViewer.aspx?mhd={invoice_info['drive_link']}"
        driver.execute_script(f"window.open('{invoice_url}', '_blank');")

        # Chuyển đến tab mới
        new_handle = driver.window_handles[-1]
        driver.switch_to.window(new_handle)

        # Giải phóng lock sau khi đã mở tab mới để các thread khác có thể tiếp tục
        if lock:
            lock.release()

        # Thử tải PDF với cơ chế retry
        for retry in range(max_retries + 1):
            try:
                # Đợi trang load xong
                start_time = time.time()
                max_wait_time = 60 if retry == 0 else 30  # Giảm thời gian chờ cho các lần thử lại

                # Sử dụng polling nhanh hơn để kiểm tra trạng thái trang
                poll_interval = 0.05
                while time.time() - start_time < max_wait_time:
                    if ChromeManager.is_page_loaded(driver):
                        # Đợi thêm một chút để đảm bảo trang đã render hoàn toàn
                        time.sleep(0.5)

                        # Cấu hình tối ưu cho PDF
                        print_options = {
                            'landscape': False,
                            'displayHeaderFooter': False,
                            'printBackground': True,
                            'preferCSSPageSize': True,
                            'scale': 1.0,  # Đảm bảo tỷ lệ 1:1
                        }

                        # Thực hiện lệnh in PDF
                        pdf = driver.execute_cdp_cmd("Page.printToPDF", print_options)
                        pdf_data = base64.b64decode(pdf['data'])

                        # Kiểm tra kích thước PDF
                        if len(pdf_data) < 1000:
                            if retry < max_retries:
                                print(f"PDF size too small ({len(pdf_data)} bytes), retrying... (lần {retry + 1}/{max_retries})")
                                time.sleep(1)
                                # Refresh trang để thử lại
                                driver.refresh()
                                break  # Thoát khỏi vòng lặp hiện tại và thử lại
                            else:
                                print(f"PDF size too small sau {max_retries} lần thử, bỏ qua")
                                return None

                        # PDF hợp lệ, trả về kết quả
                        return pdf_data

                    time.sleep(poll_interval)

                # Nếu hết thời gian chờ và chưa phải lần thử cuối cùng
                if retry < max_retries:
                    print(f"Timeout {max_wait_time}s chờ trang load, thử lại... (lần {retry + 1}/{max_retries})")
                    driver.refresh()  # Refresh trang để thử lại
                else:
                    # Đã hết số lần thử
                    raise TimeoutException(f"Timeout {max_wait_time}s chờ trang load sau {max_retries} lần thử")

            except TimeoutException as te:
                if retry == max_retries:
                    raise te  # Nếu đã hết số lần thử, ném lại ngoại lệ
            except Exception as e:
                if retry == max_retries:
                    print(f"Lỗi khi tải PDF (lần {retry + 1}/{max_retries + 1}): {str(e)}")
                    raise e  # Nếu đã hết số lần thử, ném lại ngoại lệ
                else:
                    print(f"Lỗi khi tải PDF (lần {retry + 1}/{max_retries + 1}): {str(e)}, thử lại...")

    except Exception as e:
        print(f"Lỗi không mong đợi khi download biên lai {invoice_info.get('invoice_no', '')}: {str(e)}")
        return None

    finally:
        # Đảm bảo đóng đúng tab và trả về tab ban đầu
        try:
            # Sử dụng lock khi đóng tab và chuyển về tab chính
            if lock:
                lock.acquire()

            # Kiểm tra xem tab mới có tồn tại không
            if new_handle and new_handle in driver.window_handles:
                # Đảm bảo đang ở đúng tab trước khi đóng
                current_handle = driver.current_window_handle
                if current_handle != new_handle:
                    driver.switch_to.window(new_handle)
                driver.close()

            # Trả về tab ban đầu
            if original_window and original_window in driver.window_handles:
                driver.switch_to.window(original_window)
            else:
                # Nếu không tìm thấy tab ban đầu, chuyển về tab đầu tiên
                driver.switch_to.window(driver.window_handles[0])

        except Exception as e:
            print(f"Lỗi khi đóng tab cho biên lai {invoice_info.get('invoice_no', '')}: {str(e)}")
            # Cố gắng khôi phục bằng cách chuyển về tab đầu tiên
            try:
                if driver.window_handles:
                    driver.switch_to.window(driver.window_handles[0])
            except:
                pass
        finally:
            if lock and lock.locked():
                lock.release()

def process_and_save_invoices_batch(invoice_batch):
    """
    Lưu nhiều PDF về local storage và append sheet theo batch
    """
    try:
        # Chuẩn bị data cho batch save
        files_to_save = []
        sheet_rows = []

        for invoice_info, pdf_data in invoice_batch:
            ngay_formatted = invoice_info['ngay'].replace('/', '') if invoice_info.get('ngay') else datetime.now().strftime('%d%m%Y')
            print(json.dumps(invoice_info, indent=2, ensure_ascii=False))

            # Xử lý jobId nếu có
            job_id_prefix = ""
            if invoice_info.get('jobId'):
                # Trim và lấy phần tử đầu tiên nếu có dấu /
                job_id = invoice_info['jobId'].strip()
                if '/' in job_id:
                    job_id = job_id.split('/')[0]
                job_id_prefix = f"{job_id}-"

            filename = f"{job_id_prefix}CSHT{invoice_info['invoice_no']}.pdf"
            files_to_save.append({
                'content': pdf_data,
                'filename': filename,
                'date_folder': ngay_formatted,
                'invoice_no': invoice_info['invoice_no']
            })
            sheet_rows.append(invoice_info)

        # Batch save files to local storage
        save_results = batch_save_to_local(files_to_save)
        successful_saves = sum(1 for r in save_results if r['success'])
        print(f"📁 Đã lưu {successful_saves}/{len(save_results)} files về local")

        # Batch append to sheet
        append_result = batch_append_to_sheet(sheet_rows)
        print(f"📝 Đã append {len(sheet_rows)} dòng vào sheet")

        return successful_saves > 0

    except Exception as e:
        print(f"Lỗi khi xử lý batch: {str(e)}")
        return False

def process_matched_results(driver, matched_results, extracted_results, batch_size=10, max_workers=3):
    """
    Xử lý danh sách các biên lai đã match theo batch và di chuyển file thành công
    Tải PDF tuần tự và sử dụng đa luồng để xử lý và upload

    Args:
        driver: WebDriver instance
        matched_results: List các biên lai đã match
        extracted_results: List các kết quả trích xuất ban đầu
        batch_size: Số lượng file xử lý mỗi batch
        max_workers: Số lượng worker tối đa cho ThreadPoolExecutor
    """



    success_count = 0
    driver_lock = threading.Lock()  # Lock để đồng bộ hóa truy cập vào driver
    file_move_lock = threading.Lock()  # Lock để đồng bộ việc di chuyển file

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

    def validate_pdf_match(source_path, pdf_data):
        """
        Kiểm tra xem PDF được tải về có match với thông tin của invoice không
        """
        try:
            # Có thể thêm các validation khác như:
            # - So sánh kích thước file
            # - So sánh metadata
            # - So sánh một số thông tin cơ bản trong nội dung
            return True
        except Exception as e:
            print(f"Lỗi khi validate PDF: {str(e)}")
            return False

    def move_source_files(successful_invoices):
        """
        Di chuyển các file nguồn sang thư mục success sau khi xử lý thành công
        """
        moved_count = 0
        with file_move_lock:
            for invoice_info in successful_invoices:
                try:
                    customs_no = invoice_info.get('custom_no')
                    if customs_no and customs_no in customs_to_file:
                        source_file = customs_to_file[customs_no]
                        source_path = os.path.join(customs_dir, source_file)
                        dest_path = os.path.join(success_dir, source_file)

                        if os.path.exists(source_path):
                            shutil.move(source_path, dest_path)
                            moved_count += 1
                except Exception as e:
                    customs_no = invoice_info.get('custom_no', 'unknown')
                    print(f"Lỗi khi di chuyển file {customs_no}: {str(e)}")
        return moved_count

    # Tải PDF tuần tự
    downloaded_results = []


    for invoice_info in matched_results:
        tracking_id = f"{invoice_info.get('custom_no')}_{int(time.time())}"
        try:
            pdf_data = download_invoice_pdf(driver, invoice_info, driver_lock)
            if pdf_data:
                # Validate PDF trước khi thêm vào kết quả
                source_file = customs_to_file.get(invoice_info.get('custom_no'))
                if source_file:
                    invoice_info['source_file'] = source_file

                    source_path = os.path.join(customs_dir, source_file)
                    if validate_pdf_match(source_path, pdf_data):
                        downloaded_results.append((invoice_info, pdf_data))
                    else:
                        print(f"PDF validation failed for {tracking_id}")
                else:
                    print(f"No source file found for {tracking_id}")
            else:
                print(f"Failed to download PDF for {tracking_id}")
        except Exception as e:
            print(f"Error processing invoice {tracking_id}: {str(e)}")

    # Xử lý batch upload với ThreadPool
    for i in range(0, len(downloaded_results), batch_size):
        current_batch = downloaded_results[i:i + batch_size]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future = executor.submit(process_and_save_invoices_batch, current_batch)
            try:
                if future.result():
                    # Chỉ di chuyển file khi upload và append thành công
                    successful_invoices = [invoice_info for invoice_info, _ in current_batch]
                    moved_count = move_source_files(successful_invoices)
                    success_count += moved_count
                    print(f"Successfully processed and moved {moved_count} files in current batch")
            except Exception as e:
                print(f"Error in batch upload: {str(e)}")

    return success_count

