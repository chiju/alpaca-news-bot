#!/usr/bin/env python3
"""
Fully Automated Covered Call Engine
- Scans portfolio for covered call opportunities
- AI sentiment filter (skip negative news stocks)
- Auto-places trades via Alpaca paper account
- Logs to Google Sheets journal
- Sends Telegram notifications
- Closes positions at 50% profit
- No human intervention needed
"""
import os, requests
from datetime import datetime, timezone, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import QueryOrderStatus, OrderSide, OrderType, TimeInForce
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest

# Load local env
_env = os.path.expanduser("~/.alpaca/options-paper.env")
if os.path.exists(_env):
    for line in open(_env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from wheel_params import DELTA_MIN, DELTA_MAX, EXPIRATION_MIN, EXPIRATION_MAX, OPEN_INTEREST_MIN

KEY    = os.environ["ALPACA_API_KEY"]
SECRET = os.environ["ALPACA_SECRET_KEY"]
HF     = os.environ["HF_TOKEN"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT  = os.environ["TELEGRAM_CHAT_ID"]

PROFIT_TARGET = 0.50   # Close at 50% profit
MAX_POSITIONS = 5      # Max open covered calls at once


def notify(msg: str):
    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                  json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown",
                        "disable_web_page_preview": True}, timeout=10)


def log_sheets(symbol, contract, premium, status):
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        return
    try:
        import json
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        key_file = os.path.expanduser("~/Desktop/down/yahoo-portfolio-data-44dbe4ae4313.json")
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if os.path.exists(key_file):
            creds = Credentials.from_service_account_file(key_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        else:
            creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range="Trade Journal!A:L",
            valueInputOption="USER_ENTERED",
            body={"values": [[datetime.now().strftime("%Y-%m-%d %H:%M"), symbol,
                              "Covered Call", contract, "", "", "", f"${premium:.2f}", "", "", status, ""]]}
        ).execute()
    except Exception as e:
        print(f"Sheets: {e}")


def get_sentiment(symbol: str) -> str:
    try:
        client = NewsClient(api_key=KEY, secret_key=SECRET)
        start = datetime.now(timezone.utc) - timedelta(hours=24)
        news = client.get_news(NewsRequest(symbols=symbol, start=start, limit=3, sort="desc"))
        articles = news.data.get("news", [])
        labels = []
        for a in articles[:3]:
            r = requests.post(
                "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert",
                headers={"Authorization": f"Bearer {HF}"},
                json={"inputs": a.headline[:200]}, timeout=10)
            if r.status_code == 200:
                result = r.json()
                if isinstance(result, list) and result:
                    top = max(result[0], key=lambda x: x["score"])
                    if top["score"] > 0.70:
                        labels.append(top["label"])
        return max(set(labels), key=labels.count) if labels else "neutral"
    except:
        return "neutral"


def find_best_call(symbol: str, stock_price: float) -> dict | None:
    """Find best covered call to sell for this stock."""
    try:
        client = OptionHistoricalDataClient(api_key=KEY, secret_key=SECRET)
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=datetime.now().date() + timedelta(days=EXPIRATION_MIN),
            expiration_date_lte=datetime.now().date() + timedelta(days=EXPIRATION_MAX),
        )
        chain = client.get_option_chain(req)
        candidates = []
        for sym, snap in chain.items():
            if "C" not in sym[len(symbol)+6:len(symbol)+7]:
                continue
            if snap.greeks is None or snap.implied_volatility is None:
                continue
            if snap.latest_quote.bid_price is None or snap.latest_quote.bid_price <= 0:
                continue
            delta = snap.greeks.delta
            if not (DELTA_MIN <= delta <= DELTA_MAX):
                continue
            candidates.append({
                "symbol": sym, "bid": snap.latest_quote.bid_price,
                "delta": delta, "iv": snap.implied_volatility,
                "premium_pct": snap.latest_quote.bid_price / stock_price * 100
            })
        if not candidates:
            return None
        return max(candidates, key=lambda x: x["premium_pct"])
    except:
        return None


def close_profitable_positions(trade_client: TradingClient) -> list:
    """Close covered calls that hit 50% profit target."""
    closed = []
    positions = trade_client.get_all_positions()
    for p in positions:
        sym = p.symbol
        # Only short calls (negative qty, contains digits + C)
        if float(p.qty) >= 0 or not any(c.isdigit() for c in sym):
            continue
        if "C" not in sym:
            continue
        entry = float(p.avg_entry_price)
        current = float(p.current_price)
        profit_pct = (entry - current) / entry  # short position profits when price drops
        if profit_pct >= PROFIT_TARGET:
            try:
                trade_client.close_position(sym, close_options=ClosePositionRequest(qty="1"))
                premium = entry * 100
                pnl = (entry - current) * 100
                closed.append(f"✅ Closed `{sym}` at 50% profit | P&L: +${pnl:.2f}")
                log_sheets(sym[:4], sym, premium, "CLOSED")
            except Exception as e:
                closed.append(f"⚠️ Failed to close {sym}: {e}")
    return closed


def run():
    trade_client = TradingClient(api_key=KEY, secret_key=SECRET, paper=True)
    lines = [f"📞 *Covered Call Engine* — {datetime.now().strftime('%b %d %H:%M')}\n"]

    # Step 1: Close profitable positions
    closed = close_profitable_positions(trade_client)
    if closed:
        lines.append("*Closed positions:*")
        lines.extend(closed)
        lines.append("")

    # Step 2: Count open covered calls
    positions = trade_client.get_all_positions()
    open_calls = [p for p in positions
                  if float(p.qty) < 0 and any(c.isdigit() for c in p.symbol) and "C" in p.symbol]
    if len(open_calls) >= MAX_POSITIONS:
        lines.append(f"⏸️ Max positions reached ({MAX_POSITIONS}). No new trades.")
        notify("\n".join(lines))
        return

    # Step 3: Find stocks we own 100+ shares of
    owned = {p.symbol: float(p.current_price)
             for p in positions
             if not any(c.isdigit() for c in p.symbol) and float(p.qty) >= 100}
    lines.append(f"Eligible: {', '.join(owned.keys()) or 'None'}\n")

    # Step 4: AI filter + find + place covered calls
    new_trades = []
    for symbol, price in owned.items():
        if len(open_calls) + len(new_trades) >= MAX_POSITIONS:
            break

        # Skip if already have a call on this stock
        if any(symbol in p.symbol for p in open_calls):
            continue

        # AI sentiment check
        sentiment = get_sentiment(symbol)
        if sentiment == "negative":
            lines.append(f"⛔ `{symbol}` skipped — negative news")
            continue

        # Find best call
        best = find_best_call(symbol, price)
        if not best:
            continue

        # Place the trade
        try:
            req = MarketOrderRequest(
                symbol=best["symbol"], qty=1,
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                time_in_force=TimeInForce.DAY
            )
            trade_client.submit_order(req)
            premium = best["bid"] * 100
            new_trades.append(best["symbol"])
            lines.append(f"✅ Sold `{best['symbol']}` | Premium: ${premium:.2f} ({best['premium_pct']:.1f}%) | IV: {best['iv']:.0%} | δ{best['delta']:.2f}")
            log_sheets(symbol, best["symbol"], premium, "OPEN")
        except Exception as e:
            lines.append(f"⚠️ `{symbol}` order failed: {e}")

    if not new_trades and not closed:
        lines.append("No new trades placed today.")

    msg = "\n".join(lines)
    notify(msg)
    print(msg)


if __name__ == "__main__":
    run()
