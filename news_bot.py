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
from options import get_options_opportunities, format_options_section
from journal import sync_trades
from reddit import get_reddit_sentiment, format_reddit_section
from options_flow import get_unusual_flow, format_flow_section

PORTFOLIO = [
    "POET","AMZN","NVDA","UUUU","PLTR","TSLA",
    "SOFI","META","ACHR","IONQ","PATH","JOBY",
    "OKLO","PYPL","LAES","CRWV","DUOL"
]
WATCHLIST = ["MSFT"]  # Add any symbols you want to watch here
MARKET_ETFS = ["SPY","QQQ","DIA","IWM","TLT","GLD","USO"]
NOISE = ["bitcoin","crypto","penguins","nft","meme","dogecoin"]
MIN_CONFIDENCE = 0.70  # Only show if FinBERT score > 70%


if __name__ == "__main__":
    # Detect run type based on UTC hour
    utc_hour = datetime.utcnow().hour
    if utc_hour == 12:
        hours_back, run_type = 18, "🌅 Morning Digest"    # overnight news
    elif utc_hour == 17:
        hours_back, run_type = 5,  "📊 Midday Digest"     # morning session
    elif utc_hour == 21:
        hours_back, run_type = 9,  "🌆 End of Day Digest" # full trading day
    else:
        hours_back, run_type = 4,  "📊 Portfolio Digest"  # manual/fallback
    # 1. Fetch data
    market_news    = get_news(MARKET_ETFS, hours_back)
    portfolio_news = get_news(PORTFOLIO, hours_back)
    watchlist_news = get_news(WATCHLIST, hours_back) if WATCHLIST else []
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
            save(sym, label, score, a.headline, a.url)
        scored.append({"syms": syms, "label": label, "score": score,
                       "headline": a.headline, "url": a.url})

    positive = [x for x in scored if x["label"] == "positive"]
    negative = [x for x in scored if x["label"] == "negative"]
    neutral  = [x for x in scored if x["label"] == "neutral"]

    # 4. Build message
    lines = [f"{run_type} — {datetime.now().strftime('%b %d %H:%M')}\n"]

    # Market
    lines.append(f"*🌍 Market:* {mkt_mood}")
    for a in market_news[:2]:
        lines.append(f"  • [{a.headline[:65]}...]({a.url})")

    # AI summary
    summary = generate_summary(mkt_mood, positive, negative)
    if summary:
        lines.append(f"\n_{summary}_")

    # Portfolio
    shown_syms = set(s for x in positive + negative for s in x["syms"])
    neutral_filtered = [x for x in neutral if not any(s in shown_syms for s in x["syms"])]

    lines.append(f"\n*📈 Portfolio:* 🟢 {len(positive)}  🔴 {len(negative)}  ⚪ {len(neutral_filtered)}\n")

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
                if s in prices and abs(prices[s]) >= 0.1:  # hide if < 0.1%
                    p = prices[s]
                    price_str = f" {'📈' if p > 0 else '📉'}{p:+.1f}%"
                    break
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

    if neutral_filtered:
        lines.append("\n*⚪ Neutral*")
        lines.extend(fmt(neutral_filtered[:3]))

    # Watchlist section
    if watchlist_news:
        watch_scored = []
        seen_watch = set()
        for a in watchlist_news:
            if a.url in seen_watch:
                continue
            syms = [s for s in a.symbols if s in WATCHLIST]
            if not syms:
                continue
            label, score = get_sentiment(a.summary if a.summary else a.headline)
            if score < MIN_CONFIDENCE:
                continue  # same threshold as portfolio
            seen_watch.add(a.url)
            for sym in syms:
                save(sym, label, score, a.headline, a.url, dedup_key=f"w:{sym}:{a.url}")
            watch_scored.append({"syms": syms, "label": label, "score": score,
                                  "headline": a.headline, "url": a.url})
        if watch_scored:
            lines.append("\n*👀 Watchlist*")
            lines.extend(fmt(watch_scored[:5]))

    # Auto-sync trade journal on morning run
    if run_type == "🌅 Morning Digest":
        sync_trades()

    # Options opportunities (morning + EOD only)
    if run_type != "📊 Portfolio Digest" and prices:
        sym_sentiments = {x["syms"][0]: x["label"] for x in scored if x["syms"]}
        sym_trends = {sym: get_trend(sym) for sym in PORTFOLIO[:8]}
        opps = get_options_opportunities(PORTFOLIO[:8], prices)
        options_section = format_options_section(opps, sym_sentiments, sym_trends, mkt_mood)
        if options_section:
            lines.append(options_section)

        # Reddit sentiment
        reddit_data = get_reddit_sentiment(PORTFOLIO + WATCHLIST)
        reddit_section = format_reddit_section(reddit_data)
        if reddit_section:
            lines.append(reddit_section)

        # Unusual options flow
        flow = get_unusual_flow(PORTFOLIO[:8])
        flow_section = format_flow_section(flow)
        if flow_section:
            lines.append(flow_section)

    # For intraday runs, skip if no bullish/bearish signals
    if run_type == "📊 Portfolio Digest" and len(positive) == 0 and len(negative) == 0:
        print("⏭️  No actionable signals - skipping Telegram message")
    else:
        send("\n".join(lines))
        print(f"✅ Sent: {mkt_mood} | 🟢{len(positive)} 🔴{len(negative)} ⚪{len(neutral_filtered)}")
