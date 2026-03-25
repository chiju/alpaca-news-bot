"""Options flow tracker - finds best covered call and CSP opportunities."""
import os
from datetime import datetime, timedelta
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest

KEY    = os.environ["ALPACA_API_KEY"]
SECRET = os.environ["ALPACA_SECRET_KEY"]


def get_options_opportunities(symbols: list, stock_prices: dict) -> list:
    """Find best covered call + CSP opportunities for portfolio stocks."""
    client = OptionHistoricalDataClient(api_key=KEY, secret_key=SECRET)
    opportunities = []

    for sym in symbols:
        price = stock_prices.get(sym)
        if not price or price <= 0:
            continue
        try:
            req = OptionChainRequest(
                underlying_symbol=sym,
                expiration_date_gte=datetime.now().date(),
                expiration_date_lte=(datetime.now() + timedelta(days=45)).date(),
            )
            chain = client.get_option_chain(req)

            calls, puts = [], []
            for contract_sym, snap in chain.items():
                if snap.greeks is None or snap.implied_volatility is None:
                    continue
                if snap.latest_quote.bid_price is None or snap.latest_quote.bid_price <= 0:
                    continue

                delta = abs(snap.greeks.delta)
                iv    = snap.implied_volatility
                bid   = snap.latest_quote.bid_price
                theta = abs(snap.greeks.theta) if snap.greeks.theta else 0

                # Parse expiry from symbol (format: SYM YYMMDD C/P STRIKE)
                try:
                    expiry_str = contract_sym[len(sym):len(sym)+6]
                    expiry = datetime.strptime(expiry_str, "%y%m%d").date()
                    dte = (expiry - datetime.now().date()).days
                except:
                    continue

                if dte < 7 or dte > 45:
                    continue

                entry = {
                    "sym": sym, "contract": contract_sym, "iv": iv,
                    "delta": snap.greeks.delta, "theta": theta,
                    "bid": bid, "dte": dte, "expiry": str(expiry),
                    "premium_pct": round(bid / price * 100, 2)
                }

                # Covered call: OTM calls (delta 0.20-0.35)
                if "C" in contract_sym[len(sym)+6] and 0.20 <= delta <= 0.35:
                    calls.append(entry)

                # CSP: OTM puts (delta 0.20-0.35)
                if "P" in contract_sym[len(sym)+6] and 0.20 <= delta <= 0.35:
                    puts.append(entry)

            # Best covered call: highest premium % with good theta
            if calls:
                best_call = max(calls, key=lambda x: x["premium_pct"])
                best_call["type"] = "Covered Call"
                opportunities.append(best_call)

            # Best CSP: highest premium % 
            if puts:
                best_put = max(puts, key=lambda x: x["premium_pct"])
                best_put["type"] = "Cash-Secured Put"
                opportunities.append(best_put)

        except Exception as e:
            continue

    return sorted(opportunities, key=lambda x: x["premium_pct"], reverse=True)


def get_ai_recommendation(sym: str, opp: dict, sentiment_label: str, trend: str, mkt_mood: str) -> str:
    """Ask Llama to analyze the options opportunity with context."""
    import requests, os
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
    if not HF_TOKEN:
        return ""

    prompt = f"""You are an options trading advisor. Analyze this opportunity in 2 lines max:

Stock: {sym}
Trade: Sell {opp['type']} | Premium: {opp['premium_pct']:.1f}% | IV: {opp['iv']:.0%} | DTE: {opp['dte']} days | Delta: {opp['delta']:.2f}
News sentiment today: {sentiment_label}
Recent sentiment trend: {trend}
Market mood: {mkt_mood}

Give a 2-line recommendation: should they sell this contract now? Consider IV, sentiment, and risk."""

    try:
        r = requests.post(
            "https://router.huggingface.co/novita/v3/openai/chat/completions",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"model": "meta-llama/llama-3.1-8b-instruct",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 80},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return ""


def format_options_section(opportunities: list, sentiments: dict = None, trends: dict = None, mkt_mood: str = "") -> str:
    if not opportunities:
        return ""

    lines = ["\n*⚡ Options Opportunities*"]
    lines.append("_(Delta 0.20-0.35, 7-45 DTE)_\n")

    for o in opportunities[:4]:  # top 4 with AI analysis
        type_emoji = "📞" if "Call" in o["type"] else "📤"
        lines.append(
            f"{type_emoji} `{o['sym']}` {o['type']} | "
            f"Bid: ${o['bid']:.2f} ({o['premium_pct']:.1f}%) | "
            f"IV: {o['iv']:.0%} | DTE: {o['dte']} | δ{o['delta']:.2f}"
        )
        # Add AI recommendation if context available
        if sentiments and trends:
            sentiment = sentiments.get(o['sym'], 'neutral')
            trend = trends.get(o['sym'], '')
            ai_rec = get_ai_recommendation(o['sym'], o, sentiment, trend, mkt_mood)
            if ai_rec:
                lines.append(f"  _💡 {ai_rec}_")
        lines.append("")

    return "\n".join(lines)
