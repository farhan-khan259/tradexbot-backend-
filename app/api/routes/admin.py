from datetime import datetime, timedelta, timezone
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.schemas.admin import AdminStats
from app.schemas.transaction import TransactionPublic, TransactionResolve
from app.schemas.user import UserAdminView
from app.services.referral import REFERRAL_BONUS, should_credit_referral_bonus

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
def stats(_: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    users_collection = db.users
    transactions_collection = db.transactions
    referrals_collection = db.referrals
    
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Count stats
    total_users = users_collection.count_documents({})
    active_users = users_collection.count_documents({"is_active": True})
    admin_users = users_collection.count_documents({"is_admin": True})
    new_users_7d = users_collection.count_documents({"created_at": {"$gte": week_ago}})
    
    # Balance calculations
    balance_result = users_collection.aggregate([{"$group": {"_id": None, "total": {"$sum": "$balance"}}}])
    total_balance = list(balance_result)[0]["total"] if list(users_collection.aggregate([{"$group": {"_id": None, "total": {"$sum": "$balance"}}}])) else 0
    
    # Transaction stats
    deposits_pending = transactions_collection.count_documents({"type": "deposit", "status": "pending"})
    deposits_approved = transactions_collection.count_documents({"type": "deposit", "status": "approved"})
    withdrawals_pending = transactions_collection.count_documents({"type": "withdrawal", "status": "pending"})
    withdrawals_approved = transactions_collection.count_documents({"type": "withdrawal", "status": "approved"})
    
    # Sum deposits and withdrawals
    deposits_sum_result = list(transactions_collection.aggregate([
        {"$match": {"type": "deposit", "status": "approved"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]))
    deposits_total_amount = deposits_sum_result[0]["total"] if deposits_sum_result else 0
    
    withdrawals_sum_result = list(transactions_collection.aggregate([
        {"$match": {"type": "withdrawal", "status": "approved"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]))
    withdrawals_total_amount = withdrawals_sum_result[0]["total"] if withdrawals_sum_result else 0
    
    # Referral bonus sum
    referral_sum_result = list(referrals_collection.aggregate([
        {"$group": {"_id": None, "total": {"$sum": "$bonus_amount"}}}
    ]))
    referral_bonus_total = referral_sum_result[0]["total"] if referral_sum_result else 0
    
    return AdminStats(
        total_users=total_users,
        active_users=active_users,
        admin_users=admin_users,
        new_users_7d=new_users_7d,
        total_balance=float(total_balance or 0),
        deposits_pending_count=deposits_pending,
        deposits_approved_count=deposits_approved,
        deposits_total_amount=float(deposits_total_amount or 0),
        withdrawals_pending_count=withdrawals_pending,
        withdrawals_approved_count=withdrawals_approved,
        withdrawals_total_amount=float(withdrawals_total_amount or 0),
        referral_bonus_total=float(referral_bonus_total or 0),
    )


@router.get("/users", response_model=list[UserAdminView])
def list_users(_: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    users_collection = db.users
    users = list(users_collection.find().sort("created_at", -1))
    return users


@router.get("/transactions", response_model=list[TransactionPublic])
def list_transactions(
    status_filter: str | None = None,
    type_filter: str | None = None,
    _: dict = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    transactions_collection = db.transactions
    query = {}
    
    if status_filter:
        query["status"] = status_filter
    if type_filter:
        query["type"] = type_filter
    
    txs = list(transactions_collection.find(query).sort("created_at", -1))
    return [_tx_doc_to_response(tx) for tx in txs]


def _tx_doc_to_response(doc: dict) -> dict:
    """Convert MongoDB transaction document to response"""
    if doc is None:
        return None
    doc["id"] = str(doc.get("_id", ""))
    return doc


@router.post("/transactions/{tx_id}/resolve", response_model=TransactionPublic)
def resolve_transaction(
    tx_id: str,
    payload: TransactionResolve,
    _: dict = Depends(get_current_admin),
    db: Database = Depends(get_db),
):
    if payload.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")

    transactions_collection = db.transactions
    users_collection = db.users
    referrals_collection = db.referrals
    
    try:
        tx_obj_id = ObjectId(tx_id)
    except:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    tx = transactions_collection.find_one({"_id": tx_obj_id})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Transaction already resolved")

    user = users_collection.find_one({"_id": ObjectId(tx["user_id"])})

    if payload.status == "approved":
        if tx["type"] == "deposit":
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$inc": {"balance": tx["amount"]}}
            )

            if user.get("referred_by_id"):
                # Check total approved deposits for this user
                approved_deposits = list(transactions_collection.aggregate([
                    {"$match": {
                        "user_id": str(user["_id"]),
                        "type": "deposit",
                        "status": "approved"
                    }},
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
                ]))
                approved_deposit_total = (approved_deposits[0]["total"] if approved_deposits else 0) + tx["amount"]

                if should_credit_referral_bonus(approved_deposit_total):
                    referrer = users_collection.find_one({"_id": ObjectId(user["referred_by_id"])})
                    existing_referral = referrals_collection.find_one({
                        "referrer_id": str(referrer["_id"]),
                        "referred_id": str(user["_id"])
                    })
                    
                    if referrer and not existing_referral:
                        users_collection.update_one(
                            {"_id": referrer["_id"]},
                            {"$inc": {"balance": REFERRAL_BONUS}}
                        )
                        referrals_collection.insert_one({
                            "referrer_id": str(referrer["_id"]),
                            "referred_id": str(user["_id"]),
                            "bonus_amount": REFERRAL_BONUS,
                            "created_at": datetime.now(timezone.utc),
                        })
        # Withdrawals already debited the balance at request time.
    else:  # rejected
        if tx["type"] == "withdrawal":
            # Refund the reserved amount.
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$inc": {"balance": tx["amount"]}}
            )

    transactions_collection.update_one(
        {"_id": tx_obj_id},
        {
            "$set": {
                "status": payload.status,
                "resolved_at": datetime.now(timezone.utc)
            }
        }
    )
    
    updated_tx = transactions_collection.find_one({"_id": tx_obj_id})
    return _tx_doc_to_response(updated_tx)
