#!/usr/bin/env python3
"""Alpaca News Bot — uses official alpaca-py SDK + FinBERT sentiment → Telegram."""

import os, requests
from datetime import datetime, timezone, timedelta
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import NewsRequest

# Load local env file if running locally
_env = os.path.expanduser("~/.alpaca/options-paper.env")
if os.path.exists(_env):
    for line in open(_env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

ALPACA_KEY     = os.environ["ALPACA_API_KEY"]
ALPACA_SECRET  = os.environ["ALPACA_SECRET_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT  = os.environ["TELEGRAM_CHAT_ID"]
HF_TOKEN       = os.environ["HF_TOKEN"]

SYMBOLS = [
    "POET","AMZN","NVDA","UUUU","PLTR","TSLA",
    "SOFI","META","ACHR","IONQ","PATH","JOBY",
    "OKLO","PYPL","LAES","CRWV","DUOL"
]

MARKET_SYMBOLS = ["SPY", "QQQ", "VIX", "DIA", "IWM", "SQQQ", "TQQQ"]

SENTIMENT_EMOJI = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}


def fetch_news(hours_back=2):
    client = NewsClient(api_key=ALPACA_KEY, secret_key=ALPACA_SECRET)
    start = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    all_symbols = ",".join(SYMBOLS + MARKET_SYMBOLS)
    req = NewsRequest(symbols=all_symbols, start=start, limit=30, sort="desc")
    response = client.get_news(req)
    return response.data.get("news", [])


def get_sentiment(headline: str) -> str:
    try:
        r = requests.post(
            "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"inputs": headline},
            timeout=15,
        )
        result = r.json()
        if isinstance(result, list) and result:
            top = max(result[0], key=lambda x: x["score"])
            return f"{SENTIMENT_EMOJI.get(top['label'], '⚪')} {top['label']} ({top['score']:.0%})"
    except Exception:
        pass
    return "⚪"


def send_telegram(text):
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": chunk, "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=10,
        ).raise_for_status()


if __name__ == "__main__":
    articles = fetch_news()
    if not articles:
        send_telegram("📰 No new portfolio news in the last 2 hours.")
        print("No news.")
    else:
        # Separate portfolio vs market news
        portfolio_articles = []
        market_articles = []
        for a in articles:
            port_syms = [s for s in a.symbols if s in SYMBOLS]
            mkt_syms  = [s for s in a.symbols if s in MARKET_SYMBOLS]
            if port_syms:
                portfolio_articles.append((port_syms, a))
            elif mkt_syms:
                market_articles.append((mkt_syms, a))

        # Score portfolio articles - skip noise (crypto/unrelated)
        scored = []
        for syms, a in portfolio_articles:
            # Skip if headline is clearly not about the stock
            headline_lower = a.headline.lower()
            if any(w in headline_lower for w in ["bitcoin", "crypto", "penguins", "nft", "meme"]):
                continue
            sentiment = get_sentiment(a.headline)
            scored.append({"syms": syms, "sentiment": sentiment, "headline": a.headline, "url": a.url})

        positive = [x for x in scored if "🟢" in x["sentiment"]]
        negative = [x for x in scored if "🔴" in x["sentiment"]]
        neutral  = [x for x in scored if "⚪"  in x["sentiment"]]

        lines = [f"📊 *Portfolio Digest* — {datetime.now().strftime('%b %d %H:%M')}\n"]

        # Overall market section
        if market_articles:
            mkt_sentiments = [get_sentiment(a.headline) for _, a in market_articles[:5]]
            mkt_pos = sum(1 for s in mkt_sentiments if "🟢" in s)
            mkt_neg = sum(1 for s in mkt_sentiments if "🔴" in s)
            if mkt_pos > mkt_neg:
                mkt_mood = "🟢 Bullish"
            elif mkt_neg > mkt_pos:
                mkt_mood = "🔴 Bearish"
            else:
                mkt_mood = "⚪ Neutral"
            lines.append(f"*🌍 Market Sentiment:* {mkt_mood}")
            for _, a in market_articles[:3]:
                lines.append(f"  • [{a.headline[:70]}...]({a.url})")
            lines.append("")

        # Portfolio summary
        lines.append(f"*📈 Portfolio:* 🟢 {len(positive)}  🔴 {len(negative)}  ⚪ {len(neutral)}\n")

        if positive:
            lines.append("*🟢 Bullish*")
            for x in positive:
                syms = " ".join(f"`{s}`" for s in x["syms"])
                lines.append(f"• {syms} [{x['headline'][:80]}...]({x['url']})")

        if negative:
            lines.append("\n*🔴 Bearish*")
            for x in negative:
                syms = " ".join(f"`{s}`" for s in x["syms"])
                lines.append(f"• {syms} [{x['headline'][:80]}...]({x['url']})")

        if neutral:
            lines.append("\n*⚪ Neutral* (FYI)")
            for x in neutral[:3]:  # max 3 neutral items
                syms = " ".join(f"`{s}`" for s in x["syms"])
                lines.append(f"• {syms} [{x['headline'][:80]}...]({x['url']})")

        send_telegram("\n".join(lines))
        print(f"Sent digest: {len(positive)}🟢 {len(negative)}🔴 {len(neutral)}⚪")
