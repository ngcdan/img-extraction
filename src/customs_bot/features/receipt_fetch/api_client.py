"""HTTP client tra cứu biên lai qua FMS API.

TODO: Implement FmsApiClient — chờ thông tin chi tiết về FMS API:
    - Endpoint URL (base URL + path)
    - Auth method (API key header / Bearer token / Basic auth / ...)
    - Request format: HTTP method, payload shape (input là customs_numbers?)
    - Response format: field nào chứa mhd (drive_link)?
    - Error semantics: status codes, error envelope shape

Khi có thông tin trên, implement theo pattern Protocol-based để testable
qua respx mock (xem `tests/test_api_client.py`).
"""

from __future__ import annotations

import os

import httpx

from customs_bot.shared.models import ReceiptSearchResult

DEFAULT_TIMEOUT = 30.0


class FmsApiError(Exception):
    """Lỗi khi gọi FMS API."""


class FmsApiClient:
    """Client httpx cho FMS API tra cứu biên lai.

    TODO: Thay stub này bằng implementation thật khi có spec FMS API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key không được rỗng")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._http = http_client or httpx.Client(timeout=timeout)
        self._owns_client = http_client is None

    @classmethod
    def from_env(cls) -> FmsApiClient:
        """Đọc FMS_API_KEY (và optional FMS_API_BASE_URL) từ environment."""
        api_key = os.environ.get("FMS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "FMS_API_KEY chưa được cấu hình trong environment variables"
            )
        base_url = os.environ.get("FMS_API_BASE_URL", "")
        return cls(api_key=api_key, base_url=base_url)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> FmsApiClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def search(self, customs_numbers: list[str]) -> list[ReceiptSearchResult]:
        """Gửi danh sách số tờ khai, trả về danh sách kết quả đã typed.

        TODO: Implement HTTP call sau khi xác nhận FMS API spec:
            - URL: f"{self.base_url}/<endpoint>"
            - Method: GET hoặc POST
            - Headers: tự động thêm auth (API key / Bearer)
            - Body: payload shape phụ thuộc API (vd {"customs_numbers": [...]})
            - Parse response → list[ReceiptSearchResult]
            - Error handling: raise FmsApiError trên HTTP error / parse fail
        """
        raise NotImplementedError(
            "FmsApiClient.search chưa implement — chờ spec FMS API "
            "(endpoint, auth, request/response shape)"
        )
