import requests
from utils import send_notification
import os
from dotenv import load_load_dotenv

load_dotenv()

class DatabaseAPI:
    def __init__(self):
        self.api_base_url = os.getenv('API_BASE_URL')
        self.api_key = os.getenv('API_KEY')

    def get_headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def query_customs_info(self, customs_number):
        """Truy vấn thông tin qua API thay vì kết nối trực tiếp"""
        try:
            response = requests.get(
                f"{self.api_base_url}/customs/info",
                params={'customs_number': customs_number},
                headers=self.get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    print("\nKết quả truy vấn từ API:")
                    for item in data['data']:
                        print(f"TransID: {item['TransID']}, HWBNO: {item['HWBNO']}, "
                              f"TKSo: {item['TKSo']}, Người khai: {item['nguoi_khai']}")
                    return data['data']
                else:
                    print("Không tìm thấy dữ liệu phù hợp.")
                    return None
            else:
                error_msg = f"Lỗi API: {response.status_code} - {response.text}"
                print(error_msg)
                send_notification(error_msg, "error")
                return None

        except requests.exceptions.RequestException as e:
            error_msg = f"Lỗi kết nối API: {str(e)}"
            print(error_msg)
            send_notification(error_msg, "error")
            return None