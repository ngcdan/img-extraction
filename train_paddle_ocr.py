import os
import cv2
import numpy as np
from paddleocr import PaddleOCR
from sklearn.model_selection import train_test_split

def prepare_data():
    data_dir = "training_captchas"
    images = []
    labels = []

    # Đọc file labels.txt
    with open(os.path.join(data_dir, "labels.txt"), "r") as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 2:
                img_name, label = parts
                img_path = os.path.join(data_dir, img_name)
                if os.path.exists(img_path):
                    images.append(img_path)
                    labels.append(label)

    print(f"Đã tải {len(images)} ảnh và nhãn")
    return images, labels

def train_model():
    print("Khởi tạo PaddleOCR...")
    ocr = PaddleOCR(
        use_angle_cls=True,
        lang='en',
        use_gpu=False,
        show_log=True
    )

    print("Chuẩn bị dữ liệu...")
    images, labels = prepare_data()

    if not images:
        print("Không tìm thấy dữ liệu training!")
        return

    # Chia dữ liệu training/test
    train_images, test_images, train_labels, test_labels = train_test_split(
        images, labels, test_size=0.2, random_state=42
    )

    print(f"Số lượng ảnh training: {len(train_images)}")
    print(f"Số lượng ảnh test: {len(test_images)}")

    try:
        print("Bắt đầu training...")
        # Cấu hình training
        config = {
            'learning_rate': 0.001,
            'batch_size': 32,
            'epoch_num': 100,
            'save_model_dir': './output/captcha_model',
            'train_images': train_images,
            'train_labels': train_labels,
            'eval_images': test_images,
            'eval_labels': test_labels
        }

        # Training
        ocr.train(config)

        print("Training hoàn tất!")

    except Exception as e:
        print(f"Lỗi trong quá trình training: {e}")

def test_model():
    print("Kiểm tra model...")
    ocr = PaddleOCR(
        use_angle_cls=True,
        lang='en',
        use_gpu=False,
        model_dir='./output/captcha_model'
    )

    # Test với một số ảnh
    test_dir = "training_captchas"
    test_images = [f for f in os.listdir(test_dir) if f.endswith('.png')][:5]

    for img_name in test_images:
        img_path = os.path.join(test_dir, img_name)
        result = ocr.ocr(img_path)
        print(f"Ảnh {img_name}:")
        print(f"Kết quả: {result}")
        print("---")

if __name__ == "__main__":
    print("=== Bắt đầu quá trình training ===")

    # Kiểm tra thư mục output
    if not os.path.exists('./output'):
        os.makedirs('./output')
        print("Đã tạo thư mục output")

    # Training
    train_model()

    # Test model
    test_model()