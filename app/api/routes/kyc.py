from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.database import Database

from app.api.deps import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/kyc", tags=["kyc"])


class KYCSubmission(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    date_of_birth: str = Field(min_length=8, max_length=20)
    country: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=5, max_length=300)
    id_type: str = Field(min_length=2, max_length=50)
    id_number: str = Field(min_length=3, max_length=100)
    identity_document: str = Field(min_length=20, max_length=10_000_000)
    proof_of_address: str = Field(min_length=20, max_length=10_000_000)
    selfie_document: str | None = Field(default=None, max_length=10_000_000)


@router.get("")
def get_kyc(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    submission = db.kyc.find_one({"user_id": str(user["_id"])}, {"identity_document": 0, "proof_of_address": 0, "selfie_document": 0})
    if not submission:
        return {"status": "not_verified"}
    return {"status": submission.get("status", "not_verified")}


@router.post("")
def submit_kyc(payload: KYCSubmission, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    existing = db.kyc.find_one({"user_id": str(user["_id"])})
    if existing and existing.get("status") == "pending":
        raise HTTPException(status_code=409, detail="A KYC submission is already pending review")
    now = datetime.now(timezone.utc)
    doc = payload.model_dump()
    doc.update({"user_id": str(user["_id"]), "status": "pending", "review_notes": None, "created_at": now, "updated_at": now})
    db.kyc.replace_one({"user_id": str(user["_id"])}, doc, upsert=True)
    return {"status": "pending", "message": "KYC submitted for review"}