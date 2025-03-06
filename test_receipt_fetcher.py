import requests

# Định nghĩa URL
url = "http://thuphi.haiphong.gov.vn:8222/DBienLaiThuPhi_TraCuu/GetListEinvoiceByMaDN/"

# Định nghĩa headers
headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7,fr-FR;q=0.6,fr;q=0.5",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Host": "thuphi.haiphong.gov.vn:8222",
    "Origin": "http://thuphi.haiphong.gov.vn:8222",
    "Pragma": "no-cache",
    "Referer": "http://thuphi.haiphong.gov.vn:8222/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "__RequestVerificationToken": "qtoNiopogBruJdSwe0oA-CYxHULIshLnQLE2RU4FPe9IIpitzR4DDsReflJcpixOITjx5OmLzqVjxkwPnFUdLT8NAy8FXE4mFKnoVXlGotg1"
}

# Định nghĩa cookies
cookies = {
    "SessionToken": "eyJTZXNzaW9uX1Rva2VuIjoiZTIzNmIzMjYtOTBmYS00YjNkLTlhNDYtYTg2NmNiNmM2ZTMzIiwiVXNlcklkIjo1NDUzNCwiQWNjb3VudFR5cGUiOjF9",
    "ASP.NET_SessionId": "bagdnbumiz1515wfldvkcwle",
    "__RequestVerificationToken": "OV5aPQ1D15z4qWOR018LFfFZXhml00vppSQpaax1b-Mmgz1RNGVfvZpeVPU9Ip555gOLBKNE3LQHmitdhWdzqoz0JFhcjJQRCSdPWL6Q1kU1"
}

# Định nghĩa form data
data = {
    "EinvoiceFrom": "0",
    "tu_ngay": "01/03/2025",
    "den_ngay": "06/03/2025",
    "ma_dn": "0800470967",
    "so_tokhai": "106980540920",
    "pageNum": "1",
    "__RequestVerificationToken": "qtoNiopogBruJdSwe0oA-CYxHULIshLnQLE2RU4FPe9IIpitzR4DDsReflJcpixOITjx5OmLzqVjxkwPnFUdLT8NAy8FXE4mFKnoVXlGotg1"
}

# Gửi yêu cầu POST
response = requests.post(url, headers=headers, cookies=cookies, data=data)

# Kiểm tra xem yêu cầu có thành công không
if response.status_code == 200:
    """
     python test_receipt_fetcher.py
        Phản hồi: {"code":1,"isBefore":0,"Des":"SUCCESS!",
        "DANHSACH":[
            {"Id":8731248,"NgayBienLai":"\/Date(1740966318867)\/","MauBienLai":"01BLP0-001","KiHieu":"VC-21E","SoBienLai":4656688,"TrangThai":1,"TrangThaiEinvoice":1,"TongTien":41352.00000,"InvoiceKey":"c64d0633-9f16-45e7-9190-bae7d43c8678","MaTraCuu":"STIND9TY76","SoTK":"106980540920","NgayTK":"\/Date(1740762000000)\/","MaLH":"E21","NhomLH":"TF003"}]
            ,"COUNT":1,"COUNT_PAGE":1}
    """
    print("Phản hồi:", response.text)
else:
    print(f"Yêu cầu thất bại với mã trạng thái {response.status_code}")


