#!/usr/bin/env python3
"""Main orchestrator — runs the full portfolio news digest pipeline."""

import os

# Load local env FIRST before any module imports
_env = os.path.expanduser("~/.alpaca/options-paper.env")
if os.path.exists(_env):
    for line in open(_env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from datetime import datetime
from fetcher import get_news, get_price_changes
from sentiment import get_sentiment, generate_summary
from history import save, get_trend
from notifier import send

PORTFOLIO = [
    "POET","AMZN","NVDA","UUUU","PLTR","TSLA",
    "SOFI","META","ACHR","IONQ","PATH","JOBY",
    "OKLO","PYPL","LAES","CRWV","DUOL"
]
MARKET_ETFS = ["SPY","QQQ","DIA","IWM","TLT","GLD","USO"]
NOISE = ["bitcoin","crypto","penguins","nft","meme","dogecoin"]
MIN_CONFIDENCE = 0.70  # Only show if FinBERT score > 70%


if __name__ == "__main__":
    # 1. Fetch data
    market_news    = get_news(MARKET_ETFS)
    portfolio_news = get_news(PORTFOLIO)
    prices         = get_price_changes(PORTFOLIO)

    # 2. Market sentiment
    mkt_scores = [get_sentiment(a.headline) for a in market_news[:5]]
    mkt_pos = sum(1 for l, _ in mkt_scores if l == "positive")
    mkt_neg = sum(1 for l, _ in mkt_scores if l == "negative")
    mkt_mood = "🟢 Bullish" if mkt_pos > mkt_neg else ("🔴 Bearish" if mkt_neg > mkt_pos else "⚪ Neutral")

    # 3. Score portfolio articles (high confidence only, deduplicated by URL)
    scored = []
    seen_urls = set()
    for a in portfolio_news:
        if a.url in seen_urls:
            continue
        syms = [s for s in a.symbols if s in PORTFOLIO]
        if not syms or any(w in a.headline.lower() for w in NOISE):
            continue
        text = a.summary if a.summary else a.headline
        label, score = get_sentiment(text)
        if score < MIN_CONFIDENCE:
            continue
        seen_urls.add(a.url)
        for sym in syms:
            save(sym, label, score)
        scored.append({"syms": syms, "label": label, "score": score,
                       "headline": a.headline, "url": a.url})

    positive = [x for x in scored if x["label"] == "positive"]
    negative = [x for x in scored if x["label"] == "negative"]
    neutral  = [x for x in scored if x["label"] == "neutral"]

    # 4. Build message
    lines = [f"📊 *Portfolio Digest* — {datetime.now().strftime('%b %d %H:%M')}\n"]

    # Market
    lines.append(f"*🌍 Market:* {mkt_mood}")
    for a in market_news[:2]:
        lines.append(f"  • [{a.headline[:65]}...]({a.url})")

    # AI summary
    summary = generate_summary(mkt_mood, positive, negative)
    if summary:
        lines.append(f"\n_{summary}_")

    # Portfolio
    lines.append(f"\n*📈 Portfolio:* 🟢 {len(positive)}  🔴 {len(negative)}  ⚪ {len(neutral)}\n")

    def fmt(items):
        out = []
        seen_headlines = set()
        for x in items:
            if x["headline"] in seen_headlines:
                continue
            seen_headlines.add(x["headline"])
            syms_str = " ".join(f"`{s}`" for s in x["syms"])
            price_str = ""
            for s in x["syms"]:
                if s in prices and prices[s] != 0.0:
                    p = prices[s]
                    price_str = f" {'📈' if p > 0 else '📉'}{p:+.1f}%"
                    break  # only show price for first matched symbol
            trend = get_trend(x["syms"][0], last_n=3)  # max 3
            conf = f"({x['score']:.0%})"
            out.append(f"• {syms_str}{price_str} {conf} {trend}\n  [{x['headline'][:75]}...]({x['url']})")
        return out

    if positive:
        lines.append("*🟢 Bullish*")
        lines.extend(fmt(positive))

    if negative:
        lines.append("\n*🔴 Bearish*")
        lines.extend(fmt(negative))

    if neutral:
        lines.append("\n*⚪ Neutral*")
        lines.extend(fmt(neutral[:3]))

    send("\n".join(lines))
    print(f"✅ Sent: {mkt_mood} | 🟢{len(positive)} 🔴{len(negative)} ⚪{len(neutral)}")
