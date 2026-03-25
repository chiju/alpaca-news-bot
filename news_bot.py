#!/usr/bin/env python3
"""Alpaca News Bot — sends portfolio news to Telegram. pip install requests"""

import os, requests
from datetime import datetime, timezone, timedelta

# Load from local env file if running locally
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

SYMBOLS = [
    "POET","AMZN","NVDA","UUUU","PLTR","TSLA",
    "SOFI","META","ACHR","IONQ","PATH","JOBY",
    "OKLO","PYPL","LAES","CRWV","DUOL"
]

def fetch_news(hours_back=6, limit=20):
    start = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(
        "https://data.alpaca.markets/v1beta1/news",
        headers={"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET},
        params={"symbols": ",".join(SYMBOLS), "start": start, "limit": limit, "sort": "DESC"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("news", [])

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
        send_telegram("📰 No new portfolio news in the last 6 hours.")
    else:
        lines = [f"📰 *Portfolio News* — {datetime.now().strftime('%b %d %H:%M')}\n"]
        for a in articles:
            syms = " ".join(f"`{s}`" for s in a["symbols"] if s in SYMBOLS)
            lines.append(f"*{a['created_at'][11:16]}* {syms}\n{a['headline']}\n[Read]({a['url']})\n")
        send_telegram("\n".join(lines))
    print(f"Sent {len(articles)} articles.")
