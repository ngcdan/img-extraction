import layoutparser as lp
import cv2
import numpy as np
from pathlib import Path
from pdf2image import convert_from_path
import re
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Hàm xử lý ảnh riêng
def preprocess_image(image):
    # Chuyển sang ảnh xám
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Tăng độ tương phản
    gray = cv2.convertScaleAbs(gray, alpha=2.0, beta=20)

    # Làm mịn ảnh để giảm nhiễu
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    # Nhị phân hóa với Otsu để làm nổi bật văn bản
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Làm sắc nét ảnh
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(binary, -1, kernel)

    return sharpened

# Đường dẫn file PDF trong thư mục 'data'
pdf_path = Path("data/3.pdf")

# Tạo thư mục 'data/img' nếu chưa tồn tại
img_dir = Path("data/img")
img_dir.mkdir(parents=True, exist_ok=True)

# Chuyển PDF thành danh sách hình ảnh và lưu vào 'data/img'
raw_images = convert_from_path(pdf_path, dpi=400)  # Tăng DPI để cải thiện OCR
optimized_images = []
for i, image in enumerate(raw_images):
    # Chuyển PIL sang numpy để xử lý
    image_np = np.array(image)
    # Tối ưu ảnh
    optimized_image = preprocess_image(image_np)

    # Lưu ảnh đã tối ưu
    image_path = img_dir / f"page_{i + 1}_optimized.png"
    cv2.imwrite(str(image_path), optimized_image)
    print(f"Đã lưu ảnh tối ưu: {image_path}")

    # Thêm vào danh sách để xử lý tiếp
    optimized_images.append(optimized_image)

# Tải mô hình Detectron2
model = lp.Detectron2LayoutModel(
    "lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
    # "lp://TableBank/faster_rcnn_R_50_FPN_3x/config", tốt cho việc đọc thông tin ở bảng.
    extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.3],
    label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
)

# Tải công cụ OCR (Tesseract)
# ocr_agent = lp.TesseractAgent(languages="vie")
# ocr_agent = lp.TesseractAgent(languages="vie", config="--psm 6")  # PSM 6 giả định văn bản là khối đồng nhất
ocr_agent = lp.TesseractAgent(languages="vie", config="--psm 3")

# Biến lưu trữ kết quả
extracted_data = {"Ma_lo": "", "Ngay": "", "Table": []}

# Xử lý từng trang
for i, image in enumerate(raw_images):
    image = np.array(image)
    layout = model.detect(image)

    # In các loại khối được nhận diện
    print(f"Trang {i + 1}: Các loại khối được phát hiện: {[block.type for block in layout]}")

    # Trích xuất văn bản từ các khối
    full_text = ""
    table_text = ""
    for block in layout:
        x1, y1, x2, y2 = block.coordinates
        region = image[int(y1):int(y2), int(x1):int(x2)]

        # Áp dụng mô hình xử lý ảnh
        processed_region = preprocess_image(region)

        text = ocr_agent.detect(region).strip()
        print(f"Khối {block.type}: {text}")  # In văn bản OCR

        if block.type in ["Text", "Title"]:
            full_text += text + "\n"
        elif block.type == "Table":
            table_text = text

    # Trích xuất mã lô và ngày với regex linh hoạt hơn
    ma_lo_match = re.search(r"(Mãlô|Mã lô|Mã lo|Mã số):?\s*(\d+)", full_text, re.IGNORECASE)
    if ma_lo_match:
        extracted_data["Ma_lo"] = ma_lo_match.group(2)

    ngay_match = re.search(r"Ngày\(Date\): (\d{2}/\d{2}/\d{4} \d{2}:\d{2})", full_text)
    if ngay_match:
        extracted_data["Ngay"] = ngay_match.group(1)

# Trích xuất bảng
    if table_text:
        print(f"\n\nTable text:\n{table_text}")
        table_lines = table_text.split("\n")

        # Tích hợp dữ liệu bảng
        table_data = {
            "So_DK": "", "So_Container": "", "Phuong_an": "", "So_luong": "",
            "Don_gia": "", "Thue": "", "Giam_gia": "", "Thanh_tien": ""
        }

        for j, line in enumerate(table_lines):
            line = line.strip()
            if re.match(r"^[A-Z0-9]{5,}", line):  # Số ĐK (ví dụ: L9Y2D2, L9X5D3)
                table_data["So_DK"] = line
            elif re.match(r"^[A-Z]{4}.*\d{5,}", line):  # Số Container (ví dụ: TXGU7846426, TXGUƯ781463126)
                table_data["So_Container"] = re.sub(r"[^A-Z0-9]", "", line)[:11]  # Lấy 11 ký tự sạch
            elif "Hạ bãi" in line or "40GP" in line or "Hàng" in line:  # Phương án
                table_data["Phuong_an"] += line + " "
            elif re.match(r"^\d+$", line) and len(line) <= 2:  # Số lượng hoặc Thuế
                if not table_data["So_luong"]:
                    table_data["So_luong"] = line
                elif 0 <= int(line) <= 100:
                    table_data["Thue"] = line
            elif re.match(r"^[I1]\.?\d{3}\.?\d{3}", line):  # Đơn giá/Thành tiền (bắt đầu bằng 1 hoặc I)
                clean_price = re.sub(r"[^0-9]", "", line)
                if not table_data["Don_gia"]:
                    table_data["Don_gia"] = clean_price
                else:
                    table_data["Thanh_tien"] = clean_price
            elif line == "0":  # Giảm giá
                table_data["Giam_gia"] = line

        # Kiểm tra và thêm bảng
        if table_data["So_DK"] and table_data["So_Container"]:
            table_data["Phuong_an"] = table_data["Phuong_an"].strip()
            extracted_data["Table"].append(table_data)

# In kết quả
print("\n\nThông tin trích xuất:")
print(f"Mã lô: {extracted_data['Ma_lo']}")
print(f"Ngày: {extracted_data['Ngay']}")
print("\nBảng thông tin:")
print("Số ĐK - Số Container - Phương án - Số lượng - Đơn giá - Thuế (%) - Giảm giá - Thành tiền")
for row in extracted_data["Table"]:
    print(f"{row['So_DK']} - {row['So_Container']} - {row['Phuong_an']} - {row['So_luong']} - {row['Don_gia']} - {row['Thue']} - {row['Giam_gia']} - {row['Thanh_tien']}")