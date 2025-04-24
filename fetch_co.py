from chrome_manager import ChromeManager
from cookie_manager import CookieManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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
from pdf_generator import PDFGenerator
from custom_api_client import CustomApiClient, parse_response

pdf_generator = PDFGenerator()

def access_page_with_retry(driver, url, max_retries=3, delay_between_retries=5):
    for retry in range(max_retries):
        try:
            print(f"Lần {retry + 1}: Đang truy cập {url}")
            driver.get(url)

            # Kiểm tra URL hiện tại
            current_url = driver.current_url
            print(f"URL hiện tại: {current_url}")

            # Kiểm tra lỗi 404
            try:
                error_404 = driver.find_element(
                    By.XPATH,
                    '//h2[normalize-space()="404 - File or directory not found."]'
                )
                if error_404.is_displayed():
                    print("Phát hiện lỗi 404, đợi 5s và thử lại...")
                    time.sleep(5)
                    continue
            except:
                pass  # Không tìm thấy lỗi 404, tiếp tục kiểm tra

            # Kiểm tra các trường hợp cần reload
            if (current_url == "about:blank" or
                "ContainerBarcode;jsessionid=" in current_url):
                print("Phát hiện URL không hợp lệ, đang tải lại trang...")
                time.sleep(2)  # Chờ 2s trước khi reload
                driver.get(url)
                print(f"Đã tải lại trang. URL mới: {driver.current_url}")

            # Kiểm tra lại URL sau khi reload
            if driver.current_url == "about:blank":
                raise Exception("Trang vẫn trống sau khi reload")

            print(f"Lần {retry + 1}: Truy cập thành công")
            return True

        except Exception as e:
            print(f"Lần {retry + 1}: Lỗi khi truy cập - {str(e)}")
            if retry < max_retries - 1:
                print(f"Chờ {delay_between_retries}s trước khi thử lại...")
                time.sleep(delay_between_retries)
                continue
            else:
                print("Đã hết số lần thử")
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
    """Refresh session by accessing backup URL with minimal waiting"""
    try:
        print("Truy cập URL backup để lấy session mới...")
        driver.get("https://pus1.customs.gov.vn/BarcodeContainer/BarcodeContainer.aspx")

        # Chỉ đợi cho đến khi document.readyState là 'complete'
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        print("Đã lấy session mới thành công")
        return True

    except TimeoutException as te:
        print(f"Timeout khi chờ trang load: {str(te)}")
        return False
    except Exception as e:
        print(f"Lỗi khi refresh session: {str(e)}")
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

