import secrets
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.database import Database

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    RegisterRequest,
    ResetPasswordRequest,
    Token,
)
from app.schemas.user import UserPublic
from app.services.referral import generate_referral_code
from app.services.mail import send_password_reset_otp_email
from app.services.totp import decrypt_secret, verify as verify_totp

router = APIRouter(prefix="/auth", tags=["auth"])


def _utc_now_matching(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def _user_doc_to_response(doc: dict) -> dict:
    """Convert MongoDB document to response format"""
    if doc is None:
        return None
    doc["id"] = str(doc.get("_id", ""))
    return doc


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Database = Depends(get_db)):
    users_collection = db.users
    
    # Check if email already exists
    if users_collection.find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    referrer = None
    if payload.referral_code:
        referrer = users_collection.find_one({"referral_code": payload.referral_code})
        if not referrer:
            raise HTTPException(status_code=400, detail="Invalid referral code")

    user_doc = {
        "email": payload.email,
        "full_name": payload.full_name,
        "hashed_password": hash_password(payload.password),
        "is_active": True,
        "is_admin": False,
        "balance": 0.0,
        "basic_funded_balance": 0.0,
        "pro_funded_balance": 0.0,
        "purchased_bot_ids": [],
        "referral_code": generate_referral_code(db),
        "referred_by_id": str(referrer["_id"]) if referrer else None,
        "created_at": datetime.now(timezone.utc),
        "password_reset_otp": None,
        "password_reset_expires_at": None,
    }
    
    result = users_collection.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    return _user_doc_to_response(user_doc)


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), two_factor_code: str | None = None, db: Database = Depends(get_db)):
    users_collection = db.users
    user = users_collection.find_one({"email": form.username})
    
    if not user or not verify_password(form.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.get("is_active", False):
        raise HTTPException(status_code=403, detail="Account disabled")
    if user.get("two_factor_enabled"):
        encrypted = user.get("two_factor_secret")
        totp_valid = bool(encrypted and two_factor_code and verify_totp(decrypt_secret(encrypted), two_factor_code))
        backup_valid = bool(two_factor_code and two_factor_code in user.get("two_factor_backup_codes", []))
        if not totp_valid and not backup_valid:
            raise HTTPException(status_code=401, detail="Two-factor authentication code required or invalid")
        if backup_valid:
            users_collection.update_one({"_id": user["_id"]}, {"$pull": {"two_factor_backup_codes": two_factor_code}})
    
    return Token(access_token=create_access_token(str(user["_id"])))


@router.get("/me", response_model=UserPublic)
def me(user: dict = Depends(get_current_user)):
    return _user_doc_to_response(user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Database = Depends(get_db)):
    users_collection = db.users
    user = users_collection.find_one({"email": payload.email})
    
    generic = "If an account exists for that email, a password reset OTP has been sent."
    if not user:
        return ForgotPasswordResponse(message=generic)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_reset_otp": otp,
                "password_reset_expires_at": datetime.now(timezone.utc) + timedelta(
                    minutes=settings.PASSWORD_RESET_OTP_EXPIRE_MINUTES
                ),
            }
        },
    )

    try:
        send_password_reset_otp_email(user["email"], otp)
    except Exception:
        pass

    return ForgotPasswordResponse(
        message=generic,
        otp=otp if settings.EXPOSE_FORGOT_PASSWORD_OTP else None,
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: Database = Depends(get_db)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Password and confirm password do not match")

    users_collection = db.users
    user = users_collection.find_one({"email": payload.email})
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or OTP")

    if not user.get("password_reset_otp") or not user.get("password_reset_expires_at"):
        raise HTTPException(status_code=400, detail="No password reset request found")
    if user.get("password_reset_otp") != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid email or OTP")
    if user.get("password_reset_expires_at") < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP has expired")

    users_collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "hashed_password": hash_password(payload.new_password),
                "password_reset_otp": None,
                "password_reset_expires_at": None,
            }
        },
    )
