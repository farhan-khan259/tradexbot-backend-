from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import random
from typing import Dict, List

from app.core.config import settings
from app.services.outcome_cycle import generate_balanced_outcomes
from app.core.database import connect_to_mongo, close_mongo_connection, get_db
from app.api.routes import auth, transactions, referrals, admin, bot, dashboard, security, notifications, kyc, trades, market
from app.core.security import decode_token
from bson import ObjectId
from app.services.seed import seed_admin

# In-memory state for demo accounts (persist for process lifetime)
accounts: Dict[str, Dict] = {}
# Active websocket connections per account
ws_connections: Dict[str, List[WebSocket]] = {}


def generate_new_block() -> List[str]:
    return generate_balanced_outcomes()


def get_or_create_account(account_id: str) -> Dict:
    if account_id not in accounts:
        accounts[account_id] = {
            "balance": 1158.0,
            "total_wins": 0,
            "total_losses": 0,
            "remaining_outcomes": [],
        }
    return accounts[account_id]


def broadcast_update(account_id: str, message: Dict) -> None:
    conns = ws_connections.get(account_id) or []
    for ws in list(conns):
        try:
            # schedule async send to avoid blocking
            import asyncio

            asyncio.create_task(ws.send_json(message))
        except Exception:
            try:
                conns.remove(ws)
            except ValueError:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB on startup
    connect_to_mongo()
    db = get_db()
    try:
        seed_admin(db)
    except Exception as e:
        print(f"Warning: Could not seed admin: {e}")
    yield
    # Close MongoDB connection on shutdown
    close_mongo_connection()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "service": settings.PROJECT_NAME}


api = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=api)
app.include_router(transactions.router, prefix=api)
app.include_router(referrals.router, prefix=api)
app.include_router(admin.router, prefix=api)
app.include_router(bot.router, prefix=api)
app.include_router(dashboard.router, prefix=api)
app.include_router(security.router, prefix=api)
app.include_router(notifications.router, prefix=api)
app.include_router(kyc.router, prefix=api)
app.include_router(trades.router, prefix=api)
app.include_router(market.router, prefix=api)


# Pydantic models for account endpoints

class TradeRequest(BaseModel):
    stake: float


class TradeResponse(BaseModel):
    outcome: str
    profit: float
    new_balance: float


class AccountStatus(BaseModel):
    balance: float
    wins: int
    losses: int
    remaining_trades_in_block: int


@app.post("/accounts/{account_id}/trade", response_model=TradeResponse)
def account_trade(account_id: str, req: TradeRequest):
    acct = get_or_create_account(account_id)
    stake = float(req.stake)
    if stake <= 0:
        raise HTTPException(status_code=400, detail="Stake must be > 0")
    if acct["balance"] < stake:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Ensure a block exists
    if not acct["remaining_outcomes"]:
        acct["remaining_outcomes"].extend(generate_new_block())

    outcome = acct["remaining_outcomes"].pop(0)

    if outcome == "W":
        profit = round(stake * 0.90, 2)
        acct["balance"] = round(acct["balance"] + profit, 2)
        acct["total_wins"] += 1
    else:
        profit = round(-stake, 2)
        acct["balance"] = round(acct["balance"] + profit, 2)
        acct["total_losses"] += 1

    # Broadcast to websockets if any
    try:
        broadcast_update(account_id, {"outcome": outcome, "profit": profit, "balance": acct["balance"]})
    except Exception:
        pass

    return TradeResponse(outcome=outcome, profit=profit, new_balance=acct["balance"])


@app.get("/accounts/{account_id}/status", response_model=AccountStatus)
def account_status(account_id: str):
    acct = get_or_create_account(account_id)
    return AccountStatus(
        balance=acct["balance"],
        wins=acct["total_wins"],
        losses=acct["total_losses"],
        remaining_trades_in_block=len(acct["remaining_outcomes"]),
    )


@app.websocket("/ws/{account_id}")
async def websocket_endpoint(websocket: WebSocket, account_id: str):
    await websocket.accept()
    ws_connections.setdefault(account_id, []).append(websocket)
    try:
        while True:
            # keep the connection alive; we don't expect messages from client
            await websocket.receive_text()
    except WebSocketDisconnect:
        try:
            ws_connections[account_id].remove(websocket)
        except Exception:
            pass


@app.websocket("/ws/dashboard")
async def dashboard_websocket(websocket: WebSocket, token: str):
    """Authenticated dashboard stream; sends fresh account state on a bounded cadence."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        user = get_db().users.find_one({"_id": ObjectId(user_id)})
        if not user or not user.get("is_active", False):
            await websocket.close(code=4401)
            return
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type": "dashboard", "data": dashboard.dashboard(user, get_db())})
            await asyncio.sleep(10)
    except (WebSocketDisconnect, RuntimeError):
        return
