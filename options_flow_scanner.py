"""
Options Flow Scanner — Unusual activity detector for S&P, Nasdaq ETFs + portfolio stocks.
Sends Telegram alerts when smart money is detected.

Usage:
    python options_flow_scanner.py            # run once
    python options_flow_scanner.py --loop     # run every 30 min during market hours
"""
import os, sys, time, argparse
from datetime import datetime, timedelta
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest
import requests

# ── Watchlist ────────────────────────────────────────────────────────────────
INDEX_ETFS = ["SPY", "QQQ", "IWM"]          # S&P 500, Nasdaq, Russell 2000

PORTFOLIO   = [                              # your holdings
    "MSFT", "NVDA", "AMZN", "META", "TSLA",
    "PLTR", "CRWV", "IONQ", "OKLO", "ACHR",
    "DUOL", "SOFI", "PYPL", "PATH", "JOBY",
    "UUUU", "POET",
]

MEGA_CAPS   = ["AAPL", "GOOGL", "MSFT", "NVDA", "AMZN", "META", "TSLA"]

ALL_SYMBOLS = list(dict.fromkeys(INDEX_ETFS + PORTFOLIO + MEGA_CAPS))  # deduped

# ── Thresholds ────────────────────────────────────────────────────────────────
UNUSUAL_VOL_OI_RATIO = 1.5   # volume > 1.5× open interest
MIN_PREMIUM          = 25000  # $25k minimum notional (filters noise)
MAX_DTE              = 45     # only look at options expiring within 45 days
OTM_CALL_DELTA_MAX   = 0.45  # OTM calls have delta < 0.45
SWEEP_RATIO          = 3.0   # 3× OI = likely institutional sweep

# ── Credentials ──────────────────────────────────────────────────────────────
def _key():    return os.environ.get("ALPACA_API_KEY", "")
def _secret(): return os.environ.get("ALPACA_SECRET_KEY", "")
def _tg_token(): return os.environ.get("TELEGRAM_BOT_TOKEN", "")
def _tg_chat():  return os.environ.get("TELEGRAM_CHAT_ID", "")


# ── Core scanner ─────────────────────────────────────────────────────────────
def scan_symbol(client: OptionHistoricalDataClient, sym: str) -> dict:
    """Scan one symbol. Returns {calls: [...], puts: [...], pc_ratio: float}"""
    today = datetime.now().date()
    cutoff = today + timedelta(days=MAX_DTE)

    try:
        req = OptionChainRequest(
            underlying_symbol=sym,
            expiration_date_gte=today,
            expiration_date_lte=cutoff,
        )
        chain = client.get_option_chain(req)
    except Exception as e:
        print(f"  [{sym}] chain error: {e}")
        return None

    calls, puts = [], []
    total_call_vol = total_put_vol = 0

    for contract_sym, snap in chain.items():
        if snap.latest_quote is None:
            continue

        # Parse contract metadata from OCC symbol
        try:
            offset = len(sym)
            cp = contract_sym[offset + 6]
            strike = int(contract_sym[offset + 7:]) / 1000
            expiry_str = contract_sym[offset:offset + 6]
            expiry_date = datetime.strptime(expiry_str, "%y%m%d").date()
            expiry_fmt = expiry_date.strftime("%b %d")
            dte = (expiry_date - today).days
        except Exception:
            continue

        bid = snap.latest_quote.bid_price or 0
        ask = snap.latest_quote.ask_price or 0
        mid = (bid + ask) / 2 if ask else bid

        # Use daily bar volume if available, else 0
        volume = 0
        if snap.daily_bar:
            volume = snap.daily_bar.volume or 0

        oi = 0  # OI not always in chain snapshot; use volume signal only

        # Greeks
        delta = iv = None
        if snap.greeks:
            delta = snap.greeks.delta
            iv = snap.implied_volatility

        if cp == "C":
            total_call_vol += volume
        else:
            total_put_vol += volume

        if volume == 0 or mid == 0:
            continue

        premium = mid * volume * 100
        if premium < MIN_PREMIUM:
            continue

        entry = {
            "symbol":   sym,
            "contract": contract_sym,
            "type":     "CALL" if cp == "C" else "PUT",
            "strike":   strike,
            "expiry":   expiry_fmt,
            "dte":      dte,
            "volume":   int(volume),
            "premium":  int(premium),
            "delta":    round(delta, 2) if delta else None,
            "iv":       round(iv * 100, 1) if iv else None,
            "mid":      round(mid, 2),
        }

        # Tag as sweep if very high volume
        entry["sweep"] = volume > 500 and cp == "C"  # large call block = sweep signal

        if cp == "C":
            calls.append(entry)
        else:
            puts.append(entry)

    pc_ratio = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else None

    return {
        "symbol":   sym,
        "calls":    sorted(calls, key=lambda x: x["premium"], reverse=True),
        "puts":     sorted(puts,  key=lambda x: x["premium"], reverse=True),
        "pc_ratio": pc_ratio,
        "call_vol": int(total_call_vol),
        "put_vol":  int(total_put_vol),
    }


