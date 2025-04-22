from chrome_manager import ChromeManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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


        # Query String Params:
        #    Adf-Window-Id: w391hhlu4a
        #    Adf-Page-Id: 1

        # Form Data:
        #    pt1:it1: 0901067514
        #    pt1:it2: 107096646160
        #    pt1:it3: 03PL
        #    pt1:it4: 12/04/2025
        #    org.apache.myfaces.trinidad.faces.FORM: f1
        #    Adf-Window-Id: w391hhlu4a
        #    Adf-Page-Id: 1
        #    javax.faces.ViewState: !7rtfk0021
        #    event: pt1:btngetdata
        #    event.pt1:btngetdata: <m xmlns="http://oracle.com/richClient/comm"><k v="type"><s>action</s></k></m>
        #    oracle.adf.view.rich.PROCESS: f1,pt1:btngetdata

#         Request URL:
# https://pus.customs.gov.vn/faces/ContainerBarcode?Adf-Window-Id=w391hhlu4a&Adf-Page-Id=1
# Request Method:
# POST
# Status Code:
# 200 OK
# Remote Address:
# 58.186.80.48:443
# Referrer Policy:
# strict-origin-when-cross-origin
# access-control-allow-origin:
# *.customs.gov.vn
# content-type:
# text/xml;charset=utf-8
# date:
# Tue, 22 Apr 2025 08:31:27 GMT
# server:
# nginx/1.14.2
# transfer-encoding:
# chunked
# x-content-type-options:
# nosniff
# x-oracle-dms-ecid:
# 4f22502d-5df2-458f-8d8a-080f22a66ea2-00cb81d6
# x-oracle-dms-rid:
# 0
# x-xss-protection:
# 1; mode=block
# accept:
# */*
# accept-encoding:
# gzip, deflate, br, zstd
# accept-language:
# en-US,en;q=0.9,vi;q=0.8
# adf-ads-page-id:
# 3
# adf-rich-message:
# true
# connection:
# keep-alive
# content-length:
# 415
# content-type:
# application/x-www-form-urlencoded; charset=UTF-8
# cookie:
# JSESSIONID=nVtceKGrGNmK2cyuevRzp7Z154EhovMcNpTKec7Dr2GCEFt2ma-M!-1434043787; _gtpk_testcookie..undefined=1; _gtpk_testcookie.299.44cc=1; _gtpk_ses.299.44cc=1; _gtpk_id.299.44cc=7125c0f80b5b9595.1745308163.1.1745309736.1745308163.; _ga=GA1.3.763947152.1745309737; _gid=GA1.3.1663894412.1745309737; _ga_EHX0TT1MG6=GS1.3.1745309736.1.0.1745309736.0.0.0
# host:
# pus.customs.gov.vn
# origin:
# https://pus.customs.gov.vn
# referer:
# https://pus.customs.gov.vn/faces/ContainerBarcode
# sec-ch-ua:
# "Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"
# sec-ch-ua-mobile:
# ?0
# sec-ch-ua-platform:
# "macOS"
# sec-fetch-dest:
# empty
# sec-fetch-mode:
# cors
# sec-fetch-site:
# same-origin
# user-agent:
# Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36

        # Điều hướng đến trang web
        print("Đang truy cập trang web...")
        url = "https://pus.customs.gov.vn/faces/ContainerBarcode"
        if not ChromeManager.wait_for_page_load(driver, url):
            raise Exception("Không thể tải trang web")

        # Wait for elements to be present
        wait = WebDriverWait(driver, 20)

        # Fill tax code
        tax_code_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it1::content")))
        tax_code_input.clear()
        tax_code_input.send_keys(tax_code)

        # Fill custom number
        custom_no_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it2::content")))
        custom_no_input.clear()
        custom_no_input.send_keys(custom_no)

        # Fill custom name
        custom_name_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it3::content")))
        custom_name_input.clear()
        custom_name_input.send_keys(custom_name)

        # Fill date register
        date_register_input = wait.until(EC.presence_of_element_located((By.ID, "pt1:it4::content")))
        date_register_input.clear()
        date_register_input.send_keys(date_register)

        # Find and click the button
        print("Đợi và click Lay thon tin...")
        get_data_button = wait.until(EC.element_to_be_clickable((By.ID, "pt1:btngetdata")))
        driver.execute_script("arguments[0].click();", get_data_button)

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




