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
        driver = initialize_chrome()
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
                driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")

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
                        if is_table_loaded_with_data(driver, short_wait):
                            break
                    time.sleep(0.5)  # Đợi 500ms trước khi check lại

                if not is_table_loaded_with_data(driver, short_wait):
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
                clear_all_cookies_and_sessions(driver)
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

def fill_login_info(driver, username, password, max_wait_time=240):  # 4 phút timeout
    """Điền thông tin đăng nhập và đợi user login thành công"""
    wait = WebDriverWait(driver, 10)
    login_url = "http://thuphi.haiphong.gov.vn:8222/dang-nhap"
    home_url = "http://thuphi.haiphong.gov.vn:8222/Home"
    start_time = time.time()
    last_captcha = {'text': None, 'image': None}

    def is_login_successful():
        """Kiểm tra đăng nhập thành công"""
        return (driver.current_url == home_url or
                (driver.current_url != login_url and "dang-nhap" not in driver.current_url))

    def needs_refill():
        """Kiểm tra xem có cần điền lại thông tin không"""
        try:
            username_input = driver.find_element(By.ID, "form-username")
            return not username_input.get_attribute('value')
        except:
            return False

    def get_current_captcha():
        """Lấy giá trị captcha hiện tại"""
        try:
            captcha_input = driver.find_element(By.ID, "CaptchaInputText")
            return captcha_input.get_attribute('value')
        except:
            return None

    def fill_form():
        """Điền thông tin form"""
        try:
            # Đợi và điền username
            username_input = wait.until(EC.presence_of_element_located((By.ID, "form-username")))
            username_input.clear()
            username_input.send_keys(username)

            # Đợi và điền password
            password_input = wait.until(EC.presence_of_element_located((By.ID, "form-password")))
            password_input.clear()
            password_input.send_keys(password)

            # Đảm bảo focus vào ô captcha
            try:
                captcha_input = driver.find_element(By.ID, "CaptchaInputText")
                captcha_input.click()
            except:
                pass

            return True
        except Exception as e:
            print(f"Lỗi khi điền form: {str(e)}")
            return False

    # Thêm script theo dõi captcha để tự động submit
    js_script = """
    window.captchaValue = '';
    window.lastSubmittedCaptcha = '';
    window.getCaptchaValue = function() {
        return window.captchaValue;
    };

    const captchaInput = document.getElementById('CaptchaInputText');
    if (captchaInput) {
        captchaInput.addEventListener('input', function() {
            window.captchaValue = this.value;

            // Tự động submit khi đủ 5 ký tự và khác với lần submit trước
            if (this.value.length >= 5 && this.value !== window.lastSubmittedCaptcha) {
                window.lastSubmittedCaptcha = this.value;
                const submitBtn = document.querySelector('button[type="submit"]');
                if (submitBtn) {
                    console.log('Auto submitting with captcha:', this.value);
                    submitBtn.click();
                }
            }
        });

        captchaInput.addEventListener('blur', function() {
            window.captchaValue = this.value;
        });
    }
    """
    try:
        driver.execute_script(js_script)
    except:
        print("Không thể thêm script theo dõi captcha")

    # Đảm bảo đang ở trang đăng nhập
    if driver.current_url != login_url:
        driver.get(login_url)
        time.sleep(1)

    # Điền thông tin lần đầu
    if not fill_form():
        raise Exception("Không thể điền thông tin đăng nhập lần đầu")

    # Loop kiểm tra liên tục
    while time.time() - start_time < max_wait_time:
        try:
            # Cập nhật captcha cuối cùng
            current_captcha = get_current_captcha()
            if (current_captcha and
                len(current_captcha) >= 5 and
                current_captcha != last_captcha.get('text')):
                try:
                    captcha_element = driver.find_element(By.ID, "CaptchaImage")
                    last_captcha = {
                        'text': current_captcha,
                        'image': captcha_element.screenshot_as_png
                    }
                    # Thêm kiểm tra và click submit nếu chưa được click
                    try:
                        submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                        if submit_btn and submit_btn.is_enabled():
                            driver.execute_script("arguments[0].click();", submit_btn)
                    except:
                        pass

                except:
                    pass

            # Kiểm tra đăng nhập thành công
            if is_login_successful():
                # Submit tác vụ lưu dữ liệu vào thread pool
                # async_save_data(username, last_captcha, driver)
                if last_captcha['text'] and last_captcha['image']:
                    save_captcha_and_label(last_captcha['image'], last_captcha['text'])
                # save_cookies(driver, username)
                return True

            # Kiểm tra URL hiện tại
            current_url = driver.current_url

            # Nếu đang ở trang login
            if "dang-nhap" in current_url:
                # Kiểm tra thông báo lỗi
                error_messages = driver.find_elements(By.CLASS_NAME, "validation-summary-errors")
                if error_messages and any(msg.is_displayed() for msg in error_messages):
                    # Điền lại thông tin nếu form trống
                    if needs_refill():
                        fill_form()

                # Kiểm tra và điền lại nếu form trống
                elif needs_refill():
                    fill_form()

            time.sleep(0.5)  # Giảm tải CPU

        except Exception as e:
            print(f"Lỗi khi kiểm tra trạng thái: {str(e)}")
            # Nếu có lỗi, thử refresh trang và điền lại
            try:
                driver.get(login_url)
                time.sleep(1)
                fill_form()
            except:
                pass

    raise Exception(f"Hết thời gian chờ ({max_wait_time}s) - Người dùng chưa đăng nhập thành công")

