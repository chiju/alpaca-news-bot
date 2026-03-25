"""Fetch news and price data from Alpaca."""
import os
from datetime import datetime, timezone, timedelta
from alpaca.data.historical.news import NewsClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest, StockLatestBarRequest

KEY    = os.environ["ALPACA_API_KEY"]
SECRET = os.environ["ALPACA_SECRET_KEY"]


def get_news(symbols: list, hours_back: int = 2) -> list:
    client = NewsClient(api_key=KEY, secret_key=SECRET)
    start = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    req = NewsRequest(symbols=",".join(symbols), start=start, limit=30, sort="desc")
    return client.get_news(req).data.get("news", [])


def get_price_changes(symbols: list) -> dict:
    """Returns {symbol: day_change_pct} for each symbol."""
    client = StockHistoricalDataClient(api_key=KEY, secret_key=SECRET)
    try:
        bars = client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols=symbols))
        result = {}
        for sym, bar in bars.items():
            if bar.open and bar.open > 0:
                pct = round((bar.close - bar.open) / bar.open * 100, 2)
                result[sym] = pct
        return result
    except Exception:
        return {}
