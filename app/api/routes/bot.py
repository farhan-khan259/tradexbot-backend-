import random
from typing import List
from datetime import datetime
from pymongo.database import Database

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.bot import BotPurchaseRequest, BotPurchaseResponse, BotTradeRequest, BotTradeResponse
from app.services.trading_engine import trading_engine

router = APIRouter(prefix="/bot", tags=["bot"])

WIN_PROFIT_RATE = 1.90
BOT_PRICES = {
    "basic-funded": 100.0,
    "pro-funded": 200.0,
    "basic-bot": 30.0,
    "pro-bot": 60.0,
}
FUNDED_BOT_CREDITS = {"basic-funded": 500.0, "pro-funded": 1000.0}
_user_sessions: dict[str, dict] = {}
_user_pending_trades: dict[str, dict] = {}


def compute_trade_delta(amount: float, win: bool) -> float:
    """Calculate trade delta (profit/loss)"""
    if win:
        # Return the payout: original stake + 90% profit = 190% of stake
        return round(amount * WIN_PROFIT_RATE, 2)
    return round(-amount, 2)


@router.post("/purchase", response_model=BotPurchaseResponse)
def purchase_bot(
    payload: BotPurchaseRequest,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Unlock a paid bot using the user's wallet balance exactly once."""
    bot_id = payload.bot_id
    price = BOT_PRICES[bot_id]
    owned = user.get("purchased_bot_ids", [])
    if bot_id in owned:
        raise HTTPException(status_code=400, detail="This bot has already been purchased")

    # The balance condition makes the deduction safe even if two purchases are sent together.
    credit = FUNDED_BOT_CREDITS.get(bot_id, 0.0)
    result = db.users.find_one_and_update(
        {
            "_id": user["_id"],
            "balance": {"$gte": price},
            "purchased_bot_ids": {"$ne": bot_id},
        },
        {
            "$inc": {"balance": credit - price},
            "$addToSet": {"purchased_bot_ids": bot_id},
        },
        return_document=True,
    )
    if result is None:
        latest = db.users.find_one({"_id": user["_id"]}, {"balance": 1, "purchased_bot_ids": 1}) or {}
        if bot_id in latest.get("purchased_bot_ids", []):
            raise HTTPException(status_code=400, detail="This bot has already been purchased")
        raise HTTPException(status_code=400, detail="Wallet balance is not enough. Go and deposit first.")

    return BotPurchaseResponse(
        bot_id=bot_id,
        balance=round(float(result.get("balance", 0)), 2),
        purchased_bot_ids=result.get("purchased_bot_ids", []),
        funded_credit=credit,
    )


@router.post("/trade/start")
def start_bot_session(
    pair: str = "BTC/USDT",
    timeframe: str = "1M",
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Start a new trading session"""
    user_id = str(user["_id"])
    
    if user_id in _user_sessions:
        raise HTTPException(status_code=400, detail="Session already active")
    
    balance = float(user.get("balance", 0))
    session = trading_engine.start_session(pair=pair, timeframe=timeframe, initial_balance=balance)
    
    _user_sessions[user_id] = {
        "pair": pair,
        "timeframe": timeframe,
        "initial_balance": balance,
        "started_at": session["start_time"].isoformat()
    }
    
    return {
        "status": "started",
        "pair": pair,
        "timeframe": timeframe,
        "balance": balance,
        "logs": trading_engine.analysis_logs[-5:] if trading_engine.analysis_logs else []
    }


@router.post("/trade", response_model=BotTradeResponse)
def execute_bot_trade(
    payload: BotTradeRequest,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Execute a bot trade (start or settle phase)"""
    user_id = str(user["_id"])
    balance = float(user.get("balance", 0))
    users_collection = db.users
    
    if payload.phase not in {"start", "settle"}:
        raise HTTPException(status_code=400, detail="Invalid phase")

    side = "BUY" if random.random() < 0.5 else "SELL"

    if payload.phase == "start":
        if payload.amount <= 0:
            raise HTTPException(status_code=400, detail="Stake must be greater than 0")
        if payload.amount > balance:
            raise HTTPException(status_code=400, detail="Trade amount cannot exceed account balance")
        if user_id in _user_pending_trades:
            raise HTTPException(status_code=400, detail="A trade is already pending")

        # Reserve the stake
        users_collection.update_one(
            {"_id": user["_id"]},
            {"$inc": {"balance": -payload.amount}}
        )
        
        _user_pending_trades[user_id] = {
            "amount": payload.amount,
            "pair": payload.pair,
            "side": side,
            "duration": getattr(payload, "duration", 60),
            "started_at": datetime.now().isoformat(),
        }

        return BotTradeResponse(
            pair=payload.pair,
            side=side,
            amount=payload.amount,
            win=False,
            delta=0.0,
            balance=round(balance - payload.amount, 2),
            message="Trade started and stake reserved",
        )

    # Settle phase
    pending_trade = _user_pending_trades.pop(user_id, None)
    if pending_trade is None:
        raise HTTPException(status_code=400, detail="No pending trade to settle")

    # Execute trade through trading engine if session active
    try:
        if user_id in _user_sessions:
            result = trading_engine.execute_trade(
                pair=pending_trade["pair"],
                amount=pending_trade["amount"],
                direction=pending_trade["side"]
            )
            win = result["is_win"]
            delta = result.get("delta", 0)
        else:
            # Fallback to simple random outcome
            win = random.random() < 0.7
            delta = compute_trade_delta(pending_trade["amount"], win)
    except RuntimeError:
        # No active session, use simple logic
        win = random.random() < 0.7
        delta = compute_trade_delta(pending_trade["amount"], win)

    delta = compute_trade_delta(pending_trade["amount"], win)
    # The stake was deducted when the trade started. On a loss there is no
    # further balance change; on a win, credit the existing 190% payout.
    new_balance = round(balance + delta, 2) if win else round(balance, 2)
    
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"balance": new_balance}}
    )

    return BotTradeResponse(
        pair=pending_trade["pair"],
        side=pending_trade["side"],
        amount=pending_trade["amount"],
        win=win,
        delta=delta,
        balance=new_balance,
        message="Trade settled",
    )


