import unittest
from unittest.mock import patch

from app.services.risk import validate_trade_risk
from app.services.totp import code, new_secret, verify


class RiskValidationTests(unittest.TestCase):
    def valid(self, **overrides):
        values = {
            "side": "BUY",
            "quantity": 0.001,
            "entry_price": 100_000,
            "stop_loss": 99_000,
            "take_profit": 102_000,
            "balance": 10_000,
            "leverage": 1,
            "max_risk_fraction": 0.01,
            "max_position_fraction": 0.25,
            "max_leverage": 3,
        }
        values.update(overrides)
        return validate_trade_risk(**values)

    def test_buy_levels_and_risk_are_validated(self):
        result = self.valid()
        self.assertEqual(result["risk_amount"], 1.0)
        self.assertGreater(result["risk_reward_ratio"], 1)

    def test_sell_levels_must_be_reversed(self):
        with self.assertRaises(Exception):
            self.valid(side="SELL")

    def test_risk_limit_rejects_large_position(self):
        with self.assertRaises(Exception):
            self.valid(quantity=0.2)


class TotpTests(unittest.TestCase):
    def test_current_code_verifies(self):
        secret = new_secret()
        with patch("app.services.totp.time.time", return_value=1_700_000_000):
            token = code(secret)
            self.assertTrue(verify(secret, token))
            self.assertFalse(verify(secret, "000000"))


if __name__ == "__main__":
    unittest.main()