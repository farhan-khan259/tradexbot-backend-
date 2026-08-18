from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Referral(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    referrer_id: str
    referred_id: str
    bonus_amount: float = 0.0
    created_at: datetime = Field(default_factory=_utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


# MongoDB document helper
class ReferralDocument(dict):
    @staticmethod
    def from_model(referral: Referral) -> dict:
        return {
            "referrer_id": referral.referrer_id,
            "referred_id": referral.referred_id,
            "bonus_amount": referral.bonus_amount,
            "created_at": _utcnow(),
        }
