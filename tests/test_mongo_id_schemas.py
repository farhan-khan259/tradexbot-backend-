from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.user import UserPublic
from app.schemas.transaction import TransactionPublic


def test_user_public_accepts_mongo_object_id_string():
    payload = {
        "id": "507f1f77bcf86cd799439011",
        "email": "user@example.com",
        "full_name": "Test User",
        "is_active": True,
        "is_admin": False,
        "balance": 25.5,
        "referral_code": "ABC123",
        "created_at": datetime.now(timezone.utc),
    }

    user = UserPublic.model_validate(payload)
    assert user.id == "507f1f77bcf86cd799439011"


def test_transaction_public_accepts_mongo_object_id_string():
    payload = {
        "id": "507f1f77bcf86cd799439012",
        "user_id": "507f1f77bcf86cd799439013",
        "type": "deposit",
        "status": "pending",
        "amount": 100.0,
        "note": "Test deposit",
        "screenshot_data": None,
        "account_name": None,
        "wallet_address": None,
        "network": None,
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
    }

    tx = TransactionPublic.model_validate(payload)
    assert tx.id == "507f1f77bcf86cd799439012"
    assert tx.user_id == "507f1f77bcf86cd799439013"
