import os
import time
import base64
import tkinter as tk
from tkinter import simpledialog, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from dotenv import load_dotenv

load_dotenv()

class ReceiptFetcher:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.base_url = os.getenv('BASE_URL', 'http://thuphi.haiphong.gov.vn:8222')
        self.debug_port = os.getenv('CHROME_DEBUG_PORT', '9222')

    def initialize_driver(self):
        try:
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.debug_port}")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            print("Successfully connected to Chrome")
            return True
        except Exception as e:
            print(f"Error initializing Chrome driver: {e}")
            return False

    def get_login_credentials(self):
        root = tk.Tk()
        root.withdraw()

        while True:
            username = simpledialog.askstring("Login", "Enter tax number:")
            if username is None:
                messagebox.showerror("Error", "Tax number is required!")
                return None, None
            if not username.strip() or not username.strip().isdigit():
                messagebox.showerror("Error", "Tax number must contain only digits!")
                continue
            break
        return username.strip(), username.strip()

    def login(self, username, password):
        try:
            self.navigate_to_page('/dang-nhap')

            # Fill login form
            self.wait.until(EC.presence_of_element_located((By.ID, "form-username")))
            username_input = self.driver.find_element(By.ID, "form-username")
            username_input.clear()
            username_input.send_keys(username)

            password_input = self.driver.find_element(By.ID, "form-password")
            password_input.clear()
            password_input.send_keys(password)

            return True
        except Exception as e:
            print(f"Login error: {e}")
            return False

    def navigate_to_page(self, path):
        try:
            # Mở tab mới với target URL
            self.driver.execute_script(f"window.open('{self.base_url}{path}', '_blank');")
            time.sleep(1)

            # Chuyển đến tab mới
            self.driver.switch_to.window(self.driver.window_handles[-1])

        except Exception as e:
            print(f"Navigation error: {e}")
            return False

    def navigate_to_receipt_list(self, customs_number=''):
        try:
            self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[.//p[contains(text(), 'Tra cứu')]]")
            )).click()

            self.driver.execute_script("document.querySelector('ul.nav-treeview').style.display = 'block';")
            time.sleep(2)

            self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[href='/danh-sach-tra-cuu-bien-lai-dien-tu']")
            )).click()

            if customs_number:
                time.sleep(3)
                customs_input = self.wait.until(EC.presence_of_element_located((By.NAME, "SO_TK")))
                customs_input.clear()
                customs_input.send_keys(customs_number)

                self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.btnSearch")
                )).click()
                time.sleep(3)

            return True
        except Exception as e:
            print(f"Error navigating to receipt list: {e}")
            return False

    def download_receipt(self, link_element):
        try:
            file_info = self._get_file_info(link_element)
            if not file_info:
                return False

            href = link_element.get_attribute('href')
            self.driver.execute_script(f"window.open('{href}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])

            pdf_data = self._capture_pdf()
            if not pdf_data:
                return False

            self._save_pdf(pdf_data, file_info)

            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[-1])
            return True
        except Exception as e:
            print(f"Error downloading PDF: {e}")
            self._cleanup_after_error()
            return False

    def _get_file_info(self, link_element):
        try:
            row = link_element.find_element(By.XPATH, "./ancestor::tr")
            columns = row.find_elements(By.TAG_NAME, "td")

            return {
                'customs_number': columns[4].text.strip(),
                'date': columns[5].text.strip().replace('/', ''),
                'filename': f"{columns[4].text.strip()}.pdf"
            }
        except Exception as e:
            print(f"Error getting file info: {e}")
            return None

    def _capture_pdf(self):
        try:
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            print_options = {
                'landscape': False,
                'displayHeaderFooter': False,
                'printBackground': True,
                'preferCSSPageSize': True,
            }
            pdf = self.driver.execute_cdp_cmd("Page.printToPDF", print_options)
            return base64.b64decode(pdf['data'])
        except Exception as e:
            print(f"Error capturing PDF: {e}")
            return None

    def _save_pdf(self, pdf_data, file_info):
        base_dir = os.getenv('PDF_STORAGE_PATH', 'downloaded_pdfs')
        date_dir = os.path.join(base_dir, file_info['date'])
        customs_dir = os.path.join(date_dir, file_info['customs_number'])

        # Create directories if they don't exist
        for directory in [base_dir, date_dir, customs_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        file_path = os.path.join(customs_dir, file_info['filename'])

        # Handle duplicate filenames
        if os.path.exists(file_path):
            base_name = os.path.splitext(file_info['filename'])[0]
            counter = 1
            while os.path.exists(file_path):
                new_filename = f"{base_name}_{counter}.pdf"
                file_path = os.path.join(customs_dir, new_filename)
                counter += 1

        with open(file_path, 'wb') as f:
            f.write(pdf_data)
        print(f"Saved file: {file_path}")

    def _cleanup_after_error(self):
        try:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[-1])
        except:
            pass

    def close(self):
        if self.driver:
            self.driver.quit()
