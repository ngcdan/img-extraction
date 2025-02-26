import requests

# URL
url = "http://thuphi.haiphong.gov.vn:8222/tra-cuu-bien-lai-dien-tu"

# Query parameters
params = {
    "ma_tracuu": "FKJA4y8G6a",
    "textView": "SUCCESS!"
}

# Headers
headers = {
    "Host": "thuphi.haiphong.gov.vn:8222",
    "Pragma": "no-cache",
    "Referer": "http://thuphi.haiphong.gov.vn:8222/"
}

# Cookies
cookies = {
    "ASP.NET_SessionId": "1hxgwkxo4o4b31vg0vrocr0h",
    "__RequestVerificationToken": "L0RDS71AK2dJnn9cGY7KDwbaTATkOw4MHsxiZSQ5LAT8Bzk2beUD_7n4AohCRhGBgutK6aL8HC1-Ch71rUvGrmskvyUeW4UlUTWyjdXhhHI1"
}

try:
    # Gửi GET request
    response = requests.get(url, params=params, headers=headers, cookies=cookies)

    # Kiểm tra status code
    if response.status_code == 200:
        print("Request thành công!")
        # In nội dung response
        print(response.text)
    else:
        print(f"Request thất bại với status code: {response.status_code}")

except requests.exceptions.RequestException as e:
    print(f"Đã xảy ra lỗi: {e}")