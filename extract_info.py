import os
import sys
import platform
import json
import re
import pyodbc
import io
from datetime import datetime
from openpyxl import load_workbook
from pdfminer.high_level import extract_text
from utils import send_notification, get_download_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from time import sleep
from tenacity import retry, stop_after_attempt, wait_exponential
from threading import Thread
from queue import Queue
from google_drive_utils import upload_file_to_drive
from google_sheet_utils import append_to_google_sheet, update_last_row_sheet

def extract_text_from_pdf(pdf_path):
    """Trích xuất văn bản từ file PDF."""
    try:
        text = extract_text(pdf_path)
        sections = split_sections(text)
        return sections
    except Exception as e:
        print(f"Lỗi khi trích xuất văn bản: {e}")
        return None

def convert_price_to_number(price_str):
    """Chuyển đổi chuỗi giá tiền sang số"""
    try:
        # Loại bỏ dấu chấm và phẩy
        return int(price_str.replace('.', '').replace(',', ''))
    except:
        return 0

def split_sections(text):
    """Làm sạch và phân vùng văn bản thành header, table và footer dạng lists"""
    try:
        # Xử lý và làm sạch text
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line:  # Chỉ giữ lại các dòng không trống
                lines.append(line)

        # Tìm vị trí của các marker
        stt_index = -1
        total_index = -1

        for i, line in enumerate(lines):
            if line == "STT":
                stt_index = i
            elif line.startswith("Tổng cộng:"):
                total_index = i
                break

        if stt_index == -1 or total_index == -1:
            print("Không tìm thấy các marker để phân vùng")
            return None

        # Phân vùng dữ liệu thành lists
        sections = {
            'header': lines[:stt_index],
            'table': lines[stt_index:total_index],
            'footer': lines[total_index:]
        }
        return sections

    except Exception as e:
        print(f"Lỗi khi xử lý và phân vùng dữ liệu: {str(e)}")
        return None

def process_file_content(file):
    """
    Xử lý file upload, đọc nội dung và trích xuất thông tin

    Args:
        file: FileStorage object từ request.files

    Returns:
        dict: Chứa thông tin trích xuất và đường dẫn file đã lưu
    """
    try:
        if not file or not file.filename:
            raise ValueError('File không hợp lệ')

        # Đọc và xử lý nội dung file
        if file.filename.endswith('.pdf'):
            file_bytes = io.BytesIO(file.read())
            file_content = file_bytes.getvalue()

            text = extract_text(file_bytes)
            sections = split_sections(text)
            if sections:
                extracted_info = extract_header_info(sections['header'])
                items = extract_items(sections['table'])
                extracted_info['line_items'] = items

                customs_number = extracted_info['customs_number']
                if customs_number:
                    # Tạo queue để nhận kết quả
                    result_queue = Queue()

                    # Khởi tạo và start thread
                    query_thread = Thread(
                        target=async_query_customs_info,
                        args=(customs_number, result_queue)
                    )
                    query_thread.start()

                    # Đợi kết quả tối đa 10 giây
                    query_thread.join(timeout=10)

                    if not result_queue.empty():
                        result = result_queue.get()
                        if result.get('success'):
                            extracted_info.update({
                                'jobId': result['jobId'],
                                'hawb': result['hawb'],
                                'nguoi_khai': result['nguoi_khai']
                            })
                            send_notification(
                                f"Đã tìm thấy thông tin tờ khai: {customs_number}\n"
                                f"Job ID: {result['jobId']}\n"
                                f"HAWB: {result['hawb']}\n"
                                f"Người khai: {result['nguoi_khai']}",
                                "success"
                            )
                        else:
                            extracted_info.update({
                                'jobId': '',
                                'hawb': '',
                                'nguoi_khai': ''
                            })
                            if 'error' in result:
                                send_notification(
                                    f"Lỗi khi truy vấn thông tin tờ khai {customs_number}: {result['error']}",
                                    "error"
                                )
                            else:
                                send_notification(
                                    f"Không tìm thấy thông tin tờ khai: {customs_number}",
                                    "warning"
                                )
                    else:
                        extracted_info.update({
                            'jobId': '',
                            'hawb': '',
                            'nguoi_khai': ''
                        })
                        send_notification(
                            f"Timeout khi truy vấn thông tin tờ khai: {customs_number}",
                            "error"
                        )

                # Chuyển đổi định dạng ngày từ DD/MM/YYYY thành DDMMYYYY
                ngay_formatted = extracted_info['date'].replace('/', '')

                # Upload file lên Drive với cấu trúc thư mục
                upload_result = upload_file_to_drive(
                    file_content=file_content,
                    filename=file.filename,
                    parent_folder_date=ngay_formatted,
                    custom_no=extracted_info['customs_number']
                )

                if not upload_result['success']:
                    raise Exception(f"Lỗi upload file: {upload_result.get('error')}")

                # Thêm dữ liệu vào Google Sheet
                google_sheet_success = append_to_google_sheet(extracted_info)

                return {
                    'success': True,
                    'message': 'Trích xuất và lưu file thành công',
                    'data': extracted_info,
                    'saved_path': upload_result['file_path'],
                    'google_sheet_status': google_sheet_success
                }
            else:
                print("Không thể trích xuất văn bản từ file.")
    except Exception as e:
        print(f"Lỗi khi xử lý file: {str(e)}")
        return {
            'success': False,
            'error': f'Lỗi khi xử lý file: {str(e)}'
        }

