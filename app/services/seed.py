from pymongo.database import Database

from app.core.config import settings
from app.core.security import hash_password
from app.services.referral import generate_referral_code


def seed_admin(db: Database) -> None:
    """Create a default admin account if no users exist yet."""
    users_collection = db.users
    
    # Check if any users exist
    if users_collection.count_documents({}) > 0:
        return
    
    # Create admin user
    admin_doc = {
        "email": settings.FIRST_ADMIN_EMAIL,
        "full_name": "Tradeify Admin",
        "hashed_password": hash_password(settings.FIRST_ADMIN_PASSWORD),
        "is_admin": True,
        "is_active": True,
        "balance": 0.0,
        "purchased_bot_ids": [],
        "referral_code": generate_referral_code(db),
        "referred_by_id": None,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "password_reset_otp": None,
        "password_reset_expires_at": None,
    }
    users_collection.insert_one(admin_doc)
