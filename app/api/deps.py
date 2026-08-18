from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from pymongo.database import Database
from bson import ObjectId

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Database = Depends(get_db),
) -> dict:
    """Get current authenticated user from token"""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise _credentials_error
    except (PyJWTError, ValueError):
        raise _credentials_error

    # Find user in MongoDB
    users_collection = db.users
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = None
    
    if user is None or not user.get("is_active", False):
        raise _credentials_error
    
    return user


def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    """Get current user and verify admin status"""
    if not user.get("is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
