from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.database import Database
from bson import ObjectId

from app.api.deps import get_current_user
from app.core.database import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=2000)
    type: str = Field(default="information", pattern="^(information|success|warning|alert|maintenance|trading|security)$")
    priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    expires_at: datetime | None = None


def _public(doc: dict) -> dict:
    return {**{key: value for key, value in doc.items() if key != "_id"}, "id": str(doc["_id"])}


@router.get("")
def list_notifications(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    now = datetime.now(timezone.utc)
    docs = db.notifications.find({
        "status": "published",
        "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
        "$and": [{"$or": [{"target_user_ids": None}, {"target_user_ids": {"$exists": False}}, {"target_user_ids": str(user["_id"])}]}],
    }).sort("created_at", -1)
    reads = {str(item["notification_id"]) for item in db.notification_reads.find({"user_id": str(user["_id"])})}
    result = []
    for doc in docs:
        item = _public(doc)
        item["read"] = item["id"] in reads
        result.append(item)
    return {"unread_count": sum(not item["read"] for item in result), "items": result}


@router.patch("/{notification_id}/read")
def mark_read(notification_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    try:
        object_id = ObjectId(notification_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc
    if not db.notifications.find_one({"_id": object_id, "status": "published"}):
        raise HTTPException(status_code=404, detail="Notification not found")
    db.notification_reads.update_one({"notification_id": object_id, "user_id": str(user["_id"])}, {"$set": {"read_at": datetime.now(timezone.utc)}}, upsert=True)
    return {"read": True}


@router.post("/read-all")
def mark_all_read(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    now = datetime.now(timezone.utc)
    docs = db.notifications.find({"status": "published"}, {"_id": 1})
    db.notification_reads.bulk_write([
        __import__("pymongo").UpdateOne({"notification_id": doc["_id"], "user_id": str(user["_id"])}, {"$set": {"read_at": now}}, upsert=True)
        for doc in docs
    ])
    return {"read": True}