def query_customs_info(customs_number):
    """Tạo kết nối SQL Server và truy vấn thông tin"""
    try:
        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            f"UID={os.getenv('DB_USER')};"
            f"PWD={os.getenv('DB_PASSWORD')};"
            f"Encrypt={os.getenv('DB_ENCRYPT', 'yes')};"
            f"TrustServerCertificate={os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'yes')};"
        )
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        query = """
            SELECT
                td.TransID, td.HWBNO, cs.TKSo, ui.FullName as nguoi_khai
            FROM TransactionDetails td
                JOIN CustomsDeclaration cs ON cs.MasoTK = td.CustomsID
                JOIN UserInfos ui ON ui.Username = cs.NguoiKhai
            WHERE cs.TKSo = ?
        """

        cursor.execute(query, customs_number)
        result = cursor.fetchall()
        cursor.close()
        conn.close()

        if result:
            return result
        return None

    except Exception as e:
        error_msg = f"Lỗi database: {str(e)}"
        print(error_msg)
        send_notification(error_msg, "error")
        return None

def extract_header_info(lines):
    """Extract thông tin từ văn bản sử dụng regex và logic phân tích chuỗi"""
    try:
        result = {
            'so_ct': None,
            'date': None,
            'tax_number': None,
            'customs_number': None,
            'partner_invoice_name': None
        }

        # Tìm vị trí của "Mẫu số:"
        mau_so_index = -1
        for i, line in enumerate(lines):
            if line.startswith("Mẫu số:"):
                mau_so_index = i
                break

        if mau_so_index != -1:
            # Lấy số chứng từ (line bắt đầu bằng "Số:")
            if mau_so_index + 1 < len(lines) and lines[mau_so_index + 1].startswith("Số:"):
                result['so_ct'] = lines[mau_so_index + 1].replace("Số:", "").strip()

            # Lấy ngày (line bắt đầu bằng "Ngày:")
            if mau_so_index + 2 < len(lines) and lines[mau_so_index + 2].startswith("Ngày:"):
                result['date'] = lines[mau_so_index + 2].replace("Ngày:", "").strip()

        # Tìm tên đối tác (dòng sau "Kính gửi:")
        for i, line in enumerate(lines):
            if line == "Kính gửi:":
                if i + 1 < len(lines):
                    result['partner_invoice_name'] = lines[i + 1].strip()
                break

        # Tìm mã số thuế
        for i, line in enumerate(lines):
            if line == "Mã số thuế:":
                # Tìm số thuế trong 3 dòng tiếp theo
                for j in range(i + 1, min(i + 4, len(lines))):
                    potential_tax = lines[j].strip()
                    # Kiểm tra xem có phải là số và không phải là "Địa chỉ:"
                    if potential_tax.isdigit() and potential_tax != "Địa chỉ:":
                        result['tax_number'] = potential_tax
                        break
                break

        # Tìm số tờ khai hải quan
        for i, line in enumerate(lines):
            if line == "Số tờ khai Hải quan:":
                if i + 2 < len(lines):  # +2 vì có thể có dòng trống ở giữa
                    # Lấy line tiếp theo là số tờ khai
                    customs_number = lines[i + 2].strip()
                    if customs_number.isdigit():  # Kiểm tra xem có phải là số không
                        result['customs_number'] = customs_number
                break

        # Kiểm tra kết quả
        if not all(result.values()):
            missing = [k for k, v in result.items() if v is None]
            print(f"Thiếu thông tin cho các trường: {', '.join(missing)}")

        return result

    except Exception as e:
        print(f"Lỗi khi trích xuất thông tin: {str(e)}")
        return None

