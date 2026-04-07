"""Pydantic models shared across features."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Account(BaseModel):
    """Tài khoản đăng nhập cổng thuế."""

    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class Invoice(BaseModel):
    """Header tờ khai parsed từ PDF đầu vào."""

    customs_number: str = Field(min_length=1)
    registration_date: date
    company_name: str
    tax_code: str
    source_file: str
    total_amount: float | None = None


class ReceiptStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class Receipt(BaseModel):
    """Biên lai trả về sau khi gọi API + download."""

    mhd: str = Field(min_length=1)
    customs_number: str
    status: ReceiptStatus
    saved_path: str | None = None
    fetched_at: datetime
    error: str | None = None


class BatchResult(BaseModel):
    """Tổng hợp kết quả 1 batch xử lý."""

    total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_sum(self) -> BatchResult:
        if self.succeeded + self.failed + self.skipped != self.total:
            raise ValueError("succeeded + failed + skipped must equal total")
        return self
