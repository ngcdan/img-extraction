from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time
import requests
from PIL import Image
import pytesseract

# Khởi tạo driver Chrome
driver = webdriver.Chrome()

# Mở trang đăng nhập
driver.get("http://thuphi.haiphong.gov.vn:8222/dang-nhap")

# Điền username và password
username_input = driver.find_element(By.ID, "form-username")
username_input.send_keys("0104232742")
password_input = driver.find_element(By.ID, "form-password")
password_input.send_keys("0104232742")

# Lấy đường dẫn hình ảnh captcha
captcha_image_element = driver.find_element(By.ID, "CaptchaImage")
captcha_image_src = captcha_image_element.get_attribute("src")

# Tải hình ảnh captcha
response = requests.get(captcha_image_src)
with open("captcha.png", "wb") as f:
    f.write(response.content)

# Nhận diện văn bản từ captcha bằng Tesseract
image = Image.open("captcha.png")
text = pytesseract.image_to_string(image, lang='vie')  # Có thể điều chỉnh ngôn ngữ

# Điền captcha vào input
captcha_input = driver.find_element(By.ID, "CaptchaInputText")
captcha_input.send_keys(text)

# Nhấn nút đăng nhập
wait = WebDriverWait(driver, 10)
submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
submit_button.click()

# Chờ trang tải
time.sleep(5)

# Kiểm tra đăng nhập thành công
if driver.current_url != "http://thuphi.haiphong.gov.vn:8222/dang-nhap":
    print("Đăng nhập thành công")
    # Điều hướng đến trang mong muốn
    driver.get("http://thuphi.haiphong.gov.vn:8222/danh-sach-tra-cuu-bien-lai-dien-tu")
else:
    print("Đăng nhập thất bại")

# Đóng trình duyệt
driver.quit()