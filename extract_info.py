import os
import json
import re
import pyodbc
import io
from datetime import datetime
from openpyxl import load_workbook
from pdfminer.high_level import extract_text
from utils import send_notification
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
        line_items = extracted_info.get('line_items', {}).get('items', [])
        if not line_items:
            send_notification("Không có thông tin container để thêm vào Sheet", "warning")
            return False

        # Lấy số dòng hiện tại với retry
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            current_row = len(result.get('values', [])) + 1
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
                extracted_info.get('jobID', ''),
                extracted_info.get('hawb', ''),
                fixed_data['charge_code'],
                fixed_data['description'],
                line.get('quantity', ''),
                fixed_data['unit'],
                line.get('unit_price', ''),
                '',  # Cột 12 để trống
                line.get('total', ''),
                '', '', '', '', '', '', '',  # Cột 14-20 để trống
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
        return text
    except Exception as e:
        print(f"Lỗi khi trích xuất văn bản: {e}")
        return None

def extract_so_chung_tu_regex(text):
    """Sử dụng regex để tìm số sau chữ 'Số:'"""
    # Pattern tìm dòng bắt đầu bằng 'Số:' và lấy chuỗi số
    pattern = r'Số:\s*(\d+)'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

def extract_date_by_lines(text):
    """Trích xuất ngày từ văn bản"""
    lines = text.split('\n')
    found_so = False

    for line in lines:
        line = line.strip()
        # Tìm dòng bắt đầu bằng "Số:"
        if line.startswith("Số:"):
            found_so = True
            continue

        # Nếu đã tìm thấy "Số:", kiểm tra dòng tiếp theo bắt đầu bằng "Ngày:"
        if found_so and line.startswith("Ngày:"):
            # Tách và lấy phần ngày
            date = line.split(":")[-1].strip()
            return date

    return None

def extract_so_ct_by_lines(text):
    """Tìm số bằng cách xử lý từng dòng"""
    lines = text.split('\n')
    found_mau_so = False

    for line in lines:
        line = line.strip()
        # Tìm dòng bắt đầu bằng "Mẫu số:"
        if line.startswith("Mẫu số:"):
            found_mau_so = True
            continue

        # Nếu đã tìm thấy "Mẫu số:", kiểm tra dòng tiếp theo
        if found_mau_so and line.startswith("Số:"):
            # Tách và lấy phần số
            number = line.split(":")[-1].strip()
            # Chỉ lấy các ký tự số
            number = ''.join(filter(str.isdigit, number))
            return number

    return None

def extract_tax_number(text):
    """Trích xuất mã số thuế từ văn bản"""
    lines = text.split('\n')
    found_tax_label = False
    found_address_label = False
    next_line_data = False

    for i, line in enumerate(lines):
        line = line.strip()

        # Tìm dòng "Mã số thuế:"
        if line == "Mã số thuế:":
            found_tax_label = True
            continue

        # Tìm dòng "Địa chỉ:"
        if line == "Địa chỉ:":
            found_address_label = True
            continue

        # Nếu đã tìm thấy cả 2 label và gặp dòng trống
        if found_tax_label and found_address_label and line == "":
            next_line_data = True
            continue

        # Lấy dữ liệu ở dòng tiếp theo sau dòng trống
        if next_line_data and line:
            # Kiểm tra xem dòng có phải là số không
            if line.isdigit():
                return line
            break

    return None

def extract_customs_declaration(text):
    """Trích xuất số tờ khai hải quan từ văn bản"""
    lines = text.split('\n')
    found_customs_label = False
    found_fee_label = False
    next_line_data = False

    for i, line in enumerate(lines):
        line = line.strip()

        # Tìm dòng "Số tờ khai Hải quan:"
        if line == "Số tờ khai Hải quan:":
            found_customs_label = True
            continue

        # Tìm dòng "Tờ khai nộp phí:"
        if line == "Tờ khai nộp phí:":
            found_fee_label = True
            continue

        # Nếu đã tìm thấy cả 2 label và gặp dòng trống
        if found_customs_label and found_fee_label and line == "":
            next_line_data = True
            continue

        # Lấy dữ liệu ở dòng tiếp theo sau dòng trống
        if next_line_data and line:
            # Kiểm tra xem dòng có phải là số không
            if line.isdigit():
                return line
            break

    return None