def interpret_signal(result: dict) -> str:
    """Return a human-readable signal based on flow."""
    pc = result["pc_ratio"]
    if pc is None:
        return "⚪ No data"
    if pc < 0.3:
        return "🔥 Very Bullish"
    if pc < 0.6:
        return "🟢 Bullish"
    if pc < 1.0:
        return "🟡 Neutral"
    if pc < 1.5:
        return "🟠 Cautious"
    return "🔴 Bearish"


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(text: str):
    token, chat = _tg_token(), _tg_chat()
    if not token or not chat:
        print("⚠️  No Telegram credentials — printing to console only.")
        print(text)
        return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": chunk,
                      "parse_mode": "Markdown", "disable_web_page_preview": True},
                timeout=10,
            )
            if not r.ok:
                print(f"Telegram error: {r.text}")
        except Exception as e:
            print(f"Telegram error: {e}")


# ── Formatter ─────────────────────────────────────────────────────────────────
def format_report(results: list) -> str:
    now = datetime.now().strftime("%b %d %H:%M")
    lines = [f"*📊 Options Flow Scanner — {now}*\n"]

    # ── Index ETFs section ──
    lines.append("*🏛 Index ETFs (S&P / Nasdaq / Russell)*")
    for r in results:
        if r["symbol"] not in INDEX_ETFS:
            continue
        sig = interpret_signal(r)
        pc = r["pc_ratio"]
        lines.append(
            f"`{r['symbol']}` {sig} | P/C: {pc if pc else 'N/A'} "
            f"| Calls: {r['call_vol']:,} | Puts: {r['put_vol']:,}"
        )
        # Top call
        if r["calls"]:
            c = r["calls"][0]
            sweep = " 🚨SWEEP" if c["sweep"] else ""
            lines.append(
                f"  ↳ Top CALL: ${c['strike']:.0f} {c['expiry']} "
                f"| Vol: {c['volume']:,} | 💰 ${c['premium']:,}{sweep}"
            )

    # ── Unusual flow across all symbols ──
    all_unusual = []
    for r in results:
        for c in r["calls"][:3]:
            if c["volume"] > 200:
                c["_sym"] = r["symbol"]
                all_unusual.append(c)
        for p in r["puts"][:2]:
            if p["volume"] > 200:
                p["_sym"] = r["symbol"]
                all_unusual.append(p)

    all_unusual.sort(key=lambda x: x["premium"], reverse=True)

    if all_unusual:
        lines.append("\n*🐳 Top Unusual Flow (Smart Money)*")
        lines.append("_Sorted by premium size_\n")
        for f in all_unusual[:8]:
            sweep_tag = " 🚨" if f.get("sweep") else ""
            side = "🐂" if f["type"] == "CALL" else "🐻"
            iv_str = f" IV:{f['iv']}%" if f["iv"] else ""
            delta_str = f" Δ{f['delta']}" if f["delta"] else ""
            lines.append(
                f"{side} `{f['_sym']}` {f['type']} ${f['strike']:.0f} {f['expiry']} "
                f"| Vol: {f['volume']:,}{iv_str}{delta_str} "
                f"| 💰 ${f['premium']:,}{sweep_tag}"
            )

    # ── Portfolio summary ──
    lines.append("\n*💼 Portfolio Stocks Flow*")
    for r in results:
        if r["symbol"] not in PORTFOLIO:
            continue
        if r["call_vol"] == 0 and r["put_vol"] == 0:
            continue
        sig = interpret_signal(r)
        pc = r["pc_ratio"]
        lines.append(
            f"`{r['symbol']}` {sig} | P/C: {pc if pc else 'N/A'} "
            f"| C:{r['call_vol']:,} P:{r['put_vol']:,}"
        )

    lines.append("\n_Options flow is a leading indicator. Not financial advice._")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────
def run_scan():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting options flow scan...")
    client = OptionHistoricalDataClient(api_key=_key(), secret_key=_secret())

    results = []
    for sym in ALL_SYMBOLS:
        print(f"  Scanning {sym}...")
        r = scan_symbol(client, sym)
        if r:
            results.append(r)

    if not results:
        print("No results.")
        return

    report = format_report(results)
    send_telegram(report)
    print("✅ Report sent.")


def is_market_hours() -> bool:
    now = datetime.utcnow()
    # Mon-Fri, 13:30-20:00 UTC (9:30am-4pm ET)
    if now.weekday() >= 5:
        return False
    return time.struct_time(now.timetuple()).tm_hour * 60 + now.minute >= 810 and \
           time.struct_time(now.timetuple()).tm_hour * 60 + now.minute <= 1200


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run every 30 min during market hours")
    args = parser.parse_args()

    if args.loop:
        print("Running in loop mode (every 30 min during market hours)...")
        while True:
            if is_market_hours():
                run_scan()
            else:
                print(f"[{datetime.now().strftime('%H:%M')}] Market closed, sleeping...")
            time.sleep(1800)  # 30 minutes
    else:
        run_scan()
