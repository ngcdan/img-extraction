import json

import pytest

from customs_bot.features.auth.account_pool import AccountPool, NoAccountsAvailable
from customs_bot.shared.models import Account


@pytest.fixture
def accounts_file(tmp_path):
    p = tmp_path / "accounts.json"
    p.write_text(
        json.dumps(
            [
                {"username": "u1", "password": "p1"},
                {"username": "u2", "password": "p2"},
                {"username": "u3", "password": "p3"},
            ]
        )
    )
    return p


def test_load_returns_pool(accounts_file):
    pool = AccountPool.load(accounts_file)
    assert len(pool) == 3


def test_current_returns_first(accounts_file):
    pool = AccountPool.load(accounts_file)
    acc = pool.current()
    assert isinstance(acc, Account)
    assert acc.username == "u1"


def test_rotate_advances(accounts_file):
    pool = AccountPool.load(accounts_file)
    assert pool.current().username == "u1"
    pool.rotate()
    assert pool.current().username == "u2"
    pool.rotate()
    assert pool.current().username == "u3"


def test_rotate_exhausted_raises(accounts_file):
    pool = AccountPool.load(accounts_file)
    pool.rotate()
    pool.rotate()
    with pytest.raises(NoAccountsAvailable):
        pool.rotate()


def test_load_empty_raises(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("[]")
    with pytest.raises(NoAccountsAvailable):
        AccountPool.load(p)


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        AccountPool.load(tmp_path / "nope.json")
