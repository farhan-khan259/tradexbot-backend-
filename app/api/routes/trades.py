from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.api.deps import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/trades", tags=["trades"])


def _public(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id", "")),
        "pair": doc.get("pair"),
        "side": doc.get("side"),
        "quantity": doc.get("quantity", doc.get("amount")),
        "amount": doc.get("amount", doc.get("quantity")),
        "entry_price": doc.get("entry_price"),
        "stop_loss": doc.get("stop_loss"),
        "take_profit": doc.get("take_profit"),
        "profit_loss": doc.get("profit_loss", 0),
        "status": doc.get("status"),
        "source": doc.get("source"),
        "opened_at": doc.get("opened_at"),
        "risk": doc.get("risk"),
    }


@router.get("")
def list_trades(page: int = 1, page_size: int = 25, source: str | None = None, status: str | None = None, search: str | None = None, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    query = {"user_id": str(user["_id"])}
    if source == "AI": query["source"] = source
    if status in {"open", "closed"}: query["status"] = status
    if search: query["pair"] = {"$regex": search[:50], "$options": "i"}
    safe_page = max(page, 1)
    safe_size = min(max(page_size, 1), 100)
    total = db.trades.count_documents(query)
    docs = db.trades.find(query).sort("opened_at", -1).skip((safe_page - 1) * safe_size).limit(safe_size)
    return {"items": [_public(doc) for doc in docs], "page": safe_page, "page_size": safe_size, "total": total}


@router.get("/positions")
def list_positions(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    return [_public(doc) for doc in db.trades.find({"user_id": str(user["_id"]), "status": "open"}).sort("opened_at", -1)]

