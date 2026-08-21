from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import TransactionType, TransactionStatus


class TransactionCreate(BaseModel):
    amount: float = Field(gt=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=255)
    screenshot_data: str | None = None
    account_name: str | None = Field(default=None, max_length=120)
    wallet_address: str | None = Field(default=None, max_length=255)
    network: str | None = Field(default=None, max_length=50)


class TransactionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    type: TransactionType
    status: TransactionStatus
    amount: float
    note: str | None
    screenshot_data: str | None
    account_name: str | None
    wallet_address: str | None
    network: str | None
    created_at: datetime
    resolved_at: datetime | None


class TransactionResolve(BaseModel):
    status: TransactionStatus  # approved or rejected
