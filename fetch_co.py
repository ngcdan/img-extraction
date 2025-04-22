from chrome_manager import ChromeManager
from cookie_manager import CookieManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

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

        # Điều hướng đến trang web và xử lý URL
        print("Đang truy cập trang web...")
        base_url = "https://pus.customs.gov.vn/faces/ContainerBarcode"

        # Truy cập URL và đợi load
        if not ChromeManager.wait_for_page_load(driver, base_url):
            raise Exception("Không thể tải trang web")

        # Nếu URL hiện tại khác base_url, force navigate lại
        current_url = driver.current_url
        if base_url not in current_url:
            print("Đang chuyển về URL gốc...")
            driver.execute_script(f"window.location.href = '{base_url}'")
            if not ChromeManager.wait_for_page_load(driver, base_url):
                raise Exception("Không thể tải lại trang web")

        print("✓ Đã truy cập trang web thành công")

        # Wait for elements to be present
        wait = WebDriverWait(driver, 30)
        short_wait = WebDriverWait(driver, 2)  # wait ngắn để check nhanh

        # Đợi preloader xuất hiện và biến mất
        print("Đang đợi trang load hoàn tất...")
        try:
            # Đợi preloader xuất hiện
            preloader = short_wait.until(EC.presence_of_element_located((By.CLASS_NAME, "preloader-container")))
            print("Đang load...")

            # Đợi preloader biến mất
            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "preloader-container")))
            print("✓ Preloader đã biến mất")
        except:
            print("Không thấy preloader, tiếp tục...")

        # Đợi tất cả các trường input xuất hiện và có thể tương tác
        print("Đang đợi form load hoàn tất...")
        try:
            # Đợi tất cả các trường input
            tax_code_input = wait.until(EC.element_to_be_clickable((By.ID, "pt1:it1::content")))
            custom_no_input = wait.until(EC.element_to_be_clickable((By.ID, "pt1:it2::content")))
            custom_name_input = wait.until(EC.element_to_be_clickable((By.ID, "pt1:it3::content")))
            date_register_input = wait.until(EC.element_to_be_clickable((By.ID, "pt1:it4::content")))
            print("✓ Tất cả trường input đã sẵn sàng")
        except Exception as e:
            raise Exception(f"Form chưa load hoàn tất: {str(e)}")

        print("Bắt đầu điền thông tin form...")
        # Fill tax code
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

        # Đợi 2s trước khi click nút lấy thông tin
        print("Đợi 2s trước khi click nút lấy thông tin...")
        time.sleep(2)

        # <div id="pt1:btngetdata" class="btngetdata xfn p_AFTextOnly" _afrgrp="0" role="presentation" style="display: inline-block;"><a href="#" onclick="this.focus();return false" data-afr-fcs="true" class="xfp" role="button"><span class="xfx">Lấy thông tin </span></a></div>

        # Find and click the button
        print("Tìm và click nút lấy thông tin...")
        get_data_div = wait.until(EC.presence_of_element_located((By.ID, "pt1:btngetdata")))
        print("✓ Đã tìm thấy div chứa nút lấy thông tin")

        # Tìm thẻ a bên trong
        get_data_link = get_data_div.find_element(By.TAG_NAME, "a")
        print("✓ Đã tìm thấy nút lấy thông tin")

        # Mô phỏng chuỗi events như người dùng thực hiện
        driver.execute_script("""
            // Focus vào element
            arguments[0].focus();

            // Trigger event focus như trong onClick
            var focusEvent = new FocusEvent('focus', {
                'view': window,
                'bubbles': true,
                'cancelable': true
            });
            arguments[0].dispatchEvent(focusEvent);
        """, get_data_link)
        print("✓ Đã trigger events trên nút lấy thông tin")

        # Đợi trang load xong
        ChromeManager.wait_for_page_load(driver, driver.current_url)

        # Đợi và click vào label "Trang để in"
        print("Đợi và click vào label 'Trang để in'...")
        label_element = wait.until(EC.element_to_be_clickable((By.ID, "lbl_BanIn")))
        driver.execute_script("arguments[0].click();", label_element)

    except Exception as e:
        print(f"Lỗi khi xử lý: {str(e)}")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()




