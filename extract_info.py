from pdfminer.high_level import extract_text
import re
import os
import pyodbc
from openpyxl import load_workbook
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def append_to_excel(extracted_info):
    """Thêm thông tin vào file Excel template"""
    try:
        # Mở file Excel
        excel_path = "./downloaded_pdfs/template_updated.xlsx"
        wb = load_workbook(excel_path)
        ws = wb.active

        # Đếm số dòng hiện tại
        current_row = ws.max_row

        # Lấy danh sách items
        print("Extracted info:", json.dumps(extracted_info, indent=2, ensure_ascii=False))
        line_items = extracted_info.get('line_items', {}).get('items', [])
        if not line_items:
            print("Không có thông tin container để thêm vào Excel")
            return False

        # Thêm từng dòng cho mỗi item
        for line in line_items:
            # Tăng STT
            current_row += 1

            # Chuẩn bị dữ liệu cố định
            fixed_data = {
                'service_code': 'CL014920',
                'vendor': 'VETC',
                'charge_code': 'B_EWF',
                'description': 'EXPRESS WAY FEES',
                'unit': 'shipment'
            }

            # Tạo row data
            row_data = [
                current_row - 1,  # STT
                extracted_info.get('so_ct', ''),  # Số chứng từ
                fixed_data['service_code'],  # CL014920
                fixed_data['vendor'],  # VETC
                extracted_info.get('jobID', ''),  # JobID
                extracted_info.get('hawb', ''),  # HAWB
                fixed_data['charge_code'],  # B_EWF
                fixed_data['description'],  # EXPRESS WAY FEES
                line['quantity'],  # Số lượng
                fixed_data['unit'],  # shipment
                line['unit_price'],  # Đơn giá
                '',  # Cột 12 để trống
                line['total'],  # Thành tiền
                '', '', '', '', '', '', '',  # Cột 14-20 để trống
                line['container_no'],  # Số container
                line['label']  # Loại container
            ]

            # Thêm dữ liệu vào worksheet
            for col, value in enumerate(row_data, 1):
                ws.cell(row=current_row, column=col, value=value)

        # Lưu file
        wb.save(excel_path)
        print(f"Đã thêm {len(line_items)} dòng vào file Excel")
        return True

    except Exception as e:
        print(f"Lỗi khi thêm dữ liệu vào Excel: {str(e)}")
        return False

def extract_text_from_pdf(pdf_path):
    """Trích xuất văn bản từ file PDF."""
    try:
        text = extract_text(pdf_path)
        return text
    except Exception as e:
        print(f"Lỗi khi trích xuất văn bản: {e}")
        return None

def find_target_number(text, target="202509340850"):
    """Tìm số mục tiêu trong văn bản."""
    match = re.search(target, text)
    if match:
        return match.group()
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

def process_file_content(text):
    """Xử lý nội dung văn bản và trả về thông tin trích xuất"""
    text_copy = text[:]
    so_ct = extract_so_ct_by_lines(text_copy)
    text_copy = text[:]
    tax_number = extract_tax_number(text_copy)
    text_copy = text[:]
    customs_number = extract_customs_declaration(text_copy)
    text_copy = text[:]
    date = extract_date_by_lines(text_copy)
    text_copy = text[:]
    line_items = extract_items(text_copy)
    print("Extracted items:", json.dumps(line_items, indent=2, ensure_ascii=False))

    return {
        'so_ct': so_ct,
        'tax_number': tax_number,
        'customs_number': customs_number,
        'date': date,
        'line_items': line_items
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
        print(f"Lỗi khi kết nối hoặc truy vấn cơ sở dữ liệu: {e}")
        return None

def main():

    # Giả lập việc trích xuất từ PDF
    pdf_path = "data/BLHPH005202.pdf"
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
