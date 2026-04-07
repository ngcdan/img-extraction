import os
import time

from customs_bot.features.auth.session import CookieStore


def test_save_and_load_roundtrip(tmp_path):
    store = CookieStore(tmp_path / "cookies.json")
    cookies = [{"name": "ASP.NET_SessionId", "value": "abc123", "domain": "example.com"}]
    store.save(cookies)
    loaded = store.load()
    assert loaded == cookies


def test_load_missing_returns_none(tmp_path):
    store = CookieStore(tmp_path / "missing.json")
    assert store.load() is None


def test_load_corrupt_returns_none(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json")
    store = CookieStore(p)
    assert store.load() is None


def test_is_expired_when_missing(tmp_path):
    store = CookieStore(tmp_path / "missing.json")
    assert store.is_expired() is True


def test_is_expired_fresh(tmp_path):
    store = CookieStore(tmp_path / "fresh.json")
    store.save([{"name": "x", "value": "y"}])
    assert store.is_expired(max_age_hours=24) is False


def test_is_expired_old(tmp_path):
    p = tmp_path / "old.json"
    store = CookieStore(p)
    store.save([{"name": "x", "value": "y"}])
    old_time = time.time() - (10 * 3600)
    os.utime(p, (old_time, old_time))
    assert store.is_expired(max_age_hours=8) is True
    assert store.is_expired(max_age_hours=12) is False


def test_clear(tmp_path):
    store = CookieStore(tmp_path / "c.json")
    store.save([{"name": "x", "value": "y"}])
    store.clear()
    assert store.load() is None
