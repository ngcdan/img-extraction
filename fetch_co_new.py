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

def access_page_with_retry(driver, url, max_retries=3, delay_between_retries=5):
    for retry in range(max_retries):
        try:
            driver.get(url)
            # Đợi để kiểm tra lỗi
            time.sleep(2)

            # Kiểm tra lỗi 404
            error_elements = driver.find_elements(By.CSS_SELECTOR, "h2")
            if any("404" in element.text for element in error_elements):
                print(f"Lần {retry + 1}: Phát hiện lỗi 404, đang thử lại...")
                if retry < max_retries - 1:
                    time.sleep(delay_between_retries)
                    refresh_session(driver)
                    continue
                return False
            return True
        except Exception as e:
            print(f"Lần {retry + 1}: Lỗi - {str(e)}")
            if retry < max_retries - 1:
                time.sleep(delay_between_retries)
                continue
    return False

# Trước khi truy cập URL, thêm đoạn code sau
def refresh_session(driver):
    try:
        driver.get("https://pus.customs.gov.vn/faces/Home")
        time.sleep(2)  # Đợi để session được thiết lập
        return True
    except:
        return False

def main():
    print('call main function!!!')


    customs_data = [
        {
            "custom_name": "03PL",  # HQHUNGYEN
            "custom_no": "107096649442",
            "date_register": "12/04/2025",
            "tax_code": "0901067514"
        },
        {
            "custom_name": "03PL",  # HQHUNGYEN
            "custom_no": "107096646160",
            "date_register": "12/04/2025",
            "tax_code": "0901067514"
        },
    ]

    driver = None

    try:
        # Khởi tạo Chrome
        driver = ChromeManager.initialize_chrome()
        if not driver:
            raise Exception("Không thể khởi tạo Chrome driver")

        # Clear tất cả cookies và sessions
        CookieManager.clear_all_cookies_and_sessions(driver)
        refresh_session(driver)

        # Truy cập trang với retry được cải thiện
        base_url = "https://pus.customs.gov.vn/faces/ContainerBarcode"
        if not access_page_with_retry(driver, base_url):
            raise Exception("Không thể truy cập trang sau nhiều lần thử")

        # Wait for elements to be present
        wait = WebDriverWait(driver, 30)
        short_wait = WebDriverWait(driver, 2)  # wait ngắn để check nhanh

        for customs_item in customs_data:
            print(f"\nXử lý dữ liệu hải quan: {customs_item['custom_no']}")
            print("Bắt đầu điền thông tin form...")

            # Fill tax code
            tax_code_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it1::content")))
            tax_code_input.clear()
            tax_code_input.send_keys(customs_item['tax_code'])
            print("✓ Đã điền mã số thuế:", customs_item['tax_code'])

            # Fill custom number
            custom_no_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it2::content")))
            custom_no_input.clear()
            custom_no_input.send_keys(customs_item['custom_no'])
            print("✓ Đã điền số tờ khai:", customs_item['custom_no'])

            # Fill custom name
            custom_name_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it3::content")))
            custom_name_input.clear()
            custom_name_input.send_keys(customs_item['custom_name'])
            print("✓ Đã điền tên hải quan:", customs_item['custom_name'])

            # Fill date register
            date_register_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it4::content")))
            date_register_input.clear()
            date_register_input.send_keys(customs_item['date_register'])
            print("✓ Đã điền ngày đăng ký:", customs_item['date_register'])


            # Đợi cho đến khi button xuất hiện và có thể click được
            wait = WebDriverWait(driver, 10)
            button = wait.until(EC.element_to_be_clickable((By.ID, "pt1:btngetdata")))

            link = driver.find_element(By.CSS_SELECTOR, "#pt1\\:btngetdata a")
            actions = ActionChains(driver)
            actions.move_to_element(link).pause(1).click().perform()

            print("Thực hiện request lấy thông tin...")
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
                    @page {
                        size: A4;
                        margin: 1cm;
                    }
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

            # Tạo tên file theo format: tax_code-customs_no.pdf
            output_filename = f"{customs_item['tax_code']}-{customs_item['custom_no']}.pdf"

            # Chuyển HTML thành PDF sử dụng WeasyPrint với các tùy chọn
            from weasyprint import HTML, CSS
            pdf = HTML(string=html_content).write_pdf(
                stylesheets=[CSS(string='''
                    @page {
                        size: A4;
                        margin: 1cm;
                    }
                    body {
                        font-family: "Times New Roman", serif;
                    }
                ''')]
            )

            # Lưu PDF với tên file mới
            with open(output_filename, 'wb') as f:
                f.write(pdf)
            print(f"✓ Đã tạo file PDF: {output_filename}")

            # Set lại style display:none sau khi download xong
            driver.execute_script("""
                var span = document.getElementById('pt1:png1');
                if (span) {
                    span.style.display = 'none';
                }
            """)

    except Exception as e:
        print(f"Lỗi khi xử lý: {str(e)}")

    # Giữ cho trình duyệt mở và chờ input từ người dùng
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




