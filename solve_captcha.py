from paddleocr import PaddleOCR

def solve_captcha(image_path):
    # Load mô hình đã train
    ocr = PaddleOCR(use_angle_cls=True, lang='en',
                    model_path='custom_captcha_model')

    try:
        # Nhận dạng text
        result = ocr.ocr(image_path, cls=True)

        if result:
            # Lấy text từ kết quả
            text = ''.join([line[1][0] for line in result[0]])
            return text.strip()
    except Exception as e:
        print(f"Lỗi khi nhận dạng captcha: {e}")

    return ""