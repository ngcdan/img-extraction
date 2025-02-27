from pdfminer.high_level import extract_text
import re
import os

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

def main():

    # Giả lập việc trích xuất từ PDF
    pdf_path = "data/2.pdf"
    text = extract_text_from_pdf(pdf_path)

    if text:
        print("Văn bản trích xuất:")
        print(text)

        # Tìm số 202509340850
        target_number = find_target_number(text)
        if target_number:
            print(f"Đã tìm thấy số: {target_number}")
        else:
            print("Không tìm thấy số 202509340850 trong văn bản.")
    else:
        print("Không thể trích xuất văn bản từ file.")

if __name__ == "__main__":
    main()