def extract_total_amount(text):
    """Trích xuất tổng số tiền từ văn bản"""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if "Tổng tiền phí phải nộp:" in line:
            # Lấy số tiền ở dòng tiếp theo
            if i + 1 < len(lines):
                amount_str = lines[i + 1].strip()
                # Chuyển đổi chuỗi tiền thành số
                return convert_price_to_number(amount_str)
    return 0

# Thêm hàm kiểm tra định dạng số tờ khai
def validate_customs_number(number):
    """Kiểm tra định dạng số tờ khai hải quan"""
    if not number:
        return False

    # Kiểm tra độ dài (thường là 12 số)
    if len(number) != 12:
        return False

    # Kiểm tra chỉ chứa số
    if not number.isdigit():
        return False

    return True

def count_lines(text):
    """Đếm số lines dựa trên format chuẩn"""
    lines = text.split('\n')
    try:
        # Tìm vị trí của "STT" và "Biểu cước"
        stt_index = next(i for i, line in enumerate(lines) if line.strip() == "STT")
        bieu_cuoc_index = next(i for i, line in enumerate(lines) if line.strip() == "Biểu cước")

        # Đếm số số thứ tự giữa "STT" và "Biểu cước"
        numbers = []
        for line in lines[stt_index:bieu_cuoc_index]:
            if line.strip().isdigit():
                numbers.append(int(line.strip()))

        return len(numbers)
    except Exception as e:
        print(f"Lỗi khi đếm số lines: {str(e)}")
        return 0

def extract_items(text):
    """Trích xuất thông tin container từ văn bản"""
    try:
        lines = text.split('\n')
        num_lines = count_lines(text)
        if num_lines == 0:
            return None

        # Tìm vị trí bắt đầu của thông tin
        start_index = -1
        for i, line in enumerate(lines):
            if "(7) = (5)*(6)" in line:
                start_index = i + 1
                break

        if start_index == -1:
            return None

        # Khởi tạo list để lưu thông tin các lines
        container_items = []
        current_index = start_index

        # Đọc từng block thông tin
        while current_index < len(lines):
            try:
                item = {}

                # Đọc label (Container...)
                while current_index < len(lines):
                    line = lines[current_index].strip()
                    if line and "Container" in line:
                        item['label'] = line
                        current_index += 1
                        break
                    current_index += 1

                # Nếu không tìm thấy label, thoát khỏi vòng lặp
                if 'label' not in item:
                    break

                # Đọc container number
                while current_index < len(lines):
                    line = lines[current_index].strip()
                    if line:
                        item['container_no'] = line
                        current_index += 1
                        break
                    current_index += 1

                # Bỏ qua "Đồng/Container"
                while current_index < len(lines):
                    line = lines[current_index].strip()
                    if line == "Đồng/Container":
                        current_index += 1
                        break
                    current_index += 1

                # Đọc unit price
                while current_index < len(lines):
                    line = lines[current_index].strip()
                    if line and any(c.isdigit() for c in line):
                        item['unit_price'] = convert_price_to_number(line)
                        current_index += 1
                        break
                    current_index += 1

                # Đọc quantity
                while current_index < len(lines):
                    line = lines[current_index].strip()
                    if line and line.isdigit():
                        item['quantity'] = int(line)
                        current_index += 1
                        break
                    current_index += 1

                # Đọc total
                while current_index < len(lines):
                    line = lines[current_index].strip()
                    if line and any(c.isdigit() for c in line):
                        item['total'] = convert_price_to_number(line)
                        current_index += 1
                        break
                    current_index += 1

                # Kiểm tra xem đã có đủ thông tin chưa
                required_fields = ['label', 'container_no', 'unit_price', 'quantity', 'total']
                if all(field in item for field in required_fields):
                    container_items.append(item)

                # Kiểm tra nếu đã đủ số lines
                if len(container_items) >= num_lines:
                    break

            except Exception as e:
                print(f"Lỗi khi xử lý item: {str(e)}")
                continue

        # Kiểm tra kết quả
        if not container_items:
            print("Không tìm thấy thông tin container hợp lệ")
            return None

        return {
            'num_lines': len(container_items),
            'items': container_items,
            'total_amount': sum(item['total'] for item in container_items)
        }

    except Exception as e:
        print(f"Lỗi khi trích xuất thông tin container: {str(e)}")
        return None

