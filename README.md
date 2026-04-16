# Alpaca Portfolio Bot 🤖

> News intelligence + automated paper trading strategies.
> Companion repo to [options-flow-scanner](https://github.com/chiju/options-flow-scanner).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   ALPACA PORTFOLIO BOT                       │
│                                                              │
│  📰 NEWS INTELLIGENCE          🤖 TRADING ENGINE            │
│  ─────────────────             ──────────────────           │
│  Alpaca News API               5 isolated paper accounts    │
│       ↓                                                      │
│  FinBERT Sentiment             Wheel      ($980K)           │
│  (🟢🔴⚪ per headline)         CSP        ($100K)           │
│       ↓                        Bull-Put   ($100K)           │
│  Groq Llama Summary            Iron-Condor($100K)           │
│       ↓                        Covered-Call($100K)          │
│  Reddit Buzz                          ↓                     │
│       ↓                        Sentiment Filter             │
│  Telegram Digest               (blocks >85% negative)       │
│  (5x/day)                             ↓                     │
│                                Alpaca Paper Trading         │
│                                                              │
│  📊 PERFORMANCE TRACKING                                    │
│  ──────────────────                                         │
│  PERFORMANCE_LOG (Google Sheets)                            │
│  Daily equity + P&L per strategy                            │
│  Win rate + position sizing compliance                      │
│  Trade Journal                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Schedule (cron-job.org → GitHub Actions)

| Berlin time | ET | Job input | What runs |
|------------|-----|-----------|-----------|
| 14:00 | 8:00am | `digest` | Morning news digest |
| 16:00 | 10:00am | `digest` | Late morning digest |
| 18:00 | 12:00pm | `digest` | Midday digest |
| 20:00 | 2:00pm | `digest` | Afternoon digest |
| 22:00 | 4:00pm | `report` | EOD digest + P&L report |
| Every 30min 15:00-22:00 | 9am-4pm | `trading` | All 5 trading engines |

---

## News Digest (5x/day)

1. Fetch headlines from Alpaca News API (Benzinga source)
2. **FinBERT** scores each headline: 🟢 positive / 🔴 negative / ⚪ neutral
3. **Groq Llama** generates 4-line market summary
4. Reddit buzz (r/wallstreetbets, r/stocks, r/investing)
5. Telegram digest with trend dots (last 3 sentiment readings)

Sentiment filter: blocks stocks with >85% negative news from trading.

---

## Trading Strategies

### Wheel ($980K account)
```
Phase 1: Sell Cash-Secured Put → collect premium
Phase 2: If assigned → own 100 shares
Phase 3: Sell Covered Call → collect premium
Phase 4: If called away → back to Phase 1
```
Currently: 18 stock positions + 6 covered calls open.

### CSP — Cash-Secured Put ($100K)
Sell puts 10-15% below price, DTE 21-45, delta 0.20-0.25.
Close at 50% profit or 2× loss.

### Bull-Put Spread ($100K)
Sell put at strike A, buy put at strike B ($5 below).
Max loss capped. Capital efficient.

### Iron Condor ($100K)
Sell put spread + call spread. Profit if price stays in range.

### Covered Call ($100K)
Own 100 shares, sell OTM calls. Collect premium, cap upside.
Currently holds: PLTR, SOFI, PYPL, OKLO, IONQ (100 shares each).

---

## Risk Rules (all strategies)

| Rule | Value |
|------|-------|
| Max position size | 20% of account |
| Max open positions | 5 |
| Daily loss limit | 2% → halt trading |
| Profit target | 50% of premium |
| Stop loss | 2× premium collected |
| Close before expiry | 7 days |

---

## Performance Tracking

**PERFORMANCE_LOG** sheet updated daily at EOD:

| Column | What |
|--------|------|
| `*_equity` | Equity per strategy |
| `*_pnl` | P&L vs starting capital |
| `total_equity` | All 5 accounts combined |
| `win_rate_pct` | % of positions currently profitable |
| `max_position_pct` | Largest position as % of account |
| `position_sizing_ok` | ✅ if all within 20% limit |
| `avg_unrealized_pnl_pct` | Average unrealized gain/loss % |

**Current performance (Apr 16, 2026):**
- Wheel: $1,013,765 (+$33,765)
- CSP: $101,318 (+$1,318)
- Bull-Put: $100,570 (+$570)
- Iron-Condor: $101,164 (+$1,164)
- Covered-Call: $99,949 (-$51, just started)
- **Total: $1,416,766 (+$36,766)**

---

## Paper Accounts

| Strategy | Env Key | Account ID |
|----------|---------|-----------|
| Wheel | `ALPACA_API_KEY` | PK7ITJL... |
| CSP | `ALPACA_CSP_API_KEY` | PKIINOW... |
| Bull-Put | `ALPACA_BULL_PUT_SPREAD_API_KEY` | PK6HIZA... |
| Iron-Condor | `ALPACA_IRON_CONDOR_API_KEY` | PKCFSO4... |
| Covered-Call | `ALPACA_COVERED_CALL_API_KEY` | PKOKKG... |

---

## Files

| File | Purpose |
|------|---------|
| `news_bot.py` | News digest orchestrator |
| `run_strategy.py` | Strategy runner entry point |
| `daily_report.py` | Daily P&L report + PERFORMANCE_LOG snapshot |
| `config_loader.py` | Load account credentials per strategy |
| `fetcher.py` | Alpaca News API wrapper |
| `sentiment.py` | FinBERT + Groq summary |
| `history.py` | SQLite sentiment history + Google Sheets |
| `reddit.py` | Reddit sentiment (no API key needed) |
| `notifier.py` | Telegram sender |
| `strategies/csp.py` | Cash-Secured Put |
| `strategies/bull_put.py` | Bull Put Spread |
| `strategies/covered_call.py` | Covered Call |
| `strategies/iron_condor.py` | Iron Condor |
| `wheel/` | Official Alpaca wheel strategy |

---

## Local Setup

```bash
source ~/.alpaca/options-paper.env
cd ~/stocks/alpaca-news-bot
source ~/stocks/options-flow-scanner/.venv/bin/activate

python news_bot.py                          # news digest
python run_strategy.py --strategy csp       # CSP engine
python run_strategy.py --strategy wheel     # Wheel engine
python daily_report.py                      # P&L report
```

---

## Disclaimer
Paper trading only. Not financial advice. Options trading involves significant risk.
