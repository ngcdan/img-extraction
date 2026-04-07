"""Application settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for customs_bot."""

    model_config = SettingsConfigDict(
        env_prefix="CUSTOMS_BOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(
        default_factory=lambda: Path.home() / "Desktop" / "customs",
        description="Thư mục chứa PDF tờ khai đầu vào",
    )
    log_level: str = Field(default="INFO", description="Loguru log level")
    accounts_file: Path = Field(default=Path("accounts.json"))
    service_account_file: Path = Field(default=Path("driver-service-account.json"))
    cookie_store: Path = Field(
        default_factory=lambda: Path.home() / ".customs_bot" / "cookies.json"
    )
