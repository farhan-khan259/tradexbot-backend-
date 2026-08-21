from datetime import datetime, timezone
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas.transaction import TransactionCreate, TransactionPublic
from app.services.audit import record_audit

router = APIRouter(prefix="/transactions", tags=["transactions"])

MIN_DEPOSIT = 30
MIN_WITHDRAWAL = 100
WITHDRAWAL_BALANCE_FIELDS = {
    "Wallet": ("balance", 0),
    "Basic Funded": ("basic_funded_balance", 700),
    "Pro Funded": ("pro_funded_balance", 1500),
}


def _tx_doc_to_response(doc: dict) -> dict:
    """Convert MongoDB transaction document to response"""
    if doc is None:
        return None
    doc["id"] = str(doc.get("_id", ""))
    return doc


@router.get("", response_model=list[TransactionPublic])
def list_my_transactions(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    transactions_collection = db.transactions
    txs = list(
        transactions_collection.find({"user_id": str(user["_id"])})
        .sort("created_at", -1)
    )
    return [_tx_doc_to_response(tx) for tx in txs]


@router.post("/deposit", response_model=TransactionPublic, status_code=201)
def request_deposit(
    payload: TransactionCreate,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    if payload.amount < MIN_DEPOSIT:
        raise HTTPException(status_code=400, detail=f"Minimum deposit is ${MIN_DEPOSIT}")

    if not payload.note or not payload.note.strip():
        raise HTTPException(status_code=400, detail="Transaction reference or note is required")

    if not payload.screenshot_data or not payload.screenshot_data.strip():
        raise HTTPException(status_code=400, detail="Upload the payment screenshot")

    # Demo deposits are recorded as pending and credited only on admin approval.
    tx_doc = {
        "user_id": str(user["_id"]),
        "type": "deposit",
        "status": "pending",
        "amount": payload.amount,
        "note": payload.note,
        "screenshot_data": payload.screenshot_data,
        "account_name": None,
        "wallet_address": None,
        "network": None,
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
    }
    
    transactions_collection = db.transactions
    result = transactions_collection.insert_one(tx_doc)
    tx_doc["_id"] = result.inserted_id
    return _tx_doc_to_response(tx_doc)


@router.post("/withdraw", response_model=TransactionPublic, status_code=201)
def request_withdrawal(
    payload: TransactionCreate,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    if payload.amount < MIN_WITHDRAWAL:
        raise HTTPException(status_code=400, detail=f"Minimum withdrawal is ${MIN_WITHDRAWAL}")
    if not payload.account_name:
        raise HTTPException(status_code=400, detail="Please select the account name")
    if not payload.wallet_address:
        raise HTTPException(status_code=400, detail="Please enter your wallet address")
    if not payload.network:
        raise HTTPException(status_code=400, detail="Please choose the network/chain")
    source = WITHDRAWAL_BALANCE_FIELDS.get(payload.account_name)
    if source is None:
        raise HTTPException(status_code=400, detail="Please select a valid withdrawal source")
    balance_field, minimum_balance = source
    current_balance = float(user.get(balance_field, 0))
    if current_balance < minimum_balance:
        raise HTTPException(
            status_code=400,
            detail=f"{payload.account_name} withdrawals are available once the balance reaches ${minimum_balance:,.0f}",
        )
    if payload.amount > current_balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Reserve funds immediately
    users_collection = db.users
    reserved = users_collection.update_one(
        {"_id": user["_id"], balance_field: {"$gte": payload.amount}},
        {"$inc": {balance_field: -payload.amount}},
    )
    if reserved.modified_count != 1:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    tx_doc = {
        "user_id": str(user["_id"]),
        "type": "withdrawal",
        "status": "pending",
        "amount": payload.amount,
        "note": payload.note or "",
        "screenshot_data": None,
        "account_name": payload.account_name,
        "wallet_address": payload.wallet_address,
        "network": payload.network,
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
    }
    
    transactions_collection = db.transactions
    result = transactions_collection.insert_one(tx_doc)
    tx_doc["_id"] = result.inserted_id
    record_audit(db, str(user["_id"]), "withdrawal_requested", "success", str(result.inserted_id), {"amount": payload.amount})
    return _tx_doc_to_response(tx_doc)
