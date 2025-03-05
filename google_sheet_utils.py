import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

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
                print(f"Lỗi khởi tạo Sheet service: {str(e)}")
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
            print("Không có thông tin container để thêm vào Sheet")
            return False

        # Lấy số dòng hiện tại
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            current_row = len(result.get('values', []))
        except HttpError as e:
            print(f"Lỗi khi đọc dữ liệu từ sheet: {str(e)}")
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
            print(f"Đã thêm {len(line_items)} dòng vào Google Sheet")
            return True
        except Exception as e:
            print(f"Lỗi sau 3 lần thử append dữ liệu: {str(e)}")
            return False

    except Exception as e:
        print(f"Lỗi không mong đợi: {str(e)}")
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
            print(f"Lỗi khi đọc dữ liệu từ sheet: {str(e)}")
            return False

        # Lấy số dòng hiện tại
        try:
            result = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID,
                range=RANGE_NAME
            ).execute()
            current_row = len(result.get('values', []))
        except HttpError as e:
            print(f"Lỗi khi đọc dữ liệu từ sheet: {str(e)}")
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
            1,
            fixed_data['unit'],
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
            print(f"Đã thêm 1 dòng vào Google Sheet")
            return True
        except Exception as e:
            print(f"Lỗi sau 3 lần thử append dữ liệu: {str(e)}")
            return False

    except Exception as e:
        print(f"Lỗi không mong đợi: {str(e)}")
        return False

def update_invoice_info(invoice_info):
    """
    Cập nhật thông tin invoice vào Google Sheet cho dòng đầu tiên có số tờ khai tương ứng và cột P trống

    Args:
        invoice_info: dict chứa thông tin invoice {
            'custom_no': số tờ khai,
            'invoice_no': số hóa đơn,
            'seriesNo': số series,
            'ngay': ngày hóa đơn,
            'total_amount': tổng tiền
        }
    """
    try:
        sheet_instance = SheetService.get_instance()
        sheet = sheet_instance.service.spreadsheets()

        # Tìm dòng chứa số tờ khai
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()
        values = result.get('values', [])

        # Tìm dòng đầu tiên có số tờ khai tương ứng (cột G - index 6) và cột P (index 15) trống
        target_row = None
        for i, row in enumerate(values, 1):  # Bắt đầu từ 1 vì Google Sheet bắt đầu từ 1
            if len(row) > 6 and row[6] == invoice_info['custom_no']:
                # Kiểm tra cột P trống
                if len(row) <= 15 or not row[15].strip():
                    target_row = i
                    break

        if not target_row:
            print(
                f"Không tìm thấy dòng phù hợp cho số tờ khai {invoice_info['custom_no']} "
                "hoặc tất cả các dòng đã có thông tin invoice"
            )
            return False

        # Cập nhật thông tin vào các cột tương ứng
        update_range = f'main!P{target_row}:R{target_row}'  # Cột P-R (16-18)
        update_values = [[
            invoice_info['invoice_no'],
            invoice_info['seriesNo'],
            invoice_info['ngay']
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

        # Cập nhật total_amount vào cột N (14)
        amount_range = f'main!N{target_row}'
        amount_body = {
            'values': [[invoice_info['total_amount']]]
        }

        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=amount_range,
            valueInputOption='USER_ENTERED',
            body=amount_body
        ).execute()

        print("Đã cập nhật thông tin invoice thành công")
        return True

    except Exception as e:
        print(f"Lỗi khi cập nhật thông tin invoice: {str(e)}")
        return False
