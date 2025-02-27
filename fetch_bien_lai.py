# Yêu cầu cài đặt:
# 1. Python 3.10+: python.org
# 2. Thư viện: pip install selenium requests Pillow pytesseract opencv-python
# 3. Chrome Driver: Tải từ chromedriver.chromium.org, thêm vào PATH
# 4. Tesseract OCR: Cài từ github.com/UB-Mannheim/tesseract/wiki (Windows)
#    hoặc brew install tesseract (macOS) hoặc sudo apt install tesseract-ocr (Linux)

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import requests
from PIL import Image
import pytesseract
import cv2
import os
from selenium.webdriver.chrome.options import Options

# Đường dẫn lưu ảnh captcha
CAPTCHA_DIR = "captchas"
if not os.path.exists(CAPTCHA_DIR):
    os.makedirs(CAPTCHA_DIR)

# Thiết lập Chrome options
chrome_options = Options()
# chrome_options.add_argument('--headless')  # Bỏ comment nếu muốn chạy ẩn
driver = webdriver.Chrome(options=chrome_options)

# Hàm xử lý ảnh captcha để tăng độ chính xác
def process_captcha_image(image_path):
    if not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
        raise ValueError(f"File ảnh captcha không tồn tại hoặc rỗng: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Không thể đọc file ảnh captcha: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    processed = cv2.convertScaleAbs(blurred, alpha=1.5, beta=0)
    processed_path = image_path.replace(".png", "_processed.png")
    cv2.imwrite(processed_path, processed)
    return processed_path

# Hàm lưu ảnh captcha với timestamp
def save_captcha_image(image_data, attempt, suffix="downloaded"):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    captcha_filename = os.path.join(CAPTCHA_DIR, f"captcha_{timestamp}_attempt_{attempt}_{suffix}.png")
    with open(captcha_filename, "wb") as f:
        f.write(image_data)
    return captcha_filename

# Hàm chụp ảnh captcha từ Selenium
def capture_captcha_image(element, attempt):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    captcha_filename = os.path.join(CAPTCHA_DIR, f"captcha_{timestamp}_attempt_{attempt}_captured.png")
    element.screenshot(captcha_filename)
    return captcha_filename

# Hàm nhận diện captcha (ưu tiên ảnh chụp)
def solve_captcha(captured_path, downloaded_path=None):
    # Ưu tiên xử lý ảnh chụp
    try:
        processed_path = process_captcha_image(captured_path)
        image = Image.open(processed_path)
        text = pytesseract.image_to_string(image, lang='eng')
        print(f"Captcha text detected from captured {captured_path}: {text.strip()}")
        if text.strip():
            return text.strip()
        else:
            print(f"Không nhận diện được từ ảnh chụp {captured_path}, thử ảnh tải về...")
    except Exception as e:
        print(f"Lỗi khi giải captcha từ ảnh chụp {captured_path}: {e}")

    # Nếu ảnh chụp thất bại, dùng ảnh tải về
    if downloaded_path:
        try:
            processed_path = process_captcha_image(downloaded_path)
            image = Image.open(processed_path)
            text = pytesseract.image_to_string(image, lang='eng')
            print(f"Captcha text detected from downloaded {downloaded_path}: {text.strip()}")
            return text.strip()
        except Exception as e:
            print(f"Lỗi khi giải captcha từ ảnh tải về {downloaded_path}: {e}")
    return ""

# Mở trang đăng nhập
driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")
time.sleep(5)  # Chờ trang tải để đảm bảo captcha xuất hiện

# Điền username và password
username_input = driver.find_element(By.ID, "form-username")
username_input.send_keys("0104232742")
password_input = driver.find_element(By.ID, "form-password")
password_input.send_keys("0104232742")

# Header giả lập trình duyệt
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
}

# Số lần thử tối đa
max_attempts = 5
attempt = 0
login_success = False

while attempt < max_attempts and not login_success:
    print(f"Thử lần {attempt + 1}/{max_attempts}")

    # Lấy phần tử ảnh captcha
    captcha_image_element = driver.find_element(By.ID, "CaptchaImage")
    captcha_image_src = captcha_image_element.get_attribute("src")
    full_captcha_url = "http://thuphi.haiphong.gov.vn:8222" + captcha_image_src

    # Tải ảnh từ URL (fallback)
    downloaded_captcha = None
    try:
        response = requests.get(full_captcha_url, headers=headers, timeout=10)
        if response.status_code == 200 and response.content:
            downloaded_captcha = save_captcha_image(response.content, attempt + 1, "downloaded")
            print(f"Tải captcha thành công từ URL: {full_captcha_url}")
        else:
            print(f"Tải captcha thất bại (Status: {response.status_code})")
    except Exception as e:
        print(f"Lỗi tải captcha bằng requests: {e}")

    # Chụp ảnh captcha (ưu tiên)
    captured_captcha = capture_captcha_image(captcha_image_element, attempt + 1)
    print(f"Đã chụp ảnh captcha: {captured_captcha}")

    # Nhận diện captcha (ưu tiên ảnh chụp)
    captcha_text = solve_captcha(captured_captcha, downloaded_captcha)
    if not captcha_text:
        print("Không nhận diện được captcha từ cả hai nguồn, thử lại...")
        attempt += 1
        if attempt < max_attempts:
            driver.refresh()
            time.sleep(5)
        continue

    # Điền captcha vào input
    captcha_input = driver.find_element(By.ID, "CaptchaInputText")
    captcha_input.clear()
    captcha_input.send_keys(captcha_text)
    time.sleep(2)  # Đợi 2 giây để đảm bảo captcha được xử lý

    # Nhấn nút đăng nhập
    try:
        wait = WebDriverWait(driver, 15)
        submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(text(), 'Đăng nhập')]")))
        print("Nút 'Đăng nhập' đã sẵn sàng, kiểm tra trạng thái...")

        if not submit_button.is_displayed():
            print("Nút 'Đăng nhập' không hiển thị!")
        if not submit_button.is_enabled():
            print("Nút 'Đăng nhập' bị vô hiệu hóa!")

        actions = ActionChains(driver)
        actions.move_to_element(submit_button).click().perform()
        print("Đã nhấp nút 'Đăng nhập' bằng ActionChains")
    except Exception as e:
        print(f"Lỗi khi nhấp nút 'Đăng nhập': {e}")
        attempt += 1
        if attempt < max_attempts:
            driver.refresh()
            time.sleep(5)
        continue

    # Chờ trang tải
    time.sleep(5)

    # Kiểm tra đăng nhập thành công
    if driver.current_url != "http://thuphi.haiphong.gov.vn:8222/dang-nhap":
        print("Đăng nhập thành công")
        login_success = True
        driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")
    else:
        print("Đăng nhập thất bại, thử lại...")
        attempt += 1
        if attempt < max_attempts:
            driver.refresh()
            time.sleep(5)

if not login_success:
    print("Đã đạt số lần thử tối đa, đăng nhập thất bại")

# Đóng trình duyệt
# driver.quit()