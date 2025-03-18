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
    append_to_labels_file
)

from google_sheet_utils import append_to_google_sheet_new

from pdf_invoice_parser import (
    extract_text_from_pdf,
    extract_header_info,
    convert_price_to_number
)

from utils import get_default_customs_dir, parse_date, format_date
from cookie_manager import CookieManager
from chrome_manager import ChromeManager

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

def group_results_by_tax_number(extracted_results: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Nhóm kết quả theo tax_number và customs_number

    Args:
        extracted_results: Danh sách kết quả đã trích xuất

    Returns:
        Dict[str, List[Dict]]: Kết quả đã nhóm theo tax_number
    """
    grouped_results = {}

    for result in sorted(extracted_results, key=lambda x: x.get('tax_number', '0')):
        tax_number = result.get('tax_number')
        customs_number = result.get('customs_number')
        date_str = result.get('date')

        if not all([tax_number, customs_number, date_str]):
            continue

        if tax_number not in grouped_results:
            grouped_results[tax_number] = []

        current_date = parse_date(date_str)
        if not current_date:
            print(f"Warning: Invalid date format for {date_str}")
            continue

        existing_customs = next(
            (item for item in grouped_results[tax_number]
             if item['customs_number'] == customs_number),
            None
        )

        if existing_customs:
            existing_min_date = parse_date(existing_customs['min_date'])
            existing_max_date = parse_date(existing_customs['max_date'])

            current_min_date = current_date - timedelta(days=7)
            current_max_date = current_date + timedelta(days=7)

            if current_min_date < existing_min_date:
                existing_customs['min_date'] = format_date(current_min_date)
            if current_max_date > existing_max_date:
                existing_customs['max_date'] = format_date(current_max_date)

            existing_customs['date'] = result['date']
        else:
            new_entry = result.copy()
            new_entry['min_date'] = format_date(current_date - timedelta(days=7))
            new_entry['max_date'] = format_date(current_date + timedelta(days=7))
            grouped_results[tax_number].append(new_entry)

    return grouped_results

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
        # 2. Nhóm kết quả theo tax_number
        grouped_results = group_results_by_tax_number(extracted_results)
        # 3. Thực hiện download và write dữ liệu
        for tax_number, customs_numbers in grouped_results.items():
            session = requests.Session()
            session.verify = False
            success_count = 0

            try:
                # Xử lý đăng nhập
                if not handle_login_process(driver, tax_number):
                    print(f"Không thể đăng nhập với MST {tax_number} - bỏ qua và chuyển sang MST tiếp theo")
                    download_results.append({
                        'tax_number': tax_number,
                        'status': 'error',
                        'customs_count': len(customs_numbers),
                        'success_count': 0,
                        'error': 'Lỗi đăng nhập'
                    })
                    continue

                # Truy cập trang tìm kiếm
                if not ChromeManager.wait_for_page_load(driver, "http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu"):
                    raise Exception("Không thể truy cập trang tìm kiếm")

                # Tăng thời gian chờ tối đa lên 60 giây
                wait = WebDriverWait(driver, 60)
                short_wait = WebDriverWait(driver, 2)  # wait ngắn để check nhanh

                try:
                    preloader = short_wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
                except:
                    pass

                start_time = time.time()
                while time.time() - start_time < 60:  # Tối đa 60 giây
                    if not driver.find_elements(By.CLASS_NAME, "preloader-container"):
                        if ChromeManager.is_table_loaded_with_data(driver, short_wait):
                            break
                    time.sleep(0.5)  # Đợi 500ms trước khi check lại

                if not ChromeManager.is_table_loaded_with_data(driver, short_wait):
                    print(f"MST {tax_number}: Không thể load dữ liệu bảng sau 60 giây - bỏ qua")
                    download_results.append({
                        'tax_number': tax_number,
                        'status': 'error',
                        'customs_count': len(customs_numbers),
                        'success_count': 0,
                        'error': 'Timeout load bảng dữ liệu'
                    })
                    continue

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
                        tu_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "TU_NGAY")))
                        tu_ngay_input.clear()
                        tu_ngay_input.send_keys(customs['min_date'])

                        den_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "DEN_NGAY")))
                        den_ngay_input.clear()
                        den_ngay_input.send_keys(customs['max_date'])

                    except Exception as e:
                        print(f"MST {tax_number}: Lỗi khi điền form tìm kiếm: {str(e)} - bỏ qua")
                        download_results.append({
                            'tax_number': tax_number,
                            'status': 'error',
                            'customs_count': len(customs_numbers),
                            'success_count': 0,
                            'error': f'Lỗi điền form: {str(e)}'
                        })
                        continue

                    search_success = False
                    max_retries = 3
                    retry_count = 0

                    while retry_count < max_retries:
                        try:
                            search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                            driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                            driver.execute_script("arguments[0].click();", search_button)

                            def is_search_complete():
                                try:
                                    if driver.find_elements(By.CLASS_NAME, "preloader-container"):
                                        return False
                                    table = driver.find_element(By.ID, "TBLDANHSACH")
                                    if not table:
                                        return False

                                    new_rows = len(driver.find_elements(By.CSS_SELECTOR, "#TBLDANHSACH tr"))
                                    has_no_data = bool(driver.find_elements(By.CSS_SELECTOR, ".dataTables_empty"))

                                    if new_rows > 0 or has_no_data:
                                        return True
                                    return False
                                except Exception:
                                    return False

                            start_time = time.time()
                            while time.time() - start_time < 30:
                                if is_search_complete():
                                    search_success = True
                                    break
                                time.sleep(0.1)

                            if search_success:
                                break

                        except Exception as e:
                            retry_count += 1
                            if retry_count == max_retries:
                                print(f"MST {tax_number}: Không thể hoàn thành tìm kiếm sau {max_retries} lần thử - bỏ qua")
                                download_results.append({
                                    'tax_number': tax_number,
                                    'status': 'error',
                                    'customs_count': len(customs_numbers),
                                    'success_count': 0,
                                    'error': f'Lỗi tìm kiếm sau {max_retries} lần thử'
                                })
                                continue
                            time.sleep(1)

                try:
                    # Tìm bảng và trích xuất số tờ khai
                    table = driver.find_element(By.ID, "TBLDANHSACH")
                    rows = table.find_elements(By.TAG_NAME, "tr")
                except Exception as e:
                    print(f"MST {tax_number}: Lỗi khi tìm bảng dữ liệu: {str(e)} - bỏ qua")
                    download_results.append({
                        'tax_number': tax_number,
                        'status': 'error',
                        'customs_count': len(customs_numbers),
                        'success_count': 0,
                        'error': f'Lỗi load bảng: {str(e)}'
                    })
                    continue

            except Exception as e:
                print(f"MST {tax_number}: Lỗi không xác định: {str(e)} - bỏ qua")
                download_results.append({
                    'tax_number': tax_number,
                    'status': 'error',
                    'customs_count': len(customs_numbers),
                    'success_count': 0,
                    'error': f'Lỗi không xác định: {str(e)}'
                })
                continue

            matched_results = []
            for row in rows[1:]:  # Bỏ qua row đầu tiên (header)
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) == 1 and "No data available" in cells[0].text:
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

                        raw_series_no = cells[7].text.strip() if len(cells) > 7 else ''
                        seriesNo = raw_series_no.split('/')[-1].strip() if '/' in raw_series_no else raw_series_no

                        result = {
                            'custom_no': custom_no,
                            'invoice_no': cells[8].text.strip() if len(cells) > 8 else '',
                            'seriesNo': seriesNo,
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
                    continue

            if len(matched_results) != len(customs_numbers):
                matched_customs_numbers = {str(result['custom_no']) for result in matched_results}
                unmatched_customs = [
                    customs for customs in customs_numbers
                    if str(customs['customs_number']) not in matched_customs_numbers
                ]
                for customs in unmatched_customs:
                    try:
                        so_tk_input = wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
                        so_tk_input.clear()
                        so_tk_input.send_keys(customs['customs_number'])

                        # tu_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "TU_NGAY")))
                        # tu_ngay_input.clear()

                        # den_ngay_input = wait.until(EC.presence_of_element_located((By.NAME, "DEN_NGAY")))
                        # den_ngay_input.clear()

                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnSearch")))
                                driver.execute_script("arguments[0].scrollIntoView(true);", search_button)
                                driver.execute_script("arguments[0].click();", search_button)
                                # time.sleep(10)

                                def is_search_complete():
                                    try:
                                        if driver.find_elements(By.CLASS_NAME, "preloader-container"):
                                            return False
                                        table = driver.find_element(By.ID, "TBLDANHSACH")
                                        if not table:
                                            return False
                                        new_rows = len(driver.find_elements(By.CSS_SELECTOR, "#TBLDANHSACH tr"))
                                        has_no_data = bool(driver.find_elements(By.CSS_SELECTOR, ".dataTables_empty"))
                                        if new_rows > 0 or has_no_data:
                                            return True
                                        return False
                                    except Exception:
                                        return False

                                start_time = time.time()
                                search_completed = False
                                while time.time() - start_time < 30:
                                    if is_search_complete():
                                        search_completed = True
                                        break
                                    time.sleep(0.1)  # Check mỗi 100ms

                                if search_completed:
                                    break  # Thoát khỏi vòng lặp retry
                                else:
                                    raise TimeoutException("Timeout chờ kết quả tìm kiếm")

                            except Exception as e:
                                retry_count += 1
                                print(f"- Lỗi: {str(e)}")
                                if retry_count == max_retries:
                                    raise Exception(f"Không thể hoàn thành tìm kiếm sau {max_retries} lần thử")
                                print(f"- Đợi 4s trước khi thử lại...")
                                time.sleep(4)  # Tăng thời gian chờ giữa các lần thử

                        table = driver.find_element(By.ID, "TBLDANHSACH")
                        rows = table.find_elements(By.TAG_NAME, "tr")

                        if len(rows) <= 1:  # Chỉ có header
                            continue

                        first_row = rows[1]
                        cells = first_row.find_elements(By.TAG_NAME, "td")

                        if len(cells) == 1 and "No data available" in cells[0].text:
                            continue

                        found_custom_no = str(cells[4].text.strip())
                        print(f"Đã tìm thấy tờ khai {found_custom_no}")

                        if found_custom_no == str(customs['customs_number']):
                            try:
                                link_cell = cells[1]
                                link_element = link_cell.find_element(By.TAG_NAME, "a")
                                href = link_element.get_attribute("href")
                                mhd = href.split("mhd=")[-1] if "mhd=" in href else ""

                                raw_series_no = cells[7].text.strip() if len(cells) > 7 else ''
                                seriesNo = raw_series_no.split('/')[-1].strip() if '/' in raw_series_no else raw_series_no

                                result = {
                                    'custom_no': found_custom_no,
                                    'invoice_no': cells[8].text.strip() if len(cells) > 8 else '',
                                    'seriesNo': seriesNo,
                                    'ngay': cells[9].text.strip() if len(cells) > 9 else '',
                                    'total_amount': convert_price_to_number(cells[11].text.strip()) if len(cells) > 11 else 0,
                                    'drive_link': mhd,
                                    'tax_number': customs.get('tax_number'),
                                    'so_ct': customs.get('so_ct', ''),
                                    'partner_invoice_name': customs.get('partner_invoice_name', ''),
                                    'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                matched_results.append(result)
                            except:
                                print(f"Lỗi khi trích xuất dữ liệu tờ khai {found_custom_no}")
                                print(f"Cells: {cells}")
                                continue

                        else:
                            continue

                    except Exception as e:
                        print(f"Lỗi khi tìm kiếm tờ khai {customs['customs_number']}: {str(e)}")
                        continue

                # Thông báo kết quả cuối cùng
                final_unmatched = [
                    customs for customs in customs_numbers
                    if str(customs['customs_number']) not in {str(result['custom_no']) for result in matched_results}
                ]

                if final_unmatched:
                    print("\nDanh sách tờ khai không tìm thấy và sẽ bị bỏ qua:")
                    for customs in final_unmatched:
                        print(f"- Số tờ khai: {customs['customs_number']}")

            success_count, drive_upload_results = process_matched_results(driver, matched_results, cached_extracted_files)

            download_results.append({
                'tax_number': tax_number,
                'status': 'success' if success_count > 0 else 'error',
                'customs_count': len(customs_numbers),
                'success_count': success_count
            })

            # Redirect về trang login sau khi xử lý xong tax_number
            try:
                CookieManager.clear_all_cookies_and_sessions(driver)
                driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
            except Exception as e:
                print(f"Lỗi khi redirect về trang login: {str(e)}")

            try:
                if 'session' in locals():
                    session.close()
            except:
                pass

        # Tính toán thống kê và trả về kết quả
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

def process_and_upload_invoice(invoice_info, pdf_data, cached_extracted_files, drive_upload_results):
    """
    Upload PDF lên drive và append vào sheet, sau đó di chuyển file đã xử lý vào thư mục success
    """
    try:
        customs_no = invoice_info.get('custom_no')

        ngay_formatted = invoice_info['ngay'].replace('/', '') if invoice_info.get('ngay') else datetime.now().strftime('%d%m%Y')


        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_id = drive_instance.get_root_folder_id('CUSTOMS')

        date_folder_id = get_or_create_folder(service, root_id, ngay_formatted)
        if not date_folder_id:
            raise Exception("Không thể tạo/tìm folder ngày")

        filename = f"CSHT_{invoice_info['invoice_no']}.pdf"
        pattern = ['BEHPH', 'BLHPH', 'BIHPH', 'BEHAN', 'BLHAN', 'BIHAN', 'BLDAD', 'BEDAD', 'BIDAD', 'BEHCM', 'BLHCM', 'BIHCM']

        # Upload related customs file if exists
        if customs_no and customs_no in cached_extracted_files:
            try:
                cached_data = cached_extracted_files[customs_no]
                source_file = cached_data['header_info']['source_file']

                # Xử lý source_file để tạo prefix cho filename
                prefix = None
                for p in pattern:
                    if p in source_file:
                        # Lấy phần text trước pattern và xử lý
                        prefix = source_file[:source_file.index(p)].strip()
                        prefix = prefix.replace(' ', '_')
                        break

                if prefix:
                    filename = f"{prefix}_{filename}"

                customs_upload_result = upload_file_to_drive(
                    file_content=cached_data['file_content'],
                    filename=source_file,
                    parent_folder_date=ngay_formatted
                )

                if customs_upload_result['success']:
                    cached_data['header_info']['drive_file_path'] = customs_upload_result['file_path']
                    drive_upload_results.append({
                        'file': source_file,
                        'status': 'success',
                        'path': customs_upload_result['file_path']
                    })

                    # Move file to customs_success folder after successful upload
                    source_path = os.path.join(get_default_customs_dir(), source_file)
                    success_dir = os.path.join(get_default_customs_dir(), 'customs_success')

                    # Create customs_success directory if it doesn't exist
                    if not os.path.exists(success_dir):
                        os.makedirs(success_dir)

                    target_path = os.path.join(success_dir, source_file)

                    try:
                        # If file already exists in success folder, replace it
                        if os.path.exists(target_path):
                            os.remove(target_path)
                        shutil.move(source_path, target_path)
                        print(f"Đã di chuyển file {source_file} vào thư mục customs_success")
                    except Exception as move_error:
                        print(f"Lỗi khi di chuyển file {source_file}: {str(move_error)}")

                else:
                    drive_upload_results.append({
                        'file': cached_data['header_info']['source_file'],
                        'status': 'error',
                        'error': customs_upload_result.get('error', 'Unknown error')
                    })
            except Exception as e:
                print(f"Lỗi upload file cho customs_no {customs_no}: {str(e)}")

        file_exists, existing_file_id = check_file_exists(service, date_folder_id, filename)

        if file_exists:
            print(f"File {filename} đã tồn tại trong thư mục {ngay_formatted}")
            upload_result = {
                'success': True,
                'file_id': existing_file_id,
                'file_path': f"{ngay_formatted}/{filename}",
                'already_exists': True
            }
        else:
            upload_result = upload_file_to_drive(
                file_content=pdf_data,
                filename=filename,
                parent_folder_date=ngay_formatted
            )

        if upload_result['success']:
            if append_to_google_sheet_new(invoice_info):
                print(f"Đã upload và append sheet thành công cho biên lai {invoice_info['invoice_no']}")
                return True
        else:
            print(f"Lỗi upload file: {upload_result.get('error')}")

        return False

    except Exception as e:
        print(f"Lỗi khi upload/append biên lai {invoice_info['invoice_no']}: {str(e)}")
        return False

def process_matched_results(driver, matched_results, cached_extracted_files):
    """
    Xử lý danh sách các biên lai đã match

    Args:
        driver: WebDriver instance
        matched_results: List các biên lai đã match
        cached_extracted_files: Dict chứa các file đã extract

    Returns:
        tuple: (success_count, drive_upload_results)
    """
    success_count = 0
    drive_upload_results = []
    cached_files = {}

    # Download all PDFs first
    for invoice_info in matched_results:
        pdf_data = download_invoice_pdf(driver, invoice_info)
        if pdf_data:
            cached_files[invoice_info['invoice_no']] = {
                'pdf_data': pdf_data,
                'invoice_info': invoice_info
            }
            print(f"Đã download và cache biên lai {invoice_info['invoice_no']}")

    # Process and upload files
    for invoice_no, cache_data in cached_files.items():
        if process_and_upload_invoice(
            cache_data['invoice_info'],
            cache_data['pdf_data'],
            cached_extracted_files,
            drive_upload_results
        ):
            success_count += 1

    return success_count, drive_upload_results

def handle_login_process(driver, tax_number):
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

    cookies_loaded = CookieManager.load_cookies(driver, tax_number)
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
            if ChromeManager.fill_login_info(driver, tax_number, tax_number):
                login_success = True

    if not login_success:
        raise Exception(f"Không thể đăng nhập với MST {tax_number}")

    return login_success
