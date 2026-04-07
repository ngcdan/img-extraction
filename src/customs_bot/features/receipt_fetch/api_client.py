"""HTTP client tra cứu biên lai qua API Beelogistics."""

from __future__ import annotations

import os
from typing import Any

import httpx
from loguru import logger

from customs_bot.shared.models import ReceiptSearchResult

DEFAULT_BASE_URL = "https://beelogistics.cloud/api"
RESOURCE_ENDPOINT = "/resource"
RESOURCE_NAME = "resource:custom-ie-api"
DEFAULT_TIMEOUT = 30.0


class BeelogisticsApiError(Exception):
    """Lỗi khi gọi API Beelogistics."""


class BeelogisticsApiClient:
    """Client httpx cho API tra cứu biên lai Beelogistics."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
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
    def from_env(cls) -> BeelogisticsApiClient:
        api_key = os.environ.get("DATATP_API_KEY")
        if not api_key:
            raise RuntimeError(
                "DATATP_API_KEY chưa được cấu hình trong environment variables"
            )
        return cls(api_key=api_key)

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> BeelogisticsApiClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "DataTP-Authorization": self.api_key,
        }

    def search(self, customs_numbers: list[str]) -> list[ReceiptSearchResult]:
        """Gửi danh sách số tờ khai, trả về danh sách kết quả đã typed."""
        url = f"{self.base_url}{RESOURCE_ENDPOINT}"
        body = {
            "resourceName": RESOURCE_NAME,
            "customsNumbers": customs_numbers,
        }
        try:
            response = self._http.post(
                url, json=body, headers=self._headers(), timeout=self.timeout
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise BeelogisticsApiError(
                f"API trả về status {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise BeelogisticsApiError(f"Lỗi HTTP khi gọi API: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise BeelogisticsApiError(f"Response không phải JSON hợp lệ: {exc}") from exc

        return _parse_records(payload)


def _parse_records(payload: Any) -> list[ReceiptSearchResult]:
    if not isinstance(payload, dict):
        logger.warning("Payload API không phải dict, bỏ qua")
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        logger.warning("Thiếu field 'data' trong response API")
        return []
    result = data.get("result")
    if not isinstance(result, dict):
        logger.warning("Thiếu field 'result' trong data")
        return []
    records = result.get("records") or []
    if not isinstance(records, list):
        logger.warning("Field 'records' không phải list")
        return []

    parsed: list[ReceiptSearchResult] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        mhd = record.get("drive_link") or ""
        customs_no = record.get("customs_no") or ""
        if not mhd or not customs_no:
            logger.warning(
                "Bỏ qua record thiếu drive_link/customs_no: customs_no={}", customs_no or "?"
            )
            continue
        parsed.append(
            ReceiptSearchResult(
                customs_number=str(customs_no),
                mhd=str(mhd),
                trans_id=_opt_str(record.get("TransID")),
                hawb=_opt_str(record.get("hawb")),
                partner_name=_opt_str(record.get("PartnerName3")),
                raw=record,
            )
        )
    return parsed


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value)
    return s if s else None
