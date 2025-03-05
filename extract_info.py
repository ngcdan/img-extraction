import os
import io
from datetime import datetime
from pdfminer.high_level import extract_text
from google_drive_utils import upload_file_to_drive
from google_sheet_utils import append_to_google_sheet

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
        return int(price_str.replace('.', '').replace(',', ''))
    except:
        return 0

def split_sections(text):
    """Làm sạch và phân vùng văn bản thành header, table và footer"""
    try:
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

        sections = {
            'header': lines[:stt_index],
            'table': lines[stt_index:total_index],
            'footer': lines[total_index:]
        }
        return sections

    except Exception as e:
        print(f"Lỗi khi xử lý và phân vùng dữ liệu: {str(e)}")
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
            if mau_so_index + 1 < len(lines) and lines[mau_so_index + 1].startswith("Số:"):
                result['so_ct'] = lines[mau_so_index + 1].replace("Số:", "").strip()
            if mau_so_index + 2 < len(lines) and lines[mau_so_index + 2].startswith("Ngày:"):
                result['date'] = lines[mau_so_index + 2].replace("Ngày:", "").strip()

        for i, line in enumerate(lines):
            if line == "Kính gửi:":
                if i + 1 < len(lines):
                    result['partner_invoice_name'] = lines[i + 1].strip()
                break

        for i, line in enumerate(lines):
            if line == "Mã số thuế:":
                for j in range(i + 1, min(i + 4, len(lines))):
                    potential_tax = lines[j].strip()
                    if potential_tax.isdigit() and potential_tax != "Địa chỉ:":
                        result['tax_number'] = potential_tax
                        break
                break

        for i, line in enumerate(lines):
            if line == "Số tờ khai Hải quan:":
                if i + 2 < len(lines):
                    customs_number = lines[i + 2].strip()
                    if customs_number.isdigit():
                        result['customs_number'] = customs_number
                break

        if not all(result.values()):
            missing = [k for k, v in result.items() if v is None]
            print(f"Thiếu thông tin cho các trường: {', '.join(missing)}")

        return result

    except Exception as e:
        print(f"Lỗi khi trích xuất thông tin: {str(e)}")
        return None

def extract_items(table_data):
    """Trích xuất thông tin các items từ dữ liệu bảng"""
    try:
        items = []
        stt_index = table_data.index("STT")
        bieu_cuoc_index = table_data.index("Biểu cước")
        numbers_between = []
        for i in range(stt_index, bieu_cuoc_index):
            if table_data[i].isdigit():
                numbers_between.append(int(table_data[i]))
        num_rows = max(numbers_between) if numbers_between else 0

        if num_rows == 0:
            return []

        start_data_index = table_data.index("(7) = (5)*(6)") + 1
        current_index = len(table_data) - 1
        amounts = []
        quantities = []
        unit_prices = []
        units = []
        container_numbers = []
        labels = []

        for _ in range(num_rows):
            while current_index >= 0 and not table_data[current_index].replace('.', '').isdigit():
                current_index -= 1
            if current_index >= 0:
                amounts.insert(0, table_data[current_index])
                current_index -= 1

        for _ in range(num_rows):
            while current_index >= 0 and not table_data[current_index].isdigit():
                current_index -= 1
            if current_index >= 0:
                quantities.insert(0, table_data[current_index])
                current_index -= 1

        for _ in range(num_rows):
            while current_index >= 0 and not table_data[current_index].replace('.', '').isdigit():
                current_index -= 1
            if current_index >= 0:
                unit_prices.insert(0, table_data[current_index])
                current_index -= 1

        for _ in range(num_rows):
            while current_index >= 0 and table_data[current_index] != "Đồng/Container":
                current_index -= 1
            if current_index >= 0:
                units.insert(0, table_data[current_index])
                current_index -= 1

        for _ in range(num_rows):
            while current_index >= 0 and table_data[current_index] in ['Đồng/Container']:
                current_index -= 1
            if current_index >= 0:
                container_numbers.insert(0, table_data[current_index])
                current_index -= 1

        for _ in range(num_rows):
            label = []
            while current_index >= start_data_index:
                if table_data[current_index] not in ['Đồng/Container']:
                    label.insert(0, table_data[current_index])
                current_index -= 1
                if current_index < start_data_index:
                    break
            labels.insert(0, ' '.join(label) if label else '')

        for i in range(num_rows):
            if (i < len(container_numbers) and i < len(unit_prices) and
                i < len(quantities) and i < len(amounts)):
                item = {
                    'container_no': container_numbers[i],
                    'label': labels[i] if i < len(labels) else '',
                    'unit': units[i] if i < len(units) else 'Đồng/Container',
                    'unit_price': int(unit_prices[i].replace('.', '')),
                    'quantity': int(quantities[i]),
                    'amount': int(amounts[i].replace('.', ''))
                }
                items.append(item)

        return items

    except Exception as e:
        print(f"Lỗi khi trích xuất items: {str(e)}")
        print(f"Chi tiết bảng dữ liệu: {table_data}")
        return []

def process_pdf(pdf_path):
    """Hàm chính để xử lý file PDF"""
    try:
        sections = extract_text_from_pdf(pdf_path)
        if not sections:
            return None

        result = extract_header_info(sections['header'])
        if not result:
            return None

        items = extract_items(sections['table'])
        result['line_items'] = items

        # Xóa phần query SQL Server
        result.update({
            'jobId': '',
            'hawb': '',
            'nguoi_khai': ''
        })

        return result

    except Exception as e:
        print(f"Lỗi khi xử lý PDF: {str(e)}")
        return None

def main():
    pdf_path = "data/BLHPH005202.pdf"
    result = process_pdf(pdf_path)
    if result:
        print("Kết quả xử lý:", result)
    else:
        print("Không thể xử lý file PDF")

if __name__ == "__main__":
    main()
