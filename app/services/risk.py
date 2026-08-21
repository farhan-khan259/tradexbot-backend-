class RiskValidationError(ValueError):
    pass


def validate_trade_risk(
    side: str,
    quantity: float,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    balance: float,
    leverage: float,
    max_risk_fraction: float,
    max_position_fraction: float,
    max_leverage: float,
) -> dict:
    normalized_side = side.upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise RiskValidationError("Invalid order side")
    if quantity <= 0 or entry_price <= 0:
        raise RiskValidationError("Quantity and entry price must be greater than zero")
    if balance <= 0:
        raise RiskValidationError("Insufficient balance")
    if leverage <= 0 or leverage > max_leverage:
        raise RiskValidationError(f"Leverage cannot exceed {max_leverage:g}x")
    if normalized_side == "BUY" and not (stop_loss < entry_price < take_profit):
        raise RiskValidationError("For BUY orders, stop-loss must be below entry and take-profit above entry")
    if normalized_side == "SELL" and not (take_profit < entry_price < stop_loss):
        raise RiskValidationError("For SELL orders, take-profit must be below entry and stop-loss above entry")

    notional = quantity * entry_price / leverage
    risk_amount = quantity * abs(entry_price - stop_loss)
    if notional > balance * max_position_fraction:
        raise RiskValidationError("Maximum position size exceeded")
    if risk_amount > balance * max_risk_fraction:
        raise RiskValidationError("Risk limit exceeded for this trade")
    reward_amount = quantity * abs(take_profit - entry_price)
    return {
        "notional": round(notional, 8),
        "risk_amount": round(risk_amount, 8),
        "reward_amount": round(reward_amount, 8),
        "risk_reward_ratio": round(reward_amount / risk_amount, 4) if risk_amount else 0,
    }