def save_captcha_and_label(image_data, captcha_text):
    try:
        from google_drive_utils import upload_captcha_to_drive, append_to_labels_file
        result = upload_captcha_to_drive(image_data)

        if result['success']:
            append_result = append_to_labels_file(result['filename'], captcha_text)
            return append_result['success']
        return False

    except Exception as e:
        print(f"Lỗi khi lưu captcha và label: {e}")
        return False

def initialize_chrome(max_retries=3):
    """Khởi tạo Chrome và mở trang web"""
    for attempt in range(max_retries):
        try:
            print(f"Đang khởi tạo Chrome driver... (lần thử {attempt + 1}/{max_retries})")

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

            # Kill tất cả các process Chrome debug hiện tại
            if platform.system() == 'Windows':
                os.system('taskkill /f /im "chrome.exe" >nul 2>&1')
            else:
                os.system('pkill -f "Chrome.*--remote-debugging-port=9222" >/dev/null 2>&1')

            time.sleep(2)  # Đợi process được kill hoàn toàn

            # Khởi động Chrome mới
            chrome_options = Options()
            chrome_options.add_argument(f'--user-data-dir={default_profile}')
            chrome_options.add_argument('--remote-debugging-port=9222')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--no-default-browser-check')
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--no-sandbox')

            # Thêm một số options để tăng độ ổn định
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-popup-blocking')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')

            service = Service(ChromeDriverManager().install())

            try:
                driver = webdriver.Chrome(service=service, options=chrome_options)
                print("Đã kết nối với Chrome thành công")
                return driver
            except Exception as e:
                print(f"Lỗi khi kết nối với Chrome (lần {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:  # Nếu là lần thử cuối
                    print("Đã hết số lần thử kết nối với Chrome")
                    return None
                time.sleep(3)  # Đợi trước khi thử lại
                continue

        except Exception as e:
            print(f"Lỗi khi khởi tạo Chrome (lần {attempt + 1}): {str(e)}")
            if attempt == max_retries - 1:  # Nếu là lần thử cuối
                print("Đã hết số lần thử khởi tạo Chrome")
                return None
            time.sleep(3)  # Đợi trước khi thử lại
            continue

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

def clear_all_cookies_and_sessions(driver):
    try:
        """Xóa tất cả cookies và sessions trên browser"""
        driver.delete_all_cookies()
        # Xóa localStorage và sessionStorage
        driver.execute_script("""
            window.localStorage.clear();
            window.sessionStorage.clear();
        """)
        # Refresh trang để đảm bảo các thay đổi có hiệu lực
        driver.refresh()

        # Xóa thư mục cookies nếu tồn tại
        if os.path.exists('cookies'):
            for cookie_file in os.listdir('cookies'):
                try:
                    os.remove(os.path.join('cookies', cookie_file))
                except Exception as e:
                    print(f"Lỗi khi xóa file cookie {cookie_file}: {str(e)}")
            os.rmdir('cookies')
        return True
    except Exception as e:
        print(f"Lỗi khi xóa cookies và sessions: {str(e)}")
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
                return True
            time.sleep(0.5)
        return False

    except Exception as e:
        print(f"Lỗi khi load trang {url}: {str(e)}")
        return False

def download_invoice_pdf(driver, invoice_info):
    """
    Download PDF của biên lai từ website

    Args:
        driver: WebDriver instance
        invoice_info: Dict chứa thông tin biên lai

    Returns:
        bytes: PDF data nếu thành công, None nếu thất bại
    """
    try:
        invoice_url = f"http://thuphi.haiphong.gov.vn:8224/Viewer/HoaDonViewer.aspx?mhd={invoice_info['drive_link']}"
        driver.execute_script(f"window.open('{invoice_url}', '_blank');")
        new_handle = driver.window_handles[-1]
        driver.switch_to.window(new_handle)

        def is_page_loaded():
            content_element = driver.find_element(By.ID, "form1")
            if not content_element:
                return False
            page_state = driver.execute_script('return document.readyState;')
            return page_state == 'complete'

        start_time = time.time()
        max_wait_time = 120
        while time.time() - start_time < max_wait_time:
            if is_page_loaded():
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
        ngay_formatted = invoice_info['ngay'].replace('/', '') if invoice_info.get('ngay') else datetime.now().strftime('%d%m%Y')
        filename = f"CSHT_{invoice_info['invoice_no']}.pdf"

        drive_instance = DriveService.get_instance()
        service = drive_instance.service
        root_id = drive_instance.get_root_folder_id('CUSTOMS')

        date_folder_id = get_or_create_folder(service, root_id, ngay_formatted)
        if not date_folder_id:
            raise Exception("Không thể tạo/tìm folder ngày")

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

        # Upload related customs file if exists
        customs_no = invoice_info.get('custom_no')
        if customs_no and customs_no in cached_extracted_files:
            try:
                cached_data = cached_extracted_files[customs_no]
                customs_upload_result = upload_file_to_drive(
                    file_content=cached_data['file_content'],
                    filename=cached_data['header_info']['source_file'],
                    parent_folder_date=ngay_formatted
                )

                if customs_upload_result['success']:
                    cached_data['header_info']['drive_file_path'] = customs_upload_result['file_path']
                    drive_upload_results.append({
                        'file': cached_data['header_info']['source_file'],
                        'status': 'success',
                        'path': customs_upload_result['file_path']
                    })

                    # Move file to customs_success folder after successful upload
                    source_file = cached_data['header_info']['source_file']
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

    # cookies_loaded = load_cookies(driver, tax_number)
    # if cookies_loaded:
    #     if wait_for_page_load("http://thuphi.haiphong.gov.vn:8222/Home"):
    #         try:
    #             long_wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
    #             login_success = "dang-nhap" not in driver.current_url
    #         except:
    #             print("Timeout khi đợi trang Home load hoàn tất")

    if not login_success:
        if wait_for_page_load("http://thuphi.haiphong.gov.vn:8222/dang-nhap"):
            long_wait.until(EC.presence_of_element_located((By.ID, "form-username")))
            if fill_login_info(driver, tax_number, tax_number):
                login_success = True

    if not login_success:
        raise Exception(f"Không thể đăng nhập với MST {tax_number}")

    return login_success
