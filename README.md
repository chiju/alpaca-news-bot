# Alpaca Portfolio Bot 🤖

> News intelligence + automated paper trading strategies.
> Companion repo to [options-flow-scanner](https://github.com/chiju/options-flow-scanner).

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   ALPACA PORTFOLIO BOT                       │
│                                                              │
│  📰 NEWS INTELLIGENCE          🤖 TRADING ENGINE            │
│  ─────────────────             ──────────────────           │
│  Alpaca News API               3 active paper accounts      │
│       ↓                                                      │
│  FinBERT Sentiment             Bull-Put   ($101K) ✅        │
│  (🟢🔴⚪ per headline)         Iron-Condor($101K) ✅        │
│       ↓                        Covered-Call($101K) ✅       │
│  Groq Llama Summary                   ↓                     │
│       ↓                        Sentiment Filter             │
│  Reddit Buzz                   (blocks >85% negative)       │
│       ↓                               ↓                     │
│  Telegram Digest               Alpaca Paper Trading         │
│  (5x/day)                                                   │
│                                                              │
│  📊 PERFORMANCE TRACKING                                    │
│  ──────────────────                                         │
│  NEWS_SEEN (Google Sheets) — dedup across runs              │
│  Per-symbol tabs — sentiment history                        │
│  PERFORMANCE_LOG — daily P&L                                │
└──────────────────────────────────────────────────────────────┘
```

---

## Active Strategies

| Strategy | Balance | Status |
|----------|---------|--------|
| Bull-Put | $101K | ✅ Active |
| Iron-Condor | $101K | ✅ Active |
| Covered-Call | $101K | ✅ Active |
| ~~Wheel~~ | — | ❌ Disabled (account gone) |
| ~~CSP~~ | — | ❌ Disabled (flow_trader handles) |

**Note:** All API keys are stored as GitHub Secrets. No keys are hardcoded in the repo.

---

## News Coverage

**Portfolio (owned stocks):**
```
POET, AMZN, NVDA, UUUU, PLTR, TSLA, SOFI, META,
ACHR, IONQ, PATH, JOBY, OKLO, PYPL, LAES, CRWV, DUOL, MSFT
```

**Watchlist (monitoring for flow signals):**
```
SMCI, ASTS, NBIS, RMBS, AVGO, NFLX, UBER, CRM
```

---

## Schedule (cron-job.org → GitHub Actions)

| UTC | Berlin | ET | Job | What runs |
|-----|--------|-----|-----|-----------|
| 9:00-23:00 | 11am-1am | 5am-7pm | `digest` (hourly) | News digest every hour |
| 13:00-20:00 | 3pm-10pm | 9am-4pm | `trading` (every 30min) | 3 trading strategies |
| 20:00 | 22:00 | 4pm | `report` | EOD P&L report |
| 10:00 Sat+Sun | 12:00 | 6am | `digest` | Weekend digest |

---

## News Dedup

Uses Google Sheets (`NEWS_SEEN` tab) as filesystem — persists across GitHub Actions runs.
Same URL won't appear twice in the same day regardless of how many times the job runs.

---

## Key Files

| File | Purpose |
|------|---------|
| `news_bot.py` | Main news digest — FinBERT + Groq + Reddit |
| `run_strategy.py` | Trading engine runner |
| `history.py` | Sentiment persistence (Google Sheets only, no SQLite) |
| `sentiment.py` | FinBERT model |
| `strategies/bull_put.py` | Bull put spread strategy |
| `strategies/iron_condor.py` | Iron condor strategy |
| `strategies/covered_call.py` | Covered call strategy |

---

## Disclaimer
Educational and research purposes only. Not financial advice.
