#!/usr/bin/env python3
"""
Bull Put Spread Engine
- Sell higher strike PUT + Buy lower strike PUT
- Capital needed = spread width × 100 (e.g. $5 spread = $500)
- Max profit = net premium collected
- Max loss = spread width - premium
- Target: 20%+ return on capital, 30-45 DTE, delta 0.20-0.30
"""
import os, requests, json
from datetime import datetime, timezone, timedelta
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, OrderClass
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest

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
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT  = os.environ["TELEGRAM_CHAT_ID"]

# Strategy parameters
SPREAD_WIDTH   = 5      # $5 between strikes = $500 capital per spread
DTE_MIN        = 30
DTE_MAX        = 45
DELTA_MIN      = 0.20   # Sell strike delta
DELTA_MAX      = 0.30
MIN_PREMIUM    = 0.80   # Min $0.80 net credit ($80 per spread)
MIN_ROC        = 0.15   # Min 15% return on capital
MAX_POSITIONS  = 5
PROFIT_TARGET  = 0.50   # Close at 50% profit

# Stocks to trade (too expensive for full CSP)
SYMBOLS = ["NVDA", "AMZN", "PLTR", "CRWV", "META", "TSLA", "DUOL"]


def notify(msg: str):
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "Markdown",
                            "disable_web_page_preview": True}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")


def log_sheets(symbol, sell_contract, buy_contract, net_credit, capital, status):
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
            body={"values": [[
                datetime.now().strftime("%Y-%m-%d %H:%M"), symbol,
                "Bull Put Spread",
                f"{sell_contract} / {buy_contract}",
                "", "", "",
                f"${net_credit * 100:.2f}",
                f"${capital}",
                "", status, ""
            ]]}
        ).execute()
    except Exception as e:
        print(f"Sheets: {e}")
    try:
        client = TradingClient(api_key=KEY, secret_key=SECRET, paper=True)
        return client.get_clock().is_open
    except:
        return True


def find_best_spread(symbol: str, stock_price: float) -> dict | None:
    """Find best bull put spread: sell higher PUT, buy lower PUT."""
    try:
        client = OptionHistoricalDataClient(api_key=KEY, secret_key=SECRET)
        req = OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=datetime.now().date() + timedelta(days=DTE_MIN),
            expiration_date_lte=datetime.now().date() + timedelta(days=DTE_MAX),
        )
        chain = client.get_option_chain(req)

        # Collect all puts with valid data
        puts = {}
        for sym, snap in chain.items():
            import re
            m = re.search(r'\d{6}([CP])\d{8}', sym)
            if not m or m.group(1) != "P":
                continue
            if snap.greeks is None or snap.latest_quote is None:
                continue
            bid = snap.latest_quote.bid_price or 0
            ask = snap.latest_quote.ask_price or 0
            if bid <= 0:
                continue

            try:
                offset = len(symbol)
                strike = int(sym[offset + 7:]) / 1000
                expiry_str = sym[offset:offset + 6]
                dte = (datetime.strptime(expiry_str, "%y%m%d").date() - datetime.now().date()).days
                expiry = datetime.strptime(expiry_str, "%y%m%d").strftime("%b %d")
            except:
                continue

            puts[strike] = {
                "symbol": sym, "bid": bid, "ask": ask,
                "delta": abs(snap.greeks.delta),
                "dte": dte, "expiry": expiry, "strike": strike
            }

        if not puts:
            return None

        # Find sell leg: delta 0.20-0.30
        candidates = []
        for strike, data in puts.items():
            if not (DELTA_MIN <= data["delta"] <= DELTA_MAX):
                continue

            # Find buy leg: SPREAD_WIDTH below sell strike
            buy_strike = strike - SPREAD_WIDTH
            if buy_strike not in puts:
                # Try nearest available strike
                available = [s for s in puts.keys() if s < strike]
                if not available:
                    continue
                buy_strike = max(s for s in available if s <= strike - SPREAD_WIDTH + 1)

            buy_data = puts.get(buy_strike)
            if not buy_data:
                continue

            # Net credit = sell bid - buy ask
            net_credit = data["bid"] - buy_data["ask"]
            if net_credit < MIN_PREMIUM:
                continue

            spread_width = strike - buy_strike
            capital = spread_width * 100
            max_loss = capital - (net_credit * 100)
            roc = (net_credit * 100) / capital

            if roc < MIN_ROC:
                continue

            candidates.append({
                "sell_symbol": data["symbol"],
                "buy_symbol":  buy_data["symbol"],
                "sell_strike": strike,
                "buy_strike":  buy_strike,
                "net_credit":  round(net_credit, 2),
                "capital":     capital,
                "max_loss":    round(max_loss, 2),
                "roc":         round(roc * 100, 1),
                "delta":       data["delta"],
                "dte":         data["dte"],
                "expiry":      data["expiry"],
            })

        if not candidates:
            return None

        # Best = highest ROC
        return max(candidates, key=lambda x: x["roc"])

    except Exception as e:
        print(f"find_best_spread error {symbol}: {e}")
        return None


