import secrets
import string

from pymongo.database import Database

_ALPHABET = string.ascii_uppercase + string.digits

# Demo-only bonus credited (in simulated balance) to a referrer once the referred user
# reaches the minimum deposit threshold.
REFERRAL_BONUS = 5.0
MIN_REFERRAL_DEPOSIT = 50.0


def should_credit_referral_bonus(deposit_total: float) -> bool:
    return float(deposit_total) >= MIN_REFERRAL_DEPOSIT


def generate_referral_code(db: Database, length: int = 8) -> str:
    """Generate a unique referral code not already present in the users collection."""
    users_collection = db.users
    for _ in range(20):
        code = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if not users_collection.find_one({"referral_code": code}):
            return code
    raise RuntimeError("Could not generate a unique referral code")
