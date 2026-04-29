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

| Strategy | Account | Balance | Status |
|----------|---------|---------|--------|
| Bull-Put | PK6HIZAWDB7W7WPZ6U7243344G | $101K | ✅ Active |
| Iron-Condor | PKCFSO4B3LTZSGAXFLZBJM2BSV | $101K | ✅ Active |
| Covered-Call | PKOKKGGWWHIHRI67SUHVQPFGDN | $101K | ✅ Active |
| ~~Wheel~~ | ~~PK7ITJLLP2542TQFJ2QZTM4B4I~~ | $0 | ❌ Disabled (account gone) |
| ~~CSP~~ | — | — | ❌ Disabled (flow_trader handles) |

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

| Berlin time | ET | Job | What runs |
|------------|-----|-----|-----------|
| 14:00 | 8:00am | `digest` | Morning news digest |
| 16:00 | 10:00am | `digest` | Late morning digest |
| 18:00 | 12:00pm | `digest` | Midday digest |
| 20:00 | 2:00pm | `digest` | Afternoon digest |
| 22:00 | 4:00pm | `report` | EOD digest + P&L report |
| Every 30min 15:00-22:00 | 9am-4pm | `trading` | 3 trading engines |
| 12:00 Sat+Sun | 6am | `digest` | Weekend digest |

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
