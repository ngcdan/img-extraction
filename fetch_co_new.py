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
        driver.get("https://pus.customs.gov.vn")
        time.sleep(2)  # Đợi để session được thiết lập
        return True
    except:
        return False

def main():
    print('call main function!!!')
    custom_name = "03PL" # HQHUNGYEN
    custom_no = "107096649442"
    date_register = "12/04/2025"
    tax_code = "0901067514"


    driver = None

    try:
        # Khởi tạo Chrome
        driver = ChromeManager.initialize_chrome()
        if not driver:
            raise Exception("Không thể khởi tạo Chrome driver")



        # Clear tất cả cookies và sessions
        CookieManager.clear_all_cookies_and_sessions(driver)
        refresh_session(driver)

        def is_page_loaded(driver):
            try:
                # Kiểm tra xem các element quan trọng đã load chưa
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "pt1:it1::content"))
                )
                return True
            except:
                return False

        # Truy cập trang với retry được cải thiện
        base_url = "https://pus.customs.gov.vn/faces/ContainerBarcode"
        if not access_page_with_retry(driver, base_url):
            raise Exception("Không thể truy cập trang sau nhiều lần thử")

        # Kiểm tra trang đã load đầy đủ
        if not is_page_loaded(driver):
            raise Exception("Trang không load đầy đủ các element cần thiết")

        #  day la request toi copy tu trinh duyet
        # fetch("https://pus.customs.gov.vn/faces/ContainerBarcode?Adf-Window-Id=e8q57k1ki&Adf-Page-Id=0", {
        # "headers": {
        #     "accept": "*/*",
        #     "accept-language": "en-US,en;q=0.9,vi;q=0.8",
        #     "adf-ads-page-id": "1",
        #     "adf-rich-message": "true",
        #     "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        #     "sec-ch-ua": "\"Google Chrome\";v=\"135\", \"Not-A.Brand\";v=\"8\", \"Chromium\";v=\"135\"",
        #     "sec-ch-ua-mobile": "?0",
        #     "sec-ch-ua-platform": "\"macOS\"",
        #     "sec-fetch-dest": "empty",
        #     "sec-fetch-mode": "cors",
        #     "sec-fetch-site": "same-origin",
        #     "cookie": "JSESSIONID=hX5dxSOppfET4vIg-OpUKYFLMPsExahq8CkWNTcf8qfmQYKPhqrc!-1434043787; _gtpk_testcookie..undefined=1; _gtpk_testcookie.299.44cc=1; _gtpk_id.299.44cc=0a0b1e399f7b587b.1745329955.1.1745329955.1745329955.; _gtpk_ses.299.44cc=1; _ga=GA1.3.1256538774.1745329955; _gid=GA1.3.691031672.1745329955; _gat=1; _ga_EHX0TT1MG6=GS1.3.1745329955.1.0.1745329955.0.0.0",
        #     "Referer": "https://pus.customs.gov.vn/faces/ContainerBarcode;jsessionid=hX5dxSOppfET4vIg-OpUKYFLMPsExahq8CkWNTcf8qfmQYKPhqrc!-1434043787",
        #     "Referrer-Policy": "strict-origin-when-cross-origin"
        # },
        # "body": "pt1:it1=0901067514&pt1:it2=107096649442&pt1:it3=03PL&pt1:it4=12%2F04%2F2025&org.apache.myfaces.trinidad.faces.FORM=f1&Adf-Window-Id=e8q57k1ki&javax.faces.ViewState=!-m0si0d4wm&Adf-Page-Id=0&event=pt1%3Abtngetdata&event.pt1:btngetdata=%3Cm+xmlns%3D%22http%3A%2F%2Foracle.com%2FrichClient%2Fcomm%22%3E%3Ck+v%3D%22type%22%3E%3Cs%3Eaction%3C%2Fs%3E%3C%2Fk%3E%3C%2Fm%3E&oracle.adf.view.rich.PROCESS=f1%2Cpt1%3Abtngetdata",
        # "method": "POST"
        # });

        # Wait for elements to be present
        wait = WebDriverWait(driver, 30)
        short_wait = WebDriverWait(driver, 2)  # wait ngắn để check nhanh

        print("Bắt đầu điền thông tin form...")
        # Fill tax code
        tax_code_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it1::content")))
        tax_code_input.clear()
        tax_code_input.send_keys(tax_code)
        print("✓ Đã điền mã số thuế:", tax_code)

        # Fill custom number
        custom_no_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it2::content")))
        custom_no_input.clear()
        custom_no_input.send_keys(custom_no)
        print("✓ Đã điền số tờ khai:", custom_no)

        # Fill custom name
        custom_name_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it3::content")))
        custom_name_input.clear()
        custom_name_input.send_keys(custom_name)
        print("✓ Đã điền tên hải quan:", custom_name)

        # Fill date register
        date_register_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it4::content")))
        date_register_input.clear()
        date_register_input.send_keys(date_register)
        print("✓ Đã điền ngày đăng ký:", date_register)

        print("Vui lòng click vào nút 'Lấy thông tin'...")

        # Đợi cho đến khi phát hiện div#content xuất hiện (tối đa 10 giây)
        start_time = time.time()
        found = False

        while time.time() - start_time < 10:  # Kiểm tra trong 10 giây
            try:
                content_div = driver.find_element(By.ID, "content")
                if content_div.is_displayed():
                    found = True
                    print("Đã phát hiện thông tin hải quan, bắt đầu tạo PDF...")
                    break
            except:
                pass
            time.sleep(0.5)  # Đợi 0.5 giây trước khi kiểm tra lại

        if not found:
            raise Exception("Đã hết thời gian chờ (10s) mà không tìm thấy thông tin hải quan. Vui lòng click nút 'Lấy thông tin'")

        time.sleep(2)
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
        output_filename = f"{tax_code}-{custom_no}.pdf"

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




