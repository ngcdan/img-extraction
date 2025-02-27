import os
import re

def normalize_labels():
    labels_file = "training_captchas/labels.txt"
    if not os.path.exists(labels_file):
        print("File labels.txt chưa tồn tại")
        return

    # Đọc file hiện tại
    with open(labels_file, 'r') as f:
        lines = f.readlines()

    normalized_lines = []
    errors = []

    # Xử lý từng dòng
    for i, line in enumerate(lines, 1):
        # Bỏ khoảng trắng đầu/cuối
        line = line.strip()
        if not line:  # Bỏ qua dòng trống
            continue

        # Tách bằng khoảng trắng và gộp nhiều khoảng trắng thành một
        parts = re.split(r'\s+', line)

        if len(parts) < 2:
            errors.append(f"Dòng {i}: Thiếu text captcha - {line}")
            continue

        image_file = parts[0]
        captcha_text = parts[1]

        # Kiểm tra file ảnh tồn tại
        if not os.path.exists(f"training_captchas/{image_file}"):
            errors.append(f"Dòng {i}: Không tìm thấy file ảnh - {image_file}")
            continue

        # Tạo dòng mới với tab
        normalized_lines.append(f"{image_file}\t{captcha_text}")

    # Lưu file mới
    backup_file = labels_file + ".backup"
    print(f"Tạo backup tại: {backup_file}")
    os.rename(labels_file, backup_file)

    with open(labels_file, 'w') as f:
        f.write('\n'.join(normalized_lines) + '\n')

    # In thông tin
    print(f"\nĐã xử lý {len(lines)} dòng")
    print(f"Số nhãn hợp lệ: {len(normalized_lines)}")

    if errors:
        print("\nCác lỗi tìm thấy:")
        for error in errors:
            print(error)
    else:
        print("\nKhông tìm thấy lỗi")

    print("\nVí dụ một số nhãn đã chuẩn hóa:")
    for line in normalized_lines[:5]:  # In 5 dòng đầu
        print(line)

if __name__ == "__main__":
    normalize_labels()