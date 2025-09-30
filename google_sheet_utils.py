import os
import sys
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential
from utils import get_resource_path


# Cấu hình chung
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'driver-service-account.json'
SPREADSHEET_ID = '1OWxsCEHLzkVGv2sYheAmrHLeLswgeskGx72Q-Sze2LM'
HEADER_ROW = [
    'PartnerID', 'PartnerName', 'JobNo', 'HBLNo', 'Custom No',
    'FeeCode', 'FeeName', 'Quantity', 'Unit', 'Amount', 'VAT',
    'TotalAmount', 'OBH', 'InvoiceNo', 'SeriesNo', 'InvoiceDate',  'PartnerID_Inv', 'PartnerName_Inv', 'Source File'
]

class SheetService:
    _instance = None
    _service = None
    _sheet_cache = {}  # Cache để lưu trữ thông tin về các sheet đã tạo

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self._service is None:
            try:
                cred_path = SERVICE_ACCOUNT_FILE
                if not os.path.exists(cred_path):
                    cred_path = get_resource_path('data1.bin')

                if not os.path.exists(cred_path):
                    raise FileNotFoundError(f"Không tìm thấy file credentials")

                credentials = service_account.Credentials.from_service_account_file(
                    cred_path, scopes=SCOPES)
                self._service = build('sheets', 'v4', credentials=credentials)
                self._load_existing_sheets()
            except Exception as e:
                print(f"Lỗi khởi tạo Sheet service: {str(e)}")
                raise

    def _load_existing_sheets(self):
        """Load tất cả sheets hiện có vào cache"""
        try:
            spreadsheet = self._service.spreadsheets().get(
                spreadsheetId=SPREADSHEET_ID
            ).execute()

            sheets = []
            for sheet in spreadsheet.get('sheets', []):
                title = sheet['properties']['title']
                sheet_id = sheet['properties']['sheetId']
                try:
                    # Thử chuyển đổi tên sheet thành datetime
                    date_obj = datetime.strptime(title, '%d/%m/%Y')
                    sheets.append((title, sheet_id, date_obj))
                except ValueError:
                    # Nếu không phải định dạng ngày, thêm vào đầu danh sách
                    sheets.insert(0, (title, sheet_id, None))

            # Sắp xếp sheets theo ngày (ngày nhỏ hơn ở bên trái)
            sorted_sheets = sorted(sheets, key=lambda x: (x[2] is None, x[2] or datetime.min))

            # Cập nhật vị trí của các sheets
            requests = []
            for index, (title, sheet_id, _) in enumerate(sorted_sheets):
                self._sheet_cache[title] = sheet_id
                requests.append({
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': sheet_id,
                            'index': index
                        },
                        'fields': 'index'
                    }
                })

            if requests:
                self._service.spreadsheets().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body={'requests': requests}
                ).execute()

        except Exception as e:
            print(f"Lỗi khi load danh sách sheets: {str(e)}")

    def _create_new_sheet(self, sheet_name):
        """Tạo sheet mới với tên được chỉ định"""
        try:
            # Tìm vị trí thích hợp cho sheet mới
            new_date = datetime.strptime(sheet_name, '%d/%m/%Y')
            existing_sheets = []

            spreadsheet = self._service.spreadsheets().get(
                spreadsheetId=SPREADSHEET_ID
            ).execute()

            for sheet in spreadsheet.get('sheets', []):
                title = sheet['properties']['title']
                try:
                    date_obj = datetime.strptime(title, '%d/%m/%Y')
                    existing_sheets.append((title, date_obj))
                except ValueError:
                    continue

            # Sắp xếp sheets theo ngày
            existing_sheets.sort(key=lambda x: x[1])

            # Tìm vị trí thích hợp cho sheet mới
            insert_index = 0
            for i, (_, date_obj) in enumerate(existing_sheets):
                if new_date > date_obj:
                    insert_index = i + 1

            # Tạo sheet mới tại vị trí đã xác định
            request = {
                'addSheet': {
                    'properties': {
                        'title': sheet_name,
                        'index': insert_index
                    }
                }
            }

            result = self._service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={'requests': [request]}
            ).execute()

            # Lấy sheet ID mới
            new_sheet_id = result['replies'][0]['addSheet']['properties']['sheetId']

            # Thêm header với định dạng
            range_name = f"'{sheet_name}'!A1:U1"
            self._service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=range_name,
                valueInputOption='RAW',
                body={'values': [HEADER_ROW]}
            ).execute()

            # Định dạng header
            requests = [
                # Định dạng chung cho header
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': new_sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': len(HEADER_ROW)
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': {
                                    'red': 1.0,
                                    'green': 0.427,
                                    'blue': 0.004,
                                },
                                'textFormat': {
                                    'bold': True,
                                    'fontSize': 11
                                },
                                'verticalAlignment': 'MIDDLE',
                                'horizontalAlignment': 'CENTER'
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,textFormat,verticalAlignment,horizontalAlignment)'
                    }
                },
                # Định dạng text cho cột Custom No (index 4)
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': new_sheet_id,
                            'startRowIndex': 1,
                            'startColumnIndex': 4,
                            'endColumnIndex': 5
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'numberFormat': {
                                    'type': 'TEXT'
                                }
                            }
                        },
                        'fields': 'userEnteredFormat.numberFormat'
                    }
                },
                # Điều chỉnh độ rộng cột cho VendorName (index 1)
                {
                    'updateDimensionProperties': {
                        'range': {
                            'sheetId': new_sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': 1,
                            'endIndex': 2
                        },
                        'properties': {
                            'pixelSize': 300
                        },
                        'fields': 'pixelSize'
                    }
                },
                # Điều chỉnh độ rộng cột cho Description (index 6)
                {
                    'updateDimensionProperties': {
                        'range': {
                            'sheetId': new_sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': 6,
                            'endIndex': 7
                        },
                        'properties': {
                            'pixelSize': 300
                        },
                        'fields': 'pixelSize'
                    }
                },
                # Điều chỉnh độ rộng cột cho PartnerInvoiceName (index 17)
                {
                    'updateDimensionProperties': {
                        'range': {
                            'sheetId': new_sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': 18,
                            'endIndex': 19
                        },
                        'properties': {
                            'pixelSize': 300
                        },
                        'fields': 'pixelSize'
                    }
                }
            ]

            # Thực hiện các thay đổi định dạng
            self._service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body={'requests': requests}
            ).execute()

            # Cập nhật cache
            self._sheet_cache[sheet_name] = new_sheet_id
            return new_sheet_id
        except Exception as e:
            print(f"Lỗi khi tạo sheet mới {sheet_name}: {str(e)}")
            raise

    def get_or_create_sheet(self, date_str):
        """Lấy hoặc tạo sheet theo ngày"""
        try:
            # Chuyển đổi date_str (dd/mm/yyyy) thành datetime để sắp xếp
            date_obj = datetime.strptime(date_str, '%d/%m/%Y')
            sheet_name = date_obj.strftime('%d/%m/%Y')

            if sheet_name not in self._sheet_cache:
                self._create_new_sheet(sheet_name)

            return sheet_name
        except Exception as e:
            print(f"Lỗi khi get/create sheet cho ngày {date_str}: {str(e)}")
            raise

    @property
    def service(self):
        return self._service

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=lambda e: isinstance(e, HttpError) and e.resp.status_code in [500, 503]
)
def execute_append(sheet, sheet_name, values):
    """Thực hiện append dữ liệu vào sheet với retry logic"""
    body = {'values': values}
    range_name = f"'{sheet_name}'!A:U"
    return sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=range_name,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()

