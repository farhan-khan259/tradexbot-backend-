from functools import lru_cache
import json
import re
from urllib.error import URLError
from urllib.request import urlopen

from app.core.config import settings

SYMBOL_TO_MARKET_PAIR = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "BNB": "BNBUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
    "ADA": "ADAUSDT",
}

# Fallbacks keep API deterministic when external market data is unavailable.
FALLBACK_PRICES = {
    "BTC": 78000.0,
    "ETH": 3800.0,
    "BNB": 620.0,
    "SOL": 180.0,
    "XRP": 0.62,
    "ADA": 0.72,
    "XAU": 2400.0,
    "EUR": 1.08,
    "GBP": 1.27,
}


def normalize_symbol(pair: str) -> str:
    cleaned = re.sub(r"\s*\(.*\)$", "", pair or "").strip().upper()
    if "/" in cleaned:
        return cleaned.split("/", 1)[0]
    return cleaned.split("-", 1)[0]


@lru_cache(maxsize=64)
def reference_price_for_pair(pair: str) -> float:
    symbol = normalize_symbol(pair)
    market_pair = SYMBOL_TO_MARKET_PAIR.get(symbol)

    if market_pair:
        try:
            timeout = min(max(int(settings.MARKET_DATA_TIMEOUT_SECONDS), 1), 2)
            with urlopen(
                f"{settings.MARKET_DATA_BASE_URL.rstrip('/')}/api/v3/ticker/24hr?symbol={market_pair}",
                timeout=timeout,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
                price = float(payload["lastPrice"])
                if price > 0:
                    return price
        except (OSError, URLError, TimeoutError, ValueError, KeyError, TypeError):
            pass

    return FALLBACK_PRICES.get(symbol, 1.0)


def derive_trade_levels(side: str, entry_price: float) -> tuple[float, float]:
    normalized_side = (side or "BUY").upper()
    if normalized_side == "SELL":
        stop_loss = entry_price * 1.005
        take_profit = entry_price * 0.99
    else:
        stop_loss = entry_price * 0.995
        take_profit = entry_price * 1.01
    return round(stop_loss, 8), round(take_profit, 8)


def derive_quantity(amount: float, entry_price: float) -> float:
    if entry_price <= 0:
        return 0.0
    return round(amount / entry_price, 8)