from datetime import datetime, timezone


def record_audit(db, user_id: str | None, action: str, result: str, entity: str | None = None, metadata: dict | None = None) -> None:
    db.audit_logs.insert_one({
        "user_id": user_id,
        "action": action,
        "result": result,
        "entity": entity,
        "metadata": metadata or {},
        "created_at": datetime.now(timezone.utc),
    })