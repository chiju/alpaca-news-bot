# Alpaca Portfolio Bot

AI-powered portfolio news digest + automated options trading strategies.

## Architecture

```
alpaca-news-bot/
│
├── news_bot.py          # Main news digest orchestrator
├── run_strategy.py      # Strategy runner (all strategies)
├── config_loader.py     # Credential loader (local + GitHub Actions)
│
├── core/
│   ├── broker.py        # Alpaca API facade (single entry point)
│   └── risk.py          # Position sizing + daily loss limits
│
├── strategies/
│   ├── base.py          # Base class (rules enforcement)
│   ├── csp.py           # Cash-Secured Put
│   ├── covered_call.py  # Covered Call (TODO)
│   └── bull_put.py      # Bull Put Spread (TODO)
│
├── strategy_config/
│   └── params.py        # All strategy parameters (single source of truth)
│
├── fetcher.py           # Alpaca news fetcher
├── sentiment.py         # FinBERT + Llama summary
├── history.py           # SQLite + Google Sheets history
├── notifier.py          # Telegram sender
├── reddit.py            # Reddit sentiment
└── options_flow.py      # Unusual options activity
```

## News Digest

Runs 3x/day (morning 8am ET, midday 12pm ET, EOD 4pm ET):
- Fetches news from Alpaca (Benzinga)
- FinBERT sentiment analysis per headline
- Llama 3.1 4-line summary
- Reddit buzz tracking
- Unusual options flow detection
- Sends to Telegram with 🟢🔴⚪ signals
- Logs to Google Sheets with URL

## Trading Strategies

Runs every 30min during market hours (9am-5pm ET):

### Cash-Secured Put (CSP)
- Sell PUT 10-15% below current price
- DTE: 30-45 days, Delta: 0.20-0.25
- Close at 50% profit or 2x loss
- Separate paper account for isolation

### Covered Call (coming)
- Sell call on owned 100+ share positions
- Delta 0.20-0.35, DTE 21-45 days

### Bull Put Spread (coming)
- Sell higher PUT + buy lower PUT
- Capital efficient ($500 vs $15,000 for CSP)

## Running Locally

```bash
# News digest
python news_bot.py

# Strategy (market must be open)
python run_strategy.py --strategy csp
python run_strategy.py --strategy covered_call
python run_strategy.py --strategy bull_put
```

## Credentials

Local: `~/.alpaca/{strategy}-paper.env`
```
ALPACA_API_KEY=xxx
ALPACA_SECRET_KEY=xxx
```

GitHub Actions: Set secrets `ALPACA_CSP_API_KEY`, `ALPACA_CSP_SECRET_KEY` etc.

## GitHub Actions Schedule

| Time (UTC) | ET | Job |
|---|---|---|
| 12:00 Mon-Fri | 8am | 🌅 Morning digest |
| 17:00 Mon-Fri | 12pm | 📊 Midday digest |
| 21:00 Mon-Fri | 4pm | 🌆 EOD digest |
| Every 30min 13-21 Mon-Fri | 9am-5pm | ⚙️ Trading engines |

## Strategy Parameters (`strategy_config/params.py`)

All thresholds in one place - change here, applies everywhere:
- `DELTA_MIN/MAX` = 0.20-0.30
- `DTE_MIN/MAX` = 21-45 days
- `PROFIT_TARGET` = 50%
- `STOP_LOSS_MULT` = 2x premium
- `MAX_POSITIONS` = 5
- `MAX_POSITION_PCT` = 20% of account
