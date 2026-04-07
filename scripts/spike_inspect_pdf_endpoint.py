"""Spike: điều tra HoaDonViewer.aspx có direct PDF endpoint hay không.

CÁCH CHẠY (cần login thủ công 1 lần):

1. Đảm bảo Chrome đã đóng hết, sau đó mở Chrome debug:
       /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
           --remote-debugging-port=9222 \\
           --user-data-dir=$HOME/chrome-debug-profile

2. Trong cửa sổ Chrome debug đó, tự login vào https://thuphi.haiphong.gov.vn
   (nhập username/password/captcha bằng tay).

3. Chuẩn bị 1 mã `mhd` (drive_link) thật từ kết quả API beelogistics — bạn có
   thể lấy bằng cách chạy `python custom_api_client.py` với customs_number thật,
   hoặc copy từ log run trước.

4. Chạy: source env/bin/activate && python scripts/spike_inspect_pdf_endpoint.py <MHD>

5. Script sẽ:
   - Attach vào Chrome debug
   - Bật Network domain qua CDP
   - Mở HoaDonViewer.aspx?mhd=<MHD>
   - Log MỌI request + response, đặc biệt highlight content-type application/pdf
   - Dump UA, cookies, headers ra spike_output.json

6. Đọc spike_output.json để biết:
   - Có direct PDF URL không
   - Cookies + headers cần copy sang httpx
   - URL pattern (.aspx?, ?mhd=, GetPDF.aspx, ...)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

OUTPUT = Path("spike_output.json")
DEBUG_PORT = 9222


def attach_to_existing_chrome() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    return webdriver.Chrome(options=options)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/spike_inspect_pdf_endpoint.py <MHD>")
        print("       (MHD = drive_link value from beelogistics API response)")
        return 2

    mhd = sys.argv[1]
    target_url = f"http://thuphi.haiphong.gov.vn:8224/Viewer/HoaDonViewer.aspx?mhd={mhd}"
    print(f"[spike] target: {target_url}")

    driver = attach_to_existing_chrome()
    print(f"[spike] attached to Chrome on :{DEBUG_PORT}")

    # Bật Network domain qua CDP để capture requests/responses
    driver.execute_cdp_cmd("Network.enable", {})

    captured_requests: dict[str, dict] = {}
    captured_responses: dict[str, dict] = {}
    pdf_responses: list[dict] = []

    # Mở tab mới và navigate
    original_window = driver.current_window_handle
    driver.execute_script(f"window.open('{target_url}', '_blank');")
    time.sleep(1)
    new_handle = [h for h in driver.window_handles if h != original_window][-1]
    driver.switch_to.window(new_handle)

    # Đợi trang load + một chút buffer cho async requests
    print("[spike] waiting 15s for page + async requests...")
    time.sleep(15)

    # Lấy performance log entries (bao gồm Network events)
    logs = driver.get_log("performance") if "performance" in [
        log["type"] for log in driver.execute("getAvailableLogTypes", {})["value"]
    ] else []

    # Selenium 4 với CDP: thay vào đó dùng CDPSession-style polling
    # Cách đơn giản hơn: dùng JS Performance API để liệt kê resources
    resources = driver.execute_script("""
        return performance.getEntriesByType('resource').map(e => ({
            name: e.name,
            initiatorType: e.initiatorType,
            transferSize: e.transferSize,
            duration: e.duration,
        }));
    """)

    # Lấy cookies hiện tại + UA
    cookies = driver.get_cookies()
    user_agent = driver.execute_script("return navigator.userAgent;")

    # Tải từng resource bằng fetch trong context trang để xem content-type
    pdf_candidates = []
    for r in resources:
        url = r["name"]
        if not url.startswith("http"):
            continue
        try:
            ct = driver.execute_script(
                """
                const url = arguments[0];
                return fetch(url, {credentials: 'include', method: 'HEAD'})
                    .then(r => r.headers.get('content-type') || '')
                    .catch(e => 'ERROR:' + e.message);
                """,
                url,
            )
        except Exception as e:
            ct = f"EXC:{e}"
        r["content_type"] = ct
        if ct and "pdf" in ct.lower():
            pdf_candidates.append(r)
            print(f"[spike] PDF FOUND: {url} (content-type={ct})")

    output = {
        "target_url": target_url,
        "mhd": mhd,
        "user_agent": user_agent,
        "cookies": cookies,
        "all_resources": resources,
        "pdf_candidates": pdf_candidates,
        "summary": {
            "total_resources": len(resources),
            "pdf_resources_found": len(pdf_candidates),
            "verdict": "DIRECT_PDF_ENDPOINT_EXISTS"
            if pdf_candidates
            else "NO_DIRECT_PDF_ENDPOINT_FOUND",
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str))
    print(f"[spike] wrote {OUTPUT}")
    print(f"[spike] verdict: {output['summary']['verdict']}")
    print(f"[spike] pdf candidates: {len(pdf_candidates)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
