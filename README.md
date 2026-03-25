# Alpaca News Bot

AI-powered portfolio news digest sent to Telegram. Monitors your stock portfolio and watchlist for news, analyzes sentiment using FinBERT, and sends structured alerts automatically.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Actions (Scheduler)                  │
│  🌅 8am ET (18hrs)  │  📊 Every 2hrs  │  🌆 4pm ET (9hrs)      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        news_bot.py                              │
│                    (Main Orchestrator)                          │
└──────┬──────────────┬──────────────┬──────────────┬────────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌──────────┐  ┌──────────────┐  ┌─────────┐  ┌──────────┐
│fetcher.py│  │ sentiment.py │  │history.py│  │notifier.py│
│          │  │              │  │          │  │           │
│ Alpaca   │  │  FinBERT     │  │ SQLite   │  │ Telegram  │
│ News API │  │  (HuggingFace│  │  + Git   │  │   Bot     │
│ + Prices │  │   Router)    │  │  + Google│  │           │
│          │  │              │  │  Sheets  │  │           │
└──────────┘  │  Llama 3.1   │  └──────────┘  └──────────┘
              │  (Summary)   │
              └──────────────┘
```

## Data Flow

```
Benzinga News
     │
     ▼
Alpaca News API ──► fetcher.py ──► Filter noise & deduplicate
                                         │
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                    Market ETFs    Portfolio (17)   Watchlist
                   SPY/QQQ/TLT    stocks            MSFT...
                          │              │
                          ▼              ▼
                    sentiment.py ◄───────┘
                          │
                    FinBERT scores each headline
                    🟢 positive / 🔴 negative / ⚪ neutral
                          │
                    Filter: score < 70% → skip
                          │
                    Llama 3.1 → 4-line summary
                          │
                    history.py
                    ├── SQLite (local + committed to repo)
                    └── Google Sheets (visualization)
                          │
                    notifier.py
                          │
                    Telegram Message
```

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
• `META` 📈+1.2% (92%) 🟢🟢⚪  [Meta AI Shopping...]

🔴 Bearish
• `TSLA` 📉-0.8% (90%) 🔴⚪🔴  [SpaceX-Tesla merger caution...]

👀 Watchlist
• `MSFT` (85%) 🟢⚪⚪  [Microsoft AI supercycle...]
```

## Components

| File | Role | External Service |
|------|------|-----------------|
| `news_bot.py` | Orchestrator - runs the pipeline | - |
| `fetcher.py` | Fetches news + price data | Alpaca API |
| `sentiment.py` | FinBERT sentiment + Llama summary | HuggingFace |
| `history.py` | Saves + retrieves sentiment history | SQLite + Google Sheets |
| `notifier.py` | Sends Telegram messages | Telegram Bot API |
| `setup_sheets.py` | One-time Google Sheet header setup | Google Sheets API |

## Intelligence Layer

```
FinBERT (ProsusAI)          Llama 3.1 8B
─────────────────           ────────────────
Financial NLP model         General LLM
Trained on:                 Used for:
- Earnings reports          - 4-line digest summary
- Analyst notes             - Natural language output
- Financial news

Input: headline/summary     Input: scored results
Output: positive/negative/  Output: human-readable
        neutral + score             briefing
```

## Filters & Logic

```
Raw news articles
      │
      ├── Skip if score < 70% confidence
      ├── Skip noise: bitcoin, crypto, nft, meme
      ├── Deduplicate by URL
      ├── Skip neutral if symbol already in bullish/bearish
      └── Watchlist: same filters as portfolio
```

## Persistence

```
Every run:
  sentiment_history.db (SQLite)
       ├── Stored in Git repo (permanent)
       └── Committed back after each run

  Google Sheets
       └── Append row: Date | Time | Symbol | Sentiment | Score | Headline
           → Use for charts, graphs, trend analysis
```

## Schedule (GitHub Actions)

| UTC | ET | Type | News window |
|-----|-----|------|-------------|
| 12:00 Mon-Fri | 8am | 🌅 Morning | Last 18hrs |
| 9,11,13,15,17,19 Mon-Fri | Intraday | 📊 Update | Last 2hrs |
| 21:00 Mon-Fri | 4pm | 🌆 End of Day | Last 9hrs |

## Setup

1. Clone repo
2. Add GitHub Secrets:
   - `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`
   - `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`
   - `HF_TOKEN` (HuggingFace free token)
   - `GOOGLE_CREDENTIALS` (service account JSON)
   - `GOOGLE_SHEET_ID`
3. GitHub Actions runs automatically

## Local Run

```bash
python3 news_bot.py
```
Reads credentials from `~/.alpaca/options-paper.env`
