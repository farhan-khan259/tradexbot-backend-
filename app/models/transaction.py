import enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TransactionType(str, enum.Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    referral_bonus = "referral_bonus"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Transaction(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    type: TransactionType
    status: TransactionStatus = TransactionStatus.pending
    amount: float
    note: Optional[str] = None
    screenshot_data: Optional[str] = None
    account_name: Optional[str] = None
    wallet_address: Optional[str] = None
    network: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


# MongoDB document helper
class TransactionDocument(dict):
    @staticmethod
    def from_model(tx: Transaction) -> dict:
        return {
            "user_id": tx.user_id,
            "type": tx.type.value,
            "status": tx.status.value,
            "amount": tx.amount,
            "note": tx.note,
            "screenshot_data": tx.screenshot_data,
            "account_name": tx.account_name,
            "wallet_address": tx.wallet_address,
            "network": tx.network,
            "created_at": _utcnow(),
            "resolved_at": tx.resolved_at,
        }
