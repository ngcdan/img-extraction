import base64
import requests
import json
from utils import Base64Util, IOUtil
from typing import TypedDict, Optional

class MSAClientConfig(TypedDict):
    rest_url: str
    authorization: str
    verbose: bool

class ServiceCall(TypedDict):
    service: str
    endpoint: str
    userParams: dict

class MSAClient:
    def __init__(self, config: MSAClientConfig):
        self.base_url = config['rest_url']
        self.config = config
        self.service_call_path = "/service/call"
        self.headers = {"Content-Type": "application/json"}

        if 'authorization' in config and config['authorization']:
            self.headers["DataTP-Authorization"] = config['authorization']

    def set_service_call_path(self, path: str) -> None:
        self.service_call_path = path

    def call(self, service: str, endpoint: str, user_params: dict):
        payload: ServiceCall = {
            "service": service,
            "endpoint": endpoint,
            "userParams": user_params
        }

        url = f"{self.base_url}{self.service_call_path}"

        if self.config.get('verbose', False):
            print(f"Calling {url}")
            print(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(url, json=payload, headers=self.headers)
        json_resp = json.loads(response.content)

        # Parse the data field if it's a JSON string
        if 'data' in json_resp and isinstance(json_resp['data'], str):
            try:
                json_resp['data'] = json.loads(json_resp['data'])
            except json.JSONDecodeError:
                # If it's not valid JSON, keep it as is
                pass

        return json_resp

def test_ecus_ie_service_xlsx_form_ie():

    # Initialize client with config
    config: MSAClientConfig = {
        'rest_url': 'http://localhost:8888/api',
        'authorization': '',
        'verbose': True
    }
    client = MSAClient(config=config)

    # Set up file paths
    data_dir = f"data/log"
    # filename = "tokhai-2.xlsx"
    filename = "tokhai-1.xls"
    file_path = f"{data_dir}/{filename}"

    # Read and encode the Excel file
    try:
        bytes_data = IOUtil.read_bytes(file_path)
        base64_data = Base64Util.encode(bytes_data)
    except Exception as e:
        # Fallback to standard library if datatp_common is not available
        with open(file_path, "rb") as file:
            bytes_data = file.read()
        base64_data = base64.b64encode(bytes_data).decode('utf-8')

    # Set up request parameters
    user_params = {
        "fileName": filename,
        "data": base64_data
    }

    # Make the API call
    result = client.call("EcusIEService", "xlsx_form_ie", user_params)

    # Print the result
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    test_ecus_ie_service_xlsx_form_ie()