def batch_append_to_sheet(rows):
    """
    Append nhiều dòng vào sheet cùng lúc
    """
    try:
        sheet_instance = SheetService.get_instance()
        sheet = sheet_instance.service.spreadsheets()  # Thêm .spreadsheets()

        # Group rows by date
        date_groups = {}
        for row in rows:
            date = row.get('ngay', datetime.now().strftime('%d/%m/%Y'))
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(row)

        # Batch append for each date group
        for date, group_rows in date_groups.items():
            sheet_name = sheet_instance.get_or_create_sheet(date)
            values = []

            for row in group_rows:
                fixed_data = {
                    'service_code': 'CL015567',
                    'vendor': 'SO GTVT- SO GIAO THONG VAN TAI',
                    'charge_code': 'B_CSHT',
                    'description': 'INFRASTRUCTURE FEES',
                    'unit': 'shipment'
                }

                row_data = [
                    fixed_data['service_code'],
                    fixed_data['vendor'],
                    row.get('jobId', ''),
                    row.get('hawb', ''),
                    f"'{row.get('custom_no', '')}",
                    fixed_data['charge_code'],
                    fixed_data['description'],
                    1,
                    fixed_data['unit'],
                    row.get('total_amount', ''),
                    '', # tax
                    row.get('total_amount', ''),
                    row.get('tax_number', '') != '0303482440',
                    f"'{row.get('invoice_no', '')}",
                    row.get('seriesNo', ''),
                    row.get('ngay', ''),
                    row.get('partner_invoice_id', ''),
                    row.get('partner_invoice_name'),
                    row.get('source_file'),
                ]
                values.append(row_data)

            execute_append(sheet, sheet_name, values)

        return True

    except Exception as e:
        print(f"Lỗi batch append to sheet: {str(e)}")
        return False

