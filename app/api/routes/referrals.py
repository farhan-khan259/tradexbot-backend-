from pydantic import BaseModel
from fastapi import APIRouter, Depends
from pymongo.database import Database
from bson import ObjectId

from app.api.deps import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/referrals", tags=["referrals"])


class ReferredUser(BaseModel):
    full_name: str
    email: str
    bonus_amount: float


class ReferralSummary(BaseModel):
    referral_code: str
    total_referrals: int
    total_bonus: float
    referred_users: list[ReferredUser]


@router.get("", response_model=ReferralSummary)
def my_referrals(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    referrals_collection = db.referrals
    users_collection = db.users
    
    # Find all referrals where current user is the referrer
    referral_docs = list(referrals_collection.find({"referrer_id": str(user["_id"])}))
    
    referred = []
    for ref_doc in referral_docs:
        referred_user = users_collection.find_one({"_id": ObjectId(ref_doc["referred_id"])})
        if referred_user:
            referred.append(
                ReferredUser(
                    full_name=referred_user.get("full_name", ""),
                    email=referred_user.get("email", ""),
                    bonus_amount=float(ref_doc.get("bonus_amount", 0))
                )
            )
    
    return ReferralSummary(
        referral_code=user.get("referral_code", ""),
        total_referrals=len(referred),
        total_bonus=sum(x.bonus_amount for x in referred),
        referred_users=referred,
    )
