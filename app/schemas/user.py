from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    phone: str | None = None
    is_active: bool
    is_admin: bool
    balance: float
    basic_funded_balance: float = 0.0
    pro_funded_balance: float = 0.0
    purchased_bot_ids: list[str] = []
    referral_code: str
    created_at: datetime


class UserAdminView(UserPublic):
    referred_by_id: str | None = None
