"""Tests cho BeelogisticsApiClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from customs_bot.features.receipt_fetch.api_client import (
    BeelogisticsApiClient,
    BeelogisticsApiError,
)
from customs_bot.shared.models import ReceiptSearchResult

BASE_URL = "https://beelogistics.cloud/api"
RESOURCE_URL = f"{BASE_URL}/resource"


def _make_client() -> BeelogisticsApiClient:
    http = httpx.Client(base_url=BASE_URL)
    return BeelogisticsApiClient(api_key="test-key", base_url=BASE_URL, http_client=http)


@respx.mock
def test_search_returns_typed_results():
    payload = {
        "data": {
            "result": {
                "records": [
                    {
                        "TransID": "T1",
                        "customs_no": "12345",
                        "hawb": "HAWB1",
                        "PartnerName3": "ACME",
                        "drive_link": "MHD001",
                    },
                    {
                        "TransID": "T2",
                        "customs_no": "67890",
                        "hawb": "HAWB2",
                        "PartnerName3": "BETA",
                        "drive_link": "MHD002",
                    },
                ]
            }
        }
    }
    respx.post(RESOURCE_URL).mock(return_value=httpx.Response(200, json=payload))

    client = _make_client()
    results = client.search(["12345", "67890"])

    assert len(results) == 2
    assert isinstance(results[0], ReceiptSearchResult)
    assert results[0].customs_number == "12345"
    assert results[0].mhd == "MHD001"
    assert results[0].trans_id == "T1"
    assert results[0].hawb == "HAWB1"
    assert results[0].partner_name == "ACME"
    assert results[1].mhd == "MHD002"


@respx.mock
def test_search_skips_records_without_drive_link():
    payload = {
        "data": {
            "result": {
                "records": [
                    {"customs_no": "1", "drive_link": "A"},
                    {"customs_no": "2", "drive_link": ""},
                    {"customs_no": "3", "drive_link": "B"},
                ]
            }
        }
    }
    respx.post(RESOURCE_URL).mock(return_value=httpx.Response(200, json=payload))

    client = _make_client()
    results = client.search(["1", "2", "3"])

    assert len(results) == 2
    assert [r.mhd for r in results] == ["A", "B"]


@respx.mock
def test_search_handles_empty_records():
    payload = {"data": {"result": {"records": []}}}
    respx.post(RESOURCE_URL).mock(return_value=httpx.Response(200, json=payload))

    client = _make_client()
    assert client.search(["1"]) == []


@respx.mock
def test_search_raises_on_http_error():
    respx.post(RESOURCE_URL).mock(return_value=httpx.Response(500, text="boom"))

    client = _make_client()
    with pytest.raises(BeelogisticsApiError):
        client.search(["1"])


@respx.mock
def test_search_raises_on_missing_data_field():
    respx.post(RESOURCE_URL).mock(return_value=httpx.Response(200, json={"status": "OK"}))

    client = _make_client()
    assert client.search(["1"]) == []


def test_from_env_reads_api_key(monkeypatch):
    monkeypatch.setenv("DATATP_API_KEY", "env-key-123")
    client = BeelogisticsApiClient.from_env()
    assert client.api_key == "env-key-123"


def test_from_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("DATATP_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        BeelogisticsApiClient.from_env()
