# Alpaca Portfolio Bot

AI-powered portfolio news digest + automated options trading strategies.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ALPACA PORTFOLIO BOT                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📰 NEWS INTELLIGENCE          🤖 TRADING ENGINE               │
│  ─────────────────             ──────────────────              │
│  Alpaca News API               run_strategy.py                 │
│       ↓                              ↓                         │
│  FinBERT Sentiment             ┌─────┴──────┐                  │
│  (🟢🔴⚪ per headline)         │            │                  │
│       ↓                      WHEEL        CSP                  │
│  Llama 3.1 Summary          Strategy    Strategy               │
│       ↓                    ($980k acct) ($100k acct)           │
│  Reddit Buzz                    ↓            ↓                 │
│       ↓                   Sentiment    BaseStrategy            │
│  Options Flow               Filter      (rules engine)         │
│       ↓                        ↓            ↓                  │
│  Telegram Digest           Alpaca Paper Trading                │
│  (3x/day)                                                      │
│                                                                 │
│  📊 HISTORY & REPORTING        🛡️ RISK MANAGEMENT              │
│  ──────────────────            ──────────────────              │
│  SQLite (local)                Max 20% per trade               │
│  Google Sheets (cloud)         Max 5 positions                 │
│  Sentiment trends (🟢🔴⚪)     2% daily loss limit             │
│  Daily P&L Report              50% profit target               │
│  (4pm ET → Telegram)           2x stop loss                    │
│                                7-day expiry close              │
└─────────────────────────────────────────────────────────────────┘
```

## Feature Status

```
✅ BUILT & WORKING                    🔲 TODO
──────────────────                    ──────
✅ News digest (3x/day)               🔲 strategies/covered_call.py
✅ FinBERT sentiment analysis         🔲 strategies/bull_put.py
✅ Llama 3.1 AI summary               🔲 Backtesting engine
✅ Reddit sentiment tracking          🔲 Win rate / Sharpe ratio dashboard
✅ Unusual options flow               🔲 Live trading (after 4-5mo paper)
✅ Google Sheets history              🔲 Multi-strategy performance compare
✅ Sentiment trend dots (🟢🔴⚪)      🔲 Email/WhatsApp alerts
✅ Wheel strategy (CSP + CC)          🔲 Portfolio rebalancing
✅ CSP strategy (separate account)    🔲 Tax lot tracking
✅ Bull Put Spread strategy           🔲 Options Greeks dashboard
✅ Iron Condor strategy               🔲 Earnings calendar integration
✅ Covered Call strategy              🔲 Macro event alerts (Fed, CPI)
✅ 5 isolated paper accounts          🔲 Backtesting engine
✅ Sentiment filter (blocks -85%)     🔲 Win rate / Sharpe ratio dashboard
✅ Daily P&L report                   🔲 Live trading (after 4-5mo paper)
✅ GitHub Actions automation          🔲 Multi-strategy performance compare
✅ Per-symbol blocking                🔲 Cloud deployment (post-validation)
✅ Modular strategy architecture
```

## Data Flow

```
Every 30min (market hours):
─────────────────────────
Alpaca News → FinBERT → SQLite/Sheets
                ↓
         Sentiment DB
                ↓
    run_strategy.py checks DB
                ↓
    Block stocks with >85% negative
                ↓
    Execute wheel/CSP on clean stocks
                ↓
    Telegram notification

3x/day (8am, 12pm, 4pm ET):
────────────────────────────
News + Reddit + Options Flow
         ↓
    FinBERT scores
         ↓
    Llama summary
         ↓
    Telegram digest

