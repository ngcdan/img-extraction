from chrome_manager import ChromeManager
from cookie_manager import CookieManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException
import base64
import requests
import pandas as pd
import json
from datetime import datetime
import os
import sys
import pdfkit
from custom_api_client import CustomApiClient, parse_response

def access_page_with_retry(driver, url, max_retries=3, delay_between_retries=5):
    for retry in range(max_retries):
        try:
            # Lưu handle của cửa sổ hiện tại
            original_window = driver.current_window_handle

            # Thử mở URL trong tab hiện tại trước
            driver.get(url)
            time.sleep(2)  # Đợi để kiểm tra lỗi

            # Kiểm tra lỗi 404
            error_elements = driver.find_elements(By.CSS_SELECTOR, "h2")
            if any("404" in element.text for element in error_elements):
                print(f"Lần {retry + 1}: Phát hiện lỗi 404, thử refresh session...")

                if retry < max_retries - 1:
                    # Truy cập trang chủ hải quan để refresh session
                    if refresh_session(driver):
                        print("Đã refresh session thành công, thử lại...")
                        # Mở URL trong tab mới
                        driver.execute_script(f"window.open('{url}', '_blank');")

                        # Chuyển đến tab mới
                        new_window = driver.window_handles[-1]
                        driver.switch_to.window(new_window)

                        time.sleep(delay_between_retries)
                        continue
                    else:
                        print("Không thể refresh session")
                return False
            return True

        except Exception as e:
            print(f"Lần {retry + 1}: Lỗi - {str(e)}")
            if retry < max_retries - 1:
                # Thử refresh session khi gặp lỗi
                print("Thử refresh session...")
                if refresh_session(driver):
                    print("Đã refresh session thành công, thử lại...")
                    time.sleep(delay_between_retries)
                    continue
                else:
                    print("Không thể refresh session")
                    time.sleep(delay_between_retries)
                    continue
    return False

def get_base_path():
    """Get base path for both dev and prod environments"""
    if getattr(sys, 'frozen', False):
        # If running as exe (production)
        return os.path.dirname(sys.executable)
    else:
        # If running in development
        return os.path.dirname(os.path.abspath(__file__))

def ensure_downloads_dir():
    """Ensure downloads directory exists and return its path"""
    try:
        base_path = get_base_path()
        downloads_dir = os.path.join(base_path, 'downloads')

        # Create downloads directory if it doesn't exist
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
            print(f"Đã tạo thư mục downloads tại: {downloads_dir}")

        return downloads_dir
    except Exception as e:
        print(f"Lỗi khi tạo thư mục downloads: {str(e)}")
        return None

def refresh_session(driver):
    try:
        driver.get("https://pus.customs.gov.vn/")
        time.sleep(2)  # Đợi để session được thiết lập
        return True
    except:
        return False

def format_excel_date(excel_date):
    try:
        # Convert Excel date number to datetime
        dt = datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(excel_date) - 2)
        # Format to dd/mm/yyyy
        return dt.strftime('%d/%m/%Y')
    except:
        return excel_date

def get_template_path():
    """Get the correct path for data_template.xlsx in both dev and prod environments"""
    try:
        # Check if running as exe (production)
        if getattr(sys, 'frozen', False):
            # If running as exe, use the directory containing the exe
            base_path = os.path.dirname(sys.executable)
        else:
            # If running in development, use the current directory
            base_path = os.path.dirname(os.path.abspath(__file__))

        template_path = os.path.join(base_path, 'data_template.xlsx')

        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Không tìm thấy file template tại: {template_path}")

        return template_path
    except Exception as e:
        print(f"Lỗi khi tìm đường dẫn template: {str(e)}")
        return None

def read_customs_data():
    try:
        template_path = get_template_path()
        if not template_path:
            return []

        # Đọc file Excel với dtype để specify kiểu dữ liệu
        df = pd.read_excel(template_path, dtype={
            'tax_code': str,
            'custom_number': str
        })

        # Chuyển DataFrame thành list of dictionaries
        customs_data = []
        for _, row in df.iterrows():
            customs_item = {
                "tax_code": str(row['tax_code']).replace('.0', ''),  # Loại bỏ .0 nếu có
                "custom_no": str(row['custom_number']).replace('.0', ''),  # Loại bỏ .0 nếu có
                "date_register": format_excel_date(row['date']),  # Format date
                "custom_name": str(row['custom_name'])
            }
            customs_data.append(customs_item)

        return customs_data
    except Exception as e:
        print(f"Lỗi khi đọc file Excel: {str(e)}")
        return []

