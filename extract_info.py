from pdfminer.high_level import extract_text
import re
import os
import pyodbc

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

    # Có thể thêm các quy tắc kiểm tra khác
    # Ví dụ: kiểm tra prefix, format date trong số tờ khai, etc.

    return True

def process_file_content(text):
    """Xử lý nội dung văn bản và trả về thông tin trích xuất"""
    tax_number = extract_tax_number(text)
    customs_number = extract_customs_declaration(text)
    date = extract_date_by_lines(text)

    return {
        'tax_number': tax_number,
        'customs_number': customs_number,
        'date': date
    }

# Hàm tạo kết nối SQL Server và thực hiện truy vấn
def query_customs_info(customs_number):
    """Tạo kết nối SQL Server và truy vấn thông tin dựa trên số tờ khai"""
    try:
        # Chuỗi kết nối SQL Server
        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=of1.beelogistics.com,34541;"
            "DATABASE=BEE_DB;"
            "UID=devhph;"
            "PWD=Hph@dev!@#123;"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
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
    pdf_path = "data/2.pdf"
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
        if customs_number:
            print("Số tờ khai hải quan:", customs_number)
            # Thực hiện truy vấn SQL với số tờ khai
            query_customs_info(customs_number)
            print("Định dạng hợp lệ:", validate_customs_number(customs_number))


    else:
        print("Không thể trích xuất văn bản từ file.")

if __name__ == "__main__":
    main()