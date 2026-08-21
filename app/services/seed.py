from pymongo.database import Database

from app.core.config import settings
from app.core.security import hash_password
from app.services.referral import generate_referral_code


def seed_admin(db: Database) -> None:
    """Ensure the configured TradeXBot admin account exists and matches the expected credentials."""
    users_collection = db.users

    admin_email = settings.FIRST_ADMIN_EMAIL.strip().lower()
    admin_password_hash = hash_password(settings.FIRST_ADMIN_PASSWORD)
    admin_doc = {
        "email": admin_email,
        "full_name": "TradeXBot Admin",
        "hashed_password": admin_password_hash,
        "is_admin": True,
        "is_active": True,
        "balance": 0.0,
        "basic_funded_balance": 0.0,
        "pro_funded_balance": 0.0,
        "purchased_bot_ids": [],
        "referral_code": generate_referral_code(db),
        "referred_by_id": None,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "password_reset_otp": None,
        "password_reset_expires_at": None,
    }

    existing_admin = users_collection.find_one({"is_admin": True})
    if existing_admin and existing_admin.get("email", "").lower() == admin_email:
        users_collection.update_one(
            {"_id": existing_admin["_id"]},
            {"$set": {
                "full_name": "TradeXBot Admin",
                "hashed_password": admin_password_hash,
                "is_admin": True,
                "is_active": True,
                "balance": 0.0,
                "basic_funded_balance": 0.0,
                "pro_funded_balance": 0.0,
                "purchased_bot_ids": [],
                "password_reset_otp": None,
                "password_reset_expires_at": None,
            }}
        )
        return

    if existing_admin:
        users_collection.update_one(
            {"_id": existing_admin["_id"]},
            {"$set": {
                "email": admin_email,
                "full_name": "TradeXBot Admin",
                "hashed_password": admin_password_hash,
                "is_admin": True,
                "is_active": True,
                "balance": 0.0,
                "basic_funded_balance": 0.0,
                "pro_funded_balance": 0.0,
                "purchased_bot_ids": [],
                "password_reset_otp": None,
                "password_reset_expires_at": None,
            }}
        )
        return

    existing_user = users_collection.find_one({"email": admin_email})
    if existing_user:
        users_collection.update_one(
            {"_id": existing_user["_id"]},
            {"$set": {
                "full_name": "TradeXBot Admin",
                "hashed_password": admin_password_hash,
                "is_admin": True,
                "is_active": True,
                "balance": 0.0,
                "basic_funded_balance": 0.0,
                "pro_funded_balance": 0.0,
                "purchased_bot_ids": [],
                "password_reset_otp": None,
                "password_reset_expires_at": None,
            }}
        )
        return

    users_collection.insert_one(admin_doc)
