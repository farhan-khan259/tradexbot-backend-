from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.api.deps import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _period_start(days: int = 0) -> datetime:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return start - timedelta(days=days)


def _trade_response(trade: dict) -> dict:
    return {
        "id": str(trade.get("_id", "")),
        "pair": trade.get("pair"),
        "side": trade.get("side"),
        "amount": float(trade.get("amount", 0)),
        "profit_loss": float(trade.get("profit_loss", 0)),
        "status": trade.get("status", "closed"),
        "source": trade.get("source", "AI"),
        "account_type": trade.get("account_type", "wallet"),
        "quantity": float(trade.get("quantity", 0)),
        "entry_price": float(trade.get("entry_price", 0)),
        "stop_loss": float(trade.get("stop_loss", 0)),
        "take_profit": float(trade.get("take_profit", 0)),
        "opened_at": trade.get("opened_at"),
        "closed_at": trade.get("closed_at"),
    }


@router.get("")
def dashboard(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    user_id = str(user["_id"])
    trades = db.trades
    today = _period_start()
    today_trades = list(trades.find({"user_id": user_id, "closed_at": {"$gte": today}}))
    completed = list(trades.find({"user_id": user_id, "status": "closed"}))
    recent = list(trades.find({"user_id": user_id}).sort("opened_at", -1).limit(10))
    open_positions = list(trades.find({"user_id": user_id, "status": "open"}).sort("opened_at", -1))

    realized_pl = round(sum(float(t.get("profit_loss", 0)) for t in completed), 2)
    today_pl = round(sum(float(t.get("profit_loss", 0)) for t in today_trades), 2)
    wins = sum(1 for t in completed if float(t.get("profit_loss", 0)) > 0)
    win_rate = round((wins / len(completed)) * 100, 2) if completed else 0.0
    wallet_balance = float(user.get("balance", 0))
    funded_balance = float(user.get("basic_funded_balance", 0)) + float(user.get("pro_funded_balance", 0))
    total_balance = round(wallet_balance + funded_balance, 2)
    pending = db.transactions.count_documents({"user_id": user_id, "status": "pending"})

    from app.api.routes.bot import _user_bot_controls, _user_pending_trades, _user_sessions

    bot_status = _user_bot_controls.get(user_id, "stopped").upper()
    if user_id in _user_pending_trades:
        bot_status = "RUNNING"
    daily_loss_limit = round(total_balance * 0.05, 2)
    risk_score = min(100, round(max(0, (-today_pl / daily_loss_limit) * 100))) if daily_loss_limit else 0
    risk_level = "CRITICAL" if risk_score >= 90 else "HIGH" if risk_score >= 65 else "MODERATE" if risk_score >= 35 else "LOW"

    return {
        "bot": {
            "status": bot_status,
            "risk_level": risk_level,
            "last_trade": _trade_response(recent[0]) if recent else None,
            "exchange_connection": "DISCONNECTED",
            "market_data_connection": "CONNECTED",
        },
        "balance": {
            "available": round(wallet_balance, 2),
            "total": total_balance,
            "wallet": round(wallet_balance, 2),
            "funded": round(funded_balance, 2),
            "equity": total_balance,
        },
        "performance": {
            "today_pl": today_pl,
            "total_pl": realized_pl,
            "win_rate": win_rate,
            "trades_today": len(today_trades),
            "completed_trades": len(completed),
        },
        "risk": {
            "level": risk_level,
            "score": risk_score,
            "daily_loss_limit": daily_loss_limit,
            "daily_loss": round(min(0, today_pl), 2),
            "recommendation": "Trading within configured limits." if risk_score < 35 else "Reduce position size and use a tighter stop-loss.",
        },
        "recent_trades": [_trade_response(t) for t in recent],
        "open_positions": [_trade_response(t) for t in open_positions],
        "transactions": {
            "pending_count": pending,
            "recent": [
                {
                    "id": str(t.get("_id", "")),
                    "type": t.get("type"),
                    "amount": float(t.get("amount", 0)),
                    "status": t.get("status"),
                    "created_at": t.get("created_at"),
                }
                for t in list(db.transactions.find({"user_id": user_id}).sort("created_at", -1).limit(8))
            ],
        },
    }