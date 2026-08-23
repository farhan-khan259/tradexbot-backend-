from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ManualSide = Literal["BUY", "SELL"]


class ManualPositionCreate(BaseModel):
    pair: str = Field(min_length=3, max_length=30)
    side: ManualSide
    amount: float = Field(gt=0, le=1_000_000)
    duration: int = Field(gt=0, le=86_400)
    timeframe: str = Field(default="5m", pattern="^(1m|5m|15m|30m|1h|4h|1d)$")
    entry_price: float = Field(gt=0)


class ManualPositionResponse(BaseModel):
    id: str
    pair: str
    side: ManualSide
    amount: float
    entry_price: float
    status: Literal["open", "closed", "cancelled"]
    source: Literal["MANUAL"]
    timeframe: str
    opened_at: datetime
    expires_at: datetime
    closed_at: datetime | None = None
    win: bool | None = None
    profit_loss: float = 0
    balance: float | None = None


class ManualPositionListResponse(BaseModel):
    items: list[ManualPositionResponse]
    balance: float
