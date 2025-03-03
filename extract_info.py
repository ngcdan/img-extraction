import os
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

def append_to_google_sheet(extracted_info):
    """Thêm thông tin vào Google Sheet với retry logic"""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=lambda e: isinstance(e, HttpError) and e.resp.status_code in [500, 503]
    )
    def execute_append(sheet, values, spreadsheet_id, range_name):
        body = {'values': values}
        return sheet.values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()

    try:
        # Cấu hình credentials
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        SERVICE_ACCOUNT_FILE = './service-account-key.json'
        SPREADSHEET_ID = '1OWxsCEHLzkVGv2sYheAmrHLeLswgeskGx72Q-Sze2LM'
        RANGE_NAME = 'main!A:V'

        # Kiểm tra file credentials tồn tại
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            send_notification("File service account không tồn tại", "error")
            return False

        # Khởi tạo credentials
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        except Exception as e:
            send_notification(f"Lỗi khởi tạo credentials: {str(e)}", "error")
            return False

        # Khởi tạo service
        try:
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
        except Exception as e:
            send_notification(f"Lỗi khởi tạo Google Sheets service: {str(e)}", "error")
            return False

        # Validate input data
        line_items = extracted_info.get('line_items', []);
        if not line_items:
            send_notification("Không có thông tin container để thêm vào Sheet", "warning")
            return False

        # Lấy số dòng hiện tại với retry
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            current_row = len(result.get('values', []))
        except HttpError as e:
            send_notification(f"Lỗi khi đọc dữ liệu từ sheet: {str(e)}", "error")
            return False

        # Chuẩn bị dữ liệu
        values = []
        for line in line_items:
            fixed_data = {
                'service_code': 'CL014920',
                'vendor': 'VETC',
                'charge_code': 'B_EWF',
                'description': 'EXPRESS WAY FEES',
                'unit': 'shipment'
            }

            row_data = [
                current_row,  # STT
                extracted_info.get('so_ct', ''),  # Số chứng từ
                fixed_data['service_code'],
                fixed_data['vendor'],
                extracted_info.get('jobId', ''),
                extracted_info.get('hawb', ''),
                extracted_info.get('customs_number', ''),
                fixed_data['charge_code'],
                fixed_data['description'],
                line.get('quantity', ''),
                fixed_data['unit'],
                line.get('unit_price', ''),
                '',  # Cột 12 để trống
                line.get('amount', ''),
                '', '', '', '',
                extracted_info.get('tax_number'),
                extracted_info.get('partner_invoice_name'),
                '',  # Cột 20 để trống (Notes)
                line.get('container_no', ''),
                line.get('label', '')
            ]
            values.append(row_data)
            current_row += 1

        # Thực hiện append với retry
        try:
            execute_append(sheet, values, SPREADSHEET_ID, RANGE_NAME)
            send_notification(f"Đã thêm {len(line_items)} dòng vào Google Sheet", "success")
            return True
        except Exception as e:
            send_notification(f"Lỗi sau 3 lần thử append dữ liệu: {str(e)}", "error")
            return False

    except Exception as e:
        send_notification(f"Lỗi không mong đợi: {str(e)}", "error")
        return False

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

        # In ra console dạng JSON
        print("\n=== SECTIONS JSON ===")
        print(json.dumps(sections, indent=2, ensure_ascii=False))

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
            print(f"Đang xử lý file: {file.filename}")
            if sections:
                extracted_info = extract_header_info(sections['header'])
                items = extract_items(sections['table'])
                print(json.dumps(items, indent=2, ensure_ascii=False))

                extracted_info['line_items'] = items

                customs_number = extracted_info['customs_number'];
                if customs_number:
                    query_result = query_customs_info(customs_number)
                    if query_result and len(query_result) > 0:
                        extracted_info.update({
                            'jobId': query_result[0].TransID,
                            'hawb': query_result[0].HWBNO,
                            'nguoi_khai': query_result[0].nguoi_khai
                        })
                    else:
                        extracted_info.update({
                            'jobId': '',
                            'hawb': '',
                            'nguoi_khai': ''
                        })

                print(json.dumps(extracted_info, indent=2, ensure_ascii=False))
                # Chuyển đổi định dạng ngày từ DD/MM/YYYY thành DDMMYYYY
                ngay_formatted = extracted_info['date'].replace('/', '')

                # Tạo cấu trúc thư mục
                base_dir = get_download_directory()
                date_dir = os.path.join(base_dir, ngay_formatted)
                so_tk_dir = os.path.join(date_dir, extracted_info['customs_number'])
                # Tạo các thư mục nếu chưa tồn tại
                for directory in [base_dir, date_dir, so_tk_dir]:
                    if not os.path.exists(directory):
                        os.makedirs(directory)
                        print(f"Đã tạo thư mục: {directory}")

                # Xử lý tên file và đường dẫn
                full_path = os.path.join(so_tk_dir, file.filename)
                if os.path.exists(full_path):
                    base_name, ext = os.path.splitext(file.filename)
                    counter = 1
                    while os.path.exists(full_path):
                        new_filename = f"{base_name}_{counter}{ext}"
                        full_path = os.path.join(so_tk_dir, new_filename)
                        counter += 1

                # Lưu file
                with open(full_path, 'wb') as f:
                    f.write(file_content)

                print(f"Đã lưu file: {full_path}")

                # Thêm dữ liệu vào Google Sheet
                google_sheet_success = append_to_google_sheet(extracted_info)

                return {
                    'success': True,
                    'message': 'Trích xuất và lưu file thành công',
                    'data': extracted_info,
                    'saved_path': full_path,
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

# Hàm tạo kết nối SQL Server và thực hiện truy vấn
def query_customs_info(customs_number):
    """Tạo kết nối SQL Server và truy vấn thông tin dựa trên số tờ khai"""
    try:
        # Chuỗi kết nối SQL Server từ biến môi trường
        conn_str = (
            f"DRIVER={{{os.getenv('DB_DRIVER')}}};"
            f"SERVER={os.getenv('DB_SERVER')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            f"UID={os.getenv('DB_USER')};"
            f"PWD={os.getenv('DB_PASSWORD')};"
            f"Encrypt={os.getenv('DB_ENCRYPT')};"
            f"TrustServerCertificate={os.getenv('DB_TRUST_SERVER_CERTIFICATE')};"
        )

        # Tạo kết nối
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Truy vấn SQL với số tờ khai
        query = """
            SELECT
                td.TransID, td.HWBNO, cs.TKSo, ui.FullName as nguoi_khai
            FROM TransactionDetails td
                JOIN CustomsDeclaration cs ON cs.MasoTK = td.CustomsID
                JOIN UserInfos ui ON ui.Username = cs.NguoiKhai
            WHERE cs.TKSo = ?
        """

        # Thực hiện truy vấn với tham số
        cursor.execute(query, customs_number)
        result = cursor.fetchall()

        # Đóng kết nối
        cursor.close()
        conn.close()

        if result:
            print("\nKết quả truy vấn từ cơ sở dữ liệu:")
            for row in result:
                print(f"TransID: {row.TransID}, HWBNO: {row.HWBNO}, TKSo: {row.TKSo}, Người khai: {row.nguoi_khai}")
            return result
        else:
            print("Không tìm thấy dữ liệu phù hợp trong cơ sở dữ liệu.")
            return None

    except pyodbc.Error as e:
        send_notification(f"Lỗi khi kết nối hoặc truy vấn cơ sở dữ liệu: {str(e)}", "error")
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

def update_last_row_sheet(invoice_info):
    """Cập nhật thông tin invoice cho dòng cuối cùng trong Google Sheet"""
    try:
        # Cấu hình credentials
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        SERVICE_ACCOUNT_FILE = './service-account-key.json'
        SPREADSHEET_ID = '1OWxsCEHLzkVGv2sYheAmrHLeLswgeskGx72Q-Sze2LM'
        RANGE_NAME = 'main!A:V'

        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            send_notification("File service account không tồn tại", "error")
            return False

        # Khởi tạo credentials và service
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
        except Exception as e:
            send_notification(f"Lỗi khởi tạo service: {str(e)}", "error")
            return False

        # Lấy số dòng hiện tại
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            values = result.get('values', [])
            last_row = len(values)

            if last_row == 0:
                send_notification("Không có dữ liệu trong sheet", "error")
                return False

            # Cập nhật các ô cần thiết ở dòng cuối
            update_range = f'main!P{last_row}:R{last_row}'  # Cột O-Q (15-17)
            update_values = [[
                invoice_info.get('invoice_no', ''),
                invoice_info.get('seriesNo', ''),
                invoice_info.get('ngay', '')
            ]]

            body = {
                'values': update_values
            }

            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            send_notification("Đã cập nhật thông tin invoice thành công", "success")
            return True

        except HttpError as e:
            send_notification(f"Lỗi khi cập nhật Google Sheet: {str(e)}", "error")
            return False

    except Exception as e:
        send_notification(f"Lỗi không mong đợi: {str(e)}", "error")
        return False

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
            print(f"Query result: {query_result}")
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

        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Không thể trích xuất văn bản từ file.")

if __name__ == "__main__":
    main()