def convert_price_to_number(price_str):
    """Chuyển đổi chuỗi giá tiền sang số"""
    try:
        # Loại bỏ dấu chấm và phẩy
        return int(price_str.replace('.', '').replace(',', ''))
    except:
        return 0

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

        print(f"Đang xử lý file: {file.filename}")

        # Đọc và xử lý nội dung file
        if file.filename.endswith('.pdf'):
            file_bytes = io.BytesIO(file.read())
            text = extract_text_from_pdf(file_bytes)
            file_content = file_bytes.getvalue()
        else:
            text = file.read().decode('utf-8')
            file_content = text.encode('utf-8')

        # Trích xuất thông tin cơ bản
        extracted_info = {
            'so_ct': extract_so_ct_by_lines(text[:]),
            'tax_number': extract_tax_number(text[:]),
            'date': extract_date_by_lines(text[:]),
            'customs_number': extract_customs_declaration(text[:]),
            'total_amount': extract_total_amount(text[:]),
            'line_items': extract_items(text[:])
        }

        # Chuyển đổi định dạng ngày từ DD/MM/YYYY thành DDMMYYYY
        ngay_formatted = extracted_info['date'].replace('/', '')

        # Tạo cấu trúc thư mục
        base_dir = "downloaded_pdfs"
        date_dir = os.path.join(base_dir, ngay_formatted)
        so_tk_dir = os.path.join(date_dir, extracted_info['customs_number'])

        # Query thông tin customs
        results = query_customs_info(extracted_info['customs_number'])

        # Cập nhật thông tin bổ sung
        if results and len(results) > 0:
            extracted_info.update({
                'jobID': results[0].TransID,
                'hawb': results[0].HWBNO,
                'nguoiKhai': results[0].nguoi_khai
            })
        else:
            extracted_info.update({
                'jobID': '',
                'hawb': '',
                'nguoiKhai': ''
            })

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
        SELECT td.TransID, td.HWBNO, cs.TKSo, ui.FullName as nguoi_khai
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

def main():

    # Giả lập việc trích xuất từ PDF
    pdf_path = "data/BLHPH005504.pdf"
    # pdf_path = "data/2.pdf"
    text = extract_text_from_pdf(pdf_path)

    if text:
        print("Văn bản trích xuất:")
        print(text)
        # number_regex = extract_so_chung_tu_regex(text)
        so_ct = extract_so_ct_by_lines(text)
        print("So CT:", so_ct)
        tax_number = extract_tax_number(text)
        print("Tax Code:", tax_number)
        customs_number = extract_customs_declaration(text)
        items = extract_items(text)
        print("Items:", items)
        if customs_number:
            print("Số tờ khai hải quan:", customs_number)
            # Thực hiện truy vấn SQL với số tờ khai
            query_customs_info(customs_number)
            print("Định dạng hợp lệ:", validate_customs_number(customs_number))


    else:
        print("Không thể trích xuất văn bản từ file.")

if __name__ == "__main__":
    main()
