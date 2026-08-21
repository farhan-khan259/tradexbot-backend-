from pydantic import BaseModel, Field


class BotPurchaseRequest(BaseModel):
    bot_id: str = Field(pattern="^(basic-funded|pro-funded|basic-bot|pro-bot)$")


class BotPurchaseResponse(BaseModel):
    bot_id: str
    balance: float
    purchased_bot_ids: list[str]
    funded_credit: float = 0
    funded_balance: float = 0


class BotTradeRequest(BaseModel):
    pair: str = Field(min_length=3, max_length=50)
    amount: float = Field(gt=0, le=1_000_000)
    phase: str = Field(default="start")
    # Duration in seconds for a trade session (used to restore after reload)
    duration: int = Field(default=60, gt=0)
    account_type: str = Field(default="wallet", pattern="^(wallet|basic-funded|pro-funded)$")


class BotTradeResponse(BaseModel):
    pair: str
    side: str
    amount: float
    win: bool
    delta: float
    balance: float
    message: str | None = None
