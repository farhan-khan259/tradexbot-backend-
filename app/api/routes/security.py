from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.database import Database

from app.api.deps import get_current_user
from app.core.database import get_db
from app.services.totp import decrypt_secret, encrypt_secret, new_secret, provisioning_uri, verify

router = APIRouter(prefix="/auth/2fa", tags=["security"])


class TwoFactorCode(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


@router.get("/status")
def status(user: dict = Depends(get_current_user)):
    return {"enabled": bool(user.get("two_factor_enabled", False))}


@router.post("/setup")
def setup(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    if user.get("two_factor_enabled"):
        raise HTTPException(status_code=400, detail="Two-factor authentication is already enabled")
    secret = new_secret()
    db.users.update_one({"_id": user["_id"]}, {"$set": {"two_factor_pending_secret": encrypt_secret(secret)}})
    return {"provisioning_uri": provisioning_uri(secret, user["email"])}


@router.post("/verify")
def enable(payload: TwoFactorCode, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    encrypted = user.get("two_factor_pending_secret")
    if not encrypted or not verify(decrypt_secret(encrypted), payload.code):
        raise HTTPException(status_code=400, detail="Invalid two-factor code")
    backup_codes = [f"{new_secret()[:4]}-{new_secret()[:4]}" for _ in range(8)]
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"two_factor_enabled": True, "two_factor_secret": encrypted, "two_factor_backup_codes": backup_codes}, "$unset": {"two_factor_pending_secret": ""}},
    )
    return {"enabled": True, "backup_codes": backup_codes}


@router.post("/disable")
def disable(payload: TwoFactorCode, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    encrypted = user.get("two_factor_secret")
    totp_valid = bool(encrypted and verify(decrypt_secret(encrypted), payload.code))
    backup_valid = payload.code in user.get("two_factor_backup_codes", [])
    if not user.get("two_factor_enabled") or not totp_valid and not backup_valid:
        raise HTTPException(status_code=400, detail="Invalid two-factor code")
    db.users.update_one({"_id": user["_id"]}, {"$set": {"two_factor_enabled": False}, "$unset": {"two_factor_secret": "", "two_factor_backup_codes": ""}})
    return {"enabled": False}