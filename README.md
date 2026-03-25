# Alpaca News Bot

AI-powered portfolio news digest sent to Telegram. Monitors your stock portfolio and watchlist for news, analyzes sentiment using FinBERT, and sends structured alerts automatically.

## What It Does

- **Fetches news** from Alpaca (Benzinga source) for your portfolio + watchlist
- **Analyzes sentiment** using FinBERT (financial AI model) — positive/negative/neutral
- **Tracks sentiment history** per stock in local SQLite DB
- **Generates 4-line summary** using Llama 3.1 8B via HuggingFace
- **Sends to Telegram** as a structured digest with market + portfolio breakdown

## Digest Format

```
🌅 Morning Digest — Mar 25 08:00

🌍 Market: 🔴 Bearish
  • Iran ceasefire talks collapse...
  • Oil hits $150 warning from BlackRock...

• Market bearish on oil/Iran concerns.
• META positive on AI shopping expansion.
• TSLA negative on merger uncertainty.
• Caution advised for aggressive positions.

📈 Portfolio: 🟢 2  🔴 1  ⚪ 0

🟢 Bullish
• `META` (92%) 🟢🟢⚪  [Meta AI Shopping...]

🔴 Bearish
• `TSLA` (90%) 🔴⚪🔴  [SpaceX-Tesla merger caution...]

👀 Watchlist
• `MSFT` (85%) 🟢⚪⚪  [Microsoft AI supercycle...]
```

## Schedule (GitHub Actions)

| Time (UTC) | ET | Type |
|---|---|---|
| 12:00 Mon-Fri | 8am | 🌅 Morning Digest (18hrs of news) |
| 9,11,13,15,17,19 Mon-Fri | Intraday | 📊 2-hour update |
| 21:00 Mon-Fri | 4pm | 🌆 End of Day Digest (9hrs) |

## Modules

| File | Purpose |
|------|---------|
| `news_bot.py` | Main orchestrator |
| `fetcher.py` | Alpaca news + price data |
| `sentiment.py` | FinBERT + Llama summary |
| `history.py` | Sentiment trend (SQLite) |
| `notifier.py` | Telegram sender |

## Setup

1. Clone repo
2. Add GitHub Secrets:
   - `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
   - `HF_TOKEN` (HuggingFace free token)
3. GitHub Actions runs automatically

## Local Run

```bash
python3 news_bot.py
```
Reads credentials from `~/.alpaca/options-paper.env`
