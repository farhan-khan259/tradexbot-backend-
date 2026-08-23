import unittest

from app.services.outcome_cycle import generate_balanced_outcomes


class ManualTradingOutcomeTests(unittest.TestCase):
    def test_buy_cycle_is_fifty_percent(self) -> None:
        outcomes = generate_balanced_outcomes(10, 5, 5)
        self.assertEqual(outcomes.count("W"), 5)
        self.assertEqual(outcomes.count("L"), 5)

    def test_sell_cycle_is_fifty_percent(self) -> None:
        outcomes = generate_balanced_outcomes(10, 5, 5)
        self.assertEqual(outcomes.count("W"), 5)
        self.assertEqual(outcomes.count("L"), 5)


if __name__ == "__main__":
    unittest.main()
