import pytest

from customs_bot.cli import _build_parser


def test_build_parser_quiet():
    args = _build_parser().parse_args(["--quiet"])
    assert args.quiet is True


def test_build_parser_data_dir():
    args = _build_parser().parse_args(["--data-dir", "/tmp/foo"])
    assert str(args.data_dir) == "/tmp/foo"


def test_build_parser_defaults():
    args = _build_parser().parse_args([])
    assert args.quiet is False
    assert args.data_dir is None
    assert args.files is None


def test_main_help_exits_zero(capsys):
    from customs_bot.cli import main
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_main_missing_data_dir_returns_2(tmp_path, monkeypatch):
    from customs_bot.cli import main
    monkeypatch.setenv("CUSTOMS_BOT_DATA_DIR", str(tmp_path / "doesnotexist"))
    rc = main([])
    assert rc == 2
