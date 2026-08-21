from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: Optional[str] = Field(None, alias="_id")
    hashed_password: str
    is_active: bool = True
    is_admin: bool = False
    balance: float = 0.0
    basic_funded_balance: float = 0.0
    pro_funded_balance: float = 0.0
    purchased_bot_ids: list[str] = []
    referral_code: str
    referred_by_id: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    password_reset_otp: Optional[str] = None
    password_reset_expires_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


# MongoDB document representation
class UserDocument(dict):
    """Helper to create user documents for MongoDB"""
    
    @staticmethod
    def from_model(user: User, hashed_password: str) -> dict:
        doc = {
            "email": user.email,
            "full_name": user.full_name,
            "hashed_password": hashed_password,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "balance": user.balance,
            "basic_funded_balance": user.basic_funded_balance,
            "pro_funded_balance": user.pro_funded_balance,
            "purchased_bot_ids": user.purchased_bot_ids,
            "referral_code": user.referral_code,
            "referred_by_id": user.referred_by_id,
            "created_at": _utcnow(),
            "password_reset_otp": user.password_reset_otp,
            "password_reset_expires_at": user.password_reset_expires_at,
        }
        return doc
