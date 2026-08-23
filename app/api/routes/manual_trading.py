from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo import ReturnDocument
from pymongo.database import Database

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.manual_trading import (
    ManualPositionCreate,
    ManualPositionListResponse,
    ManualPositionResponse,
)
from app.services.audit import record_audit
from app.services.outcome_cycle import generate_balanced_outcomes

router = APIRouter(prefix="/manual-trading", tags=["manual-trading"])

MANUAL_WIN_PROFIT_RATE = 0.90
MANUAL_WIN_RATIO = 0.50
MANUAL_CYCLE_SIZE = 10
_manual_outcome_cycles: dict[str, list[str]] = {}


def _balance_field() -> str:
    return "balance"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _next_outcome(user_id: str, side: str) -> bool:
    key = f"{user_id}:{side}"
    cycle = _manual_outcome_cycles.setdefault(key, [])
    if not cycle:
        cycle.extend(generate_balanced_outcomes(MANUAL_CYCLE_SIZE, MANUAL_CYCLE_SIZE // 2, MANUAL_CYCLE_SIZE // 2))
    return cycle.pop(0) == "W"


def _serialize(doc: dict[str, Any], balance: float | None = None) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "pair": doc["pair"],
        "side": doc["side"],
        "amount": float(doc["amount"]),
        "entry_price": float(doc["entry_price"]),
        "status": doc["status"],
        "source": "MANUAL",
        "timeframe": doc.get("timeframe", "5m"),
        "opened_at": _as_utc(doc["opened_at"]),
        "expires_at": _as_utc(doc["expires_at"]),
        "closed_at": _as_utc(doc["closed_at"]) if doc.get("closed_at") else None,
        "win": doc.get("win"),
        "profit_loss": float(doc.get("profit_loss", 0)),
        "balance": balance,
    }


def _find_position(position_id: str, user_id: str, db: Database) -> dict:
    try:
        object_id = ObjectId(position_id)
    except Exception as error:
        raise HTTPException(status_code=404, detail="Manual position not found") from error
    position = db.trades.find_one({"_id": object_id, "user_id": user_id, "source": "MANUAL"})
    if not position:
        raise HTTPException(status_code=404, detail="Manual position not found")
    return position


@router.post("/positions", response_model=ManualPositionResponse, status_code=status.HTTP_201_CREATED)
def open_position(payload: ManualPositionCreate, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    user_id = str(user["_id"])
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=payload.duration)
    reserved = db.users.find_one_and_update(
        {"_id": user["_id"], "balance": {"$gte": payload.amount}},
        {"$inc": {"balance": -payload.amount}},
        return_document=ReturnDocument.AFTER,
    )
    if reserved is None:
        raise HTTPException(status_code=400, detail="Trade amount cannot exceed account balance")

    position = {
        "user_id": user_id,
        "pair": payload.pair,
        "side": payload.side,
        "amount": float(payload.amount),
        "entry_price": float(payload.entry_price),
        "status": "open",
        "source": "MANUAL",
        "timeframe": payload.timeframe,
        "opened_at": now,
        "expires_at": expires_at,
    }
    result = db.trades.insert_one(position)
    position["_id"] = result.inserted_id
    balance = round(float(reserved.get("balance", 0)), 2)
    record_audit(db, user_id, "manual_trade_opened", "success", payload.pair, {"side": payload.side, "amount": payload.amount})
    return _serialize(position, balance)


@router.get("/positions", response_model=ManualPositionListResponse)
def list_positions(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    user_id = str(user["_id"])
    current = db.users.find_one({"_id": user["_id"]}) or {}
    positions = db.trades.find({"user_id": user_id, "source": "MANUAL", "status": "open"}).sort("opened_at", -1)
    balance = round(float(current.get(_balance_field(), 0)), 2)
    return {"items": [_serialize(position, balance) for position in positions], "balance": balance}


@router.post("/positions/{position_id}/settle", response_model=ManualPositionResponse)
def settle_position(position_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    user_id = str(user["_id"])
    position = _find_position(position_id, user_id, db)
    now = datetime.now(timezone.utc)
    if position["status"] != "open":
        current = db.users.find_one({"_id": user["_id"]}) or {}
        return _serialize(position, round(float(current.get("balance", 0)), 2))
    expires_at = position["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at > now:
        raise HTTPException(status_code=409, detail="Position has not reached expiry")

    win = _next_outcome(user_id, position["side"])
    amount = float(position["amount"])
    profit_loss = round(amount * MANUAL_WIN_PROFIT_RATE if win else -amount, 2)
    payout = round(amount * (1 + MANUAL_WIN_PROFIT_RATE), 2) if win else 0
    closed = db.trades.find_one_and_update(
        {"_id": position["_id"], "user_id": user_id, "source": "MANUAL", "status": "open"},
        {"$set": {"status": "closed", "closed_at": now, "win": win, "profit_loss": profit_loss}},
        return_document=ReturnDocument.AFTER,
    )
    if closed is None:
        raise HTTPException(status_code=409, detail="Position was already settled")
    if payout:
        db.users.update_one({"_id": user["_id"]}, {"$inc": {"balance": payout}})
    current = db.users.find_one({"_id": user["_id"]}) or {}
    balance = round(float(current.get("balance", 0)), 2)
    record_audit(db, user_id, "manual_trade_settled", "success", position["pair"], {"side": position["side"], "win": win, "profit_loss": profit_loss, "configured_win_ratio": MANUAL_WIN_RATIO})
    return _serialize(closed, balance)


@router.delete("/positions/{position_id}")
def cancel_position(position_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    user_id = str(user["_id"])
    position = _find_position(position_id, user_id, db)
    if position["status"] != "open":
        raise HTTPException(status_code=409, detail="Position is no longer open")
    cancelled = db.trades.find_one_and_update(
        {"_id": position["_id"], "user_id": user_id, "source": "MANUAL", "status": "open"},
        {"$set": {"status": "cancelled", "closed_at": datetime.now(timezone.utc), "profit_loss": 0}},
        return_document=ReturnDocument.AFTER,
    )
    if cancelled is None:
        raise HTTPException(status_code=409, detail="Position was already closed")
    db.users.update_one({"_id": user["_id"]}, {"$inc": {"balance": float(position["amount"])}})
    current = db.users.find_one({"_id": user["_id"]}) or {}
    balance = round(float(current.get("balance", 0)), 2)
    record_audit(db, user_id, "manual_trade_cancelled", "success", position["pair"], {"amount": position["amount"]})
    return {"status": "cancelled", "position": _serialize(cancelled, balance), "balance": balance}