def extract_items(table_data):
    """
    Trích xuất thông tin các items từ dữ liệu bảng dựa theo vị trí tương đối
    Return: List of dictionaries chứa thông tin của từng item
    """
    try:
        items = []

        # 1. Tìm số dòng dựa theo số lớn nhất giữa "STT" và "Biểu cước"
        stt_index = table_data.index("STT")
        bieu_cuoc_index = table_data.index("Biểu cước")
        numbers_between = []
        for i in range(stt_index, bieu_cuoc_index):
            if table_data[i].isdigit():
                numbers_between.append(int(table_data[i]))
        num_rows = max(numbers_between) if numbers_between else 0

        if num_rows == 0:
            return []

        # 2. Tìm vị trí bắt đầu của dữ liệu
        start_data_index = table_data.index("(7) = (5)*(6)") + 1

        # 3. Loop ngược từ cuối lên để lấy dữ liệu
        current_index = len(table_data) - 1
        amounts = []
        quantities = []
        unit_prices = []
        units = []
        container_numbers = []
        labels = []

        # Lấy amounts (số cuối cùng cho mỗi dòng)
        for _ in range(num_rows):
            while current_index >= 0 and not table_data[current_index].replace('.', '').isdigit():
                current_index -= 1
            if current_index >= 0:
                amounts.insert(0, table_data[current_index])
                current_index -= 1

        # Lấy quantities
        for _ in range(num_rows):
            while current_index >= 0 and not table_data[current_index].isdigit():
                current_index -= 1
            if current_index >= 0:
                quantities.insert(0, table_data[current_index])
                current_index -= 1

        # Lấy unit prices
        for _ in range(num_rows):
            while current_index >= 0 and not table_data[current_index].replace('.', '').isdigit():
                current_index -= 1
            if current_index >= 0:
                unit_prices.insert(0, table_data[current_index])
                current_index -= 1

        # Lấy units
        for _ in range(num_rows):
            while current_index >= 0 and table_data[current_index] != "Đồng/Container":
                current_index -= 1
            if current_index >= 0:
                units.insert(0, table_data[current_index])
                current_index -= 1

        # Lấy container numbers - không check startsWith, chỉ lấy theo vị trí
        for _ in range(num_rows):
            # Skip qua các phần tử không phải container number
            while current_index >= 0 and table_data[current_index] in ['Đồng/Container']:
                current_index -= 1
            if current_index >= 0:
                container_numbers.insert(0, table_data[current_index])
                current_index -= 1

        # Lấy labels
        for _ in range(num_rows):
            label = []
            while current_index >= start_data_index:
                if table_data[current_index] not in ['Đồng/Container']:
                    label.insert(0, table_data[current_index])
                current_index -= 1
                # Dừng khi gặp container number tiếp theo hoặc đến start_data_index
                if current_index < start_data_index:
                    break
            labels.insert(0, ' '.join(label) if label else '')

        # Tạo items
        for i in range(num_rows):
            if (i < len(container_numbers) and i < len(unit_prices) and
                i < len(quantities) and i < len(amounts)):
                item = {
                    'container_no': container_numbers[i],
                    'label': labels[i] if i < len(labels) else '',
                    'unit': units[i] if i < len(units) else 'Đồng/Container',
                    'price': int(unit_prices[i].replace('.', '')),
                    'quantity': int(quantities[i]),
                    'amount': int(amounts[i].replace('.', ''))
                }
                items.append(item)

        return items

    except Exception as e:
        print(f"Lỗi khi trích xuất items: {str(e)}")
        print(f"Chi tiết bảng dữ liệu: {table_data}")
        return []

def async_query_customs_info(customs_number, result_queue):
    """Hàm chạy trong thread riêng để query thông tin"""
    try:
        query_result = query_customs_info(customs_number)
        if query_result and len(query_result) > 0:
            result = {
                'jobId': query_result[0].TransID,
                'hawb': query_result[0].HWBNO,
                'nguoi_khai': query_result[0].nguoi_khai,
                'success': True
            }
        else:
            result = {
                'jobId': '',
                'hawb': '',
                'nguoi_khai': '',
                'success': False
            }
        result_queue.put(result)
    except Exception as e:
        result_queue.put({
            'error': str(e),
            'success': False
        })

def main():

    # Giả lập việc trích xuất từ PDF

    pdf_path = "data/BLHPH005202.pdf"
    # pdf_path = "data/BLHPH005504.pdf"
    # pdf_path = "data/4.pdf"

    sections = extract_text_from_pdf(pdf_path)
    if sections:
        result = extract_header_info(sections['header'])
        items = extract_items(sections['table'])
        result['line_items'] = items

        customs_number = result['customs_number'];
        if customs_number:
            query_result = query_customs_info(customs_number)
            if query_result and len(query_result) > 0:
                result.update({
                    'jobId': query_result[0].TransID,
                    'hawb': query_result[0].HWBNO,
                    'nguoi_khai': query_result[0].nguoi_khai
                })
            else:
                result.update({
                    'jobId': '',
                    'hawb': '',
                    'nguoi_khai': ''
                })
    else:
        print("Không thể trích xuất văn bản từ file.")

if __name__ == "__main__":
    main()