def wait_for_button_clickable(driver, max_retries=3, delay=2):
    """
    Đợi cho đến khi button có thể click được
    Returns: WebElement nếu thành công, None nếu thất bại
    """
    for attempt in range(max_retries):
        try:
            # Đợi cho đến khi element xuất hiện và có thể click
            wait = WebDriverWait(driver, 10)
            button = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'div[id="pt1:btngetdata"] span[class="xfx"]')
                )
            )

            # Kiểm tra thêm các thuộc tính của button
            if button.is_displayed() and button.is_enabled():
                print("Đã tìm thấy button và có thể click")
                return button

        except Exception as e:
            print(f"Lần {attempt + 1}: Không thể tìm thấy button - {str(e)}")

            if attempt < max_retries - 1:
                print(f"Chờ {delay}s và thử lại...")
                # Thử scroll đến vị trí button
                try:
                    driver.execute_script(
                        'document.querySelector(\'div[id="pt1:btngetdata"] span[class="xfx"]\').scrollIntoView(true);'
                    )
                except:
                    pass

                time.sleep(delay)
            else:
                print("Đã hết số lần thử")
                return None

    return None

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

        # Truy cập trang với retry được cải thiện
        base_url = "https://pus.customs.gov.vn/faces/ContainerBarcode"
        if not access_page_with_retry(driver, base_url):
            raise Exception("Không thể truy cập trang sau nhiều lần thử")

        button = wait_for_button_clickable(driver)
        if button is None:
            raise Exception("Không thể tìm thấy hoặc click vào button sau nhiều lần thử")

        wait = WebDriverWait(driver, 10)

        client = CustomApiClient()

        for customs_item in customs_data:
            print(f"\nXử lý dữ liệu tờ khai: {customs_item['custom_no']}")

            result = client.fetch_customs_location_by_name(customs_item['custom_name'])
            records = parse_response(result.data)
            # Lấy code của record đầu tiên nếu có
            custom_code = records[0]['code'] if records else ""

            # Skip loop nếu custom_code trống
            if not custom_code:
                print(f"Không tìm thấy mã hải quan cho {customs_item['custom_name']}, bỏ qua...")
                continue

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
            custom_name_input.send_keys(custom_code)

            # Fill date register
            date_register_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it4::content")))
            date_register_input.clear()
            date_register_input.send_keys(customs_item['date_register'])

            max_attempts = 3  # Số lần thử tối đa
            for attempt in range(max_attempts):
                try:
                    # Tạo một list để lưu requests
                    requests = []

                    # Thiết lập listener cho network requests bằng CDP
                    def process_browser_logs_for_network_events(logs):
                        for entry in logs:
                            log = json.loads(entry["message"])["message"]
                            if ("Network.responseReceived" in log["method"]
                                and "ContainerBarcode?Adf-Window-Id=" in log.get("params", {}).get("response", {}).get("url", "")):
                                return True
                        return False

                    # Enable network logging
                    driver.execute_cdp_cmd('Network.enable', {})

                    # Click button để gửi request
                    link = driver.find_element(By.CSS_SELECTOR, "#pt1\\:btngetdata a")
                    actions = ActionChains(driver)
                    actions.move_to_element(link).pause(1).click().perform()

                    # Đợi và kiểm tra response
                    start_time = time.time()
                    request_completed = False

                    while time.time() - start_time < 10:  # Kiểm tra trong 10 giây
                        # Lấy logs từ browser
                        logs = driver.get_log("performance")
                        if process_browser_logs_for_network_events(logs):
                            request_completed = True
                            time.sleep(2)  # Đợi thêm 2s để đảm bảo dữ liệu đã được render
                            print("Đã nhận được response thành công, bắt đầu tạo PDF...")
                            break
                        time.sleep(0.5)

                    # Disable network logging
                    driver.execute_cdp_cmd('Network.disable', {})

                    if not request_completed:
                        if attempt < max_attempts - 1:
                            print(f"Lần {attempt + 1}: Không nhận được response thành công, thử lại...")
                            continue
                        raise Exception("Đã hết thời gian chờ (10s) mà không nhận được response thành công")

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

                    # Tạo PDF từ HTML content
                    success, result = pdf_generator.html_to_pdf( html_with_css, output_path)

                    if not success:
                        if attempt < max_attempts - 1:
                            print(f"Lỗi khi tạo PDF: {result}, thử lại lần {attempt + 2}...")
                            time.sleep(2)
                            continue
                        else:
                            raise Exception(f"Không thể tạo PDF sau {max_attempts} lần thử: {result}")

                    # Kiểm tra kích thước file PDF
                    pdf_size = os.path.getsize(output_path)
                    if pdf_size < 1000:  # Nhỏ hơn 1KB
                        if attempt < max_attempts - 1:
                            print(f"PDF size quá nhỏ ({pdf_size} bytes), thử lại lần {attempt + 2}...")
                            os.remove(output_path)  # Xóa file PDF không hợp lệ
                            time.sleep(2)
                            continue
                        else:
                            raise Exception(f"PDF size quá nhỏ ({pdf_size} bytes) sau {max_attempts} lần thử")

                    print(f"✓ Đã tạo file PDF: {output_path}")
                    break  # Thoát khỏi vòng lặp nếu thành công

                except Exception as e:
                    print(f"Lần {attempt + 1}: Chi tiết lỗi - {str(e)}")
                    if attempt < max_attempts - 1:
                        print(f"Đang thử lại sau 2 giây...")
                        time.sleep(2)
                    else:
                        raise Exception(f"Lỗi sau {max_attempts} lần thử: {str(e)}")

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
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()