4pm ET daily:
─────────────
Both accounts → P&L report → Telegram
```

## Architecture

```
alpaca-news-bot/
│
├── news_bot.py          # News digest orchestrator
├── run_strategy.py      # Strategy runner entry point
├── daily_report.py      # Daily P&L report
├── config_loader.py     # Credential loader (local + GitHub Actions)
│
├── core/
│   ├── broker.py        # Alpaca API facade (single entry point for all API calls)
│   └── risk.py          # Position sizing + daily loss limits
│
├── strategies/
│   ├── base.py          # Base class (enforces all trading rules)
│   ├── csp.py           # Cash-Secured Put strategy
│   ├── covered_call.py  # Covered Call (TODO)
│   └── bull_put.py      # Bull Put Spread (TODO)
│
├── strategy_config/
│   └── params.py        # All strategy parameters (single source of truth)
│
├── wheel/               # Official Alpaca wheel strategy (CSP + Covered Call cycle)
│   ├── core/            # Broker client, state manager, execution
│   ├── config/          # Params, credentials, symbol list
│   └── scripts/         # run_strategy.py entry point
│
├── fetcher.py           # Alpaca news API wrapper
├── sentiment.py         # FinBERT sentiment + Llama 3.1 summary via HuggingFace
├── history.py           # SQLite (local) + Google Sheets (cloud) sentiment history
├── notifier.py          # Telegram sender
├── reddit.py            # Reddit sentiment (r/wallstreetbets, r/stocks)
└── options_flow.py      # Unusual options activity detector
```

## What It Does

### 1. News Digest (3x/day)
- Fetches news from Alpaca (Benzinga source) for 17 portfolio stocks + watchlist
- **FinBERT AI** classifies each headline: 🟢 positive / 🔴 negative / ⚪ neutral
- **Llama 3.1 8B** generates a 4-line market summary
- Checks Reddit buzz (r/wallstreetbets, r/stocks, r/investing)
- Detects unusual options flow (volume > 2× open interest)
- Sends structured digest to Telegram
- Logs all sentiment to SQLite + Google Sheets with URL

### 2. Trading Strategies (every 30min during market hours)

#### Wheel Strategy (official Alpaca implementation)
- **Step 1:** Sell Cash-Secured Puts on stocks you want to own
- **Step 2:** If assigned → own the stock
- **Step 3:** Sell Covered Calls on owned shares
- **Step 4:** If called away → back to Step 1
- **Sentiment filter:** Skips stocks with >85% negative news in last 24hrs
- Account: `options-paper` (~$980k)

#### Cash-Secured Put (CSP)
- Sells PUTs 10-15% below current price
- DTE: 21-45 days, Delta: 0.20-0.25
- Closes at 50% profit or 2× loss
- Separate paper account for clean P&L tracking
- Account: `csp-paper` ($100k fresh)

### 3. Daily P&L Report (4pm ET)
- Shows equity, today's P&L, total P&L vs $100k start
- Lists all open option positions with unrealized gains/losses
- Sent to Telegram at market close

## Trading Rules (enforced by BaseStrategy)

| Rule | Value |
|------|-------|
| Max position size | 20% of account |
| Max open positions | 5 |
| Daily loss limit | 2% → halt trading |
| Profit target | 50% of premium |
| Stop loss | 2× premium collected |
| Close before expiry | 7 days |

## Running Locally

```bash
# News digest
python news_bot.py

# Trading strategies (market must be open)
python run_strategy.py --strategy csp
python run_strategy.py --strategy wheel

# P&L report
python daily_report.py
```

## Credentials

Local files in `~/.alpaca/`:
```
options-paper.env   # main account + Telegram/Sheets creds
csp-paper.env       # CSP strategy account
```

GitHub Secrets:
```
ALPACA_API_KEY / ALPACA_SECRET_KEY          # main account
ALPACA_CSP_API_KEY / ALPACA_CSP_SECRET_KEY  # CSP account
TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
HF_TOKEN                                    # HuggingFace (FinBERT + Llama)
GOOGLE_CREDENTIALS / GOOGLE_SHEET_ID        # Google Sheets
```

## GitHub Actions Schedule

| Time (UTC) | ET | Job |
|---|---|---|
| 12:00 Mon-Fri | 8am | 🌅 Morning digest (18hrs of news) |
| 17:00 Mon-Fri | 12pm | 📊 Midday digest (5hrs) |
| 21:00 Mon-Fri | 4pm | 🌆 EOD digest + P&L report |
| 13:00 Mon-Fri | 9am | ⚙️ Open new positions |
| Every 30min 13-21 Mon-Fri | 9am-5pm | ⚙️ Check exits |

## Strategy Parameters (`strategy_config/params.py`)

All thresholds in one place:
```python
DELTA_MIN/MAX    = 0.20-0.30   # option moneyness
DTE_MIN/MAX      = 21-45       # days to expiry
CSP_OTM_MIN/MAX  = 10-15%      # how far below price
PROFIT_TARGET    = 50%         # close at 50% profit
STOP_LOSS_MULT   = 2.0         # close if loss > 2× premium
MAX_POSITIONS    = 5           # max open at once
MAX_POSITION_PCT = 20%         # max per trade
MAX_DAILY_LOSS   = 2%          # halt if down 2% today
```

## What's Next (TODO)

- [ ] `strategies/covered_call.py` - standalone covered call strategy
- [ ] `strategies/bull_put.py` - bull put spread (capital efficient)
- [ ] Backtesting on historical data before live
- [ ] Performance dashboard (win rate, Sharpe ratio per strategy)
- [ ] Live trading after 4-5 months paper validation
- [ ] Add more paper accounts per strategy for clean comparison
