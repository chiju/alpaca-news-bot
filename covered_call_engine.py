#!/usr/bin/env python3
"""
Fully Automated Covered Call Engine
Rules:
- Only sell covered calls on stocks we own 100+ shares
- Delta 0.20-0.35, DTE 21-45 days
- Smart scoring: annualized yield × probability of profit
- AI sentiment: skip only if STRONGLY negative (>85% confidence)
- Close at 50% profit (theta decay target)
- Max 5 open positions
- Only runs during market hours
"""
import os, requests, json
from datetime import datetime, timezone, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, ClosePositionRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
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

KEY      = os.environ["ALPACA_API_KEY"]
SECRET   = os.environ["ALPACA_SECRET_KEY"]
HF       = os.environ["HF_TOKEN"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT  = os.environ["TELEGRAM_CHAT_ID"]

# Strategy parameters
DELTA_MIN      = 0.20
DELTA_MAX      = 0.35
DTE_MIN        = 21
DTE_MAX        = 45
PROFIT_TARGET  = 0.50   # Close at 50% profit
MAX_POSITIONS  = 5
SENTIMENT_THRESHOLD = 0.85  # Only skip if >85% negative confidence


def notify(msg: str):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown",
                            "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def log_sheets(symbol, contract, premium, status):
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        return
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        key_file = os.path.expanduser("~/Desktop/down/yahoo-portfolio-data-44dbe4ae4313.json")
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        creds = (Credentials.from_service_account_file(key_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
                 if os.path.exists(key_file) else
                 Credentials.from_service_account_info(json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"]))
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range="Trade Journal!A:L",
            valueInputOption="USER_ENTERED",
            body={"values": [[datetime.now().strftime("%Y-%m-%d %H:%M"), symbol,
                              "Covered Call", contract, "", "", "", f"${premium:.2f}", "", "", status, ""]]}
        ).execute()
    except Exception as e:
        print(f"Sheets: {e}")


def is_market_open() -> bool:
    """Check if US market is currently open."""
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(api_key=KEY, secret_key=SECRET, paper=True)
        clock = client.get_clock()
        return clock.is_open
    except:
        return True  # Assume open if can't check


def get_sentiment(symbol: str) -> tuple[str, float]:
    """Returns (label, max_score) from FinBERT on last 24hrs news."""
    try:
        client = NewsClient(api_key=KEY, secret_key=SECRET)
        start = datetime.now(timezone.utc) - timedelta(hours=24)
        news = client.get_news(NewsRequest(symbols=symbol, start=start, limit=5, sort="desc"))
        articles = news.data.get("news", [])
        scores = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
        count = 0
        for a in articles[:5]:
            r = requests.post(
                "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert",
                headers={"Authorization": f"Bearer {HF}"},
                json={"inputs": a.headline[:200]}, timeout=10)
            if r.status_code == 200:
                result = r.json()
                if isinstance(result, list) and result:
                    top = max(result[0], key=lambda x: x["score"])
                    scores[top["label"]] += top["score"]
                    count += 1
        if count == 0:
            return "neutral", 0.0
        # Average scores
        avg = {k: v/count for k, v in scores.items()}
        top_label = max(avg, key=avg.get)
        return top_label, avg[top_label]
    except:
        return "neutral", 0.0


def score_option(delta: float, dte: int, bid: float, strike: float) -> float:
    """
    Smart scoring from Alpaca's wheel strategy:
    (1 - delta) = probability of profit
    (250 / dte) = annualized factor
    (bid / strike) = yield
    """
    return (1 - abs(delta)) * (250 / (dte + 5)) * (bid / strike)


def find_best_call(symbol: str, stock_price: float) -> dict | None:
    """Find best covered call using smart scoring."""
    try:
        client = OptionHistoricalDataClient(api_key=KEY, secret_key=SECRET)
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=datetime.now().date() + timedelta(days=DTE_MIN),
            expiration_date_lte=datetime.now().date() + timedelta(days=DTE_MAX),
        )
        chain = client.get_option_chain(req)
        candidates = []
        for sym, snap in chain.items():
            # Only calls
            try:
                contract_type = sym[len(symbol)+6]
                if contract_type != "C":
                    continue
            except:
                continue

            if snap.greeks is None or snap.implied_volatility is None:
                continue
            if snap.latest_quote is None or not snap.latest_quote.bid_price:
                continue

            delta = snap.greeks.delta
            bid   = snap.latest_quote.bid_price
            oi    = getattr(snap, 'open_interest', 100) or 100

            if not (DELTA_MIN <= delta <= DELTA_MAX):
                continue
            if bid <= 0 or oi < 50:
                continue

            # Parse DTE from symbol
            try:
                expiry_str = sym[len(symbol):len(symbol)+6]
                expiry = datetime.strptime(expiry_str, "%y%m%d").date()
                dte = (expiry - datetime.now().date()).days
            except:
                continue

            # Parse strike
            try:
                strike = int(sym[len(symbol)+7:]) / 1000
            except:
                continue

            score = score_option(delta, dte, bid, strike)
            candidates.append({
                "symbol": sym, "bid": bid, "delta": delta,
                "iv": snap.implied_volatility, "dte": dte,
                "strike": strike, "score": score,
                "premium_pct": round(bid / stock_price * 100, 2)
            })

        if not candidates:
            return None
        # Return highest scoring (best risk-adjusted return)
        return max(candidates, key=lambda x: x["score"])
    except Exception as e:
        print(f"find_best_call error for {symbol}: {e}")
        return None


def is_option_symbol(sym: str) -> bool:
    """Check if symbol is an option contract (OCC format: TSLA260430C00350000)."""
    import re
    return bool(re.search(r'\d{6}[CP]\d{8}', sym))


def close_profitable_positions(trade_client: TradingClient) -> list:
    """Close covered calls that hit 50% profit."""
    closed = []
    positions = trade_client.get_all_positions()
    for p in positions:
        sym = p.symbol
        # Must be short option (negative qty) in OCC format
        if float(p.qty) >= 0 or not is_option_symbol(sym):
            continue
        # Only calls
        import re
        m = re.search(r'\d{6}([CP])', sym)
        if not m or m.group(1) != "C":
            continue
        try:
            entry_price = abs(float(p.avg_entry_price))
            current_price = abs(float(p.current_price))
            qty = abs(int(float(p.qty)))

            # For short options: profit = (entry - current) / entry
            # e.g. sold at $1.00, now $0.40 = 60% profit
            if entry_price > 0:
                profit_pct = (entry_price - current_price) / entry_price
                if profit_pct >= PROFIT_TARGET:
                    trade_client.close_position(sym, close_options=ClosePositionRequest(qty=str(qty)))
                    profit_dollar = (entry_price - current_price) * qty * 100
                    closed.append(f"✅ Closed `{sym}` at {profit_pct:.0%} profit | +${profit_dollar:.2f}")
                    log_sheets(sym[:4], sym, entry_price * qty * 100, "CLOSED")
        except Exception as e:
            closed.append(f"⚠️ Failed to close {sym}: {e}")
    return closed


def run():
    trade_client = TradingClient(api_key=KEY, secret_key=SECRET, paper=True)
    lines = [f"📞 *Covered Call Engine* — {datetime.now().strftime('%b %d %H:%M')}\n"]

    # Check market hours - exit if closed
    if not is_market_open():
        print("Market closed - skipping")
        return

    # Step 1: Close profitable positions
    closed = close_profitable_positions(trade_client)
    if closed:
        lines.append("*Closed positions:*")
        lines.extend(closed)
        lines.append("")

    # Step 2: Count open covered calls
    positions = trade_client.get_all_positions()
    open_calls = [p for p in positions
                  if float(p.qty) < 0 and is_option_symbol(p.symbol) and "C" in p.symbol]

    if len(open_calls) >= MAX_POSITIONS:
        lines.append(f"⏸️ Max {MAX_POSITIONS} positions reached. No new trades.")
        notify("\n".join(lines))
        return

    # Step 3: Find stocks we own 100+ shares of
    owned = {p.symbol: float(p.current_price)
             for p in positions
             if not any(c.isdigit() for c in p.symbol) and float(p.qty) >= 100}

    if not owned:
        lines.append("No stocks owned with 100+ shares.")
        notify("\n".join(lines))
        return

    lines.append(f"Eligible: {', '.join(owned.keys())}\n")

    # Step 4: AI filter + smart scoring + place trades
    new_trades = []
    for symbol, price in owned.items():
        if len(open_calls) + len(new_trades) >= MAX_POSITIONS:
            break
        if any(symbol in p.symbol for p in open_calls):
            continue  # Already have a call on this stock

        # AI sentiment - only skip if STRONGLY negative (>85%)
        label, score = get_sentiment(symbol)
        if label == "negative" and score >= SENTIMENT_THRESHOLD:
            lines.append(f"⛔ `{symbol}` skipped — strong negative news ({score:.0%})")
            continue
        elif label == "negative":
            lines.append(f"⚠️ `{symbol}` weak negative ({score:.0%}) — proceeding cautiously")

        # Find best call using smart scoring
        best = find_best_call(symbol, price)
        if not best:
            lines.append(f"⚪ `{symbol}` — no suitable calls found")
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
            lines.append(
                f"✅ `{symbol}` → Sold `{best['symbol']}`\n"
                f"   Premium: ${premium:.2f} ({best['premium_pct']:.1f}%) | "
                f"IV: {best['iv']:.0%} | DTE: {best['dte']} | δ{best['delta']:.2f}"
            )
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
