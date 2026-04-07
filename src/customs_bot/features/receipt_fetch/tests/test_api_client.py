"""Tests cho FmsApiClient.

TODO: Mở rộng tests khi implement search() — verify request format, response
parsing, error handling. Hiện tại chỉ test stub behavior + env loading.
"""

from __future__ import annotations

import pytest

from customs_bot.features.receipt_fetch.api_client import FmsApiClient


def test_constructor_rejects_empty_api_key():
    with pytest.raises(ValueError):
        FmsApiClient(api_key="")


def test_constructor_strips_trailing_slash_from_base_url():
    client = FmsApiClient(api_key="k", base_url="https://fms.example.com/api/")
    assert client.base_url == "https://fms.example.com/api"


def test_search_raises_not_implemented():
    client = FmsApiClient(api_key="k")
    with pytest.raises(NotImplementedError):
        client.search(["12345"])


def test_from_env_reads_api_key(monkeypatch):
    monkeypatch.setenv("FMS_API_KEY", "env-key-123")
    monkeypatch.delenv("FMS_API_BASE_URL", raising=False)
    client = FmsApiClient.from_env()
    assert client.api_key == "env-key-123"
    assert client.base_url == ""


def test_from_env_reads_base_url(monkeypatch):
    monkeypatch.setenv("FMS_API_KEY", "k")
    monkeypatch.setenv("FMS_API_BASE_URL", "https://fms.example.com/api")
    client = FmsApiClient.from_env()
    assert client.base_url == "https://fms.example.com/api"


def test_from_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("FMS_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        FmsApiClient.from_env()


def test_context_manager_closes_owned_client():
    with FmsApiClient(api_key="k") as client:
        assert client.api_key == "k"
