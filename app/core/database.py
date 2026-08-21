from pymongo import MongoClient, ASCENDING
from pymongo.database import Database
from app.core.config import settings

# MongoDB connection
_client: MongoClient | None = None
_db: Database | None = None


def connect_to_mongo() -> None:
    """Connect to MongoDB and create indexes"""
    global _client, _db
    _client = MongoClient(settings.MONGODB_URL)
    _db = _client[settings.MONGODB_DB_NAME]
    
    # Create indexes
    if settings.AUTO_CREATE_TABLES:
        _create_indexes()


def close_mongo_connection() -> None:
    """Close MongoDB connection"""
    global _client
    if _client:
        _client.close()


def _create_indexes() -> None:
    """Create MongoDB indexes for collections"""
    if _db is None:
        return
    
    # Users collection indexes
    _db.users.create_index([("email", ASCENDING)], unique=True)
    _db.users.create_index([("referral_code", ASCENDING)], unique=True)
    _db.users.create_index([("created_at", ASCENDING)])
    
    # Transactions collection indexes
    _db.transactions.create_index([("user_id", ASCENDING)])
    _db.transactions.create_index([("created_at", ASCENDING)])
    _db.transactions.create_index([("status", ASCENDING)])

    _db.trades.create_index([("user_id", ASCENDING), ("opened_at", ASCENDING)])
    _db.trades.create_index([("user_id", ASCENDING), ("status", ASCENDING), ("closed_at", ASCENDING)])
    _db.notifications.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    _db.notification_reads.create_index([("user_id", ASCENDING), ("notification_id", ASCENDING)], unique=True)
    _db.kyc.create_index([("user_id", ASCENDING)], unique=True)
    _db.audit_logs.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    
    # Referrals collection indexes
    _db.referrals.create_index([("referrer_id", ASCENDING)])
    _db.referrals.create_index([("referred_id", ASCENDING)], unique=True)


def get_db() -> Database:
    """Get MongoDB database instance"""
    if _db is None:
        connect_to_mongo()
    return _db


def get_collection(collection_name: str):
    """Get MongoDB collection"""
    db = get_db()
    return db[collection_name]
