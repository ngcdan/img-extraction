import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential
from utils import send_notification

# Cấu hình chung
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = './service-account-key.json'
SPREADSHEET_ID = '1OWxsCEHLzkVGv2sYheAmrHLeLswgeskGx72Q-Sze2LM'
RANGE_NAME = 'main!A:V'

class SheetService:
    _instance = None
    _service = None

    @classmethod
    def get_instance(cls):
        """Singleton pattern để đảm bảo chỉ tạo một instance của Sheet service"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Khởi tạo Sheet service"""
        if self._service is None:
            try:
                if not os.path.exists(SERVICE_ACCOUNT_FILE):
                    raise FileNotFoundError(f"Không tìm thấy file {SERVICE_ACCOUNT_FILE}")

                credentials = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
                self._service = build('sheets', 'v4', credentials=credentials)
            except Exception as e:
                send_notification(f"Lỗi khởi tạo Sheet service: {str(e)}", "error")
                raise

    @property
    def service(self):
        """Trả về Sheet service instance"""
        return self._service

def prepare_row_data(line_item, extracted_info, current_row):
    """Chuẩn bị dữ liệu cho một dòng trong sheet"""
    fixed_data = {
        'service_code': 'CL014920',
        'vendor': 'VETC',
        'charge_code': 'B_EWF',
        'description': 'EXPRESS WAY FEES',
        'unit': 'container'
    }

    return [
        current_row,  # STT
        extracted_info.get('so_ct', ''),  # Số chứng từ
        fixed_data['service_code'],
        fixed_data['vendor'],
        extracted_info.get('jobId', ''),
        extracted_info.get('hawb', ''),
        extracted_info.get('customs_number', ''),
        fixed_data['charge_code'],
        fixed_data['description'],
        line_item.get('quantity', ''),
        fixed_data['unit'],
        line_item.get('unit_price', ''),
        '',  # Cột 12 để trống
        line_item.get('amount', ''),
        extracted_info.get('tax_number', '') != '0303482440',
        '', '', '',
        extracted_info.get('tax_number'),
        extracted_info.get('partner_invoice_name'),
        '',  # Cột 20 để trống (Notes)
        line_item.get('container_no', ''),
        line_item.get('label', '')
    ]

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=lambda e: isinstance(e, HttpError) and e.resp.status_code in [500, 503]
)
def execute_append(sheet, values):
    """Thực hiện append dữ liệu vào sheet với retry logic"""
    body = {'values': values}
    return sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=RANGE_NAME,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()

def append_to_google_sheet(extracted_info):
    """Thêm thông tin vào Google Sheet"""
    try:
        sheet_instance = SheetService.get_instance()
        sheet = sheet_instance.service.spreadsheets()

        # Validate input data
        line_items = extracted_info.get('line_items', [])
        if not line_items:
            send_notification("Không có thông tin container để thêm vào Sheet", "warning")
            return False

        # Lấy số dòng hiện tại
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            current_row = len(result.get('values', []))
        except HttpError as e:
            send_notification(f"Lỗi khi đọc dữ liệu từ sheet: {str(e)}", "error")
            return False

        # Chuẩn bị dữ liệu
        values = []
        for line in line_items:
            row_data = prepare_row_data(line, extracted_info, current_row)
            values.append(row_data)
            current_row += 1

        # Thực hiện append với retry
        try:
            execute_append(sheet, values)
            send_notification(f"Đã thêm {len(line_items)} dòng vào Google Sheet", "success")
            return True
        except Exception as e:
            send_notification(f"Lỗi sau 3 lần thử append dữ liệu: {str(e)}", "error")
            return False

    except Exception as e:
        send_notification(f"Lỗi không mong đợi: {str(e)}", "error")
        return False

def append_to_google_sheet_new(extracted_info):
    """Thêm thông tin vào Google Sheet"""
    try:
        sheet_instance = SheetService.get_instance()
        sheet = sheet_instance.service.spreadsheets()

        """Chuẩn bị dữ liệu cho một dòng trong sheet"""
        fixed_data = {
            'service_code': 'CL014920',
            'vendor': 'VETC',
            'charge_code': 'B_EWF',
            'description': 'EXPRESS WAY FEES',
            'unit': 'container'
        }


        result = {
            'so_ct': None,
            'date': None,
            'tax_number': None,
            'customs_number': None,
            'partner_invoice_name': None
        }

        # Lấy số dòng hiện tại
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            current_row = len(result.get('values', []))
        except HttpError as e:
            send_notification(f"Lỗi khi đọc dữ liệu từ sheet: {str(e)}", "error")
            return False

        # Lấy số dòng hiện tại
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            current_row = len(result.get('values', []))
        except HttpError as e:
            send_notification(f"Lỗi khi đọc dữ liệu từ sheet: {str(e)}", "error")
            return False

        values = []
        row_data = [
            current_row,  # STT
            extracted_info.get('so_ct', ''),  # Số chứng từ
            fixed_data['service_code'],
            fixed_data['vendor'],
            extracted_info.get('jobId', ''),
            extracted_info.get('hawb', ''),
            extracted_info.get('customs_number', ''),
            fixed_data['charge_code'],
            fixed_data['description'],
            '',
            '',
            '',
            ''
            '',
            '',
            extracted_info.get('tax_number', '') != '0303482440',
            '', '', '',
            extracted_info.get('tax_number'),
            extracted_info.get('partner_invoice_name'),
            '',  # Cột 20 để trống (Notes)
            '',
            ''
        ]
        values.append(row_data)

        # Thực hiện append với retry
        try:
            execute_append(sheet, values)
            send_notification(f"Đã thêm 1 dòng vào Google Sheet", "success")
            return True
        except Exception as e:
            send_notification(f"Lỗi sau 3 lần thử append dữ liệu: {str(e)}", "error")
            return False

    except Exception as e:
        send_notification(f"Lỗi không mong đợi: {str(e)}", "error")
        return False

def update_last_row_sheet(invoice_info):
    """Cập nhật thông tin invoice cho dòng cuối cùng trong Google Sheet"""
    try:
        sheet_instance = SheetService.get_instance()
        sheet = sheet_instance.service.spreadsheets()

        # Lấy số dòng hiện tại
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            values = result.get('values', [])
            last_row = len(values)

            if last_row == 0:
                send_notification("Không có dữ liệu trong sheet", "error")
                return False

            # Cập nhật các ô cần thiết ở dòng cuối
            update_range = f'main!P{last_row}:R{last_row}'  # Cột P-R (16-18)
            update_values = [[
                invoice_info.get('invoice_no', ''),
                invoice_info.get('seriesNo', ''),
                invoice_info.get('ngay', '')
            ]]

            body = {
                'values': update_values
            }

            sheet.values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            send_notification("Đã cập nhật thông tin invoice thành công", "success")
            return True

        except HttpError as e:
            send_notification(f"Lỗi khi cập nhật Google Sheet: {str(e)}", "error")
            return False

    except Exception as e:
        send_notification(f"Lỗi không mong đợi: {str(e)}", "error")
        return False
