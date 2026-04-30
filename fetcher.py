"""Fetch news and price data from Alpaca."""
import os
from datetime import datetime, timezone, timedelta
from alpaca.data.historical.news import NewsClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest, StockLatestBarRequest


def _key():
    # Use $15K paper key for news API (paper keys work, no need for live key)
    return os.environ.get("ALPACA_FLOW10K_API_KEY") or os.environ.get("ALPACA_LIVE_API_KEY") or os.environ["ALPACA_API_KEY"]

def _secret():
    return os.environ.get("ALPACA_FLOW10K_SECRET_KEY") or os.environ.get("ALPACA_LIVE_SECRET_KEY") or os.environ["ALPACA_SECRET_KEY"]


def get_news(symbols: list, hours_back: int = 2) -> list:
    client = NewsClient(api_key=_key(), secret_key=_secret())
    start = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    req = NewsRequest(symbols=",".join(symbols), start=start, limit=30, sort="desc")
    return client.get_news(req).data.get("news", [])


def get_price_changes(symbols: list) -> dict:
    """Returns {symbol: day_change_pct} for each symbol."""
    try:
        client = StockHistoricalDataClient(api_key=_key(), secret_key=_secret())
        bars = client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols=symbols))
        result = {}
        for sym, bar in bars.items():
            if bar.open and bar.open > 0:
                pct = round((bar.close - bar.open) / bar.open * 100, 2)
                result[sym] = pct
        return result
    except Exception:
        return {}
