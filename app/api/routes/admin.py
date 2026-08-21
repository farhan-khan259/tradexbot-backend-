from datetime import datetime, timedelta, timezone
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.api.deps import get_current_admin
from app.core.database import get_db
from app.schemas.admin import AdminStats
from app.schemas.transaction import TransactionPublic, TransactionResolve
from app.schemas.user import UserAdminView
from app.api.routes.transactions import WITHDRAWAL_BALANCE_FIELDS
from app.services.referral import REFERRAL_BONUS, should_credit_referral_bonus
from app.api.routes.notifications import NotificationCreate
from pydantic import BaseModel, Field

router = APIRouter(prefix="/admin", tags=["admin"])


class NotificationAdminCreate(NotificationCreate):
    target_user_ids: list[str] | None = None
    status: str = Field(default="draft", pattern="^(draft|published|expired)$")


class KYCReview(BaseModel):
    status: str = Field(pattern="^(verified|rejected|resubmission_required)$")
    review_notes: str | None = Field(default=None, max_length=2000)


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


@router.get("/notifications")
def list_admin_notifications(_: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    return [{**{key: value for key, value in doc.items() if key != "_id"}, "id": str(doc["_id"])} for doc in db.notifications.find().sort("created_at", -1)]


@router.post("/notifications", status_code=201)
def create_notification(payload: NotificationAdminCreate, _: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    doc = payload.model_dump()
    doc["created_at"] = datetime.now(timezone.utc)
    result = db.notifications.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@router.patch("/notifications/{notification_id}/publish")
def publish_notification(notification_id: str, _: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    try:
        object_id = ObjectId(notification_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc
    result = db.notifications.update_one({"_id": object_id}, {"$set": {"status": "published"}})
    if result.matched_count != 1:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "published"}


@router.get("/kyc")
def list_kyc(_: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    return [{**doc, "id": str(doc.pop("_id"))} for doc in db.kyc.find({}, {"identity_document": 0, "proof_of_address": 0, "selfie_document": 0}).sort("updated_at", -1)]


@router.get("/audit-logs")
def audit_logs(limit: int = 100, _: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    return [{**doc, "id": str(doc.pop("_id"))} for doc in db.audit_logs.find().sort("created_at", -1).limit(min(max(limit, 1), 500))]


@router.get("/kyc/{user_id}/documents")
def kyc_documents(user_id: str, _: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    doc = db.kyc.find_one({"user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="KYC submission not found")
    return {"identity_document": doc.get("identity_document"), "proof_of_address": doc.get("proof_of_address"), "selfie_document": doc.get("selfie_document")}


@router.patch("/kyc/{user_id}")
def review_kyc(user_id: str, payload: KYCReview, _: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    result = db.kyc.update_one({"user_id": user_id}, {"$set": {"status": payload.status, "review_notes": payload.review_notes, "updated_at": datetime.now(timezone.utc)}})
    if result.matched_count != 1:
        raise HTTPException(status_code=404, detail="KYC submission not found")
    return {"status": payload.status}


def _user_doc_to_response(doc: dict) -> dict:
    """Convert MongoDB user document to response format"""
    if doc is None:
        return None
    doc["id"] = str(doc.get("_id", ""))
    return doc


@router.get("/users", response_model=list[UserAdminView])
def list_users(_: dict = Depends(get_current_admin), db: Database = Depends(get_db)):
    users_collection = db.users
    users = list(users_collection.find().sort("created_at", -1))
    return [_user_doc_to_response(user) for user in users]


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
            balance_field = WITHDRAWAL_BALANCE_FIELDS.get(tx.get("account_name"), ("balance", 0))[0]
            users_collection.update_one(
                {"_id": user["_id"]},
                {"$inc": {balance_field: tx["amount"]}}
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