@router.get("/trade/pending")
def get_pending_trade(
    user: dict = Depends(get_current_user),
):
    """Return the current pending trade for the user, if any"""
    user_id = str(user["_id"])
    pending = _user_pending_trades.get(user_id)
    if not pending:
        return {"pending": False}
    return {"pending": True, **pending}


@router.delete("/trade/pending")
def cancel_pending_trade(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Cancel a pending trade and refund the reserved stake"""
    user_id = str(user["_id"])
    pending = _user_pending_trades.pop(user_id, None)
    
    if not pending:
        raise HTTPException(status_code=400, detail="No pending trade to cancel")

    # Refund stake to user
    try:
        users_collection = db.users
        users_collection.update_one(
            {"_id": user["_id"]},
            {"$inc": {"balance": pending.get("amount", 0)}}
        )
        refunded_balance = float(user.get("balance", 0)) + pending.get("amount", 0)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to refund stake")

    return {"status": "cancelled", "refunded": pending.get("amount", 0), "balance": refunded_balance}


@router.get("/trade/status")
def get_trade_status(
    user: dict = Depends(get_current_user),
):
    """Get current trading status"""
    status = trading_engine.get_status()
    
    return {
        "status": status.get("status", "idle"),
        "pair": status.get("pair"),
        "balance": status.get("balance"),
        "wins": status.get("wins", 0),
        "losses": status.get("losses", 0),
        "win_rate": status.get("win_rate", 0),
        "trades_count": status.get("trades_count", 0),
        "recent_logs": trading_engine.analysis_logs[-10:] if trading_engine.analysis_logs else []
    }

@router.post("/trade/end")
def end_bot_session(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End the current trading session"""
    if user.id not in _user_sessions:
        raise HTTPException(status_code=400, detail="No active session")
    
    try:
        summary = trading_engine.end_session()
        _user_sessions.pop(user.id, None)
        
        # Update user balance with final session balance
        user.balance = summary["ending_balance"]
        db.commit()
        
        return {
            "status": "ended",
            "summary": summary,
            "logs": trading_engine.analysis_logs
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