def main():
    customs_data = read_customs_data()

    if not customs_data:
        print("Không thể đọc dữ liệu từ file Excel hoặc không có dữ liệu.")
        sys.exit(1)

    print(json.dumps(customs_data, indent=2, ensure_ascii=False))

    driver = None

    try:
        # Khởi tạo Chrome
        driver = ChromeManager.initialize_chrome()
        if not driver:
            raise Exception("Không thể khởi tạo Chrome driver")

        # Clear tất cả cookies và sessions
        CookieManager.clear_all_cookies_and_sessions(driver)

        # Refresh session trước khi bắt đầu
        if not refresh_session(driver):
            print("Cảnh báo: Không thể truy cập trang chủ hải quan")

        # Truy cập trang với retry được cải thiện
        base_url = "https://pus.customs.gov.vn/faces/ContainerBarcode"
        if not access_page_with_retry(driver, base_url):
            raise Exception("Không thể truy cập trang sau nhiều lần thử")

        # Wait for elements to be present
        wait = WebDriverWait(driver, 30)
        short_wait = WebDriverWait(driver, 2)  # wait ngắn để check nhanh

        # client = CustomApiClient()

        for customs_item in customs_data:
            print(f"\nXử lý dữ liệu tờ khai: {customs_item['custom_no']}")

            # result = client.fetch_customs_location_by_name(customs_item['custom_name'])
            # records = parse_response(result.data)

            # # Lấy code của record đầu tiên nếu có
            # custom_code = records[0]['code'] if records else ""

            # # Skip loop nếu custom_code trống
            # if not custom_code:
            #     print(f"Không tìm thấy mã hải quan cho {customs_item['custom_name']}, bỏ qua...")
            #     continue

            # Fill tax code
            tax_code_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it1::content")))
            tax_code_input.clear()
            tax_code_input.send_keys(customs_item['tax_code'])

            # Fill custom number
            custom_no_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it2::content")))
            custom_no_input.clear()
            custom_no_input.send_keys(customs_item['custom_no'])

            # Fill custom name
            custom_name_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it3::content")))
            custom_name_input.clear()
            custom_name_input.send_keys(customs_item['custom_name'])

            # Fill date register
            date_register_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it4::content")))
            date_register_input.clear()
            date_register_input.send_keys(customs_item['date_register'])

            # Đợi cho đến khi button xuất hiện và có thể click được
            wait = WebDriverWait(driver, 10)
            button = wait.until(EC.element_to_be_clickable((By.ID, "pt1:btngetdata")))

            max_attempts = 3  # Số lần thử tối đa
            for attempt in range(max_attempts):
                try:
                    link = driver.find_element(By.CSS_SELECTOR, "#pt1\\:btngetdata a")
                    actions = ActionChains(driver)
                    actions.move_to_element(link).pause(1).click().perform()

                    start_time = time.time()
                    found = False

                    while time.time() - start_time < 10:  # Kiểm tra trong 10 giây
                        try:
                            span_element = driver.find_element(By.ID, "pt1:png1")
                            style_attr = span_element.get_attribute("style")

                            # Kiểm tra nếu không có style attribute hoặc style không chứa display:none
                            if not style_attr or "display:none" not in style_attr:
                                found = True
                                time.sleep(2)
                                print("Đã phát hiện thông tin hải quan, bắt đầu tạo PDF...")
                                break
                        except:
                            pass
                        time.sleep(0.5)  # Đợi 0.5 giây trước khi kiểm tra lại

                    if not found:
                        if attempt < max_attempts - 1:
                            print(f"Lần {attempt + 1}: Không tìm thấy thông tin, thử lại...")
                            continue
                        raise Exception("Đã hết thời gian chờ (10s) mà không tìm thấy thông tin hải quan")

                    # Ẩn label "Trang để in" trước khi trích xuất HTML
                    driver.execute_script("""
                        var printLabel = document.getElementById('lbl_BanIn');
                        if (printLabel) {
                            printLabel.style.display = 'none';
                        }
                    """)

                    # Trích xuất nội dung HTML và xử lý ngoài trình duyệt
                    html_content = driver.execute_script("""
                        // Thêm CSS styles cho PDF
                        var style = document.createElement('style');
                        style.textContent = `
                            body {
                                font-family: 'Times New Roman', serif;
                                line-height: 1.3;
                            }
                            table {
                                width: 100%;
                                border-collapse: collapse;
                            }
                            td {
                                padding: 5px;
                            }
                        `;

                        // Thêm style vào content
                        var contentDiv = document.getElementById('content');
                        contentDiv.appendChild(style);

                        // Cập nhật ghi chú nếu cần
                        var copy_text = $("#copy_text").html();
                        if (copy_text) {
                            $('#ghichu').html(copy_text);
                            $("#ghichu").css({'margin-bottom':'10px'});
                        }

                        return contentDiv.outerHTML;
                    """)

                    # Tạo tên file và đường dẫn đầy đủ
                    downloads_dir = ensure_downloads_dir()
                    if not downloads_dir:
                        raise Exception("Không thể tạo thư mục downloads")

                    output_filename = f"{customs_item['tax_code']}-{customs_item['custom_no']}.pdf"
                    output_path = os.path.join(downloads_dir, output_filename)

                    # Cấu hình PDF options cho pdfkit
                    options = {
                        'page-size': 'A4',
                        'margin-top': '1cm',
                        'margin-right': '1cm',
                        'margin-bottom': '1cm',
                        'margin-left': '1cm',
                        'encoding': 'UTF-8',
                        'no-outline': None,
                        'quiet': ''
                    }

                    # Thêm CSS styles trực tiếp vào HTML
                    css = '''
                        <style>
                            @page {
                                size: A4;
                                margin: 1cm;
                            }
                            body {
                                font-family: "Times New Roman", serif;
                            }
                        </style>
                    '''
                    html_with_css = css + html_content

                    # Chuyển HTML thành PDF sử dụng pdfkit
                    try:
                        pdf = pdfkit.from_string(html_with_css, False, options=options)

                        # Kiểm tra kích thước PDF
                        if len(pdf) < 1000:  # Nhỏ hơn 1KB
                            if attempt < max_attempts - 1:
                                print(f"PDF size quá nhỏ ({len(pdf)} bytes), thử lại lần {attempt + 2}...")
                                time.sleep(2)
                                continue
                            else:
                                raise Exception(f"PDF size quá nhỏ ({len(pdf)} bytes) sau {max_attempts} lần thử")

                        # Nếu PDF hợp lệ, lưu file vào thư mục downloads
                        with open(output_path, 'wb') as f:
                            f.write(pdf)
                        print(f"✓ Đã tạo file PDF: {output_path}")
                        break  # Thoát khỏi vòng lặp nếu thành công

                    except Exception as pdf_error:
                        print(f"Lỗi khi tạo PDF: {str(pdf_error)}")
                        if attempt < max_attempts - 1:
                            continue
                        raise

                except Exception as e:
                    if attempt < max_attempts - 1:
                        print(f"Lỗi trong lần thử {attempt + 1}: {str(e)}, đang thử lại...")
                        time.sleep(2)
                    else:
                        raise Exception(f"Lỗi sau {max_attempts} lần thử: {str(e)}")

            # Set lại style display:none sau khi download xong
            driver.execute_script("""
                var span = document.getElementById('pt1:png1');
                if (span) {
                    span.style.display = 'none';
                }
            """)

    except Exception as e:
        print(f"Lỗi khi xử lý: {str(e)}")

    # Giữ cho trình duyệt mở
    try:
        while True:
            user_input = input("\nNhấn 'q' để thoát, Enter để tiếp tục: ")
            if user_input.lower() == 'q':
                if driver:
                    driver.quit()
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nĐã nhận tín hiệu thoát chương trình")
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()




