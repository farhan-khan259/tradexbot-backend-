import json
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter(prefix="/market", tags=["market"])

SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "BNB": "BNBUSDT", "SOL": "SOLUSDT", "XRP": "XRPUSDT", "ADA": "ADAUSDT"}


def _fetch(path: str):
    try:
        with urlopen(f"{settings.MARKET_DATA_BASE_URL.rstrip('/')}{path}", timeout=settings.MARKET_DATA_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Market data unavailable") from error


@router.get("/{symbol}")
def ticker(symbol: str):
    pair = SYMBOLS.get(symbol.upper(), symbol.upper().replace("/", ""))
    payload = _fetch(f"/api/v3/ticker/24hr?symbol={pair}")
    return {"symbol": symbol.upper(), "pair": pair, "price": float(payload["lastPrice"]), "change": float(payload["priceChangePercent"]), "connection": "CONNECTED"}


@router.get("/{symbol}/candles")
def candles(symbol: str, interval: str = "1h", limit: int = 80):
    allowed = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}
    if interval not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported candle interval")
    pair = SYMBOLS.get(symbol.upper(), symbol.upper().replace("/", ""))
    payload = _fetch(f"/api/v3/klines?symbol={pair}&interval={interval}&limit={min(max(limit, 1), 500)}")
    return {"symbol": symbol.upper(), "interval": interval, "connection": "CONNECTED", "candles": [{"time": item[0], "o": float(item[1]), "h": float(item[2]), "l": float(item[3]), "c": float(item[4]), "v": float(item[5])} for item in payload]}