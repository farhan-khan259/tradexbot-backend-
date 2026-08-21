import random
from typing import List


def generate_balanced_outcomes(total_trades: int = 10, wins: int = 5, losses: int = 5) -> List[str]:
    """Return a random outcome sequence with exact win/loss totals and balanced prefixes."""
    if total_trades != wins + losses:
        raise ValueError("total_trades must match wins + losses")

    outcomes: List[str] = []
    wins_remaining = wins
    losses_remaining = losses
    wins_so_far = 0
    losses_so_far = 0

    while len(outcomes) < total_trades:
        choices: List[str] = []

        if wins_remaining > 0 and wins_so_far - losses_so_far < 1:
            choices.append("W")
        if losses_remaining > 0 and losses_so_far - wins_so_far < 1:
            choices.append("L")

        if not choices:
            break

        outcome = random.choice(choices)
        outcomes.append(outcome)

        if outcome == "W":
            wins_so_far += 1
            wins_remaining -= 1
        else:
            losses_so_far += 1
            losses_remaining -= 1

    if len(outcomes) != total_trades:
        raise RuntimeError("Unable to build a balanced outcome sequence")

    return outcomes


def generate_random_win_rate_outcomes(wins: int, total_trades: int = 10) -> List[str]:
    """Return a randomized trade block with an exact number of wins."""
    if wins < 0 or wins > total_trades:
        raise ValueError("wins must be between zero and total_trades")
    return random.sample(["W"] * wins + ["L"] * (total_trades - wins), total_trades)
