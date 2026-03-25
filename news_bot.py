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

SENTIMENT_EMOJI = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}


def fetch_news(hours_back=2):
    client = NewsClient(api_key=ALPACA_KEY, secret_key=ALPACA_SECRET)
    start = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    req = NewsRequest(symbols=",".join(SYMBOLS), start=start, limit=20, sort="desc")
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
        # Score each article
        scored = []
        for a in articles:
            syms = [s for s in a.symbols if s in SYMBOLS]
            if not syms:
                continue
            sentiment = get_sentiment(a.headline)
            scored.append({"syms": syms, "sentiment": sentiment, "headline": a.headline, "url": a.url, "time": str(a.created_at)[11:16]})

        # Group by sentiment
        positive = [x for x in scored if "🟢" in x["sentiment"]]
        negative = [x for x in scored if "🔴" in x["sentiment"]]
        neutral  = [x for x in scored if "⚪"  in x["sentiment"]]

        lines = [f"📊 *Portfolio Digest* — {datetime.now().strftime('%b %d %H:%M')}\n"]
        lines.append(f"🟢 {len(positive)} positive  🔴 {len(negative)} negative  ⚪ {len(neutral)} neutral\n")

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
            lines.append("\n*⚪ Neutral*")
            for x in neutral:
                syms = " ".join(f"`{s}`" for s in x["syms"])
                lines.append(f"• {syms} [{x['headline'][:80]}...]({x['url']})")

        send_telegram("\n".join(lines))
        print(f"Sent digest: {len(positive)}🟢 {len(negative)}🔴 {len(neutral)}⚪")
