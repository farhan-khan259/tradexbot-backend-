import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from bson import ObjectId
from fastapi import HTTPException

from app.api.routes.transactions import request_deposit, request_withdrawal
from app.schemas.transaction import TransactionCreate


class DepositScreenshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = SimpleNamespace(
            users=MagicMock(),
            transactions=MagicMock(),
            audit_logs=MagicMock(),
        )

    def test_deposit_requires_screenshot(self) -> None:
        user = {"_id": ObjectId()}
        with self.assertRaises(HTTPException) as ctx:
            request_deposit(
                payload=TransactionCreate(amount=100, note="demo"),
                user=user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_deposit_requires_reference_note(self) -> None:
        user = {"_id": ObjectId()}
        with self.assertRaises(HTTPException) as ctx:
            request_deposit(
                payload=TransactionCreate(amount=100, screenshot_data="data:image/png;base64,abc123"),
                user=user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_deposit_saves_screenshot_per_transaction(self) -> None:
        user = {"_id": ObjectId()}
        payload = TransactionCreate(
            amount=125,
            note="demo",
            screenshot_data="data:image/png;base64,abc123",
        )
        inserted_id = ObjectId()
        self.db.transactions.insert_one.return_value = SimpleNamespace(inserted_id=inserted_id)

        tx = request_deposit(payload=payload, user=user, db=self.db)

        self.db.transactions.insert_one.assert_called_once()
        inserted = self.db.transactions.insert_one.call_args.args[0]
        self.assertEqual(inserted["screenshot_data"], payload.screenshot_data)
        self.assertEqual(inserted["user_id"], str(user["_id"]))
        self.assertEqual(tx["id"], str(inserted_id))

    def test_deposit_requires_at_least_30(self) -> None:
        user = {"_id": ObjectId()}
        with self.assertRaises(HTTPException) as ctx:
            request_deposit(
                payload=TransactionCreate(amount=29, note="demo", screenshot_data="data:image/png;base64,abc123"),
                user=user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_withdrawal_requires_at_least_100(self) -> None:
        user = {"_id": ObjectId(), "balance": 1000.0, "two_factor_enabled": False}
        with self.assertRaises(HTTPException) as ctx:
            request_withdrawal(
                payload=TransactionCreate(amount=99, account_name="Spot", wallet_address="abc", network="TRC20"),
                user=user,
                db=self.db,
            )
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
