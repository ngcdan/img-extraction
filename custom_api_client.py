import requests
import json
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
API_CONFIG = {
    "BASE_URL": "https://beelogistics.cloud/api",
    "TIMEOUT": 30,
    "RESOURCE_NAME": "resource:custom-ie-api"
}

class ApiEndpoints(str, Enum):
    RESOURCE = "/resource"

@dataclass
class ApiCredentials:
    api_key: str = ""

    @classmethod
    def from_env(cls):
        api_key = os.getenv("DATATP_API_KEY")
        if not api_key:
            raise ValueError("DATATP_API_KEY not found in environment variables")
        return cls(api_key=api_key)

class ApiResponse:
    def __init__(self, status: str = "ERROR", data: Optional[Dict] = None, message: str = ""):
        self.status = status
        self.data = data or {}
        self.message = message

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "data": self.data,
            "message": self.message
        }

class CustomApiClient:
    def __init__(self, credentials: Optional[ApiCredentials] = None):
        self.credentials = credentials or ApiCredentials.from_env()
        self.base_url = API_CONFIG["BASE_URL"]
        self.timeout = API_CONFIG["TIMEOUT"]

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "DataTP-Authorization": self.credentials.api_key
        }

    def _make_request(self, endpoint: str, data: Dict) -> ApiResponse:
        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                headers=self._get_headers(),
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return ApiResponse(
                status="OK",
                data=response.json(),
                message="Success"
            )
        except requests.RequestException as e:
            error_message = f"Request failed: {str(e)}"
            error_details = {
                "url": e.response.url if hasattr(e, 'response') else None,
                "status_code": e.response.status_code if hasattr(e, 'response') else None,
                "headers": dict(e.response.headers) if hasattr(e, 'response') else None,
                "response_text": e.response.text if hasattr(e, 'response') else 'No response',
                "request_headers": dict(e.request.headers) if hasattr(e, 'request') else None,
                "request_body": e.request.body if hasattr(e, 'request') else None
            }
            print(f"Error: {error_message}")
            print("Error Details:")
            print(json.dumps(error_details, indent=2, ensure_ascii=False))
            return ApiResponse(
                status="ERROR",
                message=error_message,
                data=error_details
            )
        except json.JSONDecodeError as e:
            error_message = f"Failed to parse JSON response: {str(e)}"
            print(error_message)
            try:
                raw_response = response.text
                print(f"Raw response: {raw_response}")
            except Exception as raw_err:
                print(f"Could not get raw response: {str(raw_err)}")
            return ApiResponse(
                status="ERROR",
                message=error_message,
                data={"raw_response": raw_response if 'raw_response' in locals() else None}
            )

    def fetch_customs_data(self, customs_numbers: List[str]) -> ApiResponse:
        request_data = {
            "customsNumbers": customs_numbers
        }
        return self._make_request(ApiEndpoints.RESOURCE, request_data)

    def fetch_customs_location_by_name(self, custom_name: str) -> ApiResponse:
        request_data = {
            "name": custom_name
        }
        return self._make_request(ApiEndpoints.RESOURCE, request_data)

def parse_response(response_data: Dict) -> List[Dict]:
    """Parse and extract records from API response data"""
    try:
        # Kiểm tra response_data có tồn tại
        if not response_data:
            print("Response data is None or empty")
            return []

        # Parse nếu là string
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError:
                print("Failed to parse response_data as JSON string")
                return []

        # Kiểm tra và lấy data field
        data = response_data.get('data')
        if not data:
            print("No 'data' field in response")
            return []

        # Parse data nếu là string
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                print("Failed to parse data field as JSON string")
                return []

        # Lấy records với kiểm tra null
        result = data.get('result', {})
        if not result:
            print("No 'result' field in data")
            return []

        records = result.get('records', [])
        if not records:
            print("No records found")
            return []

        return records

    except Exception as e:
        print(f"Error parsing response: {str(e)}")
        print(f"Response data: {response_data}")
        return []

def main():
    # Initialize API client using environment variables
    client = CustomApiClient()

    # Example customs numbers
    # test_customs_numbers = ["1234567890", "106983609350", "106983665130"]
    custom_name = "HQTTHUAN"

    # Fetch data
    result = client.fetch_customs_location_by_name(custom_name)

    # Process results
    if result.status == "OK":
        records = parse_response(result.data)
        print(json.dumps(records, indent=2, ensure_ascii=False))

        print("\nProcessed Records:")
        # for record in records:
        #     print(f"\nTransaction: {record['TransID']}")
        #     print(f"HAWB: {record['hawb']}")
        #     print(f"Customs No: {record['customs_no']}")
        #     print(f"Partner: {record['PartnerName3']}")
        #     print("-" * 50)
    else:
        print(f"\nError: {result.message}")

if __name__ == "__main__":
    main()