def close_profitable_spreads(trade_client: TradingClient) -> list:
    """Close spreads that hit 50% profit."""
    import re
    closed = []
    positions = trade_client.get_all_positions()

    short_puts = {p.symbol: p for p in positions
                  if float(p.qty) < 0 and re.search(r'\d{6}P\d{8}', p.symbol)}

    for sym, p in short_puts.items():
        entry = abs(float(p.avg_entry_price))
        current = abs(float(p.current_price))
        if entry > 0 and (entry - current) / entry >= PROFIT_TARGET:
            try:
                trade_client.close_position(sym)
                closed.append(f"✅ Closed short PUT `{sym}` at 50% profit")
            except Exception as e:
                closed.append(f"⚠️ Failed to close {sym}: {e}")

    return closed


def run():
    if not is_market_open():
        print("Market closed")
        return

    trade_client = TradingClient(api_key=KEY, secret_key=SECRET, paper=True)
    lines = [f"📊 *Bull Put Spread Engine* — {datetime.now().strftime('%b %d %H:%M')}\n"]

    # Close profitable positions
    closed = close_profitable_spreads(trade_client)
    if closed:
        lines.append("*Closed:*")
        lines.extend(closed)
        lines.append("")

    # Count open spreads
    import re
    positions = trade_client.get_all_positions()
    open_spreads = [p for p in positions
                    if float(p.qty) < 0 and re.search(r'\d{6}P\d{8}', p.symbol)]

    if len(open_spreads) >= MAX_POSITIONS:
        lines.append(f"⏸️ Max {MAX_POSITIONS} positions reached.")
        notify("\n".join(lines))
        return

    # Get stock prices
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestBarRequest
    stock_client = StockHistoricalDataClient(api_key=KEY, secret_key=SECRET)
    bars = stock_client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols=SYMBOLS))
    prices = {sym: bar.close for sym, bar in bars.items()}

    # Find and place spreads
    new_trades = 0
    for symbol in SYMBOLS:
        if len(open_spreads) + new_trades >= MAX_POSITIONS:
            break

        # Skip if already have a spread on this stock
        if any(symbol in p.symbol for p in open_spreads):
            continue

        price = prices.get(symbol)
        if not price:
            continue

        spread = find_best_spread(symbol, price)
        if not spread:
            lines.append(f"⚪ `{symbol}` — no suitable spread found")
            continue

        # Place as two separate orders (leg by leg)
        try:
            # Sell higher strike PUT
            trade_client.submit_order(MarketOrderRequest(
                symbol=spread["sell_symbol"], qty=1,
                side=OrderSide.SELL, time_in_force=TimeInForce.DAY
            ))
            # Buy lower strike PUT
            trade_client.submit_order(MarketOrderRequest(
                symbol=spread["buy_symbol"], qty=1,
                side=OrderSide.BUY, time_in_force=TimeInForce.DAY
            ))

            new_trades += 1
            log_sheets(symbol, spread["sell_symbol"], spread["buy_symbol"],
                      spread["net_credit"], spread["capital"], "OPEN")
            lines.append(
                f"✅ `{symbol}` Bull Put Spread\n"
                f"   Sell ${spread['sell_strike']:.0f}P / Buy ${spread['buy_strike']:.0f}P "
                f"| Exp: {spread['expiry']} ({spread['dte']}d)\n"
                f"   Credit: ${spread['net_credit']:.2f} | Capital: ${spread['capital']} "
                f"| ROC: {spread['roc']}% | δ{spread['delta']:.2f}"
            )
        except Exception as e:
            lines.append(f"⚠️ `{symbol}` order failed: {e}")

    if not new_trades and not closed:
        lines.append("No new spreads placed.")

    msg = "\n".join(lines)
    notify(msg)
    print(msg)


if __name__ == "__main__":
    run()
