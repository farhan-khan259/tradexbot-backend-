from datetime import datetime

from pydantic import BaseModel


class TradePublic(BaseModel):
    id: str
    pair: str
    side: str
    quantity: float | None = None
    amount: float
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    profit_loss: float
    status: str
    source: str
    opened_at: datetime